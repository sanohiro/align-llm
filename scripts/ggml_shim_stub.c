/* R4.5-EXTERNAL-BUFFER-SPIKE — the ggml-free stub shim.
 *
 * `docs/specs/r4-5-external-buffer.md` sections 3.2 and 4.4. This file is why `ggml-spike` is a
 * complete, linkable, runnable executable on a host that has never heard of ggml — which is every
 * hosted CI host this repository uses. It includes no ggml header, links no ggml library, and
 * names no ggml symbol.
 *
 * It is real code with a real contract, not a placeholder. `align_ggml_available` returns `0`, and
 * the whole of section 3.8's pack reading, index validation, shape validation, ABI probe, type
 * predicate, and alignment validation runs against it exactly as it runs against the real shim,
 * answered from the shared checked-in table below. The run then stops at the availability gate with
 * `R4_5_GGML_UNAVAILABLE` and a `verdict` of `UNAVAILABLE`, having exercised ten of the fifteen
 * error codes for real.
 *
 * The region between the two `R4.5 SHARED SHIM CONTRACT` markers is byte-identical to
 * `scripts/ggml_shim.c` and `scripts/run-ggml-spike-smoke` asserts that on every run: the two files
 * are one contract compiled twice, and a drift between them would let the hosted owner test pass
 * against a contract the qualification does not run.
 *
 * Built by the `Makefile`'s `build/lib/libalign_ggml_shim.$(SHIM_SUFFIX)` rule whenever
 * `ALIGN_LLM_GGML_INCLUDE` is unset. There is no third state and no probing of `/opt/homebrew`,
 * because a build input that changes with the contents of a directory is not reproducible.
 */

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

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

#ifdef ALIGN_GGML_FORCE_COMPUTE_STEP2
/* R6-STEP-N section 4.1's two pieces of state: the byte count of the first decode step's past-K
 * upload, and the latch that a later, larger one sets. Both are file-scope statics of a build that
 * is never produced ordinarily. */
static int64_t align_force_first_past_bytes = -1;
static int align_force_compute_step2 = 0;
#endif

#if defined(ALIGN_GGML_FORCE_COMPUTE_SUFFIX) \
    || defined(ALIGN_GGML_FORCE_SUFFIX_WRITEBACK_OFFSET)
/* R6-PREFIX-SUFFIX-PREFILL sections 4.1 and 4.2. One latch, set by the only graph in this arm that
 * computes **more than one column at `n_past > 0`** — which is the suffix pass and nothing else.
 *
 * The key is the mask image and it is fixture-independent. Slot 14 is `MF_SLOT_MASK`. A decode step
 * uploads one row (`ne[1] == 1`) and is excluded. A prefill uploads `T` rows whose row 0 unmasks
 * exactly one column, because `mf_write_mask` is `mf_write_mask_offset` at `row_offset = 0`. The
 * suffix pass uploads `S` rows at `row_offset = T_prefix >= 1`, so its row 0 unmasks `T_prefix + 1`
 * columns. "More than one open column in row 0 of a multi-row mask" is therefore exactly the suffix
 * pass, on any geometry and any split.
 *
 * Every mask upload re-decides it, so it is **cleared** by the first decode step's own mask and the
 * latch names the graph set now being built rather than one that has finished. Never defined in an
 * ordinary build. */
static int align_force_suffix_pass = 0;
#endif

/* ---------------------------------------------------------------------------------------------
 * Availability, the ABI probe, and the type predicate — the four entry points the stub answers
 * ------------------------------------------------------------------------------------------- */

/* The **only** difference a caller can observe before any state exists (section 3.4), and the one
 * switch that selects the two stub builds `docs/specs/r5a-dense-layer-forward.md` section 5.1 needs.
 *
 * The **default** stub is unavailable, exactly as R4.5 shipped it: `ggml-spike` stops at its
 * availability gate with `R4_5_GGML_UNAVAILABLE` / `R5_GGML_UNAVAILABLE`, and every step above that
 * gate — the whole reader, the geometry, the shapes, the types, the alignments — has run for real.
 *
 * `ALIGN_GGML_STUB_ENGINE` selects the second build, and the deterministic single-precision engine
 * below answers the rest of the contract. It exists because section 4.6 requires twenty-four of the
 * twenty-six error codes, **and both oracle verdicts**, to be reachable on a host with no ggml, no
 * model, and no llama.cpp; steps 18 to 29 are simply not reachable behind an unavailable shim
 * (section 6, correction C2). The engine is not a ggml reimplementation and does not try to be: it
 * computes the eleven f32 ops of one node table over the tiny synthetic geometry of section 5.1,
 * materializing every view, and refuses everything else.
 */
int32_t align_ggml_available(void) {
#ifdef ALIGN_GGML_STUB_ENGINE
    return 1;
#else
    return 0;
#endif
}

/* The checked-in expectation the qualification asserts the real library against. Returning it —
 * rather than `ALIGN_GGML_UNAVAILABLE` — is what makes section 3.8's alignment step reachable
 * without ggml, and the `spike-misaligned` fixtures are the regression that proves it.
 */
int32_t align_ggml_tensor_alignment(void) {
    return ALIGN_GGML_TENSOR_ALIGNMENT;
}

int32_t align_ggml_blck_size(int32_t type) {
    int row = align_ggml_table_row(type);
    if (row < 0) {
        return ALIGN_GGML_TYPE;
    }
    return align_ggml_type_table[row][1];
}

int32_t align_ggml_type_size(int32_t type) {
    int row = align_ggml_table_row(type);
    if (row < 0) {
        return ALIGN_GGML_TYPE;
    }
    return align_ggml_type_table[row][2];
}

/* The stub *is* the table, so it cannot disagree with it. */
int32_t align_ggml_table_drift(void) {
    return -1;
}

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
 * Pointer arithmetic Align cannot express — identical to the real shim, because the alignment
 * step is validated here too and a stub that answered differently would validate nothing
 * ------------------------------------------------------------------------------------------- */

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
 * The deterministic single-precision engine
 *
 * `docs/specs/r5a-dense-layer-forward.md` sections 4.5, 4.6, and 5.1. Everything below is behind
 * `align_ggml_available`, so a default stub build never runs one line of it; an
 * `ALIGN_GGML_STUB_ENGINE` build runs all of it and the whole of `--layer-forward` — the node-table
 * walk, `gallocr`, the compute, the node digests, the bit-exact reference arm, and both oracle
 * verdicts — executes hosted with no ggml and no model.
 *
 * Three rules, and they are the reason this is a test rather than a second implementation.
 *
 *  1. **It owns no heap.** One fixed arena and one fixed tensor pool, both `static`. Nothing here
 *     reserves memory from the process allocator, which is the same rule the real shim obeys and
 *     the same one `scripts/run-layer-forward-smoke` asserts by scanning both files.
 *  2. **Every view is materialized.** ggml's `RESHAPE`, `PERMUTE`, and `CONT` are stride tricks;
 *     here each one copies. The values a consumer compares are identical and the engine needs no
 *     stride machinery, which is what keeps it small enough to be obviously correct.
 *  3. **It refuses what it does not implement.** Only `F32` and `I32` tensors exist. A quantized
 *     type, an unknown op, an exhausted arena, or an exhausted pool is a status, never a guess.
 * ------------------------------------------------------------------------------------------- */

#define ALIGN_STUB_MAX_TENSORS   512
#define ALIGN_STUB_MAX_CONTEXTS   16
#define ALIGN_STUB_MAX_GRAPHS      8
#define ALIGN_STUB_MAX_BUFFERS    16
#define ALIGN_STUB_MAX_GALLOCRS    8
/* R6-PREFIX-TTFT raises the hosted legal-boundary fixture from 32 to 2048 tokens. The prefill mask
 * alone is 2048 x 2048 x 4 B, and this deliberately materializing engine holds the input and graph
 * arenas together. 512 MiB is a fixed test-double ceiling, not an allocation policy or a production
 * claim; exhaustion remains a refusal and the process still performs no heap allocation here. */
#define ALIGN_STUB_ARENA_BYTES (512 * 1024 * 1024)

#define ALIGN_STUB_TYPE_F32  0
#define ALIGN_STUB_TYPE_I32 26

#define ALIGN_STUB_OP_NONE       0
#define ALIGN_STUB_OP_GET_ROWS   1
#define ALIGN_STUB_OP_RMS_NORM   2
#define ALIGN_STUB_OP_MUL        3
#define ALIGN_STUB_OP_ADD        4
#define ALIGN_STUB_OP_MUL_MAT    5
#define ALIGN_STUB_OP_RESHAPE    6
#define ALIGN_STUB_OP_PERMUTE    7
#define ALIGN_STUB_OP_CONT       8
#define ALIGN_STUB_OP_ROPE       9
#define ALIGN_STUB_OP_SOFT_MAX  10
#define ALIGN_STUB_OP_SWIGLU    11
#define ALIGN_STUB_OP_PAD       12
/* R5D-MOE-LAYER-FORWARD (`docs/specs/r5d-moe-layer-forward.md` section 5.1). Three more
 * kernels, which is what makes the routed arm's whole contract — the router, the Align-owned
 * top-k slice, the compact expert stack, and both oracles — reachable with no ggml and no
 * model. */
#define ALIGN_STUB_OP_ARGSORT   13
#define ALIGN_STUB_OP_MUL_MAT_ID 14
#define ALIGN_STUB_OP_VIEW      15
/* R6-DECODE-KV-STEP1 (`docs/specs/r6-decode-kv-step1.md` section 2.5). One more kernel, which is
 * what gives the whole decode arm — the KV plane's readback, its upload, both concat axes, the
 * offset mask, and both acceptance oracles — a path with no ggml and no model. */
#define ALIGN_STUB_OP_CONCAT    16

typedef struct align_stub_tensor {
    int32_t type;
    int64_t ne[4];
    unsigned char *data;
    int32_t op;
    /* R5D: three, not two. `ggml_mul_mat_id` takes a stacked operand, an activation, and an id
     * tensor, and every one of them has to be a graph source or the post-order walk below would
     * schedule the multiply before the ids it reads. */
    struct align_stub_tensor *src[3];
    int32_t ip[4];
    /* Two, not three. The third slot has never had a user, and dropping it pays for `src`'s third
     * entry exactly: `align_ggml_graph_context_bytes` is `node_capacity * sizeof(this struct)`, so
     * growing the record by one pointer would move `abi.graph_context_bytes` in every R5A, R5B,
     * and R5C golden document for a change that has nothing to do with those arms. */
    int64_t lp[2];
    int32_t is_output;
    int32_t visited;
    int32_t context;
} align_stub_tensor;

typedef struct align_stub_graph {
    align_stub_tensor *nodes[ALIGN_STUB_MAX_TENSORS];
    int32_t count;
    int32_t used;
} align_stub_graph;

/* R5B: the engine is now driven thirty times per run rather than once, so its fixed pools have to
 * be **recycled**. Every ggml object a graph creates is freed before the next block's read begins
 * (`docs/specs/r5b-model-prefill-forward.md` section 3.10), which means the moment no context and
 * no buffer is live the whole engine is unreachable and can be reset. Without this the tensor pool,
 * the graph pool, and the arena are exhausted after the eighth graph. */
static void align_stub_reset_if_idle(void);

/* `owns_arena` separates the two kinds of buffer record this file hands out, and the reset below is
 * the only thing that reads it: a `buffer_from_host` wrap borrows the **caller's** memory and owns
 * no engine state, while the record `align_ggml_alloc_remaining` returns describes
 * `align_stub_arena` itself. */
typedef struct align_stub_buffer {
    unsigned char *base;
    int64_t size;
    int32_t used;
    int32_t owns_arena;
} align_stub_buffer;

typedef struct align_stub_gallocr {
    int64_t bytes;
    int32_t used;
} align_stub_gallocr;

static align_stub_tensor  align_stub_tensors[ALIGN_STUB_MAX_TENSORS];
static int32_t            align_stub_tensor_count;
static int32_t            align_stub_context_used[ALIGN_STUB_MAX_CONTEXTS];
static align_stub_graph   align_stub_graphs[ALIGN_STUB_MAX_GRAPHS];
static align_stub_buffer  align_stub_buffers[ALIGN_STUB_MAX_BUFFERS];
static align_stub_gallocr align_stub_gallocrs[ALIGN_STUB_MAX_GALLOCRS];
static int32_t            align_stub_backend_token;
static int32_t            align_stub_device_token;
#ifdef ALIGN_GGML_FORCE_CACHE_WRAP_FAILURE
static int32_t            align_stub_host_wrap_calls;
#endif

