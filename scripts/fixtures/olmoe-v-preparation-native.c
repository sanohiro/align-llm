/* The owner includes the production implementation unchanged so that the real constructors and
 * static callbacks are exercised together. Native metadata and fault injection stay in this file.
 */
#include <stdio.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <sys/resource.h>

#ifdef VPREP_REAL
static _Noreturn void vprep_abort_at(int line) {
    fprintf(stderr, "production callback invariant at shim line %d\n", line);
    abort();
}
#define abort() vprep_abort_at(__LINE__)
#define ggml_custom_4d vprep_custom_4d
#include "ggml_shim.c"
#undef ggml_custom_4d
#undef abort
extern struct ggml_tensor *ggml_custom_4d(
    struct ggml_context *, enum ggml_type, int64_t, int64_t, int64_t, int64_t,
    struct ggml_tensor **, int, ggml_custom_op_t, int, void *);
typedef struct ggml_tensor Tensor;
static int custom_calls;
static int last_refusal_calls;
static int expect_construction;
static int fail_constructor;
static int corrupt_constructor;
static atomic_uint concat_workers, pad_workers, worker_mismatch;

static void observe_worker(atomic_uint *workers, int ith, int nth) {
    if (nth != 4 || ith < 0 || ith >= 4) atomic_store(&worker_mismatch, 1);
    if (ith >= 0 && ith < 4) {
        unsigned int bit = 1u << ith;
        if (atomic_fetch_or(workers, bit) & bit) atomic_store(&worker_mismatch, 1);
    }
}

static void observe_concat(Tensor *dst, int ith, int nth, void *userdata) {
    observe_worker(&concat_workers, ith, nth);
    align_ggml_v_concat_f32(dst, ith, nth, userdata);
}

static void observe_pad(Tensor *dst, int ith, int nth, void *userdata) {
    observe_worker(&pad_workers, ith, nth);
    align_ggml_v_pad_f32(dst, ith, nth, userdata);
}

struct ggml_tensor *vprep_custom_4d(
    struct ggml_context *ctx, enum ggml_type type, int64_t d, int64_t n, int64_t h,
    int64_t outer, struct ggml_tensor **args, int count, ggml_custom_op_t callback,
    int tasks, void *userdata) {
    struct ggml_tensor *result;
    if (tasks != 1 || userdata != NULL || (count != 1 && count != 2)) abort();
    if (callback != (count == 2 ? align_ggml_v_concat_f32 : align_ggml_v_pad_f32)) abort();
    custom_calls++;
    if (fail_constructor) return NULL;
    result = ggml_custom_4d(ctx, type, d, n, h, outer, args, count,
                            count == 2 ? observe_concat : observe_pad, tasks, userdata);
    if (result && corrupt_constructor >= 1 && corrupt_constructor <= 4)
        result->nb[corrupt_constructor - 1] += 4;
    if (result && corrupt_constructor >= 5 && corrupt_constructor <= 8)
        result->ne[corrupt_constructor - 5] += 1;
    if (result && corrupt_constructor == 9) result->type = GGML_TYPE_I32;
    return result;
}
#else
#include "ggml_shim_stub.c"
typedef align_stub_tensor Tensor;
#endif

static void require(int condition, const char *label) {
    if (!condition) {
        fprintf(stderr, "V preparation native failure: %s\n", label);
        exit(1);
    }
}

typedef struct Fixture {
    uint64_t slots[18];
    uint64_t initial_slots[16];
    void *inputs;
    void *ctx;
    void *buffer;
    void *allocator;
} Fixture;

static void *device;
static void *backend;

static Tensor *tensor(Fixture *f, int slot) {
    return (Tensor *) align_ggml_slot_load(f->slots, slot);
}

static unsigned char *data(Tensor *t) {
#ifdef VPREP_REAL
    return (unsigned char *) ggml_get_data(t);
#else
    return t->data;
#endif
}

