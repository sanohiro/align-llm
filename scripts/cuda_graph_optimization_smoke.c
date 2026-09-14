/* Real CUDA optimizer: named forks, shared workspace, graph switches and changed inputs. */
#define _GNU_SOURCE
#include <assert.h>
#include "ggml_shim.c"

static struct ggml_cgraph *build_graph(struct align_gpu_device_state *owner, int kind,
                                     unsigned char *slots, char key) {
    struct ggml_context *ctx = owner->graph_contexts[kind];
    struct ggml_tensor *input = align_gpu_input_at(owner, 0);
    struct ggml_tensor *weight = align_gpu_weight_at(owner, 0);
    struct ggml_tensor *root = ggml_mul(ctx, input, input);
    struct ggml_tensor *q = ggml_scale(ctx, ggml_mul_mat(ctx, weight, root), 1);
    struct ggml_tensor *k = ggml_scale(ctx, ggml_mul_mat(ctx, weight, root), 2);
    struct ggml_tensor *v = ggml_scale(ctx, ggml_mul_mat(ctx, weight, root), 3);
    struct ggml_tensor *output = ggml_add(ctx, ggml_add(ctx, q, k), v);
    struct ggml_cgraph *graph = ggml_new_graph(ctx);
    char identity[64];
    assert(align_ggml_slots_init(slots, 1040) == 0);
    assert(align_ggml_slot_store(slots, 0, root) == 0);
    assert(align_ggml_slot_store(slots, 1, output) == 0);
    assert(align_ggml_slot_store(slots, 2, input) == 0);
    assert(align_gpu_tag_attention_norm(owner, kind, slots, 2) == ALIGN_GPU_CONFIG);
    assert(align_gpu_tag_attention_norm(owner, kind, slots, 127) == ALIGN_GPU_CONFIG);
    if (kind == ALIGN_GPU_GRAPH_DECODE) {
        assert(align_gpu_tag_attention_norm(owner, kind, slots, 0) == 0);
        assert((strstr(root->name, "attn_norm") != NULL) == owner->cuda_graph_optimization);
    } else {
        assert(align_gpu_tag_attention_norm(owner, kind, slots, 0) == ALIGN_GPU_CONFIG);
    }
    ggml_build_forward_expand(graph, v);
    ggml_build_forward_expand(graph, output);
    memset(identity, key, sizeof(identity));
    assert(align_gpu_graph_prepare(owner, kind, identity, sizeof(identity), graph) == 0);
    assert(align_gpu_tag_attention_norm(owner, kind, slots, 0) == ALIGN_GPU_CONFIG);
    if (owner->cuda_graph_optimization && kind == ALIGN_GPU_GRAPH_DECODE) {
        struct ggml_cgraph *canonical = owner->canonical_graphs[kind];
        assert(canonical != NULL);
        int changed = 0;
        for (int i = 0; i < ggml_graph_n_nodes(graph); ++i) {
            changed += ggml_graph_node(graph, i) != ggml_graph_node(canonical, i);
        }
        assert(changed > 0);
    }
    return graph;
}

