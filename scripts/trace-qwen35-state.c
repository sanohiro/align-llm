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
 * Optional ALIGN_STATE_DUMP_PATH and ALIGN_STATE_DUMP_ORDINAL together write
 * that graph's full planes in index order for a separate numeric diagnostic.
 */
#include "ggml.h"
#include "ggml-backend.h"
#include <dlfcn.h>
#if defined(__APPLE__)
#include <CommonCrypto/CommonDigest.h>
#else
#include <openssl/sha.h>
#define CC_SHA256_DIGEST_LENGTH SHA256_DIGEST_LENGTH
#define CC_SHA256_CTX SHA256_CTX
#define CC_LONG size_t
#define CC_SHA256 SHA256
#define CC_SHA256_Init SHA256_Init
#define CC_SHA256_Update SHA256_Update
#define CC_SHA256_Final SHA256_Final
#endif
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
extern int64_t align_gpu_memory_bytes(void *, int32_t);
extern int64_t align_gpu_memory_allocated_bytes(void *, int32_t);
extern int64_t align_gpu_observation_state(void *, int32_t);

static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "Q35_STATE {\"event\":\"error\",\"message\":\"%s\"}\n", message);
        abort();
    }
}

static int32_t compute_original(void *owner, int32_t kind, const void *key,
                                int64_t length, void *value) {
#if defined(__APPLE__)
    return align_gpu_graph_compute(owner, kind, key, length, value);
#else
    typedef int32_t (*compute_fn)(void *, int32_t, const void *, int64_t, void *);
    static compute_fn original;
    if (original == NULL) {
        void *symbol = dlsym(RTLD_NEXT, "align_gpu_graph_compute");
        require(symbol != NULL, "native graph compute symbol unavailable");
        memcpy(&original, &symbol, sizeof(original));
    }
    return original(owner, kind, key, length, value);
#endif
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

static int64_t graph_logit_bytes(void) {
    const char *raw = getenv("ALIGN_GRAPH_LOGIT_BYTES");
    if (raw == NULL) return 0;
    require(raw[0] != '\0', "empty graph logit bytes");
    for (const char *p = raw; *p; ++p) require(*p >= '0' && *p <= '9', "invalid graph logit bytes");
    errno = 0;
    unsigned long long value = strtoull(raw, NULL, 10);
    require(errno != ERANGE && value >= 4 && value <= INT32_MAX && value % 4 == 0,
            "graph logit bytes outside diagnostic bound");
    return (int64_t)value;
}

static int native_q6_read_if_ready(void *owner, void *bytes, int64_t length) {
    typedef int32_t (*enabled_fn)(void *);
    typedef int32_t (*read_fn)(void *, void *, int64_t);
    static int initialized;
    static enabled_fn enabled;
    static read_fn read;
    if (!initialized) {
        void *enabled_symbol = dlsym(RTLD_DEFAULT, "align_gpu_native_q6_head_enabled");
        void *read_symbol = dlsym(RTLD_DEFAULT, "align_gpu_native_q6_head_read");
        if (enabled_symbol != NULL && read_symbol != NULL) {
            memcpy(&enabled, &enabled_symbol, sizeof(enabled));
            memcpy(&read, &read_symbol, sizeof(read));
        }
        initialized = 1;
    }
    return enabled != NULL && read != NULL && enabled(owner) == 1
        && read(owner, bytes, length) == 0;
}

static int32_t traced_compute(void *owner, int32_t kind, const void *key,
                              int64_t length, void *value) {
    int64_t count = state_count();
    static void *captured_owner;
    static uint64_t ordinal;
    if (count && captured_owner) require(owner == captured_owner, "diagnostic owner changed");
    int32_t status = compute_original(owner, kind, key, length, value);
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
    int64_t logit_bytes = graph_logit_bytes();
    if (logit_bytes) {
        const struct ggml_tensor *logits = NULL;
        for (int i = 0; i < nodes; ++i) {
            const struct ggml_tensor *t = ggml_graph_node(graph, i);
            if (t->op == GGML_OP_MUL_MAT && t->type == GGML_TYPE_F32
                && t->ne[0] == logit_bytes / 4 && t->ne[1] == 1
                && t->ne[2] == 1 && t->ne[3] == 1 && ggml_is_contiguous(t)) {
                require(logits == NULL, "multiple graph logit rows");
                logits = t;
            }
        }
        unsigned char *bytes = malloc((size_t)logit_bytes);
        require(bytes != NULL, "logit diagnostic allocation failed");
        int have_logits = 0;
        if (logits != NULL) {
            require(logits->buffer != NULL, "graph logit storage unavailable");
            ggml_backend_tensor_get(logits, bytes, 0, (size_t)logit_bytes);
            have_logits = 1;
        } else {
            have_logits = native_q6_read_if_ready(owner, bytes, logit_bytes);
        }
        if (have_logits) {
            static uint64_t logit_ordinal;
            const char *logit_dump = getenv("ALIGN_LOGIT_DUMP_DIR");
            if (logit_dump != NULL) {
                char path[4096];
                int length = snprintf(path, sizeof(path), "%s/%" PRIu64 ".bin",
                                      logit_dump, logit_ordinal);
                require(length > 0 && (size_t)length < sizeof(path), "logit dump path too long");
                FILE *file = fopen(path, "wb");
                require(file != NULL && fwrite(bytes, 1, (size_t)logit_bytes, file)
                        == (size_t)logit_bytes && fclose(file) == 0,
                        "logit dump write failed");
            }
            unsigned char digest[CC_SHA256_DIGEST_LENGTH];
            char hex[2 * CC_SHA256_DIGEST_LENGTH + 1];
            static const char digits[] = "0123456789abcdef";
            CC_SHA256(bytes, (CC_LONG)logit_bytes, digest);
            for (size_t i = 0; i < sizeof(digest); ++i) {
                hex[2*i] = digits[digest[i] >> 4];
                hex[2*i+1] = digits[digest[i] & 15];
            }
            hex[sizeof(hex)-1] = '\0';
            fprintf(stderr, "Q35_LOGIT {\"ordinal\":%" PRIu64 ",\"bytes\":%" PRId64
                    ",\"sha256\":\"%s\"}\n", logit_ordinal++, logit_bytes, hex);
        }
        free(bytes);
    }
    fprintf(stderr, "Q35_STATE {\"event\":\"graph\",\"ordinal\":%" PRIu64 ",\"kind\":%d,"
            "\"nodes\":%d,\"state_count\":%" PRId64 ",\"ops\":{\"MUL_MAT\":%d,\"CPY\":%d,"
            "\"SET\":%d,\"SET_ROWS\":%d,\"SSM_CONV\":%d,\"GATED_DELTA_NET\":%d,"
            "\"FLASH_ATTN_EXT\":%d,\"GLU\":%d}}\n", ordinal, kind, nodes, count,
            mul_mat, cpy, set, set_rows, ssm_conv, delta, flash, glu);
    int64_t planned = align_gpu_memory_bytes(owner, 1);
    int64_t allocated = align_gpu_memory_allocated_bytes(owner, 1);
    int64_t peak = align_gpu_observation_state(owner, 5);
    int64_t model_ops = align_gpu_observation_state(owner, 8);
    require(planned > 0 && allocated > 0 && peak >= allocated && model_ops > 0,
            "invalid device or model-work observation");
    fprintf(stderr, "Q35_ACCOUNT {\"ordinal\":%" PRIu64 ",\"planned_device\":%" PRId64
            ",\"allocated_device\":%" PRId64 ",\"device_peak\":%" PRId64
            ",\"model_ops\":%" PRId64 "}\n",
            ordinal, planned, allocated, peak, model_ops);

    const size_t chunk = 1024 * 1024;
    void *scratch = malloc(chunk);
    require(scratch != NULL, "state hash scratch allocation failed");
    const char *dump_path = getenv("ALIGN_STATE_DUMP_PATH");
    const char *dump_ordinal = getenv("ALIGN_STATE_DUMP_ORDINAL");
    require((dump_path == NULL) == (dump_ordinal == NULL),
            "state dump path and ordinal must be set together");
    FILE *dump = NULL;
    if (dump_path != NULL) {
        require(dump_path[0] != '\0' && dump_ordinal[0] != '\0', "empty state dump selector");
        for (const char *p = dump_ordinal; *p; ++p)
            require(*p >= '0' && *p <= '9', "invalid state dump ordinal");
        errno = 0;
        unsigned long long target = strtoull(dump_ordinal, NULL, 10);
        require(errno != ERANGE, "state dump ordinal overflow");
        if (target == ordinal) {
            dump = fopen(dump_path, "wb");
            require(dump != NULL, "state dump open failed");
        }
    }
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
            if (dump != NULL) require(fwrite(scratch, 1, n, dump) == n,
                                      "state dump write failed");
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
    if (dump != NULL) require(fclose(dump) == 0, "state dump close failed");
    free(scratch);
    fprintf(stderr, "Q35_STATE {\"event\":\"graph_complete\",\"ordinal\":%" PRIu64
            ",\"kind\":%d,\"state_count\":%" PRId64 "}\n", ordinal, kind, count);
    ++ordinal;
    return status;
}

#if defined(__APPLE__)
__attribute__((used)) static struct { const void *replacement, *original; } interpose_graph
    __attribute__((section("__DATA,__interpose"))) = {
        (const void *)&traced_compute, (const void *)&align_gpu_graph_compute
    };
#else
int32_t align_gpu_graph_compute(void *owner, int32_t kind, const void *key,
                               int64_t length, void *value) {
    return traced_compute(owner, kind, key, length, value);
}
#endif
