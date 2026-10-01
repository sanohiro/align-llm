/* Model-free owner of whole-batch validation, completion and poisoned reuse. */
#include "ggml_shim.c"
#include <assert.h>

static void put64(unsigned char *p, uint64_t value) {
    for (unsigned int i = 0; i < 8; ++i) { p[i] = (unsigned char) (value >> (8 * i)); }
}

static void descriptor(unsigned char *p, uint64_t index, uint64_t offset,
        uint64_t source, uint64_t length) {
    put64(p, index); put64(p + 8, offset); put64(p + 16, source); put64(p + 24, length);
}

static void unchanged(struct align_gpu_device_state *s, unsigned char before[8][64]) {
    unsigned char observed[64];
    for (int i = 0; i < 8; ++i) {
        ggml_backend_tensor_get(align_gpu_input_at(s, i), observed, 0, 64);
        assert(memcmp(observed, before[i], 64) == 0);
    }
}

static void refusal(struct align_gpu_device_state *s, const void *d, int64_t n,
        const void *p, int64_t bytes) {
    unsigned char before[8][64];
    int64_t accounting = s->input_updated_bytes, sync = s->observation_sync_calls;
    int64_t position = s->row_position;
    int valid = s->row_position_valid, values = s->row_values_valid;
    int prefill_valid = s->prefill_rows_valid;
    for (int i = 0; i < 8; ++i) {
        ggml_backend_tensor_get(align_gpu_input_at(s, i), before[i], 0, 64);
    }
    assert(align_gpu_inputs_update_batch(s, d, n, p, bytes) == ALIGN_GPU_CONFIG);
    assert(s->input_updated_bytes == accounting && s->observation_sync_calls == sync);
    assert(s->row_position == position && s->row_position_valid == valid
        && s->row_values_valid == values && s->prefill_rows_valid == prefill_valid && !s->inputs_failed);
    unchanged(s, before);
}

