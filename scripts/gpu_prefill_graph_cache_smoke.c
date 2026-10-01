/* Independent real-backend cache lifecycle and failure qualification. */
#define _GNU_SOURCE
#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>

static int binds, reserves, frees, context_frees;
static int context_failure = -1, init_ordinal, graph_init_phase;
static struct ggml_context *counted_init(struct ggml_init_params p) {
    if (graph_init_phase && context_failure >= 0 && init_ordinal++ == context_failure) return NULL;
    return ggml_init(p);
}
static bool counted_bind(ggml_gallocr_t a, struct ggml_cgraph *g) {
    binds++;
    return ggml_gallocr_alloc_graph(a, g);
}
static bool counted_reserve(ggml_gallocr_t a, struct ggml_cgraph *g) {
    reserves++;
    return ggml_gallocr_reserve(a, g);
}
static void counted_free(ggml_gallocr_t a) { frees++; ggml_gallocr_free(a); }
static void counted_context_free(struct ggml_context *c) { context_frees++; ggml_free(c); }
#define ggml_gallocr_alloc_graph counted_bind
#define ggml_gallocr_reserve counted_reserve
#define ggml_gallocr_free counted_free
#define ggml_free counted_context_free
#define ggml_init counted_init
#ifndef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE 0
#endif
#ifndef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND 0
#endif
enum { TEST_RESERVE = ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE,
       TEST_BIND = ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND };
static int force_active = 1;
#undef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE
#undef ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE (force_active && TEST_RESERVE)
#define ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND (force_active && TEST_BIND)
#include "ggml_shim.c"
#undef ggml_gallocr_alloc_graph
#undef ggml_gallocr_reserve
#undef ggml_gallocr_free
#undef ggml_free
#undef ggml_init

enum { META = 524288, WORKSPACE = 1048576, INPUTS = 16384 };
static int64_t workspace_limit = WORKSPACE;
static struct align_gpu_device_state *open_state(ggml_backend_dev_t device) {
    struct align_gpu_device_state *s = calloc(1, sizeof(*s));
    assert(s != NULL);
    s->device = device;
    s->backend = ggml_backend_dev_init(device, NULL);
    assert(s->backend != NULL);
    s->host_budget_bytes = 2 * WORKSPACE;
    s->device_budget_bytes = 2 * WORKSPACE;
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == ALIGN_GPU_CONFIG);
    assert(align_gpu_workspace_retain_mode(s, 1) == 0);
    assert(align_gpu_prefill_graph_cache_mode(s, 2) == ALIGN_GPU_CONFIG);
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == 0);
    assert(align_gpu_workspace_retain_mode(s, 0) == ALIGN_GPU_CONFIG);
    assert(align_gpu_plan_begin(s) == ALIGN_GPU_CONFIG);
    assert(align_gpu_native_conv_copy_mode(s, 1) == ALIGN_GPU_CONFIG);
    assert(align_gpu_native_prefill_state_copy_mode(s, 1) == ALIGN_GPU_CONFIG);
    assert(align_gpu_native_copy_greedy_mode(s, 1) == ALIGN_GPU_CONFIG);
    return s;
}