static void start(Fixture *f, int64_t d, int64_t n, int64_t h) {
    memset(f, 0, sizeof(*f));
    f->inputs = align_ggml_context_open(1024 * 1024);
    f->ctx = align_ggml_context_open(1024 * 1024);
    require(f->inputs != NULL && f->ctx != NULL, "context construction");
    require(align_ggml_slots_init(f->slots, sizeof(f->slots)) == 0, "slot initialization");
    require(align_ggml_slot_new_tensor_3d(f->inputs, f->slots, 0, 0, n, d, h) == 0,
            "past tensor construction");
    require(align_ggml_slot_new_tensor_3d(f->inputs, f->slots, 1, 0, 1, d, h) == 0,
            "current tensor construction");
    require(align_ggml_slot_new_tensor_3d(f->inputs, f->slots, 7, 0, 1, 1, 1) == 0,
            "output sentinel construction");
    memcpy(f->initial_slots, f->slots + 2, sizeof(f->initial_slots));
}

static void finish(Fixture *f) {
    if (f->allocator) align_ggml_gallocr_free(f->allocator);
    if (f->ctx) align_ggml_context_close(f->ctx);
    if (f->buffer) align_ggml_buffer_free(f->buffer);
    if (f->inputs) align_ggml_context_close(f->inputs);
#ifndef VPREP_REAL
    for (int i = 0; i < ALIGN_STUB_MAX_CONTEXTS; i++)
        require(!align_stub_context_used[i], "context reclamation");
    for (int i = 0; i < ALIGN_STUB_MAX_GALLOCRS; i++)
        require(!align_stub_gallocrs[i].used, "allocator reclamation");
    for (int i = 0; i < ALIGN_STUB_MAX_GRAPHS; i++)
        require(!align_stub_graphs[i].used, "graph reclamation");
#endif
}

static const uint32_t patterns[] = {
    0x00000000u, 0x80000000u, 0x00000001u, 0x807fffffu, 0x3f800000u,
    0x7f800000u, 0xff800000u, 0x7fc00001u, 0xffc12345u, 0x7f800001u, 0xff812345u,
};

static void pattern_bytes(unsigned char *out, size_t bytes, size_t offset) {
    for (size_t at = 0; at < bytes; at += 4) {
        uint32_t bits = patterns[(at / 4 + offset) % (sizeof(patterns) / sizeof(patterns[0]))];
        memcpy(out + at, &bits, 4);
    }
}

static void upload(Fixture *f, int slot, size_t offset) {
    size_t bytes = (size_t) align_ggml_slot_nbytes(f->slots, slot);
    unsigned char *source = malloc(bytes);
    require(source != NULL, "input image allocation");
    pattern_bytes(source, bytes, offset);
    require(align_ggml_slot_set(f->slots, slot, source, 0, (int64_t) bytes) == 0, "input upload");
    free(source);
}

/* Prevent a constructor's temporary args array accidentally surviving until graph compute. */
static void overwrite_stack(void) {
    volatile unsigned char bytes[16384];
    for (size_t i = 0; i < sizeof(bytes); i++) bytes[i] = (unsigned char) i;
}

static void *allocate_graph(Fixture *f, int first, int second) {
    void *graph = align_ggml_graph_new(f->ctx);
    require(graph != NULL, "graph construction");
    require(align_ggml_graph_expand(graph, f->slots, first) == 0, "candidate graph expansion");
    if (second >= 0)
        require(align_ggml_graph_expand(graph, f->slots, second) == 0, "reference graph expansion");
    f->allocator = align_ggml_gallocr_new(backend);
    require(f->allocator != NULL, "allocator construction");
    require(align_ggml_gallocr_reserve(f->allocator, graph) == 0, "graph reserve");
    require(align_ggml_gallocr_alloc(f->allocator, graph) == 0, "graph allocate");
    return graph;
}

