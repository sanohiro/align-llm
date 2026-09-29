/* Diagnostic capture of the final one-token Qwen3.5 Q4_0 FFN on Linux.
 * Build: cc -O2 -Wall -Wextra -Werror -shared -fPIC -I GGML/ggml/include \
 *   scripts/capture-q4-ffn.c -o capture-q4-ffn.so -ldl
 * Set ALIGN_Q4_FFN_CAPTURE to an existing empty directory and LD_PRELOAD this
 * library for one ordinary (non-native-SwiGLU) request with a decode token.
 * Never preload it during timing. Files appear only after a successful graph.
 */
#include "ggml.h"
#include "ggml-backend.h"
#include <dirent.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void require(int ok, const char *message) {
    if (!ok) { fprintf(stderr, "Q4_FFN_CAPTURE error=%s\n", message); abort(); }
}

static int vector_f32(const struct ggml_tensor *t, int64_t length) {
    return t && t->type == GGML_TYPE_F32 && ggml_is_vector(t) &&
        ggml_is_contiguous(t) && t->ne[0] == length &&
        ggml_nbytes(t) == (size_t) length * sizeof(float);
}

static int q4_weight(const struct ggml_tensor *t, int64_t width, int64_t rows) {
    return t && t->type == GGML_TYPE_Q4_0 && ggml_is_matrix(t) &&
        ggml_is_contiguous(t) && t->ne[0] == width && t->ne[1] == rows &&
        ggml_nbytes(t) == 7077888;
}

static int matvec(const struct ggml_tensor *t, int64_t width, int64_t rows) {
    return t && t->op == GGML_OP_MUL_MAT &&
        q4_weight(t->src[0], width, rows) &&
        vector_f32(t->src[1], width) && vector_f32(t, rows);
}

static int final_ffn(const struct ggml_tensor *t) {
    if (!matvec(t, 6144, 2048)) return 0;
    const struct ggml_tensor *gated = t->src[1];
    return gated->op == GGML_OP_GLU && gated->src[0] && gated->src[1] &&
        matvec(gated->src[0], 2048, 6144) &&
        matvec(gated->src[1], 2048, 6144) &&
        gated->src[0]->src[1] == gated->src[1]->src[1];
}

static struct ggml_tensor *select_final(struct ggml_cgraph *graph) {
    struct ggml_tensor *selected = NULL;
    int head_index = -1;
    for (int i = 0; i < ggml_graph_n_nodes(graph); ++i) {
        struct ggml_tensor *t = ggml_graph_node(graph, i);
        if (t->op == GGML_OP_MUL_MAT && t->src[0] && t->src[1] &&
            (t->flags & GGML_TENSOR_FLAG_OUTPUT) &&
            t->src[0]->type == GGML_TYPE_Q6_K &&
            t->src[0]->ne[0] == 2048 && t->src[0]->ne[1] == 248320 &&
            vector_f32(t->src[1], 2048) && vector_f32(t, 248320)) {
            require(head_index < 0, "ambiguous final output head");
            head_index = i;
        }
    }
    if (head_index < 0) return NULL;
    for (int i = 0; i < head_index; ++i) {
        struct ggml_tensor *t = ggml_graph_node(graph, i);
        if (final_ffn(t)) selected = t;
    }
    return selected;
}

void ggml_build_forward_expand(struct ggml_cgraph *graph, struct ggml_tensor *tensor) {
    typedef void (*expand_fn)(struct ggml_cgraph *, struct ggml_tensor *);
    static expand_fn original;
    if (!original) {
        void *symbol = dlsym(RTLD_NEXT, "ggml_build_forward_expand");
        require(symbol != NULL, "graph expansion symbol unavailable");
        memcpy(&original, &symbol, sizeof(original));
    }
    original(graph, tensor);
    if (!getenv("ALIGN_Q4_FFN_CAPTURE")) return;
    struct ggml_tensor *down = select_final(graph);
    if (!down) return; /* Some partial prefill graphs have no one-token FFN. */
    struct ggml_tensor *gated = down->src[1];
    ggml_set_output(gated->src[0]->src[1]);
    ggml_set_output(gated->src[0]);
    ggml_set_output(gated->src[1]);
    ggml_set_output(gated);
    ggml_set_output(down);
}