/* Two arenas so the tiny geometry never has to worry about lifetime: activations are re-assigned by
 * every `gallocr` allocation, weights and inputs are assigned once and outlive them.
 */
static unsigned char align_stub_arena[ALIGN_STUB_ARENA_BYTES];
static int64_t        align_stub_arena_used;

static unsigned char *align_stub_reserve(int64_t bytes) {
    int64_t padded = (bytes + 63) / 64 * 64;
    unsigned char *at = NULL;
    if (bytes <= 0 || padded > ALIGN_STUB_ARENA_BYTES - align_stub_arena_used) {
        return NULL;
    }
    at = align_stub_arena + align_stub_arena_used;
    align_stub_arena_used += padded;
    memset(at, 0, (size_t) padded);
    return at;
}

static int64_t align_stub_nelements(const align_stub_tensor *t) {
    return t->ne[0] * t->ne[1] * t->ne[2] * t->ne[3];
}

static int64_t align_stub_nbytes(const align_stub_tensor *t) {
    if (t->op == ALIGN_STUB_OP_NONE && t->lp[0] > 0) {
        return (t->ne[2] - 1) * t->lp[0] + t->ne[0] * t->ne[1] * 4;
    }
    return align_stub_nelements(t) * 4;
}

static int32_t align_stub_context_index(const void *ctx) {
    int32_t index = (int32_t) ((const int32_t *) ctx - align_stub_context_used);
    if (ctx == NULL || index < 0 || index >= ALIGN_STUB_MAX_CONTEXTS) {
        return -1;
    }
    return index;
}

static align_stub_tensor *align_stub_new(void *ctx, int32_t type, int64_t ne0, int64_t ne1,
                                         int64_t ne2, int64_t ne3) {
    align_stub_tensor *t = NULL;
    int32_t owner = align_stub_context_index(ctx);
    if (owner < 0 || align_stub_tensor_count >= ALIGN_STUB_MAX_TENSORS) {
        return NULL;
    }
    if (ne0 <= 0 || ne1 <= 0 || ne2 <= 0 || ne3 <= 0) {
        return NULL;
    }
    if (type != ALIGN_STUB_TYPE_F32 && type != ALIGN_STUB_TYPE_I32) {
        return NULL;
    }
    t = &align_stub_tensors[align_stub_tensor_count];
    align_stub_tensor_count++;
    memset(t, 0, sizeof(*t));
    t->type = type;
    t->ne[0] = ne0;
    t->ne[1] = ne1;
    t->ne[2] = ne2;
    t->ne[3] = ne3;
    t->context = owner;
    return t;
}

static align_stub_tensor *align_stub_slot(const void *slots, int64_t index) {
    return (align_stub_tensor *) align_ggml_slot_load(slots, index);
}

/* ---------------------------------------------------------------------------------------------
 * The eleven kernels
 * ------------------------------------------------------------------------------------------- */

static void align_stub_run(align_stub_tensor *t) {
    float *d = (float *) t->data;
    const align_stub_tensor *a = t->src[0];
    const align_stub_tensor *b = t->src[1];
    const float *x = (a != NULL) ? (const float *) a->data : NULL;
    const float *y = (b != NULL) ? (const float *) b->data : NULL;
    int64_t i0 = 0;
    int64_t i1 = 0;
    int64_t i2 = 0;
    int64_t i3 = 0;
    switch (t->op) {
    /* R5D: the general form. `ffn_moe_weights-0` is `get_rows` over a `{1, n_expert, T}` reshape
     * of the router probabilities indexed by a `{n_expert_used, T}` id tensor, so the index tensor
     * is 2-D and the source's second axis is selected by the id while its third is selected by the
     * id's own column. ggml's kernel reads
     * `src0 + i01*nb01 + i11*nb02` for the id at `(i10, i11)`, which is what this reproduces; the
     * 1-D index case R5A and R5B use is the `b->ne[1] == 1` specialisation of it and is unchanged
     * to the bit. */
    case ALIGN_STUB_OP_GET_ROWS: {
        const int32_t *rows = (const int32_t *) b->data;
        int64_t nc = t->ne[0];
        for (i2 = 0; i2 < b->ne[2]; i2++) {
            for (i1 = 0; i1 < b->ne[1]; i1++) {
                for (i0 = 0; i0 < b->ne[0]; i0++) {
                    int64_t at = i0 + b->ne[0] * (i1 + b->ne[1] * i2);
                    int64_t row = (int64_t) rows[at];
                    if (row < 0 || row >= a->ne[1]) {
                        row = 0;
                    }
                    memcpy(d + at * nc,
                           x + nc * (row + a->ne[1] * (i1 + a->ne[2] * i2)),
                           (size_t) nc * 4);
                }
            }
        }
    } break;
    case ALIGN_STUB_OP_RMS_NORM: {
        float eps = align_ggml_bits_to_f32(t->ip[0]);
        int64_t rows = align_stub_nelements(t) / t->ne[0];
        for (i1 = 0; i1 < rows; i1++) {
            const float *row = x + i1 * t->ne[0];
            float *out = d + i1 * t->ne[0];
            double total = 0.0;
            float mean = 0.0f;
            float scale = 0.0f;
            for (i0 = 0; i0 < t->ne[0]; i0++) {
                total += (double) row[i0] * (double) row[i0];
            }
            mean = (float) (total / (double) t->ne[0]);
            scale = 1.0f / sqrtf(mean + eps);
            for (i0 = 0; i0 < t->ne[0]; i0++) {
                out[i0] = row[i0] * scale;
            }
        }
    } break;
    case ALIGN_STUB_OP_MUL:
    case ALIGN_STUB_OP_ADD: {
        for (i3 = 0; i3 < t->ne[3]; i3++) {
            for (i2 = 0; i2 < t->ne[2]; i2++) {
                for (i1 = 0; i1 < t->ne[1]; i1++) {
                    for (i0 = 0; i0 < t->ne[0]; i0++) {
                        int64_t at = i0 + t->ne[0] * (i1 + t->ne[1] * (i2 + t->ne[2] * i3));
                        int64_t bt = (i0 % b->ne[0])
                            + b->ne[0] * ((i1 % b->ne[1])
                                + b->ne[1] * ((i2 % b->ne[2]) + b->ne[2] * (i3 % b->ne[3])));
                        d[at] = (t->op == ALIGN_STUB_OP_MUL) ? x[at] * y[bt] : x[at] + y[bt];
                    }
                }
            }
        }
    } break;
    case ALIGN_STUB_OP_MUL_MAT: {
        int64_t k = a->ne[0];
        int64_t m = a->ne[1];
        int64_t r2 = t->ne[2] / a->ne[2];
        int64_t r3 = t->ne[3] / a->ne[3];
        for (i3 = 0; i3 < t->ne[3]; i3++) {
            for (i2 = 0; i2 < t->ne[2]; i2++) {
                for (i1 = 0; i1 < t->ne[1]; i1++) {
                    const float *bv = y + k * (i1 + b->ne[1] * (i2 + b->ne[2] * i3));
                    for (i0 = 0; i0 < m; i0++) {
                        const float *av =
                            x + k * (i0 + m * ((i2 / r2) + a->ne[2] * (i3 / r3)));
                        float total = 0.0f;
                        int64_t at = 0;
                        for (at = 0; at < k; at++) {
                            total += av[at] * bv[at];
                        }
                        d[i0 + m * (i1 + t->ne[1] * (i2 + t->ne[2] * i3))] = total;
                    }
                }
            }
        }
    } break;
    case ALIGN_STUB_OP_RESHAPE:
    case ALIGN_STUB_OP_CONT: {
        memcpy(d, x, (size_t) align_stub_nbytes(t));
    } break;
    case ALIGN_STUB_OP_PERMUTE: {
        for (i3 = 0; i3 < a->ne[3]; i3++) {
            for (i2 = 0; i2 < a->ne[2]; i2++) {
                for (i1 = 0; i1 < a->ne[1]; i1++) {
                    for (i0 = 0; i0 < a->ne[0]; i0++) {
                        int64_t source[4];
                        int64_t target[4];
                        int axis = 0;
                        source[0] = i0;
                        source[1] = i1;
                        source[2] = i2;
                        source[3] = i3;
                        for (axis = 0; axis < 4; axis++) {
                            target[t->ip[axis]] = source[axis];
                        }
                        d[target[0] + t->ne[0] * (target[1]
                            + t->ne[1] * (target[2] + t->ne[2] * target[3]))] =
                            x[i0 + a->ne[0] * (i1 + a->ne[1] * (i2 + a->ne[2] * i3))];
                    }
                }
            }
        }
    } break;
    case ALIGN_STUB_OP_ROPE: {
        const int32_t *pos = (const int32_t *) b->data;
        int64_t n_dims = (int64_t) t->ip[0];
        float freq_base = align_ggml_bits_to_f32(t->ip[3]);
        float theta_scale = powf(freq_base, -2.0f / (float) n_dims);
        for (i2 = 0; i2 < t->ne[2]; i2++) {
            float theta_base = (float) pos[i2];
            for (i1 = 0; i1 < t->ne[1]; i1++) {
                int64_t base = t->ne[0] * (i1 + t->ne[1] * i2);
                float theta = theta_base;
                for (i0 = 0; i0 < n_dims; i0 += 2) {
                    float cos_theta = cosf(theta);
                    float sin_theta = sinf(theta);
                    float x0 = x[base + i0 / 2];
                    float x1 = x[base + i0 / 2 + n_dims / 2];
                    d[base + i0 / 2] = x0 * cos_theta - x1 * sin_theta;
                    d[base + i0 / 2 + n_dims / 2] = x0 * sin_theta + x1 * cos_theta;
                    theta *= theta_scale;
                }
                for (i0 = n_dims; i0 < t->ne[0]; i0++) {
                    d[base + i0] = x[base + i0];
                }
            }
        }
    } break;
    case ALIGN_STUB_OP_SOFT_MAX: {
        float scale = align_ggml_bits_to_f32(t->ip[0]);
        for (i3 = 0; i3 < t->ne[3]; i3++) {
            for (i2 = 0; i2 < t->ne[2]; i2++) {
                for (i1 = 0; i1 < t->ne[1]; i1++) {
                    int64_t base = t->ne[0] * (i1 + t->ne[1] * (i2 + t->ne[2] * i3));
                    /* R5D section 3.5's widened domain: a null mask is the router's plain 64-way
                     * softmax, and it contributes nothing rather than reading a tensor that does
                     * not exist. */
                    const float *mask = (b != NULL) ? y + b->ne[0] * (i1 % b->ne[1]) : NULL;
                    float highest = -INFINITY;
                    float total = 0.0f;
                    for (i0 = 0; i0 < t->ne[0]; i0++) {
                        float value = x[base + i0] * scale + (mask != NULL ? mask[i0] : 0.0f);
                        d[base + i0] = value;
                        if (value > highest) {
                            highest = value;
                        }
                    }
                    for (i0 = 0; i0 < t->ne[0]; i0++) {
                        float value = expf(d[base + i0] - highest);
                        d[base + i0] = value;
                        total += value;
                    }
                    for (i0 = 0; i0 < t->ne[0]; i0++) {
                        d[base + i0] /= total;
                    }
                }
            }
        }
    } break;
    case ALIGN_STUB_OP_SWIGLU: {
        int64_t count = align_stub_nelements(t);
        for (i0 = 0; i0 < count; i0++) {
            d[i0] = (x[i0] / (1.0f + expf(-x[i0]))) * y[i0];
        }
    } break;
    /* R5B section 3.6. `ggml_pad` appends zeroes at the end of each axis; the source keeps the
     * leading positions. The destination is zeroed first because `gallocr` reuses a dead block and
     * the padded lanes must be zero, not whatever the previous tenant left.
     */
    case ALIGN_STUB_OP_PAD: {
        int64_t count = align_stub_nelements(t);
        for (i0 = 0; i0 < count; i0++) {
            d[i0] = 0.0f;
        }
        for (i3 = 0; i3 < a->ne[3]; i3++) {
            for (i2 = 0; i2 < a->ne[2]; i2++) {
                for (i1 = 0; i1 < a->ne[1]; i1++) {
                    for (i0 = 0; i0 < a->ne[0]; i0++) {
                        d[i0 + t->ne[0] * (i1 + t->ne[1] * (i2 + t->ne[2] * i3))] =
                            x[i0 + a->ne[0] * (i1 + a->ne[1] * (i2 + a->ne[2] * i3))];
                    }
                }
            }
        }
    } break;
    /* R5D section 3.5. `ggml_argsort` sorts each row of `ne0` elements and writes the permutation
     * of indices, not the values.
     *
     * Correction C12. This kernel is a **stable insertion sort** — an index only moves past a
     * neighbour whose value is strictly out of order — so equal probabilities keep ascending index
     * order, which is the order `scripts/layer_forward_fixture.py`'s own independent forward
     * produces and therefore the only order the hosted goldens can agree with. It is deliberately
     * *not* a claim about ggml: ggml 0.21.0's CPU `argsort` is a `std::sort` over the index array,
     * whose tie order above the introsort insertion threshold is unspecified, and the exchange sort
     * this kernel used before C12 agreed with neither. Section 5.6's tie row is where that gap is
     * recorded and bounded; neither corpus holds an exact tie. */
    case ALIGN_STUB_OP_ARGSORT: {
        int32_t *out = (int32_t *) t->data;
        int64_t rows = align_stub_nelements(t) / t->ne[0];
        int32_t descending = (t->ip[0] == ALIGN_GGML_SORT_DESC);
        for (i1 = 0; i1 < rows; i1++) {
            const float *row = x + i1 * t->ne[0];
            int32_t *idx = out + i1 * t->ne[0];
            int64_t j = 0;
            for (i0 = 0; i0 < t->ne[0]; i0++) {
                idx[i0] = (int32_t) i0;
            }
            for (i0 = 1; i0 < t->ne[0]; i0++) {
                int32_t keep = idx[i0];
                for (j = i0; j > 0; j--) {
                    int32_t move = descending ? (row[idx[j - 1]] < row[keep])
                                              : (row[idx[j - 1]] > row[keep]);
                    if (!move) {
                        break;
                    }
                    idx[j] = idx[j - 1];
                }
                idx[j] = keep;
            }
#ifdef ALIGN_GGML_FORCE_ARGSORT_RANGE
            /* R5D section 4.5's `moe-routing-id-range` cell. An argsort that names a plane the
             * stack does not have is not producible from an input: the kernel writes a permutation
             * of `[0, ne0)` by construction, and that is exactly why `R5D_EXPERT_ID`'s range check
             * would otherwise be argued rather than run. Never defined in an ordinary build. */
            idx[0] = (int32_t) t->ne[0];
#endif
#ifdef ALIGN_GGML_FORCE_ARGSORT_REPEAT
            /* The `moe-routing-id-repeat` cell, and the one section 2.8's readback bug actually
             * produced: two slots of one token naming the same expert. */
            if (t->ne[0] > 1) {
                idx[1] = idx[0];
            }
#endif
        }
    } break;
    /* R5D section 3.5. One dot product per `(token, slot)` pair against the plane the id names, in
     * the **same** element order as `ALIGN_STUB_OP_MUL_MAT` above, because section 2.3's whole
     * result is that a compact stack with remapped ids is bit-identical to a whole one. The
     * activation's second extent is either the slot count or one, and `id % b->ne[1]` is ggml's own
     * broadcast rule. */
    case ALIGN_STUB_OP_MUL_MAT_ID: {
        const align_stub_tensor *ids = t->src[2];
        const int32_t *sel = (const int32_t *) ids->data;
        int64_t k = a->ne[0];
        int64_t m = a->ne[1];
        for (i2 = 0; i2 < t->ne[2]; i2++) {
            for (i1 = 0; i1 < t->ne[1]; i1++) {
                int64_t plane = (int64_t) sel[i1 + ids->ne[0] * i2];
                const float *bv = y + k * ((i1 % b->ne[1]) + b->ne[1] * i2);
                if (plane < 0 || plane >= a->ne[2]) {
                    plane = 0;
                }
                for (i0 = 0; i0 < m; i0++) {
                    const unsigned char *plane_base = (const unsigned char *) a->data
                        + plane * (a->lp[0] > 0 ? a->lp[0] : k * m * 4);
                    const float *av = (const float *) plane_base + k * i0;
                    float total = 0.0f;
                    int64_t at = 0;
                    for (at = 0; at < k; at++) {
                        total += av[at] * bv[at];
                    }
                    d[i0 + m * (i1 + t->ne[1] * i2)] = total;
                }
            }
        }
    } break;
    /* R5D section 3.5. Rule 2 of this file — every view is materialized — applied to
     * `ggml_view_2d`: the row stride and the byte offset were derived from the source's own strides
     * when the node was built, and the copy reproduces exactly the elements a strided view would
     * expose. */
    case ALIGN_STUB_OP_VIEW: {
        const unsigned char *from = (const unsigned char *) a->data + t->lp[1];
        for (i1 = 0; i1 < t->ne[1]; i1++) {
            memcpy(d + i1 * t->ne[0], from + i1 * t->lp[0], (size_t) t->ne[0] * 4);
        }
    } break;
    /* R6 section 2.5. `ggml_concat` along `dim`: `a`'s elements keep their own coordinates and
     * `b`'s are written at the same coordinates shifted by `a->ne[dim]`. Rule 2 of this file — every
     * view is materialized — applies: the kernel **copies**, it does not alias, so a stride trick
     * that happened to agree on this geometry cannot hide a layout error. The axis is carried in
     * `t->ip[0]` because a kernel reads only the node it was handed.
     *
     * Both axes the decode table uses run through this one loop nest: K concatenates on axis 1 and
     * V on axis 0 (section 2.4), and the offset below is applied to whichever coordinate `dim`
     * names rather than to a fixed one. */
    case ALIGN_STUB_OP_CONCAT: {
        int64_t dim = (int64_t) t->ip[0];
        int64_t at[4];
        int64_t shift = a->ne[dim];
        for (i3 = 0; i3 < a->ne[3]; i3++) {
            for (i2 = 0; i2 < a->ne[2]; i2++) {
                for (i1 = 0; i1 < a->ne[1]; i1++) {
                    for (i0 = 0; i0 < a->ne[0]; i0++) {
                        d[i0 + t->ne[0] * (i1 + t->ne[1] * (i2 + t->ne[2] * i3))] =
                            x[i0 + a->ne[0] * (i1 + a->ne[1] * (i2 + a->ne[2] * i3))];
                    }
                }
            }
        }
        for (i3 = 0; i3 < b->ne[3]; i3++) {
            for (i2 = 0; i2 < b->ne[2]; i2++) {
                for (i1 = 0; i1 < b->ne[1]; i1++) {
                    for (i0 = 0; i0 < b->ne[0]; i0++) {
                        at[0] = i0;
                        at[1] = i1;
                        at[2] = i2;
                        at[3] = i3;
                        at[dim] += shift;
                        d[at[0] + t->ne[0] * (at[1] + t->ne[1] * (at[2] + t->ne[2] * at[3]))] =
                            y[i0 + b->ne[0] * (i1 + b->ne[1] * (i2 + b->ne[2] * i3))];
                    }
                }
            }
        }
    } break;
    default:
        break;
    }
}