static void graph_case(int64_t d, int64_t n, int64_t h, int64_t padding, int from_permute) {
    Fixture f;
    size_t past_row = (size_t) n * 4;
    size_t current_row = 4;
    size_t concat_row = past_row + current_row;
    size_t padded_row = concat_row + (size_t) padding * 4;
    size_t rows = (size_t) d * (size_t) h;
    start(&f, d, n, h);
    if (from_permute)
        require(align_ggml_slot_new_tensor_3d(f.inputs, f.slots, 8, 0, d, h, 1) == 0,
                "current V before permutation");
    f.buffer = align_ggml_alloc_remaining(f.inputs, backend);
    require(f.buffer != NULL, "input allocation");
    upload(&f, 0, 0);
    if (from_permute) {
        upload(&f, 8, 7);
        require(align_ggml_op_permute(f.ctx, f.slots, 9, 8, 1, 2, 0, 3) == 0,
                "row21 current V permutation");
#ifdef VPREP_REAL
        int calls_before = custom_calls;
        Tensor *sentinel = tensor(&f, 7);
        require(tensor(&f, 9)->nb[0] == 4 * rows && tensor(&f, 9)->ne[0] == 1,
                "row21 noncanonical singleton stride");
        require(align_ggml_op_v_concat_f32(f.ctx, f.slots, 7, 0, 9) == ALIGN_GGML_SHAPE,
                "vprep-current-contiguous: raw row21 refuses");
        require(custom_calls == calls_before && tensor(&f, 7) == sentinel,
                "raw row21 refuses before construction or output overwrite");
#endif
        require(align_ggml_op_cont_3d(f.ctx, f.slots, 1, 9, 1, d, h) == 0,
                "vprep-current-contiguous: row22 materialization");
        require(align_ggml_slot_mark_output(f.slots, 1) == 0, "retain canonical-current oracle");
        /* Give the original arm its own current-materialization chain. Both graph expansions then
         * share leaves only, including in the engine stub's independent expansion walks. */
        require(align_ggml_op_permute(f.ctx, f.slots, 11, 8, 1, 2, 0, 3) == 0,
                "original current V permutation");
        require(align_ggml_op_cont_3d(f.ctx, f.slots, 12, 11, 1, d, h) == 0,
                "original current V materialization");
    } else {
        upload(&f, 1, 7);
    }
    require(align_ggml_op_v_concat_f32(f.ctx, f.slots, 2, 0, 1) == 0, "vprep-concat-bits");
    require(align_ggml_op_v_pad_f32(f.ctx, f.slots, 3, 2, padding) == 0, "vprep-pad-bits");
    require(align_ggml_op_concat(f.ctx, f.slots, 4, 0, from_permute ? 12 : 1, 0) == 0,
            "original concat");
    require(align_ggml_op_pad(f.ctx, f.slots, 5, 4, (int32_t) padding, 0, 0, 0) == 0,
            "original padding");
    for (int slot = 2; slot <= 5; slot++)
        require(align_ggml_slot_mark_output(f.slots, slot) == 0, "mark concat/output");
    require(align_ggml_op_cont_3d(f.ctx, f.slots, 6, 3, n + 1 + padding, d, h) == 0,
            "downstream materialization");
    void *graph = allocate_graph(&f, 6, 5);
    require(align_ggml_graph_node_count(graph) == (from_permute ? 9 : 5),
            "two custom nodes preserve graph counts");
    require(tensor(&f, 2)->src[0] == tensor(&f, 0) && tensor(&f, 2)->src[1] == tensor(&f, 1)
            && tensor(&f, 3)->src[0] == tensor(&f, 2), "vprep-callback-lifetime");
    require(data(tensor(&f, 2)) != data(tensor(&f, 0))
            && data(tensor(&f, 2)) != data(tensor(&f, 1))
            && data(tensor(&f, 3)) != data(tensor(&f, 2)), "distinct output storage");
#ifdef VPREP_REAL
    /* A graph may have more workers than this custom node requests. Idle workers must not inspect
     * storage; the graph's worker zero performs the one write, with the existing graph barrier. */
    align_ggml_v_concat_f32(NULL, 1, 4, NULL);
    align_ggml_v_pad_f32(NULL, 3, 4, NULL);
    atomic_store(&concat_workers, 0);
    atomic_store(&pad_workers, 0);
    atomic_store(&worker_mismatch, 0);
#endif
    overwrite_stack();
    require(align_ggml_graph_compute(backend, graph) == 0, "native compute");
#ifdef VPREP_REAL
    require(atomic_load(&concat_workers) == 15 && atomic_load(&pad_workers) == 15
            && !atomic_load(&worker_mismatch), "vprep-task-count: four graph workers once each");
#endif
    require((size_t) align_ggml_slot_nbytes(f.slots, 2) == concat_row * rows,
            "vprep-concat-row-layout");
    require((size_t) align_ggml_slot_nbytes(f.slots, 3) == padded_row * rows,
            "vprep-pad-row-layout");
    require(memcmp(data(tensor(&f, 2)), data(tensor(&f, 4)), concat_row * rows) == 0,
            "concat parity against original graph");
    require(memcmp(data(tensor(&f, 3)), data(tensor(&f, 5)), padded_row * rows) == 0,
            "pad parity against original graph");
    require(memcmp(data(tensor(&f, 3)), data(tensor(&f, 6)), padded_row * rows) == 0,
            "downstream consumes padded bytes");
    if (padding == 0)
        require(memcmp(data(tensor(&f, 2)), data(tensor(&f, 3)), concat_row * rows) == 0,
                "vprep-pad-zero-width-delta");
    for (size_t row = 0; row < rows; row++) {
        unsigned char *concat = data(tensor(&f, 2)) + row * concat_row;
        unsigned char *padded = data(tensor(&f, 3)) + row * padded_row;
        require(memcmp(concat, data(tensor(&f, 0)) + row * past_row, past_row) == 0,
                "vprep-special-bits: past");
        require(memcmp(concat + past_row, data(tensor(&f, 1)) + row * current_row,
                       current_row) == 0, "vprep-special-bits: current");
        require(memcmp(padded, concat, concat_row) == 0, "vprep-marked-concat");
        for (size_t at = concat_row; at < padded_row; at++)
            require(padded[at] == 0, "padding is positive zero bytes");
    }
    finish(&f);
}

