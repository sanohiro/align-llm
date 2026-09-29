/* Independent Q6_K output-projection capture; never load during a timing run.
 * Build: clang -O2 -dynamiclib -undefined dynamic_lookup -I GGML/ggml/include \
 *   scripts/capture-q6-projection.c -o capture-q6-projection.dylib
 * Linux: cc -O2 -shared -fPIC -I GGML/ggml/include \
 *   scripts/capture-q6-projection.c -o capture-q6-projection.so -ldl
 * Set ALIGN_Q6_CAPTURE to a new, existing empty directory and inject with
 * DYLD_INSERT_LIBRARIES or LD_PRELOAD. Run one prompt producing a final projection and
 * at least three generated tokens. Retains one prefill and two decode projections;
 * nonfinal prefill graphs without a projection are allowed.
 * Align diagnostic strings are not ggml tensor names: select the unique Q6_K
 * vector MUL_MAT marked as a graph output, and refuse ambiguous/missing captures.
 */
#include "ggml.h"
#include "ggml-backend.h"
#if !defined(__APPLE__)
#include <dlfcn.h>
#endif
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#if defined(__APPLE__)
#define INTERPOSE(replacement, original) \
    __attribute__((used)) static struct { const void *a; const void *b; } \
    interpose_##original __attribute__((section("__DATA,__interpose"))) = \
        { (const void *)&replacement, (const void *)&original }
#else
#define INTERPOSE(replacement, original)
#endif

static void require(int ok, const char *message) {
    if (!ok) { fprintf(stderr, "Q6_CAPTURE error=%s\n", message); abort(); }
}

static int projection(const struct ggml_tensor *t) {
    return t->op == GGML_OP_MUL_MAT && (t->flags & GGML_TENSOR_FLAG_OUTPUT) &&
        t->src[0] && t->src[1] && t->src[0]->type == GGML_TYPE_Q6_K &&
        t->src[1]->type == GGML_TYPE_F32 && t->type == GGML_TYPE_F32 &&
        ggml_is_matrix(t->src[0]) && ggml_is_vector(t->src[1]) && ggml_is_vector(t) &&
        ggml_is_contiguous(t->src[0]) && ggml_is_contiguous(t->src[1]) &&
        ggml_is_contiguous(t) && t->src[0]->ne[0] == t->src[1]->ne[0] &&
        t->src[0]->ne[1] == t->ne[0];
}

static void capture_expand(struct ggml_cgraph *graph, struct ggml_tensor *tensor) {
#if defined(__APPLE__)
    ggml_build_forward_expand(graph, tensor);
#else
    typedef void (*expand_fn)(struct ggml_cgraph *, struct ggml_tensor *);
    static expand_fn original;
    if (!original) {
        void *symbol = dlsym(RTLD_NEXT, "ggml_build_forward_expand");
        require(symbol != NULL, "graph expansion symbol unavailable");
        memcpy(&original, &symbol, sizeof(original));
    }
    original(graph, tensor);
#endif
    if (!getenv("ALIGN_Q6_CAPTURE")) return;
    for (int i = 0; i < ggml_graph_n_nodes(graph); ++i) {
        struct ggml_tensor *t = ggml_graph_node(graph, i);
        if (projection(t)) ggml_set_output(t->src[1]);
    }
}
INTERPOSE(capture_expand, ggml_build_forward_expand);

static FILE *create(const char *directory, const char *name) {
    char path[4096];
    require(snprintf(path, sizeof(path), "%s/%s", directory, name) < (int)sizeof(path), "path too long");
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    require(fd >= 0, "capture exists or cannot be created");
    FILE *file = fdopen(fd, "wb");
    require(file != NULL, "capture fdopen failed");
    return file;
}

static void save(const char *dir, const char *name, const struct ggml_tensor *t) {
    FILE *file = create(dir, name);
    const size_t chunk = 1024 * 1024, size = ggml_nbytes(t);
    void *bytes = malloc(chunk);
    require(bytes != NULL, "capture scratch allocation failed");
    for (size_t offset = 0; offset < size;) {
        size_t count = size - offset < chunk ? size - offset : chunk;
        ggml_backend_tensor_get(t, bytes, offset, count);
        require(fwrite(bytes, 1, count, file) == count, "capture write failed");
        offset += count;
    }
    free(bytes);
    require(fclose(file) == 0, "capture close failed");
}

