/* Real pinned-backend attention capability, ownership, mask and Flash arithmetic owner. */
#include <assert.h>
#include "ggml_shim.c"

int main(int argc, char **argv) {
    assert(argc == 2);
    ggml_backend_reg_t registry = ggml_backend_load(argv[1]);
    assert(registry != NULL && ggml_backend_reg_dev_count(registry) == 1);
    ggml_backend_dev_t device = ggml_backend_reg_dev_get(registry, 0);
    ggml_backend_t backend = ggml_backend_dev_init(device, NULL);
    assert(backend != NULL);
    printf("GPU attention device: %s %s\n", ggml_backend_reg_name(registry), ggml_backend_dev_name(device));
    struct align_gpu_device_state owner = {0};
    owner.device = device;
    owner.backend = backend;
    assert(align_gpu_attention_policy(&owner) == 0);
    assert(align_gpu_attention_probe(&owner, 2, 256, 128, 4, 2) == 1);
    assert(align_gpu_attention_probe(&owner, 2, 256, 33, 4, 2) == 0);
    assert(align_gpu_attention_probe(&owner, 0, 256, 128, 4, 2) == ALIGN_GPU_CONFIG);
    assert(align_gpu_attention_probe(&owner, 2, 256, 128, 3, 2) == ALIGN_GPU_CONFIG);
    assert(owner.memory_allocated == 0 && owner.weights_uploaded == 0);
    assert(align_gpu_attention_select(&owner, 1) == ALIGN_GPU_OK);
    assert(align_gpu_plan_begin(&owner) == ALIGN_GPU_OK);
    assert(align_gpu_attention_select(&owner, 0) == ALIGN_GPU_CONFIG);
    assert(align_gpu_attention_probe(&owner, 2, 256, 128, 4, 2) == ALIGN_GPU_CONFIG);
    assert(align_gpu_plan_cancel(&owner) == ALIGN_GPU_OK);
    assert(align_gpu_attention_policy(&owner) == 1);
    assert(align_gpu_attention_select(&owner, 2) == ALIGN_GPU_CONFIG);

    struct ggml_init_params params = {ggml_tensor_overhead() * 32 + ggml_graph_overhead_custom(32, false), NULL, true};
    struct ggml_context *ctx = ggml_init(params);
    assert(ctx != NULL);
    uint64_t slots[18] = {0};
    assert(align_ggml_slots_init(slots, sizeof(slots)) == ALIGN_GGML_OK);
    struct ggml_tensor *q = ggml_new_tensor_3d(ctx, GGML_TYPE_F32, 128, 2, 4);
    struct ggml_tensor *k = ggml_new_tensor_3d(ctx, GGML_TYPE_F32, 128, 256, 2);
    struct ggml_tensor *v = ggml_new_tensor_3d(ctx, GGML_TYPE_F32, 128, 256, 2);
    struct ggml_tensor *mask = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, 256, 2);
    assert(align_ggml_slot_store(slots, 0, q) == ALIGN_GGML_OK);
    assert(align_ggml_slot_store(slots, 1, k) == ALIGN_GGML_OK);
    assert(align_ggml_slot_store(slots, 2, v) == ALIGN_GGML_OK);
    assert(align_ggml_slot_store(slots, 3, mask) == ALIGN_GGML_OK);
    assert(align_ggml_op_flash_attention(ctx, slots, 5, 0, 1, 2, 3, 0x3f800000) == ALIGN_GGML_TYPE);
    assert(align_ggml_op_attention_mask(ctx, slots, 4, 3) == ALIGN_GGML_OK);
    assert(align_ggml_op_attention_mask(ctx, slots, 16, 3) == ALIGN_GGML_SLOT);
    assert(align_ggml_op_flash_attention(ctx, slots, 5, 0, 1, 2, 4, 0x7fc00000) == ALIGN_GGML_SHAPE);
    assert(align_ggml_op_flash_attention(ctx, slots, 5, 0, 1, 2, 4, 0x3f800000) == ALIGN_GGML_OK);
    struct ggml_tensor *out = align_ggml_slot_tensor(slots, 5);
    assert(out->src[1]->type == GGML_TYPE_F16 && out->src[1]->op == GGML_OP_CPY);
    assert(out->src[2]->type == GGML_TYPE_F16 && out->src[2]->op == GGML_OP_CPY);
    assert(out->type == GGML_TYPE_F32 && out->ne[0] == 128 && out->ne[1] == 4 && out->ne[2] == 2);
    struct ggml_cgraph *graph = ggml_new_graph_custom(ctx, 32, false);
    ggml_build_forward_expand(graph, out);
    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    assert(buffer != NULL && ggml_backend_buffer_get_size(buffer) < 4 * 1024 * 1024);
    float zeros[128 * 256 * 2] = {0};
    float values[128 * 256 * 2];
    float masks[256 * 2];
    for (int h = 0; h < 2; ++h) {
        for (int t = 0; t < 256; ++t) {
            for (int d = 0; d < 128; ++d) {
                values[(h * 256 + t) * 128 + d] = (float) t + (float) d * 0.125f + (float) h * 2.0f;
            }
        }
    }
    for (int row = 0; row < 2; ++row) {
        for (int t = 0; t < 256; ++t) { masks[row * 256 + t] = t < row + 2 ? 0.0f : -INFINITY; }
    }
    ggml_backend_tensor_set(q, zeros, 0, ggml_nbytes(q));
    ggml_backend_tensor_set(k, zeros, 0, ggml_nbytes(k));
    ggml_backend_tensor_set(v, values, 0, ggml_nbytes(v));
    ggml_backend_tensor_set(mask, masks, 0, ggml_nbytes(mask));
    assert(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS);
    float result[128 * 4 * 2];
    ggml_backend_tensor_get(out, result, 0, sizeof(result));
    for (int row = 0; row < 2; ++row) {
        for (int h = 0; h < 4; ++h) {
            for (int d = 0; d < 128; ++d) {
                float expected = (float) (row + 1) * 0.5f + (float) d * 0.125f + (float) (h / 2) * 2.0f;
                assert(isfinite(result[(row * 4 + h) * 128 + d]));
                assert(fabsf(result[(row * 4 + h) * 128 + d] - expected) <= 0.0001f);
            }
        }
    }
    /* Keep every graph/tensor address stable while changing the payload. Three fresh
     * computations also exercise backends whose capture warmup needs two calls. */
    for (int iteration = 1; iteration <= 3; ++iteration) {
        for (size_t at = 0; at < sizeof(values) / sizeof(values[0]); ++at) { values[at] += 1.0f; }
        ggml_backend_tensor_set(v, values, 0, sizeof(values));
        assert(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS);
        ggml_backend_tensor_get(out, result, 0, sizeof(result));
        for (int row = 0; row < 2; ++row) {
            for (int h = 0; h < 4; ++h) {
                for (int d = 0; d < 128; ++d) {
                    float expected = (float) (row + 1) * 0.5f + (float) d * 0.125f
                        + (float) (h / 2) * 2.0f + (float) iteration;
                    assert(isfinite(result[(row * 4 + h) * 128 + d]));
                    assert(fabsf(result[(row * 4 + h) * 128 + d] - expected) <= 0.0001f);
                }
            }
        }
    }
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    ggml_backend_free(backend);
    ggml_backend_unload(registry);
    puts("GPU attention policy: PASS (real Flash arithmetic, causal mask, GQA, stable graph input updates, capability and owner refusal)");
    return 0;
}
