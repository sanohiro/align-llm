/* Real-backend lifecycle owner; no model arithmetic or product dispatch lives here. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>

static ggml_gallocr_t retained;
static int retained_frees;
static void counted_free(ggml_gallocr_t allocator) {
    if (allocator == retained && retained != NULL) retained_frees++;
    ggml_gallocr_free(allocator);
}
#ifndef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE 0
#endif
#ifndef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND 0
#endif
enum { TEST_RESERVE = ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE,
       TEST_BIND = ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND };
static int force_active;
#undef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE
#undef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE (force_active && TEST_RESERVE)
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND (force_active && TEST_BIND)
#define ggml_gallocr_free counted_free
#include "ggml_shim.c"
#undef ggml_gallocr_free

enum { INPUTS = 16384, META = 262144, WORKSPACE = 1048576 };
static struct align_gpu_device_state *open_state(ggml_backend_dev_t device, int mode) {
    struct align_gpu_device_state *s = calloc(1, sizeof(*s));
    assert(s != NULL);
    s->device = device;
    s->backend = ggml_backend_dev_init(device, NULL);
    assert(s->backend != NULL);
    s->host_budget_bytes = 2 * WORKSPACE;
    s->device_budget_bytes = 2 * WORKSPACE;
    assert(align_gpu_workspace_retain_mode(s, mode) == 0);
    return s;
}

static void admission(struct align_gpu_device_state *s, int64_t workspace) {
    assert(align_gpu_memory_admit(s, 256, 128, workspace, META, 64, 0) == 0);
    assert(align_gpu_workspace_retain_mode(s, 1) == ALIGN_GPU_CONFIG);
    assert(align_gpu_memory_allocate(s) == 0);
    float weights[16] = {0};
    assert(align_gpu_weights_begin(s, 1) == 0);
    assert(align_gpu_weight_add(s, GGML_TYPE_F32, 1, 64, 1, 1, 1) == 0);
    if (!s->shape_planning) {
        for (int chunk = 0; chunk < 4; chunk++)
            assert(align_gpu_weight_upload(s, 0, chunk * 64, weights, sizeof(weights)) == 0);
    }
    assert(align_gpu_weights_finish(s) == 0);
    assert(align_gpu_kv_begin(s, 1) == 0);
    assert(align_gpu_kv_add(s, GGML_TYPE_F32, 1, 32, 1, 1, 1) == 0);
    assert(align_gpu_kv_finish(s) == 0);
    assert(align_gpu_inputs_begin(s, 1) == 0);
    assert(align_gpu_input_add(s, GGML_TYPE_F32, 1, INPUTS, 1, 1, 1) == 0);
    assert(align_gpu_inputs_finish(s) == 0);
    for (int k = 0; k < ALIGN_GPU_GRAPH_KINDS; k++)
        assert(align_gpu_graph_context_open(s, k, 65536) != NULL);
}

static struct ggml_cgraph *graph(struct align_gpu_device_state *s, int k, int length,
                               struct ggml_tensor **out) {
    struct ggml_context *ctx = s->graph_contexts[k];
    struct ggml_tensor *view = ggml_view_1d(ctx, align_gpu_input_at(s, 0), length, 0);
    *out = ggml_scale(ctx, view, (float) (k + 2));
    if (k == 1) *out = ggml_neg(ctx, ggml_neg(ctx, *out));
    struct ggml_cgraph *g = ggml_new_graph_custom(ctx, 32, false);
    ggml_build_forward_expand(g, *out);
    return g;
}

static void compute(struct align_gpu_device_state *s, int k, char key[64],
                    struct ggml_tensor *out) {
    float values[INPUTS], observed[INPUTS];
    for (int i = 0; i < INPUTS; i++) values[i] = (float) (i + 1) * 0.125f;
    assert(align_gpu_input_update(s, 0, 0, values, sizeof(values)) == 0);
    assert(align_gpu_graph_compute(s, k, key, 64, s->workspace_graphs[k]) == 0);
    assert(align_gpu_slot_ready(s, out));
    ggml_backend_tensor_get(out, observed, 0, ggml_nbytes(out));
    for (int64_t i = 0; i < out->ne[0]; i++)
        assert(observed[i] == values[i] * (float) (k + 2));
}

static void lifecycle(ggml_backend_dev_t device, int mode) {
    struct align_gpu_device_state *s = open_state(device, mode);
    struct ggml_tensor *out[ALIGN_GPU_GRAPH_KINDS];
    char keys[ALIGN_GPU_GRAPH_KINDS][64];
    admission(s, WORKSPACE);
    for (int k = 0; k < ALIGN_GPU_GRAPH_KINDS; k++) {
        memset(keys[k], 'a' + k, 64);
        struct ggml_cgraph *g = graph(s, k, 512 << k, &out[k]);
        assert(align_gpu_graph_prepare(s, k, keys[k], 63, g) == ALIGN_GPU_CONFIG);
        assert(!s->graph_prepared[k] && !s->workspace_failed);
        int32_t status = align_gpu_graph_prepare(s, k, keys[k], 64, g);
        if (status != 0) fprintf(stderr, "prepare mode=%d kind=%d status=%d failed=%d observation=%d\n",
                                mode, k, status, s->workspace_failed, s->observation_failed);
        assert(status == 0);
        compute(s, k, keys[k], out[k]);
        int64_t executions = s->graph_execution_count[k];
        assert(align_gpu_graph_compute(s, k, keys[k], 63, g) == ALIGN_GPU_CONFIG);
        assert(s->graph_execution_count[k] == executions);
        if (mode && k > 0) assert(!align_gpu_slot_ready(s, out[k - 1]));
    }
    ggml_gallocr_t allocator = s->workspace_allocator;
    if (mode) { retained = allocator; retained_frees = 0; }
    if (mode && (TEST_RESERVE || TEST_BIND)) {
        force_active = 1;
        assert(align_gpu_graph_invalidate(s, 0) == ALIGN_GPU_ALLOCATION);
        assert(s->workspace_failed && !s->workspace_prepared);
        assert(s->graph_prepared[1] && s->graph_prepared[2]);
        assert(!align_gpu_slot_ready(s, out[2]));
        assert(align_gpu_graph_compute(s, 1, keys[1], 64, s->workspace_graphs[1]) == ALIGN_GPU_CONFIG);
        if (TEST_BIND) assert(out[1]->data != NULL && out[2]->data == NULL);
        align_gpu_memory_release(s);
        align_gpu_memory_release(s);
        assert(retained_frees == 1); retained = NULL;
        align_gpu_device_close(s);
        force_active = 0;
        return;
    }
    for (int round = 0; round < 6; round++) {
        assert(align_gpu_graph_invalidate(s, 0) == 0);
        struct ggml_cgraph *g = graph(s, 0, round % 2 ? 256 : 8192, &out[0]);
        assert(align_gpu_graph_prepare(s, 0, keys[0], 64, g) == 0);
        if (mode) assert(s->workspace_allocator == allocator && retained_frees == 0);
        for (int k = 0; k < ALIGN_GPU_GRAPH_KINDS; k++) {
            compute(s, k, keys[k], out[k]);
            if (mode) {
                for (int other = 0; other < ALIGN_GPU_GRAPH_KINDS; other++)
                    if (other != k) assert(!align_gpu_slot_ready(s, out[other]));
            }
        }
        assert(align_gpu_memory_allocated_bytes(s, 4) <= s->workspace_bytes);
    }
    if (mode) {
        assert(align_gpu_slot_ready(s, out[2])); /* prime the cached fast path */
        s->workspace_failed = 1;
        assert(!align_gpu_slot_ready(s, out[2]));
        s->workspace_failed = 0;
        s->native_q6_head_ready = 1;
        s->workspace_content_generation = UINT64_MAX;
        assert(align_gpu_graph_compute(s, 2, keys[2], 64, s->workspace_graphs[2]) == ALIGN_GPU_CONFIG);
        assert(s->workspace_failed && !s->native_q6_head_ready && !align_gpu_slot_ready(s, out[2]));
        s->workspace_failed = 0;
        s->workspace_content_generation = 100;
    }
    for (int k = 0; k < ALIGN_GPU_GRAPH_KINDS; k++) assert(align_gpu_graph_invalidate(s, k) == 0);
    assert(!s->workspace_prepared);
    if (mode) {
        assert(s->workspace_allocator == allocator && retained_frees == 0);
        assert(align_gpu_memory_allocated_bytes(s, 4) > (int64_t) s->input_offset);
    } else assert(s->workspace_allocator == NULL);
    align_gpu_memory_release(s);
    align_gpu_memory_release(s);
    if (mode) { assert(retained_frees == 1); retained = NULL; }
    align_gpu_device_close(s);
}