static int admission(struct align_gpu_device_state *s) {
    assert(align_gpu_memory_admit(s, 256, 128, workspace_limit, META, 64, 0) == 0);
    assert(align_gpu_prefill_graph_cache_mode(s, 0) == ALIGN_GPU_CONFIG);
    assert(align_gpu_memory_allocate(s) == 0);
    float weights[16] = {0};
    assert(align_gpu_weights_begin(s, 1) == 0);
    assert(align_gpu_weight_add(s, GGML_TYPE_F32, 1, 64, 1, 1, 1) == 0);
    for (int chunk = 0; chunk < 4; chunk++)
        assert(align_gpu_weight_upload(s, 0, chunk * 64, weights, sizeof(weights)) == 0);
    assert(align_gpu_weights_finish(s) == 0);
    assert(align_gpu_kv_begin(s, 1) == 0);
    assert(align_gpu_kv_add(s, GGML_TYPE_F32, 1, 32, 1, 1, 1) == 0);
    assert(align_gpu_kv_finish(s) == 0);
    assert(align_gpu_inputs_begin(s, 1) == 0);
    assert(align_gpu_input_add(s, GGML_TYPE_F32, 1, INPUTS, 1, 1, 1) == 0);
    assert(align_gpu_inputs_finish(s) == 0);
    assert(align_gpu_graph_context_open(s, 0, META) == NULL); /* Span precheck. */
    assert(s->prefill_entries[0].ctx == NULL);
    init_ordinal = 0;
    graph_init_phase = 1;
    void *ctx = align_gpu_graph_context_open(s, 0, 65536);
    graph_init_phase = 0;
    if (context_failure >= 0) {
        assert(ctx == NULL && s->workspace_failed);
        for (int i = 0; i < 4; ++i)
            assert((s->prefill_entries[i].ctx != NULL) == (i < context_failure));
        return 0;
    }
    if (ALIGN_GPU_FORCE_PREFILL_CACHE_OPEN) {
        assert(ctx == NULL && s->workspace_failed);
        assert(s->prefill_entries[0].ctx != NULL && s->prefill_entries[1].ctx != NULL);
        assert(s->prefill_entries[2].ctx == NULL);
        return 0;
    }
    assert(ctx != NULL && s->graph_contexts[0] == NULL);
    assert(align_gpu_graph_context_open(s, 0, 65536) == NULL);
    assert(align_gpu_graph_context_open(s, 1, 65536) != NULL);
    assert(align_gpu_graph_context_open(s, 2, 65536) != NULL);
    return 1;
}

static struct ggml_cgraph *build(struct align_gpu_device_state *s, int kind,
        int length, struct ggml_tensor **out) {
    struct ggml_context *ctx = s->graph_contexts[kind];
    struct ggml_tensor *view = ggml_view_1d(ctx, align_gpu_input_at(s, 0), length, 0);
    *out = ggml_scale(ctx, view, (float) (kind + 2));
    struct ggml_cgraph *g = ggml_new_graph_custom(ctx, 32, false);
    ggml_build_forward_expand(g, *out);
    return g;
}

static void compute(struct align_gpu_device_state *s, int kind, const char *key,
        struct ggml_tensor *out, int seed) {
    float values[INPUTS], observed[INPUTS];
    for (int i = 0; i < INPUTS; ++i) values[i] = (float) (i + seed) * 0.125f;
    assert(align_gpu_input_update(s, 0, 0, values, sizeof(values)) == 0);
    assert(align_gpu_graph_compute(s, kind, key, 64, s->workspace_graphs[kind]) == 0);
    assert(align_gpu_slot_ready(s, out));
    assert(align_gpu_slot_ready(s, out)); /* Cached read fast path. */
    ggml_backend_tensor_get(out, observed, 0, ggml_nbytes(out));
    for (int64_t i = 0; i < out->ne[0]; ++i)
        assert(observed[i] == values[i] * (float) (kind + 2));
}

