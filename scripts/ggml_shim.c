/* R4.5-EXTERNAL-BUFFER-SPIKE — the real ggml shim.
 *
 * `docs/specs/r4-5-external-buffer.md` section 3.4 owns this contract; section 3.1 owns the reason
 * it exists. At the pinned Align compiler a `layout(C)` struct cannot cross by value on
 * `arm64-apple-darwin`, cannot contain a `raw` field, and `bool` is not an FFI type — so
 * `struct ggml_init_params { size_t; void *; bool; }`, the sole entry point to the whole library,
 * is unreachable from Align by every route. This file is not a convenience layer; it is the only
 * way ggml can be called at all.
 *
 * Four rules govern every line below.
 *
 *  1. **No ggml type appears in any signature.** Handles cross as `void *`, results as `int32_t`
 *     or `int64_t`. ABI drift therefore cannot silently change an Align declaration.
 *  2. **Allocation follows the active owner contract.** The legacy external-buffer functions
 *     reserve no model memory. G1's invocation root allocates only the explicitly admitted
 *     metadata, staging, weights, KV and workspace ranges and releases every prefix in reverse.
 *  3. **Fail closed before ggml can abort.** `ggml_backend_cpu_buffer_from_ptr` calls `abort()`
 *     through `GGML_ASSERT` on a pointer that is not `TENSOR_ALIGNMENT`-aligned (section 2.4), so
 *     every pointer and every size is validated here, in C, before the call that would assert.
 *  4. **Legacy tensor data, extent and type use accessors.** Item 66 writes `nb[2]`/`nb[3]`
 *     after checked construction because ggml exposes no standalone fixed-slot expert stack.
 *     G1's pinned native graph observation also reads public `op`, `src` and `ne` metadata to
 *     distinguish materializing nodes and identify down-projection work; no device data is read.
 *
 * Built by the `Makefile`'s `build/lib/libalign_ggml_shim.$(SHIM_SUFFIX)` rule when
 * `ALIGN_LLM_GGML_INCLUDE` is set; `scripts/ggml_shim_stub.c` is built instead when it is not.
 */

#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"

/* --- BEGIN R4.5 SHARED SHIM CONTRACT --- */
#if defined(__aarch64__)
#include <arm_neon.h>
#endif

/* Everything between these two markers is byte-identical in `scripts/ggml_shim.c` and
 * `scripts/ggml_shim_stub.c`, and `scripts/run-ggml-spike-smoke` asserts that byte-identity on
 * every run. The two files are one contract compiled twice: the real one against the host's ggml
 * headers, the stub one against nothing at all. A drift between them would let the hosted owner
 * test pass against a contract the qualification does not run.
 *
 * Status values. `0` is success; every negative value maps to exactly one `R4_5_*` code in
 * `src/ggml_ffi.align`'s single `match`. `docs/specs/r4-5-external-buffer.md` section 3.8 owns the
 * mapping and the validation order that reaches each one.
 */
/* **Floating-point contraction is off, in the source and in the build flags** (section 6,
 * correction C15). `a * b + c` may be contracted into one fused multiply-add, and whether it is
 * depends on the compiler and the target: Apple clang on `arm64` contracts by default, GCC 13 on
 * `x86-64` does not. The stub engine's kernels are the reference the checked-in golden documents
 * are generated from, so a contraction difference is a twelve-of-forty-eight golden mismatch on a
 * host that is otherwise correct. `scripts/build-ggml-shim` passes `-ffp-contract=off` and defines
 * `ALIGN_GGML_FP_CONTRACT_OFF`, and the pragma below makes the source say the same thing so a
 * golden regenerated with a hand-run compiler is still the golden a flagged build reproduces.
 * `align_ggml_fp_contract_off` reports a **behavioural** probe rather than the define, because a
 * define is what the build asked for and not what the compiler did. Contraction is not the only
 * way a host can disagree — the stub engine's kernels call libm — so the flag is diagnosis and the
 * golden corpus is the detector. Clang implements the standard pragma below; GCC 14.2 still
 * diagnoses it as unknown, so GCC is covered by the build flag and the behavioural probe.
 */
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#define ALIGN_GGML_OK           0
#define ALIGN_GGML_UNAVAILABLE (-1)
#define ALIGN_GGML_ABI         (-2)
#define ALIGN_GGML_TYPE        (-3)
#define ALIGN_GGML_SHAPE       (-4)
#define ALIGN_GGML_ALIGNMENT   (-5)
#define ALIGN_GGML_INIT        (-6)
#define ALIGN_GGML_BOUNDS      (-7)

/* The `TENSOR_ALIGNMENT` ggml asserts on inside `ggml_backend_cpu_buffer_from_ptr`. It is not a
 * public constant in any shipped header (section 6, correction C1), so the real shim reports the
 * linked library's own `ggml_backend_buft_get_alignment` for the CPU device and this value is only
 * the stub's answer and the expectation the qualification asserts the real one against.
 */
#define ALIGN_GGML_TENSOR_ALIGNMENT 32

/* The `mul_mat` left-operand table: `{ ggml_type, blck_size, type_size }`, checked in.
 *
 * Membership is the `R4_5_TYPE_UNSUPPORTED` predicate. `blck_size` is what `R4_5_SHAPE`'s
 * `ne0 % blck_size == 0` rule is evaluated against. `type_size` is carried so the qualification can
 * assert every row against the linked ggml rather than only the three Q4_K constants — a wider ABI
 * drift guard than section 3.4 asked for (section 6, correction C2).
 *
 * Absent on purpose: the deprecated and removed ids (4, 5, 31-33, 36-38), the plain integer and
 * f64 storage types (24-28), Q8_1 (9) and Q8_K (15), which exist as `mul_mat` *right*-operand
 * intermediates and never as a stored weight, and NVFP4/Q1_0/Q2_0 (40-42), which this pin's
 * GGUF corpus cannot produce.
 */
#define ALIGN_GGML_TABLE_ROWS 25
static const int align_ggml_type_table[ALIGN_GGML_TABLE_ROWS][3] = {
    {  0,   1,   4 }, /* F32     */
    {  1,   1,   2 }, /* F16     */
    {  2,  32,  18 }, /* Q4_0    */
    {  3,  32,  20 }, /* Q4_1    */
    {  6,  32,  22 }, /* Q5_0    */
    {  7,  32,  24 }, /* Q5_1    */
    {  8,  32,  34 }, /* Q8_0    */
    { 10, 256,  84 }, /* Q2_K    */
    { 11, 256, 110 }, /* Q3_K    */
    { 12, 256, 144 }, /* Q4_K    */
    { 13, 256, 176 }, /* Q5_K    */
    { 14, 256, 210 }, /* Q6_K    */
    { 16, 256,  66 }, /* IQ2_XXS */
    { 17, 256,  74 }, /* IQ2_XS  */
    { 18, 256,  98 }, /* IQ3_XXS */
    { 19, 256,  50 }, /* IQ1_S   */
    { 20,  32,  18 }, /* IQ4_NL  */
    { 21, 256, 110 }, /* IQ3_S   */
    { 22, 256,  82 }, /* IQ2_S   */
    { 23, 256, 136 }, /* IQ4_XS  */
    { 29, 256,  56 }, /* IQ1_M   */
    { 30,   1,   2 }, /* BF16    */
    { 34, 256,  54 }, /* TQ1_0   */
    { 35, 256,  66 }, /* TQ2_0   */
    { 39,  32,  17 }, /* MXFP4   */
};

/* The row index of `type`, or `-1`. Linear over 25 rows, called at most twice per process. */
static int align_ggml_table_row(int type) {
    int i = 0;
    for (i = 0; i < ALIGN_GGML_TABLE_ROWS; i++) {
        if (align_ggml_type_table[i][0] == type) {
            return i;
        }
    }
    return -1;
}

/* R5A-DENSE-LAYER-FORWARD additions (`docs/specs/r5a-dense-layer-forward.md` sections 3.5 and
 * 3.8). Two more status values and the whole of the node-slot store live inside the shared region
 * because both files must answer a slot question identically: the store's bytes are Align's, its
 * validation is C's, and a drift between the two shims would let the hosted owner test accept a
 * bounds rule the qualification never runs.
 */
#define ALIGN_GGML_ALLOC       (-8)
#define ALIGN_GGML_SLOT        (-9)

/* The node-slot store. Section 2.6 established that at this pin `raw` is refused as a struct field
 * and as an array element, so a thirty-two-node graph's `ggml_tensor *` handles cannot live in
 * Align. They live in an Align-owned byte window that this file writes into and addresses by
 * `int64_t` index:
 *
 *   [0 .. 8)    the magic "ALGNSLOT"
 *   [8 .. 16)   the capacity, as a little-endian u64
 *   [16 + 8*i)  slot i, a pointer, or NULL for empty
 *
 * Every entry point validates the magic, the 8-alignment of the base, and the index against the
 * window's own declared capacity before it reads or writes, and refuses a read of an empty slot.
 * `ALIGN_GGML_SLOT` is the one code that would otherwise not exist: without this check an
 * out-of-range index is an out-of-bounds pointer write into an Align allocation.
 */
#define ALIGN_GGML_SLOT_HEADER_BYTES 16
#define ALIGN_GGML_SLOT_BYTES 8

static const unsigned char align_ggml_slot_magic[8] = {
    'A', 'L', 'G', 'N', 'S', 'L', 'O', 'T'
};

/* The declared capacity of a well-formed store, or `-1`. A store whose base is not 8-aligned is
 * refused rather than fixed up: the caller reserved the window and the caller is told.
 */
static int64_t align_ggml_slot_capacity(const void *slots) {
    unsigned char header[8];
    uint64_t capacity = 0;
    int i = 0;
    if (slots == NULL) {
        return -1;
    }
    if ((((uintptr_t) slots) % (uintptr_t) 8) != 0) {
        return -1;
    }
    memcpy(header, slots, sizeof(header));
    for (i = 0; i < 8; i++) {
        if (header[i] != align_ggml_slot_magic[i]) {
            return -1;
        }
    }
    memcpy(&capacity, (const unsigned char *) slots + 8, sizeof(capacity));
    if (capacity == 0 || capacity > (uint64_t) 65536) {
        return -1;
    }
    return (int64_t) capacity;
}

static int32_t align_ggml_slot_store(void *slots, int64_t index, void *value) {
    int64_t capacity = align_ggml_slot_capacity(slots);
    if (capacity < 0) {
        return ALIGN_GGML_SLOT;
    }
    if (index < 0 || index >= capacity) {
        return ALIGN_GGML_SLOT;
    }
    memcpy((unsigned char *) slots + ALIGN_GGML_SLOT_HEADER_BYTES
               + (size_t) index * ALIGN_GGML_SLOT_BYTES,
           &value, sizeof(value));
    return ALIGN_GGML_OK;
}

/* The slot's pointer, or `NULL` for an empty slot, an out-of-range index, or a malformed store.
 * Every op wrapper tests the result against `NULL` and returns `ALIGN_GGML_SLOT`, so an empty read
 * and an out-of-range read are the same refusal and neither reaches a ggml call.
 */
static void *align_ggml_slot_load(const void *slots, int64_t index) {
    int64_t capacity = align_ggml_slot_capacity(slots);
    void *value = NULL;
    if (capacity < 0 || index < 0 || index >= capacity) {
        return NULL;
    }
    memcpy(&value, (const unsigned char *) slots + ALIGN_GGML_SLOT_HEADER_BYTES
                       + (size_t) index * ALIGN_GGML_SLOT_BYTES,
           sizeof(value));
    return value;
}

/* Writes the header and zeroes every slot. `bytes` is the window Align reserved; the capacity is
 * derived from it rather than declared separately, so the two can never disagree.
 */
