/* The owner includes the production implementation unchanged so that the real constructors and
 * static callbacks are exercised together. Native metadata and fault injection stay in this file.
 */
#include <stdio.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <sys/resource.h>

#ifdef KPREP_REAL
static _Noreturn void kprep_abort_at(int line) {
    fprintf(stderr, "production callback invariant at shim line %d\n", line);
    abort();
}
#define abort() kprep_abort_at(__LINE__)
#define ggml_custom_4d kprep_custom_4d
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
    align_ggml_k_concat_f32(dst, ith, nth, userdata);
}

static void observe_pad(Tensor *dst, int ith, int nth, void *userdata) {
    observe_worker(&pad_workers, ith, nth);
    align_ggml_k_pad_f32(dst, ith, nth, userdata);
}

struct ggml_tensor *kprep_custom_4d(
    struct ggml_context *ctx, enum ggml_type type, int64_t d, int64_t n, int64_t h,
    int64_t outer, struct ggml_tensor **args, int count, ggml_custom_op_t callback,
    int tasks, void *userdata) {
    struct ggml_tensor *result;
    if (tasks != 1 || userdata != NULL || (count != 1 && count != 2)) abort();
    if (callback != (count == 2 ? align_ggml_k_concat_f32 : align_ggml_k_pad_f32)) abort();
    custom_calls++;
    if (fail_constructor) return NULL;
    result = ggml_custom_4d(ctx, type, d, n, h, outer, args, count,
                            count == 2 ? observe_concat : observe_pad, tasks, userdata);
    if (result && corrupt_constructor) result->nb[0] = 8;
    return result;
}
#else
#include "ggml_shim_stub.c"
typedef align_stub_tensor Tensor;
#endif