static void lifecycle(ggml_backend_dev_t device) {
    struct align_gpu_device_state *s = open_state(device);
    int prior_contexts = context_frees;
    if (!admission(s)) {
        align_gpu_memory_release(s);
        align_gpu_memory_release(s);
        assert(context_frees - prior_contexts == (context_failure >= 0 ? context_failure + 1 : 3));
        align_gpu_device_close(s);
        return;
    }
    char keys[6][65];
    struct ggml_tensor *out[6];
    struct ggml_cgraph *graphs[6];
    for (int i = 0; i < 6; ++i) { memset(keys[i], 'a' + i, 64); keys[i][64] = 0; }
    for (int i = 0; i < 4; ++i) {
        uint64_t generation = s->workspace_content_generation;
        assert(align_gpu_prefill_graph_cache_activate(s, -1, keys[i], 64) == ALIGN_GPU_CONFIG);
        assert(align_gpu_prefill_graph_cache_activate(s, 4, keys[i], 64) == ALIGN_GPU_CONFIG);
        assert(align_gpu_prefill_graph_cache_activate(s, i, NULL, 64) == ALIGN_GPU_CONFIG);
        assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 63) == ALIGN_GPU_CONFIG);
        assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 65) == ALIGN_GPU_CONFIG);
        assert(align_gpu_prefill_graph_cache_activate(s, i, "X", 1) == ALIGN_GPU_CONFIG);
        char bad_key[64]; memset(bad_key, 'A', sizeof(bad_key));
        assert(align_gpu_prefill_graph_cache_activate(s, i, bad_key, 64) == ALIGN_GPU_CONFIG);
        assert(s->workspace_content_generation == generation);
        assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 64) == 0);
        keys[i][0] = '0'; /* Caller mutation must not alter the copied pending key. */
        assert(s->prefill_entries[i].pending_key[0] == 'a' + i);
        keys[i][0] = 'a' + i;
        assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 64) == ALIGN_GPU_CONFIG);
        assert(align_gpu_prefill_graph_cache_release(s, 0) == ALIGN_GPU_CONFIG);
        assert(align_gpu_graph_lookup(s, 0, keys[i], 64) == NULL);
        graphs[i] = build(s, 0, 512 << i, &out[i]);
        assert(align_gpu_graph_prepare(s, 0, keys[(i + 1) % 4], 64, graphs[i]) == ALIGN_GPU_CONFIG);
        int32_t status = align_gpu_graph_prepare(s, 0, keys[i], 64, graphs[i]);
        if (ALIGN_GPU_FORCE_PREFILL_CACHE_PUBLISH || ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE
            || ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND) {
            assert(status == ALIGN_GPU_ALLOCATION && s->workspace_failed);
            assert(!s->prefill_entries[i].prepared && s->prefill_entries[i].pending);
            assert(align_gpu_graph_lookup(s, 0, keys[i], 64) == NULL);
            assert(align_gpu_prefill_graph_cache_release(s, 1) == ALIGN_GPU_CONFIG);
            align_gpu_device_close(s);
            return;
        }
        assert(status == 0);
        compute(s, 0, keys[i], out[i], i + 1);
        if (i) assert(!align_gpu_slot_ready(s, out[i - 1]));
    }
    for (int kind = 1; kind < 3; ++kind) {
        graphs[kind + 3] = build(s, kind, 8192 << (kind - 1), &out[kind + 3]);
        assert(align_gpu_graph_prepare(s, kind, keys[kind + 3], 64, graphs[kind + 3]) == 0);
        compute(s, kind, keys[kind + 3], out[kind + 3], kind + 10);
    }
    ggml_gallocr_t allocator = s->workspace_allocator;
    for (int repeat = 0; repeat < 3; ++repeat) {
        for (int i = 0; i < 4; ++i) {
            int old_binds = binds, old_reserves = reserves;
            int64_t old_prepare = s->graph_prepare_count[0];
            assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 64) == 1);
            assert(align_gpu_graph_lookup(s, 0, keys[i], 64) == graphs[i]);
            assert(!align_gpu_slot_ready(s, out[i]));
            compute(s, 0, keys[i], out[i], 20 + repeat);
            assert(binds == old_binds && reserves == old_reserves);
            assert(s->graph_prepare_count[0] == old_prepare && s->workspace_allocator == allocator);
        }
    }
    assert(s->graph_reuse_count[0] == 12);
    int old_binds = binds;
    assert(align_gpu_prefill_graph_cache_release(s, 2) == ALIGN_GPU_CONFIG);
    assert(align_gpu_prefill_graph_cache_release(s, 0) == 0);
    assert(binds == old_binds && !align_gpu_slot_ready(s, out[3]));
    assert(align_gpu_graph_context_lookup(s, 0) == NULL);
    /* 0 -> 4 -> 0 collision, with growth and six live bindings. */
    for (int replacement = 0; replacement < 2; ++replacement) {
        const char *selected = replacement ? keys[0] : keys[4];
        assert(align_gpu_prefill_graph_cache_activate(s, 0, selected, 64) == 0);
        graphs[0] = build(s, 0, replacement ? 512 : INPUTS, &out[0]);
        old_binds = binds;
        assert(align_gpu_graph_prepare(s, 0, selected, 64, graphs[0]) == 0);
        assert(binds - old_binds == 6 && s->workspace_allocator == allocator);
        compute(s, 0, selected, out[0], 99);
        for (int kind = 1; kind < 3; ++kind)
            compute(s, kind, keys[kind + 3], out[kind + 3], 88);
        for (int i = 1; i < 4; ++i) {
            assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 64) == 1);
            compute(s, 0, keys[i], out[i], 77);
        }
    }
    assert(align_gpu_prefill_graph_cache_release(s, 1) == 0);
    assert(!s->prefill_active && !align_gpu_slot_ready(s, out[3]));
    assert(align_gpu_prefill_graph_cache_release(s, 1) == 0);
    assert(align_gpu_prefill_graph_cache_activate(s, 0, keys[0], 64) == 0);
    /* A shifted first node refuses before optimizing a new backend key. */
    ggml_new_tensor_1d(s->graph_contexts[0], GGML_TYPE_F32, 1);
    graphs[0] = build(s, 0, 512, &out[0]);
    assert(align_gpu_graph_prepare(s, 0, keys[0], 64, graphs[0]) == ALIGN_GPU_CONFIG);
    assert(s->workspace_failed);
    assert(align_gpu_prefill_graph_cache_activate(s, 1, keys[1], 64) == ALIGN_GPU_CONFIG);
    int before_close_frees = frees;
    align_gpu_memory_release(s);
    align_gpu_memory_release(s);
    assert(frees - before_close_frees == 1);
    assert(context_frees - prior_contexts == 7);
    align_gpu_device_close(s);
}