int32_t align_ggml_slots_init(void *slots, int64_t bytes) {
    int64_t capacity = 0;
    uint64_t stored = 0;
    if (slots == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if ((((uintptr_t) slots) % (uintptr_t) 8) != 0) {
        return ALIGN_GGML_ALIGNMENT;
    }
    if (bytes < ALIGN_GGML_SLOT_HEADER_BYTES + ALIGN_GGML_SLOT_BYTES) {
        return ALIGN_GGML_SLOT;
    }
    if ((bytes - ALIGN_GGML_SLOT_HEADER_BYTES) % ALIGN_GGML_SLOT_BYTES != 0) {
        return ALIGN_GGML_SLOT;
    }
    capacity = (bytes - ALIGN_GGML_SLOT_HEADER_BYTES) / ALIGN_GGML_SLOT_BYTES;
    if (capacity <= 0 || capacity > (int64_t) 65536) {
        return ALIGN_GGML_SLOT;
    }
#ifdef ALIGN_GGML_FORCE_SLOT_RANGE
    /* Section 4.6: `R5_SLOT` for an index the store cannot hold. A capacity smaller than the graph
     * needs makes the node-table walk reach the bounds check for real rather than by argument. The
     * macro is never defined in an ordinary build.
     */
    capacity = 20;
#endif
    memset(slots, 0, (size_t) bytes);
    memcpy(slots, align_ggml_slot_magic, sizeof(align_ggml_slot_magic));
    stored = (uint64_t) capacity;
    memcpy((unsigned char *) slots + 8, &stored, sizeof(stored));
    return ALIGN_GGML_OK;
}

/* The store's own declared capacity, published so the document can report it and so a caller can
 * refuse a graph the window cannot hold before it builds one.
 */
int64_t align_ggml_slots_capacity(const void *slots) {
    return align_ggml_slot_capacity(slots);
}

/* `1` when the header is a well-formed store this file wrote. The document's `abi.slot_magic_ok`. */
int32_t align_ggml_slots_ok(const void *slots) {
    return align_ggml_slot_capacity(slots) > 0 ? 1 : 0;
}

/* Copies one handle between two stores. The reference arm builds a second graph over the *same*
 * three input tensors, and a handle cannot cross through Align, so it crosses here.
 */
int32_t align_ggml_slot_copy(void *destination, int64_t to, const void *source, int64_t from) {
    void *value = align_ggml_slot_load(source, from);
    if (value == NULL) {
        return ALIGN_GGML_SLOT;
    }
    return align_ggml_slot_store(destination, to, value);
}

/* Reinterprets an `int32_t` bit pattern as the `float` ggml receives. Section 3.5: Align owns every
 * scalar and crosses it as a bit pattern, because `r1-qwen-model-ir.md` publishes `rms_eps_bits`
 * and `freq_base_bits` as authoritative IEEE-754 hex and a rendered float is not authoritative.
 * `memcpy` and never a cast: a cast would convert the *value*, which is the opposite of the intent.
 */
static float align_ggml_bits_to_f32(int32_t bits) {
    float value = 0.0f;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

/* A **behavioural** probe of this translation unit: `1` when `a * b + c` is rounded in two steps,
 * `0` when the compiler contracts it into one fused multiply-add. The three operands are
 * `volatile`, so each is loaded from memory rather than constant-folded, and `product` is
 * `volatile` too, so `a * b` is rounded to `float` and stored before the addition. The triple is
 * chosen so the two answers differ by exactly one ulp: `(1 + 2^-23) * (1 + 2^-22) - 1` is
 * `3 * 2^-23` when the product is rounded first and `3 * 2^-23 + 2^-45` when it is not. This is
 * well-defined C — no undefined behaviour, no libm, no reliance on a compiler flag being honest.
 * Verified to answer `0` under Apple clang 17 on `arm64` and clang 22 on `aarch64-linux` with no
 * flag, and `1` under `-ffp-contract=off` on both and under GCC 13/14 on `x86-64` either way.
 */
static int32_t align_ggml_fp_contract_probe(void) {
    volatile float a = 0x1.000002p0f; /* 1 + 2^-23 */
    volatile float b = 0x1.000004p0f; /* 1 + 2^-22 */
    volatile float c = -1.0f;
    float fused = a * b + c;
    volatile float product = a * b;
    float separate = product + c;
    return fused == separate ? 1 : 0;
}

/* `1` when this translation unit was both *built* with floating-point contraction disabled —
 * `scripts/build-ggml-shim`'s `-ffp-contract=off` plus `-DALIGN_GGML_FP_CONTRACT_OFF=1` — and is
 * *observed* not to contract. The macro on its own is build provenance and nothing more: it says
 * what the build intended, not what the compiler did, and `-ffp-contract=fast` overrides the
 * pragma above without touching the define. Reporting the probe is what makes `abi.fp_contract_off`
 * a statement about behaviour (section 6, correction C15). The document publishes it and both
 * runners assert it, so dropping the flag is a failing check rather than a golden corpus that only
 * reproduces on one compiler. The probe measures this function and not the kernels, and contraction
 * is not the only per-compiler difference the kernels can have, so it is diagnosis: the goldens
 * themselves remain the detector.
 */
int32_t align_ggml_fp_contract_off(void) {
#ifdef ALIGN_GGML_FP_CONTRACT_OFF
    return align_ggml_fp_contract_probe();
#else
    return 0;
#endif
}

/* The highest occupied slot index plus one, `0` for an empty store, or `ALIGN_GGML_SLOT` for a
 * window this file did not write. The document's `graph.slot_high_water` (section 6, correction
 * C16): it was a constant derived from the node table, which could not disagree with the node
 * table and therefore measured nothing. Scanned rather than tracked, because the store is the only
 * thing that knows what was actually written into it.
 */
int64_t align_ggml_slots_high_water(const void *slots) {
    int64_t capacity = align_ggml_slot_capacity(slots);
    int64_t index = 0;
    int64_t high = 0;
    if (capacity < 0) {
        return ALIGN_GGML_SLOT;
    }
    for (index = 0; index < capacity; index++) {
        if (align_ggml_slot_load(slots, index) != NULL) {
            high = index + 1;
        }
    }
    return high;
}

/* `1` when an `int32_t` bit pattern names a float `ggml_rms_norm` will accept (section 6,
 * correction C17). ggml asserts `eps >= 0.0f` internally and `GGML_ASSERT` is `abort()`, so a
 * geometry document carrying `7fc00000` (NaN), `ff800000` (-inf), or `bf800000` (-1.0) would take
 * the process down with no document, no error code, and no teardown — the one class of input the
 * validation order cannot otherwise reach, because Align never interprets the pattern it forwards.
 *
 * `src/layer_qwen2.align` refuses the same patterns at step 7 with `R5_GEOMETRY`, so this is the
 * fail-closed backstop for a caller that reaches the wrapper by another route. It lives in the
 * shared region because both shims must answer it identically.
 */
static int32_t align_ggml_eps_ok(int32_t bits) {
    float value = align_ggml_bits_to_f32(bits);
    if (value != value) {
        return 0;  /* NaN */
    }
    if (value - value != 0.0f) {
        return 0;  /* an infinity */
    }
    if (value < 0.0f) {
        return 0;
    }
    return 1;
}

/* R5B-MODEL-PREFILL-FORWARD (`docs/specs/r5b-model-prefill-forward.md` section 3.6). The `pad`
 * wrapper's two bounds, shared so both files refuse the same input. `MAX_PAD` is
 * `MAX_ATTENTION_WIDTH`, the ceiling `src/layer_qwen2.align` validates `KV_WIDTH` against;
 * `MAX_PAD_ELEMENTS` bounds the result so a malformed width cannot ask for a terabyte of
 * activation.
 */
#define ALIGN_GGML_MAX_PAD 4096
#define ALIGN_GGML_MAX_PAD_ELEMENTS ((int64_t) 16777216)

/* R5D-MOE-LAYER-FORWARD (`docs/specs/r5d-moe-layer-forward.md` section 3.5). `ggml_argsort`'s two
 * orders, shared so both files refuse the same third value. `ggml_top_k` is deliberately **not**
 * wrapped: its own header says the indices it returns are in no particular order, section 2.2
 * fact 3 measured `ffn_moe_topk-0` to be an `ARGSORT` plus a `VIEW` in descending probability, and
 * section 2.3 measured that slot order to be load-bearing to the last bit.
 */
#define ALIGN_GGML_SORT_ASC  0
#define ALIGN_GGML_SORT_DESC 1

/* The widened `soft_max_ext` input domain. `mask == -1` is "no mask", which is
 * `ggml_soft_max_ext(ctx, a, NULL, scale, bias)` and what the router's plain 64-way softmax needs;
 * the existing `sm == NULL -> ALIGN_GGML_SLOT` check makes it unreachable. Widening an existing
 * symbol's input domain rather than adding a second symbol is `moe-prereq-discharge.md`'s style and
 * R5B correction C1's rule: the cheapest new shim symbol is the one you do not add.
 */
#define ALIGN_GGML_NO_MASK ((int64_t) -1)

/* `align_ggml_op_view_2d`'s dimension-selector bound. Align supplies two axis **indices** and an
 * offset index, never a stride and never a byte count, so a caller cannot forge an offset; the two
 * selectors are validated against this bound in C before either stride is read (section 3.5).
 */
#define ALIGN_GGML_MAX_DIM_SELECTOR 3


/* R5B-MODEL-PREFILL-FORWARD section 6, correction C5. A bounded `memcpy` between two Align-owned
 * byte ranges, and the reason the window can be **reused** at all.
 *
 * Align's `buffer` is append-only: `put_*` and `append` write at the logical length, and `pread`
 * overwrites from index 0 and always requests the buffer's whole capacity. A 447 MB window that is
 * allocated once and refilled thirty times is therefore not expressible from Align — refilling by
 * `pread` would read the whole window from the pack on every layer, and refilling by reallocation
 * would fault in 447 MB of fresh pages thirty times. `docs/align-requests.md` owns the language
 * half of that; this is the application-side answer and it consumes no hypothetical surface.
 *
 * It allocates nothing, opens nothing, and reads no byte the caller did not hand over, so rule 2 of
 * this file is unchanged. Both ranges are the caller's, both lengths are the caller's, and every
 * bound is checked before the copy.
 */
int32_t align_ggml_window_copy(void *window, int64_t window_bytes, int64_t offset,
                               const void *source, int64_t source_bytes, int64_t n) {
    if (window == NULL || source == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (offset < 0 || n < 0 || window_bytes < 0 || source_bytes < 0) {
        return ALIGN_GGML_BOUNDS;
    }
    if (offset > window_bytes || n > window_bytes - offset) {
        return ALIGN_GGML_BOUNDS;
    }
    if (n > source_bytes) {
        return ALIGN_GGML_BOUNDS;
    }
    if (n > 0) {
        memcpy((unsigned char *) window + offset, source, (size_t) n);
    }
    return ALIGN_GGML_OK;
}


/* R8-OLMOE-KV-PLANE-STAGING-TRANSFER
 * (`docs/specs/r8-olmoe-kv-plane-staging-transfer.md` section 2). Transpose the two contiguous
 * prefixes of one layer's canonical K/V plane into the distinct layouts consumed by the decode
 * graph. Every size, source range, and overlap is refused before the first destination byte is
 * written. The caller owns both ranges; this function allocates and retains nothing.
 */
int32_t align_ggml_stage_kv(const void *plane, int64_t plane_bytes,
                            int64_t k_base, int64_t v_base,
                            void *stage, int64_t stage_bytes,
                            int64_t head_dim, int64_t n_head_kv, int64_t n_past) {
    int64_t elements = 0;
    int64_t past_bytes = 0;
    int64_t expected_stage_bytes = 0;
    uintptr_t plane_address = 0;
    uintptr_t stage_address = 0;
    uintptr_t k_address = 0;
    uintptr_t v_address = 0;
    uintptr_t stage_end = 0;
    uintptr_t k_end = 0;
    uintptr_t v_end = 0;
    const unsigned char *source = NULL;
    unsigned char *destination = NULL;
    int64_t head = 0;
    int64_t column = 0;
    int64_t lane = 0;

    if (plane == NULL || stage == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (plane_bytes < 0 || k_base < 0 || v_base < 0 || stage_bytes < 0 ||
        head_dim <= 0 || n_head_kv <= 0 || n_past <= 0) {
        return ALIGN_GGML_BOUNDS;
    }
    if (head_dim > INT64_MAX / n_head_kv) {
        return ALIGN_GGML_BOUNDS;
    }
    elements = head_dim * n_head_kv;
    if (elements > INT64_MAX / n_past) {
        return ALIGN_GGML_BOUNDS;
    }
    elements *= n_past;
    if (elements > INT64_MAX / 4) {
        return ALIGN_GGML_BOUNDS;
    }
    past_bytes = elements * 4;
    if (past_bytes > INT64_MAX / 2) {
        return ALIGN_GGML_BOUNDS;
    }
    expected_stage_bytes = past_bytes * 2;
    if (stage_bytes != expected_stage_bytes) {
        return ALIGN_GGML_BOUNDS;
    }
    if (k_base > plane_bytes || past_bytes > plane_bytes - k_base ||
        v_base > plane_bytes || past_bytes > plane_bytes - v_base) {
        return ALIGN_GGML_BOUNDS;
    }
    if ((uint64_t) plane_bytes > (uint64_t) SIZE_MAX ||
        (uint64_t) stage_bytes > (uint64_t) SIZE_MAX) {
        return ALIGN_GGML_BOUNDS;
    }

    plane_address = (uintptr_t) plane;
    stage_address = (uintptr_t) stage;
    if ((uint64_t) plane_bytes > (uint64_t) (UINTPTR_MAX - plane_address) ||
        (uint64_t) stage_bytes > (uint64_t) (UINTPTR_MAX - stage_address)) {
        return ALIGN_GGML_BOUNDS;
    }
    if ((uint64_t) k_base > (uint64_t) (UINTPTR_MAX - plane_address) ||
        (uint64_t) v_base > (uint64_t) (UINTPTR_MAX - plane_address)) {
        return ALIGN_GGML_BOUNDS;
    }
    k_address = plane_address + (uintptr_t) k_base;
    v_address = plane_address + (uintptr_t) v_base;
    stage_end = stage_address + (uintptr_t) stage_bytes;
    k_end = k_address + (uintptr_t) past_bytes;
    v_end = v_address + (uintptr_t) past_bytes;
    if ((k_address < stage_end && stage_address < k_end) ||
        (v_address < stage_end && stage_address < v_end)) {
        return ALIGN_GGML_BOUNDS;
    }

    source = (const unsigned char *) plane;
    destination = (unsigned char *) stage;
    for (head = 0; head < n_head_kv; head++) {
        for (column = 0; column < n_past; column++) {
            int64_t source_at = k_base + (column * n_head_kv + head) * head_dim * 4;
            int64_t destination_at = (head * n_past + column) * head_dim * 4;
            memcpy(destination + (size_t) destination_at,
                   source + (size_t) source_at, (size_t) (head_dim * 4));
        }
    }
#if defined(__aarch64__)
    /* Item 77: transpose canonical V [column][head][lane] into stage [head][lane][column].
     * Byte-pointer vector loads/stores retain the unaligned byte-range ABI. Full tiles and the
     * two scalar tails cover every four-byte value once, after the unchanged checks and K copy.
     */
    int64_t tiled_lanes = head_dim - head_dim % 4;
    int64_t tiled_columns = n_past - n_past % 4;
    int64_t source_stride = n_head_kv * head_dim * 4;
    int64_t destination_stride = n_past * 4;
    for (head = 0; head < n_head_kv; head++) {
        for (lane = 0; lane < tiled_lanes; lane += 4) {
            for (column = 0; column < tiled_columns; column += 4) {
                int64_t source_at =
                    v_base + ((column * n_head_kv + head) * head_dim + lane) * 4;
                int64_t destination_at =
                    past_bytes + ((head * head_dim + lane) * n_past + column) * 4;
                uint32x4_t r0 = vreinterpretq_u32_u8(vld1q_u8(
                    source + (size_t) source_at));
                uint32x4_t r1 = vreinterpretq_u32_u8(vld1q_u8(
                    source + (size_t) (source_at + source_stride)));
                uint32x4_t r2 = vreinterpretq_u32_u8(vld1q_u8(
                    source + (size_t) (source_at + source_stride * 2)));
                uint32x4_t r3 = vreinterpretq_u32_u8(vld1q_u8(
                    source + (size_t) (source_at + source_stride * 3)));
                uint32x4x2_t pairs01 = vtrnq_u32(r0, r1);
                uint32x4x2_t pairs23 = vtrnq_u32(r2, r3);
                uint64x2_t pairs02_lo = vreinterpretq_u64_u32(pairs01.val[0]);
                uint64x2_t pairs02_hi = vreinterpretq_u64_u32(pairs23.val[0]);
                uint64x2_t pairs13_lo = vreinterpretq_u64_u32(pairs01.val[1]);
                uint64x2_t pairs13_hi = vreinterpretq_u64_u32(pairs23.val[1]);
                uint32x4_t column0 = vreinterpretq_u32_u64(vtrn1q_u64(pairs02_lo, pairs02_hi));
                uint32x4_t column2 = vreinterpretq_u32_u64(vtrn2q_u64(pairs02_lo, pairs02_hi));
                uint32x4_t column1 = vreinterpretq_u32_u64(vtrn1q_u64(pairs13_lo, pairs13_hi));
                uint32x4_t column3 = vreinterpretq_u32_u64(vtrn2q_u64(pairs13_lo, pairs13_hi));
                vst1q_u8(destination + (size_t) destination_at, vreinterpretq_u8_u32(column0));
                vst1q_u8(destination + (size_t) (destination_at + destination_stride),
                         vreinterpretq_u8_u32(column1));
                vst1q_u8(destination + (size_t) (destination_at + destination_stride * 2),
                         vreinterpretq_u8_u32(column2));
                vst1q_u8(destination + (size_t) (destination_at + destination_stride * 3),
                         vreinterpretq_u8_u32(column3));
            }
            for (column = tiled_columns; column < n_past; column++) {
                int64_t tile_lane = 0;
                for (tile_lane = lane; tile_lane < lane + 4; tile_lane++) {
                    int64_t source_at =
                        v_base + ((column * n_head_kv + head) * head_dim + tile_lane) * 4;
                    int64_t destination_at =
                        past_bytes + ((head * head_dim + tile_lane) * n_past + column) * 4;
                    memcpy(destination + (size_t) destination_at,
                           source + (size_t) source_at, 4);
                }
            }
        }
        for (lane = tiled_lanes; lane < head_dim; lane++) {
            for (column = 0; column < n_past; column++) {
                int64_t source_at =
                    v_base + ((column * n_head_kv + head) * head_dim + lane) * 4;
                int64_t destination_at =
                    past_bytes + ((head * head_dim + lane) * n_past + column) * 4;
                memcpy(destination + (size_t) destination_at,
                       source + (size_t) source_at, 4);
            }
        }
    }
#else
    for (head = 0; head < n_head_kv; head++) {
        for (lane = 0; lane < head_dim; lane++) {
            for (column = 0; column < n_past; column++) {
                int64_t source_at =
                    v_base + ((column * n_head_kv + head) * head_dim + lane) * 4;
                int64_t destination_at =
                    past_bytes + ((head * head_dim + lane) * n_past + column) * 4;
                memcpy(destination + (size_t) destination_at,
                       source + (size_t) source_at, 4);
            }
        }
    }
#endif
    return ALIGN_GGML_OK;
}


/* R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY
 * (`docs/specs/r8-olmoe-plane-roundtrip-boundary.md` section 2). Compare one graph-consumed K or V
 * image against the canonical plane without interpreting any float. Zero is exact, a positive
 * result is the first mismatching column plus one, and a negative result is a status. Every scalar,
 * byte range, and pointer extent is validated before the first read. Both inputs remain borrowed;
 * overlap is safe because this function writes nothing and retains nothing.
 */
#define ALIGN_GGML_KV_LAYOUT_K 0
#define ALIGN_GGML_KV_LAYOUT_V 1

#if defined(__aarch64__)
static uint32x4_t align_ggml_load_u32x4(const unsigned char *data) {
    return vreinterpretq_u32_u8(vld1q_u8(data));
}
#endif

int64_t align_ggml_compare_kv_plane(const void *consumed, int64_t consumed_bytes,
                                    const void *plane, int64_t plane_bytes,
                                    int64_t plane_base, int64_t head_dim,
                                    int64_t n_head_kv, int64_t columns, int32_t layout) {
    int64_t elements = 0;
    int64_t span = 0;
    int64_t row_bytes = 0;
    uintptr_t consumed_address = 0;
    uintptr_t plane_address = 0;
    const unsigned char *consumed_data = NULL;
    const unsigned char *plane_data = NULL;
    int64_t head = 0;
    int64_t column = 0;
    int64_t lane = 0;

    if (consumed == NULL || plane == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (consumed_bytes < 0 || plane_bytes < 0 || plane_base < 0 ||
        head_dim <= 0 || n_head_kv <= 0 || columns <= 0 ||
        (layout != ALIGN_GGML_KV_LAYOUT_K && layout != ALIGN_GGML_KV_LAYOUT_V)) {
        return ALIGN_GGML_BOUNDS;
    }
    if (head_dim > INT64_MAX / n_head_kv) {
        return ALIGN_GGML_BOUNDS;
    }
    elements = head_dim * n_head_kv;
    if (elements > INT64_MAX / columns) {
        return ALIGN_GGML_BOUNDS;
    }
    elements *= columns;
    if (elements > INT64_MAX / 4 || head_dim > INT64_MAX / 4) {
        return ALIGN_GGML_BOUNDS;
    }
    span = elements * 4;
    row_bytes = head_dim * 4;
    if (span > consumed_bytes || plane_base > plane_bytes || span > plane_bytes - plane_base) {
        return ALIGN_GGML_BOUNDS;
    }
    if ((uint64_t) consumed_bytes > (uint64_t) SIZE_MAX ||
        (uint64_t) plane_bytes > (uint64_t) SIZE_MAX) {
        return ALIGN_GGML_BOUNDS;
    }
    consumed_address = (uintptr_t) consumed;
    plane_address = (uintptr_t) plane;
    if ((uint64_t) consumed_bytes > (uint64_t) (UINTPTR_MAX - consumed_address) ||
        (uint64_t) plane_bytes > (uint64_t) (UINTPTR_MAX - plane_address)) {
        return ALIGN_GGML_BOUNDS;
    }

    consumed_data = (const unsigned char *) consumed;
    plane_data = (const unsigned char *) plane;
    if (layout == ALIGN_GGML_KV_LAYOUT_K) {
        for (head = 0; head < n_head_kv; head++) {
            for (column = 0; column < columns; column++) {
                int64_t source_at =
                    plane_base + (column * n_head_kv + head) * row_bytes;
                int64_t consumed_at = (head * columns + column) * row_bytes;
                if (memcmp(plane_data + (size_t) source_at,
                           consumed_data + (size_t) consumed_at,
                           (size_t) row_bytes) != 0) {
                    return column + 1;
                }
            }
        }
        return 0;
    }

#if defined(__aarch64__)
    /* Consumed V is [head][lane][column], while the plane is [column][head][lane]. Four
     * contiguous row loads, an in-register transpose, and four contiguous column loads cover
     * sixteen exact lanes. A difference falls through to the original scalar traversal so its
     * observable head/lane/column priority remains authoritative.
     */
    for (head = 0; head < n_head_kv; head++) {
        int64_t tiled_lanes = head_dim - head_dim % 4;
        int64_t tiled_columns = columns - columns % 4;
        for (lane = 0; lane < tiled_lanes; lane += 4) {
            for (column = 0; column < tiled_columns; column += 4) {
                int64_t consumed_at =
                    (head * head_dim * columns + lane * columns + column) * 4;
                int64_t plane_at =
                    plane_base + ((column * n_head_kv + head) * head_dim + lane) * 4;
                uint32x4_t r0 = align_ggml_load_u32x4(
                    consumed_data + (size_t) consumed_at);
                uint32x4_t r1 = align_ggml_load_u32x4(
                    consumed_data + (size_t) (consumed_at + columns * 4));
                uint32x4_t r2 = align_ggml_load_u32x4(
                    consumed_data + (size_t) (consumed_at + columns * 8));
                uint32x4_t r3 = align_ggml_load_u32x4(
                    consumed_data + (size_t) (consumed_at + columns * 12));
                uint32x4x2_t pairs01 = vtrnq_u32(r0, r1);
                uint32x4x2_t pairs23 = vtrnq_u32(r2, r3);
                uint64x2_t pairs02_lo = vreinterpretq_u64_u32(pairs01.val[0]);
                uint64x2_t pairs02_hi = vreinterpretq_u64_u32(pairs23.val[0]);
                uint64x2_t pairs13_lo = vreinterpretq_u64_u32(pairs01.val[1]);
                uint64x2_t pairs13_hi = vreinterpretq_u64_u32(pairs23.val[1]);
                uint32x4_t column0 = vreinterpretq_u32_u64(vtrn1q_u64(pairs02_lo, pairs02_hi));
                uint32x4_t column2 = vreinterpretq_u32_u64(vtrn2q_u64(pairs02_lo, pairs02_hi));
                uint32x4_t column1 = vreinterpretq_u32_u64(vtrn1q_u64(pairs13_lo, pairs13_hi));
                uint32x4_t column3 = vreinterpretq_u32_u64(vtrn2q_u64(pairs13_lo, pairs13_hi));
                uint32x4_t equal = vceqq_u32(
                    column0,
                    align_ggml_load_u32x4(plane_data + (size_t) plane_at));
                equal = vandq_u32(equal, vceqq_u32(
                    column1,
                    align_ggml_load_u32x4(
                        plane_data + (size_t) (plane_at + n_head_kv * head_dim * 4))));
                equal = vandq_u32(equal, vceqq_u32(
                    column2,
                    align_ggml_load_u32x4(
                        plane_data + (size_t) (plane_at + n_head_kv * head_dim * 8))));
                equal = vandq_u32(equal, vceqq_u32(
                    column3,
                    align_ggml_load_u32x4(
                        plane_data + (size_t) (plane_at + n_head_kv * head_dim * 12))));
                if (vminvq_u32(equal) != UINT32_MAX) {
                    goto align_ggml_v_scalar_mismatch;
                }
            }
            for (column = tiled_columns; column < columns; column++) {
                int64_t tile_lane = 0;
                for (tile_lane = lane; tile_lane < lane + 4; tile_lane++) {
                    int64_t source_at =
                        plane_base + ((column * n_head_kv + head) * head_dim + tile_lane) * 4;
                    int64_t consumed_at =
                        (column + columns * (tile_lane + head_dim * head)) * 4;
                    if (memcmp(plane_data + (size_t) source_at,
                               consumed_data + (size_t) consumed_at, 4) != 0) {
                        goto align_ggml_v_scalar_mismatch;
                    }
                }
            }
        }
        for (lane = tiled_lanes; lane < head_dim; lane++) {
            for (column = 0; column < columns; column++) {
                int64_t source_at =
                    plane_base + ((column * n_head_kv + head) * head_dim + lane) * 4;
                int64_t consumed_at =
                    (column + columns * (lane + head_dim * head)) * 4;
                if (memcmp(plane_data + (size_t) source_at,
                           consumed_data + (size_t) consumed_at, 4) != 0) {
                    goto align_ggml_v_scalar_mismatch;
                }
            }
        }
    }
    return 0;

align_ggml_v_scalar_mismatch:
#endif
    for (head = 0; head < n_head_kv; head++) {
        for (lane = 0; lane < head_dim; lane++) {
            for (column = 0; column < columns; column++) {
                int64_t source_at =
                    plane_base + ((column * n_head_kv + head) * head_dim + lane) * 4;
                int64_t consumed_at = (column + columns * (lane + head_dim * head)) * 4;
                if (memcmp(plane_data + (size_t) source_at,
                           consumed_data + (size_t) consumed_at, 4) != 0) {
                    return column + 1;
                }
            }
        }
    }
    return 0;
}


/* R5C-METAL-PREFILL-ARM (`docs/specs/r5c-metal-prefill.md` sections 3.4, 3.8, and 3.9). The device
 * selector, the property selector, and the one clamp, shared byte-for-byte by both files so that a
 * stub GPU and a real Metal device answer the same questions with the same field ids.
 *
 * The two device kinds are `GGML_BACKEND_DEVICE_TYPE_CPU` and `..._GPU` (section 3.4): the arm
 * names no Metal-specific entry point and includes no `ggml-metal.h`, because
 * `r4-5-external-buffer.md` section 2.5 established that Metal exposes no backend-specific
 * host-pointer function and that the device-generic capability flag is the whole surface.
 */
#define ALIGN_GGML_DEVICE_CPU 0
#define ALIGN_GGML_DEVICE_GPU 1

/* The numeric device properties, selected by field id rather than returned in one record, because
 * a `layout(C)` struct cannot cross this boundary by value at this pin (section 3.1, and
 * `docs/align-requests.md` Request 32). Every field crosses as an `int64_t`, and the two capability
 * flags cross as `0` or `1` for the same reason `bool` is not an FFI type here.
 */
#define ALIGN_GGML_DEV_TYPE_ID       0
#define ALIGN_GGML_DEV_HOST_PTR      1
#define ALIGN_GGML_DEV_HOST_BUFFER   2
#define ALIGN_GGML_DEV_ALIGNMENT     3
#define ALIGN_GGML_DEV_MEMORY_FREE   4
#define ALIGN_GGML_DEV_MEMORY_TOTAL  5

/* `align_ggml_device_text`'s selector. `ggml_backend_dev_name` and `ggml_backend_dev_description`
 * both return a `const char *`, and a `str` cannot be formed over foreign memory at this pin, so
 * each is copied into an Align-owned byte range exactly as `align_ggml_backend_name` already copies
 * the backend's.
 */
#define ALIGN_GGML_DEV_TEXT_NAME        0
#define ALIGN_GGML_DEV_TEXT_DESCRIPTION 1
#define ALIGN_GGML_DEV_TEXT_ID          2

/* `ggml_backend_buft_get_max_size` reports `SIZE_MAX` for the CPU buffer type, which is not
 * representable as an `int64_t`. Both files clamp rather than truncate, so section 3.9 step 21a
 * compares two numbers Align can hold and a device that declares "no limit" reads as the largest
 * limit instead of as a negative one.
 */
#define ALIGN_GGML_MAX_BUFFER_CLAMP ((int64_t) 0x7fffffffffffffffLL)

static int64_t align_ggml_clamp_size(size_t value) {
    if (value > (size_t) ALIGN_GGML_MAX_BUFFER_CLAMP) {
        return ALIGN_GGML_MAX_BUFFER_CLAMP;
    }
    return (int64_t) value;
}

/* R5C-METAL-PREFILL-ARM section 6, correction C17. The directory the backend plugins are
 * `dlopen`ed from, named by the environment and read at **run** time by whichever of the two files
 * owns a registry.
 *
 * `ggml_backend_load_all` searches the working directory, the executable's directory, and the
 * `GGML_BACKEND_DIR` compiled into libggml, and ggml's own `GGML_BACKEND_PATH` variable only
 * **adds** one library file to that set. Measured on the 0.21.0 this host links against: a bogus
 * `libggml-metal.so` named by `GGML_BACKEND_PATH` fails to load and the registry still reports
 * `MTL0` from the compiled-in directory, so a qualification that names one install could exercise
 * another. `ggml_backend_load_all_from_path(dir)` **replaces** the search path with `dir` alone,
 * which is the scoping a named input needs: the named directory is what runs, and a directory
 * holding no loadable backend leaves the registry empty — which section 3.9 step 20a reports as
 * `R5C_GPU_UNAVAILABLE`, a document with a verdict rather than a silent substitution.
 *
 * Reading it at **run** time is correction C3's rule kept: no shim behaviour depends on the
 * environment the library was compiled in. The stub declares the same name and loads nothing,
 * because it has no registry to load into.
 */
#define ALIGN_GGML_BACKEND_DIR_ENV "ALIGN_GGML_BACKEND_DIR"

/* --- END R4.5 SHARED SHIM CONTRACT --- */

/* ---------------------------------------------------------------------------------------------
 * Availability, the ABI probe, and the type predicate
 * ------------------------------------------------------------------------------------------- */

int32_t align_ggml_available(void) {
    return 1;
}

/* The backend registry, loaded at most once per process.
 *
 * Section 2.1: this host ships `libggml.dylib` as a nineteen-symbol registry and the CPU, Metal,
 * and BLAS backends as `dlopen`ed plugins, so `ggml_backend_cpu_init` is not linkable and the
 * registry path is the only one that works. It is also the backend-agnostic one, which is why
 * section 2.5's GPU probe was three lines different rather than a second implementation.
 *
 * Correction C17: when `ALIGN_GGML_BACKEND_DIR_ENV` names a directory, that directory is the
 * **only** place a backend is loaded from. `ggml_backend_load_all` would search the compiled-in
 * `GGML_BACKEND_DIR` first and `GGML_BACKEND_PATH` only adds to that search, so neither can make a
 * named install authoritative; `ggml_backend_load_all_from_path` replaces the search path, so a
 * caller that names a directory gets the devices in it and nothing else. An empty or unset variable
 * keeps the ordinary search, which is what every other caller in this repository uses.
 */
static void align_ggml_registry_ready(void) {
    static int loaded = 0;
    if (!loaded) {
#ifndef ALIGN_GGML_STATIC_CPU_ONLY
        const char *backend_dir = getenv(ALIGN_GGML_BACKEND_DIR_ENV);
        if (backend_dir != NULL && backend_dir[0] != '\0') {
            ggml_backend_load_all_from_path(backend_dir);
        } else {
            ggml_backend_load_all();
        }
#endif
        loaded = 1;
    }
}

/* R5C section 3.4. Device selection for either kind, through the registry and nothing else, after
 * the same one-time load. A `NULL` answer is "the registry has no device of that type", which
 * section 3.9 step 20a reports as `R5C_GPU_UNAVAILABLE` — a document with a verdict, not a signal.
 */
void *align_ggml_device_by_kind(int32_t kind) {
    align_ggml_registry_ready();
    if (kind == ALIGN_GGML_DEVICE_CPU) {
        return (void *) ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
    }
    if (kind == ALIGN_GGML_DEVICE_GPU) {
        return (void *) ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU);
    }
    return NULL;
}

/* G1 resident device owner. The runtime has already verified the bundle manifest and artifacts;
 * this boundary loads the exact selected backend artifact, pins the verified bundle id, selects
 * one exact registry/device pair, and holds the process-wide serial invocation guard.
 */
#define ALIGN_GPU_OK                    0
#define ALIGN_GPU_CONFIG              (-1)
#define ALIGN_GPU_BUSY                (-2)
#define ALIGN_GPU_BUNDLE_SWITCH       (-3)
#define ALIGN_GPU_BACKEND_UNAVAILABLE (-4)
#define ALIGN_GPU_DEVICE_UNAVAILABLE  (-5)
#define ALIGN_GPU_POISONED            (-6)
#define ALIGN_GPU_ALLOCATION          (-7)
#define ALIGN_GPU_MEMORY_BUDGET       (-8)
#define ALIGN_GPU_COMPUTE             (-9)
#define ALIGN_GPU_GRAPH_KINDS           2
#define ALIGN_GPU_GRAPH_PREFILL         0
#define ALIGN_GPU_GRAPH_DECODE          1

struct align_gpu_device_state {
    ggml_backend_dev_t device;
    ggml_backend_t backend;
    char bundle_id[65];
    struct ggml_context *metadata_ctx;
    void *metadata_storage;
    unsigned char *metadata_base;
    size_t metadata_capacity;
    size_t graph_metadata_offset;
    struct ggml_context *graph_contexts[ALIGN_GPU_GRAPH_KINDS];
    size_t graph_context_bytes[ALIGN_GPU_GRAPH_KINDS];
    void *staging;
    ggml_backend_buffer_t weights_buffer;
    ggml_backend_buffer_t kv_buffer;
    ggml_backend_buffer_t input_buffer;
    struct ggml_tallocr weight_allocator;
    struct ggml_tallocr kv_allocator;
    struct ggml_tallocr input_allocator;
    struct ggml_tensor *pending_weight;
    ggml_gallocr_t workspace_allocator;
    int64_t host_budget_bytes;
    int64_t device_budget_bytes;
    int64_t host_planned_bytes;
    int64_t device_planned_bytes;
    int64_t weights_bytes;
    int64_t kv_bytes;
    int64_t workspace_bytes;
    int64_t metadata_bytes;
    int64_t staging_bytes;
    int64_t legacy_cache_bytes;
    int memory_planned;
    int memory_allocated;
    int64_t weights_expected;
    int64_t weights_created;
    int64_t weights_uploaded;
    int64_t weights_uploaded_bytes;
    size_t pending_weight_uploaded_bytes;
    int weights_finished;
    int weights_failed;
    int workspace_prepared;
    int workspace_failed;
    int64_t kv_expected;
    int64_t kv_created;
    int64_t kv_updated_bytes;
    int kv_finished;
    int kv_failed;
    int64_t inputs_expected;
    int64_t inputs_created;
    int64_t input_updated_bytes;
    size_t input_offset;
    int inputs_finished;
    int inputs_failed;
    struct ggml_cgraph *workspace_graphs[ALIGN_GPU_GRAPH_KINDS];
    char graph_keys[ALIGN_GPU_GRAPH_KINDS][65];
    int graph_prepared[ALIGN_GPU_GRAPH_KINDS];
    int64_t graph_prepare_count[ALIGN_GPU_GRAPH_KINDS];
    int64_t graph_execution_count[ALIGN_GPU_GRAPH_KINDS];
    int64_t graph_current_execution_count[ALIGN_GPU_GRAPH_KINDS];
    int64_t graph_reuse_count[ALIGN_GPU_GRAPH_KINDS];
    int64_t graph_invalidation_count[ALIGN_GPU_GRAPH_KINDS];
    int staging_consumed;
    int staging_path_valid;
    int64_t observation_nodes;
    int64_t observation_read_bytes;
    int64_t observation_read_calls;
    int64_t observation_sync_calls;
    int64_t observation_host_peak;
    int64_t observation_device_peak;
    int64_t observation_weight_payload;
    int64_t observation_kv_payload;
    int64_t observation_model_ops;
    int64_t observation_layers;
    int64_t observation_experts;
    int observation_failed;
};

static void align_gpu_synchronize(struct align_gpu_device_state *state) {
    if (state->observation_sync_calls == INT64_MAX) {
        state->observation_failed = 1;
    } else {
        state->observation_sync_calls += 1;
    }
    ggml_backend_synchronize(state->backend);
}

static atomic_int align_gpu_busy = 0;
static atomic_int align_gpu_registry_state = 0;
static char align_gpu_bundle_id[65];
static ggml_backend_reg_t align_gpu_registry = NULL;
static char align_gpu_staging_root[4097];
static int64_t align_gpu_staging_count = 0;

#if defined(__GNUC__)
__attribute__((destructor))
#endif
static void align_gpu_staging_cleanup(void) {
    char artifact[4128];
    int64_t index = align_gpu_staging_count;
    while (index > 0) {
        index -= 1;
        if (snprintf(artifact, sizeof(artifact), "%s/artifact-%lld",
                     align_gpu_staging_root, (long long) index) > 0) {
            (void) remove(artifact);
        }
    }
    if (align_gpu_staging_root[0] != '\0') {
        (void) rmdir(align_gpu_staging_root);
    }
    align_gpu_staging_root[0] = '\0';
    align_gpu_staging_count = 0;
}

int32_t align_gpu_staging_transfer(
        const void *root_input, int64_t root_length, int64_t artifact_count, int32_t poison) {
    if (root_input == NULL || root_length <= 0 || root_length > 4096
        || artifact_count <= 0 || artifact_count > 128
        || memchr(root_input, '\0', (size_t) root_length) != NULL
        || align_gpu_staging_root[0] != '\0') {
        return ALIGN_GPU_CONFIG;
    }
    memcpy(align_gpu_staging_root, root_input, (size_t) root_length);
    align_gpu_staging_root[root_length] = '\0';
    align_gpu_staging_count = artifact_count;
    if (poison != 0) {
        atomic_store(&align_gpu_registry_state, -1);
    }
    return ALIGN_GPU_OK;
}

int32_t align_gpu_staging_owned(void) {
    return align_gpu_staging_root[0] == '\0' ? 0 : 1;
}

static int align_gpu_private_backend_path(const char *path) {
    const char *root = path == NULL ? NULL : strstr(path, "/align_llm_gpu-");
    const char *artifact = root == NULL ? NULL : strstr(root, "/artifact-");
    return path != NULL && path[0] == '/' && root != NULL && artifact != NULL
        && artifact[10] >= '0' && artifact[10] <= '9';
}

static int align_gpu_copy_text(char *out, size_t cap, const void *input, int64_t length) {
    if (out == NULL || input == NULL || length <= 0 || (uint64_t) length >= (uint64_t) cap
        || memchr(input, '\0', (size_t) length) != NULL) {
        return 0;
    }
    memcpy(out, input, (size_t) length);
    out[length] = '\0';
    return 1;
}

static const char *align_gpu_registry_name(const char *backend) {
    if (strcmp(backend, "metal") == 0) {
        return "MTL";
    }
    if (strcmp(backend, "cuda") == 0) {
        return "CUDA";
    }
    return NULL;
}

static int align_gpu_bundle_id_ok(const char *bundle_id) {
    size_t index = 0;
    if (bundle_id == NULL) {
        return 0;
    }
    for (index = 0; index < 64; ++index) {
        unsigned char byte = (unsigned char) bundle_id[index];
        if (!((byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f'))) {
            return 0;
        }
    }
    return bundle_id[64] == '\0';
}

int32_t align_gpu_device_open(
        const void *backend_input, int64_t backend_length,
        const void *device_input, int64_t device_length,
        const void *backend_path_input, int64_t backend_path_length,
        const void *bundle_id_input, int64_t bundle_id_length,
        int64_t host_budget_bytes, int64_t device_budget_bytes,
        void *output) {
    char backend_name[6];
    char device_name[257];
    char backend_path[4097];
    char bundle_id[65];
    const char *registry_name = NULL;
    ggml_backend_reg_t selected_registry = NULL;
    ggml_backend_dev_t selected_device = NULL;
    struct align_gpu_device_state *state = NULL;
    size_t device_matches = 0;
    size_t i = 0;
    int expected = 0;
    int registry_state = 0;

    if (output == NULL) {
        return ALIGN_GPU_CONFIG;
    }
    *(void **) output = NULL;
    if (!align_gpu_copy_text(backend_name, sizeof(backend_name), backend_input, backend_length)
        || !align_gpu_copy_text(device_name, sizeof(device_name), device_input, device_length)
        || !align_gpu_copy_text(
            backend_path, sizeof(backend_path), backend_path_input, backend_path_length)
        || !align_gpu_copy_text(bundle_id, sizeof(bundle_id), bundle_id_input, bundle_id_length)
        || bundle_id_length != 64 || !align_gpu_bundle_id_ok(bundle_id)
        || host_budget_bytes <= 0 || device_budget_bytes <= 0) {
        return ALIGN_GPU_CONFIG;
    }
    registry_name = align_gpu_registry_name(backend_name);
    if (registry_name == NULL) {
        return ALIGN_GPU_CONFIG;
    }
    if (!atomic_compare_exchange_strong(&align_gpu_busy, &expected, 1)) {
        return ALIGN_GPU_BUSY;
    }

    registry_state = atomic_load(&align_gpu_registry_state);
    if (registry_state < 0) {
        atomic_store(&align_gpu_busy, 0);
        return ALIGN_GPU_POISONED;
    }
    if (registry_state > 0 && memcmp(align_gpu_bundle_id, bundle_id, 65) != 0) {
        atomic_store(&align_gpu_busy, 0);
        return ALIGN_GPU_BUNDLE_SWITCH;
    }
    if (registry_state == 0) {
        selected_registry = ggml_backend_load(backend_path);
    } else {
        selected_registry = align_gpu_registry;
    }
    if (selected_registry == NULL
        || strcmp(ggml_backend_reg_name(selected_registry), registry_name) != 0) {
        if (registry_state == 0) {
            atomic_store(&align_gpu_registry_state, -1);
        }
        atomic_store(&align_gpu_busy, 0);
        return ALIGN_GPU_BACKEND_UNAVAILABLE;
    }
    for (i = 0; i < ggml_backend_reg_dev_count(selected_registry); ++i) {
        ggml_backend_dev_t candidate = ggml_backend_reg_dev_get(selected_registry, i);
        if (candidate != NULL && strcmp(ggml_backend_dev_name(candidate), device_name) == 0) {
            selected_device = candidate;
            device_matches += 1;
        }
    }
    if (device_matches != 1 || selected_device == NULL) {
        if (registry_state == 0) {
            atomic_store(&align_gpu_registry_state, -1);
        }
        atomic_store(&align_gpu_busy, 0);
        return ALIGN_GPU_DEVICE_UNAVAILABLE;
    }

    state = (struct align_gpu_device_state *) calloc(1, sizeof(*state));
    if (state == NULL) {
        if (registry_state == 0) {
            atomic_store(&align_gpu_registry_state, -1);
        }
        atomic_store(&align_gpu_busy, 0);
        return ALIGN_GPU_ALLOCATION;
    }
    state->device = selected_device;
    state->backend = ggml_backend_dev_init(selected_device, NULL);
    memcpy(state->bundle_id, bundle_id, 65);
    state->host_budget_bytes = host_budget_bytes;
    state->device_budget_bytes = device_budget_bytes;
    state->staging_consumed = registry_state == 0;
    state->staging_path_valid = align_gpu_private_backend_path(backend_path);
    if (state->backend == NULL) {
        free(state);
        if (registry_state == 0) {
            atomic_store(&align_gpu_registry_state, -1);
        }
        atomic_store(&align_gpu_busy, 0);
        return ALIGN_GPU_POISONED;
    }
    if (registry_state == 0) {
        memcpy(align_gpu_bundle_id, bundle_id, 65);
        align_gpu_registry = selected_registry;
        atomic_store(&align_gpu_registry_state, 1);
    }
    *(void **) output = state;
    return ALIGN_GPU_OK;
}

int32_t align_gpu_device_staging_consumed(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    return state == NULL ? 0 : state->staging_consumed;
}

int32_t align_gpu_device_staging_path_valid(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    return state == NULL ? 0 : state->staging_path_valid;
}

int32_t align_gpu_device_bundle_id(void *owner, void *out, int32_t cap) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || out == NULL || cap < 64) {
        return 0;
    }
    memcpy(out, state->bundle_id, 64);
    return 64;
}

void *align_gpu_device_handle(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    return state == NULL ? NULL : (void *) state->device;
}

void *align_gpu_backend_handle(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    return state == NULL ? NULL : (void *) state->backend;
}

int32_t align_gpu_device_synchronize(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || state->backend == NULL) {
        return ALIGN_GPU_CONFIG;
    }
    align_gpu_synchronize(state);
    return state->observation_failed ? ALIGN_GPU_CONFIG : ALIGN_GPU_OK;
}

static int align_gpu_add_bytes(int64_t left, int64_t right, int64_t *out) {
    if (out == NULL || left < 0 || right < 0 || left > INT64_MAX - right) {
        return 0;
    }
    *out = left + right;
    return 1;
}

int32_t align_gpu_memory_admit(
        void *owner, int64_t weights_bytes, int64_t kv_bytes, int64_t workspace_bytes,
        int64_t metadata_bytes, int64_t staging_bytes, int64_t legacy_cache_bytes) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    int64_t device_total = 0;
    int64_t host_total = 0;
    if (state == NULL || state->memory_planned || weights_bytes <= 0 || kv_bytes <= 0
        || workspace_bytes <= 0 || metadata_bytes <= 0 || staging_bytes <= 0
        || legacy_cache_bytes < 0) {
        return ALIGN_GPU_CONFIG;
    }
    if (!align_gpu_add_bytes(weights_bytes, kv_bytes, &device_total)
        || !align_gpu_add_bytes(device_total, workspace_bytes, &device_total)
        || !align_gpu_add_bytes(metadata_bytes, staging_bytes, &host_total)
        || !align_gpu_add_bytes(host_total, legacy_cache_bytes, &host_total)
        || device_total > state->device_budget_bytes || host_total > state->host_budget_bytes) {
        return ALIGN_GPU_MEMORY_BUDGET;
    }
    state->weights_bytes = weights_bytes;
    state->kv_bytes = kv_bytes;
    state->workspace_bytes = workspace_bytes;
    state->metadata_bytes = metadata_bytes;
    state->staging_bytes = staging_bytes;
    state->legacy_cache_bytes = legacy_cache_bytes;
    state->device_planned_bytes = device_total;
    state->host_planned_bytes = host_total;
    state->memory_planned = 1;
    return ALIGN_GPU_OK;
}

int64_t align_gpu_memory_bytes(void *owner, int32_t field) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || !state->memory_planned) {
        return -1;
    }
    switch (field) {
    case 0: return state->host_planned_bytes;
    case 1: return state->device_planned_bytes;
    case 2: return state->weights_bytes;
    case 3: return state->kv_bytes;
    case 4: return state->workspace_bytes;
    case 5: return state->metadata_bytes;
    case 6: return state->staging_bytes;
    case 7: return state->legacy_cache_bytes;
    default: return -1;
    }
}