/* ---------------------------------------------------------------------------------------------
 * Construction, placement, compute, and teardown
 * ------------------------------------------------------------------------------------------- */

void *align_ggml_device_open(void) {
    align_stub_device_token = 1;
    return (void *) &align_stub_device_token;
}

/* R5C-METAL-PREFILL-ARM section 5.1. The stub has **no GPU device** unless it is built with
 * `ALIGN_GGML_STUB_GPU`, which is what makes `R5C_GPU_UNAVAILABLE` at section 3.9 step 20a the GPU
 * arm's hosted baseline: every step from 1 to 20 runs for real on a host with no ggml, no Metal, no
 * model, and no llama.cpp, and the arm then stops with a document and a verdict.
 *
 * `ALIGN_GGML_STUB_GPU` selects a second device token that otherwise behaves exactly as the
 * engine's CPU device, so the GPU arm's *successful* path — the window, the thirty wraps, the
 * placements, the self-reference oracle, the logits verdict — is reachable hosted too.
 */
#ifdef ALIGN_GGML_STUB_GPU
static int32_t align_stub_gpu_token = 0;
#endif

void *align_ggml_device_by_kind(int32_t kind) {
    if (kind == ALIGN_GGML_DEVICE_CPU) {
        return align_ggml_device_open();
    }
#ifdef ALIGN_GGML_STUB_GPU
    if (kind == ALIGN_GGML_DEVICE_GPU) {
        align_stub_gpu_token = 1;
        return (void *) &align_stub_gpu_token;
    }
#endif
    return NULL;
}

/* One fixed device memory figure for both `memory_free` and `memory_total`, so the golden documents
 * are reproducible: a stub that reported the host's real free memory would make every golden
 * machine-dependent. */
#define ALIGN_STUB_DEVICE_MEMORY ((int64_t) 4294967296)

static int align_stub_is_gpu(const void *device) {
#ifdef ALIGN_GGML_STUB_GPU
    return device == (const void *) &align_stub_gpu_token;
#else
    (void) device;
    return 0;
#endif
}

int64_t align_ggml_device_props(void *device, int32_t field) {
    if (device == NULL) {
        return ALIGN_GGML_UNAVAILABLE;
    }
    switch (field) {
    case ALIGN_GGML_DEV_TYPE_ID:
        return align_stub_is_gpu(device) ? ALIGN_GGML_DEVICE_GPU : ALIGN_GGML_DEVICE_CPU;
    case ALIGN_GGML_DEV_HOST_PTR:
#ifdef ALIGN_GGML_FORCE_NO_HOST_PTR
        /* Section 4.5's `R5C_NO_HOST_PTR` fixture. Never defined in an ordinary build. */
        return 0;
#else
        return 1;
#endif
    case ALIGN_GGML_DEV_HOST_BUFFER:
        return 0;
    case ALIGN_GGML_DEV_ALIGNMENT:
        return ALIGN_GGML_TENSOR_ALIGNMENT;
    case ALIGN_GGML_DEV_MEMORY_FREE:
    case ALIGN_GGML_DEV_MEMORY_TOTAL:
        return align_ggml_clamp_size((size_t) ALIGN_STUB_DEVICE_MEMORY);
    default:
        break;
    }
    return ALIGN_GGML_ABI;
}

int64_t align_ggml_device_buft_max_size(void *device) {
    if (device == NULL) {
        return ALIGN_GGML_UNAVAILABLE;
    }
#ifdef ALIGN_GGML_FORCE_MAX_BUFFER_SIZE
    /* Section 4.3's `gf-device-limit` fixture: a maximum buffer length the computed window exceeds,
     * so section 3.9 step 21a is reached hosted. Never defined in an ordinary build. */
    return (int64_t) (ALIGN_GGML_FORCE_MAX_BUFFER_SIZE);
#else
    return align_ggml_clamp_size((size_t) ALIGN_STUB_DEVICE_MEMORY);
#endif
}

