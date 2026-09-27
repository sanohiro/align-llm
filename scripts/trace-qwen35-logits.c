/* Developer-only complete F32 logit hash. Exclude from timing campaigns.
 * clang -O2 -Wall -Wextra -Werror -Wno-deprecated-declarations \
 *   -dynamiclib -undefined dynamic_lookup scripts/trace-qwen35-logits.c -o trace-logits.dylib
 * Set ALIGN_LOGIT_BYTES to the expected full row and inject with DYLD_INSERT_LIBRARIES.
 */
#include <CommonCrypto/CommonDigest.h>
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

extern int32_t align_gpu_slot_get(void *, void *, int64_t, void *, int64_t, int64_t);

static int64_t expected_bytes(void) {
    const char *raw = getenv("ALIGN_LOGIT_BYTES");
    char *end;
    unsigned long long parsed;
    if (raw == NULL) return 0;
    errno = 0;
    parsed = strtoull(raw, &end, 10);
    if (errno != 0 || end == raw || *end != '\0' || parsed < 4 || parsed > INT32_MAX
        || parsed % 4 != 0) abort();
    return (int64_t) parsed;
}

static int32_t traced_get(void *owner, void *slots, int64_t index,
        void *bytes, int64_t offset, int64_t size) {
    static uint64_t ordinal;
    int32_t status = align_gpu_slot_get(owner, slots, index, bytes, offset, size);
    if (status == 0 && offset == 0 && size == expected_bytes()) {
        unsigned char digest[CC_SHA256_DIGEST_LENGTH];
        static const char digits[] = "0123456789abcdef";
        char hex[2 * CC_SHA256_DIGEST_LENGTH + 1];
        CC_SHA256(bytes, (CC_LONG) size, digest);
        for (size_t i = 0; i < sizeof(digest); ++i) {
            hex[2*i] = digits[digest[i] >> 4];
            hex[2*i+1] = digits[digest[i] & 15];
        }
        hex[sizeof(hex)-1] = '\0';
        fprintf(stderr, "Q35_LOGIT {\"ordinal\":%" PRIu64 ",\"bytes\":%" PRId64
                ",\"sha256\":\"%s\"}\n", ordinal++, size, hex);
    }
    return status;
}

__attribute__((used)) static struct { const void *replacement, *original; } interpose_get
    __attribute__((section("__DATA,__interpose"))) = {
        (const void *)&traced_get, (const void *)&align_gpu_slot_get
    };