static void align_gpu_memory_release(struct align_gpu_device_state *state) {
    int kind = 0;
    if (state == NULL) {
        return;
    }
    if (state->workspace_allocator != NULL) {
        ggml_gallocr_free(state->workspace_allocator);
        state->workspace_allocator = NULL;
    }
    if (state->input_buffer != NULL) {
        ggml_backend_buffer_free(state->input_buffer);
        state->input_buffer = NULL;
    }
    if (state->kv_buffer != NULL) {
        ggml_backend_buffer_free(state->kv_buffer);
        state->kv_buffer = NULL;
    }
    if (state->weights_buffer != NULL) {
        ggml_backend_buffer_free(state->weights_buffer);
        state->weights_buffer = NULL;
    }
    free(state->staging);
    state->staging = NULL;
    for (kind = 0; kind < ALIGN_GPU_GRAPH_KINDS; ++kind) {
        if (state->graph_contexts[kind] != NULL) {
            ggml_free(state->graph_contexts[kind]);
            state->graph_contexts[kind] = NULL;
        }
    }
    if (state->metadata_ctx != NULL) {
        ggml_free(state->metadata_ctx);
        state->metadata_ctx = NULL;
    }
    free(state->metadata_storage);
    state->metadata_storage = NULL;
    state->metadata_base = NULL;
    state->metadata_capacity = 0;
    state->graph_metadata_offset = 0;
    state->memory_allocated = 0;
}

#ifndef ALIGN_GPU_FORCE_ALLOCATION_PREFIX
#define ALIGN_GPU_FORCE_ALLOCATION_PREFIX 0
#endif

int64_t align_gpu_memory_allocated_bytes(void *owner, int32_t field);

static void align_gpu_observe_memory(struct align_gpu_device_state *state) {
    int64_t host = align_gpu_memory_allocated_bytes(state, 0);
    int64_t device = align_gpu_memory_allocated_bytes(state, 1);
    if (host < 0 || device < 0) {
        state->observation_failed = 1;
        return;
    }
    if (host > state->observation_host_peak) { state->observation_host_peak = host; }
    if (device > state->observation_device_peak) { state->observation_device_peak = device; }
}