static void planning(ggml_backend_dev_t device, int mode, int finish, int partial) {
    struct align_gpu_device_state *s = open_state(device, mode);
    assert(align_gpu_workspace_retain_mode(s, -1) == ALIGN_GPU_CONFIG);
    assert(s->retain_workspace == mode);
    assert(align_gpu_plan_begin(s) == 0);
    assert(align_gpu_workspace_retain_mode(s, 1) == ALIGN_GPU_CONFIG);
    if (mode) {
        struct align_gpu_device_state before = *s;
        assert(align_gpu_native_state_copy_mode(s, 1) == ALIGN_GPU_CONFIG);
        assert(align_gpu_native_q6_head_mode(s, 1) == ALIGN_GPU_CONFIG);
        assert(align_gpu_native_conv_copy_mode(s, 1) == ALIGN_GPU_CONFIG);
        assert(align_gpu_native_prefill_state_copy_mode(s, 1) == ALIGN_GPU_CONFIG);
        assert(align_gpu_native_copy_greedy_mode(s, 1) == ALIGN_GPU_CONFIG);
        assert(memcmp(&before, s, sizeof(before)) == 0);
    }
    if (partial || finish) {
        admission(s, WORKSPACE);
        assert(align_gpu_memory_allocated_bytes(s, 1) == 0 && s->workspace_allocator == NULL);
        if (finish) {
            struct ggml_tensor *out;
            struct ggml_cgraph *g = graph(s, 0, 512, &out);
            char key[64]; memset(key, 'a', 64);
            assert(align_gpu_graph_prepare(s, 0, key, 64, g) == 0);
            assert(s->workspace_allocator == NULL);
        }
    }
    assert((finish ? align_gpu_plan_finish(s) : align_gpu_plan_cancel(s)) == 0);
    assert(s->retain_workspace == mode && !s->shape_planning && !s->memory_planned
        && s->metadata_storage == NULL && s->workspace_allocator == NULL
        && s->input_buffer == NULL && s->kv_buffer == NULL && s->weights_buffer == NULL);
    align_gpu_memory_release(s);
#if defined(ALIGN_LLM_NATIVE_CUDA)
    assert(align_gpu_native_q6_head_mode(s, 1) == 0);
    assert(align_gpu_native_state_copy_mode(s, 1) == 0);
    assert(s->native_state_copy_context != NULL);
    assert(align_gpu_memory_admit(s, 256, 128, WORKSPACE, META, 64, 0) == 0);
    assert(s->native_q6_head_context != NULL);
#endif
    align_gpu_device_close(s);
}