static void require(int condition, const char *label) {
    if (!condition) {
        fprintf(stderr, "K preparation native failure: %s\n", label);
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
#ifdef KPREP_REAL
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
    require(align_ggml_slot_new_tensor_3d(f->inputs, f->slots, 0, 0, d, n, h) == 0,
            "past tensor construction");
    require(align_ggml_slot_new_tensor_3d(f->inputs, f->slots, 1, 0, d, 1, h) == 0,
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
#ifndef KPREP_REAL
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

static void graph_case(int64_t d, int64_t n, int64_t h, int64_t padding) {
    Fixture f;
    size_t past_head = (size_t) d * (size_t) n * 4;
    size_t current_head = (size_t) d * 4;
    size_t concat_head = past_head + current_head;
    size_t padded_head = concat_head + (size_t) d * (size_t) padding * 4;
    start(&f, d, n, h);
    f.buffer = align_ggml_alloc_remaining(f.inputs, backend);
    require(f.buffer != NULL, "input allocation");
    upload(&f, 0, 0);
    upload(&f, 1, 7);
    require(align_ggml_op_k_concat_f32(f.ctx, f.slots, 2, 0, 1) == 0, "kprep-concat-bits");
    require(align_ggml_op_k_pad_f32(f.ctx, f.slots, 3, 2, padding) == 0, "kprep-pad-bits");
    require(align_ggml_op_concat(f.ctx, f.slots, 4, 0, 1, 1) == 0, "original concat");
    require(align_ggml_op_pad(f.ctx, f.slots, 5, 4, 0, (int32_t) padding, 0, 0) == 0,
            "original padding");
    for (int slot = 2; slot <= 5; slot++)
        require(align_ggml_slot_mark_output(f.slots, slot) == 0, "mark concat/output");
    require(align_ggml_op_cont_3d(f.ctx, f.slots, 6, 3, d, n + 1 + padding, h) == 0,
            "downstream materialization");
    void *graph = allocate_graph(&f, 6, 5);
    require(align_ggml_graph_node_count(graph) == 5, "two custom nodes preserve graph counts");
    require(tensor(&f, 2)->src[0] == tensor(&f, 0) && tensor(&f, 2)->src[1] == tensor(&f, 1)
            && tensor(&f, 3)->src[0] == tensor(&f, 2), "kprep-callback-lifetime");
    require(data(tensor(&f, 2)) != data(tensor(&f, 0))
            && data(tensor(&f, 2)) != data(tensor(&f, 1))
            && data(tensor(&f, 3)) != data(tensor(&f, 2)), "distinct output storage");
#ifdef KPREP_REAL
    /* A graph may have more workers than this custom node requests. Idle workers must not inspect
     * storage; the graph's worker zero performs the one write, with the existing graph barrier. */
    align_ggml_k_concat_f32(NULL, 1, 4, NULL);
    align_ggml_k_pad_f32(NULL, 3, 4, NULL);
    atomic_store(&concat_workers, 0);
    atomic_store(&pad_workers, 0);
    atomic_store(&worker_mismatch, 0);
#endif
    overwrite_stack();
    require(align_ggml_graph_compute(backend, graph) == 0, "native compute");
#ifdef KPREP_REAL
    require(atomic_load(&concat_workers) == 15 && atomic_load(&pad_workers) == 15
            && !atomic_load(&worker_mismatch), "kprep-task-count: four graph workers once each");
#endif
    require((size_t) align_ggml_slot_nbytes(f.slots, 2) == concat_head * (size_t) h,
            "kprep-concat-head-layout");
    require((size_t) align_ggml_slot_nbytes(f.slots, 3) == padded_head * (size_t) h,
            "kprep-pad-head-layout");
    require(memcmp(data(tensor(&f, 2)), data(tensor(&f, 4)), concat_head * (size_t) h) == 0,
            "concat parity against original graph");
    require(memcmp(data(tensor(&f, 3)), data(tensor(&f, 5)), padded_head * (size_t) h) == 0,
            "pad parity against original graph");
    require(memcmp(data(tensor(&f, 3)), data(tensor(&f, 6)), padded_head * (size_t) h) == 0,
            "downstream consumes padded bytes");
    if (padding == 0)
        require(memcmp(data(tensor(&f, 2)), data(tensor(&f, 3)), concat_head * (size_t) h) == 0,
                "kprep-pad-zero-width-delta");
    for (size_t head = 0; head < (size_t) h; head++) {
        unsigned char *concat = data(tensor(&f, 2)) + head * concat_head;
        unsigned char *padded = data(tensor(&f, 3)) + head * padded_head;
        require(memcmp(concat, data(tensor(&f, 0)) + head * past_head, past_head) == 0,
                "kprep-special-bits: past");
        require(memcmp(concat + past_head, data(tensor(&f, 1)) + head * current_head,
                       current_head) == 0, "kprep-special-bits: current");
        require(memcmp(padded, concat, concat_head) == 0, "kprep-marked-concat");
        for (size_t at = concat_head; at < padded_head; at++)
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
    require(align_ggml_op_k_pad_f32(f.ctx, f.slots, 2, 0, 4095) == 0, "maximum legal padding");
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
#ifdef KPREP_REAL
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
#ifdef KPREP_REAL
    last_refusal_calls = custom_calls;
#endif
#define CONCAT(label, code) refused(&f, align_ggml_op_k_concat_f32(f.ctx, f.slots, 7, 0, 1), code, before, label)
#define PAD(label, value, code) refused(&f, align_ggml_op_k_pad_f32(f.ctx, f.slots, 7, 0, value), code, before, label)
    refused(&f, align_ggml_op_k_concat_f32(NULL, NULL, -1, -1, -1), ALIGN_GGML_INIT, before,
            "kprep-concat-null-context");
    refused(&f, align_ggml_op_k_pad_f32(NULL, NULL, -1, -1, -1), ALIGN_GGML_INIT, before,
            "kprep-pad-null-context");
    uint64_t saved_magic = f.slots[0];
    f.slots[0] = 0;
    CONCAT("kprep-concat-slot-precedence: magic", ALIGN_GGML_SLOT);
    PAD("kprep-pad-slot-precedence: magic", -1, ALIGN_GGML_SLOT);
    f.slots[0] = saved_magic;
    before = tensor(&f, 7);
    uint64_t saved_capacity = f.slots[1];
    f.slots[1] = 0;
    CONCAT("kprep-concat-slot-precedence: capacity", ALIGN_GGML_SLOT);
    PAD("kprep-pad-slot-precedence: capacity", -1, ALIGN_GGML_SLOT);
    f.slots[1] = 65537;
    CONCAT("kprep-concat-slot-precedence: oversized capacity", ALIGN_GGML_SLOT);
    PAD("kprep-pad-slot-precedence: oversized capacity", -1, ALIGN_GGML_SLOT);
    f.slots[1] = saved_capacity;
    refused(&f, align_ggml_op_k_concat_f32(f.ctx, (unsigned char *) f.slots + 1, 7, 0, 1),
            ALIGN_GGML_SLOT, before, "kprep-concat-slot-precedence: unaligned store");
    refused(&f, align_ggml_op_k_pad_f32(f.ctx, NULL, 7, 0, -1),
            ALIGN_GGML_SLOT, before, "kprep-pad-slot-precedence: null store");
    for (int input = -1; input <= 16; input += 17) {
        refused(&f, align_ggml_op_k_concat_f32(f.ctx, f.slots, 7, input, 1), ALIGN_GGML_SLOT,
                before, "kprep-concat-slot-precedence: input");
        refused(&f, align_ggml_op_k_concat_f32(f.ctx, f.slots, 7, 0, input), ALIGN_GGML_SLOT,
                before, "kprep-concat-slot-precedence: current input");
        refused(&f, align_ggml_op_k_pad_f32(f.ctx, f.slots, 7, input, -1), ALIGN_GGML_SLOT,
                before, "kprep-pad-slot-precedence: input");
    }
    refused(&f, align_ggml_op_k_concat_f32(f.ctx, f.slots, 7, 0, 15), ALIGN_GGML_SLOT, before,
            "kprep-concat-slot-precedence: empty");
    refused(&f, align_ggml_op_k_pad_f32(f.ctx, f.slots, 7, 15, -1), ALIGN_GGML_SLOT, before,
            "kprep-pad-slot-precedence: empty");
    for (int out = -1; out <= 16; out += 17) {
        refused(&f, align_ggml_op_k_concat_f32(f.ctx, f.slots, out, 0, 1), ALIGN_GGML_SLOT,
                before, "kprep-concat-slot-precedence: out");
        refused(&f, align_ggml_op_k_pad_f32(f.ctx, f.slots, out, 0, -1), ALIGN_GGML_SLOT,
                before, "kprep-pad-slot-precedence: out");
    }
    past->type = 26;
    refused(&f, align_ggml_op_k_concat_f32(f.ctx, f.slots, 0, 0, 1), ALIGN_GGML_SLOT, before,
            "kprep-concat-out-alias");
    refused(&f, align_ggml_op_k_concat_f32(f.ctx, f.slots, 1, 0, 1), ALIGN_GGML_SLOT, before,
            "kprep-concat-out-alias: current");
    refused(&f, align_ggml_op_k_pad_f32(f.ctx, f.slots, 0, 0, -1), ALIGN_GGML_SLOT, before,
            "kprep-pad-out-alias");
    CONCAT("kprep-concat-type", ALIGN_GGML_TYPE);
    PAD("kprep-pad-type precedes padding", -1, ALIGN_GGML_TYPE);
    *past = saved_past;
    current->type = 26;
    CONCAT("kprep-concat-current-type", ALIGN_GGML_TYPE);
    *current = saved_current;
    for (int dimension = 0; dimension < 4; dimension++) {
        past->ne[dimension] = dimension == 3 ? 2 : 0;
        CONCAT("kprep-concat-shape", ALIGN_GGML_SHAPE);
        PAD("kprep-pad-shape", 0, ALIGN_GGML_SHAPE);
        *past = saved_past;
    }
    current->ne[1] = 2;
    CONCAT("kprep-concat-current-columns", ALIGN_GGML_SHAPE);
    *current = saved_current;
    current->ne[0] = 4;
    CONCAT("kprep-concat-head-dimension", ALIGN_GGML_SHAPE);
    *current = saved_current;
    current->ne[2] = 3;
    CONCAT("kprep-concat-head-count", ALIGN_GGML_SHAPE);
    *current = saved_current;
    PAD("kprep-pad-negative", -1, ALIGN_GGML_SHAPE);
    PAD("kprep-pad-width", 4095, ALIGN_GGML_SHAPE);
    PAD("kprep-pad-padding-cap", 4097, ALIGN_GGML_SHAPE);
    PAD("kprep-pad-overflow", INT64_MAX, ALIGN_GGML_SHAPE);
    const int64_t large[][3] = {
        {INT64_MAX, 2, 2}, {3, INT64_MAX, 2}, {3, 2, INT64_MAX},
        {INT64_MAX / 4 + 1, 1, 1}, {4097, 4095, 1}, {4096, 4096, 1},
    };
    for (size_t i = 0; i < sizeof(large) / sizeof(large[0]); i++) {
        for (int dim = 0; dim < 3; dim++) past->ne[dim] = large[i][dim];
        current->ne[0] = past->ne[0];
        current->ne[2] = past->ne[2];
        CONCAT("kprep-concat-overflow/cap", ALIGN_GGML_SHAPE);
        PAD("kprep-pad-overflow/cap", 1, ALIGN_GGML_SHAPE);
        *past = saved_past;
        *current = saved_current;
    }
#ifdef KPREP_REAL
    for (int stride = 0; stride < 4; stride++) {
        past->nb[stride] += 4;
        CONCAT("kprep-concat-stride", ALIGN_GGML_SHAPE);
        PAD("kprep-pad-stride", 0, ALIGN_GGML_SHAPE);
        *past = saved_past;
        current->nb[stride] += 4;
        CONCAT("kprep-concat-current-stride", ALIGN_GGML_SHAPE);
        *current = saved_current;
    }
    expect_construction = 1;
    fail_constructor = 1;
    CONCAT("kprep-init-failure: concat", ALIGN_GGML_INIT);
    PAD("kprep-init-failure: pad", 0, ALIGN_GGML_INIT);
    fail_constructor = 0;
    corrupt_constructor = 1;
    CONCAT("result stride validation: concat", ALIGN_GGML_SHAPE);
    PAD("result stride validation: pad", 0, ALIGN_GGML_SHAPE);
    corrupt_constructor = 0;
    expect_construction = 0;
#else
    past->lp[0] = 28;
    CONCAT("kprep-concat-stride", ALIGN_GGML_SHAPE);
    PAD("kprep-pad-stride", 0, ALIGN_GGML_SHAPE);
    *past = saved_past;
    int saved_count = align_stub_tensor_count;
    align_stub_tensor_count = ALIGN_STUB_MAX_TENSORS;
    CONCAT("kprep-init-failure: concat", ALIGN_GGML_INIT);
    PAD("kprep-init-failure: pad", 0, ALIGN_GGML_INIT);
    align_stub_tensor_count = saved_count;
#endif
    finish(&f);
    /* Construction must admit the maximum exact element count without reading unallocated data. */
    start(&f, 4096, 4095, 1);
    require(align_ggml_op_k_concat_f32(f.ctx, f.slots, 2, 0, 1) == 0, "exact concat element cap");
    require(align_ggml_op_k_pad_f32(f.ctx, f.slots, 3, 2, 0) == 0, "exact pad element cap");
    finish(&f);
#undef CONCAT
#undef PAD
}

static void byte_kernels(void) {
    unsigned char past[74], current[38], concat[110], padded[182];
    unsigned char saved_past[74], saved_current[38];
    memset(past, 0xa5, sizeof(past));
    memset(current, 0xa6, sizeof(current));
    memset(concat, 0xb5, sizeof(concat));
    memset(padded, 0xb6, sizeof(padded));
    pattern_bytes(past + 1, 72, 2);
    pattern_bytes(current + 1, 36, 5);
    memcpy(saved_past, past, sizeof(past));
    memcpy(saved_current, current, sizeof(current));
    align_ggml_k_concat_bytes(concat + 1, past + 1, current + 1, 12, 24, 3);
    align_ggml_k_pad_bytes(padded + 1, concat + 1, 36, 60, 3);
    require(memcmp(past, saved_past, sizeof(past)) == 0
            && memcmp(current, saved_current, sizeof(current)) == 0, "byte kernels preserve sources");
    require(concat[0] == 0xb5 && concat[109] == 0xb5
            && padded[0] == 0xb6 && padded[181] == 0xb6, "kprep-sentinels");
    for (size_t h = 0; h < 3; h++) {
        require(memcmp(concat + 1 + h * 36, past + 1 + h * 24, 24) == 0,
                "kprep-unaligned-byte-kernel: past");
        require(memcmp(concat + 25 + h * 36, current + 1 + h * 12, 12) == 0,
                "kprep-unaligned-byte-kernel: current");
        require(memcmp(padded + 1 + h * 60, concat + 1 + h * 36, 36) == 0,
                "kprep-unaligned-byte-kernel: pad");
        for (size_t at = 36; at < 60; at++)
            require(padded[1 + h * 60 + at] == 0, "unaligned positive-zero tail");
    }
}

#ifdef KPREP_REAL
static void callback_fault(const char *fault) {
    Fixture f;
    start(&f, 3, 2, 2);
    f.buffer = align_ggml_alloc_remaining(f.inputs, backend);
    require(f.buffer != NULL, "fault input allocation");
    require(align_ggml_op_k_concat_f32(f.ctx, f.slots, 2, 0, 1) == 0, "fault concat");
    require(align_ggml_op_k_pad_f32(f.ctx, f.slots, 3, 2, 2) == 0, "fault pad");
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
    if (strcmp(kind, "null") == 0) target = NULL;
    if (pad) align_ggml_k_pad_f32(target, ith, nth, userdata);
    else align_ggml_k_concat_f32(target, ith, nth, userdata);
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
#ifdef KPREP_REAL
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
    refusals();
    graph_case(1, 1, 1, 0);
    graph_case(17, 3, 3, 5);
    graph_case(17, 3, 3, 1);
    graph_case(7, 4095, 2, 0);
    graph_case(3, 1, 3, 4094);
    pad_limit_case();
#ifdef KPREP_REAL
    require(custom_calls >= 11, "kprep-task-count");
#endif
    align_ggml_backend_close(backend);
    puts("K preparation native cases: PASS");
    return 0;
}