int32_t align_gpu_memory_allocate(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_init_params params;
    ggml_backend_buffer_type_t buft = NULL;
    uintptr_t metadata_addr = 0;
    uintptr_t metadata_aligned = 0;
    uintptr_t metadata_modulus = 0;
    size_t metadata_padding = 0;
    void *weights_base = NULL;
    void *kv_base = NULL;
    size_t weights_alignment = 0;
    size_t kv_alignment = 0;
    uintptr_t weights_modulus = 0;
    uintptr_t kv_modulus = 0;
    if (state == NULL || state->backend == NULL || !state->memory_planned
        || state->memory_allocated) {
        return ALIGN_GPU_CONFIG;
    }
    if ((uint64_t) state->metadata_bytes > SIZE_MAX || (uint64_t) state->staging_bytes > SIZE_MAX
        || (uint64_t) state->weights_bytes > SIZE_MAX || (uint64_t) state->kv_bytes > SIZE_MAX
        || (uint64_t) state->workspace_bytes > SIZE_MAX) {
        return ALIGN_GPU_ALLOCATION;
    }
    if (ALIGN_GPU_FORCE_ALLOCATION_PREFIX != 1) {
        state->metadata_storage = malloc((size_t) state->metadata_bytes);
    }
    if (state->metadata_storage == NULL) {
        goto fail;
    }
    metadata_addr = (uintptr_t) state->metadata_storage;
    metadata_modulus = metadata_addr & (uintptr_t) (GGML_MEM_ALIGN - 1);
    metadata_padding = metadata_modulus == 0 ? 0 : GGML_MEM_ALIGN - metadata_modulus;
    if (metadata_padding >= (size_t) state->metadata_bytes) {
        goto fail;
    }
    metadata_aligned = metadata_addr + metadata_padding;
    params.mem_size = (size_t) state->metadata_bytes - metadata_padding;
    params.mem_buffer = (void *) metadata_aligned;
    params.no_alloc = true;
    state->metadata_ctx = ggml_init(params);
    if (state->metadata_ctx == NULL) {
        goto fail;
    }
    state->metadata_base = (unsigned char *) metadata_aligned;
    state->metadata_capacity = params.mem_size;
    if (ALIGN_GPU_FORCE_ALLOCATION_PREFIX != 2) {
        state->staging = malloc((size_t) state->staging_bytes);
    }
    if (state->staging == NULL) {
        goto fail;
    }
    buft = ggml_backend_get_default_buffer_type(state->backend);
    if (buft == NULL) {
        goto fail;
    }
    if (ALIGN_GPU_FORCE_ALLOCATION_PREFIX != 3) {
        state->weights_buffer =
            ggml_backend_buft_alloc_buffer(buft, (size_t) state->weights_bytes);
    }
    if (state->weights_buffer == NULL) {
        goto fail;
    }
    if (ggml_backend_buffer_get_size(state->weights_buffer) != (size_t) state->weights_bytes) {
        goto fail;
    }
    weights_base = ggml_backend_buffer_get_base(state->weights_buffer);
    weights_alignment = ggml_backend_buffer_get_alignment(state->weights_buffer);
    if (weights_base == NULL || weights_alignment == 0
        || (weights_alignment & (weights_alignment - 1)) != 0) {
        goto fail;
    }
    weights_modulus = (uintptr_t) weights_base & (uintptr_t) (weights_alignment - 1);
    state->weight_allocator.buffer = state->weights_buffer;
    state->weight_allocator.base = weights_base;
    state->weight_allocator.alignment = weights_alignment;
    state->weight_allocator.offset = weights_modulus == 0 ? 0 : weights_alignment - weights_modulus;
    if (ALIGN_GPU_FORCE_ALLOCATION_PREFIX != 4) {
        state->kv_buffer = ggml_backend_buft_alloc_buffer(buft, (size_t) state->kv_bytes);
    }
    if (state->kv_buffer == NULL) {
        goto fail;
    }
    if (ggml_backend_buffer_get_size(state->kv_buffer) != (size_t) state->kv_bytes) {
        goto fail;
    }
    kv_base = ggml_backend_buffer_get_base(state->kv_buffer);
    kv_alignment = ggml_backend_buffer_get_alignment(state->kv_buffer);
    if (kv_base == NULL || kv_alignment == 0 || (kv_alignment & (kv_alignment - 1)) != 0) {
        goto fail;
    }
    kv_modulus = (uintptr_t) kv_base & (uintptr_t) (kv_alignment - 1);
    state->kv_allocator.buffer = state->kv_buffer;
    state->kv_allocator.base = kv_base;
    state->kv_allocator.alignment = kv_alignment;
    state->kv_allocator.offset = kv_modulus == 0 ? 0 : kv_alignment - kv_modulus;
    /* Reserve no unused workspace: input and graph extents are measured separately. */
    state->memory_allocated = 1;
    align_gpu_observe_memory(state);
    return ALIGN_GPU_OK;

fail:
    align_gpu_memory_release(state);
    return ALIGN_GPU_ALLOCATION;
}

int64_t align_gpu_memory_allocated_bytes(void *owner, int32_t field) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    int64_t weights = 0;
    int64_t kv = 0;
    int64_t inputs = 0;
    int64_t workspace = 0;
    if (state == NULL || !state->memory_allocated) {
        return -1;
    }
    weights = (int64_t) ggml_backend_buffer_get_size(state->weights_buffer);
    kv = (int64_t) ggml_backend_buffer_get_size(state->kv_buffer);
    if (state->input_buffer != NULL) {
        inputs = (int64_t) ggml_backend_buffer_get_size(state->input_buffer);
    }
    if (state->workspace_allocator != NULL) {
        workspace = (int64_t) ggml_gallocr_get_buffer_size(state->workspace_allocator, 0);
    }
    switch (field) {
    case 0: return state->metadata_bytes + state->staging_bytes;
    case 1: return weights + kv + inputs + workspace;
    case 2: return weights;
    case 3: return kv;
    case 4: return inputs + workspace;
    case 5: return state->metadata_bytes;
    case 6: return state->staging_bytes;
    case 7: return 0;
    default: return -1;
    }
}

int64_t align_gpu_weight_metadata_bytes(int64_t tensor_count) {
    size_t overhead = ggml_tensor_overhead();
    int64_t payload = 0;
    if (tensor_count <= 0 || overhead == 0
        || (uint64_t) tensor_count > (uint64_t) INT64_MAX / overhead) {
        return -1;
    }
    payload = (int64_t) ((size_t) tensor_count * overhead);
    if (payload > INT64_MAX - (GGML_MEM_ALIGN - 1)) {
        return -1;
    }
    return payload + (GGML_MEM_ALIGN - 1);
}

int32_t align_gpu_weights_begin(void *owner, int64_t tensor_count) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    int64_t required = align_gpu_weight_metadata_bytes(tensor_count);
    if (state == NULL || !state->memory_allocated || state->weights_expected != 0
        || required <= 0 || required > state->metadata_bytes) {
        return ALIGN_GPU_CONFIG;
    }
    state->weights_expected = tensor_count;
    return ALIGN_GPU_OK;
}

static int align_gpu_weight_shape(
        int32_t type, int32_t n_dims, const int64_t ne[4], size_t *nbytes) {
    int row = align_ggml_table_row(type);
    uint64_t total = 0;
    uint64_t first = 0;
    int dim = 0;
    if (row < 0 || n_dims < 1 || n_dims > 4 || nbytes == NULL || ne[0] <= 0
        || ne[0] % align_ggml_type_table[row][1] != 0) {
        return 0;
    }
    first = (uint64_t) (ne[0] / align_ggml_type_table[row][1]);
    if (first > (uint64_t) SIZE_MAX / (uint64_t) align_ggml_type_table[row][2]) {
        return 0;
    }
    total = first * (uint64_t) align_ggml_type_table[row][2];
    for (dim = 1; dim < 4; ++dim) {
        if ((dim < n_dims && ne[dim] <= 0) || (dim >= n_dims && ne[dim] != 1)) {
            return 0;
        }
        if (dim < n_dims) {
            if ((uint64_t) ne[dim] > (uint64_t) SIZE_MAX / total) {
                return 0;
            }
            total *= (uint64_t) ne[dim];
        }
    }
    if (total == 0 || total > SIZE_MAX || total > INT64_MAX) {
        return 0;
    }
    *nbytes = (size_t) total;
    return 1;
}

int64_t align_gpu_weight_allocation_bytes(
        void *owner, int32_t type, int32_t n_dims,
        int64_t ne0, int64_t ne1, int64_t ne2, int64_t ne3) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_init_params params;
    struct ggml_context *ctx = NULL;
    struct ggml_tensor *tensor = NULL;
    ggml_backend_buffer_type_t buft = NULL;
    int64_t ne[4] = { ne0, ne1, ne2, ne3 };
    int64_t required = align_gpu_weight_metadata_bytes(1);
    size_t logical = 0;
    size_t alignment = 0;
    size_t alloc_size = 0;
    size_t padded = 0;
    void *storage = NULL;
    uintptr_t address = 0;
    uintptr_t modulus = 0;
    size_t padding = 0;
    int64_t result = ALIGN_GPU_ALLOCATION;
    if (state == NULL || state->backend == NULL || state->memory_planned || required <= 0
        || !align_gpu_weight_shape(type, n_dims, ne, &logical)) {
        return ALIGN_GPU_CONFIG;
    }
    storage = malloc((size_t) required);
    if (storage == NULL) {
        return ALIGN_GPU_ALLOCATION;
    }
    address = (uintptr_t) storage;
    modulus = address & (uintptr_t) (GGML_MEM_ALIGN - 1);
    padding = modulus == 0 ? 0 : GGML_MEM_ALIGN - modulus;
    if (padding >= (size_t) required) {
        goto done;
    }
    params.mem_size = (size_t) required - padding;
    params.mem_buffer = (unsigned char *) storage + padding;
    params.no_alloc = true;
    ctx = ggml_init(params);
    if (ctx == NULL) {
        goto done;
    }
    tensor = ggml_new_tensor(ctx, (enum ggml_type) type, n_dims, ne);
    buft = ggml_backend_get_default_buffer_type(state->backend);
    if (tensor == NULL || ggml_nbytes(tensor) != logical || buft == NULL) {
        goto done;
    }
    alignment = ggml_backend_buft_get_alignment(buft);
    alloc_size = ggml_backend_buft_get_alloc_size(buft, tensor);
    if (alignment == 0 || (alignment & (alignment - 1)) != 0
        || alloc_size > SIZE_MAX - (alignment - 1)) {
        goto done;
    }
    padded = (alloc_size + alignment - 1) & ~(alignment - 1);
    if (padded == 0 || padded > INT64_MAX) {
        goto done;
    }
    result = (int64_t) padded;
done:
    if (ctx != NULL) {
        ggml_free(ctx);
    }
    free(storage);
    return result;
}

int64_t align_gpu_weight_add(
        void *owner, int32_t type, int32_t n_dims,
        int64_t ne0, int64_t ne1, int64_t ne2, int64_t ne3) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = NULL;
    int64_t ne[4] = { ne0, ne1, ne2, ne3 };
    size_t nbytes = 0;
    size_t alloc_size = 0;
    size_t padded = 0;
    size_t alignment = 0;
    size_t used = 0;
    if (state == NULL || state->weights_expected <= 0 || state->weights_finished
        || state->weights_failed || state->weights_created != state->weights_uploaded
        || state->weights_created >= state->weights_expected
        || !align_gpu_weight_shape(type, n_dims, ne, &nbytes)) {
        return ALIGN_GPU_CONFIG;
    }
    used = ggml_used_mem(state->metadata_ctx);
    if (used > ggml_get_mem_size(state->metadata_ctx)
        || ggml_tensor_overhead() > ggml_get_mem_size(state->metadata_ctx) - used) {
        state->weights_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    tensor = ggml_new_tensor(state->metadata_ctx, (enum ggml_type) type, n_dims, ne);
    if (tensor == NULL || ggml_nbytes(tensor) != nbytes) {
        state->weights_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    alignment = state->weight_allocator.alignment;
    alloc_size = ggml_backend_buffer_get_alloc_size(state->weights_buffer, tensor);
    if (alignment == 0 || (alignment & (alignment - 1)) != 0
        || alloc_size > SIZE_MAX - (alignment - 1)) {
        state->weights_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    padded = (alloc_size + alignment - 1) & ~(alignment - 1);
    if (state->weight_allocator.offset > (size_t) state->weights_bytes
        || padded > (size_t) state->weights_bytes - state->weight_allocator.offset) {
        state->weights_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    if (ggml_tallocr_alloc(&state->weight_allocator, tensor) != GGML_STATUS_SUCCESS) {
        state->weights_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    state->pending_weight = tensor;
    state->weights_created += 1;
    return state->weights_created - 1;
}

int32_t align_gpu_weight_upload(
        void *owner, int64_t index, int64_t offset, const void *data, int64_t length) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    size_t logical = 0;
    size_t staging = 0;
    if (state == NULL || state->backend == NULL || state->pending_weight == NULL || data == NULL
        || offset < 0 || length <= 0 || index != state->weights_uploaded
        || index + 1 != state->weights_created) {
        return ALIGN_GPU_CONFIG;
    }
    logical = ggml_nbytes(state->pending_weight);
    staging = (size_t) state->staging_bytes;
    if ((size_t) offset != state->pending_weight_uploaded_bytes
        || (size_t) length > staging || state->pending_weight_uploaded_bytes > logical
        || (size_t) length > logical - state->pending_weight_uploaded_bytes) {
        return ALIGN_GPU_CONFIG;
    }
    memcpy(state->staging, data, (size_t) length);
    ggml_backend_tensor_set_async(
        state->backend, state->pending_weight, state->staging, (size_t) offset, (size_t) length);
    align_gpu_synchronize(state);
    state->pending_weight_uploaded_bytes += (size_t) length;
    state->weights_uploaded_bytes += length;
    if (state->pending_weight_uploaded_bytes == logical) {
        state->weights_uploaded += 1;
        state->pending_weight_uploaded_bytes = 0;
        state->pending_weight = NULL;
    }
    return ALIGN_GPU_OK;
}

static int align_gpu_payload_interval(uintptr_t data, size_t bytes, uintptr_t base,
                                      size_t capacity, size_t *end, int64_t *total) {
    size_t offset = 0;
    if (data == 0 || base == 0 || data < base || bytes == 0 || data - base > capacity) {
        return 0;
    }
    offset = (size_t) (data - base);
    if (offset < *end || bytes > capacity - offset || bytes > (uint64_t) (INT64_MAX - *total)) {
        return 0;
    }
    *end = offset + bytes;
    *total += (int64_t) bytes;
    return 1;
}

static int align_gpu_observe_payload(struct align_gpu_device_state *state) {
    int64_t seen = 0;
    int64_t count = 0;
    int64_t weights = 0;
    int64_t kv = 0;
    size_t weight_end = 0;
    size_t kv_end = 0;
    struct ggml_tensor *tensor = NULL;
    uintptr_t weight_base = 0;
    uintptr_t kv_base = 0;
    if (state == NULL || state->observation_failed) { return 0; }
    if (!state->weights_finished) { return 1; }
    if (!state->memory_allocated || state->weights_buffer == NULL || state->kv_buffer == NULL
        || state->weights_failed || state->kv_failed) { goto fail; }
    if (state->weights_expected <= 0 || state->kv_expected < 0
        || state->kv_expected > INT64_MAX - state->weights_expected) { goto fail; }
    count = state->weights_expected + (state->kv_finished ? state->kv_expected : 0);
    weight_base = (uintptr_t) ggml_backend_buffer_get_base(state->weights_buffer);
    kv_base = (uintptr_t) ggml_backend_buffer_get_base(state->kv_buffer);
    tensor = ggml_get_first_tensor(state->metadata_ctx);
    while (seen < count) {
        uintptr_t data = 0;
        size_t bytes = 0;
        if (tensor == NULL) { goto fail; }
        data = (uintptr_t) ggml_get_data(tensor);
        bytes = ggml_nbytes(tensor);
        if (seen < state->weights_expected) {
            if (!align_gpu_payload_interval(data, bytes, weight_base, (size_t) state->weights_bytes,
                                            &weight_end, &weights)) { goto fail; }
        } else if (!align_gpu_payload_interval(data, bytes, kv_base, (size_t) state->kv_bytes,
                                              &kv_end, &kv)) { goto fail; }
        seen += 1;
        tensor = ggml_get_next_tensor(state->metadata_ctx, tensor);
    }
    if (seen != count || weights <= 0 || (state->kv_finished && kv <= 0)
        || (state->observation_weight_payload != 0 && state->observation_weight_payload != weights)
        || (state->observation_kv_payload != 0 && state->observation_kv_payload != kv)) { goto fail; }
    state->observation_weight_payload = weights;
    state->observation_kv_payload = kv;
    return 1;
fail:
    state->observation_failed = 1;
    return 0;
}

int32_t align_gpu_weights_finish(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || state->weights_failed || state->weights_finished
        || state->weights_expected <= 0 || state->weights_created != state->weights_expected
        || state->weights_uploaded != state->weights_expected || state->pending_weight != NULL
        || state->pending_weight_uploaded_bytes != 0
        || state->weight_allocator.offset != (size_t) state->weights_bytes) {
        return ALIGN_GPU_CONFIG;
    }
    state->weights_finished = 1;
    return align_gpu_observe_payload(state) ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

int64_t align_gpu_weight_state(void *owner, int32_t field) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || state->weights_expected <= 0) {
        return -1;
    }
    switch (field) {
    case 0: return state->weights_expected;
    case 1: return state->weights_created;
    case 2: return state->weights_uploaded;
    case 3: return state->weights_uploaded_bytes;
    case 4: return state->weights_finished;
    default: return -1;
    }
}

int32_t align_gpu_kv_begin(void *owner, int64_t tensor_count) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    size_t used = 0;
    size_t overhead = ggml_tensor_overhead();
    if (state == NULL || !state->weights_finished || state->kv_expected != 0
        || tensor_count <= 0 || overhead == 0
        || (uint64_t) tensor_count > (uint64_t) SIZE_MAX / overhead) {
        return ALIGN_GPU_CONFIG;
    }
    used = ggml_used_mem(state->metadata_ctx);
    if (used > ggml_get_mem_size(state->metadata_ctx)
        || (size_t) tensor_count * overhead > ggml_get_mem_size(state->metadata_ctx) - used) {
        return ALIGN_GPU_MEMORY_BUDGET;
    }
    ggml_backend_buffer_clear(state->kv_buffer, 0);
    align_gpu_synchronize(state);
    state->kv_expected = tensor_count;
    return ALIGN_GPU_OK;
}

