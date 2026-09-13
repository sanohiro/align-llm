/* Test-only validation of the GPU loader's observed payload traversal.
 *
 * This is intentionally tied to the two fixed layer-forward fixtures. It reads their alignpack
 * header, block table, and member table, then checks the native observer log against the loader's
 * known Qwen2 or OLMoE role order. It is not a general alignpack reader or a production utility.
 */

#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#else
#define _GNU_SOURCE 1
#endif

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define ALIGN_TEST_HEADER_BYTES 128U
#define ALIGN_TEST_BLOCK_RECORD_BYTES 64U
#define ALIGN_TEST_MEMBER_RECORD_BYTES 96U
#define ALIGN_TEST_MAX_BLOCKS 32U
#define ALIGN_TEST_MAX_MEMBERS 128U
#define ALIGN_TEST_MAX_EXPECTED 128U

#define ALIGN_TEST_KIND_WEIGHT 0
#define ALIGN_TEST_KIND_ATTENTION 1
#define ALIGN_TEST_KIND_MLP 2
#define ALIGN_TEST_KIND_EXPERT 3
#define ALIGN_TEST_KIND_ROUTER 4

typedef enum align_test_model {
    ALIGN_TEST_MODEL_QWEN,
    ALIGN_TEST_MODEL_OLMOE,
} align_test_model;

typedef enum align_test_validation {
    ALIGN_TEST_VALIDATION_NONE,
    ALIGN_TEST_VALIDATION_SHORT,
    ALIGN_TEST_VALIDATION_ZERO,
    ALIGN_TEST_VALIDATION_ERROR,
} align_test_validation;

typedef struct align_test_member {
    uint32_t role;
    int32_t kind;
    int32_t layer;
    int32_t expert;
    int32_t slice_index;
    int32_t slice_count;
    uint64_t nbytes;
    uint64_t pack_offset;
} align_test_member;

typedef struct align_test_fixture {
    uint64_t total_bytes;
    uint64_t payload_offset;
    size_t member_count;
    align_test_member members[ALIGN_TEST_MAX_MEMBERS];
    unsigned char assigned[ALIGN_TEST_MAX_MEMBERS];
} align_test_fixture;

typedef struct align_test_expected {
    uint64_t pack_offset;
    uint64_t bytes;
} align_test_expected;

static uint32_t align_test_decode_u32(const unsigned char *bytes) {
    return (uint32_t) bytes[0]
        | ((uint32_t) bytes[1] << 8)
        | ((uint32_t) bytes[2] << 16)
        | ((uint32_t) bytes[3] << 24);
}

static uint64_t align_test_decode_u64(const unsigned char *bytes) {
    return (uint64_t) bytes[0]
        | ((uint64_t) bytes[1] << 8)
        | ((uint64_t) bytes[2] << 16)
        | ((uint64_t) bytes[3] << 24)
        | ((uint64_t) bytes[4] << 32)
        | ((uint64_t) bytes[5] << 40)
        | ((uint64_t) bytes[6] << 48)
        | ((uint64_t) bytes[7] << 56);
}

static int align_test_read_exact(int fd, void *destination, size_t bytes, uint64_t offset) {
    unsigned char *cursor = (unsigned char *) destination;
    while (bytes > 0) {
        ssize_t count;
        if (offset > (uint64_t) INT64_MAX) {
            return 0;
        }
        count = pread(fd, cursor, bytes, (off_t) offset);
        if (count < 0 && errno == EINTR) {
            continue;
        }
        if (count <= 0) {
            return 0;
        }
        cursor += (size_t) count;
        bytes -= (size_t) count;
        offset += (uint64_t) count;
    }
    return 1;
}

static int align_test_region_valid(uint64_t offset, uint64_t bytes, uint64_t total) {
    return offset <= total && bytes <= total - offset;
}

static int align_test_table_valid(uint64_t offset, uint64_t count, uint64_t record_bytes,
                                  uint64_t total) {
    if (count > UINT64_MAX / record_bytes) {
        return 0;
    }
    return align_test_region_valid(offset, count * record_bytes, total);
}

