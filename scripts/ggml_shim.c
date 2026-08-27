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
 *  2. **Nothing here allocates memory the document describes.** It reserves no heap, opens no
 *     path, and reads no byte the caller did not hand over. Every byte ggml computes over came from
 *     an Align `buffer` filled by `f.pread`, which is what makes "Align owns the buffer" true
 *     rather than nominal.
 *  3. **Fail closed before ggml can abort.** `ggml_backend_cpu_buffer_from_ptr` calls `abort()`
 *     through `GGML_ASSERT` on a pointer that is not `TENSOR_ALIGNMENT`-aligned (section 2.4), so
 *     every pointer and every size is validated here, in C, before the call that would assert.
 *  4. **No `struct ggml_tensor` field is read directly.** Its layout is private; `ggml_get_data`,
 *     `ggml_nbytes`, and `ggml_blck_size` are the accessors, which is the third of section 5.6's
 *     ABI-drift mitigations.
 *
 * Built by the `Makefile`'s `build/lib/libalign_ggml_shim.$(SHIM_SUFFIX)` rule when
 * `ALIGN_LLM_GGML_INCLUDE` is set; `scripts/ggml_shim_stub.c` is built instead when it is not.
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"

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
 */
static ggml_backend_dev_t align_ggml_cpu_device(void) {
    static int loaded = 0;
    if (!loaded) {
        ggml_backend_load_all();
        loaded = 1;
    }
    return ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
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
    int32_t alignment = 0;
    if (device == NULL || ptr == NULL || size <= 0) {
        return NULL;
    }
    alignment = align_ggml_tensor_alignment();
    if (alignment <= 0) {
        return NULL;
    }
    if (align_ptr_align_mod(ptr, (int64_t) alignment) != 0) {
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
    if (status == ALIGN_GGML_OK && index >= 0 && index <= 12) {
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

int32_t align_ggml_op_soft_max_ext(
    void *ctx, void *slots, int64_t out, int64_t a, int64_t mask,
    int32_t scale_bits, int32_t max_bias_bits) {
    struct ggml_tensor *sm = align_ggml_slot_tensor(slots, mask);
    ALIGN_GGML_OP_PROLOGUE_1(ctx, slots, a)
    if (sm == NULL) {
        return ALIGN_GGML_SLOT;
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