static void pad_limit_case(void) {
    Fixture f;
    start(&f, 1, 1, 2);
    f.buffer = align_ggml_alloc_remaining(f.inputs, backend);
    require(f.buffer != NULL, "pad-only input allocation");
    upload(&f, 0, 1);
    require(align_ggml_op_v_pad_f32(f.ctx, f.slots, 2, 0, 4095) == 0, "maximum legal padding");
    void *graph = allocate_graph(&f, 2, -1);
    require(align_ggml_graph_compute(backend, graph) == 0, "maximum padding compute");
    unsigned char *output = data(tensor(&f, 2));
    for (size_t head = 0; head < 2; head++) {
        require(memcmp(output + head * 16384, data(tensor(&f, 0)) + head * 4, 4) == 0,
                "maximum padding copied source");
        for (size_t at = 4; at < 16384; at++)
            require(output[head * 16384 + at] == 0, "maximum padding tail");
    }
    finish(&f);
}

static void refused(Fixture *f, int actual, int expected, void *before, const char *label) {
    void *after;
    require(actual == expected, label);
    memcpy(&after, (unsigned char *) f->slots + 16 + 7 * 8, sizeof(after));
    require(after == before, "refusal preserves output slot");
    require(memcmp(f->slots + 2, f->initial_slots, sizeof(f->initial_slots)) == 0,
            "refusal preserves all input and output handles");
#ifdef VPREP_REAL
    require(custom_calls - last_refusal_calls == expect_construction,
            "validation precedes native construction");
    last_refusal_calls = custom_calls;
#endif
}