static void parked_failure(ggml_backend_dev_t device) {
    force_active = 0;
    struct align_gpu_device_state *s = open_state(device);
    assert(admission(s));
    char keys[6][64];
    struct ggml_tensor *out[6];
    for (int i = 0; i < 6; ++i) {
        memset(keys[i], '0' + i, 64);
        int kind = i < 4 ? 0 : i - 3;
        if (i < 4) assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 64) == 0);
        struct ggml_cgraph *g = build(s, kind, 512, &out[i]);
        assert(align_gpu_graph_prepare(s, kind, keys[i], 64, g) == 0);
    }
    assert(align_gpu_prefill_graph_cache_activate(s, 0, keys[4], 64) == 0);
    struct ggml_cgraph *g = build(s, 0, 8192, &out[0]);
    force_active = 1;
    assert(align_gpu_graph_prepare(s, 0, keys[4], 64, g) == ALIGN_GPU_ALLOCATION);
    assert(s->workspace_failed && !s->prefill_entries[0].prepared && s->prefill_entries[0].pending);
    assert(s->prefill_entries[1].prepared && s->graph_prepared[1] && s->graph_prepared[2]);
    assert(out[1]->data == NULL && out[4]->data == NULL);
    if (TEST_BIND) assert(out[0]->data != NULL);
    assert(!align_gpu_slot_ready(s, out[1]));
    align_gpu_device_close(s);
}