int64_t align_gpu_kv_add(
        void *owner, int32_t type, int32_t n_dims,
        int64_t ne0, int64_t ne1, int64_t ne2, int64_t ne3) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = NULL;
    int64_t ne[4] = { ne0, ne1, ne2, ne3 };
    size_t nbytes = 0;
    size_t alloc_size = 0;
    size_t padded = 0;
    size_t alignment = 0;
    size_t used = 0;
    if (state == NULL || state->kv_expected <= 0 || state->kv_finished || state->kv_failed
        || state->kv_created >= state->kv_expected
        || !align_gpu_weight_shape(type, n_dims, ne, &nbytes)) {
        return ALIGN_GPU_CONFIG;
    }
    used = ggml_used_mem(state->metadata_ctx);
    if (used > ggml_get_mem_size(state->metadata_ctx)
        || ggml_tensor_overhead() > ggml_get_mem_size(state->metadata_ctx) - used) {
        state->kv_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    tensor = ggml_new_tensor(state->metadata_ctx, (enum ggml_type) type, n_dims, ne);
    if (tensor == NULL || ggml_nbytes(tensor) != nbytes) {
        state->kv_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    alignment = state->kv_allocator.alignment;
    alloc_size = ggml_backend_buffer_get_alloc_size(state->kv_buffer, tensor);
    if (alignment == 0 || alloc_size > SIZE_MAX - (alignment - 1)) {
        state->kv_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    padded = (alloc_size + alignment - 1) & ~(alignment - 1);
    if (state->kv_allocator.offset > (size_t) state->kv_bytes
        || padded > (size_t) state->kv_bytes - state->kv_allocator.offset) {
        state->kv_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    if (ggml_tallocr_alloc(&state->kv_allocator, tensor) != GGML_STATUS_SUCCESS) {
        state->kv_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    state->kv_created += 1;
    return state->kv_created - 1;
}

int32_t align_gpu_kv_finish(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || state->kv_failed || state->kv_finished || state->kv_expected <= 0
        || state->kv_created != state->kv_expected
        || state->kv_allocator.offset != (size_t) state->kv_bytes) {
        return ALIGN_GPU_CONFIG;
    }
    state->kv_finished = 1;
    return align_gpu_observe_payload(state) ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

static struct ggml_tensor *align_gpu_kv_at(struct align_gpu_device_state *state, int64_t index) {
    struct ggml_tensor *tensor = NULL;
    int64_t at = 0;
    int64_t target = 0;
    if (state == NULL || !state->kv_finished || index < 0 || index >= state->kv_expected) {
        return NULL;
    }
    target = state->weights_expected + index;
    tensor = ggml_get_first_tensor(state->metadata_ctx);
    while (tensor != NULL && at < target) {
        tensor = ggml_get_next_tensor(state->metadata_ctx, tensor);
        at += 1;
    }
    return tensor;
}

int32_t align_gpu_kv_update(
        void *owner, int64_t index, int64_t offset, const void *data, int64_t length) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = align_gpu_kv_at(state, index);
    const unsigned char *source = (const unsigned char *) data;
    size_t at = 0;
    size_t staging = 0;
    size_t capacity = 0;
    if (tensor == NULL || data == NULL || offset < 0 || length <= 0) {
        return ALIGN_GPU_CONFIG;
    }
    if (state->kv_updated_bytes > INT64_MAX - length) {
        return ALIGN_GPU_CONFIG;
    }
    capacity = ggml_nbytes(tensor);
    if ((uint64_t) offset > capacity || (uint64_t) length > capacity - (size_t) offset) {
        return ALIGN_GPU_CONFIG;
    }
    staging = (size_t) state->staging_bytes;
    align_gpu_synchronize(state);
    while (at < (size_t) length) {
        size_t chunk = (size_t) length - at;
        if (chunk > staging) {
            chunk = staging;
        }
        memcpy(state->staging, source + at, chunk);
        ggml_backend_tensor_set_async(
            state->backend, tensor, state->staging, (size_t) offset + at, chunk);
        align_gpu_synchronize(state);
        at += chunk;
    }
    state->kv_updated_bytes += length;
    return ALIGN_GPU_OK;
}

int32_t align_gpu_kv_slot(void *owner, int64_t index, void *slots, int64_t out) {
    struct ggml_tensor *tensor = align_gpu_kv_at((struct align_gpu_device_state *) owner, index);
    if (tensor == NULL) {
        return ALIGN_GPU_CONFIG;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor) == ALIGN_GGML_OK
        ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

static int align_gpu_graph_kind_ok(int32_t kind) {
    return kind == ALIGN_GPU_GRAPH_PREFILL || kind == ALIGN_GPU_GRAPH_DECODE;
}

static struct ggml_context *align_gpu_graph_context_at(
        struct align_gpu_device_state *state, int32_t kind) {
    if (state == NULL || !align_gpu_graph_kind_ok(kind)) {
        return NULL;
    }
    return state->graph_contexts[kind];
}

/* Root tensor metadata is frozen once the first graph context opens.  Both request-local graph
 * contexts then occupy fixed, disjoint slices of the already admitted metadata allocation. */
void *align_gpu_graph_context_open(void *owner, int32_t kind, int64_t metadata_bytes) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_init_params params;
    struct ggml_context *ctx = NULL;
    size_t offset = 0;
    size_t span = 0;
    if (state == NULL || !state->inputs_finished || state->workspace_failed
        || !align_gpu_graph_kind_ok(kind) || metadata_bytes <= 0
        || (uint64_t) metadata_bytes > SIZE_MAX || state->graph_contexts[kind] != NULL) {
        return NULL;
    }
    if (state->graph_metadata_offset == 0) {
        size_t used = ggml_used_mem(state->metadata_ctx);
        if (used > SIZE_MAX - (GGML_MEM_ALIGN - 1)) {
            return NULL;
        }
        state->graph_metadata_offset = (used + GGML_MEM_ALIGN - 1)
            & ~(size_t) (GGML_MEM_ALIGN - 1);
    }
    offset = state->graph_metadata_offset;
    if ((size_t) metadata_bytes > SIZE_MAX - (GGML_MEM_ALIGN - 1)) {
        return NULL;
    }
    span = ((size_t) metadata_bytes + GGML_MEM_ALIGN - 1)
        & ~(size_t) (GGML_MEM_ALIGN - 1);
    if (offset > state->metadata_capacity || span > state->metadata_capacity - offset) {
        return NULL;
    }
    params.mem_size = (size_t) metadata_bytes;
    params.mem_buffer = state->metadata_base + offset;
    params.no_alloc = true;
    ctx = ggml_init(params);
    if (ctx == NULL) {
        return NULL;
    }
    state->graph_contexts[kind] = ctx;
    state->graph_context_bytes[kind] = span;
    state->graph_metadata_offset += span;
    return (void *) ctx;
}

/* A maximum-context KV tensor keeps its allocation and native strides for the whole request.  K
 * stores sequence on dimension 1; V stores it on dimension 0, matching the two attention
 * operands.  A graph receives only the currently valid prefix.  Deriving the selected extent here
 * prevents the language caller from manufacturing a byte offset into device storage. */
int32_t align_gpu_kv_prefix_slot(
        void *owner, int64_t index, int32_t kind, int32_t layout, int64_t valid_width,
        void *slots, int64_t out) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = align_gpu_kv_at(state, index);
    struct ggml_tensor *view = NULL;
    struct ggml_context *ctx = align_gpu_graph_context_at(state, kind);
    int sequence_dim = layout == 0 ? 1 : 0;
    if (state == NULL || tensor == NULL || ctx == NULL || state->graph_prepared[kind]
        || (layout != 0 && layout != 1) || valid_width <= 0
        || valid_width > tensor->ne[sequence_dim] || tensor->type != GGML_TYPE_F32) {
        return ALIGN_GPU_CONFIG;
    }
    view = ggml_view_4d(ctx, tensor,
                        layout == 0 ? tensor->ne[0] : valid_width,
                        layout == 0 ? valid_width : tensor->ne[1],
                        tensor->ne[2], tensor->ne[3],
                        tensor->nb[1], tensor->nb[2], tensor->nb[3], 0);
    if (view == NULL) {
        return ALIGN_GPU_ALLOCATION;
    }
    return align_ggml_slot_store(slots, out, (void *) view) == ALIGN_GGML_OK
        ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

/* Store one graph-produced K or V range directly into the request's resident plane.  The caller
 * supplies a layout and logical starting position, never a byte offset; the selected sequence
 * axis and plane's native strides define the destination view.  Returning the `ggml_cpy` node lets
 * the graph register the write before any later prefix consumer without a host readback. */
int32_t align_gpu_kv_write_slot(
        void *owner, int64_t index, int32_t kind, int32_t layout, int64_t position,
        void *slots, int64_t out, int64_t source) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = align_gpu_kv_at(state, index);
    struct ggml_tensor *src = (struct ggml_tensor *) align_ggml_slot_load(slots, source);
    struct ggml_tensor *view = NULL;
    struct ggml_tensor *result = NULL;
    struct ggml_context *ctx = align_gpu_graph_context_at(state, kind);
    int sequence_dim = layout == 0 ? 1 : 0;
    int dim = 0;
    size_t offset = 0;
    if (state == NULL || tensor == NULL || src == NULL || ctx == NULL
        || state->graph_prepared[kind] || (layout != 0 && layout != 1) || position < 0
        || tensor->type != GGML_TYPE_F32 || src->type != tensor->type
        || src->ne[sequence_dim] <= 0
        || position > tensor->ne[sequence_dim]
        || src->ne[sequence_dim] > tensor->ne[sequence_dim] - position) {
        return ALIGN_GPU_CONFIG;
    }
    for (dim = 0; dim < 4; ++dim) {
        if (dim != sequence_dim && src->ne[dim] != tensor->ne[dim]) {
            return ALIGN_GPU_CONFIG;
        }
    }
    if ((uint64_t) position > (uint64_t) SIZE_MAX / tensor->nb[sequence_dim]) {
        return ALIGN_GPU_CONFIG;
    }
    offset = (size_t) position * tensor->nb[sequence_dim];
    view = ggml_view_4d(ctx, tensor,
                        src->ne[0], src->ne[1], src->ne[2], src->ne[3],
                        tensor->nb[1], tensor->nb[2], tensor->nb[3], offset);
    if (view == NULL) {
        return ALIGN_GPU_ALLOCATION;
    }
    result = ggml_cpy(ctx, src, view);
    if (result == NULL) {
        return ALIGN_GPU_ALLOCATION;
    }
    return align_ggml_slot_store(slots, out, (void *) result) == ALIGN_GGML_OK
        ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

int64_t align_gpu_kv_state(void *owner, int32_t field) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || state->kv_expected <= 0) {
        return -1;
    }
    switch (field) {
    case 0: return state->kv_expected;
    case 1: return state->kv_created;
    case 2: return state->kv_updated_bytes;
    case 3: return state->kv_finished;
    default: return -1;
    }
}

int32_t align_gpu_inputs_begin(void *owner, int64_t tensor_count) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    size_t used = 0;
    size_t overhead = ggml_tensor_overhead();
    if (state == NULL || !state->kv_finished || state->inputs_expected != 0
        || tensor_count <= 0 || overhead == 0
        || (uint64_t) tensor_count > (uint64_t) SIZE_MAX / overhead) {
        return ALIGN_GPU_CONFIG;
    }
    used = ggml_used_mem(state->metadata_ctx);
    if (used > ggml_get_mem_size(state->metadata_ctx)
        || (size_t) tensor_count * overhead > ggml_get_mem_size(state->metadata_ctx) - used) {
        return ALIGN_GPU_MEMORY_BUDGET;
    }
    state->inputs_expected = tensor_count;
    return ALIGN_GPU_OK;
}

static int align_gpu_input_shape(
        int32_t type, int32_t n_dims, const int64_t ne[4], size_t *nbytes) {
    size_t total = sizeof(float);
    int dim = 0;
    if ((type != GGML_TYPE_F32 && type != GGML_TYPE_I32)
        || n_dims < 1 || n_dims > 4 || nbytes == NULL) {
        return 0;
    }
    for (dim = 0; dim < 4; ++dim) {
        if ((dim < n_dims && ne[dim] <= 0) || (dim >= n_dims && ne[dim] != 1)) {
            return 0;
        }
        if (dim < n_dims) {
            if ((uint64_t) ne[dim] > (uint64_t) SIZE_MAX / total) {
                return 0;
            }
            total *= (size_t) ne[dim];
        }
    }
    if (total == 0 || total > INT64_MAX) {
        return 0;
    }
    *nbytes = total;
    return 1;
}

int64_t align_gpu_input_add(
        void *owner, int32_t type, int32_t n_dims,
        int64_t ne0, int64_t ne1, int64_t ne2, int64_t ne3) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = NULL;
    int64_t ne[4] = { ne0, ne1, ne2, ne3 };
    size_t nbytes = 0;
    size_t alloc_size = 0;
    size_t padded = 0;
    size_t alignment = 0;
    size_t used = 0;
    if (state == NULL || state->inputs_expected <= 0 || state->inputs_finished
        || state->inputs_failed || state->inputs_created >= state->inputs_expected
        || !align_gpu_input_shape(type, n_dims, ne, &nbytes)) {
        return ALIGN_GPU_CONFIG;
    }
    used = ggml_used_mem(state->metadata_ctx);
    if (used > ggml_get_mem_size(state->metadata_ctx)
        || ggml_tensor_overhead() > ggml_get_mem_size(state->metadata_ctx) - used) {
        state->inputs_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    tensor = ggml_new_tensor(state->metadata_ctx, (enum ggml_type) type, n_dims, ne);
    if (tensor == NULL || ggml_nbytes(tensor) != nbytes) {
        state->inputs_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    ggml_backend_buffer_type_t buft = ggml_backend_get_default_buffer_type(state->backend);
    if (buft == NULL) {
        state->inputs_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    alignment = ggml_backend_buft_get_alignment(buft);
    alloc_size = ggml_backend_buft_get_alloc_size(buft, tensor);
    if (alignment == 0 || (alignment & (alignment - 1)) != 0
        || alloc_size > SIZE_MAX - (alignment - 1)) {
        state->inputs_failed = 1;
        return ALIGN_GPU_ALLOCATION;
    }
    padded = (alloc_size + alignment - 1) & ~(alignment - 1);
    if (state->input_offset > (size_t) state->workspace_bytes
        || padded > (size_t) state->workspace_bytes - state->input_offset) {
        state->inputs_failed = 1;
        return ALIGN_GPU_MEMORY_BUDGET;
    }
    state->input_offset += padded;
    state->inputs_created += 1;
    return state->inputs_created - 1;
}

int32_t align_gpu_inputs_finish(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = NULL;
    ggml_backend_buffer_type_t buft = NULL;
    void *base = NULL;
    size_t alignment = 0;
    int64_t index = 0;
    if (state == NULL || state->inputs_failed || state->inputs_finished
        || state->inputs_expected <= 0 || state->inputs_created != state->inputs_expected
        || state->input_offset == 0 || state->input_offset >= (size_t) state->workspace_bytes
        || !state->memory_allocated || state->input_buffer != NULL) {
        return ALIGN_GPU_CONFIG;
    }
    buft = ggml_backend_get_default_buffer_type(state->backend);
    align_gpu_synchronize(state);
    if (buft == NULL) {
        goto fail;
    }
    if (ALIGN_GPU_FORCE_ALLOCATION_PREFIX != 6) {
        state->input_buffer = ggml_backend_buft_alloc_buffer(buft, state->input_offset);
    }
    if (state->input_buffer == NULL
        || ggml_backend_buffer_get_size(state->input_buffer) != state->input_offset) {
        goto fail;
    }
    base = ggml_backend_buffer_get_base(state->input_buffer);
    alignment = ggml_backend_buffer_get_alignment(state->input_buffer);
    if (base == NULL || alignment == 0 || (alignment & (alignment - 1)) != 0
        || ((uintptr_t) base & (uintptr_t) (alignment - 1)) != 0) {
        goto fail;
    }
    state->input_allocator.buffer = state->input_buffer;
    state->input_allocator.base = base;
    state->input_allocator.alignment = alignment;
    state->input_allocator.offset = 0;
    tensor = ggml_get_first_tensor(state->metadata_ctx);
    for (index = 0; index < state->weights_expected + state->kv_expected; ++index) {
        if (tensor == NULL) {
            goto fail;
        }
        tensor = ggml_get_next_tensor(state->metadata_ctx, tensor);
    }
    for (index = 0; index < state->inputs_expected; ++index) {
        if (tensor == NULL
            || ggml_tallocr_alloc(&state->input_allocator, tensor) != GGML_STATUS_SUCCESS) {
            goto fail;
        }
        tensor = ggml_get_next_tensor(state->metadata_ctx, tensor);
    }
    if (state->input_allocator.offset != state->input_offset) {
        goto fail;
    }
    state->inputs_finished = 1;
    align_gpu_observe_memory(state);
    return ALIGN_GPU_OK;

fail:
    state->inputs_failed = 1;
    return ALIGN_GPU_ALLOCATION;
}

static struct ggml_tensor *align_gpu_input_at(
        struct align_gpu_device_state *state, int64_t index) {
    struct ggml_tensor *tensor = NULL;
    int64_t at = 0;
    int64_t target = 0;
    if (state == NULL || !state->inputs_finished || index < 0
        || index >= state->inputs_expected) {
        return NULL;
    }
    target = state->weights_expected + state->kv_expected + index;
    tensor = ggml_get_first_tensor(state->metadata_ctx);
    while (tensor != NULL && at < target) {
        tensor = ggml_get_next_tensor(state->metadata_ctx, tensor);
        at += 1;
    }
    return tensor;
}

int32_t align_gpu_input_slot(void *owner, int64_t index, void *slots, int64_t out) {
    struct ggml_tensor *tensor =
        align_gpu_input_at((struct align_gpu_device_state *) owner, index);
    if (tensor == NULL) {
        return ALIGN_GPU_CONFIG;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor) == ALIGN_GGML_OK
        ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

/* Attention masks are allocated once at their request capacity and prefill width.  Updates pack
 * each live rectangle densely at offset zero, so the graph view must use the live row stride too.
 * Keeping the allocation stride here makes every prefix except full capacity non-contiguous, and
 * current ggml deliberately asserts rather than returning an error for such soft-max masks. */
int32_t align_gpu_mask_prefix_slot(
        void *owner, int64_t index, int32_t kind, int64_t valid_width, int64_t query_width,
        void *slots, int64_t out) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = align_gpu_input_at(state, index);
    struct ggml_tensor *view = NULL;
    struct ggml_context *ctx = align_gpu_graph_context_at(state, kind);
    if (state == NULL || tensor == NULL || ctx == NULL || state->graph_prepared[kind]
        || valid_width <= 0 || (uint64_t) valid_width > SIZE_MAX / sizeof(float)
        || query_width <= 0 || valid_width > tensor->ne[0] || query_width > tensor->ne[1]
        || tensor->ne[2] != 1 || tensor->ne[3] != 1 || tensor->type != GGML_TYPE_F32) {
        return ALIGN_GPU_CONFIG;
    }
    view = ggml_view_2d(ctx, tensor, valid_width, query_width,
                        (size_t) valid_width * sizeof(float), 0);
    if (view == NULL) {
        return ALIGN_GPU_ALLOCATION;
    }
    return align_ggml_slot_store(slots, out, (void *) view) == ALIGN_GGML_OK
        ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

int32_t align_gpu_input_update(
        void *owner, int64_t index, int64_t offset, const void *data, int64_t length) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = align_gpu_input_at(state, index);
    const unsigned char *source = (const unsigned char *) data;
    size_t at = 0;
    size_t staging = 0;
    size_t capacity = 0;
    if (state == NULL || tensor == NULL || !state->workspace_prepared || data == NULL
        || offset < 0 || length <= 0 || state->input_updated_bytes > INT64_MAX - length) {
        return ALIGN_GPU_CONFIG;
    }
    capacity = ggml_nbytes(tensor);
    if (tensor->data == NULL || (uint64_t) offset > capacity
        || (uint64_t) length > capacity - (size_t) offset) {
        return ALIGN_GPU_CONFIG;
    }
    staging = (size_t) state->staging_bytes;
    align_gpu_synchronize(state);
    while (at < (size_t) length) {
        size_t chunk = (size_t) length - at;
        if (chunk > staging) {
            chunk = staging;
        }
        memcpy(state->staging, source + at, chunk);
        ggml_backend_tensor_set_async(
            state->backend, tensor, state->staging, (size_t) offset + at, chunk);
        align_gpu_synchronize(state);
        at += chunk;
    }
    state->input_updated_bytes += length;
    return ALIGN_GPU_OK;
}

int64_t align_gpu_input_state(void *owner, int32_t field) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || state->inputs_expected <= 0) {
        return -1;
    }
    switch (field) {
    case 0: return state->inputs_expected;
    case 1: return state->inputs_created;
    case 2: return state->input_updated_bytes;
    case 3: return state->inputs_finished;
    default: return -1;
    }
}

static struct ggml_tensor *align_gpu_weight_at(
        struct align_gpu_device_state *state, int64_t index) {
    struct ggml_tensor *tensor = NULL;
    int64_t at = 0;
    if (state == NULL || !state->weights_finished || index < 0
        || index >= state->weights_expected) {
        return NULL;
    }
    tensor = ggml_get_first_tensor(state->metadata_ctx);
    while (tensor != NULL && at < index) {
        tensor = ggml_get_next_tensor(state->metadata_ctx, tensor);
        at += 1;
    }
    return tensor;
}

int32_t align_gpu_weight_slot(void *owner, int64_t index, void *slots, int64_t out) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = align_gpu_weight_at(state, index);
    if (tensor == NULL) {
        return ALIGN_GPU_CONFIG;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor) == ALIGN_GGML_OK
        ? ALIGN_GPU_OK : ALIGN_GPU_CONFIG;
}

static int align_gpu_topology_key_ok(const void *key, int64_t length) {
    const unsigned char *bytes = (const unsigned char *) key;
    int64_t index = 0;
    if (bytes == NULL || length != 64) {
        return 0;
    }
    for (index = 0; index < length; ++index) {
        if (!((bytes[index] >= '0' && bytes[index] <= '9')
              || (bytes[index] >= 'a' && bytes[index] <= 'f'))) {
            return 0;
        }
    }
    return 1;
}

static int align_gpu_graph_required(
        ggml_backend_buffer_type_t buft, struct ggml_cgraph *graph, size_t *required) {
    ggml_gallocr_t measure = NULL;
    if (buft == NULL || graph == NULL || required == NULL) {
        return 0;
    }
    measure = ggml_gallocr_new(buft);
    if (measure == NULL) {
        return 0;
    }
    *required = 0;
    ggml_gallocr_reserve_n_size(measure, graph, NULL, NULL, required);
    ggml_gallocr_free(measure);
    return *required > 0;
}

static void align_gpu_workspace_tensor_reset(
        struct align_gpu_device_state *state, struct ggml_tensor *tensor) {
    if (state == NULL || tensor == NULL || tensor->buffer == NULL
        || tensor->buffer == state->weights_buffer || tensor->buffer == state->kv_buffer
        || tensor->buffer == state->input_buffer) {
        return;
    }
    tensor->buffer = NULL;
    tensor->data = NULL;
    tensor->extra = NULL;
}

static void align_gpu_workspace_context_reset(
        struct align_gpu_device_state *state, struct ggml_context *ctx) {
    struct ggml_tensor *tensor = NULL;
    if (state == NULL || ctx == NULL) {
        return;
    }
    tensor = ggml_get_first_tensor(ctx);
    while (tensor != NULL) {
        align_gpu_workspace_tensor_reset(state, tensor);
        tensor = ggml_get_next_tensor(ctx, tensor);
    }
}

/* The two graphs execute serially and share one reservation sized for the larger live topology.
 * Rebuilding either slot first drains and discards the previous allocator, then assigns both live
 * graphs again so no tensor retains a pointer into released workspace. */
static int32_t align_gpu_workspace_rebuild(struct align_gpu_device_state *state) {
    ggml_backend_buffer_type_t buft = NULL;
    struct ggml_cgraph *largest = NULL;
    size_t largest_bytes = 0;
    int kind = 0;
    if (state == NULL || state->input_buffer == NULL) {
        return ALIGN_GPU_CONFIG;
    }
    align_gpu_synchronize(state);
    for (kind = 0; kind < ALIGN_GPU_GRAPH_KINDS; ++kind) {
        if (state->graph_prepared[kind]) {
            align_gpu_workspace_context_reset(state, state->graph_contexts[kind]);
        }
    }
    if (state->workspace_allocator != NULL) {
        ggml_gallocr_free(state->workspace_allocator);
        state->workspace_allocator = NULL;
    }
    state->workspace_prepared = 0;
    buft = ggml_backend_get_default_buffer_type(state->backend);
    if (buft == NULL) {
        return ALIGN_GPU_ALLOCATION;
    }
    for (kind = 0; kind < ALIGN_GPU_GRAPH_KINDS; ++kind) {
        size_t required = 0;
        if (!state->graph_prepared[kind]) {
            continue;
        }
        if (!align_gpu_graph_required(buft, state->workspace_graphs[kind], &required)) {
            return ALIGN_GPU_ALLOCATION;
        }
        if (required > largest_bytes) {
            largest = state->workspace_graphs[kind];
            largest_bytes = required;
        }
    }
    if (largest == NULL) {
        return ALIGN_GPU_OK;
    }
    if (state->input_offset >= (size_t) state->workspace_bytes
        || largest_bytes > (size_t) state->workspace_bytes - state->input_offset) {
        return ALIGN_GPU_MEMORY_BUDGET;
    }
    if (ALIGN_GPU_FORCE_ALLOCATION_PREFIX == 5) { return ALIGN_GPU_ALLOCATION; }
    state->workspace_allocator = ggml_gallocr_new(buft);
    if (state->workspace_allocator == NULL
        || !ggml_gallocr_reserve(state->workspace_allocator, largest)) {
        return ALIGN_GPU_ALLOCATION;
    }
    for (kind = 0; kind < ALIGN_GPU_GRAPH_KINDS; ++kind) {
        if (state->graph_prepared[kind]
            && !ggml_gallocr_alloc_graph(
                state->workspace_allocator, state->workspace_graphs[kind])) {
            return ALIGN_GPU_ALLOCATION;
        }
    }
    if (ggml_gallocr_get_buffer_size(state->workspace_allocator, 0) > largest_bytes
        || largest_bytes > (size_t) state->workspace_bytes - state->input_offset) {
        return ALIGN_GPU_MEMORY_BUDGET;
    }
    state->workspace_prepared = 1;
    align_gpu_observe_memory(state);
    return ALIGN_GPU_OK;
}