extern int32_t align_gpu_graph_compute(void *, int32_t, const void *, int64_t, void *);
static int32_t capture_compute(void *owner, int32_t kind, const void *key,
                               int64_t length, void *value) {
#if defined(__APPLE__)
    int32_t status = align_gpu_graph_compute(owner, kind, key, length, value);
#else
    typedef int32_t (*compute_fn)(void *, int32_t, const void *, int64_t, void *);
    static compute_fn original;
    if (!original) {
        void *symbol = dlsym(RTLD_NEXT, "align_gpu_graph_compute");
        require(symbol != NULL, "graph compute symbol unavailable");
        memcpy(&original, &symbol, sizeof(original));
    }
    int32_t status = original(owner, kind, key, length, value);
#endif
    static unsigned ordinal;
    static int64_t width, rows;
    static const void *captured_owner, *weight_data;
    const char *dir = getenv("ALIGN_Q6_CAPTURE");
    if (status || !dir || ordinal == 3) return status;
    struct ggml_cgraph *graph = value;
    struct ggml_tensor *output = NULL;
    for (int i = 0; i < ggml_graph_n_nodes(graph); ++i) {
        struct ggml_tensor *t = ggml_graph_node(graph, i);
        if (projection(t)) {
            require(output == NULL, "ambiguous Q6_K graph output");
            output = t;
        }
    }
    if (!output) {
        require(kind == 0, "decode graph has no Q6_K output projection");
        return status; /* Nonfinal prefill deliberately has no head. */
    }
    require((ordinal == 0 && kind == 0) || (ordinal > 0 && (kind == 1 || kind == 2)),
            "expected one prefill followed by two decode projections");
    require((output->src[1]->flags & GGML_TENSOR_FLAG_OUTPUT) != 0,
            "activation was not retained before graph allocation");
    if (ordinal == 0) {
        captured_owner = owner; weight_data = output->src[0]->data;
        width = output->src[0]->ne[0]; rows = output->src[0]->ne[1];
        require(width >= 256 && width <= 65536 && width % 256 == 0 && rows >= 3 &&
                rows <= 1048576 && ggml_nbytes(output->src[0]) <= 2147483648ULL,
                "capture geometry exceeds probe limits");
        FILE *meta = create(dir, "geometry.txt");
        require(fprintf(meta, "q6-capture-v1 %lld %lld 14\n", (long long)width,
                        (long long)rows) > 0 && fclose(meta) == 0, "metadata write failed");
        save(dir, "weights.bin", output->src[0]);
    }
    require(owner == captured_owner && output->src[0]->data == weight_data,
            "capture session or retained weights changed");
    require(width == output->src[0]->ne[0] && rows == output->src[0]->ne[1], "capture geometry changed");
    char name[64];
    snprintf(name, sizeof(name), "%u-input.bin", ordinal); save(dir, name, output->src[1]);
    snprintf(name, sizeof(name), "%u-output.bin", ordinal); save(dir, name, output);
    snprintf(name, sizeof(name), "%u-kind.txt", ordinal);
    FILE *meta = create(dir, name);
    require(fprintf(meta, "%d\n", kind) > 0 && fclose(meta) == 0, "kind write failed");
    fprintf(stderr, "Q6_CAPTURE ordinal=%u kind=%d width=%lld rows=%lld input_bytes=%zu output_bytes=%zu\n",
            ordinal, kind, (long long)width, (long long)rows,
            ggml_nbytes(output->src[1]), ggml_nbytes(output));
    ++ordinal;
    if (ordinal == 3) {
        FILE *done = create(dir, "complete.txt");
        require(fputs("3\n", done) >= 0 && fclose(done) == 0, "completion write failed");
    }
    return status;
}
INTERPOSE(capture_compute, align_gpu_graph_compute);

#if !defined(__APPLE__)
void ggml_build_forward_expand(struct ggml_cgraph *graph, struct ggml_tensor *tensor) {
    capture_expand(graph, tensor);
}

int32_t align_gpu_graph_compute(void *owner, int32_t kind, const void *key,
                                int64_t length, void *value) {
    return capture_compute(owner, kind, key, length, value);
}
#endif