static void cache_refusals(ggml_backend_dev_t device) {
    char keys[6][64];
    for (int i = 0; i < 6; ++i) memset(keys[i], '0' + i, 64);
    for (int foreign = 0; foreign < 2; ++foreign) {
        struct align_gpu_device_state *s = open_state(device); assert(admission(s));
        assert(align_gpu_prefill_graph_cache_activate(s, 0, keys[0], 64) == 0);
        struct ggml_tensor *out;
        struct ggml_cgraph *g = build(s, 0, 512, &out);
        assert(align_gpu_graph_prepare(s, 0, keys[0], 64, g) == 0);
        assert(align_gpu_prefill_graph_cache_activate(s, 1, keys[1], 64) == 0);
        assert(align_gpu_graph_prepare(s, 0, keys[1], 64, foreign ? (void *) s : (void *) g)
            == ALIGN_GPU_CONFIG);
        assert(s->workspace_failed);
        align_gpu_device_close(s);
    }
    struct align_gpu_device_state *s = open_state(device); assert(admission(s));
    assert(align_gpu_prefill_graph_cache_activate(s, 0, keys[0], 64) == 0);
    struct ggml_tensor *out;
    build(s, 0, 512, &out);
    assert(align_gpu_prefill_graph_cache_release(s, 1) == 0);
    assert(align_gpu_prefill_graph_cache_release(s, 1) == 0);
    assert(align_gpu_prefill_graph_cache_activate(s, 0, keys[0], 64) == 0);
    struct ggml_cgraph *g = build(s, 0, INPUTS, &out);
    size_t required = 0;
    assert(align_gpu_graph_required(ggml_backend_get_default_buffer_type(s->backend), g, &required));
    int64_t exact = (int64_t) s->input_offset + (int64_t) required;
    s->graph_prepare_count[0] = INT64_MAX;
    assert(align_gpu_graph_prepare(s, 0, keys[0], 64, g) == ALIGN_GPU_CONFIG && s->workspace_failed);
    align_gpu_device_close(s);
    for (int below = 0; below < 2; ++below) {
        workspace_limit = exact - below;
        s = open_state(device); assert(admission(s));
        for (int i = 0; i < 6; ++i) {
            int kind = i < 4 ? 0 : i - 3;
            if (i < 4) assert(align_gpu_prefill_graph_cache_activate(s, i, keys[i], 64) == 0);
            g = build(s, kind, 512, &out);
            assert(align_gpu_graph_prepare(s, kind, keys[i], 64, g) == 0);
        }
        assert(align_gpu_prefill_graph_cache_activate(s, 0, keys[4], 64) == 0);
        g = build(s, 0, INPUTS, &out);
        int status = align_gpu_graph_prepare(s, 0, keys[4], 64, g);
        assert(status == (below ? ALIGN_GPU_MEMORY_BUDGET : ALIGN_GPU_OK));
        if (below) assert(s->workspace_failed && !align_gpu_slot_ready(s, out));
        else compute(s, 0, keys[4], out, 99);
        align_gpu_device_close(s);
    }
    workspace_limit = WORKSPACE;
}

static void selector_orders(ggml_backend_dev_t device) {
    struct align_gpu_device_state *s = open_state(device);
    assert(align_gpu_prefill_graph_cache_mode(s, 0) == 0);
    assert(align_gpu_workspace_retain_mode(s, 0) == 0);
    struct align_gpu_device_state before = *s;
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == ALIGN_GPU_CONFIG);
    assert(memcmp(s, &before, sizeof(*s)) == 0);
    assert(align_gpu_workspace_retain_mode(s, 1) == 0);
    assert(align_gpu_plan_begin(s) == 0);
    before = *s;
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == ALIGN_GPU_CONFIG);
    assert(memcmp(s, &before, sizeof(*s)) == 0);
    assert(align_gpu_plan_cancel(s) == 0);
    assert(s->retain_workspace && !s->shape_planning && !s->prefill_graph_cache);
    int32_t (*helpers[])(void *, int32_t) = {
        align_gpu_native_conv_copy_mode, align_gpu_native_prefill_state_copy_mode,
        align_gpu_native_copy_greedy_mode,
    };
    int *selected[] = {&s->native_conv_copy, &s->native_prefill_state_copy,
                      &s->native_copy_greedy};
    for (int i = 0; i < 3; ++i) {
        before = *s;
        /* CUDA refuses these Metal-only helpers before cache selection. */
        assert(helpers[i](s, 1) == ALIGN_GPU_UNSUPPORTED);
        assert(memcmp(s, &before, sizeof(*s)) == 0);
        /* Exercise the backend-neutral guard on an already selected policy. */
        *selected[i] = 1;
        before = *s;
        assert(align_gpu_prefill_graph_cache_mode(s, 1) == ALIGN_GPU_CONFIG);
        assert(memcmp(s, &before, sizeof(*s)) == 0);
        *selected[i] = 0;
        assert(align_gpu_prefill_graph_cache_mode(s, 1) == 0);
        before = *s;
        assert(helpers[i](s, 1) == ALIGN_GPU_CONFIG);
        assert(align_gpu_workspace_retain_mode(s, 0) == ALIGN_GPU_CONFIG);
        assert(align_gpu_plan_begin(s) == ALIGN_GPU_CONFIG);
        assert(memcmp(s, &before, sizeof(*s)) == 0);
        assert(align_gpu_prefill_graph_cache_mode(s, 0) == 0);
    }
    align_gpu_device_close(s);
    puts("prefill_graph_cache selector orders: refusal preserves policy/state");
}

