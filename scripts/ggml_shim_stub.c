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

#include <stddef.h>
#include <stdint.h>

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
/* --- END R4.5 SHARED SHIM CONTRACT --- */

/* ---------------------------------------------------------------------------------------------
 * Availability, the ABI probe, and the type predicate — the four entry points the stub answers
 * ------------------------------------------------------------------------------------------- */

/* The **only** difference a caller can observe before any state exists (section 3.4). */
int32_t align_ggml_available(void) {
    return 0;
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
 * Construction, placement, compute, and teardown — unreachable, and total anyway
 *
 * Every one of these is behind the availability gate, so nothing below runs in a stub build. They
 * are written as total no-ops rather than omitted because the Align declaration block names one
 * library and every symbol in it must resolve at link time, and because a stub that aborted on an
 * ordering mistake would be a worse test than one that reports it.
 * ------------------------------------------------------------------------------------------- */

void *align_ggml_device_open(void) {
    return NULL;
}

void *align_ggml_backend_open(void *device) {
    (void) device;
    return NULL;
}

int32_t align_ggml_backend_name(void *backend, void *out, int32_t cap) {
    (void) backend;
    (void) out;
    (void) cap;
    return 0;
}

void align_ggml_backend_close(void *backend) {
    (void) backend;
}

void *align_ggml_context_open(int64_t mem_bytes) {
    (void) mem_bytes;
    return NULL;
}

void align_ggml_context_close(void *ctx) {
    (void) ctx;
}

/* Validates identically to the real shim, then reports unavailable (section 4.4). */
void *align_ggml_buffer_from_host(void *device, void *ptr, int64_t size) {
    (void) device;
    if (ptr == NULL || size <= 0) {
        return NULL;
    }
    if (align_ptr_align_mod(ptr, (int64_t) ALIGN_GGML_TENSOR_ALIGNMENT) != 0) {
        return NULL;
    }
    return NULL;
}

void align_ggml_buffer_free(void *buffer) {
    (void) buffer;
}

void *align_ggml_new_tensor_2d(void *ctx, int32_t type, int64_t ne0, int64_t ne1) {
    (void) ctx;
    (void) type;
    (void) ne0;
    (void) ne1;
    return NULL;
}

int32_t align_ggml_tensor_place(void *buffer, void *tensor, void *addr) {
    (void) buffer;
    (void) tensor;
    if (addr != NULL
        && align_ptr_align_mod(addr, (int64_t) ALIGN_GGML_TENSOR_ALIGNMENT) != 0) {
        return ALIGN_GGML_ALIGNMENT;
    }
    return ALIGN_GGML_UNAVAILABLE;
}

void *align_ggml_alloc_remaining(void *ctx, void *backend) {
    (void) ctx;
    (void) backend;
    return NULL;
}

/* Bounds-checked against the caller's declared size, which is all a ggml-free build can know. */
int32_t align_ggml_tensor_set(void *tensor, const void *data, int64_t offset, int64_t size) {
    (void) tensor;
    if (data == NULL || offset < 0 || size <= 0) {
        return ALIGN_GGML_INIT;
    }
    return ALIGN_GGML_UNAVAILABLE;
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
    (void) tensor;
    if (out == NULL || offset < 0 || size <= 0) {
        return ALIGN_GGML_INIT;
    }
    return ALIGN_GGML_UNAVAILABLE;
}

int64_t align_ggml_tensor_nbytes(void *tensor) {
    (void) tensor;
    return -1;
}

int64_t align_ggml_tensor_data_offset(void *tensor, const void *base) {
    (void) tensor;
    (void) base;
    return -1;
}