int32_t align_ggml_device_text(void *device, int32_t which, void *out, int32_t cap) {
    static const char cpu_name[] = "stub-cpu";
    static const char gpu_name[] = "stub-gpu";
    static const char description[] = "align stub device";
    const char *text = NULL;
    size_t length = 0;
    if (device == NULL || out == NULL || cap <= 0) {
        return 0;
    }
    if (which == ALIGN_GGML_DEV_TEXT_NAME) {
        text = align_stub_is_gpu(device) ? gpu_name : cpu_name;
    } else if (which == ALIGN_GGML_DEV_TEXT_DESCRIPTION) {
        text = description;
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

void *align_ggml_backend_open(void *device) {
    if (device == NULL) {
        return NULL;
    }
    /* The token records which device the backend came from, so `graph.backend_name` names the
     * device the run actually used rather than the only one the stub used to have. */
    align_stub_backend_token = align_stub_is_gpu(device) ? 2 : 1;
    return (void *) &align_stub_backend_token;
}

int32_t align_ggml_backend_name(void *backend, void *out, int32_t cap) {
    static const char cpu_name[] = "stub-cpu";
    static const char gpu_name[] = "stub-gpu";
    const char *name = NULL;
    int32_t length = 0;
    if (backend == NULL || out == NULL || cap <= 0) {
        return 0;
    }
    name = (*(const int32_t *) backend == 2) ? gpu_name : cpu_name;
    length = (int32_t) strlen(name);
    if (length > cap) {
        length = cap;
    }
    memcpy(out, name, (size_t) length);
    return length;
}

void align_ggml_backend_close(void *backend) {
    (void) backend;
}

void *align_ggml_context_open(int64_t mem_bytes) {
    int32_t i = 0;
    if (mem_bytes <= 0) {
        return NULL;
    }
#ifdef ALIGN_GGML_FORCE_INIT_FAILURE
    /* Section 4.6: a live shim that refuses to construct, which no input can produce. */
    return NULL;
#endif
    for (i = 0; i < ALIGN_STUB_MAX_CONTEXTS; i++) {
        if (!align_stub_context_used[i]) {
            align_stub_context_used[i] = 1;
            return (void *) &align_stub_context_used[i];
        }
    }
    return NULL;
}

void align_ggml_context_close(void *ctx) {
    int32_t index = align_stub_context_index(ctx);
    if (index >= 0) {
        align_stub_context_used[index] = 0;
    }
    align_stub_reset_if_idle();
}

/* The engine's own state — graphs, tensor records, and the activation arena — reclaimed once
 * nothing points into it. A caller that leaks a context simply never triggers it and exhausts a
 * pool instead, which is the failure this file should report rather than hide.
 *
 * R6-RESIDENT-WEIGHTS: **contexts alone gate the reset, not buffers.** A buffer record here is a
 * borrowed `(base, size)` over the caller's own memory and owns nothing in the arena; every tensor
 * and every graph is owned by a context. Including buffers in the test made the reset depend on a
 * lifetime it does not describe, and a caller that legitimately holds one wrap across many graphs —
 * which is exactly what a resident weight arena is — exhausted `ALIGN_STUB_MAX_GRAPHS` after eight
 * graphs with every context correctly closed. Real ggml frees a graph with its context and has no
 * such coupling, so the double was refusing a program the thing it doubles accepts. The teardown
 * order the arm contracts (`teardown_graph`: gallocr, then contexts) is what keeps this safe: no
 * gallocr is live across a context close, so nothing points into the arena when it is reclaimed.
 *
 * **The narrowing is by ownership, not by kind.** Section 11.1 correction 15: dropping the buffer
 * test outright also dropped the one buffer record that *does* describe arena memory — the record
 * `align_ggml_alloc_remaining` returns over `align_stub_arena` for the reference arm's tensors. A
 * caller that closes its context while still holding that record would have had the bytes under it
 * reclaimed and handed out again. `owns_arena` is exactly the old test restricted to the records
 * that own something, so a resident weight wrap over the caller's own memory no longer gates the
 * reset and an arena-backed record still does. */
static void align_stub_reset_if_idle(void) {
    int32_t i = 0;
    for (i = 0; i < ALIGN_STUB_MAX_CONTEXTS; i++) {
        if (align_stub_context_used[i]) {
            return;
        }
    }
    for (i = 0; i < ALIGN_STUB_MAX_GALLOCRS; i++) {
        if (align_stub_gallocrs[i].used) {
            return;
        }
    }
    for (i = 0; i < ALIGN_STUB_MAX_BUFFERS; i++) {
        if (align_stub_buffers[i].used && align_stub_buffers[i].owns_arena) {
            return;
        }
    }
    for (i = 0; i < ALIGN_STUB_MAX_GRAPHS; i++) {
        align_stub_graphs[i].used = 0;
        align_stub_graphs[i].count = 0;
    }
    align_stub_tensor_count = 0;
    align_stub_arena_used = 0;
}

/* Validates identically to the real shim — the alignment rule is the one that keeps `abort()`
 * unreachable there, so answering it differently here would validate nothing — and then wraps the
 * caller's range in a borrowed buffer record. No byte is copied: the engine computes over the
 * caller's own memory, which is what makes the `EXTERNAL` verdict mean the same thing in both
 * builds.
 */
void *align_ggml_buffer_from_host(void *device, void *ptr, int64_t size) {
    int32_t i = 0;
#ifdef ALIGN_GGML_FORCE_HOST_WRAP_FAILURE
    /* R6-RESIDENT-WEIGHTS section 5.1's early-exit cell, `ds-force-resident-wrap`. The wrap is the
     * first thing after the resident fill, so refusing it is the one input-reachable way to reach a
     * resident run that has a live, filled arena, no wrap, and a converged teardown ahead of it.
     * Never defined in an ordinary build. */
    (void) device;
    (void) ptr;
    (void) size;
    return NULL;
#endif
#ifdef ALIGN_GGML_FORCE_CACHE_WRAP_FAILURE
    if (align_stub_host_wrap_calls == 0) {
        align_stub_host_wrap_calls++;
        return NULL;
    }
    align_stub_host_wrap_calls++;
#endif
    if (device == NULL || ptr == NULL || size <= 0) {
        return NULL;
    }
    if (align_ptr_align_mod(ptr, (int64_t) ALIGN_GGML_TENSOR_ALIGNMENT) != 0) {
        return NULL;
    }
    /* R5C section 2.6's second gate, in the same shape as the real shim's: an oversize wrap
     * segfaults there, so both files refuse the length rather than letting it reach the backend.
     * Section 6, correction C15: a non-positive limit is a negative status or no limit at all, and
     * this gate refuses on it rather than failing open. */
    {
        int64_t max_size = align_ggml_device_buft_max_size(device);
        if (max_size <= 0 || size > max_size) {
            return NULL;
        }
    }
    for (i = 0; i < ALIGN_STUB_MAX_BUFFERS; i++) {
        if (!align_stub_buffers[i].used) {
            align_stub_buffers[i].used = 1;
            align_stub_buffers[i].base = (unsigned char *) ptr;
            align_stub_buffers[i].size = size;
            align_stub_buffers[i].owns_arena = 0;
            return (void *) &align_stub_buffers[i];
        }
    }
    return NULL;
}

void align_ggml_buffer_free(void *buffer) {
    if (buffer != NULL) {
        ((align_stub_buffer *) buffer)->used = 0;
        align_stub_reset_if_idle();
    }
}

void *align_ggml_new_tensor_2d(void *ctx, int32_t type, int64_t ne0, int64_t ne1) {
    if (align_ggml_table_row(type) < 0) {
        return NULL;
    }
    return (void *) align_stub_new(ctx, type, ne0, ne1, 1, 1);
}

int32_t align_ggml_tensor_place(void *buffer, void *tensor, void *addr) {
    align_stub_buffer *window = (align_stub_buffer *) buffer;
    align_stub_tensor *t = (align_stub_tensor *) tensor;
    int64_t at = 0;
    if (addr != NULL
        && align_ptr_align_mod(addr, (int64_t) ALIGN_GGML_TENSOR_ALIGNMENT) != 0) {
        return ALIGN_GGML_ALIGNMENT;
    }
    if (window == NULL || t == NULL || addr == NULL) {
        return ALIGN_GGML_INIT;
    }
    at = align_ptr_offset(addr, window->base);
    if (at < 0 || at + align_stub_nbytes(t) > window->size) {
        return ALIGN_GGML_BOUNDS;
    }
    t->data = (unsigned char *) addr;
    return ALIGN_GGML_OK;
}

/* The reference arm's allocator: every tensor of `ctx` that has no data gets arena bytes, which is
 * memory this file owns and the caller cannot reach. That is the property the bit-exact oracle
 * needs — `ggml_get_data(t)` must not be the host pointer — and it holds here too.
 */
void *align_ggml_alloc_remaining(void *ctx, void *backend) {
    int32_t owner = align_stub_context_index(ctx);
    int32_t i = 0;
    int32_t slot = 0;
    if (owner < 0 || backend == NULL) {
        return NULL;
    }
    for (i = 0; i < align_stub_tensor_count; i++) {
        align_stub_tensor *t = &align_stub_tensors[i];
        if (t->context != owner || t->data != NULL) {
            continue;
        }
        t->data = align_stub_reserve(align_stub_nbytes(t));
        if (t->data == NULL) {
            return NULL;
        }
    }
    for (slot = 0; slot < ALIGN_STUB_MAX_BUFFERS; slot++) {
        if (!align_stub_buffers[slot].used) {
            align_stub_buffers[slot].used = 1;
            align_stub_buffers[slot].base = align_stub_arena;
            align_stub_buffers[slot].size = ALIGN_STUB_ARENA_BYTES;
            align_stub_buffers[slot].owns_arena = 1;
            return (void *) &align_stub_buffers[slot];
        }
    }
    return NULL;
}

int32_t align_ggml_tensor_set(void *tensor, const void *data, int64_t offset, int64_t size) {
    align_stub_tensor *t = (align_stub_tensor *) tensor;
    if (t == NULL || data == NULL || offset < 0 || size <= 0) {
        return ALIGN_GGML_INIT;
    }
    if (t->data == NULL || offset > align_stub_nbytes(t)
        || size > align_stub_nbytes(t) - offset) {
        return ALIGN_GGML_BOUNDS;
    }
    memcpy(t->data + offset, data, (size_t) size);
    return ALIGN_GGML_OK;
}

void *align_ggml_mul_mat(void *ctx, void *a, void *b) {
    (void) ctx;
    (void) a;
    (void) b;
    return NULL;
}

#define ALIGN_GGML_COMPUTE_NULL (-1000)

int32_t align_ggml_compute(void *backend, void *ctx, void *result) {
    (void) backend;
    (void) ctx;
    (void) result;
    return ALIGN_GGML_COMPUTE_NULL;
}

int32_t align_ggml_tensor_get(void *tensor, void *out, int64_t offset, int64_t size) {
    align_stub_tensor *t = (align_stub_tensor *) tensor;
    if (t == NULL || out == NULL || offset < 0 || size <= 0) {
        return ALIGN_GGML_INIT;
    }
    if (t->data == NULL || offset > align_stub_nbytes(t)
        || size > align_stub_nbytes(t) - offset) {
        return ALIGN_GGML_BOUNDS;
    }
    memcpy(out, t->data + offset, (size_t) size);
    return ALIGN_GGML_OK;
}

int64_t align_ggml_tensor_nbytes(void *tensor) {
    if (tensor == NULL) {
        return -1;
    }
    return align_stub_nbytes((const align_stub_tensor *) tensor);
}

int64_t align_ggml_tensor_data_offset(void *tensor, const void *base) {
    align_stub_tensor *t = (align_stub_tensor *) tensor;
    if (t == NULL || base == NULL || t->data == NULL) {
        return -1;
    }
    return align_ptr_offset(t->data, base);
}

/* ---------------------------------------------------------------------------------------------
 * R5A — the node-slot accessors, the one-op wrappers, and the graph
 *
 * Signature for signature with `scripts/ggml_shim.c`. Everything the real shim delegates to ggml,
 * this file answers from the engine above.
 * ------------------------------------------------------------------------------------------- */

int64_t align_ggml_slot_nbytes(const void *slots, int64_t index) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    if (t == NULL) {
        return -1;
    }
#ifdef ALIGN_GGML_FORCE_SHORT_READBACK
    /* R5B section 4.5: `R5_RESIDUAL` is the carried activation's length disagreeing with the next
     * graph's declared input, which no input can produce because both come from the same node
     * table. The layer table's `l_out` is slot 51; under-reporting it by one element makes the
     * residual invariant refuse for real. Never defined in an ordinary build. */
    if (index == 51) {
        return align_stub_nbytes(t) - 4;
    }
#endif
#ifdef ALIGN_GGML_FORCE_MOE_RESIDUAL_SHORT
    /* R5E section 4.5, the same class one slot map over: `src/moe_model_forward.align`'s phase-B
     * `l_out` is slot 69 at the synthetic corpus's `n_expert_used = 3`
     * (`MM_B_NODE_BASE` 56 + `2u + 8` - 1), and under-reporting it by one element makes the
     * per-layer residual invariant refuse for real. Never defined in an ordinary build. */
    if (index == 69) {
        return align_stub_nbytes(t) - 4;
    }
#endif
#ifdef ALIGN_GGML_FORCE_MOE_CARRY_SHORT
    /* R5E section 3.9 step 31's length arm. `ffn_norm-L` is phase A's node at
     * `MM_A_NODE_BASE` 21 + 31 = 52, and it is one of the five values that cross the phase
     * boundary; under-reporting it makes `R5E_CARRY` reachable without corrupting a table the arm
     * has already validated. Never defined in an ordinary build. */
    if (index == 52) {
        return align_stub_nbytes(t) - 4;
    }
#endif
    return align_stub_nbytes(t);
}

/* R8-OLMOE-PLANE-ROUNDTRIP-BOUNDARY intervention B. Every deterministic-engine tensor uses the
 * host arena, so resolving the slot and its data is the stub counterpart of the real shim's
 * explicit host-buffer proof. The shared primitive keeps traversal and range validation identical.
 */
int64_t align_ggml_slot_compare_kv_plane(
    const void *slots, int64_t index, const void *plane, int64_t plane_bytes,
    int64_t plane_base, int64_t head_dim, int64_t n_head_kv, int64_t columns,
    int32_t layout) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    int64_t elements = 0;
    int64_t span = 0;
    if (t == NULL) {
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
    if (align_stub_nbytes(t) != span || t->data == NULL) {
        return ALIGN_GGML_BOUNDS;
    }
    return align_ggml_compare_kv_plane(
        t->data, span, plane, plane_bytes, plane_base,
        head_dim, n_head_kv, columns, layout);
}

int64_t align_ggml_slot_ne(const void *slots, int64_t index, int32_t dim) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    if (t == NULL || dim < 0 || dim > 3) {
        return -1;
    }
    return t->ne[dim];
}

