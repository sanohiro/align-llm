/* Real backend arithmetic: incremental half KV must equal the old full-view cast. */
static void retained_f16_kv(ggml_backend_dev_t device) {
    struct align_gpu_device_state state = {0};
    _Alignas(8) unsigned char slots[1040];
    char key[64];
    float weights[16] = {0};
    const float rows[8] = {0.0f, -0.0f, 1.00048828125f, 1.00146484375f,
                           65504.0f, 0.000000059604644775390625f, -2.5f, 3.25f};
    ggml_fp16_t expected[10] = {0}, observed[10], reference[4];
    state.device = device;
    state.backend = ggml_backend_dev_init(device, NULL);
    state.host_budget_bytes = state.device_budget_bytes = 1048576;
    assert(state.backend != NULL);
    assert(align_gpu_attention_select(&state, 2) == ALIGN_GPU_CONFIG);
    assert(align_gpu_attention_select(&state, 1) == ALIGN_GPU_OK);
    assert(align_gpu_attention_select(&state, 2) == ALIGN_GPU_OK);
    assert(align_gpu_attention_select(&state, 2) == ALIGN_GPU_CONFIG);
    assert(align_gpu_attention_select(&state, 3) == ALIGN_GPU_CONFIG);
    int indexed = align_gpu_kv_prefill_indexed(&state);
    int64_t kv_bytes = align_gpu_weight_allocation_bytes(&state, GGML_TYPE_F16, 3, 2, 5, 1, 1);
    assert(kv_bytes >= 20);
    assert(align_gpu_memory_admit(&state, 256, kv_bytes, 65536, 393216, 64, 0) == 0);
    assert(align_gpu_memory_allocate(&state) == 0);
    assert(align_gpu_weights_begin(&state, 1) == 0);
    assert(align_gpu_weight_add(&state, GGML_TYPE_F32, 1, 64, 1, 1, 1) == 0);
    for (int i = 0; i < 4; ++i) {
        assert(align_gpu_weight_upload(&state, 0, i * 64, weights, 64) == 0);
    }
    assert(align_gpu_weights_finish(&state) == 0);
    assert(align_gpu_kv_begin(&state, 1) == 0);
    assert(align_gpu_kv_add(&state, GGML_TYPE_F16, 3, 2, 5, 1, 1) == 0);
    assert(align_gpu_kv_finish(&state) == 0);
    assert(state.observation_kv_payload == 20);
    assert(align_gpu_inputs_begin(&state, 4) == 0);
    assert(align_gpu_input_add(&state, GGML_TYPE_F32, 3, 2, 2, 1, 1) == 0);
    assert(align_gpu_input_add(&state, GGML_TYPE_F32, 3, 2, 1, 1, 1) == 1);
    assert(align_gpu_input_add(&state, GGML_TYPE_I32, 1, 1, 1, 1, 1) == 2);
    assert(align_gpu_input_add(&state, GGML_TYPE_I32, 1, 2, 1, 1, 1) == 3);
    assert(align_gpu_inputs_finish(&state) == 0);
    assert(align_gpu_graph_context_open(&state, 0, 131072) != NULL);

    for (int chunk = 0; chunk < 2; ++chunk) {
        if (chunk) { assert(align_gpu_graph_invalidate(&state, 0) == 0); }
        struct ggml_context *ctx = state.graph_contexts[0];
        int position = chunk * 2, width = position + 2;
        assert(align_ggml_slots_init(slots, sizeof(slots)) == 0);
        assert(align_gpu_input_slot(&state, 0, slots, 0) == 0);
        size_t before = ggml_used_mem(ctx);
        assert(align_gpu_kv_write_prefix(&state, 0, 0, 0, position, 6, slots, 2, 0) == ALIGN_GPU_CONFIG);
        assert(align_gpu_kv_write_prefix(&state, 0, 0, 1, position, width, slots, 2, 0) == ALIGN_GPU_CONFIG);
        struct ggml_tensor *input = align_gpu_input_at(&state, 0);
        input->type = GGML_TYPE_F16;
        assert(align_gpu_kv_write_prefix(&state, 0, 0, 0, position, width, slots, 2, 0) == ALIGN_GPU_CONFIG);
        input->type = GGML_TYPE_F32;
        size_t stride = input->nb[1];
        input->nb[1] += 4;
        assert(align_gpu_kv_write_prefix(&state, 0, 0, 0, position, width, slots, 2, 0) == ALIGN_GPU_CONFIG);
        input->nb[1] = stride;
        assert(ggml_used_mem(ctx) == before);
        if (indexed) {
            assert(align_gpu_kv_write_indexed_prefix(&state, 0, 0, 0, 2, width, slots, 2, 0) == ALIGN_GPU_CONFIG);
            assert(align_gpu_kv_write_indexed_prefix(&state, 0, 0, 1, 3, width, slots, 2, 0) == ALIGN_GPU_CONFIG);
            assert(align_gpu_kv_write_indexed_prefix(&state, 0, 0, 0, 3, 6, slots, 2, 0) == ALIGN_GPU_CONFIG);
            assert(align_gpu_kv_write_indexed_prefix(&state, 0, 0, 0, 3, width, slots, 2, 0) == 0);
        } else {
            assert(align_gpu_kv_write_prefix(&state, 0, 0, 0, position, width, slots, 2, 0) == 0);
        }
        struct ggml_tensor *prefix = align_ggml_slot_tensor(slots, 2);
        assert(prefix->type == GGML_TYPE_F16 && prefix->nb[0] == 2 && prefix->nb[1] == 4);
        assert(align_ggml_op_pad(ctx, slots, 3, 2, 0, 0, 0, 0) == 0);
        assert(align_ggml_slot_tensor(slots, 3) == prefix);
        assert(align_ggml_op_pad(ctx, slots, 4, 2, 0, 1, 0, 0) == 0);
        struct ggml_tensor *padded = align_ggml_slot_tensor(slots, 4);
        assert(padded->type == GGML_TYPE_F32 && padded->ne[1] == width + 1);
        struct ggml_tensor *cast = ggml_cast(ctx, align_gpu_input_at(&state, 0), GGML_TYPE_F16);
        ggml_set_output(padded);
        ggml_set_output(cast);
        struct ggml_cgraph *graph = ggml_new_graph(ctx);
        ggml_build_forward_expand(graph, padded);
        ggml_build_forward_expand(graph, cast);
        memset(key, 'a' + chunk, sizeof(key));
        assert(align_gpu_graph_prepare(&state, 0, key, sizeof(key), graph) == 0);
        assert(align_gpu_input_update(&state, 0, 0, rows + chunk * 4, 16) == 0);
        if (indexed) {
            int32_t positions[2] = {position, position + 1};
            int32_t duplicate[2] = {position, position};
            int32_t negative[2] = {-1, 0};
            int32_t wrong_start[2] = {position + 1, position + 2};
            assert(align_gpu_graph_compute(&state, 0, key, sizeof(key), graph) == ALIGN_GPU_CONFIG);
            assert(align_gpu_input_update(&state, 3, 0, duplicate, 8) == ALIGN_GPU_CONFIG);
            assert(align_gpu_input_update(&state, 3, 0, negative, 8) == ALIGN_GPU_CONFIG);
            assert(align_gpu_input_update(&state, 3, 0, wrong_start, 8) == ALIGN_GPU_CONFIG);
            assert(align_gpu_input_update(&state, 3, 4, positions, 4) == ALIGN_GPU_CONFIG);
            assert(align_gpu_input_update(&state, 3, 0, positions, 4) == ALIGN_GPU_CONFIG);
            assert(align_gpu_input_update(&state, 3, 0, positions, 8) == 0);
        }
        assert(align_gpu_graph_compute(&state, 0, key, sizeof(key), graph) == 0);
        if (indexed) { assert(align_gpu_graph_compute(&state, 0, key, sizeof(key), graph) == ALIGN_GPU_CONFIG); }
        ggml_backend_tensor_get(cast, reference, 0, sizeof(reference));
        for (int i = 0; i < 4; ++i) {
            assert(reference[i] == ggml_fp32_to_fp16(rows[chunk * 4 + i]));
            expected[chunk * 4 + i] = reference[i];
        }
        ggml_backend_tensor_get(align_gpu_kv_at(&state, 0), observed, 0, sizeof(observed));
        assert(memcmp(observed, expected, sizeof(expected)) == 0);
        float padded_values[10];
        ggml_backend_tensor_get(padded, padded_values, 0, (size_t) (width + 1) * 2 * sizeof(float));
        for (int i = 0; i < width * 2; ++i) {
            assert(padded_values[i] == ggml_fp16_to_fp32(expected[i]));
        }
        assert(padded_values[width * 2] == 0 && padded_values[width * 2 + 1] == 0);
    }

    struct ggml_context *ctx = align_gpu_graph_context_open(&state, 1, 131072);
    assert(ctx != NULL);
    assert(align_ggml_slots_init(slots, sizeof(slots)) == 0);
    assert(align_gpu_input_slot(&state, 1, slots, 0) == 0);
    assert(align_gpu_kv_write_indexed_prefix(&state, 0, 1, 1, 2, 5, slots, 1, 0) == ALIGN_GPU_CONFIG);
    assert(align_gpu_kv_write_indexed_prefix(&state, 0, 1, 0, 2, 6, slots, 1, 0) == ALIGN_GPU_CONFIG);
    assert(align_gpu_kv_write_indexed_prefix(&state, 0, 1, 0, 2, 5, slots, 1, 0) == 0);
    struct ggml_cgraph *graph = ggml_new_graph(ctx);
    ggml_build_forward_expand(graph, align_ggml_slot_tensor(slots, 1));
    memset(key, 'c', sizeof(key));
    assert(align_gpu_graph_prepare(&state, 1, key, sizeof(key), graph) == 0);
    const int32_t positions[3] = {4, 1, 4};
    for (int step = 0; step < 3; ++step) {
        int32_t invalid = 5;
        float values[2] = {rows[step * 2], rows[step * 2 + 1]};
        assert(align_gpu_input_update(&state, 2, 0, &invalid, 4) == ALIGN_GPU_CONFIG);
        assert(align_gpu_input_update(&state, 1, 0, values, sizeof(values)) == 0);
        assert(align_gpu_input_update(&state, 2, 0, positions + step, 4) == 0);
        assert(align_gpu_graph_compute(&state, 1, key, sizeof(key), graph) == 0);
        expected[positions[step] * 2] = ggml_fp32_to_fp16(values[0]);
        expected[positions[step] * 2 + 1] = ggml_fp32_to_fp16(values[1]);
        ggml_backend_tensor_get(align_gpu_kv_at(&state, 0), observed, 0, sizeof(observed));
        assert(memcmp(observed, expected, sizeof(expected)) == 0);
    }
    assert(state.graph_reuse_count[1] == 2);
    assert(align_gpu_graph_invalidate(&state, 0) == 0);
    ctx = state.graph_contexts[0];
    while (ggml_get_mem_size(ctx) - ggml_used_mem(ctx) >= 2 * ggml_tensor_overhead()) {
        assert(ggml_new_tensor_1d(ctx, GGML_TYPE_F32, 1) != NULL);
    }
    assert(align_ggml_slots_init(slots, sizeof(slots)) == 0);
    assert(align_gpu_input_slot(&state, 0, slots, 0) == 0);
    size_t exhausted = ggml_used_mem(ctx);
    if (indexed) {
        assert(align_gpu_kv_write_indexed_prefix(&state, 0, 0, 0, 3, 2, slots, 2, 0) == ALIGN_GPU_ALLOCATION);
    } else {
        assert(align_gpu_kv_write_prefix(&state, 0, 0, 0, 0, 2, slots, 2, 0) == ALIGN_GPU_ALLOCATION);
    }
    assert(ggml_used_mem(ctx) == exhausted);
    align_gpu_memory_release(&state);
    assert(state.kv_buffer == NULL && state.metadata_storage == NULL);
    ggml_backend_free(state.backend);
    puts("GPU F16 KV: PASS (incremental rounding, prefix preservation, overwrite, tail, padding, refusal, cleanup)");
}
