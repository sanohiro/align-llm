/* Independent state/dependency diagnostic. Never inject into a timing campaign.
 * Build: clang -O2 -Wall -Wextra -Werror -Wno-deprecated-declarations \
 *   -dynamiclib -undefined dynamic_lookup -I GGML/ggml/include \
 *   scripts/trace-qwen35-state.c -o trace-qwen35-state.dylib
 * Inject with DYLD_INSERT_LIBRARIES and set ALIGN_STATE_COUNT to the geometry's
 * resident state count: 2*attention_layers + 4*recurrent_layers (84 for 2B).
 * Without that environment variable this library records nothing.
 * Emits Q35_STATE-prefixed JSON lines after each successful synchronized graph.
 * A graph_complete record is required before treating its plane set as complete.
 * Hashes both recurrent parity banks and entire KV allocations, including tails.
 */
#include "ggml.h"
#include "ggml-backend.h"
#include <CommonCrypto/CommonDigest.h>
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern int32_t align_gpu_graph_compute(void *, int32_t, const void *, int64_t, void *);
extern int32_t align_gpu_native_state_copy_finish(void *);
extern int32_t align_gpu_kv_slot(void *, int64_t, void *, int64_t);
extern int32_t align_ggml_slots_init(void *, int64_t);

static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "Q35_STATE {\"event\":\"error\",\"message\":\"%s\"}\n", message);
        abort();
    }
}

static int64_t state_count(void) {
    static int initialized;
    static int64_t count;
    if (initialized) return count;
    const char *raw = getenv("ALIGN_STATE_COUNT");
    if (raw) {
        require(raw[0] != '\0', "empty state count");
        for (const char *p = raw; *p; ++p) require(*p >= '0' && *p <= '9', "invalid state count");
        errno = 0;
        unsigned long long value = strtoull(raw, NULL, 10);
        require(errno != ERANGE && value >= 1 && value <= 4096, "state count outside 1..4096");
        count = (int64_t)value;
    }
    initialized = 1;
    return count;
}

