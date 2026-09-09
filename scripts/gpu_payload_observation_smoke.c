/* Internal fault injection complements the public Align device owner. */
#include "ggml_shim_stub.c"
#include <assert.h>
#include "gpu_host_reservation_smoke.h"

int main(void) {
    host_reservation();
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
    assert(align_gpu_observation_state(&state, 11) == 0);
    assert(align_gpu_observation_state(&state, 12) == -1);
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
    {
        align_stub_tensor node = {0};
        state.observation_failed = 0;
        state.observation_model_ops = INT64_MAX;
        node.op = ALIGN_STUB_OP_ADD;
        graph.count = 1;
        graph.nodes[0] = &node;
        assert(align_gpu_graph_compute(&state, 0, key, 64, &graph) == ALIGN_GPU_CONFIG);
        assert(state.graph_execution_count[0] == 0);
        assert(state.observation_model_ops == INT64_MAX);
    }
    align_ggml_context_close(state.metadata_ctx);
    {
        struct align_gpu_device_state model = {0};
        align_stub_tensor node = {0};
        align_stub_tensor *members[15];
        int64_t operations = 0, layers = 0, experts = 0;
        int index;
        model.metadata_ctx = align_ggml_context_open(32768);
        assert(model.metadata_ctx != NULL);
        model.weights_expected = 15;
        for (index = 0; index < 15; ++index) {
            members[index] = align_stub_new(model.metadata_ctx, ALIGN_STUB_TYPE_F32, 1, 1, 1, 1);
            assert(members[index] != NULL);
        }
        node.op = ALIGN_STUB_OP_MUL_MAT_ID;
        node.src[0] = members[12];
        node.ne[1] = 2;
        node.ne[2] = 3;
        assert(align_gpu_count_model_node(&model, &node, &operations, &layers, &experts));
        assert(operations == 1 && layers == 1 && experts == 6);
        node.src[0] = members[11];
        assert(align_gpu_count_model_node(&model, &node, &operations, &layers, &experts));
        assert(operations == 2 && layers == 1 && experts == 6);
        node.op = ALIGN_STUB_OP_VIEW;
        assert(align_gpu_count_model_node(&model, &node, &operations, &layers, &experts));
        assert(operations == 2 && layers == 1 && experts == 6);
        node.op = ALIGN_STUB_OP_MUL_MAT_ID;
        node.src[0] = members[12];
        node.ne[2] = INT64_MAX;
        assert(!align_gpu_count_model_node(&model, &node, &operations, &layers, &experts));
        {
            align_stub_graph first = {0}, second = {0};
            unsigned char slots[128] = {0};
            align_stub_tensor *a = align_stub_new(model.metadata_ctx, ALIGN_STUB_TYPE_F32, 1, 1, 1, 1);
            align_stub_tensor *b = align_stub_new(model.metadata_ctx, ALIGN_STUB_TYPE_F32, 1, 1, 1, 1);
            assert(a != NULL && b != NULL);
            a->op = ALIGN_STUB_OP_RMS_NORM;
            a->src[0] = members[0];
            b->op = ALIGN_STUB_OP_MUL;
            b->src[0] = b->src[1] = a;
            assert(align_ggml_slots_init(slots, sizeof(slots)) == ALIGN_GGML_OK);
            assert(align_ggml_slot_store(slots, 0, a) == ALIGN_GGML_OK);
            assert(align_ggml_slot_store(slots, 1, b) == ALIGN_GGML_OK);
            assert(align_ggml_graph_expand(&first, slots, 0) == ALIGN_GGML_OK);
            assert(first.count == 1);
            assert(align_ggml_graph_expand(&second, slots, 1) == ALIGN_GGML_OK);
            assert(second.count == 2);
            assert(align_ggml_graph_expand(&first, slots, 1) == ALIGN_GGML_OK);
            assert(first.count == 2);
            assert(align_ggml_graph_expand(&first, slots, 1) == ALIGN_GGML_OK);
            assert(first.count == 2);
        }
        align_ggml_context_close(model.metadata_ctx);
    }
    return 0;
}