static void refusals(void) {
    Fixture f;
    start(&f, 3, 2, 2);
    Tensor *past = tensor(&f, 0), *current = tensor(&f, 1);
    Tensor saved_past = *past, saved_current = *current;
    void *before = tensor(&f, 7);
#ifdef VPREP_REAL
    last_refusal_calls = custom_calls;
#endif
#define CONCAT(label, code) refused(&f, align_ggml_op_v_concat_f32(f.ctx, f.slots, 7, 0, 1), code, before, label)
#define PAD(label, value, code) refused(&f, align_ggml_op_v_pad_f32(f.ctx, f.slots, 7, 0, value), code, before, label)
    refused(&f, align_ggml_op_v_concat_f32(NULL, NULL, -1, -1, -1), ALIGN_GGML_INIT, before,
            "vprep-concat-null-context");
    refused(&f, align_ggml_op_v_pad_f32(NULL, NULL, -1, -1, -1), ALIGN_GGML_INIT, before,
            "vprep-pad-null-context");
    uint64_t saved_magic = f.slots[0];
    f.slots[0] = 0;
    CONCAT("vprep-concat-slot-precedence: magic", ALIGN_GGML_SLOT);
    PAD("vprep-pad-slot-precedence: magic", -1, ALIGN_GGML_SLOT);
    f.slots[0] = saved_magic;
    before = tensor(&f, 7);
    uint64_t saved_capacity = f.slots[1];
    f.slots[1] = 0;
    CONCAT("vprep-concat-slot-precedence: capacity", ALIGN_GGML_SLOT);
    PAD("vprep-pad-slot-precedence: capacity", -1, ALIGN_GGML_SLOT);
    f.slots[1] = 65537;
    CONCAT("vprep-concat-slot-precedence: oversized capacity", ALIGN_GGML_SLOT);
    PAD("vprep-pad-slot-precedence: oversized capacity", -1, ALIGN_GGML_SLOT);
    f.slots[1] = saved_capacity;
    refused(&f, align_ggml_op_v_concat_f32(f.ctx, (unsigned char *) f.slots + 1, 7, 0, 1),
            ALIGN_GGML_SLOT, before, "vprep-concat-slot-precedence: unaligned store");
    refused(&f, align_ggml_op_v_pad_f32(f.ctx, NULL, 7, 0, -1),
            ALIGN_GGML_SLOT, before, "vprep-pad-slot-precedence: null store");
    for (int input = -1; input <= 16; input += 17) {
        refused(&f, align_ggml_op_v_concat_f32(f.ctx, f.slots, 7, input, 1), ALIGN_GGML_SLOT,
                before, "vprep-concat-slot-precedence: input");
        refused(&f, align_ggml_op_v_concat_f32(f.ctx, f.slots, 7, 0, input), ALIGN_GGML_SLOT,
                before, "vprep-concat-slot-precedence: current input");
        refused(&f, align_ggml_op_v_pad_f32(f.ctx, f.slots, 7, input, -1), ALIGN_GGML_SLOT,
                before, "vprep-pad-slot-precedence: input");
    }
    refused(&f, align_ggml_op_v_concat_f32(f.ctx, f.slots, 7, 0, 15), ALIGN_GGML_SLOT, before,
            "vprep-concat-slot-precedence: empty");
    refused(&f, align_ggml_op_v_pad_f32(f.ctx, f.slots, 7, 15, -1), ALIGN_GGML_SLOT, before,
            "vprep-pad-slot-precedence: empty");
    for (int out = -1; out <= 16; out += 17) {
        refused(&f, align_ggml_op_v_concat_f32(f.ctx, f.slots, out, 0, 1), ALIGN_GGML_SLOT,
                before, "vprep-concat-slot-precedence: out");
        refused(&f, align_ggml_op_v_pad_f32(f.ctx, f.slots, out, 0, -1), ALIGN_GGML_SLOT,
                before, "vprep-pad-slot-precedence: out");
    }
    past->type = 26;
    refused(&f, align_ggml_op_v_concat_f32(f.ctx, f.slots, 0, 0, 1), ALIGN_GGML_SLOT, before,
            "vprep-concat-out-alias");
    refused(&f, align_ggml_op_v_concat_f32(f.ctx, f.slots, 1, 0, 1), ALIGN_GGML_SLOT, before,
            "vprep-concat-out-alias: current");
    refused(&f, align_ggml_op_v_pad_f32(f.ctx, f.slots, 0, 0, -1), ALIGN_GGML_SLOT, before,
            "vprep-pad-out-alias");
    CONCAT("vprep-concat-type", ALIGN_GGML_TYPE);
    PAD("vprep-pad-type precedes padding", -1, ALIGN_GGML_TYPE);
    *past = saved_past;
    current->type = 26;
    CONCAT("vprep-concat-current-type", ALIGN_GGML_TYPE);
    *current = saved_current;
    for (int dimension = 0; dimension < 4; dimension++) {
        past->ne[dimension] = dimension == 3 ? 2 : 0;
        CONCAT("vprep-concat-shape", ALIGN_GGML_SHAPE);
        PAD("vprep-pad-shape", 0, ALIGN_GGML_SHAPE);
        *past = saved_past;
        current->ne[dimension] = dimension == 3 ? 2 : -1;
        CONCAT("vprep-concat-current-shape", ALIGN_GGML_SHAPE);
        *current = saved_current;
    }
    current->ne[0] = 2;
    CONCAT("vprep-concat-current-columns", ALIGN_GGML_SHAPE);
    *current = saved_current;
    current->ne[1] = 4;
    CONCAT("vprep-concat-head-dimension", ALIGN_GGML_SHAPE);
    *current = saved_current;
    current->ne[2] = 3;
    CONCAT("vprep-concat-head-count", ALIGN_GGML_SHAPE);
    *current = saved_current;
    PAD("vprep-pad-negative", -1, ALIGN_GGML_SHAPE);
    PAD("vprep-pad-width", 4095, ALIGN_GGML_SHAPE);
    PAD("vprep-pad-padding-cap", 4097, ALIGN_GGML_SHAPE);
    PAD("vprep-pad-overflow", INT64_MAX, ALIGN_GGML_SHAPE);
    const int64_t large[][3] = {
        {INT64_MAX, 2, 2}, {3, INT64_MAX, 2}, {3, 2, INT64_MAX},
        {1, INT64_MAX / 4 + 1, 1}, {4095, 4097, 1}, {4096, 4096, 1},
    };
    for (size_t i = 0; i < sizeof(large) / sizeof(large[0]); i++) {
        for (int dim = 0; dim < 3; dim++) past->ne[dim] = large[i][dim];
        current->ne[1] = past->ne[1];
        current->ne[2] = past->ne[2];
        CONCAT("vprep-concat-overflow/cap", ALIGN_GGML_SHAPE);
        PAD("vprep-pad-overflow/cap", 1, ALIGN_GGML_SHAPE);
        *past = saved_past;
        *current = saved_current;
    }
#ifdef VPREP_REAL
    for (int stride = 0; stride < 4; stride++) {
        past->nb[stride] += 4;
        CONCAT("vprep-concat-stride", ALIGN_GGML_SHAPE);
        PAD("vprep-pad-stride", 0, ALIGN_GGML_SHAPE);
        *past = saved_past;
        current->nb[stride] += 4;
        CONCAT("vprep-concat-current-stride", ALIGN_GGML_SHAPE);
        *current = saved_current;
    }
    expect_construction = 1;
    fail_constructor = 1;
    CONCAT("vprep-init-failure: concat", ALIGN_GGML_INIT);
    PAD("vprep-init-failure: pad", 0, ALIGN_GGML_INIT);
    fail_constructor = 0;
    for (corrupt_constructor = 1; corrupt_constructor <= 9; corrupt_constructor++) {
        CONCAT("result metadata validation: concat", ALIGN_GGML_SHAPE);
        PAD("result metadata validation: pad", 0, ALIGN_GGML_SHAPE);
    }
    corrupt_constructor = 0;
    expect_construction = 0;
#else
    past->lp[0] = 28;
    CONCAT("vprep-concat-stride", ALIGN_GGML_SHAPE);
    PAD("vprep-pad-stride", 0, ALIGN_GGML_SHAPE);
    *past = saved_past;
    int saved_count = align_stub_tensor_count;
    align_stub_tensor_count = ALIGN_STUB_MAX_TENSORS;
    CONCAT("vprep-init-failure: concat", ALIGN_GGML_INIT);
    PAD("vprep-init-failure: pad", 0, ALIGN_GGML_INIT);
    align_stub_tensor_count = saved_count;
#endif
    finish(&f);
    /* Construction must admit the maximum exact element count without reading unallocated data. */
    start(&f, 4096, 4095, 1);
    require(align_ggml_op_v_concat_f32(f.ctx, f.slots, 2, 0, 1) == 0, "exact concat element cap");
    require(align_ggml_op_v_pad_f32(f.ctx, f.slots, 3, 2, 0) == 0, "exact pad element cap");
    finish(&f);
    /* These sources have valid declared strides and fit the cap; only the result exceeds it. */
    start(&f, 4097, 4095, 1);
    before = tensor(&f, 7);
#ifdef VPREP_REAL
    last_refusal_calls = custom_calls;
#endif
    CONCAT("vprep-concat-cap: result only", ALIGN_GGML_SHAPE);
    PAD("vprep-pad-cap: result only", 1, ALIGN_GGML_SHAPE);
    finish(&f);
#undef CONCAT
#undef PAD
}

