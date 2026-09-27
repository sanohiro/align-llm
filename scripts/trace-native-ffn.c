/* Independent macOS graph-phase timing interposer; excluded from production.
 * Build against the measured shim and ggml bundle; DYLD_INSERT_LIBRARIES loads it.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t) ts.tv_sec * 1000000000ULL + (uint64_t) ts.tv_nsec;
}

#define INTERPOSE(replacement, original) \
    __attribute__((used)) static struct { const void *a; const void *b; } \
    interpose_##original __attribute__((section("__DATA,__interpose"))) = \
        { (const void *)(unsigned long)&replacement, (const void *)(unsigned long)&original }

extern int32_t align_gpu_graph_compute(void *, int32_t, const void *, int64_t, void *);
static int32_t timed_graph_compute(void *owner, int32_t kind, const void *key, int64_t length, void *graph) {
    uint64_t start = now_ns();
    int32_t result = align_gpu_graph_compute(owner, kind, key, length, graph);
    fprintf(stderr, "Q35_TIMING graph_kind=%d elapsed_ns=%llu status=%d\n", kind,
            (unsigned long long) (now_ns() - start), result);
    return result;
}
INTERPOSE(timed_graph_compute, align_gpu_graph_compute);

extern int ggml_backend_graph_compute(void *, void *);
static int timed_backend_compute(void *backend, void *graph) {
    uint64_t start = now_ns();
    int result = ggml_backend_graph_compute(backend, graph);
    fprintf(stderr, "Q35_TIMING backend_compute_ns=%llu status=%d\n",
            (unsigned long long) (now_ns() - start), result);
    return result;
}
INTERPOSE(timed_backend_compute, ggml_backend_graph_compute);

extern void ggml_backend_tensor_get(const void *, void *, size_t, size_t);
static void timed_tensor_get(const void *tensor, void *data, size_t offset, size_t size) {
    uint64_t start = now_ns();
    ggml_backend_tensor_get(tensor, data, offset, size);
    /* Optional diagnostic capture. Never set this during timing. */
    const char *directory = getenv("ALIGN_FFN_LOGITS_DIR");
    const char *extent = getenv("ALIGN_FFN_LOGITS_BYTES");
    if (directory && extent && offset == 0 && size == strtoull(extent, NULL, 10)) {
        static unsigned ordinal = 0;
        char path[4096];
        if (snprintf(path, sizeof(path), "%s/%04u.bin", directory, ordinal++) >= (int)sizeof(path)) abort();
        FILE *file = fopen(path, "wb");
        if (!file || fwrite(data, 1, size, file) != size || fclose(file)) abort();
    }
    fprintf(stderr, "Q35_TIMING tensor_get_bytes=%zu elapsed_ns=%llu\n", size,
            (unsigned long long) (now_ns() - start));
}
INTERPOSE(timed_tensor_get, ggml_backend_tensor_get);