static int align_test_load_fixture(int fd, align_test_model model, align_test_fixture *fixture) {
    unsigned char header[ALIGN_TEST_HEADER_BYTES];
    unsigned char record[ALIGN_TEST_BLOCK_RECORD_BYTES];
    struct stat file_status;
    uint64_t block_table_offset;
    uint64_t block_count;
    uint64_t member_table_offset;
    uint64_t member_count;
    uint64_t payload_bytes;
    uint64_t block_at;
    uint64_t member_at;

    if (fstat(fd, &file_status) != 0 || file_status.st_size < 0
        || (uint64_t) file_status.st_size < sizeof(header)
        || !align_test_read_exact(fd, header, sizeof(header), 0)
        || memcmp(header, "ALGP", 4) != 0
        || align_test_decode_u32(header + 4) != 1
        || align_test_decode_u32(header + 8) != ALIGN_TEST_HEADER_BYTES) {
        return 0;
    }
    memset(fixture, 0, sizeof(*fixture));
    fixture->total_bytes = align_test_decode_u64(header + 24);
    block_table_offset = align_test_decode_u64(header + 48);
    block_count = align_test_decode_u64(header + 56);
    member_table_offset = align_test_decode_u64(header + 64);
    member_count = align_test_decode_u64(header + 72);
    fixture->payload_offset = align_test_decode_u64(header + 88);
    payload_bytes = align_test_decode_u64(header + 96);
    if (fixture->total_bytes != (uint64_t) file_status.st_size
        || fixture->total_bytes < sizeof(header)
        || fixture->payload_offset > fixture->total_bytes
        || payload_bytes != fixture->total_bytes - fixture->payload_offset
        || block_count > ALIGN_TEST_MAX_BLOCKS
        || member_count > ALIGN_TEST_MAX_MEMBERS
        || (model == ALIGN_TEST_MODEL_QWEN && member_count != 27)
        || (model == ALIGN_TEST_MODEL_OLMOE && member_count != 69)
        || !align_test_table_valid(block_table_offset, block_count,
                                   ALIGN_TEST_BLOCK_RECORD_BYTES, fixture->total_bytes)
        || !align_test_table_valid(member_table_offset, member_count,
                                   ALIGN_TEST_MEMBER_RECORD_BYTES, fixture->total_bytes)) {
        return 0;
    }
    fixture->member_count = (size_t) member_count;

    block_at = 0;
    while (block_at < block_count) {
        uint64_t block_offset = block_table_offset
            + block_at * ALIGN_TEST_BLOCK_RECORD_BYTES;
        uint64_t member_start;
        uint64_t block_members;
        uint64_t inner;
        int32_t kind;
        int32_t layer;
        int32_t expert;

        if (!align_test_read_exact(fd, record, sizeof(record), block_offset)) {
            return 0;
        }
        kind = (int32_t) align_test_decode_u32(record);
        layer = (int32_t) align_test_decode_u32(record + 4);
        expert = (int32_t) align_test_decode_u32(record + 8);
        block_members = align_test_decode_u32(record + 12);
        member_start = align_test_decode_u64(record + 16);
        if (member_start > member_count || block_members > member_count - member_start) {
            return 0;
        }
        inner = 0;
        while (inner < block_members) {
            size_t index = (size_t) (member_start + inner);
            if (fixture->assigned[index] != 0) {
                return 0;
            }
            fixture->assigned[index] = 1;
            fixture->members[index].kind = kind;
            fixture->members[index].layer = layer;
            fixture->members[index].expert = expert;
            inner += 1;
        }
        block_at += 1;
    }

    member_at = 0;
    while (member_at < member_count) {
        unsigned char member_record[ALIGN_TEST_MEMBER_RECORD_BYTES];
        uint64_t member_offset = member_table_offset
            + member_at * ALIGN_TEST_MEMBER_RECORD_BYTES;
        align_test_member *member = &fixture->members[member_at];

        if (fixture->assigned[member_at] == 0
            || !align_test_read_exact(fd, member_record, sizeof(member_record), member_offset)) {
            return 0;
        }
        member->role = align_test_decode_u32(member_record + 12);
        member->nbytes = align_test_decode_u64(member_record + 24);
        member->pack_offset = align_test_decode_u64(member_record + 32);
        member->slice_index = (int32_t) align_test_decode_u32(member_record + 80);
        member->slice_count = (int32_t) align_test_decode_u32(member_record + 84);
        if (member->nbytes == 0 || member->pack_offset < fixture->payload_offset
            || !align_test_region_valid(member->pack_offset, member->nbytes,
                                        fixture->total_bytes)) {
            return 0;
        }
        member_at += 1;
    }
    return 1;
}

