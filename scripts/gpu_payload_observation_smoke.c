/* Internal fault injection complements the public Align device owner. */
#include "ggml_shim_stub.c"
#include <assert.h>

int main(void) {
    struct align_gpu_device_state state = {0};
    align_stub_tensor *weight;
    align_stub_tensor *kv;
    align_stub_graph graph = {0};
    unsigned char weights[64] = {0};
    unsigned char cache[64] = {0};
    char key[65];
    int variant;
    state.metadata_ctx = align_ggml_context_open(4096);
    assert(state.metadata_ctx != NULL);
    weight = align_stub_new(state.metadata_ctx, ALIGN_STUB_TYPE_F32, 3, 1, 1, 1);
    kv = align_stub_new(state.metadata_ctx, ALIGN_STUB_TYPE_F32, 5, 1, 1, 1);
    assert(weight != NULL && kv != NULL);
    state.weights_buffer = weights;
    state.kv_buffer = cache;
    state.weights_bytes = sizeof(weights);
    state.kv_bytes = sizeof(cache);
    state.weights_expected = state.kv_expected = 1;
    state.memory_allocated = 1;
    weight->data = weights;
    kv->data = cache;
    assert(align_gpu_observation_state(&state, 6) == 0);
    assert(align_gpu_observation_state(&state, 7) == 0);
    state.weights_finished = state.kv_finished = 1;
    assert(align_gpu_observation_state(&state, 6) == 12);
    assert(align_gpu_observation_state(&state, 7) == 20);
    assert(align_gpu_observation_state(&state, 6) == 12);
    memset(key, 'a', 64);
    key[64] = '\0';
    memcpy(state.graph_keys[0], key, 65);
    state.workspace_graphs[0] = &graph;
    state.graph_prepared[0] = state.workspace_prepared = 1;
    for (variant = 0; variant < 3; ++variant) {
        state.observation_failed = 0;
        weight->data = weights;
        weight->ne[0] = 3;
        kv->data = cache;
        if (variant == 0) { weight->data = weights + sizeof(weights); }
        if (variant == 1) { weight->ne[0] = 2; }
        if (variant == 2) { kv->data = NULL; }
        assert(align_gpu_graph_compute(&state, 0, key, 64, &graph) == ALIGN_GPU_CONFIG);
        assert(state.graph_execution_count[0] == 0);
        assert(align_gpu_observation_state(&state, 6) == -1);
        weight->data = weights;
        weight->ne[0] = 3;
        kv->data = cache;
        assert(align_gpu_observation_state(&state, 7) == -1); /* Refusal stays sticky. */
    }
    align_ggml_context_close(state.metadata_ctx);
    return 0;
}
