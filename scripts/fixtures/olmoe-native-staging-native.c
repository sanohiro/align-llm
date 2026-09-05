/* Test-owned byte oracle and allocations. Both implementations are linked as separate translation
 * units; no test macro changes the candidate's architecture dispatch or byte-copy implementation. */
#define _GNU_SOURCE 1
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#ifndef MAP_ANONYMOUS
#define MAP_ANONYMOUS MAP_ANON
#endif

typedef int32_t (*Stage)(const void *, int64_t, int64_t, int64_t, void *, int64_t,
                         int64_t, int64_t, int64_t);
extern int32_t align_ggml_stage_kv(const void *, int64_t, int64_t, int64_t, void *, int64_t,
                                  int64_t, int64_t, int64_t);
extern int32_t control_stage_kv(const void *, int64_t, int64_t, int64_t, void *, int64_t,
                                int64_t, int64_t, int64_t);
extern int32_t align_ggml_available(void);

static const Stage implementations[] = {align_ggml_stage_kv, control_stage_kv};
static size_t allocations;
static size_t mappings;

static void require(int condition, const char *label) {
    if (!condition) {
        fprintf(stderr, "Native staging failure: %s\n", label);
        exit(1);
    }
}

static unsigned char *allocate(size_t bytes) {
    void *result = NULL;
    require(posix_memalign(&result, 64, bytes) == 0 && result != NULL, "test allocation");
    allocations++;
    return result;
}

static void release(void *pointer) {
    require(pointer != NULL && allocations > 0, "test allocation balance");
    free(pointer);
    allocations--;
}

static const uint32_t bits[] = {
    0x00000000u, 0x80000000u, 0x00000001u, 0x80000001u, 0x007fffffu, 0x807fffffu,
    0x00800000u, 0x80800000u, 0x7f7fffffu, 0xff7fffffu, 0x7f800000u, 0xff800000u,
    0x7fc00001u, 0xffc12345u, 0x7f800001u, 0xff812345u, 0x12345678u, 0xdeadbeefu,
};

static void fill(unsigned char *destination, size_t bytes, size_t salt) {
    for (size_t at = 0; at < bytes; at += 4) {
        size_t index = at / 4;
        size_t count = sizeof(bits) / sizeof(bits[0]);
        uint32_t value = index < count ? bits[(index + salt) % count]
            : ((uint32_t) (index + salt) * UINT32_C(0x9e3779b9)) ^ UINT32_C(0xa5c31f07);
        memcpy(destination + at, &value, 4);
    }
}

/* Traverse canonical source order and scatter each byte independently. This oracle uses neither
 * the candidate's tile coordinates/shuffles nor the control's head/lane/column loop order. */
static void oracle(unsigned char *destination, const unsigned char *plane, size_t k, size_t v,
                   size_t d, size_t h, size_t n) {
    size_t b = 4 * d * h * n;
    for (size_t c = 0; c < n; c++) {
        for (size_t head = 0; head < h; head++) {
            for (size_t lane = 0; lane < d; lane++) {
                size_t source = ((c * h + head) * d + lane) * 4;
                size_t to_k = ((head * n + c) * d + lane) * 4;
                size_t to_v = b + ((head * d + lane) * n + c) * 4;
                for (size_t byte = 0; byte < 4; byte++) {
                    destination[to_k + byte] = plane[k + source + byte];
                    destination[to_v + byte] = plane[v + source + byte];
                }
            }
        }
    }
}

