/* Model-free real-backend owner: ceilings must not become placeholder allocations.
 * Compile against the pinned ggml headers/libraries; argv[1] is its GPU plugin. */
#include "ggml_shim.c"
#include <assert.h>

static void attention_precision(void) {
    struct ggml_init_params params = { .mem_size = 65536, .mem_buffer = NULL, .no_alloc = true };
    struct ggml_context *ctx = ggml_init(params);
    _Alignas(8) unsigned char slots[1040];
    assert(ctx != NULL);
    assert(align_ggml_slots_init(slots, sizeof(slots)) == 0);
    assert(align_ggml_slot_new_tensor_2d(ctx, slots, 0, GGML_TYPE_F32, 32, 8) == 0);
    assert(align_ggml_slot_new_tensor_2d(ctx, slots, 1, GGML_TYPE_F32, 32, 2) == 0);
    assert(align_ggml_op_attention_scores(ctx, slots, 2, 0, 1) == 0);
    assert(align_ggml_slot_tensor(slots, 2)->op_params[0] == GGML_PREC_F32);
    assert(align_ggml_op_mul_mat(ctx, slots, 3, 0, 1) == 0);
    assert(align_ggml_slot_tensor(slots, 3)->op_params[0] == GGML_PREC_DEFAULT);
    assert(align_ggml_slot_new_tensor_2d(ctx, slots, 4, GGML_TYPE_F32, 16, 2) == 0);
    assert(align_ggml_slot_new_tensor_2d(ctx, slots, 5, GGML_TYPE_F16, 32, 2) == 0);
    assert(align_ggml_op_attention_scores(NULL, slots, 6, 0, 1) == ALIGN_GGML_INIT);
    assert(align_ggml_op_attention_scores(ctx, slots, 6, 0, 100) == ALIGN_GGML_SLOT);
    assert(align_ggml_op_attention_scores(ctx, slots, 6, 0, 4) == ALIGN_GGML_SHAPE);
    assert(align_ggml_op_attention_scores(ctx, slots, 6, 0, 5) == ALIGN_GGML_TYPE);
    assert(align_ggml_slot_tensor(slots, 6) == NULL);
    ggml_free(ctx);
}

int main(int argc, char **argv) {
    ggml_backend_reg_t registry;
    ggml_backend_dev_t device;
    int64_t first_peak = 0;
    int pass;
    assert(argc == 2);
    attention_precision();
    registry = ggml_backend_load(argv[1]);
    assert(registry != NULL && ggml_backend_reg_dev_count(registry) > 0);
    device = ggml_backend_reg_dev_get(registry, 0);
    assert(device != NULL && ggml_backend_dev_type(device) == GGML_BACKEND_DEVICE_TYPE_GPU);
    for (pass = 0; pass < 2; ++pass) {
        struct align_gpu_device_state state = {0};
        int64_t ceiling = pass == 0 ? 1048576 : 1073741824;
        struct ggml_context *ctx;
        struct ggml_tensor *input;
        struct ggml_tensor *sum;
        struct ggml_cgraph *graph;
        size_t context_bytes = ggml_graph_overhead() + 8 * ggml_tensor_overhead();
        state.device = device;
        state.backend = ggml_backend_dev_init(device, NULL);
        state.host_budget_bytes = 1048576;
        state.device_budget_bytes = ceiling + 8192;
        assert(state.backend != NULL);
        assert(align_gpu_memory_admit(&state, 4096, 4096, ceiling, 262144, 4096, 0) == 0);
        assert(align_gpu_memory_allocate(&state) == 0);
        assert(align_gpu_memory_allocated_bytes(&state, 1) == 8192);
        assert(align_gpu_memory_allocated_bytes(&state, 4) == 0);
        assert(state.observation_device_peak == 8192);
        /* No model payload is needed to exercise input/graph resource ownership. */
        state.weights_finished = state.kv_finished = 1;
        assert(align_gpu_inputs_begin(&state, 1) == 0);
        assert(align_gpu_input_add(&state, GGML_TYPE_F32, 1, 32, 1, 1, 1) == 0);
        assert(align_gpu_memory_allocated_bytes(&state, 1) == 8192);
        assert(align_gpu_inputs_finish(&state) == 0);
        ctx = align_gpu_graph_context_open(&state, 0, (int64_t) context_bytes);
        assert(ctx != NULL);
        input = align_gpu_input_at(&state, 0);
        assert(input != NULL);
        sum = ggml_add(ctx, input, input);
        graph = ggml_new_graph(ctx);
        ggml_build_forward_expand(graph, sum);
        state.workspace_graphs[0] = graph;
        state.graph_prepared[0] = 1;
        assert(align_gpu_workspace_rebuild(&state) == 0);
        assert(state.observation_device_peak > 8192);
        assert(state.observation_device_peak < 1048576);
        if (pass == 0) { first_peak = state.observation_device_peak; }
        else { assert(state.observation_device_peak == first_peak); }
        align_gpu_memory_release(&state);
        assert(state.metadata_storage == NULL && state.input_buffer == NULL);
        assert(state.weights_buffer == NULL && state.kv_buffer == NULL);
        assert(state.workspace_allocator == NULL);
        ggml_backend_free(state.backend);
    }
    puts("real GPU workspace allocation: PASS (identical peaks for 1 MiB and 1 GiB ceilings)");
    return 0;
}