int64_t align_ggml_slot_data_offset(const void *slots, int64_t index, const void *base) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    if (t == NULL || base == NULL || t->data == NULL) {
        return -1;
    }
    return align_ptr_offset(t->data, base);
}

int32_t align_ggml_slot_new_tensor_1d(
    void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0) {
    align_stub_tensor *t = NULL;
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    t = align_stub_new(ctx, type, ne0, 1, 1, 1);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) t);
}

int32_t align_ggml_slot_new_tensor_2d(
    void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0, int64_t ne1) {
    align_stub_tensor *t = NULL;
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    t = align_stub_new(ctx, type, ne0, ne1, 1, 1);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) t);
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
#ifdef ALIGN_GGML_FORCE_SLOT_EMPTY_MOE
    /* R5D section 4.5: the same refusal again, at slot 11 — the routed arm's `inp_pos`. R5A's and
     * R5B's macros target slots 14 and 13, which R5D uses for the causal mask and for nothing, so
     * neither fires here. Never defined in an ordinary build. */
    if (out == 11) {
        (void) ctx;
        (void) ne0;
        (void) slots;
        return ALIGN_GGML_OK;
    }
#endif
    align_stub_tensor *t = align_stub_new(ctx, ALIGN_STUB_TYPE_I32, ne0, 1, 1, 1);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) t);
}

int32_t align_ggml_slot_place(void *buffer, void *slots, int64_t index, void *addr) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    if (t == NULL) {
        return ALIGN_GGML_SLOT;
    }
    return align_ggml_tensor_place(buffer, (void *) t, addr);
}

/* The reference arm's weights are the only tensors R5A ever *copies* into engine-owned memory, so
 * slots 0 to 12 of a store are exactly those weights and the forced perturbation below perturbs the
 * reference arm and nothing else (section 6, correction C7).
 */
int32_t align_ggml_slot_set(void *slots, int64_t index, const void *bytes, int64_t off, int64_t n) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    int32_t status = ALIGN_GGML_OK;
    if (t == NULL) {
        return ALIGN_GGML_SLOT;
    }
    status = align_ggml_tensor_set((void *) t, bytes, off, n);
#ifdef ALIGN_GGML_FORCE_REFERENCE_PERTURBATION
    /* Slots 0 to 11 are the reference arm's weights in both arms' slot maps; R5B's slot 12 is the
     * Align-owned residual **input**, which the primary arm also writes through `slot_set`, so the
     * range stops at 11 (R5B section 6, correction C8). */
    if (status == ALIGN_GGML_OK && index >= 0 && index <= 11) {
        t->data[off] = (unsigned char) (t->data[off] ^ 0x01u);
    }
#endif
#ifdef ALIGN_GGML_FORCE_REFERENCE_PERTURBATION_MOE
    /* R5D section 4.4's `self-reference failure` cell. Slots 44 to 46 are the **compact expert
     * stacks**, which only the reference arm ever writes — the primary places its three over the
     * Align-owned claim window and never copies a byte into them — so one flipped bit here
     * perturbs the reference arm and nothing else. R5A's slot range 0-11 is R5D's dense weights
     * plus its token and position vectors, which the primary *does* write, so that macro is the
     * wrong instrument for this arm. Never defined in an ordinary build. */
    if (status == ALIGN_GGML_OK && index >= 44 && index <= 46) {
        t->data[off] = (unsigned char) (t->data[off] ^ 0x01u);
    }
#endif
#ifdef ALIGN_GGML_FORCE_PLANE_STAGE_OFFSET
    /* R6-DECODE-KV-STEP1 section 4.2's `plane failure` cell, and oracle B's own regression. Slot 64
     * is `layer_qwen2.MF_SLOT_KPAST`, which **only** the decode arm writes and only with the past-K
     * columns it staged out of the plane; no other arm allocates the slot at all, so the shift below
     * perturbs the decode graph's past K and nothing else. One `float` of shift is exactly the
     * off-by-one stride error section 3.3 says oracle B exists to catch: the graph still has valid
     * shapes and computes a plausible answer, and the bytes it consumed no longer equal the bytes the
     * prefill wrote, which is `R6_PLANE_MISMATCH layer[0]tensor[k]col[0]`. Never defined in an
     * ordinary build. */
    if (status == ALIGN_GGML_OK && (index == 64 || index == 126) && n >= 8) {
        memmove(t->data + off, t->data + off + 4, (size_t) (n - 4));
    }
#endif
#ifdef ALIGN_GGML_FORCE_DECODE_POSITION
    /* R6 section 11.1's "positions are `[n_past]`" row, shipped as a build rather than as a source
     * mutation. Slot 13 is `MF_SLOT_POS`; the decode graph writes exactly **one** `int32` into it and
     * a prefill graph writes `T` of them, so `n == 4` selects the decode graph's position and only
     * it. Writing 0 ropes the decoded token at position 0 — a confidently wrong answer every shape
     * check accepts — and oracle A is what refuses it. Never defined in an ordinary build. */
    if (status == ALIGN_GGML_OK && index == 13 && n == 4 && off == 0) {
        t->data[0] = 0u;
        t->data[1] = 0u;
        t->data[2] = 0u;
        t->data[3] = 0u;
    }
#endif
#ifdef ALIGN_GGML_FORCE_DECODE_POSITION_MOE
    /* R6-OLMOE-DECODE's routed counterpart of `ALIGN_GGML_FORCE_DECODE_POSITION`. The routed arm's
     * `inp_pos` is `layer_olmoe.MM_SLOT_POS` (10), which is an ordinary **weight** slot in a dense
     * graph, so this is a separate build rather than a second index on the dense one: the dense
     * builds stay behaviourally byte-unchanged. `ne[0] == 1` with `n == 4` is the decode graph's
     * one-element position vector and nothing else. Never defined in an ordinary build. */
    if (status == ALIGN_GGML_OK && index == 10 && t->ne[0] == 1 && n == 4 && off == 0) {
        t->data[0] = 0u;
        t->data[1] = 0u;
        t->data[2] = 0u;
        t->data[3] = 0u;
    }
#endif
#ifdef ALIGN_GGML_FORCE_MASK_OFFSET_MOE
    /* R6-OLMOE-DECODE's routed counterpart of `ALIGN_GGML_FORCE_MASK_OFFSET`. The routed arm's
     * `kq_mask` is `layer_olmoe.MM_SLOT_MASK` (11), a weight slot in a dense graph, so this too is
     * a separate build. The row is additionally required to end in `-inf`, which every masked row
     * at a width above `n_past + 1` does and no weight does. Never defined in an ordinary build. */
    if (status == ALIGN_GGML_OK && index == 11 && t->ne[1] == 1 && off == 0 && n >= 8
        && ((float *) (void *) t->data)[n / 4 - 1] == -INFINITY) {
        int64_t lane = 0;
        int64_t last = -1;
        float *row = (float *) (void *) t->data;
        for (lane = 0; lane < n / 4; lane++) {
            if (row[lane] == 0.0f) {
                last = lane;
            }
        }
        if (last >= 0) {
            row[last] = -INFINITY;
        }
    }
#endif
#ifdef ALIGN_GGML_FORCE_COMPUTE_STEP2
    /* R6-STEP-N section 4.1's `failure` cell: a step that fails at a chosen **step** index, which is
     * the axis this capability adds. Slot 64 is `MF_SLOT_KPAST` and only a decode layer graph ever
     * writes it, with `n = n_past * n_head_kv * head_dim * 4`; every layer of one step writes the
     * same `n`, and every later step writes a strictly larger one because the plane grew. So the
     * first `n` seen is step 1's and any larger `n` is step 2 or beyond. Keying on the growth rather
     * than on a token count keeps the build independent of the fixture's `T`. Never defined in an
     * ordinary build. */
    /* R6-OLMOE-DECODE: the routed arm's past-K slot is `layer_olmoe.MM_SLOT_KPAST` (126). The
     * growth rule is identical on both arms and only one of the two slots exists in any one run. */
    if (status == ALIGN_GGML_OK && (index == 64 || index == 126)) {
        if (align_force_first_past_bytes < 0) {
            align_force_first_past_bytes = n;
        } else if (n > align_force_first_past_bytes) {
            align_force_compute_step2 = 1;
        }
    }
#endif
#if defined(ALIGN_GGML_FORCE_COMPUTE_SUFFIX) \
    || defined(ALIGN_GGML_FORCE_SUFFIX_WRITEBACK_OFFSET)
    /* The latch above, set from the mask the graph is about to consume. It is read below by
     * `align_ggml_graph_compute` and by `align_ggml_slot_get`, both of which run after this call for
     * the same graph, so the pass is identified before either can act on it.
     *
     * It is **re-decided on every mask upload and therefore cleared after the pass**, not only
     * set: a decode step uploads a one-row mask and a prefill's row 0 unmasks exactly one column,
     * so either drives the latch back to 0. A set-only latch would leave the forced arms armed for
     * every decode step that followed a suffix pass, which is not what the two comments below
     * claim and not what the two forced builds are regressions for. */
    if (status == ALIGN_GGML_OK && index == 14 && off == 0 && n >= 8) {
        const float *mask_row = (const float *) (const void *) t->data;
        int64_t open_columns = 0;
        int64_t column = 0;
        if (t->ne[1] > 1) {
            for (column = 0; column < t->ne[0]; column++) {
                if (mask_row[column] == 0.0f) {
                    open_columns++;
                }
            }
        }
        align_force_suffix_pass = (open_columns > 1) ? 1 : 0;
    }
#endif
#ifdef ALIGN_GGML_FORCE_MASK_OFFSET
    /* R6 section 11.1's "mask `{KV_WIDTH, 1}` with offset" row, shipped as a build. Slot 14 is
     * `MF_SLOT_MASK`, and `ne[1] == 1` is the decode graph's one-row mask — a prefill mask has `T`
     * rows. `mf_write_mask_offset` unmasks columns `0 ..= n_past`, so the highest `0.0f` in the row
     * is the decoded token's own column; masking it is `mf_write_mask_offset(.., n_past - 1)`, which
     * is the off-by-one the offset mask exists to get right. The scan reads the row rather than
     * taking `n_past` as a constant, because a kernel knows only the node it was handed. Never
     * defined in an ordinary build. */
    if (status == ALIGN_GGML_OK && index == 14 && t->ne[1] == 1 && off == 0 && n >= 8) {
        int64_t lane = 0;
        int64_t last = -1;
        float *row = (float *) (void *) t->data;
        for (lane = 0; lane < n / 4; lane++) {
            if (row[lane] == 0.0f) {
                last = lane;
            }
        }
        if (last >= 0) {
            row[last] = -INFINITY;
        }
    }
#endif
    return status;
}

int32_t align_ggml_slot_get(void *slots, int64_t index, void *bytes, int64_t off, int64_t n) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    if (t == NULL) {
        return ALIGN_GGML_SLOT;
    }
#ifdef ALIGN_GGML_FORCE_WRITEBACK_OFFSET_MOE
    /* R6-OLMOE-DECODE's routed counterpart of `ALIGN_GGML_FORCE_WRITEBACK_OFFSET`. The routed arm
     * reads its write-back out of `layer_olmoe.MM_A_NODE_BASE + MM_K_ROW` (32), which is the K
     * concatenation's own slot in a dense graph, so this is a separate build and the dense one is
     * behaviourally byte-unchanged. A routed **prefill** reads slot 32 with `ne[2] == T`, so
     * `ne[2] == 1` selects the decode step's own readback. Never defined in an ordinary build. */
    if (index == 32 && t->ne[2] == 1) {
        int32_t status = align_ggml_tensor_get((void *) t, bytes, off, n);
        if (status == ALIGN_GGML_OK && bytes != NULL && n >= 8) {
            memmove(bytes, (unsigned char *) bytes + 4, (size_t) (n - 4));
        }
        return status;
    }