static void image_case(size_t d, size_t h, size_t n, size_t source_shift, size_t stage_shift,
                       int overlap_sources) {
    size_t b = 4 * d * h * n;
    size_t k = 16;
    size_t v = overlap_sources == 2 ? k : overlap_sources ? k + b / 2 : k + b + 32;
    size_t plane_bytes = v + b + 32;
    size_t source_bytes = 32 + source_shift + plane_bytes + 32;
    size_t output_bytes = 32 + stage_shift + 2 * b + 32;
    unsigned char *source = allocate(source_bytes), *saved = allocate(source_bytes);
    unsigned char *output = allocate(output_bytes), *expected = allocate(2 * b);
    unsigned char *plane = source + 32 + source_shift;
    unsigned char *stage = output + 32 + stage_shift;
    memset(source, 0xa7, source_bytes);
    fill(plane + k, b, 0);
    fill(plane + v, b, 9);
    memcpy(saved, source, source_bytes);
    oracle(expected, plane, k, v, d, h, n);
    for (size_t which = 0; which < 2; which++) {
        memset(output, 0xcd, output_bytes);
        require(implementations[which](plane, (int64_t) plane_bytes, (int64_t) k, (int64_t) v,
                stage, (int64_t) (2 * b), (int64_t) d, (int64_t) h, (int64_t) n) == 0,
                "valid exported stage call");
        require(memcmp(stage, expected, b) == 0, "k_block_copy_unchanged");
        require(memcmp(stage + b, expected + b, b) == 0, "scalar_reference_parity");
        require(memcmp(source, saved, source_bytes) == 0, "source_unchanged");
        for (size_t at = 0; at < output_bytes; at++) {
            if (at < 32 + stage_shift || at >= 32 + stage_shift + 2 * b)
                require(output[at] == 0xcd, "stage_sentinels");
        }
    }
    release(expected); release(output); release(saved); release(source);
}

static void admitted_alias(size_t k, size_t v, size_t destination) {
    enum { D = 5, H = 2, N = 2, B = 80, SPAN = 512 };
    unsigned char *storage = allocate(SPAN), *saved = allocate(SPAN);
    unsigned char *expected = allocate(SPAN), *stage = allocate(2 * B);
    memset(storage, 0xa7, SPAN);
    fill(storage + k, B, 1);
    fill(storage + v, B, 7);
    memcpy(saved, storage, SPAN);
    oracle(stage, saved, k, v, D, H, N);
    memcpy(expected, saved, SPAN);
    memcpy(expected + destination, stage, 2 * B);
    for (size_t which = 0; which < 2; which++) {
        memcpy(storage, saved, SPAN);
        require(implementations[which](storage, SPAN, (int64_t) k, (int64_t) v,
                storage + destination, 2 * B, D, H, N) == 0, "used-span alias admission");
        require(memcmp(storage, expected, SPAN) == 0, "admitted alias byte image");
        require(memcmp(storage + k, saved + k, B) == 0
                && memcmp(storage + v, saved + v, B) == 0, "used source spans unchanged");
    }
    release(stage); release(expected); release(saved); release(storage);
}

typedef struct Call {
    const void *plane;
    int64_t plane_bytes, k, v;
    void *stage;
    int64_t stage_bytes, d, h, n;
} Call;

static unsigned char refusal_plane[1024], refusal_stage[1024];

static void refused(Call call, int32_t status, const char *label) {
    unsigned char plane_before[sizeof(refusal_plane)], stage_before[sizeof(refusal_stage)];
    memcpy(plane_before, refusal_plane, sizeof(plane_before));
    memcpy(stage_before, refusal_stage, sizeof(stage_before));
    for (size_t which = 0; which < 2; which++) {
        require(implementations[which](call.plane, call.plane_bytes, call.k, call.v, call.stage,
                call.stage_bytes, call.d, call.h, call.n) == status, label);
        require(memcmp(refusal_plane, plane_before, sizeof(plane_before)) == 0
                && memcmp(refusal_stage, stage_before, sizeof(stage_before)) == 0,
                "refusal preserves every source/destination sentinel");
    }
}