static int32_t traced_compute(void *owner, int32_t kind, const void *key,
                              int64_t length, void *value) {
    int64_t count = state_count();
    static void *captured_owner;
    static uint64_t ordinal;
    if (count && captured_owner) require(owner == captured_owner, "diagnostic owner changed");
    int32_t status = align_gpu_graph_compute(owner, kind, key, length, value);
    if (!count) return status;
    if (status) {
        fprintf(stderr, "Q35_STATE {\"event\":\"graph_failed\",\"ordinal\":%" PRIu64
                ",\"kind\":%d,\"status\":%d}\n", ordinal, kind, status);
        return status;
    }
    require(align_gpu_native_state_copy_finish(owner) == 0,
            "native state copy did not complete before diagnostic read");
    require(owner != NULL && value != NULL && kind >= 0 && kind <= 2, "invalid successful graph");
    require(ordinal < UINT64_MAX, "graph ordinal exhausted");
    captured_owner = owner;

    // Existing slot ABI: 16-byte header, one 8-byte pointer, 8-byte alignment.
    uint64_t slots[3];
    _Static_assert(sizeof(void *) == 8 && sizeof(slots) == 24, "requires the 64-bit slot ABI");
    require(align_ggml_slots_init(slots, sizeof(slots)) == 0, "slot initialization failed");
    require(align_gpu_kv_slot(owner, count, slots, 0) == -1, "unexpected extra state plane or refusal status");

    struct ggml_cgraph *graph = value;
    int nodes = ggml_graph_n_nodes(graph);
    int mul_mat = 0, cpy = 0, set = 0, set_rows = 0, ssm_conv = 0, delta = 0, flash = 0, glu = 0;
    for (int i = 0; i < nodes; ++i) {
        const struct ggml_tensor *t = ggml_graph_node(graph, i);
        require(t != NULL, "missing graph node");
        switch (t->op) {
            case GGML_OP_MUL_MAT: ++mul_mat; break;
            case GGML_OP_CPY: ++cpy; break;
            case GGML_OP_SET: ++set; break;
            case GGML_OP_SET_ROWS: ++set_rows; break;
            case GGML_OP_SSM_CONV: ++ssm_conv; break;
            case GGML_OP_GATED_DELTA_NET: ++delta; break;
            case GGML_OP_FLASH_ATTN_EXT: ++flash; break;
            case GGML_OP_GLU: ++glu; break;
            default: break;
        }
    }
    fprintf(stderr, "Q35_STATE {\"event\":\"graph\",\"ordinal\":%" PRIu64 ",\"kind\":%d,"
            "\"nodes\":%d,\"state_count\":%" PRId64 ",\"ops\":{\"MUL_MAT\":%d,\"CPY\":%d,"
            "\"SET\":%d,\"SET_ROWS\":%d,\"SSM_CONV\":%d,\"GATED_DELTA_NET\":%d,"
            "\"FLASH_ATTN_EXT\":%d,\"GLU\":%d}}\n", ordinal, kind, nodes, count,
            mul_mat, cpy, set, set_rows, ssm_conv, delta, flash, glu);

    const size_t chunk = 1024 * 1024;
    void *scratch = malloc(chunk);
    require(scratch != NULL, "state hash scratch allocation failed");
    for (int64_t index = 0; index < count; ++index) {
        require(align_gpu_kv_slot(owner, index, slots, 0) == 0, "missing resident state plane");
        struct ggml_tensor *tensor = NULL;
        memcpy(&tensor, (const unsigned char *)slots + 16, sizeof(tensor));
        require(tensor != NULL && tensor->data != NULL && tensor->buffer != NULL &&
                ggml_is_contiguous(tensor), "state plane has no contiguous retained storage");
        size_t bytes = ggml_nbytes(tensor);
        require(bytes > 0 && bytes <= (UINT64_C(1) << 34), "state plane extent outside diagnostic bound");
        CC_SHA256_CTX hash;
        require(CC_SHA256_Init(&hash) == 1, "hash initialization failed");
        for (size_t offset = 0; offset < bytes;) {
            size_t n = bytes - offset < chunk ? bytes - offset : chunk;
            ggml_backend_tensor_get(tensor, scratch, offset, n);
            require(CC_SHA256_Update(&hash, scratch, (CC_LONG)n) == 1, "hash update failed");
            offset += n;
        }
        unsigned char digest[CC_SHA256_DIGEST_LENGTH];
        char hex[2 * CC_SHA256_DIGEST_LENGTH + 1];
        require(CC_SHA256_Final(digest, &hash) == 1, "hash finalization failed");
        static const char digits[] = "0123456789abcdef";
        for (size_t i = 0; i < sizeof(digest); ++i) {
            hex[2*i] = digits[digest[i] >> 4]; hex[2*i+1] = digits[digest[i] & 15];
        }
        hex[sizeof(hex)-1] = '\0';
        fprintf(stderr, "Q35_STATE {\"event\":\"plane\",\"ordinal\":%" PRIu64
                ",\"kind\":%d,\"index\":%" PRId64 ",\"type\":%d,\"ne\":[%" PRId64
                ",%" PRId64 ",%" PRId64 ",%" PRId64 "],\"nb\":[%zu,%zu,%zu,%zu],"
                "\"bytes\":%zu,\"sha256\":\"%s\"}\n", ordinal, kind, index, tensor->type,
                tensor->ne[0], tensor->ne[1], tensor->ne[2], tensor->ne[3],
                tensor->nb[0], tensor->nb[1], tensor->nb[2], tensor->nb[3], bytes, hex);
    }
    free(scratch);
    fprintf(stderr, "Q35_STATE {\"event\":\"graph_complete\",\"ordinal\":%" PRIu64
            ",\"kind\":%d,\"state_count\":%" PRId64 "}\n", ordinal, kind, count);
    ++ordinal;
    return status;
}

__attribute__((used)) static struct { const void *replacement, *original; } interpose_graph
    __attribute__((section("__DATA,__interpose"))) = {
        (const void *)&traced_compute, (const void *)&align_gpu_graph_compute
    };