#endif
#ifdef ALIGN_GGML_FORCE_WRITEBACK_OFFSET
    /* R6-STEP-N section 4.2's `failure -- round trip` cell, and the shipped regression that proves
     * oracle B compares the **new** column and not only the past ones. Slot 28 is
     * `MF_SLOT_NODE_BASE + 12`, the post-RoPE K the write-back reads; the prefill reads it with
     * `ne[2] == T` and a decode step reads it with `ne[2] == 1`, so the guard below selects the
     * write-back's own readback and nothing else. Shifting the copied column by one `float` is
     * exactly the off-by-one lane a write-back can commit: every shape stays valid, the graph
     * computed what it computed, and the bytes now in the plane are not the bytes the graph
     * produced -- which oracle B reports at column `T`, the column the step just wrote. Never
     * defined in an ordinary build. */
    if (index == 28 && t->ne[2] == 1) {
        int32_t status = align_ggml_tensor_get((void *) t, bytes, off, n);
        if (status == ALIGN_GGML_OK && bytes != NULL && n >= 8) {
            memmove(bytes, (unsigned char *) bytes + 4, (size_t) (n - 4));
        }
        return status;
    }
#endif
#ifdef ALIGN_GGML_FORCE_SUFFIX_WRITEBACK_OFFSET
    /* R6-PREFIX-SUFFIX-PREFILL section 4.2's `failure -- round trip` cell, and the shipped
     * regression that proves oracle B compares the **first suffix column** and not only the loaded
     * ones. Slot 28 is `MF_SLOT_NODE_BASE + 12`, the post-RoPE K the write-back reads; the latch
     * confines the shift to the suffix pass, so the prefill's own capture and every decode step's
     * write-back are untouched. Shifting the copied bytes by one `float` is exactly the off-by-one
     * lane a write-back can commit: every shape stays valid and the bytes now in the plane are not
     * the bytes the graph produced, which oracle B reports at column `T_prefix` — the first column
     * this pass wrote. Never defined in an ordinary build. */
    if (index == 28 && align_force_suffix_pass) {
        int32_t status = align_ggml_tensor_get((void *) t, bytes, off, n);
        if (status == ALIGN_GGML_OK && bytes != NULL && n >= 8) {
            memmove(bytes, (unsigned char *) bytes + 4, (size_t) (n - 4));
        }
        return status;
    }
#endif
#ifdef ALIGN_GGML_FORCE_INF_READBACK
    /* R5C section 6, correction C19. A **computed** activation with no ten-thousandths value is a
     * condition no operand can produce: every fixture's inputs are finite and the engine's eleven
     * kernels are closed over them, so the oracle's own conversion of a non-finite activation — and
     * the logits comparison's non-finite *primary* branch — were argued rather than run. This build
     * makes the first element of every readback `+inf` and changes nothing else: the tensor data is
     * untouched, so the graph still computes what it computed and only the bytes the arm reads back
     * carry the value. Never defined in an ordinary build.
     */
    {
        int32_t status = align_ggml_tensor_get((void *) t, bytes, off, n);
        static const unsigned char positive_infinity[4] = { 0x00u, 0x00u, 0x80u, 0x7fu };
        if (status == ALIGN_GGML_OK && bytes != NULL && off == 0 && n >= 4) {
            memcpy(bytes, positive_infinity, sizeof(positive_infinity));
        }
        return status;
    }
#else
    return align_ggml_tensor_get((void *) t, bytes, off, n);
#endif
}

int32_t align_ggml_slot_mark_output(void *slots, int64_t index) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    if (t == NULL) {
        return ALIGN_GGML_SLOT;
    }
#ifdef ALIGN_GGML_FORCE_NO_MARK_OUTPUT
    /* Section 4.6, added by the review repair: the mark is silently dropped, which is what a node
     * table that forgets `node_oracle` would do. The allocator below then hands an oracle node's
     * bytes to a later node and the readback is not the node computed — the failure section 5.6
     * names and that the hosted owner previously could not observe. The macro is never defined in
     * an ordinary build.
     */
    (void) t;
    return ALIGN_GGML_OK;
#else
    t->is_output = 1;
    return ALIGN_GGML_OK;
#endif
}

static int32_t align_stub_bind(void *slots, int64_t out, align_stub_tensor *t,
                               align_stub_tensor *a, align_stub_tensor *b, int32_t op) {
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->op = op;
    t->src[0] = a;
    t->src[1] = b;
    t->src[2] = NULL;
    return align_ggml_slot_store(slots, out, (void *) t);
}

/* R5D: the same bind with a third source, for `mul_mat_id`. */
static int32_t align_stub_bind3(void *slots, int64_t out, align_stub_tensor *t,
                                align_stub_tensor *a, align_stub_tensor *b,
                                align_stub_tensor *c, int32_t op) {
    int32_t status = align_stub_bind(slots, out, t, a, b, op);
    if (status == ALIGN_GGML_OK) {
        t->src[2] = c;
    }
    return status;
}

int32_t align_ggml_op_get_rows(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *sb = align_stub_slot(slots, b);
    if (sa == NULL || sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (sa->type != ALIGN_STUB_TYPE_F32 || sb->type != ALIGN_STUB_TYPE_I32) {
        return ALIGN_GGML_TYPE;
    }
    /* R5D: ggml's own result shape, `{a->ne[0], b->ne[0], b->ne[1], a->ne[3]}`. For R5A's and
     * R5B's 1-D index vectors `b->ne[1]` is 1 and this is the shape they already had. */
    return align_stub_bind(slots, out,
        align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[0], sb->ne[0], sb->ne[1], sa->ne[3]),
        sa, sb, ALIGN_STUB_OP_GET_ROWS);
}

int32_t align_ggml_op_rms_norm(void *ctx, void *slots, int64_t out, int64_t a, int32_t eps_bits) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *t = NULL;
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
    /* The same refusal the real shim makes, for the same reason: the engine must not accept a
     * pattern the linked library would abort on.
     */
    if (!align_ggml_eps_ok(eps_bits)) {
        return ALIGN_GGML_SHAPE;
    }
    t = align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[0], sa->ne[1], sa->ne[2], sa->ne[3]);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->ip[0] = eps_bits;
    return align_stub_bind(slots, out, t, sa, NULL, ALIGN_STUB_OP_RMS_NORM);
}

static int32_t align_stub_elementwise(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t b, int32_t op) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *sb = align_stub_slot(slots, b);
    if (sa == NULL || sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    return align_stub_bind(slots, out,
        align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[0], sa->ne[1], sa->ne[2], sa->ne[3]),
        sa, sb, op);
}

int32_t align_ggml_op_mul(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    return align_stub_elementwise(ctx, slots, out, a, b, ALIGN_STUB_OP_MUL);
}

int32_t align_ggml_op_add(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    return align_stub_elementwise(ctx, slots, out, a, b, ALIGN_STUB_OP_ADD);
}

int32_t align_ggml_op_mul_mat(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *sb = align_stub_slot(slots, b);
    if (sa == NULL || sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (sa->type != ALIGN_STUB_TYPE_F32 || sb->type != ALIGN_STUB_TYPE_F32) {
        return ALIGN_GGML_TYPE;
    }
    if (sa->ne[0] != sb->ne[0] || sa->ne[2] <= 0 || sb->ne[2] % sa->ne[2] != 0
        || sb->ne[3] % sa->ne[3] != 0) {
        return ALIGN_GGML_SHAPE;
    }
    return align_stub_bind(slots, out,
        align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[1], sb->ne[1], sb->ne[2], sb->ne[3]),
        sa, sb, ALIGN_STUB_OP_MUL_MAT);
}

int32_t align_ggml_op_reshape_3d(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, int64_t ne1, int64_t ne2) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (ne0 <= 0 || ne1 <= 0 || ne2 <= 0 || align_stub_nelements(sa) != ne0 * ne1 * ne2) {
        return ALIGN_GGML_SHAPE;
    }
    return align_stub_bind(slots, out,
        align_stub_new(ctx, ALIGN_STUB_TYPE_F32, ne0, ne1, ne2, 1),
        sa, NULL, ALIGN_STUB_OP_RESHAPE);
}

int32_t align_ggml_op_permute(
    void *ctx, void *slots, int64_t out, int64_t a,
    int32_t p0, int32_t p1, int32_t p2, int32_t p3) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *t = NULL;
    int32_t axes[4];
    int32_t seen = 0;
    int64_t dims[4];
    int i = 0;
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
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
    for (i = 0; i < 4; i++) {
        dims[axes[i]] = sa->ne[i];
    }
    t = align_stub_new(ctx, ALIGN_STUB_TYPE_F32, dims[0], dims[1], dims[2], dims[3]);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    for (i = 0; i < 4; i++) {
        t->ip[i] = axes[i];
    }
    return align_stub_bind(slots, out, t, sa, NULL, ALIGN_STUB_OP_PERMUTE);
}

int32_t align_ggml_op_cont_3d(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, int64_t ne1, int64_t ne2) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (ne0 <= 0 || ne1 <= 0 || ne2 <= 0 || align_stub_nelements(sa) != ne0 * ne1 * ne2) {
        return ALIGN_GGML_SHAPE;
    }
    return align_stub_bind(slots, out,
        align_stub_new(ctx, ALIGN_STUB_TYPE_F32, ne0, ne1, ne2, 1),
        sa, NULL, ALIGN_STUB_OP_CONT);
}

int32_t align_ggml_op_rope_neox(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t pos,
    int32_t n_dims, int32_t mode, int32_t n_ctx_orig, int32_t freq_base_bits) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *sp = align_stub_slot(slots, pos);
    align_stub_tensor *t = NULL;
    if (sa == NULL || sp == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (mode != 2) {
        return ALIGN_GGML_SHAPE;
    }
    if (n_dims <= 0 || n_dims % 2 != 0 || (int64_t) n_dims > sa->ne[0] || n_ctx_orig <= 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (sp->ne[0] != sa->ne[2]) {
        return ALIGN_GGML_SHAPE;
    }
    t = align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[0], sa->ne[1], sa->ne[2], sa->ne[3]);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->ip[0] = n_dims;
    t->ip[1] = mode;
    t->ip[2] = n_ctx_orig;
    t->ip[3] = freq_base_bits;
    return align_stub_bind(slots, out, t, sa, sp, ALIGN_STUB_OP_ROPE);
}

/* R5D section 3.5: the one **widened** symbol, answered identically here. `mask == -1` is the
 * router's plain softmax; every other value is a slot index that must name a live tensor, so an
 * empty slot is still `ALIGN_GGML_SLOT` and never silently becomes an unmasked softmax.
 */
int32_t align_ggml_op_soft_max_ext(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t mask,
    int32_t scale_bits, int32_t max_bias_bits) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *sm = (mask == ALIGN_GGML_NO_MASK) ? NULL : align_stub_slot(slots, mask);
    align_stub_tensor *t = NULL;
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (sm == NULL && mask != ALIGN_GGML_NO_MASK) {
        return ALIGN_GGML_SLOT;
    }
    if (sm != NULL && sm->ne[0] < sa->ne[0]) {
        return ALIGN_GGML_SHAPE;
    }
    t = align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[0], sa->ne[1], sa->ne[2], sa->ne[3]);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->ip[0] = scale_bits;
    t->ip[1] = max_bias_bits;
    return align_stub_bind(slots, out, t, sa, sm, ALIGN_STUB_OP_SOFT_MAX);
}

int32_t align_ggml_op_swiglu_split(void *ctx, void *slots, int64_t out, int64_t a, int64_t b) {
    return align_stub_elementwise(ctx, slots, out, a, b, ALIGN_STUB_OP_SWIGLU);
}

/* R5B section 3.6's one new op, answered from the engine. The two forced builds below are section
 * 4.2's `pad` bounds cells: neither a negative pad nor an oversized result is producible from an
 * input, because `KV_WIDTH` is validated in `[token_count, MAX_ATTENTION_WIDTH]` before the table
 * is built, so the refusals are exercised by a build rather than reasoned about. Neither macro is
 * ever defined in an ordinary build.
 */