static void refusals(void) {
    memset(refusal_plane, 0xa7, sizeof(refusal_plane));
    memset(refusal_stage, 0xcd, sizeof(refusal_stage));
    Call valid = {refusal_plane + 128, 512, 32, 160, refusal_stage + 32, 96, 2, 2, 3};
    Call bad = valid;
    bad.plane = NULL; bad.d = INT64_MAX; bad.h = -1; bad.stage_bytes = -1;
    refused(bad, -6, "null_precedence");
    bad = valid; bad.stage = NULL; bad.plane_bytes = -1; bad.n = 0;
    refused(bad, -6, "null_precedence");
    bad.plane = NULL;
    refused(bad, -6, "null_precedence");
    for (int field = 0; field < 7; field++) {
        bad = valid;
        int64_t *fields[] = {&bad.plane_bytes, &bad.k, &bad.v, &bad.stage_bytes,
                            &bad.d, &bad.h, &bad.n};
        *fields[field] = -1;
        refused(bad, -7, "scalar_bounds");
        if (field >= 4) {
            *fields[field] = 0;
            refused(bad, -7, "scalar_bounds");
        }
    }
    const int64_t products[][3] = {
        {INT64_MAX, 2, 1}, {INT64_MAX / 2, 1, 3},
        {INT64_MAX / 4 + 1, 1, 1}, {INT64_MAX / 8 + 1, 1, 1},
    };
    for (size_t i = 0; i < sizeof(products) / sizeof(products[0]); i++) {
        bad = valid; bad.d = products[i][0]; bad.h = products[i][1]; bad.n = products[i][2];
        refused(bad, -7, "product_overflow");
    }
    for (int delta = -1; delta <= 1; delta += 2) {
        bad = valid; bad.stage_bytes += delta;
        refused(bad, -7, "stage_exact_size");
    }
    for (int source = 0; source < 2; source++) {
        bad = valid;
        if (source) bad.v = 465; else bad.k = 465;
        refused(bad, -7, "source_bounds: one byte short");
        if (source) bad.v = 513; else bad.k = 513;
        refused(bad, -7, "source_bounds: base beyond plane");
    }
    bad = valid; bad.plane = (const void *) (UINTPTR_MAX - 511);
    refused(bad, -7, "pointer_extent: plane");
    bad = valid; bad.stage = (void *) (UINTPTR_MAX - 95);
    refused(bad, -7, "pointer_extent: stage");
    bad = valid; bad.plane_bytes = INT64_MAX; bad.plane = (const void *) (UINTPTR_MAX - 1024);
    refused(bad, -7, "pointer_extent: declared whole plane");
    const int64_t overlaps[] = {32, 32 - 95, 32 + 47, 160, 160 - 95, 160 + 47};
    for (size_t i = 0; i < sizeof(overlaps) / sizeof(overlaps[0]); i++) {
        bad = valid; bad.stage = refusal_plane + 128 + overlaps[i];
        refused(bad, -7, "destination_overlap_refused");
    }
#if SIZE_MAX < INT64_MAX
    bad = valid; bad.plane_bytes = (int64_t) SIZE_MAX + 1;
    refused(bad, -7, "SIZE_MAX plane extent");
    bad = valid; bad.d = (int64_t) SIZE_MAX / 8 + 1; bad.h = 1; bad.n = 1;
    bad.plane_bytes = bad.stage_bytes = bad.d * 8; bad.k = bad.v = 0;
    refused(bad, -7, "SIZE_MAX stage extent");
#else
    puts("N/A SIZE_MAX-only refusal: nonnegative signed-i64 lengths fit size_t on this 64-bit host");
#endif
}