int main(int argc, char **argv) {
    struct align_gpu_device_state state = {0};
    unsigned char encoded[257] = {0}, payload[512], observed[64], zero[64] = {0};
    /* Deliberately unaligned framing; little-endian bytes are the wire contract. */
    unsigned char *d = encoded + 1;
    assert(argc == 2);
    ggml_backend_reg_t registry = ggml_backend_load(argv[1]);
    assert(registry != NULL && ggml_backend_reg_dev_count(registry) > 0);
    state.device = ggml_backend_reg_dev_get(registry, 0);
    assert(ggml_backend_dev_type(state.device) == GGML_BACKEND_DEVICE_TYPE_GPU);
    state.backend = ggml_backend_dev_init(state.device, NULL);
    assert(state.backend != NULL);
    state.host_budget_bytes = state.device_budget_bytes = 1048576;
    assert(align_gpu_memory_admit(&state, 256, 128, 65536, 262144, 512, 0) == 0);
    assert(align_gpu_memory_allocate(&state) == 0);
    state.weights_finished = state.kv_finished = 1;
    assert(align_gpu_inputs_begin(&state, 8) == 0);
    for (int i = 0; i < 8; ++i) {
        assert(align_gpu_input_add(&state, GGML_TYPE_I32, 1, 16, 1, 1, 1) == i);
    }
    assert(align_gpu_inputs_finish(&state) == 0);
    state.workspace_prepared = 1;
    for (int i = 0; i < 8; ++i) {
        ggml_backend_tensor_set(align_gpu_input_at(&state, i), zero, 0, 64);
    }
    for (int i = 0; i < 512; ++i) { payload[i] = (unsigned char) (i * 37 + 3); }
    descriptor(d, 0, 1, 2, 3);
    const unsigned char golden[32] = {0,0,0,0,0,0,0,0, 1,0,0,0,0,0,0,0,
                                      2,0,0,0,0,0,0,0, 3,0,0,0,0,0,0,0};
    assert(memcmp(d, golden, 32) == 0);
    refusal(&state, NULL, 32, payload, 512);
    refusal(&state, d, 0, payload, 512);
    refusal(&state, d, -1, payload, 512);
    refusal(&state, d, 31, payload, 512);
    refusal(&state, d, 33, payload, 512);
    refusal(&state, d, 257, payload, 512);
    refusal(&state, d, 32, NULL, 512);
    refusal(&state, d, 32, payload, 0);
    refusal(&state, d, 32, payload, -1);
    refusal(&state, d, 32, payload, 513);
    state.workspace_prepared = 0; refusal(&state, d, 32, payload, 512);
    state.workspace_prepared = 1;
    assert(align_gpu_inputs_update_batch(NULL, d, 32, payload, 512) == ALIGN_GPU_CONFIG);
    state.shape_planning = 1; refusal(&state, d, 32, payload, 512); state.shape_planning = 0;
    for (int field = 0; field < 4; ++field) {
        descriptor(d, 0, 0, 0, 4);
        put64(d + field * 8, UINT64_MAX); refusal(&state, d, 32, payload, 512);
        put64(d + field * 8, INT64_MAX); refusal(&state, d, 32, payload, 512);
    }
    descriptor(d, 8, 0, 0, 4); refusal(&state, d, 32, payload, 512);
    descriptor(d, 0, 0, 0, 0); refusal(&state, d, 32, payload, 512);
    descriptor(d, 0, 63, 0, 2); refusal(&state, d, 32, payload, 512);
    descriptor(d, 0, 0, 511, 2); refusal(&state, d, 32, payload, 512);
    for (int i = 0; i < 4; ++i) { descriptor(d + i * 32, i, 0, i * 64, 64); }
    descriptor(d + 96, 99, 0, 192, 64); refusal(&state, d, 128, payload, 512);
    descriptor(d + 96, 0, 0, 192, 64); refusal(&state, d, 128, payload, 512);
    descriptor(d + 96, 3, 0, 192, 64);
    state.input_updated_bytes = INT64_MAX - 255;
    refusal(&state, d, 128, payload, 512); state.input_updated_bytes = 0;
    state.observation_sync_calls = INT64_MAX;
    refusal(&state, d, 128, payload, 512); state.observation_sync_calls = 0;
    state.prefill_rows_registered = 1; state.prefill_rows_input = 7;
    state.prefill_rows_start = 2; state.prefill_rows_count = 4;
    int32_t rows[] = {2, 3, 4, 99}; memcpy(payload + 256, rows, sizeof(rows));
    descriptor(d, 6, 0, 0, 4); descriptor(d + 32, 7, 0, 256, 16);
    refusal(&state, d, 64, payload, 512); state.prefill_rows_registered = 0;
    /* Row values depend on a new position in the same batch, not the old state. */
    assert(align_gpu_row_inputs_register(&state, 0, 0, 16, 4));
    assert(align_gpu_row_inputs_register(&state, 1, 1, 16, 4));
    put64(payload, 5);
    for (int i = 0; i < 4; ++i) {
        int32_t value = i * 16 + 5; memcpy(payload + 8 + i * 4, &value, 4);
    }
    descriptor(d, 0, 0, 0, 4); descriptor(d + 32, 1, 0, 8, 16);
    int32_t bad = 99; memcpy(payload + 20, &bad, 4);
    refusal(&state, d, 64, payload, 24);
    bad = 53; memcpy(payload + 20, &bad, 4);
    descriptor(d, 1, 0, 8, 16); descriptor(d + 32, 0, 0, 0, 4);
    refusal(&state, d, 64, payload, 24);
    descriptor(d, 0, 0, 0, 4); descriptor(d + 32, 1, 0, 8, 16);
    int32_t status = align_gpu_inputs_update_batch(&state, d, 64, payload, 24);
    if (ALIGN_GPU_FORCE_INPUT_BATCH_SUBMIT_FAILURE || ALIGN_GPU_FORCE_INPUT_BATCH_COMPLETION_FAILURE) {
        assert(status == ALIGN_GPU_COMPUTE && state.inputs_failed && state.workspace_failed);
        assert(state.input_updated_bytes == 0 && !state.row_position_valid && !state.row_values_valid);
        assert(state.observation_sync_calls == 1);
        /* Work is drained: host storage can be destroyed after the failed return. */
        memset(payload, 0, sizeof(payload));
        ggml_backend_tensor_get(align_gpu_input_at(&state, 0), observed, 0, 4);
        assert(observed[0] == 5 && observed[1] == 0 && observed[2] == 0 && observed[3] == 0);
        assert(align_gpu_inputs_update_batch(&state, d, 64, payload, 24) == ALIGN_GPU_CONFIG);
        assert(state.observation_sync_calls == 1);
    } else {
        assert(status == 0 && state.row_position == 5 && state.row_position_valid && state.row_values_valid);
        assert(state.input_updated_bytes == 20 && state.observation_sync_calls == 1);
        put64(payload, 7);
        refusal(&state, d, 64, payload, 24);
        for (int i = 0; i < 4; ++i) {
            int32_t value = i * 16 + 7; memcpy(payload + 8 + i * 4, &value, 4);
        }
        assert(align_gpu_inputs_update_batch(&state, d, 64, payload, 24) == 0);
        assert(state.row_position == 7 && state.row_values_valid);
        state.row_registered[0] = state.row_registered[1] = 0;
        for (int count = 1; count <= 8; count *= 2) {
            if (count == 2) { continue; }
            for (int i = 0; i < 8; ++i) { descriptor(d + i * 32, i, 0, i * 64, 64); }
            int64_t sync = state.observation_sync_calls, bytes = state.input_updated_bytes;
            assert(align_gpu_inputs_update_batch(&state, d, count * 32, payload, 512) == 0);
            assert(state.observation_sync_calls == sync + 1 && state.input_updated_bytes == bytes + count * 64);
            for (int i = 0; i < count; ++i) {
                ggml_backend_tensor_get(align_gpu_input_at(&state, i), observed, 0, 64);
                assert(memcmp(observed, payload + i * 64, 64) == 0);
            }
        }
    }
    align_gpu_memory_release(&state);
    assert(state.input_buffer == NULL && state.metadata_storage == NULL && state.staging == NULL);
    ggml_backend_free(state.backend);
    puts("GPU input batch: PASS (validation, bytes, one completion, drain/poison, cleanup)");
    return 0;
}