int32_t align_ggml_op_pad(void *ctx, void *slots, int64_t out, int64_t a,
                          int32_t p0, int32_t p1, int32_t p2, int32_t p3) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *t = NULL;
    int64_t ne[4];
    int i = 0;
#ifdef ALIGN_GGML_FORCE_PAD_NEGATIVE
    p1 = -1;
#endif
#ifdef ALIGN_GGML_FORCE_PAD_OVERSIZE
    p0 = ALIGN_GGML_MAX_PAD;
    p1 = ALIGN_GGML_MAX_PAD;
    p2 = ALIGN_GGML_MAX_PAD;
#endif
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (p0 < 0 || p1 < 0 || p2 < 0 || p3 < 0) {
        return ALIGN_GGML_SHAPE;
    }
    if (p0 > ALIGN_GGML_MAX_PAD || p1 > ALIGN_GGML_MAX_PAD
        || p2 > ALIGN_GGML_MAX_PAD || p3 > ALIGN_GGML_MAX_PAD) {
        return ALIGN_GGML_SHAPE;
    }
    ne[0] = sa->ne[0] + p0;
    ne[1] = sa->ne[1] + p1;
    ne[2] = sa->ne[2] + p2;
    ne[3] = sa->ne[3] + p3;
    for (i = 0; i < 4; i++) {
        if (ne[i] <= 0) {
            return ALIGN_GGML_SHAPE;
        }
    }
    if (ne[0] * ne[1] * ne[2] * ne[3] > ALIGN_GGML_MAX_PAD_ELEMENTS) {
        return ALIGN_GGML_SHAPE;
    }
    t = align_stub_new(ctx, ALIGN_STUB_TYPE_F32, ne[0], ne[1], ne[2], ne[3]);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_stub_bind(slots, out, t, sa, NULL, ALIGN_STUB_OP_PAD);
}

/* R6-DECODE-KV-STEP1 section 2.5's one new op, answered from the engine. Signature for signature
 * with `scripts/ggml_shim.c` and refusing the same inputs: the axis selector, the type agreement,
 * and the "every axis but `dim` must match" rule are restated here, because a stub that accepted a
 * shape the linked library refuses would let the hosted owner pass a table the qualification cannot
 * run.
 *
 * The forced build is section 4.5's `ds-stub-concat-axis` cell. A wrong axis is not producible from
 * any operand the decode table can supply — `dim` is a compiled-in column of the row, 1 for K and 0
 * for V — so the refusal is exercised by a build rather than reasoned about. It is never defined in
 * an ordinary build.
 */
int32_t align_ggml_op_concat(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t b, int32_t dim) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *sb = align_stub_slot(slots, b);
    align_stub_tensor *t = NULL;
    int64_t ne[4];
    int axis = 0;
#ifdef ALIGN_GGML_FORCE_CONCAT_AXIS
    dim = (dim == 0) ? 1 : 0;
#endif
    if (sa == NULL || sb == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (dim < 0 || dim > ALIGN_GGML_MAX_DIM_SELECTOR) {
        return ALIGN_GGML_INIT;
    }
    if (sa->type != sb->type) {
        return ALIGN_GGML_TYPE;
    }
    for (axis = 0; axis <= ALIGN_GGML_MAX_DIM_SELECTOR; axis++) {
        ne[axis] = sa->ne[axis];
        if (axis != (int) dim && sa->ne[axis] != sb->ne[axis]) {
            return ALIGN_GGML_SHAPE;
        }
    }
    ne[dim] = sa->ne[dim] + sb->ne[dim];
    if (ne[0] * ne[1] * ne[2] * ne[3] > ALIGN_GGML_MAX_PAD_ELEMENTS) {
        return ALIGN_GGML_SHAPE;
    }
    t = align_stub_new(ctx, sa->type, ne[0], ne[1], ne[2], ne[3]);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->ip[0] = (int32_t) dim;
    return align_stub_bind(slots, out, t, sa, sb, ALIGN_STUB_OP_CONCAT);
}

/* ---------------------------------------------------------------------------------------------
 * R5D-MOE-LAYER-FORWARD — the five new entry points, answered from the engine
 *
 * Signature for signature with `scripts/ggml_shim.c`, and refusing the same inputs: without them
 * the hosted owner would stop at the router and neither the routing-identity oracle nor the
 * compact-stack multiply would be reachable on a host with no ggml.
 * ------------------------------------------------------------------------------------------- */

int32_t align_ggml_op_argsort(void *ctx, void *slots, int64_t out, int64_t a, int32_t order) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *t = NULL;
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
#ifdef ALIGN_GGML_FORCE_ARGSORT_ORDER
    /* R5D section 4.2's `argsort order` cell: a third sort order, which the node table cannot
     * express because it carries `0` or `1` and `src/ggml_ffi.align` refuses anything else before
     * the call. Never defined in an ordinary build. */
    order = 7;
#endif
    if (order != ALIGN_GGML_SORT_ASC && order != ALIGN_GGML_SORT_DESC) {
        return ALIGN_GGML_INIT;
    }
    if (sa->type != ALIGN_STUB_TYPE_F32) {
        return ALIGN_GGML_TYPE;
    }
    t = align_stub_new(ctx, ALIGN_STUB_TYPE_I32, sa->ne[0], sa->ne[1], sa->ne[2], sa->ne[3]);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->ip[0] = order;
    return align_stub_bind(slots, out, t, sa, NULL, ALIGN_STUB_OP_ARGSORT);
}

int32_t align_ggml_op_mul_mat_id(
    void *ctx, void *slots, int64_t out, int64_t as_slot, int64_t b, int64_t ids) {
    align_stub_tensor *sa = align_stub_slot(slots, as_slot);
    align_stub_tensor *sb = align_stub_slot(slots, b);
    align_stub_tensor *si = align_stub_slot(slots, ids);
    if (sa == NULL || sb == NULL || si == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (sa->type != ALIGN_STUB_TYPE_F32 || sb->type != ALIGN_STUB_TYPE_F32) {
        return ALIGN_GGML_TYPE;
    }
    if (si->type != ALIGN_STUB_TYPE_I32) {
        return ALIGN_GGML_TYPE;
    }
    /* ggml's six shape assertions, re-stated before the engine runs so a malformed node table is a
     * status naming the row rather than an out-of-range read. */
    if (sa->ne[3] != 1 || sb->ne[3] != 1 || si->ne[2] != 1 || si->ne[3] != 1) {
        return ALIGN_GGML_SHAPE;
    }
    if (si->ne[1] != sb->ne[2] || sa->ne[0] != sb->ne[0]) {
        return ALIGN_GGML_SHAPE;
    }
    if (sb->ne[1] <= 0 || si->ne[0] <= 0 || si->ne[0] % sb->ne[1] != 0) {
        return ALIGN_GGML_SHAPE;
    }
    return align_stub_bind3(slots, out,
        align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[1], si->ne[0], sb->ne[2], 1),
        sa, sb, si, ALIGN_STUB_OP_MUL_MAT_ID);
}

/* The stride and the offset are derived from the source's **own** strides, exactly as the real
 * shim derives them from `a->nb[]`; an engine tensor is contiguous, so the strides are the products
 * of its extents. The extent test is the same strict one: the reachable span of a strided view is
 * `offset + (ne1 - 1) * nb1 + ne0 * 4`. The F32 source gate below is the same one too, since
 * correction C13 restated it in `scripts/ggml_shim.c`.
 */
int32_t align_ggml_op_view_2d(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t ne0, int64_t ne1,
    int32_t nb1_dim, int32_t offset_dim, int64_t offset_index) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *t = NULL;
    int64_t nb[4];
    int64_t nb1 = 0;
    int64_t offset = 0;
    int64_t span = 0;
    int i = 0;
    if (sa == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (nb1_dim < 0 || nb1_dim > ALIGN_GGML_MAX_DIM_SELECTOR
        || offset_dim < 0 || offset_dim > ALIGN_GGML_MAX_DIM_SELECTOR) {
        return ALIGN_GGML_INIT;
    }
#ifdef ALIGN_GGML_FORCE_VIEW_EXTENT
    /* R5D section 4.2's `view_2d extent` cell: a window that reads past its source, which the node
     * table cannot express because its extents are the geometry's. This is the class section 2.8's
     * strided-readback bug belonged to, made observable. Never defined in an ordinary build. */
    ne1 = ne1 * 64 + 1;
#endif
    if (ne0 <= 0 || ne1 <= 0 || offset_index < 0 || ne0 > sa->ne[0]) {
        return ALIGN_GGML_SHAPE;
    }
    if (sa->type != ALIGN_STUB_TYPE_F32) {
        return ALIGN_GGML_TYPE;
    }
    nb[0] = 4;
    for (i = 1; i < 4; i++) {
        nb[i] = nb[i - 1] * sa->ne[i - 1];
    }
    nb1 = nb[nb1_dim];
    offset = offset_index * nb[offset_dim];
    span = offset + (ne1 - 1) * nb1 + ne0 * 4;
    if (span < 0 || span > align_stub_nbytes(sa)) {
        return ALIGN_GGML_BOUNDS;
    }
    t = align_stub_new(ctx, ALIGN_STUB_TYPE_F32, ne0, ne1, 1, 1);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->lp[0] = nb1;
    t->lp[1] = offset;
    return align_stub_bind(slots, out, t, sa, NULL, ALIGN_STUB_OP_VIEW);
}

int32_t align_ggml_slot_new_tensor_3d(
    void *ctx, void *slots, int64_t out, int32_t type, int64_t ne0, int64_t ne1, int64_t ne2) {
    align_stub_tensor *t = NULL;
    if (align_ggml_table_row(type) < 0) {
        return ALIGN_GGML_TYPE;
    }
    t = align_stub_new(ctx, type, ne0, ne1, ne2, 1);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) t);
}