int32_t align_gpu_graph_prepare(
        void *owner, int32_t kind, const void *key, int64_t key_length, void *graph) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    int32_t status = ALIGN_GPU_OK;
    if (state == NULL || graph == NULL || !state->weights_finished || !state->kv_finished
        || !state->inputs_finished || state->workspace_failed
        || state->input_buffer == NULL || !align_gpu_graph_kind_ok(kind)
        || state->graph_contexts[kind] == NULL || state->graph_prepared[kind]
        || !align_gpu_topology_key_ok(key, key_length)
        || state->graph_prepare_count[kind] == INT64_MAX) {
        return ALIGN_GPU_CONFIG;
    }
    if (!align_gpu_observe_payload(state)) { return ALIGN_GPU_CONFIG; }
    state->workspace_graphs[kind] = (struct ggml_cgraph *) graph;
    memcpy(state->graph_keys[kind], key, 64);
    state->graph_keys[kind][64] = '\0';
    state->graph_prepared[kind] = 1;
    status = align_gpu_workspace_rebuild(state);
    if (status != ALIGN_GPU_OK) {
        state->workspace_failed = 1;
        return status;
    }
    state->graph_prepare_count[kind] += 1;
    state->graph_current_execution_count[kind] = 0;
    return ALIGN_GPU_OK;
}

int32_t align_gpu_graph_invalidate(void *owner, int32_t kind) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    int32_t status = ALIGN_GPU_OK;
    if (state == NULL || !align_gpu_graph_kind_ok(kind) || !state->graph_prepared[kind]
        || state->workspace_failed || state->graph_invalidation_count[kind] == INT64_MAX) {
        return ALIGN_GPU_CONFIG;
    }
    if (!align_gpu_observe_payload(state)) { return ALIGN_GPU_CONFIG; }
    align_gpu_synchronize(state);
    state->graph_prepared[kind] = 0;
    state->workspace_graphs[kind] = NULL;
    state->graph_keys[kind][0] = '\0';
    state->graph_current_execution_count[kind] = 0;
    status = align_gpu_workspace_rebuild(state);
    if (status != ALIGN_GPU_OK) {
        state->workspace_failed = 1;
        return status;
    }
    ggml_reset(state->graph_contexts[kind]);
    state->graph_invalidation_count[kind] += 1;
    return ALIGN_GPU_OK;
}

static int align_gpu_count_model_node(struct align_gpu_device_state *state,
                                      struct ggml_tensor *tensor,
                                      int64_t *operations, int64_t *layers, int64_t *experts) {
    struct ggml_tensor *weight = NULL;
    int64_t ordinal = 0;
    if (tensor->op == GGML_OP_NONE || tensor->op == GGML_OP_VIEW || tensor->op == GGML_OP_RESHAPE
        || tensor->op == GGML_OP_PERMUTE || tensor->op == GGML_OP_CPY) { return 1; }
    if (*operations == INT64_MAX) { return 0; }
    *operations += 1;
    if (tensor->op != GGML_OP_MUL_MAT && tensor->op != GGML_OP_MUL_MAT_ID) { return 1; }
    if (state->weights_expected < 15 || (state->weights_expected - 3) % 12 != 0) { return 1; }
    weight = ggml_get_first_tensor(state->metadata_ctx);
    while (weight != NULL && ordinal < state->weights_expected) {
        if (ordinal > 0 && ordinal % 12 == 0 && tensor->src[0] == weight) {
            int64_t invoked = 0;
            if (*layers == INT64_MAX) { return 0; }
            *layers += 1;
            if (tensor->op == GGML_OP_MUL_MAT_ID) {
                if (tensor->ne[1] <= 0 || tensor->ne[2] <= 0
                    || tensor->ne[1] > INT64_MAX / tensor->ne[2]) { return 0; }
                invoked = tensor->ne[1] * tensor->ne[2];
                if (*experts > INT64_MAX - invoked) { return 0; }
                *experts += invoked;
            }
            return 1;
        }
        weight = ggml_get_next_tensor(state->metadata_ctx, weight);
        ordinal += 1;
    }
    return 1;
}

int32_t align_gpu_graph_compute(
        void *owner, int32_t kind, const void *key, int64_t key_length, void *graph) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    enum ggml_status status = GGML_STATUS_FAILED;
    int64_t observed_nodes = 0;
    int64_t observed_ops = 0;
    int64_t observed_layers = 0;
    int64_t observed_experts = 0;
    int node = 0;
    if (state == NULL || graph == NULL || !align_gpu_graph_kind_ok(kind)
        || !state->workspace_prepared || state->workspace_failed || !state->graph_prepared[kind]
        || state->workspace_graphs[kind] != (struct ggml_cgraph *) graph
        || !align_gpu_topology_key_ok(key, key_length)
        || memcmp(state->graph_keys[kind], key, 64) != 0) {
        return ALIGN_GPU_CONFIG;
    }
    if (!align_gpu_observe_payload(state)) { return ALIGN_GPU_CONFIG; }
    if (state->graph_execution_count[kind] == INT64_MAX
        || (state->graph_current_execution_count[kind] > 0
            && state->graph_reuse_count[kind] == INT64_MAX)) {
        return ALIGN_GPU_CONFIG;
    }
    for (node = 0; node < ggml_graph_n_nodes((struct ggml_cgraph *) graph); node++) {
        if (ggml_graph_node((struct ggml_cgraph *) graph, node)->op != GGML_OP_NONE) {
            observed_nodes += 1;
        }
        if (!align_gpu_count_model_node(state, ggml_graph_node((struct ggml_cgraph *) graph, node),
                                         &observed_ops, &observed_layers, &observed_experts)) {
            state->observation_failed = 1;
            return ALIGN_GPU_CONFIG;
        }
    }
    if (state->observation_failed || state->observation_nodes > INT64_MAX - observed_nodes
        || state->observation_model_ops > INT64_MAX - observed_ops
        || state->observation_layers > INT64_MAX - observed_layers
        || state->observation_experts > INT64_MAX - observed_experts) {
        state->observation_failed = 1;
        return ALIGN_GPU_CONFIG;
    }
    status = ggml_backend_graph_compute(state->backend, state->workspace_graphs[kind]);
    if (status != GGML_STATUS_SUCCESS) {
        state->workspace_failed = 1;
        return ALIGN_GPU_COMPUTE;
    }
    if (!align_gpu_observe_payload(state)) { return ALIGN_GPU_CONFIG; }
    if (state->graph_current_execution_count[kind] > 0) {
        state->graph_reuse_count[kind] += 1;
    }
    state->observation_nodes += observed_nodes;
    state->observation_model_ops += observed_ops;
    state->observation_layers += observed_layers;
    state->observation_experts += observed_experts;
    state->graph_current_execution_count[kind] += 1;
    state->graph_execution_count[kind] += 1;
    return ALIGN_GPU_OK;
}

int64_t align_gpu_observation_state(void *owner, int32_t field) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (field < 0 || field > 10 || !align_gpu_observe_payload(state)) { return -1; }
    switch (field) {
    case 0: return state->observation_nodes;
    case 1: return state->observation_read_bytes;
    case 2: return state->observation_read_calls;
    case 3: return state->observation_sync_calls;
    case 4: return state->observation_host_peak;
    case 5: return state->observation_device_peak;
    case 6: return state->observation_weight_payload;
    case 7: return state->observation_kv_payload;
    case 8: return state->observation_model_ops;
    case 9: return state->observation_layers;
    case 10: return state->observation_experts;
    default: return -1;
    }
}

int64_t align_gpu_graph_state(void *owner, int32_t kind, int32_t field) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL || !align_gpu_graph_kind_ok(kind) || state->graph_contexts[kind] == NULL) {
        return -1;
    }
    switch (field) {
    case 0: return state->graph_prepare_count[kind];
    case 1: return state->graph_execution_count[kind];
    case 2: return state->graph_reuse_count[kind];
    case 3: return state->graph_invalidation_count[kind];
    default: return -1;
    }
}

void align_gpu_device_close(void *owner) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    if (state == NULL) {
        return;
    }
    if (state->backend != NULL) {
        align_gpu_synchronize(state);
    }
    align_gpu_memory_release(state);
    if (state->backend != NULL) {
        ggml_backend_free(state->backend);
        state->backend = NULL;
    }
    state->device = NULL;
    free(state);
    atomic_store(&align_gpu_busy, 0);
}

static ggml_backend_dev_t align_ggml_cpu_device(void) {
    return (ggml_backend_dev_t) align_ggml_device_by_kind(ALIGN_GGML_DEVICE_CPU);
}

/* R5C section 3.4. One numeric device property, selected by field id. `ALIGN_GGML_DEV_ALIGNMENT`
 * comes from the device's **own** buffer type rather than from the CPU's, which is section 3.9
 * step 21's whole change: the arm validates the alignment of the device it is about to hand the
 * window to.
 */
int64_t align_ggml_device_props(void *device, int32_t field) {
    struct ggml_backend_dev_props props;
    if (device == NULL) {
        return ALIGN_GGML_UNAVAILABLE;
    }
    if (field == ALIGN_GGML_DEV_ALIGNMENT) {
        ggml_backend_buffer_type_t buft =
            ggml_backend_dev_buffer_type((ggml_backend_dev_t) device);
        size_t alignment = 0;
        if (buft == NULL) {
            return ALIGN_GGML_ABI;
        }
        alignment = ggml_backend_buft_get_alignment(buft);
        if (alignment == 0 || alignment > (size_t) 65536) {
            return ALIGN_GGML_ABI;
        }
        return (int64_t) alignment;
    }
    memset(&props, 0, sizeof(props));
    ggml_backend_dev_get_props((ggml_backend_dev_t) device, &props);
    switch (field) {
    case ALIGN_GGML_DEV_TYPE_ID:
        return (int64_t) props.type;
    case ALIGN_GGML_DEV_HOST_PTR:
#ifdef ALIGN_GGML_FORCE_NO_HOST_PTR
        /* Section 4.5: a device that does not advertise `buffer_from_host_ptr` is a condition no
         * input can produce on a host whose only devices do. The macro is never defined in an
         * ordinary build. */
        return 0;
#else
        return props.caps.buffer_from_host_ptr ? 1 : 0;
#endif
    case ALIGN_GGML_DEV_HOST_BUFFER:
        return props.caps.host_buffer ? 1 : 0;
    case ALIGN_GGML_DEV_MEMORY_FREE:
        return align_ggml_clamp_size(props.memory_free);
    case ALIGN_GGML_DEV_MEMORY_TOTAL:
        return align_ggml_clamp_size(props.memory_total);
    default:
        break;
    }
    return ALIGN_GGML_ABI;
}

/* R5C section 3.5's one new bound, and section 2.6 is why it is a *pre*-check rather than a null
 * check on the wrap: `ggml_backend_dev_buffer_from_host_ptr` on Metal logs a failure and then
 * segfaults for an oversize length, so nothing downstream can observe the refusal.
 */
int64_t align_ggml_device_buft_max_size(void *device) {
    if (device == NULL) {
        return ALIGN_GGML_UNAVAILABLE;
    }
#ifdef ALIGN_GGML_FORCE_MAX_BUFFER_SIZE
    /* Section 4.3's `gf-device-limit` cell: a device whose maximum buffer length the computed
     * window exceeds. No real device here has one small enough, so the qualification and the owner
     * both reach the check through this macro. */
    return (int64_t) (ALIGN_GGML_FORCE_MAX_BUFFER_SIZE);
#else
    {
        ggml_backend_buffer_type_t buft =
            ggml_backend_dev_buffer_type((ggml_backend_dev_t) device);
        size_t max_size = 0;
        if (buft == NULL) {
            return ALIGN_GGML_ABI;
        }
        max_size = ggml_backend_buft_get_max_size(buft);
        if (max_size == 0) {
            return ALIGN_GGML_ABI;
        }
        return align_ggml_clamp_size(max_size);
    }
#endif
}

/* The device's name and description, copied into caller memory exactly as the backend's name is.
 * Returns the copied length, never NUL-terminates, and never writes more than `cap`.
 */
int32_t align_ggml_device_text(void *device, int32_t which, void *out, int32_t cap) {
    const char *text = NULL;
    size_t length = 0;
    if (device == NULL || out == NULL || cap <= 0) {
        return 0;
    }
    if (which == ALIGN_GGML_DEV_TEXT_NAME) {
        text = ggml_backend_dev_name((ggml_backend_dev_t) device);
    } else if (which == ALIGN_GGML_DEV_TEXT_DESCRIPTION) {
        text = ggml_backend_dev_description((ggml_backend_dev_t) device);
    } else if (which == ALIGN_GGML_DEV_TEXT_ID) {
        struct ggml_backend_dev_props props;
        memset(&props, 0, sizeof(props));
        ggml_backend_dev_get_props((ggml_backend_dev_t) device, &props);
        text = props.device_id;
    }
    if (text == NULL) {
        return 0;
    }
    length = strlen(text);
    if (length > (size_t) cap) {
        length = (size_t) cap;
    }
    memcpy(out, text, length);
    return (int32_t) length;
}

/* The alignment ggml will assert on, asked of the linked library rather than assumed.
 * Non-positive means the CPU device is absent, which the caller reports as `R4_5_GGML_UNAVAILABLE`
 * at section 3.8 step 10 or as `R4_5_ABI` at step 11.
 */
int32_t align_ggml_tensor_alignment(void) {
    ggml_backend_dev_t dev = align_ggml_cpu_device();
    ggml_backend_buffer_type_t buft = NULL;
    size_t alignment = 0;
    if (dev == NULL) {
        return ALIGN_GGML_UNAVAILABLE;
    }
    buft = ggml_backend_dev_buffer_type(dev);
    if (buft == NULL) {
        return ALIGN_GGML_ABI;
    }
    alignment = ggml_backend_buft_get_alignment(buft);
    if (alignment == 0 || alignment > (size_t) 65536) {
        return ALIGN_GGML_ABI;
    }
    return (int32_t) alignment;
}

int32_t align_ggml_blck_size(int32_t type) {
    int64_t blck = 0;
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    blck = ggml_blck_size((enum ggml_type) type);
    if (blck <= 0 || blck > (int64_t) 65536) {
        return ALIGN_GGML_ABI;
    }
    return (int32_t) blck;
}

int32_t align_ggml_type_size(int32_t type) {
    size_t size = 0;
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    size = ggml_type_size((enum ggml_type) type);
    if (size == 0 || size > (size_t) 65536) {
        return ALIGN_GGML_ABI;
    }
    return (int32_t) size;
}

/* The section 5.6 ABI-drift guard, widened from section 3.4's three Q4_K constants to every row of
 * the checked-in table (section 6, correction C2). Returns the first `ggml_type` whose block size
 * or type size disagrees with the table, or `-1` when the whole table agrees with the linked ggml.
 * The stub returns `-1` unconditionally: it *is* the table.
 */
int32_t align_ggml_table_drift(void) {
    int i = 0;
    for (i = 0; i < ALIGN_GGML_TABLE_ROWS; i++) {
        enum ggml_type type = (enum ggml_type) align_ggml_type_table[i][0];
        if (ggml_blck_size(type) != (int64_t) align_ggml_type_table[i][1]) {
            return align_ggml_type_table[i][0];
        }
        if (ggml_type_size(type) != (size_t) align_ggml_type_table[i][2]) {
            return align_ggml_type_table[i][0];
        }
    }
    return -1;
}

/* Section 3.1's `bool` translation. `ggml_backend_dev_supports_op` needs a built graph, which is
 * exactly what must not exist before the type is validated, so the predicate is the checked-in
 * `mul_mat` left-operand table plus the linked library's own block size.
 */