static void singleton_layouts(void) {
    const int64_t dims[][4] = {{1, 1, 1, 1}, {1, 5, 2, 1}, {7, 1, 3, 1}, {2, 3, 1, 1}};
    for (size_t i = 0; i < sizeof(dims) / sizeof(dims[0]); i++) {
        size_t bytes[3];
        require(align_ggml_v_extents(dims[i], bytes) == 0, "valid V byte extents");
        size_t strides[] = {4, bytes[0], bytes[1], bytes[2]};
        require(align_ggml_v_layout(dims[i], strides) == 0, "vprep-current-contiguous");
        for (int axis = 0; axis < 4; axis++) {
            strides[axis] += 4;
            require(align_ggml_v_layout(dims[i], strides) == ALIGN_GGML_SHAPE,
                    "noncanonical singleton strides refuse");
            strides[axis] -= 4;
        }
    }
}

static void byte_kernels(void) {
    enum { ROWS = 6, PAST_ROW = 12, CONCAT_ROW = 16, PADDED_ROW = 24 };
    unsigned char past[ROWS * PAST_ROW + 2], current[ROWS * 4 + 2];
    unsigned char concat[ROWS * CONCAT_ROW + 2], padded[ROWS * PADDED_ROW + 2];
    unsigned char saved_past[sizeof(past)], saved_current[sizeof(current)];
    memset(past, 0xa5, sizeof(past));
    memset(current, 0xa6, sizeof(current));
    memset(concat, 0xb5, sizeof(concat));
    memset(padded, 0xb6, sizeof(padded));
    pattern_bytes(past + 1, sizeof(past) - 2, 2);
    pattern_bytes(current + 1, sizeof(current) - 2, 5);
    memcpy(saved_past, past, sizeof(past));
    memcpy(saved_current, current, sizeof(current));
    align_ggml_v_concat_bytes(concat + 1, past + 1, current + 1, PAST_ROW, ROWS);
    align_ggml_v_pad_bytes(padded + 1, concat + 1, CONCAT_ROW, PADDED_ROW, ROWS);
    require(memcmp(past, saved_past, sizeof(past)) == 0
            && memcmp(current, saved_current, sizeof(current)) == 0, "byte kernels preserve sources");
    require(concat[0] == 0xb5 && concat[sizeof(concat) - 1] == 0xb5
            && padded[0] == 0xb6 && padded[sizeof(padded) - 1] == 0xb6, "vprep-sentinels");
    for (size_t row = 0; row < ROWS; row++) {
        require(memcmp(concat + 1 + row * CONCAT_ROW, past + 1 + row * PAST_ROW, PAST_ROW) == 0,
                "vprep-unaligned-byte-kernel: past");
        require(memcmp(concat + 1 + row * CONCAT_ROW + PAST_ROW, current + 1 + row * 4, 4) == 0,
                "vprep-unaligned-byte-kernel: current");
        require(memcmp(padded + 1 + row * PADDED_ROW, concat + 1 + row * CONCAT_ROW,
                       CONCAT_ROW) == 0, "vprep-unaligned-byte-kernel: pad");
        for (size_t at = CONCAT_ROW; at < PADDED_ROW; at++)
            require(padded[1 + row * PADDED_ROW + at] == 0, "unaligned positive-zero tail");
    }
}