int32_t align_ggml_slot_new_strided_tensor_3d(
    void *ctx, void *slots, int64_t out, int32_t type,
    int64_t ne0, int64_t ne1, int64_t ne2, int64_t slice_stride) {
    align_stub_tensor *t = NULL;
    int row_index = -1;
    int64_t row_bytes = 0;
    int64_t plane_bytes = 0;
    if (align_stub_context_index(ctx) < 0) {
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
    if (ne0 / (int64_t) align_ggml_type_table[row_index][1]
        > INT64_MAX / (int64_t) align_ggml_type_table[row_index][2]) {
        return ALIGN_GGML_SHAPE;
    }
    row_bytes = ne0 / (int64_t) align_ggml_type_table[row_index][1]
        * (int64_t) align_ggml_type_table[row_index][2];
    if (ne1 > INT64_MAX / row_bytes) {
        return ALIGN_GGML_SHAPE;
    }
    plane_bytes = row_bytes * ne1;
    if (slice_stride < plane_bytes
        || ne2 - 1 > (INT64_MAX - plane_bytes) / slice_stride
        || ne2 > INT64_MAX / slice_stride) {
        return ALIGN_GGML_SHAPE;
    }
    t = align_stub_new(ctx, type, ne0, ne1, ne2, 1);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    t->lp[0] = slice_stride;
    return align_ggml_slot_store(slots, out, (void *) t);
}

int32_t align_ggml_slot_new_i32_2d(void *ctx, void *slots, int64_t out, int64_t ne0, int64_t ne1) {
    align_stub_tensor *t = align_stub_new(ctx, ALIGN_STUB_TYPE_I32, ne0, ne1, 1, 1);
    if (t == NULL) {
        return ALIGN_GGML_INIT;
    }
    return align_ggml_slot_store(slots, out, (void *) t);
}

int64_t align_ggml_graph_context_bytes(int64_t node_capacity) {
    if (node_capacity <= 0 || node_capacity > (int64_t) 65536) {
        return -1;
    }
    return node_capacity * (int64_t) sizeof(align_stub_tensor) + 4096;
}

void *align_ggml_graph_new(void *ctx) {
    int32_t i = 0;
    if (align_stub_context_index(ctx) < 0) {
        return NULL;
    }
    for (i = 0; i < ALIGN_STUB_MAX_GRAPHS; i++) {
        if (!align_stub_graphs[i].used) {
            memset(&align_stub_graphs[i], 0, sizeof(align_stub_graphs[i]));
            align_stub_graphs[i].used = 1;
            return (void *) &align_stub_graphs[i];
        }
    }
    return NULL;
}

/* R8-OLMOE-PHASE-A-OPERATION-DIAGNOSIS. Match the real shim's borrowed contiguous graph views;
 * the deterministic engine's graph pool stands in for the context-owned ggml graph metadata.
 */
void *align_ggml_graph_partition(void *ctx, void *graph, void *slots,
                                 int64_t boundary_slot, int32_t suffix) {
    align_stub_graph *source = (align_stub_graph *) graph;
    align_stub_graph *result = NULL;
    align_stub_tensor *boundary = align_stub_slot(slots, boundary_slot);
    int32_t boundary_at = -1;
    int32_t matches = 0;
    int32_t start = 0;
    int32_t end = 0;
    int32_t i = 0;

    if (align_stub_context_index(ctx) < 0 || source == NULL || boundary == NULL ||
        (suffix != 0 && suffix != 1) || source->count < 2) {
        return NULL;
    }
    for (i = 0; i < source->count; i++) {
        if (source->nodes[i] == boundary) {
            boundary_at = i;
            matches++;
        }
    }
    if (matches != 1 || boundary_at < 0 || boundary_at >= source->count - 1) {
        return NULL;
    }
    result = (align_stub_graph *) align_ggml_graph_new(ctx);
    if (result == NULL) {
        return NULL;
    }
    start = suffix ? boundary_at + 1 : 0;
    end = suffix ? source->count : boundary_at + 1;
    for (i = start; i < end; i++) {
        if (result->count >= ALIGN_STUB_MAX_TENSORS) {
            result->used = 0;
            result->count = 0;
            return NULL;
        }
        result->nodes[result->count] = source->nodes[i];
        result->count++;
    }
    return (void *) result;
}

/* R8-OLMOE-ATTENTION-OPERATION-DIAGNOSIS. Match the real shim's exact slot-membership selection
 * while retaining the source graph's dependency order.
 */
void *align_ggml_graph_select_slot_range(void *ctx, void *graph, void *slots,
                                         int64_t first_slot, int64_t last_slot) {
    align_stub_graph *source = (align_stub_graph *) graph;
    align_stub_graph *result = NULL;
    int64_t capacity = 0;
    int64_t requested = 0;
    int64_t slot = 0;
    int32_t selected = 0;
    int32_t i = 0;

    capacity = align_ggml_slot_capacity(slots);
    if (align_stub_context_index(ctx) < 0 || source == NULL || capacity < 0 || first_slot < 0 ||
        last_slot < first_slot || last_slot >= capacity) {
        return NULL;
    }
    for (slot = first_slot; slot <= last_slot; slot++) {
        align_stub_tensor *target = align_stub_slot(slots, slot);
        int32_t matches = 0;
        if (target == NULL) {
            continue;
        }
        for (i = 0; i < source->count; i++) {
            if (source->nodes[i] == target) {
                matches++;
            }
        }
        if (matches != 1) {
            return NULL;
        }
        requested++;
    }
    if (requested <= 0 || requested > source->count) {
        return NULL;
    }
    result = (align_stub_graph *) align_ggml_graph_new(ctx);
    if (result == NULL) {
        return NULL;
    }
    for (i = 0; i < source->count; i++) {
        for (slot = first_slot; slot <= last_slot; slot++) {
            if (source->nodes[i] == align_stub_slot(slots, slot)) {
                if (result->count >= ALIGN_STUB_MAX_TENSORS) {
                    result->used = 0;
                    result->count = 0;
                    return NULL;
                }
                result->nodes[result->count] = source->nodes[i];
                result->count++;
                selected++;
                break;
            }
        }
    }
    if (selected != requested) {
        result->used = 0;
        result->count = 0;
        return NULL;
    }
    return (void *) result;
}

/* `ggml_build_forward_expand`'s shape: a post-order walk that visits each source once and appends
 * every op tensor in dependency order. Leaves — the weights and the three inputs — are not nodes.
 */
static int32_t align_stub_expand(align_stub_graph *graph, align_stub_tensor *t) {
    int i = 0;
    if (t == NULL || t->visited) {
        return ALIGN_GGML_OK;
    }
    t->visited = 1;
    for (i = 0; i < 3; i++) {
        int32_t status = align_stub_expand(graph, t->src[i]);
        if (status != ALIGN_GGML_OK) {
            return status;
        }
    }
    if (t->op == ALIGN_STUB_OP_NONE) {
        return ALIGN_GGML_OK;
    }
    if (graph->count >= ALIGN_STUB_MAX_TENSORS) {
        return ALIGN_GGML_ALLOC;
    }
    graph->nodes[graph->count] = t;
    graph->count++;
    return ALIGN_GGML_OK;
}

int32_t align_ggml_graph_expand(void *graph, void *slots, int64_t index) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    int32_t i = 0;
    if (graph == NULL) {
        return ALIGN_GGML_INIT;
    }
    if (t == NULL) {
        return ALIGN_GGML_SLOT;
    }
    for (i = 0; i < align_stub_tensor_count; i++) {
        align_stub_tensors[i].visited = 0;
    }
    return align_stub_expand((align_stub_graph *) graph, t);
}

int32_t align_ggml_graph_node_count(void *graph) {
    if (graph == NULL) {
        return ALIGN_GGML_INIT;
    }
    return ((align_stub_graph *) graph)->count;
}

void *align_ggml_gallocr_new(void *backend) {
    int32_t i = 0;
    if (backend == NULL) {
        return NULL;
    }
    for (i = 0; i < ALIGN_STUB_MAX_GALLOCRS; i++) {
        if (!align_stub_gallocrs[i].used) {
            align_stub_gallocrs[i].used = 1;
            align_stub_gallocrs[i].bytes = 0;
            return (void *) &align_stub_gallocrs[i];
        }
    }
    return NULL;
}

/* The reuse plan, which is the whole reason `reserve` and `alloc` are two passes over one
 * algorithm (section 6, correction C18).
 *
 * The engine used to bump-allocate one block per node and never reuse one. That made the hosted
 * owner blind to the single most consequential mistake this design can make: an oracle node that
 * `mark_outputs` forgets is, under a real `ggml_gallocr`, handed to a later node and the bytes read
 * back are not the bytes computed. Section 5.6 names that risk and the probe hit it for real, but
 * with a bump allocator every golden still passed.
 *
 * So the engine does what `ggml_gallocr` does. A node's block is returned to a free list once its
 * last consumer has run, unless `ggml_set_output` marked it, and the next node that fits takes it.
 * Allocation happens **before** the frees for that node, so a node never aliases its own source.
 * First fit by lowest offset keeps the plan deterministic, which the golden corpus requires.
 *
 * `base == NULL` measures and returns the peak; a non-NULL base assigns `t->data` from the same
 * walk, so the number `align_ggml_gallocr_bytes` publishes is the number that was allocated.
 * A negative return is a refusal: too many nodes, too many live blocks, or an empty tensor.
 */
#define ALIGN_STUB_MAX_FREE 256

static int64_t align_stub_plan(align_stub_graph *g, unsigned char *base) {
    static int64_t last_use[ALIGN_STUB_MAX_TENSORS];
    static int64_t block_offset[ALIGN_STUB_MAX_TENSORS];
    static int64_t block_size[ALIGN_STUB_MAX_TENSORS];
    static int64_t free_offset[ALIGN_STUB_MAX_FREE];
    static int64_t free_size[ALIGN_STUB_MAX_FREE];
    int32_t free_count = 0;
    int64_t peak = 0;
    int32_t i = 0;
    int32_t j = 0;
    int32_t k = 0;
    if (g->count > ALIGN_STUB_MAX_TENSORS) {
        return -1;
    }
    for (i = 0; i < g->count; i++) {
        last_use[i] = -1;
        block_offset[i] = -1;
        block_size[i] = 0;
    }
    for (j = 0; j < g->count; j++) {
        for (k = 0; k < 3; k++) {
            align_stub_tensor *source = g->nodes[j]->src[k];
            if (source == NULL) {
                continue;
            }
            for (i = 0; i < j; i++) {
                if (g->nodes[i] == source) {
                    last_use[i] = j;
                    break;
                }
            }
        }
    }
    for (i = 0; i < g->count; i++) {
        align_stub_tensor *t = g->nodes[i];
        int64_t need = (align_stub_nbytes(t) + 63) / 64 * 64;
        int32_t pick = -1;
        if (t->data != NULL) {
            continue;
        }
        if (need <= 0) {
            return -1;
        }
        for (j = 0; j < free_count; j++) {
            if (free_size[j] < need) {
                continue;
            }
            if (pick < 0 || free_offset[j] < free_offset[pick]) {
                pick = j;
            }
        }
        if (pick >= 0) {
            block_offset[i] = free_offset[pick];
            if (free_size[pick] > need) {
                free_offset[pick] += need;
                free_size[pick] -= need;
            } else {
                free_offset[pick] = free_offset[free_count - 1];
                free_size[pick] = free_size[free_count - 1];
                free_count--;
            }
        } else {
            block_offset[i] = peak;
            peak += need;
        }
        block_size[i] = need;
        if (base != NULL) {
            t->data = base + block_offset[i];
        }
        for (j = 0; j < i; j++) {
            if (last_use[j] != i || block_offset[j] < 0 || g->nodes[j]->is_output) {
                continue;
            }
            if (free_count >= ALIGN_STUB_MAX_FREE) {
                return -1;
            }
            free_offset[free_count] = block_offset[j];
            free_size[free_count] = block_size[j];
            free_count++;
            block_offset[j] = -1;
        }
    }
    return peak;
}

/* `reserve` measures and `alloc` assigns, so the two are not one bump allocation counted twice and
 * `align_ggml_gallocr_bytes` is a number the golden document can carry.
 */
int32_t align_ggml_gallocr_reserve(void *galloc, void *graph) {
    align_stub_graph *g = (align_stub_graph *) graph;
    int64_t total = 0;
    if (galloc == NULL || g == NULL) {
        return ALIGN_GGML_INIT;
    }
#ifdef ALIGN_GGML_FORCE_ALLOC_FAILURE
    return ALIGN_GGML_ALLOC;
#endif
    total = align_stub_plan(g, NULL);
    if (total < 0) {
        return ALIGN_GGML_ALLOC;
    }
    ((align_stub_gallocr *) galloc)->bytes = total;
    return ALIGN_GGML_OK;
}

int32_t align_ggml_gallocr_alloc(void *galloc, void *graph) {
    align_stub_graph *g = (align_stub_graph *) graph;
    unsigned char *base = NULL;
    int64_t total = 0;
    if (galloc == NULL || g == NULL) {
        return ALIGN_GGML_INIT;
    }
    total = align_stub_plan(g, NULL);
    if (total < 0) {
        return ALIGN_GGML_ALLOC;
    }
    base = align_stub_reserve(total);
    if (base == NULL) {
        return ALIGN_GGML_ALLOC;
    }
    if (align_stub_plan(g, base) < 0) {
        return ALIGN_GGML_ALLOC;
    }
    return ALIGN_GGML_OK;
}

int64_t align_ggml_gallocr_bytes(void *galloc) {
    if (galloc == NULL) {
        return -1;
    }
    return ((align_stub_gallocr *) galloc)->bytes;
}

void align_ggml_gallocr_free(void *galloc) {
    if (galloc != NULL) {
        ((align_stub_gallocr *) galloc)->used = 0;
    }
}

int32_t align_ggml_graph_compute(void *backend, void *graph) {
    align_stub_graph *g = (align_stub_graph *) graph;
    int32_t i = 0;
    if (backend == NULL || g == NULL) {
        return ALIGN_GGML_COMPUTE_NULL;
    }
#ifdef ALIGN_GGML_FORCE_COMPUTE_FAILURE
    /* Section 4.6: a non-success status from an engine that is working correctly. */
    return 2;
#endif
#ifdef ALIGN_GGML_FORCE_COMPUTE_STEP2
    /* R6-STEP-N section 4.1. The same non-success status, withheld until the plane has grown once. */
    if (align_force_compute_step2) {
        return 2;
    }
#endif
#ifdef ALIGN_GGML_FORCE_COMPUTE_SUFFIX
    /* R6-PREFIX-SUFFIX-PREFILL section 4.1's `failure` cell: the same non-success status, withheld
     * until a graph computes more than one column at `n_past > 0`. It therefore fires inside the
     * suffix pass, in no prefill, and in no decode step — which is what makes the document it
     * produces a statement about a partial **pass**. */
    if (align_force_suffix_pass) {
        return 2;
    }
#endif
    for (i = 0; i < g->count; i++) {
        if (g->nodes[i]->data == NULL) {
            return ALIGN_GGML_ALLOC;
        }
        align_stub_run(g->nodes[i]);
    }
    return 0;
}