static void indexed_hit(ggml_backend_dev_t device) {
    struct align_gpu_device_state *s = open_state(device);
    assert(align_gpu_attention_select(s, 1) == 0);
    assert(align_gpu_attention_select(s, 2) == 0);
    assert(align_gpu_memory_admit(s, 256, 128, WORKSPACE, META, 64, 0) == 0);
    assert(align_gpu_memory_allocate(s) == 0);
    float weights[64] = {0};
    assert(align_gpu_weights_begin(s, 1) == 0);
    assert(align_gpu_weight_add(s, GGML_TYPE_F32, 1, 64, 1, 1, 1) == 0);
    for (int chunk = 0; chunk < 4; ++chunk)
        assert(align_gpu_weight_upload(s, 0, chunk * 64, weights, 64) == 0);
    assert(align_gpu_weights_finish(s) == 0);
    assert(align_gpu_kv_begin(s, 1) == 0);
    assert(align_gpu_kv_add(s, GGML_TYPE_F32, 2, 4, 8, 1, 1) == 0);
    assert(align_gpu_kv_finish(s) == 0);
    assert(align_gpu_inputs_begin(s, 2) == 0);
    assert(align_gpu_input_add(s, GGML_TYPE_F32, 2, 4, 4, 1, 1) == 0);
    assert(align_gpu_input_add(s, GGML_TYPE_I32, 1, 4, 1, 1, 1) == 1);
    assert(align_gpu_inputs_finish(s) == 0);
    assert(align_gpu_graph_context_open(s, 0, 65536) != NULL);
    char key[64]; memset(key, 'a', sizeof(key));
    assert(align_gpu_prefill_graph_cache_activate(s, 0, key, sizeof(key)) == 0);
    unsigned char slots[32] = {0};
    assert(align_ggml_slots_init(slots, sizeof(slots)) == 0);
    assert(align_gpu_input_slot(s, 0, slots, 0) == 0);
    assert(align_gpu_kv_write_indexed_prefix(s, 0, 0, 0, 1, 6, slots, 1, 0) == 0);
    struct ggml_tensor *out = align_ggml_slot_load(slots, 1);
    struct ggml_cgraph *graph = ggml_new_graph_custom(s->graph_contexts[0], 32, false);
    ggml_build_forward_expand(graph, out);
    assert(align_gpu_graph_prepare(s, 0, key, sizeof(key), graph) == 0);
    assert(s->prefill_entries[0].rows_registered && !s->prefill_rows_valid);
    int32_t rows[4] = {2, 3, 4, 5}, observed_rows[4];
    float values[16], observed[24];
    for (int iteration = 0; iteration < 3; ++iteration) {
        if (iteration) {
            assert(align_gpu_prefill_graph_cache_activate(s, 0, key, sizeof(key)) == 1);
            assert(align_gpu_graph_lookup(s, 0, key, sizeof(key)) == graph);
            assert(s->prefill_rows_registered && !s->prefill_rows_valid);
            assert(!align_gpu_slot_ready(s, out));
        }
        uint64_t generation = s->workspace_content_generation;
        int64_t executions = s->graph_execution_count[0], updated = s->input_updated_bytes;
        assert(align_gpu_graph_compute(s, 0, key, sizeof(key), graph) == ALIGN_GPU_CONFIG);
        assert(s->workspace_content_generation == generation && s->graph_execution_count[0] == executions);
        int32_t wrong[4] = {2, 3, 4, 99};
        assert(align_gpu_input_update(s, 1, 0, wrong, sizeof(wrong)) == ALIGN_GPU_CONFIG);
        assert(align_gpu_input_update(s, 1, 0, rows, sizeof(rows) - 4) == ALIGN_GPU_CONFIG);
        assert(align_gpu_input_update(s, 1, 4, rows, sizeof(rows) - 4) == ALIGN_GPU_CONFIG);
        assert(!s->prefill_rows_valid && s->input_updated_bytes == updated);
        if (iteration) {
            ggml_backend_tensor_get(align_gpu_input_at(s, 1), observed_rows, 0, sizeof(observed_rows));
            assert(memcmp(observed_rows, rows, sizeof(rows)) == 0);
        }
        for (int i = 0; i < 16; ++i) values[i] = (float) (i + 1 + iteration * 100);
        ggml_backend_tensor_memset(align_gpu_kv_at(s, 0), 0, 0, 128);
        assert(align_gpu_input_update(s, 0, 0, values, sizeof(values)) == 0);
        assert(align_gpu_input_update(s, 1, 0, rows, sizeof(rows)) == 0);
        assert(align_gpu_graph_compute(s, 0, key, sizeof(key), graph) == 0);
        assert(!s->prefill_rows_valid && align_gpu_slot_ready(s, out));
        ggml_backend_tensor_get(out, observed, 0, sizeof(observed));
        for (int i = 0; i < 24; ++i) assert(observed[i] == (i < 8 ? 0.0f : values[i - 8]));
        executions = s->graph_execution_count[0];
        assert(align_gpu_graph_compute(s, 0, key, sizeof(key), graph) == ALIGN_GPU_CONFIG);
        assert(s->graph_execution_count[0] == executions);
    }
    assert(s->graph_prepare_count[0] == 1 && s->graph_reuse_count[0] == 2);
    assert(align_gpu_prefill_graph_cache_release(s, 0) == 0);
    assert(!align_gpu_slot_ready(s, out));
    align_gpu_device_close(s);
    puts("prefill_graph_cache indexed hit: missing/wrong/consumed indices refuse; fresh rows compute");
}