static FILE *create(const char *directory, const char *name) {
    char path[4096];
    int length = snprintf(path, sizeof(path), "%s/%s", directory, name);
    require(length > 0 && length < (int) sizeof(path), "path too long");
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    require(fd >= 0, "capture exists or cannot be created");
    FILE *file = fdopen(fd, "wb");
    require(file != NULL, "fdopen failed");
    return file;
}

static void save(const char *dir, const char *name, const struct ggml_tensor *t,
                 size_t expected, int finite) {
    require(t && ggml_nbytes(t) == expected, "tensor size mismatch");
    FILE *file = create(dir, name);
    unsigned char bytes[16384];
    for (size_t offset = 0; offset < expected;) {
        size_t count = expected - offset < sizeof(bytes) ? expected - offset : sizeof(bytes);
        ggml_backend_tensor_get(t, bytes, offset, count);
        if (finite) {
            require(count % sizeof(float) == 0, "F32 chunk misaligned");
            for (size_t i = 0; i < count; i += sizeof(float)) {
                float value;
                memcpy(&value, bytes + i, sizeof(value));
                require(isfinite(value), "nonfinite F32 value");
            }
        }
        require(fwrite(bytes, 1, count, file) == count, "capture write failed");
        offset += count;
    }
    require(fclose(file) == 0, "capture close failed");
}

int32_t align_gpu_graph_compute(void *owner, int32_t kind, const void *key,
                                int64_t length, void *value) {
    typedef int32_t (*compute_fn)(void *, int32_t, const void *, int64_t, void *);
    static compute_fn original;
    if (!original) {
        void *symbol = dlsym(RTLD_NEXT, "align_gpu_graph_compute");
        require(symbol != NULL, "graph compute symbol unavailable");
        memcpy(&original, &symbol, sizeof(original));
    }
    int32_t status = original(owner, kind, key, length, value);
    const char *dir = getenv("ALIGN_Q4_FFN_CAPTURE");
    static int captured;
    if (status || !dir || captured || (kind != 1 && kind != 2)) return status;
    struct ggml_tensor *down = select_final((struct ggml_cgraph *) value);
    require(down != NULL, "decode graph has no final Q4_0 FFN");
    struct ggml_tensor *gated = down->src[1];
    struct ggml_tensor *gate = gated->src[0], *up = gated->src[1];
    require((down->flags & GGML_TENSOR_FLAG_OUTPUT) &&
            (gated->flags & GGML_TENSOR_FLAG_OUTPUT) &&
            (gate->flags & GGML_TENSOR_FLAG_OUTPUT) &&
            (up->flags & GGML_TENSOR_FLAG_OUTPUT) &&
            (gate->src[1]->flags & GGML_TENSOR_FLAG_OUTPUT),
            "FFN values were not retained before allocation");
    DIR *directory = opendir(dir);
    require(directory != NULL, "capture directory unavailable");
    struct dirent *entry;
    while ((entry = readdir(directory)) != NULL)
        require(strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0,
                "capture directory must be empty");
    require(closedir(directory) == 0, "capture directory close failed");
    FILE *meta = create(dir, "geometry.txt");
    require(fputs("q4-ffn-capture-v1 2048 6144 18\n", meta) >= 0 &&
            fclose(meta) == 0, "geometry write failed");
    save(dir, "gate.bin", gate->src[0], 7077888, 0);
    save(dir, "up.bin", up->src[0], 7077888, 0);
    save(dir, "down.bin", down->src[0], 7077888, 0);
    save(dir, "input.bin", gate->src[1], 8192, 1);
    save(dir, "gated.bin", gated, 24576, 1);
    save(dir, "output.bin", down, 8192, 1);
    FILE *done = create(dir, "complete.txt");
    require(fputs("1\n", done) >= 0 && fclose(done) == 0, "completion write failed");
    captured = 1;
    fprintf(stderr, "Q4_FFN_CAPTURE kind=%d final_decode_ffn=1\n", kind);
    return status;
}