static unsigned char *map_guarded(size_t bytes) {
    void *memory = mmap(NULL, bytes, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    require(memory != MAP_FAILED, "guard mapping");
    mappings++;
    return memory;
}

static void unmap_guarded(void *memory, size_t bytes) {
    require(munmap(memory, bytes) == 0 && mappings > 0, "guard mapping release");
    mappings--;
}

static void guarded_case(size_t d, size_t h, size_t n, int at_end) {
    size_t b = 4 * d * h * n;
    long page_result = sysconf(_SC_PAGESIZE);
    require(page_result > 0, "host page size");
    size_t page = (size_t) page_result;
    size_t span = (b + page - 1) / page * page;
    size_t stage_span = (2 * b + page - 1) / page * page;
    size_t source_map_bytes = 2 * span + 3 * page;
    size_t stage_map_bytes = stage_span + 2 * page;
    unsigned char *source_map = map_guarded(source_map_bytes);
    unsigned char *stage_map = map_guarded(stage_map_bytes);
    unsigned char *k_page = source_map + page;
    unsigned char *v_page = source_map + 2 * page + span;
    unsigned char *stage_page = stage_map + page;
    require(mprotect(k_page, span, PROT_READ | PROT_WRITE) == 0
            && mprotect(v_page, span, PROT_READ | PROT_WRITE) == 0
            && mprotect(stage_page, stage_span, PROT_READ | PROT_WRITE) == 0, "guard permissions");
    memset(k_page, 0xa7, span); memset(v_page, 0xa7, span);
    unsigned char *k = k_page + (at_end ? span - b : 0);
    unsigned char *v = v_page + (at_end ? span - b : 0);
    unsigned char *stage = stage_page + (at_end ? stage_span - 2 * b : 0);
    fill(k, b, 3); fill(v, b, 11);
    unsigned char *expected = allocate(2 * b);
    unsigned char *k_saved = allocate(span), *v_saved = allocate(span);
    memcpy(k_saved, k_page, span); memcpy(v_saved, v_page, span);
    oracle(expected, k, 0, (size_t) (v - k), d, h, n);
    require(mprotect(k_page, span, PROT_READ) == 0 && mprotect(v_page, span, PROT_READ) == 0,
            "read-only source windows");
    for (size_t which = 0; which < 2; which++) {
        memset(stage_page, 0xcd, stage_span);
        require(implementations[which](k, (int64_t) (v - k + b), 0, (int64_t) (v - k),
                stage, (int64_t) (2 * b), (int64_t) d, (int64_t) h, (int64_t) n) == 0,
                "guarded native transfer");
        require(memcmp(stage, expected, 2 * b) == 0, "guarded tile/tail exact image");
        require(memcmp(k_page, k_saved, span) == 0 && memcmp(v_page, v_saved, span) == 0,
                "guarded source unchanged");
        size_t offset = (size_t) (stage - stage_page);
        for (size_t at = 0; at < stage_span; at++) {
            if (at < offset || at >= offset + 2 * b)
                require(stage_page[at] == 0xcd, "guarded stage sentinels");
        }
    }
    release(v_saved); release(k_saved); release(expected);
    unmap_guarded(stage_map, stage_map_bytes); unmap_guarded(source_map, source_map_bytes);
}

int main(void) {
#if defined(NATIVE_UNAVAILABLE)
    require(align_ggml_available() == 0, "strict unavailable flavor");
#else
    require(align_ggml_available() == 1, "engine/real flavor");
#endif
    image_case(2, 2, 3, 0, 0, 0);
    image_case(4, 1, 4, 0, 0, 0);
    image_case(12, 3, 16, 0, 0, 0);
    const size_t edges[] = {1, 3, 4, 5, 8, 9};
    for (size_t di = 0; di < 6; di++) {
        for (size_t ni = 0; ni < 6; ni++) {
            image_case(edges[di], 1, edges[ni], 0, 0, 0);
            image_case(edges[di], 3, edges[ni], 0, 0, 0);
            guarded_case(edges[di], 3, edges[ni], 0);
            guarded_case(edges[di], 3, edges[ni], 1);
        }
    }
    for (size_t source = 0; source < 16; source++) {
        for (size_t stage = 0; stage < 16; stage++) image_case(5, 3, 5, source, stage, 0);
    }
    image_case(5, 2, 5, 1, 3, 1);
    image_case(5, 2, 5, 1, 3, 2);
    admitted_alias(160, 240, 0);
    admitted_alias(0, 80, 160);
    admitted_alias(0, 240, 80);
    admitted_alias(0, 32, 112);
    refusals();
    require(allocations == 0 && mappings == 0, "test allocation/mapping cleanup");
    puts("PASS legacy_d2_h2_n3 tile4_exact multihead_multitile k_block_copy_unchanged");
    puts("PASS no_tile_edges lane_tail column_tail both_tails tile_boundary_shapes");
    puts("PASS special_bits_exact unaligned_source_and_stage source_unchanged stage_sentinels");
    puts("PASS guarded_tile_bounds guarded_tail_bounds");
    puts("PASS null_precedence scalar_bounds product_overflow stage_exact_size source_bounds pointer_extent");
    puts("PASS source_overlap_allowed touching_endpoints_allowed stage_in_unused_plane_allowed destination_overlap_refused");
    puts("PASS scalar_reference_parity test_allocation_cleanup");
#if defined(__aarch64__)
    puts("Platform: AArch64 SIMD/tails executed; immutable scalar control executed; non-AArch64 dispatch runtime N/A");
#else
    puts("Platform: native scalar fallback executed; AArch64 SIMD runtime N/A");
#endif
    puts("Native staging cases: PASS");
    return 0;
}