static int align_test_find_member(const align_test_fixture *fixture, int32_t kind, int32_t layer,
                                  int32_t expert, uint32_t role, size_t *found) {
    size_t at;
    size_t hits = 0;
    size_t candidate = 0;
    for (at = 0; at < fixture->member_count; at += 1) {
        const align_test_member *member = &fixture->members[at];
        if (member->kind == kind && member->layer == layer && member->expert == expert
            && member->role == role) {
            hits += 1;
            candidate = at;
        }
    }
    if (hits != 1) {
        return 0;
    }
    *found = candidate;
    return 1;
}

static int align_test_add_member(const align_test_fixture *fixture, int32_t kind, int32_t layer,
                                 int32_t expert, uint32_t role, int expert_piece,
                                 align_test_expected *expected, size_t *expected_count,
                                 unsigned char *seen) {
    size_t member_index;
    const align_test_member *member;
    if (*expected_count >= ALIGN_TEST_MAX_EXPECTED
        || !align_test_find_member(fixture, kind, layer, expert, role, &member_index)
        || seen[member_index] != 0) {
        return 0;
    }
    member = &fixture->members[member_index];
    if (expert_piece) {
        if (member->slice_index != expert || member->slice_count != 8) {
            return 0;
        }
    } else if (member->slice_index != -1 || member->slice_count != -1) {
        return 0;
    }
    seen[member_index] = 1;
    expected[*expected_count].pack_offset = member->pack_offset;
    expected[*expected_count].bytes = member->nbytes;
    *expected_count += 1;
    return 1;
}

static int align_test_build_expected(const align_test_fixture *fixture, align_test_model model,
                                     align_test_expected *expected, size_t *expected_count) {
    static const uint32_t qwen_layer_roles[12] = {
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
    };
    static const uint32_t olmoe_dense_roles[9] = {
        0, 1, 27, 3, 28, 5, 7, 8, 17,
    };
    static const uint32_t olmoe_expert_roles[3] = { 19, 21, 23 };
    unsigned char seen[ALIGN_TEST_MAX_MEMBERS];
    size_t layer;
    size_t row;

    memset(seen, 0, sizeof(seen));
    *expected_count = 0;
    if (!align_test_add_member(fixture, ALIGN_TEST_KIND_WEIGHT, -1, -1, 12, 0,
                               expected, expected_count, seen)) {
        return 0;
    }
    if (model == ALIGN_TEST_MODEL_QWEN) {
        for (layer = 0; layer < 2; layer += 1) {
            for (row = 0; row < 12; row += 1) {
                int32_t kind = row <= 7 ? ALIGN_TEST_KIND_ATTENTION : ALIGN_TEST_KIND_MLP;
                if (!align_test_add_member(fixture, kind, (int32_t) layer, -1,
                                           qwen_layer_roles[row], 0,
                                           expected, expected_count, seen)) {
                    return 0;
                }
            }
        }
    } else {
        for (layer = 0; layer < 2; layer += 1) {
            for (row = 0; row < 9; row += 1) {
                int32_t kind = row < 7 ? ALIGN_TEST_KIND_ATTENTION : ALIGN_TEST_KIND_ROUTER;
                if (!align_test_add_member(fixture, kind, (int32_t) layer, -1,
                                           olmoe_dense_roles[row], 0,
                                           expected, expected_count, seen)) {
                    return 0;
                }
            }
            for (row = 0; row < 3; row += 1) {
                size_t expert;
                for (expert = 0; expert < 8; expert += 1) {
                    if (!align_test_add_member(fixture, ALIGN_TEST_KIND_EXPERT, (int32_t) layer,
                                               (int32_t) expert, olmoe_expert_roles[row], 1,
                                               expected, expected_count, seen)) {
                        return 0;
                    }
                }
            }
        }
    }
    if (!align_test_add_member(fixture, ALIGN_TEST_KIND_WEIGHT, -1, -1, 13, 0,
                               expected, expected_count, seen)
        || !align_test_add_member(fixture, ALIGN_TEST_KIND_WEIGHT, -1, -1, 14, 0,
                                  expected, expected_count, seen)
        || *expected_count != fixture->member_count
        || expected[0].pack_offset != fixture->payload_offset) {
        return 0;
    }
    for (row = 0; row < fixture->member_count; row += 1) {
        if (seen[row] == 0) {
            return 0;
        }
    }
    return 1;
}

