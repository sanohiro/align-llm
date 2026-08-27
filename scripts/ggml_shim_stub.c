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
 * golden corpus is the detector.
 */
#if defined(__clang__) || (defined(__GNUC__) && __GNUC__ >= 14)
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

/* --- END R4.5 SHARED SHIM CONTRACT --- */

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
#define ALIGN_STUB_ARENA_BYTES (4 * 1024 * 1024)

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

typedef struct align_stub_tensor {
    int32_t type;
    int64_t ne[4];
    unsigned char *data;
    int32_t op;
    struct align_stub_tensor *src[2];
    int32_t ip[4];
    int64_t lp[3];
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

typedef struct align_stub_buffer {
    unsigned char *base;
    int64_t size;
    int32_t used;
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
    case ALIGN_STUB_OP_GET_ROWS: {
        const int32_t *rows = (const int32_t *) b->data;
        for (i1 = 0; i1 < t->ne[1]; i1++) {
            int64_t row = (int64_t) rows[i1];
            if (row < 0 || row >= a->ne[1]) {
                row = 0;
            }
            memcpy(d + i1 * t->ne[0], x + row * a->ne[0], (size_t) t->ne[0] * 4);
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
                    const float *mask = y + b->ne[0] * (i1 % b->ne[1]);
                    float highest = -INFINITY;
                    float total = 0.0f;
                    for (i0 = 0; i0 < t->ne[0]; i0++) {
                        float value = x[base + i0] * scale + mask[i0];
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

void *align_ggml_backend_open(void *device) {
    if (device == NULL) {
        return NULL;
    }
    align_stub_backend_token = 1;
    return (void *) &align_stub_backend_token;
}

int32_t align_ggml_backend_name(void *backend, void *out, int32_t cap) {
    static const char name[] = "stub-cpu";
    int32_t length = (int32_t) (sizeof(name) - 1);
    if (backend == NULL || out == NULL || cap <= 0) {
        return 0;
    }
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

/* The whole engine, reclaimed once nothing points into it. A caller that leaks a context or a
 * buffer simply never triggers it and exhausts a pool instead, which is the failure this file
 * should report rather than hide. */
static void align_stub_reset_if_idle(void) {
    int32_t i = 0;
    for (i = 0; i < ALIGN_STUB_MAX_CONTEXTS; i++) {
        if (align_stub_context_used[i]) {
            return;
        }
    }
    for (i = 0; i < ALIGN_STUB_MAX_BUFFERS; i++) {
        if (align_stub_buffers[i].used) {
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
    if (device == NULL || ptr == NULL || size <= 0) {
        return NULL;
    }
    if (align_ptr_align_mod(ptr, (int64_t) ALIGN_GGML_TENSOR_ALIGNMENT) != 0) {
        return NULL;
    }
    for (i = 0; i < ALIGN_STUB_MAX_BUFFERS; i++) {
        if (!align_stub_buffers[i].used) {
            align_stub_buffers[i].used = 1;
            align_stub_buffers[i].base = (unsigned char *) ptr;
            align_stub_buffers[i].size = size;
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
    return align_stub_nbytes(t);
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
    return status;
}

int32_t align_ggml_slot_get(void *slots, int64_t index, void *bytes, int64_t off, int64_t n) {
    align_stub_tensor *t = align_stub_slot(slots, index);
    if (t == NULL) {
        return ALIGN_GGML_SLOT;
    }
    return align_ggml_tensor_get((void *) t, bytes, off, n);
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
    return align_ggml_slot_store(slots, out, (void *) t);
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
    return align_stub_bind(slots, out,
        align_stub_new(ctx, ALIGN_STUB_TYPE_F32, sa->ne[0], sb->ne[0], 1, 1),
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

int32_t align_ggml_op_soft_max_ext(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t mask,
    int32_t scale_bits, int32_t max_bias_bits) {
    align_stub_tensor *sa = align_stub_slot(slots, a);
    align_stub_tensor *sm = align_stub_slot(slots, mask);
    align_stub_tensor *t = NULL;
    if (sa == NULL || sm == NULL) {
        return ALIGN_GGML_SLOT;
    }
    if (sm->ne[0] < sa->ne[0]) {
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

/* `ggml_build_forward_expand`'s shape: a post-order walk that visits each source once and appends
 * every op tensor in dependency order. Leaves — the weights and the three inputs — are not nodes.
 */
static int32_t align_stub_expand(align_stub_graph *graph, align_stub_tensor *t) {
    int i = 0;
    if (t == NULL || t->visited) {
        return ALIGN_GGML_OK;
    }
    t->visited = 1;
    for (i = 0; i < 2; i++) {
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
        for (k = 0; k < 2; k++) {
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
    for (i = 0; i < g->count; i++) {
        if (g->nodes[i]->data == NULL) {
            return ALIGN_GGML_ALLOC;
        }
        align_stub_run(g->nodes[i]);
    }
    return 0;
}
