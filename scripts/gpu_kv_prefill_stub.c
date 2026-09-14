/* Accept indexed writes to isolate the real Align wrapper's interval admission. */
#define ALIGN_GGML_STUB_ENGINE 1
#define ALIGN_GGML_STUB_GPU 1
#define align_gpu_kv_prefill_indexed fixture_original_prefill_indexed
#define align_gpu_kv_write_indexed_prefix fixture_original_indexed_prefix
#include "ggml_shim_stub.c"
#undef align_gpu_kv_prefill_indexed
#undef align_gpu_kv_write_indexed_prefix
int32_t align_gpu_kv_prefill_indexed(void *owner) { return owner != NULL; }
int32_t align_gpu_kv_write_indexed_prefix(void *owner, int64_t index, int32_t kind,
        int32_t layout, int64_t indices, int64_t width, void *slots, int64_t out, int64_t source) {
    (void) index; (void) layout; (void) indices; (void) width; (void) slots; (void) out; (void) source;
    return owner != NULL && kind == ALIGN_GPU_GRAPH_PREFILL ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}