static int align_test_parse_unsigned(const char **cursor, uint64_t *value) {
    char *end;
    unsigned long long parsed;
    while (isspace((unsigned char) **cursor) != 0) {
        *cursor += 1;
    }
    if (**cursor == '-' || **cursor == '\0') {
        return 0;
    }
    errno = 0;
    parsed = strtoull(*cursor, &end, 10);
    if (end == *cursor || errno == ERANGE || parsed > UINT64_MAX) {
        return 0;
    }
    *cursor = end;
    *value = (uint64_t) parsed;
    return 1;
}

static int align_test_parse_signed(const char **cursor, int64_t *value) {
    char *end;
    long long parsed;
    while (isspace((unsigned char) **cursor) != 0) {
        *cursor += 1;
    }
    if (**cursor == '\0') {
        return 0;
    }
    errno = 0;
    parsed = strtoll(*cursor, &end, 10);
    if (end == *cursor || errno == ERANGE) {
        return 0;
    }
    *cursor = end;
    *value = (int64_t) parsed;
    return 1;
}

static int align_test_parse_row(const char *line, uint64_t *requested, int64_t *offset,
                                int64_t *returned) {
    const char *cursor = line;
    if (!align_test_parse_unsigned(&cursor, requested)
        || !align_test_parse_signed(&cursor, offset)
        || !align_test_parse_signed(&cursor, returned)) {
        return 0;
    }
    while (isspace((unsigned char) *cursor) != 0) {
        cursor += 1;
    }
    return *cursor == '\0';
}

static int align_test_parse_model(const char *value, align_test_model *model) {
    if (strcmp(value, "qwen") == 0) {
        *model = ALIGN_TEST_MODEL_QWEN;
        return 1;
    }
    if (strcmp(value, "olmoe") == 0) {
        *model = ALIGN_TEST_MODEL_OLMOE;
        return 1;
    }
    return 0;
}

static int align_test_parse_validation(const char *value, align_test_validation *validation) {
    if (strcmp(value, "none") == 0) {
        *validation = ALIGN_TEST_VALIDATION_NONE;
        return 1;
    }
    if (strcmp(value, "short") == 0) {
        *validation = ALIGN_TEST_VALIDATION_SHORT;
        return 1;
    }
    if (strcmp(value, "zero") == 0) {
        *validation = ALIGN_TEST_VALIDATION_ZERO;
        return 1;
    }
    if (strcmp(value, "error") == 0) {
        *validation = ALIGN_TEST_VALIDATION_ERROR;
        return 1;
    }
    return 0;
}

static int align_test_parse_staging(const char *value, uint64_t *staging) {
    const char *cursor = value;
    if (!align_test_parse_unsigned(&cursor, staging) || *staging == 0) {
        return 0;
    }
    while (isspace((unsigned char) *cursor) != 0) {
        cursor += 1;
    }
    return *cursor == '\0';
}