#ifdef VPREP_REAL
static void callback_fault(const char *fault) {
    Fixture f;
    start(&f, 3, 2, 2);
    f.buffer = align_ggml_alloc_remaining(f.inputs, backend);
    require(f.buffer != NULL, "fault input allocation");
    require(align_ggml_op_v_concat_f32(f.ctx, f.slots, 2, 0, 1) == 0, "fault concat");
    require(align_ggml_op_v_pad_f32(f.ctx, f.slots, 3, 2, 2) == 0, "fault pad");
    (void) allocate_graph(&f, 3, -1);
    int pad = strncmp(fault, "pad-", 4) == 0;
    const char *kind = fault + (pad ? 4 : 7);
    Tensor *target = tensor(&f, pad ? 3 : 2);
    int ith = 0;
    int nth = 1;
    void *userdata = NULL;
    if (strcmp(kind, "task") == 0) ith = 1;
    if (strcmp(kind, "negative-task") == 0) ith = -1;
    if (strcmp(kind, "nth") == 0) nth = 0;
    if (strcmp(kind, "userdata") == 0) userdata = target;
    if (strcmp(kind, "data") == 0) target->data = NULL;
    if (strcmp(kind, "alias") == 0) target->data = target->src[0]->data;
    if (strcmp(kind, "buffer") == 0) target->buffer = NULL;
    if (strcmp(kind, "source") == 0) target->src[0] = NULL;
    if (strcmp(kind, "stride") == 0) target->nb[0] = 8;
    if (strcmp(kind, "type") == 0) target->type = GGML_TYPE_I32;
    if (strcmp(kind, "source-type") == 0) target->src[0]->type = GGML_TYPE_I32;
    if (strcmp(kind, "range") == 0) target->data = (void *) (UINTPTR_MAX - 3);
    if (strcmp(kind, "null") == 0) target = NULL;
    if (pad) align_ggml_v_pad_f32(target, ith, nth, userdata);
    else align_ggml_v_concat_f32(target, ith, nth, userdata);
    finish(&f);
    exit(3);
}
#endif