static void budgets(ggml_backend_dev_t device) {
    struct align_gpu_device_state *s = open_state(device, 1);
    admission(s, WORKSPACE);
    struct ggml_tensor *out;
    struct ggml_cgraph *g = graph(s, 0, 512, &out);
    size_t required = 0;
    assert(align_gpu_graph_required(ggml_backend_get_default_buffer_type(s->backend), g, &required));
    int64_t exact = (int64_t) (s->input_offset + required);
    align_gpu_device_close(s);
    for (int below = 0; below < 2; below++) {
        s = open_state(device, 1);
        admission(s, exact - below);
        g = graph(s, 0, 512, &out);
        char key[64]; memset(key, 'a', 64);
        int32_t status = align_gpu_graph_prepare(s, 0, key, 64, g);
        assert(status == (below ? ALIGN_GPU_MEMORY_BUDGET : ALIGN_GPU_OK));
        if (below) assert(s->workspace_failed && !s->workspace_allocator);
        else compute(s, 0, key, out);
        align_gpu_device_close(s);
    }
}

int main(int argc, char **argv) {
    assert(argc == 2);
    ggml_backend_reg_t registry = ggml_backend_load(argv[1]);
    assert(registry != NULL && ggml_backend_reg_dev_count(registry) > 0);
    ggml_backend_dev_t device = ggml_backend_reg_dev_get(registry, 0);
    if (ALIGN_GPU_FORCE_ALLOCATION_PREFIX == 1) {
        struct align_gpu_device_state *failed = open_state(device, 1);
        assert(align_gpu_plan_begin(failed) == 0);
        assert(align_gpu_memory_admit(failed, 256, 128, WORKSPACE, META, 64, 0) == 0);
        assert(align_gpu_memory_allocate(failed) == ALIGN_GPU_ALLOCATION);
        assert(failed->metadata_storage == NULL && failed->workspace_allocator == NULL);
        assert(align_gpu_plan_cancel(failed) == 0 && failed->retain_workspace == 1);
        align_gpu_memory_release(failed);
        align_gpu_device_close(failed);
        puts("workspace retention: PASS (first allocation failure and planning cleanup)");
        return 0;
    }
    assert(align_gpu_workspace_retain_mode(NULL, 1) == ALIGN_GPU_CONFIG);
    for (int mode = 0; mode < 2; mode++) {
        lifecycle(device, mode);
        planning(device, mode, 0, 0);
        planning(device, mode, 0, 1);
        planning(device, mode, 1, 1);
    }
    struct align_gpu_device_state *s = open_state(device, 0);
    s->native_q6_head = 1;
    assert(align_gpu_workspace_retain_mode(s, 1) == 0);
    struct align_gpu_device_state before = *s;
    assert(align_gpu_plan_begin(s) == ALIGN_GPU_CONFIG);
    assert(memcmp(&before, s, sizeof(before)) == 0);
    s->native_q6_head = 0;
    align_gpu_device_close(s);
#if defined(ALIGN_LLM_NATIVE_CUDA)
    int32_t (*selectors[])(void *, int32_t) = {
        align_gpu_native_state_copy_mode, align_gpu_native_q6_head_mode
    };
    for (int helper = 0; helper < 2; helper++) {
        for (int retain_first = 0; retain_first < 2; retain_first++) {
            s = open_state(device, retain_first);
            assert(selectors[helper](s, 1) == 0);
            assert(align_gpu_workspace_retain_mode(s, 1) == 0);
            before = *s;
            assert(align_gpu_plan_begin(s) == ALIGN_GPU_CONFIG);
            assert(memcmp(&before, s, sizeof(before)) == 0);
            align_gpu_device_close(s);
        }
    }
#endif
    if (!TEST_RESERVE && !TEST_BIND) budgets(device);
    puts("workspace retention: PASS (layouts, output lifetime, empty capacity, planning, budgets and cleanup)");
}