static int align_test_validate_log(const char *pack_path, const char *log_path,
                                   align_test_model model, uint64_t staging,
                                   align_test_validation validation) {
    align_test_fixture fixture;
    align_test_expected expected[ALIGN_TEST_MAX_EXPECTED];
    size_t expected_count;
    size_t expected_at = 0;
    uint64_t done = 0;
    uint64_t maximum_request = 0;
    int short_seen = 0;
    int fd = open(pack_path, O_RDONLY);
    FILE *log;
    char line[256];
    size_t lines = 0;

    if (fd < 0 || !align_test_load_fixture(fd, model, &fixture)
        || !align_test_build_expected(&fixture, model, expected, &expected_count)) {
        if (fd >= 0) {
            (void) close(fd);
        }
        fprintf(stderr, "gpu load pread validator: invalid fixture %s\n", pack_path);
        return 1;
    }
    (void) close(fd);
    log = fopen(log_path, "r");
    if (log == NULL) {
        fprintf(stderr, "gpu load pread validator: cannot read log %s\n", log_path);
        return 1;
    }
    while (fgets(line, sizeof(line), log) != NULL) {
        uint64_t requested;
        int64_t offset;
        int64_t returned;
        uint64_t remaining;
        uint64_t expected_request;
        uint64_t expected_offset;

        lines += 1;
        if (strchr(line, '\n') == NULL
            || !align_test_parse_row(line, &requested, &offset, &returned)
            || expected_at >= expected_count) {
            fclose(log);
            fprintf(stderr, "gpu load pread validator: malformed or extra row %zu in %s\n",
                    lines, log_path);
            return 1;
        }
        if (done > expected[expected_at].bytes
            || expected[expected_at].pack_offset > UINT64_MAX - done) {
            fclose(log);
            fprintf(stderr, "gpu load pread validator: expected traversal overflow at row %zu\n",
                    lines);
            return 1;
        }
        remaining = expected[expected_at].bytes - done;
        expected_request = staging < remaining ? staging : remaining;
        expected_offset = expected[expected_at].pack_offset + done;
        if (requested != expected_request || offset < 0
            || (uint64_t) offset != expected_offset) {
            fclose(log);
            fprintf(stderr,
                    "gpu load pread validator: row %zu expected count=%" PRIu64
                    " offset=%" PRIu64 ", got count=%" PRIu64 " offset=%" PRId64 "\n",
                    lines, expected_request, expected_offset, requested, offset);
            return 1;
        }
        if (requested > maximum_request) {
            maximum_request = requested;
        }
        if (validation == ALIGN_TEST_VALIDATION_ZERO || validation == ALIGN_TEST_VALIDATION_ERROR) {
            int64_t expected_return = validation == ALIGN_TEST_VALIDATION_ZERO ? 0 : -1;
            if (lines != 1 || returned != expected_return) {
                fclose(log);
                fprintf(stderr, "gpu load pread validator: fault row %zu is not payload terminal\n",
                        lines);
                return 1;
            }
            continue;
        }
        if (returned < 1 || (uint64_t) returned > remaining) {
            fclose(log);
            fprintf(stderr, "gpu load pread validator: invalid returned count at row %zu\n", lines);
            return 1;
        }
        if (validation == ALIGN_TEST_VALIDATION_SHORT && (uint64_t) returned < requested) {
            short_seen = 1;
        }
        done += (uint64_t) returned;
        if (done == expected[expected_at].bytes) {
            expected_at += 1;
            done = 0;
        }
    }
    if (ferror(log) != 0) {
        fclose(log);
        fprintf(stderr, "gpu load pread validator: failed while reading %s\n", log_path);
        return 1;
    }
    fclose(log);
    if (validation == ALIGN_TEST_VALIDATION_ZERO || validation == ALIGN_TEST_VALIDATION_ERROR) {
        if (lines != 1) {
            fprintf(stderr, "gpu load pread validator: fault log has no payload terminal\n");
            return 1;
        }
        return 0;
    }
    if (expected_at != expected_count || done != 0 || maximum_request == 0
        || (!short_seen && validation == ALIGN_TEST_VALIDATION_SHORT)) {
        fprintf(stderr, "gpu load pread validator: incomplete traversal in %s\n", log_path);
        return 1;
    }
    return 0;
}

static void align_test_usage(void) {
    fprintf(stderr, "usage: gpu_load_pread_validator MODEL PACK LOG STAGING MODE\n");
}

int main(int argc, char **argv) {
    align_test_model model;
    align_test_validation validation;
    uint64_t staging;

    if (argc != 6 || !align_test_parse_model(argv[1], &model)
        || !align_test_parse_staging(argv[4], &staging)
        || !align_test_parse_validation(argv[5], &validation)) {
        align_test_usage();
        return 2;
    }
    return align_test_validate_log(argv[2], argv[3], model, staging, validation);
}