int main(int argc, char **argv) {
    assert(argc == 3);
    int mode = atoi(argv[2]);
    if (mode == -1) {
        assert(align_gpu_cuda_policy_admit() == -1);
        puts("CUDA optimizer malformed process policy: PASS");
        return 0;
    }
    assert(align_gpu_cuda_policy_admit() == mode);
    assert(align_gpu_cuda_policy_admit() == mode);
    assert(setenv("GGML_CUDA_GRAPH_OPT", mode ? "0" : "1", 1) == 0);
    assert(align_gpu_cuda_policy_admit() == -1);
    assert(setenv("GGML_CUDA_GRAPH_OPT", mode ? "1" : "0", 1) == 0);
    ggml_backend_reg_t registry = ggml_backend_load(argv[1]);
    assert(registry != NULL && strcmp(ggml_backend_reg_name(registry), "CUDA") == 0);
    ggml_backend_dev_t device = ggml_backend_reg_dev_get(registry, 0);
    const char *name = ggml_backend_dev_name(device);
    char bundle[65];
    memset(bundle, 'a', 64); bundle[64] = 0;
    struct align_gpu_device_state *owner = NULL;
    assert(align_gpu_device_open("cuda", 4, name, strlen(name), argv[1], strlen(argv[1]),
                                bundle, 64, 8388608, 8388608, &owner) == 0);
    assert(owner != NULL && align_gpu_graph_optimization(owner) == mode);
    void *second = (void *) 1;
    assert(align_gpu_device_open("cuda", 4, name, strlen(name), argv[1], strlen(argv[1]),
                                bundle, 64, 8388608, 8388608, &second) == ALIGN_GPU_BUSY);
    assert(second == NULL);
    assert(align_gpu_memory_admit(owner, 4096, 256, 2097152, 2097152, 256, 0) == 0);
    assert(align_gpu_memory_allocate(owner) == 0);
    assert(align_gpu_weights_begin(owner, 1) == 0);
    assert(align_gpu_weight_add(owner, GGML_TYPE_F32, 2, 32, 32, 1, 1) == 0);
    float identity[1024] = {0};
    for (int i = 0; i < 32; ++i) { identity[i * 33] = 1; }
    for (int offset = 0; offset < 4096; offset += 256) {
        assert(align_gpu_weight_upload(owner, 0, offset, (char *) identity + offset, 256) == 0);
    }
    assert(align_gpu_weights_finish(owner) == 0);
    assert(align_gpu_kv_begin(owner, 1) == 0);
    assert(align_gpu_kv_add(owner, GGML_TYPE_F32, 1, 64, 1, 1, 1) == 0);
    assert(align_gpu_kv_finish(owner) == 0);
    assert(align_gpu_inputs_begin(owner, 1) == 0);
    assert(align_gpu_input_add(owner, GGML_TYPE_F32, 1, 32, 1, 1, 1) == 0);
    assert(align_gpu_inputs_finish(owner) == 0);
    _Alignas(8) unsigned char slots[2][1040];
    struct ggml_cgraph *graphs[2];
    for (int kind = 0; kind < 2; ++kind) {
        int64_t bytes = align_gpu_graph_context_bytes(owner, 64);
        assert(align_gpu_graph_context_open(owner, kind, bytes) != NULL);
        graphs[kind] = build_graph(owner, kind, slots[kind], 'a' + kind);
    }
    const int sequence[] = {0, 1, 1, 1, 1, 0, 1, 1, 1, 1};
    for (int iteration = 0; iteration < 30; ++iteration) {
        int kind = sequence[iteration % 10];
        if (iteration == 10 || iteration == 20) {
            assert(align_gpu_graph_invalidate(owner, 0) == 0);
            graphs[0] = build_graph(owner, 0, slots[0], 'a');
        }
        char key[64]; memset(key, 'a' + kind, sizeof(key));
        float input[32], output[32];
        for (int i = 0; i < 32; ++i) { input[i] = (float) (iteration + i + 1) / 32; }
        assert(align_gpu_input_update(owner, 0, 0, input, sizeof(input)) == 0);
        assert(align_gpu_graph_compute(owner, kind, key, sizeof(key), graphs[kind]) == 0);
        assert(align_gpu_slot_get(owner, slots[kind], 1, output, 0, sizeof(output)) == 0);
        for (int i = 0; i < 32; ++i) { assert(output[i] == 6 * input[i] * input[i]); }
    }
    assert(align_gpu_memory_allocated_bytes(owner, 0) <= owner->host_budget_bytes);
    assert(align_gpu_memory_allocated_bytes(owner, 1) <= owner->device_budget_bytes);
    align_gpu_device_close(owner);
    assert(align_gpu_device_open("cuda", 4, name, strlen(name), argv[1], strlen(argv[1]),
                                bundle, 64, 8388608, 8388608, &owner) == 0);
    assert(align_gpu_graph_optimization(owner) == mode);
    align_gpu_device_close(owner);
    printf("CUDA graph optimization mode %d: PASS (30 exact computations, two graphs, rebuild and reuse)\n", mode);
    return 0;
}