int main(int argc, char **argv) {
    assert(argc == 2);
    unsetenv("GGML_CUDA_DISABLE_GRAPHS");
    unsetenv("GGML_CUDA_GRAPH_OPT");
    ggml_backend_reg_t registry = ggml_backend_load(argv[1]);
    assert(registry != NULL && ggml_backend_reg_dev_count(registry) >= 1);
    ggml_backend_dev_t device = ggml_backend_reg_dev_get(registry, 0);
    struct align_gpu_device_state *s = open_state(device);
    assert(align_gpu_prefill_graph_cache_mode(s, 0) == 0);
    setenv("GGML_CUDA_DISABLE_GRAPHS", "0", 1);
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == ALIGN_GPU_CONFIG);
    unsetenv("GGML_CUDA_DISABLE_GRAPHS");
    setenv("GGML_CUDA_GRAPH_OPT", "", 1);
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == ALIGN_GPU_CONFIG);
    setenv("GGML_CUDA_GRAPH_OPT", "1", 1);
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == ALIGN_GPU_CONFIG);
    setenv("GGML_CUDA_GRAPH_OPT", "0", 1);
    assert(align_gpu_prefill_graph_cache_mode(s, 1) == 0);
    unsetenv("GGML_CUDA_GRAPH_OPT");
    align_gpu_device_close(s);
    lifecycle(device);
    if (TEST_RESERVE || TEST_BIND) parked_failure(device);
    if (!ALIGN_GPU_FORCE_PREFILL_CACHE_OPEN && !ALIGN_GPU_FORCE_PREFILL_CACHE_PUBLISH
        && !ALIGN_GPU_FORCE_WORKSPACE_RETAIN_RESERVE && !ALIGN_GPU_FORCE_WORKSPACE_RETAIN_BIND) {
        selector_orders(device);
        indexed_hit(device);
        cache_refusals(device);
        for (int failure = 0; failure < 4; ++failure) {
            context_failure = failure;
            lifecycle(device);
        }
        context_failure = -1;
        for (int poison = 0; poison < 4; ++poison) {
            s = open_state(device); assert(admission(s));
            char key[64]; memset(key, '0', sizeof(key));
            assert(align_gpu_prefill_graph_cache_activate(s, 0, key, 64) == 0);
            struct ggml_tensor *result;
            struct ggml_cgraph *g = build(s, 0, 512, &result);
            assert(align_gpu_graph_prepare(s, 0, key, 64, g) == 0);
            compute(s, 0, key, result, 5);
            if (poison == 0) s->inputs_failed = 1;
            if (poison == 1) s->weights_failed = 1;
            if (poison == 2) s->kv_failed = 1;
            if (poison == 3) s->observation_failed = 1;
            uint64_t generation = s->workspace_content_generation;
            assert(align_gpu_prefill_graph_cache_activate(s, 0, key, 64) == ALIGN_GPU_CONFIG);
            assert(align_gpu_prefill_graph_cache_release(s, 0) == ALIGN_GPU_CONFIG);
            assert(align_gpu_prefill_graph_cache_release(s, 1) == ALIGN_GPU_CONFIG);
            assert(align_gpu_graph_context_lookup(s, 0) == NULL);
            assert(align_gpu_graph_lookup(s, 0, key, 64) == NULL);
            assert(align_gpu_graph_compute(s, 0, key, 64, g) == ALIGN_GPU_CONFIG);
            assert(!align_gpu_slot_ready(s, result));
            assert(s->workspace_content_generation == generation);
            align_gpu_device_close(s);
        }
        s = open_state(device);
        assert(admission(s));
        char key[64]; memset(key, '0', sizeof(key));
        s->workspace_content_generation = UINT64_MAX;
        assert(align_gpu_prefill_graph_cache_activate(s, 0, key, 64) == ALIGN_GPU_CONFIG);
        assert(s->workspace_failed && align_gpu_prefill_graph_cache_release(s, 1) == ALIGN_GPU_CONFIG);
        align_gpu_device_close(s);
        for (int kind = 0; kind < 3; ++kind) {
            s = open_state(device); assert(admission(s));
            if (kind == 0) assert(align_gpu_prefill_graph_cache_activate(s, 0, key, 64) == 0);
            struct ggml_tensor *result;
            struct ggml_cgraph *g = build(s, kind, 512, &result);
            assert(align_gpu_graph_prepare(s, kind, key, 64, g) == 0);
            if (kind == 0) {
                assert(align_gpu_prefill_graph_cache_release(s, 1) == 0);
                assert(align_gpu_prefill_graph_cache_activate(s, 0, key, 64) == 0);
            } else assert(align_gpu_graph_invalidate(s, kind) == 0);
            ggml_new_tensor_1d(s->graph_contexts[kind], GGML_TYPE_F32, 1);
            g = build(s, kind, 512, &result);
            assert(align_gpu_graph_prepare(s, kind, key, 64, g) == ALIGN_GPU_CONFIG);
            assert(s->workspace_failed);
            align_gpu_device_close(s);
        }
    }
    printf("prefill_graph_cache lifecycle passed: entry_bytes=%zu binds=%d reserves=%d\n",
        sizeof(struct align_gpu_prefill_entry) * ALIGN_GPU_PREFILL_ENTRIES, binds, reserves);
    assert(sizeof(struct align_gpu_prefill_entry) * ALIGN_GPU_PREFILL_ENTRIES + 4160 + 32 < 65536);
    return 0;
}