int32_t align_ggml_type_ok(int32_t type, int64_t ne0) {
    int32_t blck = align_ggml_blck_size(type);
    if (blck < 0) {
        return blck;
    }
    if (ne0 <= 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (ne0 % (int64_t) blck != 0) {
        return ALIGN_GGML_SHAPE;
    }
    return ALIGN_GGML_OK;
}

/* ---------------------------------------------------------------------------------------------
 * Pointer arithmetic Align cannot express
 * ------------------------------------------------------------------------------------------- */

/* Align has no `raw`-to-integer cast and no `==` on `raw` (section 2.6), so the two facts the
 * gate's second clause is made of — "is this pointer aligned" and "how far into our buffer is
 * ggml's data pointer" — are computed here and cross as `int64_t`.
 */
int64_t align_ptr_align_mod(const void *p, int64_t modulus) {
    if (modulus <= 0) {
        return -1;
    }
    return (int64_t) (((uintptr_t) p) % (uintptr_t) modulus);
}

int64_t align_ptr_offset(const void *a, const void *b) {
    return (int64_t) ((const char *) a - (const char *) b);
}

/* ---------------------------------------------------------------------------------------------
 * Construction, placement, compute, and teardown
 * ------------------------------------------------------------------------------------------- */

void *align_ggml_device_open(void) {
    return (void *) align_ggml_cpu_device();
}

void *align_ggml_backend_open(void *device) {
    if (device == NULL) {
        return NULL;
    }
    return (void *) ggml_backend_dev_init((ggml_backend_dev_t) device, NULL);
}

/* The backend's own name, copied into a caller-owned byte range. A `const char *` cannot become an
 * Align `str` at this pin, so the name crosses as bytes the caller decodes with `as_str()`.
 * Returns the copied length, never NUL-terminates, and never writes more than `cap`.
 */
int32_t align_ggml_backend_name(void *backend, void *out, int32_t cap) {
    const char *name = NULL;
    size_t length = 0;
    if (backend == NULL || out == NULL || cap <= 0) {
        return 0;
    }
    name = ggml_backend_name((ggml_backend_t) backend);
    if (name == NULL) {
        return 0;
    }
    length = strlen(name);
    if (length > (size_t) cap) {
        length = (size_t) cap;
    }
    memcpy(out, name, length);
    return (int32_t) length;
}

void align_ggml_backend_close(void *backend) {
    if (backend != NULL) {
        ggml_backend_free((ggml_backend_t) backend);
    }
}

/* Section 3.1: `ggml_init` takes a 24-byte struct by value and is unreachable from Align. `no_alloc`
 * is always true — every tensor in this capability is placed in caller memory or allocated by
 * `ggml_backend_alloc_ctx_tensors`, never in the context's own arena.
 */
void *align_ggml_context_open(int64_t mem_bytes) {
    struct ggml_init_params params;
    if (mem_bytes <= 0) {
        return NULL;
    }
#ifdef ALIGN_GGML_FORCE_INIT_FAILURE
    /* Section 4.6: `R4_5_GGML_INIT` needs a live ggml that refuses to construct, which no input can
     * produce. The qualification rebuilds this one file with the macro and reruns the same
     * executable against the same pack, so the failure path is exercised rather than reasoned
     * about. The macro is never defined in an ordinary build.
     */
    return NULL;
#endif
    params.mem_size = (size_t) mem_bytes;
    params.mem_buffer = NULL;
    params.no_alloc = true;
    return (void *) ggml_init(params);
}

void align_ggml_context_close(void *ctx) {
    if (ctx != NULL) {
        ggml_free((struct ggml_context *) ctx);
    }
}

/* Rule 3, and the single most important line in this file. Section 2.4 measured
 * `GGML_ASSERT((uintptr_t)ptr % TENSOR_ALIGNMENT == 0) failed` followed by `abort()` — no error
 * return, no unwinding, no document. `src/ggml_spike.align` already refused a misaligned pointer at
 * section 3.8 step 13; this is the fail-closed second gate, so the abort is unreachable even if a
 * caller skips the step.
 */
void *align_ggml_buffer_from_host(void *device, void *ptr, int64_t size) {
    int64_t alignment = 0;
    int64_t max_size = 0;
    if (device == NULL || ptr == NULL || size <= 0) {
        return NULL;
    }
    /* R5C section 3.5: the **device's** own alignment, not the CPU's. On this host both are 32, and
     * asking the device is what keeps the gate meaningful when they differ. */
    alignment = align_ggml_device_props(device, ALIGN_GGML_DEV_ALIGNMENT);
    if (alignment <= 0) {
        return NULL;
    }
    if (align_ptr_align_mod(ptr, alignment) != 0) {
        return NULL;
    }
    /* R5C section 2.6 measured `exit 139`: an oversize wrap does not return `NULL`, it segfaults.
     * `src/model_forward.align` refuses the window at step 21a before the first wrap; this is the
     * fail-closed second gate, in the same shape as the alignment rule above it.
     *
     * Section 6, correction C15: a non-positive `max_size` is a **negative shim status** or a
     * device that reports no limit at all, and either one is a limit this file cannot check. The
     * gate refuses rather than passing the length through, which is the same fail-closed reading
     * `device_flag` gives a capability that is not exactly `1` (correction C1). */
    max_size = align_ggml_device_buft_max_size(device);
    if (max_size <= 0 || size > max_size) {
        return NULL;
    }
    return (void *) ggml_backend_dev_buffer_from_host_ptr(
        (ggml_backend_dev_t) device, ptr, (size_t) size, 0);
}

/* Section 2.4's second abort: a ggml buffer that outlives process teardown aborted inside `exit`
 * on the Metal backend. Freeing is mandatory, not hygiene, which is why section 3.9 makes the
 * teardown order a contract and the document records the counts.
 */
void align_ggml_buffer_free(void *buffer) {
    if (buffer != NULL) {
        ggml_backend_buffer_free((ggml_backend_buffer_t) buffer);
    }
}

void *align_ggml_new_tensor_2d(void *ctx, int32_t type, int64_t ne0, int64_t ne1) {
    if (ctx == NULL || ne0 <= 0 || ne1 <= 0) {
        return NULL;
    }
    if (align_ggml_table_row(type) < 0) {
        return NULL;
    }
    return (void *) ggml_new_tensor_2d(
        (struct ggml_context *) ctx, (enum ggml_type) type, ne0, ne1);
}

/* Section 2.2: `ggml_backend_tensor_alloc` is how a tensor is pointed at caller memory, and no
 * `ggml_tallocr` is involved. The plan guessed otherwise; section 5.5 records the refutation.
 */
int32_t align_ggml_tensor_place(void *buffer, void *tensor, void *addr) {
    int32_t alignment = 0;
    void *base = NULL;
    size_t span = 0;
    if (buffer == NULL || tensor == NULL || addr == NULL) {
        return ALIGN_GGML_INIT;
    }
    alignment = align_ggml_tensor_alignment();
    if (alignment <= 0) {
        return ALIGN_GGML_UNAVAILABLE;
    }
    if (align_ptr_align_mod(addr, (int64_t) alignment) != 0) {
        return ALIGN_GGML_ALIGNMENT;
    }
    base = ggml_backend_buffer_get_base((ggml_backend_buffer_t) buffer);
    span = ggml_backend_buffer_get_size((ggml_backend_buffer_t) buffer);
    if (base == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (align_ptr_offset(addr, base) < 0) {
        return ALIGN_GGML_BOUNDS;
    }
    if ((size_t) align_ptr_offset(addr, base) + ggml_nbytes((struct ggml_tensor *) tensor) > span) {
        return ALIGN_GGML_BOUNDS;
    }
    if (ggml_backend_tensor_alloc(
            (ggml_backend_buffer_t) buffer, (struct ggml_tensor *) tensor, addr)
        != GGML_STATUS_SUCCESS) {
        return ALIGN_GGML_INIT;
    }
    return ALIGN_GGML_OK;
}

void *align_ggml_alloc_remaining(void *ctx, void *backend) {
    if (ctx == NULL || backend == NULL) {
        return NULL;
    }
    return (void *) ggml_backend_alloc_ctx_tensors(
        (struct ggml_context *) ctx, (ggml_backend_t) backend);
}

int32_t align_ggml_tensor_set(void *tensor, const void *data, int64_t offset, int64_t size) {
    size_t capacity = 0;
    if (tensor == NULL || data == NULL || offset < 0 || size <= 0) {
        return ALIGN_GGML_INIT;
    }
    capacity = ggml_nbytes((struct ggml_tensor *) tensor);
    if ((size_t) offset > capacity || (size_t) size > capacity - (size_t) offset) {
        return ALIGN_GGML_BOUNDS;
    }
    ggml_backend_tensor_set((struct ggml_tensor *) tensor, data, (size_t) offset, (size_t) size);
    return ALIGN_GGML_OK;
}

void *align_ggml_mul_mat(void *ctx, void *a, void *b) {
    if (ctx == NULL || a == NULL || b == NULL) {
        return NULL;
    }
    return (void *) ggml_mul_mat(
        (struct ggml_context *) ctx, (struct ggml_tensor *) a, (struct ggml_tensor *) b);
}

/* Returns the `ggml_status` verbatim — `0` is `GGML_STATUS_SUCCESS`, and section 3.8 step 16 maps
 * anything else to `R4_5_COMPUTE` with detail `status[<n>]`. `ALIGN_GGML_COMPUTE_NULL` is outside
 * the `ggml_status` range so a null argument is never mistaken for a backend verdict.
 *
 * `ggml_abort` is `abort()`: a kernel that hits an internal assertion takes the process down before
 * any status is returned. Section 3.9 states that plainly rather than pretending otherwise.
 */
#define ALIGN_GGML_COMPUTE_NULL (-1000)

int32_t align_ggml_compute(void *backend, void *ctx, void *result) {
    struct ggml_cgraph *graph = NULL;
    if (backend == NULL || ctx == NULL || result == NULL) {
        return ALIGN_GGML_COMPUTE_NULL;
    }
#ifdef ALIGN_GGML_FORCE_COMPUTE_FAILURE
    /* Section 4.6: a non-success `ggml_status` from a backend that is working correctly. */
    return (int32_t) GGML_STATUS_FAILED;
#endif
    graph = ggml_new_graph((struct ggml_context *) ctx);
    if (graph == NULL) {
        return ALIGN_GGML_COMPUTE_NULL;
    }
    ggml_build_forward_expand(graph, (struct ggml_tensor *) result);
    return (int32_t) ggml_backend_graph_compute((ggml_backend_t) backend, graph);
}

/* Copies a tensor's bytes out into caller memory. The reference arm's output lives in ggml's own
 * memory by construction (section 3.6), and Align can form no view over foreign memory, so a
 * bit-exact comparison needs the bytes on this side of the boundary (section 6, correction C4).
 * `ggml_backend_tensor_get` is the public accessor; no `struct ggml_tensor` field is read here.
 */
int32_t align_ggml_tensor_get(void *tensor, void *out, int64_t offset, int64_t size) {
    size_t capacity = 0;
    if (tensor == NULL || out == NULL || offset < 0 || size <= 0) {
        return ALIGN_GGML_INIT;
    }
    capacity = ggml_nbytes((struct ggml_tensor *) tensor);
    if ((size_t) offset > capacity || (size_t) size > capacity - (size_t) offset) {
        return ALIGN_GGML_BOUNDS;
    }
    ggml_backend_tensor_get((struct ggml_tensor *) tensor, out, (size_t) offset, (size_t) size);
#ifdef ALIGN_GGML_FORCE_REFERENCE_PERTURBATION
    /* Section 4.6, and section 6 correction C11: `R4_5_REFERENCE_MISMATCH` is not producible by
     * mutating an input, because the byte-equality precheck stops a divergent reference first and
     * reports the correct cause. The code exists for a divergence the byte check cannot explain —
     * a nondeterministic or mis-dispatched kernel — so the qualification perturbs one byte of the
     * copied-out reference output and asserts the comparison loop names the exact element.
     */
    ((unsigned char *) out)[0] ^= 0x01u;
#endif
    return ALIGN_GGML_OK;
}

int64_t align_ggml_tensor_nbytes(void *tensor) {
    if (tensor == NULL) {
        return -1;
    }
    return (int64_t) ggml_nbytes((struct ggml_tensor *) tensor);
}

/* The gate's second clause as a number. `EXTERNAL` is this value equalling the member's own
 * interior offset; any other value is `COPIED`, which is a successful run reporting the answer the
 * roadmap asked for rather than a failure.
 */
int64_t align_ggml_tensor_data_offset(void *tensor, const void *base) {
    void *data = NULL;
    if (tensor == NULL || base == NULL) {
        return -1;
    }
    data = ggml_get_data((struct ggml_tensor *) tensor);
    if (data == NULL) {
        return -1;
    }
    return align_ptr_offset(data, base);
}

/* ---------------------------------------------------------------------------------------------
 * R5A-DENSE-LAYER-FORWARD — the node-slot accessors, the one-op wrappers, and the graph
 *
 * `docs/specs/r5a-dense-layer-forward.md` section 3.5. Rule 1 of this file is unchanged: no ggml
 * type appears in any signature, handles cross as `void *`, and a slot index crosses as `int64_t`.
 * Rule 5 is new and is section 4.3's "one op per wrapper" cell: every function below is exactly one
 * ggml call plus validation. None composes two ops, and none decides anything the node table in
 * `src/layer_qwen2.align` owns.
 * ------------------------------------------------------------------------------------------- */

static struct ggml_tensor *align_ggml_slot_tensor(const void *slots, int64_t index) {
    return (struct ggml_tensor *) align_ggml_slot_load(slots, index);
}

int64_t align_ggml_slot_nbytes(const void *slots, int64_t index) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    if (tensor == NULL) {
        return -1;
    }
    return (int64_t) ggml_nbytes(tensor);
}

/* R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY intervention B. Oracle B already runs on the fixed CPU
 * backend, but validate the tensor's actual buffer rather than trusting that caller context: only
 * host-visible storage may be dereferenced in place. The shared byte primitive owns traversal and
 * complete pointer-range validation. Exact tensor extent is checked here so no unrelated bytes can
 * become part of the oracle contract if a node-table shape drifts.
 */
int64_t align_ggml_slot_compare_kv_plane(
    const void *slots, int64_t index, const void *plane, int64_t plane_bytes,
    int64_t plane_base, int64_t head_dim, int64_t n_head_kv, int64_t columns,
    int32_t layout) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    int64_t elements = 0;
    int64_t span = 0;
    size_t tensor_bytes = 0;
    void *data = NULL;
    if (tensor == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (plane == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (head_dim <= 0 || n_head_kv <= 0 || columns <= 0 ||
        (layout != ALIGN_GGML_KV_LAYOUT_K && layout != ALIGN_GGML_KV_LAYOUT_V)) {
        return ALIGN_GGML_BOUNDS;
    }
    if (head_dim > INT64_MAX / n_head_kv) {
        return ALIGN_GGML_BOUNDS;
    }
    elements = head_dim * n_head_kv;
    if (elements > INT64_MAX / columns) {
        return ALIGN_GGML_BOUNDS;
    }
    elements *= columns;
    if (elements > INT64_MAX / 4) {
        return ALIGN_GGML_BOUNDS;
    }
    span = elements * 4;
    tensor_bytes = ggml_nbytes(tensor);
    if ((uint64_t) tensor_bytes > (uint64_t) INT64_MAX ||
        (int64_t) tensor_bytes != span) {
        return ALIGN_GGML_BOUNDS;
    }
    if (tensor->buffer == NULL || !ggml_backend_buffer_is_host(tensor->buffer)) {
        return ALIGN_GGML_BOUNDS;
    }
    data = ggml_get_data(tensor);
    if (data == NULL) {
        return ALIGN_GGML_BOUNDS;
    }
    return align_ggml_compare_kv_plane(
        data, span, plane, plane_bytes, plane_base,
        head_dim, n_head_kv, columns, layout);
}

int64_t align_ggml_slot_ne(const void *slots, int64_t index, int32_t dim) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    if (tensor == NULL || dim < 0 || dim > 3) {
        return -1;
    }
    return (int64_t) tensor->ne[dim];
}

int64_t align_ggml_slot_data_offset(const void *slots, int64_t index, const void *base) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    void *data = NULL;
    if (tensor == NULL || base == NULL) {
        return -1;
    }
    data = ggml_get_data(tensor);
    if (data == NULL) {
        return -1;
    }
    return align_ptr_offset(data, base);
}

int32_t align_ggml_slot_new_tensor_1d(
    void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0) {
    struct ggml_tensor *tensor = NULL;
    if (ctx == NULL || ne0 <= 0) {
        return ALIGN_GGML_INIT;
    }
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    tensor = ggml_new_tensor_1d((struct ggml_context *) ctx, (enum ggml_type) type, ne0);
    if (tensor == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor);
}

int32_t align_ggml_slot_new_tensor_2d(
    void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0, int64_t ne1) {
    struct ggml_tensor *tensor = NULL;
    if (ctx == NULL || ne0 <= 0 || ne1 <= 0) {
        return ALIGN_GGML_INIT;
    }
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    tensor = ggml_new_tensor_2d((struct ggml_context *) ctx, (enum ggml_type) type, ne0, ne1);
    if (tensor == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor);
}

/* The two index inputs. `I32` is deliberately absent from the checked-in operand table — that table
 * is the `mul_mat` **left-operand** predicate — so the token and position vectors get their own
 * entry point rather than widening a table that means something else (section 6, correction C3).
 */
int32_t align_ggml_slot_new_i32_1d(void *ctx, void *slots, int64_t out, int64_t ne0) {
#ifdef ALIGN_GGML_FORCE_SLOT_EMPTY
    /* Section 4.6: `R5_SLOT` for a *read* of an empty slot, which no input can produce because the
     * arm writes every slot it later reads. The position vector is the one slot no size check
     * guards, so reporting success without storing it makes the first use of that slot reach the
     * emptiness check for real. The macro is never defined in an ordinary build.
     */
    if (out == 14) {
        (void) ctx;
        (void) ne0;
        (void) slots;
        return ALIGN_GGML_OK;
    }
#endif
#ifdef ALIGN_GGML_FORCE_SLOT_EMPTY_POS
    /* R5B section 4.5: the same refusal, at the slot the whole-model arm's position vector uses.
     * R5A's `ALIGN_GGML_FORCE_SLOT_EMPTY` targets slot 14, which is R5A's `inp_pos` and R5B's
     * `kq_mask` — a tensor R5B creates through `slot_new_tensor_2d`, so that macro never fires for
     * the model arm. Never defined in an ordinary build.
     */
    if (out == 13) {
        (void) ctx;
        (void) ne0;
        (void) slots;
        return ALIGN_GGML_OK;
    }
#endif
    struct ggml_tensor *tensor = NULL;
    if (ctx == NULL || ne0 <= 0) {
        return ALIGN_GGML_INIT;
    }
    tensor = ggml_new_tensor_1d((struct ggml_context *) ctx, GGML_TYPE_I32, ne0);
    if (tensor == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor);
}

/* R4.5's `align_ggml_tensor_place`, addressed by slot. The alignment pre-check is the same line
 * that keeps `GGML_ASSERT` and `abort()` unreachable, now applied thirteen times per run.
 */
int32_t align_ggml_slot_place(void *buffer, void *slots, int64_t index, void *addr) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    if (tensor == NULL) {
        return ALIGN_GGML_SLOT;
    }
    return align_ggml_tensor_place(buffer, (void *) tensor, addr);
}

/* The reference arm's weights are the only tensors R5A ever *copies* into ggml-owned memory: the
 * primary arm places its thirteen at interior offsets in the Align window and never writes one.
 * Slots 0 to 12 of a store are therefore exactly the reference weights, which is what makes the
 * forced perturbation below a perturbation of the **reference arm only** (section 6, correction C7).
 */
int32_t align_ggml_slot_set(void *slots, int64_t index, const void *bytes, int64_t off, int64_t n) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    int32_t status = ALIGN_GGML_OK;
    if (tensor == NULL) {
        return ALIGN_GGML_SLOT;
    }
    status = align_ggml_tensor_set((void *) tensor, bytes, off, n);
#ifdef ALIGN_GGML_FORCE_REFERENCE_PERTURBATION
    /* Section 4.6, and section 6 correction C7: `R5_REFERENCE_MISMATCH` is not producible by
     * mutating an input, because step 26's byte-equality precheck stops a divergent reference first
     * and reports the correct cause. The code exists for a divergence that check cannot explain — a
     * nondeterministic or mis-dispatched kernel — so one bit of one reference weight is flipped
     * after it lands in ggml's own memory and the comparison loop must name the exact node and
     * element. The macro is never defined in an ordinary build.
     */
    /* Slots 0 to 11 are the reference arm's weights in both arms' slot maps; R5B's slot 12 is the
     * Align-owned residual **input**, which the primary arm also writes through `slot_set`, so the
     * range stops at 11 (R5B section 6, correction C8). */
    if (status == ALIGN_GGML_OK && index >= 0 && index <= 11) {
        unsigned char victim = 0;
        ggml_backend_tensor_get((struct ggml_tensor *) tensor, &victim, (size_t) off, 1);
        victim = (unsigned char) (victim ^ 0x01u);
        ggml_backend_tensor_set((struct ggml_tensor *) tensor, &victim, (size_t) off, 1);
    }
#endif
    return status;
}

/* Deliberately not `align_ggml_tensor_get`: that entry point carries R4.5's own forced
 * perturbation, and an R5A readback must report what the graph computed.
 */
int32_t align_ggml_slot_get(void *slots, int64_t index, void *bytes, int64_t off, int64_t n) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    size_t capacity = 0;
    if (tensor == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (bytes == NULL || off < 0 || n <= 0) {
        return ALIGN_GGML_INIT;
    }
    capacity = ggml_nbytes(tensor);
    if ((size_t) off > capacity || (size_t) n > capacity - (size_t) off) {
        return ALIGN_GGML_BOUNDS;
    }
    ggml_backend_tensor_get(tensor, bytes, (size_t) off, (size_t) n);
    return ALIGN_GGML_OK;
}

int32_t align_gpu_slot_get(void *owner, void *slots, int64_t index,
                           void *bytes, int64_t off, int64_t n) {
    struct align_gpu_device_state *state = (struct align_gpu_device_state *) owner;
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    int kind = 0;
    int node = 0;
    int found = 0;
    int32_t status = ALIGN_GGML_OK;
    if (state == NULL || tensor == NULL || state->observation_failed || n <= 0
        || state->observation_read_bytes > INT64_MAX - n
        || state->observation_read_calls == INT64_MAX) {
        return ALIGN_GGML_INIT;
    }
    for (kind = 0; kind < ALIGN_GPU_GRAPH_KINDS; kind++) {
        if (!state->graph_prepared[kind] || state->graph_current_execution_count[kind] < 1) {
            continue;
        }
        struct ggml_cgraph *graph = state->workspace_graphs[kind];
        if (graph == NULL) { continue; }
        for (node = 0; node < ggml_graph_n_nodes(graph); node++) {
            if (ggml_graph_node(graph, node) == tensor) { found = 1; }
        }
    }
    if (!found) { return ALIGN_GGML_SLOT; }
    status = align_ggml_slot_get(slots, index, bytes, off, n);
    if (status != ALIGN_GGML_OK) { return status; }
    state->observation_read_bytes += n;
    state->observation_read_calls += 1;
    return ALIGN_GGML_OK;
}


/* Mandatory for every oracle node. Without it `ggml_gallocr` reuses an intermediate's memory and
 * the node read back is not the node computed — the probe hit exactly this before adding it.
 */
int32_t align_ggml_slot_mark_output(void *slots, int64_t index) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    if (tensor == NULL) {
        return ALIGN_GGML_SLOT;
    }
    ggml_set_output(tensor);
    return ALIGN_GGML_OK;
}

/* One op per wrapper. `out` is the slot the result is stored in; `a`, `b`, and `pos` are the slots
 * the sources are read from. A source slot that is empty or out of range is `ALIGN_GGML_SLOT`
 * before any ggml call, which is the whole of section 3.8 step 22.
 */
#define ALIGN_GGML_OP_PROLOGUE_1(context, store, first)                     \
    struct ggml_tensor *result = NULL;                                      \
    struct ggml_tensor *sa = align_ggml_slot_tensor((store), (first));      \
    if ((context) == NULL) { return ALIGN_GGML_INIT; }                      \
    if (sa == NULL) { return ALIGN_GGML_SLOT; }