int main(int argc, char **argv) {
    struct rlimit no_core = {0, 0};
    (void) setrlimit(RLIMIT_CORE, &no_core);
    device = align_ggml_device_open();
    require(device != NULL, "CPU device");
    backend = align_ggml_backend_open(device);
    require(backend != NULL, "CPU backend");
#ifdef VPREP_REAL
    ggml_backend_reg_t cpu = ggml_backend_dev_backend_reg(ggml_backend_get_device(backend));
    ggml_backend_set_n_threads_t set_threads = (ggml_backend_set_n_threads_t)
        ggml_backend_reg_get_proc_address(cpu, "ggml_backend_set_n_threads");
    require(set_threads != NULL, "CPU thread configuration proc");
    set_threads(backend, 4);
    if (argc == 2) callback_fault(argv[1]);
#else
    (void) argc;
    (void) argv;
#endif
    byte_kernels();
    singleton_layouts();
    refusals();
    graph_case(1, 1, 1, 0, 0);
    graph_case(17, 3, 2, 5, 0);
    graph_case(17, 3, 2, 1, 0);
    graph_case(7, 4095, 2, 0, 0);
    graph_case(3, 1, 3, 4094, 0);
    graph_case(5, 3, 2, 7, 1);
    pad_limit_case();
#ifdef VPREP_REAL
    require(custom_calls >= 11, "vprep-task-count");
#endif
    align_ggml_backend_close(backend);
    puts("V preparation native cases: PASS");
    return 0;
}