int32_t align_ggml_op_get_rows(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    struct ggml_tensor *sb = align_ggml_slot_tensor(slots, b);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    result = ggml_get_rows((struct ggml_context *) ctx, sa, sb);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

int32_t align_ggml_op_rms_norm(void *ctx, void *slots, int64_t out, int64_t a, int32_t eps_bits) {
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    /* Before the call that would `abort()` on a negative or non-finite epsilon. */
    if (!align_ggml_eps_ok(eps_bits)) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_rms_norm((struct ggml_context *) ctx, sa, align_ggml_bits_to_f32(eps_bits));
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

int32_t align_ggml_op_mul(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    struct ggml_tensor *sb = align_ggml_slot_tensor(slots, b);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    result = ggml_mul((struct ggml_context *) ctx, sa, sb);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

int32_t align_ggml_op_add(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    struct ggml_tensor *sb = align_ggml_slot_tensor(slots, b);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    result = ggml_add((struct ggml_context *) ctx, sa, sb);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

int32_t align_ggml_op_mul_mat(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    struct ggml_tensor *sb = align_ggml_slot_tensor(slots, b);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    result = ggml_mul_mat((struct ggml_context *) ctx, sa, sb);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* Attention KQ requires the reference's explicit F32 precision, including on CUDA. */
int32_t align_ggml_op_attention_scores(void *ctx, void *slots, int64_t out, int64_t k, int64_t q) {
    struct ggml_tensor *key = align_ggml_slot_tensor(slots, k);
    struct ggml_tensor *query = align_ggml_slot_tensor(slots, q);
    struct ggml_tensor *result;
    if (ctx == NULL) { return ALIGN_GGML_INIT; }
    if (key == NULL || query == NULL) { return ALIGN_GGML_SLOT; }
    if (key->type != GGML_TYPE_F32 || query->type != GGML_TYPE_F32) { return ALIGN_GGML_TYPE; }
    if (key->ne[0] != query->ne[0] || key->ne[2] <= 0 || key->ne[3] <= 0
        || query->ne[2] % key->ne[2] != 0 || query->ne[3] % key->ne[3] != 0
        || ggml_is_transposed(key)) { return ALIGN_GGML_SHAPE; }
    result = ggml_mul_mat(ctx, key, query);
    if (result == NULL) { return ALIGN_GGML_INIT; }
    ggml_mul_mat_set_prec(result, GGML_PREC_F32);
    return align_ggml_slot_store(slots, out, result);
}

int32_t align_ggml_op_reshape_3d(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, int64_t ne1, int64_t ne2) {
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (ne0 <= 0 || ne1 <= 0 || ne2 <= 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (ggml_nelements(sa) != ne0 * ne1 * ne2) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_reshape_3d((struct ggml_context *) ctx, sa, ne0, ne1, ne2);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

int32_t align_ggml_op_permute(
    void *ctx, void *slots, int64_t out, int64_t a,
    int32_t p0, int32_t p1, int32_t p2, int32_t p3) {
    int32_t seen = 0;
    int32_t axes[4];
    int i = 0;
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    axes[0] = p0;
    axes[1] = p1;
    axes[2] = p2;
    axes[3] = p3;
    for (i = 0; i < 4; i++) {
        if (axes[i] < 0 || axes[i] > 3) {
            return ALIGN_GGML_SHAPE;
        }
        seen |= 1 << axes[i];
    }
    if (seen != 0x0F) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_permute((struct ggml_context *) ctx, sa, p0, p1, p2, p3);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* `ggml_cont_3d` covers both shapes the layer needs: `kqv_out` is the `ne2 = 1` case the plan
 * called `cont_2d`, and the transposed V is the genuinely 3-D one (section 6, correction C4).
 */
int32_t align_ggml_op_cont_3d(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, int64_t ne1, int64_t ne2) {
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (ne0 <= 0 || ne1 <= 0 || ne2 <= 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (ggml_nelements(sa) != ne0 * ne1 * ne2) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_cont_3d((struct ggml_context *) ctx, sa, ne0, ne1, ne2);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* The five fixed scalars are compiled in and `mode` is validated `== 2`. Section 3.8 step 9 —
 * `rope.scaling_type == null` — is what earns the right to fix them: a model with YaRN scaling is
 * out of scope and is refused before this function is reached.
 */
int32_t align_ggml_op_rope_neox(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t pos,
    int32_t n_dims, int32_t mode, int32_t n_ctx_orig, int32_t freq_base_bits) {
    struct ggml_tensor *sp = align_ggml_slot_tensor(slots, pos);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sp == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (mode != GGML_ROPE_TYPE_NEOX) {
        return ALIGN_GGML_SHAPE;
    }
    if (n_dims <= 0 || n_ctx_orig <= 0) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_rope_ext((struct ggml_context *) ctx, sa, sp, NULL, n_dims, mode, n_ctx_orig,
                           align_ggml_bits_to_f32(freq_base_bits),
                           1.0f, 0.0f, 1.0f, 32.0f, 1.0f);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* R5D section 3.5: the one **widened** symbol. `mask == ALIGN_GGML_NO_MASK` is
 * `ggml_soft_max_ext(ctx, a, NULL, scale, bias)` — the plain softmax the router's 64-way gate is —
 * and every other value is a slot index that must name a live tensor exactly as before. The
 * sentinel is tested rather than inferred from a NULL load, so a genuinely empty slot is still
 * `ALIGN_GGML_SLOT` and never silently becomes an unmasked softmax.
 */
int32_t align_ggml_op_soft_max_ext(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t mask,
    int32_t scale_bits, int32_t max_bias_bits) {
    struct ggml_tensor *sm =
        (mask == ALIGN_GGML_NO_MASK) ? NULL : align_ggml_slot_tensor(slots, mask);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sm == NULL && mask != ALIGN_GGML_NO_MASK) {
        return ALIGN_GGML_SLOT;
    }
    if (sm != NULL && !ggml_is_contiguous(sm)) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_soft_max_ext((struct ggml_context *) ctx, sa, sm,
                               align_ggml_bits_to_f32(scale_bits),
                               align_ggml_bits_to_f32(max_bias_bits));
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

int32_t align_ggml_op_swiglu_split(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    struct ggml_tensor *sb = align_ggml_slot_tensor(slots, b);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    result = ggml_swiglu_split((struct ggml_context *) ctx, sa, sb);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* R5B section 3.6's one new op. `ggml_pad` appends `p` zero elements to the end of each axis; the
 * source keeps the leading positions, which is what makes the reconciliation pass's extra lanes
 * both zero and masked while the f32 reduction *length* matches llama.cpp's padded KV cache
 * (section 2.7).
 *
 * Rule 4 is kept: no `struct ggml_tensor` field is read here. The result's size is judged with
 * `ggml_nelements` **after** construction, which is safe because the context is `no_alloc` and a
 * refused tensor is metadata the caller never reaches.
 */
int32_t align_ggml_op_pad(void *ctx, void *slots, int64_t out, int64_t a,
                          int32_t p0, int32_t p1, int32_t p2, int32_t p3) {
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (p0 < 0 || p1 < 0 || p2 < 0 || p3 < 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (p0 > ALIGN_GGML_MAX_PAD || p1 > ALIGN_GGML_MAX_PAD
        || p2 > ALIGN_GGML_MAX_PAD || p3 > ALIGN_GGML_MAX_PAD) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_pad((struct ggml_context *) ctx, sa, p0, p1, p2, p3);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (ggml_nelements(result) > ALIGN_GGML_MAX_PAD_ELEMENTS) {
        return ALIGN_GGML_SHAPE;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* ---------------------------------------------------------------------------------------------
 * R6-DECODE-KV-STEP1 — the one new entry point
 *
 * `docs/specs/r6-decode-kv-step1.md` section 2.5. `ggml_concat(ctx, a, b, dim)` joins two tensors
 * along `dim`; every other axis must agree exactly. It is what turns "the KV plane's past columns"
 * and "this step's one new column" into the single operand the attention reduces over, and it is
 * the whole difference between a prefill layer and a decode layer.
 *
 * `sb` is fetched **before** `ALIGN_GGML_OP_PROLOGUE_1` because the macro emits declarations and C89
 * requires them first in the block. The axis check is stated here, before the call, for rule 3's
 * reason: `ggml_concat` asserts the same relation internally and `GGML_ASSERT` is `abort()` with no
 * unwinding, no document, and no error code. Section 2.4 records that K and V concatenate on
 * **different** axes — K's column axis is 1 and V's is 0 — so a single shared constant here would be
 * a silent transpose, and the shape refusal below is what makes a wrong one a code rather than a
 * plausible number.
 */
int32_t align_ggml_op_concat(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t b, int32_t dim) {
    struct ggml_tensor *sb = align_ggml_slot_tensor(slots, b);
    int axis = 0;
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (dim < 0 || dim > ALIGN_GGML_MAX_DIM_SELECTOR) {
        return ALIGN_GGML_INIT;
    }
    if (sa->type != sb->type) {
        return ALIGN_GGML_TYPE;
    }
    for (axis = 0; axis <= ALIGN_GGML_MAX_DIM_SELECTOR; axis++) {
        if (axis != (int) dim && sa->ne[axis] != sb->ne[axis]) {
            return ALIGN_GGML_SHAPE;
        }
    }
    result = ggml_concat((struct ggml_context *) ctx, sa, sb, (int) dim);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (ggml_nelements(result) > ALIGN_GGML_MAX_PAD_ELEMENTS) {
        return ALIGN_GGML_SHAPE;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* ---------------------------------------------------------------------------------------------
 * R5D-MOE-LAYER-FORWARD — the five new entry points
 *
 * `docs/specs/r5d-moe-layer-forward.md` section 3.5. Rule 5 is kept: each is exactly one ggml call
 * plus validation, and none decides anything the two node tables in `src/layer_olmoe.align` own.
 * Rule 3 is why each one validates first: `ggml_mul_mat_id` and `ggml_view_2d` both reach a
 * `GGML_ASSERT`, which is `abort()` with no unwinding, no document, and no error code.
 * ------------------------------------------------------------------------------------------- */

int32_t align_ggml_op_argsort(void *ctx, void *slots, int64_t out, int64_t a, int32_t order) {
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (order != ALIGN_GGML_SORT_ASC && order != ALIGN_GGML_SORT_DESC) {
        return ALIGN_GGML_INIT;
    }
    result = ggml_argsort((struct ggml_context *) ctx, sa,
                          order == ALIGN_GGML_SORT_DESC ? GGML_SORT_ORDER_DESC
                                                        : GGML_SORT_ORDER_ASC);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* `ggml_mul_mat_id` asserts six shape relations internally. Each is re-stated here, before the
 * call, so a malformed node table is `ALIGN_GGML_SHAPE` naming the row rather than a SIGABRT: the
 * stacked operand and the activation are 3-D, the id tensor is 2-D `I32`, its row count is the
 * token count, the reduction widths agree, and its slot count is a multiple of the activation's
 * second extent so the broadcast ggml performs is the one the table intends.
 */
int32_t align_ggml_op_mul_mat_id(
    void *ctx, void *slots, int64_t out, int64_t as_slot, int64_t b, int64_t ids) {
    struct ggml_tensor *sb = align_ggml_slot_tensor(slots, b);
    struct ggml_tensor *si = align_ggml_slot_tensor(slots, ids);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, as_slot)
    if (sb == NULL || si == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (si->type != GGML_TYPE_I32) {
        return ALIGN_GGML_TYPE;
    }
    if (sa->ne[3] != 1 || sb->ne[3] != 1 || si->ne[2] != 1 || si->ne[3] != 1) {
        return ALIGN_GGML_SHAPE;
    }
    if (si->ne[1] != sb->ne[2]) {
        return ALIGN_GGML_SHAPE;
    }
    if (sa->ne[0] != sb->ne[0]) {
        return ALIGN_GGML_SHAPE;
    }
    if (sb->ne[1] <= 0 || si->ne[0] <= 0 || si->ne[0] % sb->ne[1] != 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (ggml_is_transposed(sa)) {
        return ALIGN_GGML_SHAPE;
    }
    result = ggml_mul_mat_id((struct ggml_context *) ctx, sa, sb, si);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* A 2-D window on `a`, whose row stride and byte offset are **derived from `a`'s own strides** and
 * never supplied by the caller: `nb1 = a->nb[nb1_dim]` and `offset = offset_index * a->nb[
 * offset_dim]`. Align therefore hands over two axis indices and one element index, and cannot name
 * a byte position at all.
 *
 * The extent test is stricter than ggml's own. `ggml_new_tensor_impl` compares
 * `row_size(ne0) * ne1 + offset` against `ggml_nbytes(a)`, which is correct only for a contiguous
 * view; the reachable span of a strided one is `offset + (ne1 - 1) * nb1 + row_size(ne0)`, and that
 * is what is checked here. A view that reads past its source is the exact class of defect section
 * 2.8's readback bug belonged to.
 *
 * `ne0` is an element count and `ggml_row_size` is the only place the type enters the span
 * arithmetic. G1 also views the I32 argsort result, so the boundary accepts the two four-byte
 * element types F32 and I32 and keeps refusing quantized or sub-byte sources.
 */
int32_t align_ggml_op_view_2d(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, int64_t ne1,
    int32_t nb1_dim, int32_t offset_dim, int64_t offset_index) {
    size_t nb1 = 0;
    size_t offset = 0;
    size_t row = 0;
    size_t span = 0;
    size_t capacity = 0;
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (nb1_dim < 0 || nb1_dim > ALIGN_GGML_MAX_DIM_SELECTOR
        || offset_dim < 0 || offset_dim > ALIGN_GGML_MAX_DIM_SELECTOR) {
        return ALIGN_GGML_INIT;
    }
    if (ne0 <= 0 || ne1 <= 0 || offset_index < 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (ne0 > sa->ne[0]) {
        return ALIGN_GGML_SHAPE;
    }
    if (sa->type != GGML_TYPE_F32 && sa->type != GGML_TYPE_I32) {
        return ALIGN_GGML_TYPE;
    }
    nb1 = sa->nb[nb1_dim];
    offset = (size_t) offset_index * sa->nb[offset_dim];
    row = ggml_row_size(sa->type, ne0);
    capacity = ggml_nbytes(sa);
    span = offset + (size_t) (ne1 - 1) * nb1 + row;
    if (span < row || span > capacity) {
        return ALIGN_GGML_BOUNDS;
    }
    result = ggml_view_2d((struct ggml_context *) ctx, sa, ne0, ne1, nb1, offset);
    if (result == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) result);
}

/* The stacked expert operand. Same operand-table gate as the 1-D and 2-D constructors, because a
 * stacked tensor is a `mul_mat_id` left operand and the table is that predicate.
 */
int32_t align_ggml_slot_new_tensor_3d(
    void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0, int64_t ne1, int64_t ne2) {
    struct ggml_tensor *tensor = NULL;
    if (ctx == NULL || ne0 <= 0 || ne1 <= 0 || ne2 <= 0) {
        return ALIGN_GGML_INIT;
    }
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    tensor = ggml_new_tensor_3d((struct ggml_context *) ctx, (enum ggml_type) type, ne0, ne1, ne2);
    if (tensor == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor);
}

/* Item 66. A standalone stacked expert operand over fixed-size cache slots. `ggml_new_tensor_3d`
 * establishes the linked type's ordinary row and matrix strides; only the expert stride changes.
 * All arithmetic is checked before construction so neither ggml's shape asserts nor a later
 * placement can observe a wrapped extent.
 */
int32_t align_ggml_slot_new_strided_tensor_3d(
    void *ctx, void *slots, int64_t out, int32_t type,
    int64_t ne0, int64_t ne1, int64_t ne2, int64_t slice_stride) {
    struct ggml_tensor *tensor = NULL;
    int row_index = -1;
    size_t row_bytes = 0;
    size_t plane_bytes = 0;
    size_t stride = 0;
    size_t reachable = 0;
    if (ctx == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (ne0 <= 0 || ne1 <= 0 || ne2 <= 0 || slice_stride <= 0) {
        return ALIGN_GGML_SHAPE;
    }
    row_index = align_ggml_table_row(type);
    if (row_index < 0) {
        return ALIGN_GGML_TYPE;
    }
    if (ne0 % (int64_t) align_ggml_type_table[row_index][1] != 0) {
        return ALIGN_GGML_SHAPE;
    }
    if ((uint64_t) (ne0 / (int64_t) align_ggml_type_table[row_index][1])
        > (uint64_t) SIZE_MAX / (uint64_t) align_ggml_type_table[row_index][2]) {
        return ALIGN_GGML_SHAPE;
    }
    row_bytes = (size_t) (ne0 / (int64_t) align_ggml_type_table[row_index][1])
        * (size_t) align_ggml_type_table[row_index][2];
    if ((uint64_t) ne1 > (uint64_t) SIZE_MAX / row_bytes) {
        return ALIGN_GGML_SHAPE;
    }
    plane_bytes = row_bytes * (size_t) ne1;
    if ((uint64_t) slice_stride > (uint64_t) SIZE_MAX) {
        return ALIGN_GGML_SHAPE;
    }
    stride = (size_t) slice_stride;
    if (stride < plane_bytes) {
        return ALIGN_GGML_SHAPE;
    }
    if ((uint64_t) (ne2 - 1) > (uint64_t) (SIZE_MAX - plane_bytes) / stride
        || (uint64_t) ne2 > (uint64_t) SIZE_MAX / stride) {
        return ALIGN_GGML_SHAPE;
    }
    reachable = (size_t) (ne2 - 1) * stride + plane_bytes;
    if (reachable < plane_bytes) {
        return ALIGN_GGML_SHAPE;
    }
    tensor = ggml_new_tensor_3d((struct ggml_context *) ctx, (enum ggml_type) type, ne0, ne1, ne2);
    if (tensor == NULL) {
        return ALIGN_GGML_INIT;
    }
    tensor->nb[2] = stride;
    tensor->nb[3] = (size_t) ne2 * stride;
    return align_ggml_slot_store(slots, out, (void *) tensor);
}

/* The `{n_expert_used, T}` id tensors, beside `align_ggml_slot_new_i32_1d` and for its reason: the
 * operand table has no `I32` row and must not gain one (section 2.8).
 */
int32_t align_ggml_slot_new_i32_2d(void *ctx, void *slots, int64_t out, int64_t ne0, int64_t ne1) {
    struct ggml_tensor *tensor = NULL;
    if (ctx == NULL || ne0 <= 0 || ne1 <= 0) {
        return ALIGN_GGML_INIT;
    }
    tensor = ggml_new_tensor_2d((struct ggml_context *) ctx, GGML_TYPE_I32, ne0, ne1);
    if (tensor == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) tensor);
}

/* The context size a graph of `node_capacity` tensors needs, asked of the linked library so Align
 * never guesses one.
 */
int64_t align_ggml_graph_context_bytes(int64_t node_capacity) {
    if (node_capacity <= 0 || node_capacity > (int64_t) 65536) {
        return -1;
    }
    return (int64_t) (ggml_tensor_overhead() * (size_t) node_capacity + ggml_graph_overhead());
}

void *align_ggml_graph_new(void *ctx) {
    if (ctx == NULL) {
        return NULL;
    }
    return (void *) ggml_new_graph((struct ggml_context *) ctx);
}

/* R8-OLMOE-PHASE-A-OPERATION-DIAGNOSIS. Build one of the two contiguous views of an existing
 * topologically ordered graph. The returned graph owns only its pointer table through `ctx`; every
 * tensor and buffer remains owned by the source graph's contexts and allocator. The boundary must
 * be one unique interior compute node so prefix and suffix are both non-empty.
 */
void *align_ggml_graph_partition(void *ctx, void *graph, void *slots,
                                 int64_t boundary_slot, int32_t suffix) {
    struct ggml_cgraph *source = (struct ggml_cgraph *) graph;
    struct ggml_tensor *boundary = align_ggml_slot_tensor(slots, boundary_slot);
    struct ggml_cgraph *result = NULL;
    int count = 0;
    int boundary_at = -1;
    int matches = 0;
    int start = 0;
    int end = 0;
    int i = 0;

    if (ctx == NULL || source == NULL || boundary == NULL || (suffix != 0 && suffix != 1)) {
        return NULL;
    }
    count = ggml_graph_n_nodes(source);
    if (count < 2) {
        return NULL;
    }
    for (i = 0; i < count; i++) {
        if (ggml_graph_node(source, i) == boundary) {
            boundary_at = i;
            matches++;
        }
    }
    if (matches != 1 || boundary_at < 0 || boundary_at >= count - 1) {
        return NULL;
    }
    result = ggml_new_graph_custom((struct ggml_context *) ctx, (size_t) count, false);
    if (result == NULL) {
        return NULL;
    }
    start = suffix ? boundary_at + 1 : 0;
    end = suffix ? count : boundary_at + 1;
    for (i = start; i < end; i++) {
        ggml_graph_add_node(result, ggml_graph_node(source, i));
    }
    return (void *) result;
}

/* R8-OLMOE-ATTENTION-OPERATION-DIAGNOSIS. Select the tensors stored in one inclusive slot range
 * while retaining the source graph's actual topological order. Table rows are operation classes,
 * but a branched graph's dependency walk does not preserve row order. Requiring every requested
 * slot exactly once prevents a partial or aliased class from becoming a plausible timing result.
 */
void *align_ggml_graph_select_slot_range(void *ctx, void *graph, void *slots,
                                         int64_t first_slot, int64_t last_slot) {
    struct ggml_cgraph *source = (struct ggml_cgraph *) graph;
    struct ggml_cgraph *result = NULL;
    int64_t capacity = 0;
    int64_t requested = 0;
    int64_t slot = 0;
    int count = 0;
    int selected = 0;
    int i = 0;

    capacity = align_ggml_slot_capacity(slots);
    if (ctx == NULL || source == NULL || capacity < 0 || first_slot < 0 ||
        last_slot < first_slot || last_slot >= capacity) {
        return NULL;
    }
    count = ggml_graph_n_nodes(source);
    for (slot = first_slot; slot <= last_slot; slot++) {
        struct ggml_tensor *target = align_ggml_slot_tensor(slots, slot);
        int matches = 0;
        if (target == NULL) {
            continue;
        }
        for (i = 0; i < count; i++) {
            if (ggml_graph_node(source, i) == target) {
                matches++;
            }
        }
        if (matches != 1) {
            return NULL;
        }
        requested++;
    }
    if (requested <= 0 || requested > count) {
        return NULL;
    }
    result = ggml_new_graph_custom((struct ggml_context *) ctx, (size_t) count, false);
    if (result == NULL) {
        return NULL;
    }
    for (i = 0; i < count; i++) {
        struct ggml_tensor *node = ggml_graph_node(source, i);
        for (slot = first_slot; slot <= last_slot; slot++) {
            if (node == align_ggml_slot_tensor(slots, slot)) {
                ggml_graph_add_node(result, node);
                selected++;
                break;
            }
        }
    }
    if (selected != requested) {
        return NULL;
    }
    return (void *) result;
}

int32_t align_ggml_graph_expand(void *graph, void *slots, int64_t index) {
    struct ggml_tensor *tensor = align_ggml_slot_tensor(slots, index);
    if (graph == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (tensor == NULL) {
        return ALIGN_GGML_SLOT;
    }
    ggml_build_forward_expand((struct ggml_cgraph *) graph, tensor);
    return ALIGN_GGML_OK;
}

int32_t align_ggml_graph_node_count(void *graph) {
    if (graph == NULL) {
        return ALIGN_GGML_INIT;
    }
    return (int32_t) ggml_graph_n_nodes((struct ggml_cgraph *) graph);
}

void *align_ggml_gallocr_new(void *backend) {
    if (backend == NULL) {
        return NULL;
    }
    return (void *) ggml_gallocr_new(
        ggml_backend_get_default_buffer_type((ggml_backend_t) backend));
}

/* Section 2.6's `bool` translation: `bool` is not an FFI type at this pin, so the two `gallocr`
 * predicates cross as `int32_t` and a `false` becomes `ALIGN_GGML_ALLOC`.
 */
int32_t align_ggml_gallocr_reserve(void *galloc, void *graph) {
    if (galloc == NULL || graph == NULL) {
        return ALIGN_GGML_INIT;
    }
#ifdef ALIGN_GGML_FORCE_ALLOC_FAILURE
    /* Section 4.6: a `false` from a `gallocr` that is working correctly. */
    return ALIGN_GGML_ALLOC;
#endif
    if (!ggml_gallocr_reserve((ggml_gallocr_t) galloc, (struct ggml_cgraph *) graph)) {
        return ALIGN_GGML_ALLOC;
    }
    return ALIGN_GGML_OK;
}

int32_t align_ggml_gallocr_alloc(void *galloc, void *graph) {
    if (galloc == NULL || graph == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (!ggml_gallocr_alloc_graph((ggml_gallocr_t) galloc, (struct ggml_cgraph *) graph)) {
        return ALIGN_GGML_ALLOC;
    }
    return ALIGN_GGML_OK;
}

int64_t align_ggml_gallocr_bytes(void *galloc) {
    if (galloc == NULL) {
        return -1;
    }
    return (int64_t) ggml_gallocr_get_buffer_size((ggml_gallocr_t) galloc, 0);
}

void align_ggml_gallocr_free(void *galloc) {
    if (galloc != NULL) {
        ggml_gallocr_free((ggml_gallocr_t) galloc);
    }
}

/* Returns the `ggml_status` verbatim; section 3.8 step 24 maps anything else to `R5_COMPUTE`. */
int32_t align_ggml_graph_compute(void *backend, void *graph) {
    if (backend == NULL || graph == NULL) {
        return ALIGN_GGML_COMPUTE_NULL;
    }
#ifdef ALIGN_GGML_FORCE_COMPUTE_FAILURE
    return (int32_t) GGML_STATUS_FAILED;
#endif
    return (int32_t) ggml_backend_graph_compute((ggml_backend_t) backend,
                                                (struct ggml_cgraph *) graph);
}
