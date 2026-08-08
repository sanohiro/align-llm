#define _GNU_SOURCE

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/memfd.h>
#include <limits.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include "supervisor_payload.inc"

#ifndef F_ADD_SEALS
#define F_ADD_SEALS 1033
#define F_GET_SEALS 1034
#endif

#ifndef F_SEAL_SEAL
#define F_SEAL_SEAL 0x0001
#define F_SEAL_SHRINK 0x0002
#define F_SEAL_GROW 0x0004
#define F_SEAL_WRITE 0x0008
#endif

#define PYTHON_PATH "/usr/bin/python3"
#define REQUIRED_SEALS (F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL)
#define ORDINARY_DISPATCHER_PATH "/usr/local/libexec/align-llm/request6-adoption-entrypoint"
#define IMAGE_ATTESTATION_PATH "/run/align-llm-fresh/image-attestation.dsse"
#define MANIFEST_PATH "/usr/local/share/align-llm/fresh-toolchain.json"
#define ORDINARY_TICKET_BYTES 32U
#define ORDINARY_STREAM_LIMIT 65536U
#define ORDINARY_PREFLIGHT_SECONDS 5
#define ORDINARY_WORKER_SECONDS 5000

#ifndef AT_EMPTY_PATH
#define AT_EMPTY_PATH 0x1000
#endif

#ifndef SYS_execveat
#define SYS_execveat 322
#endif

extern char **environ;

static int fail(void) {
    static const char message[] = "fresh compiler: ERROR TRUST supervisor\n";
    (void)!write(STDERR_FILENO, message, sizeof(message) - 1);
    return 1;
}

static int ordinary_debug_enabled(void) {
    return access("/tmp/fresh-debug", F_OK) == 0;
}

static void ordinary_debug(const char *message) {
    int fd;
    if (!ordinary_debug_enabled()) return;
    fd = open("/tmp/fresh-debug", O_WRONLY | O_APPEND | O_CLOEXEC);
    if (fd < 0) return;
    (void)!write(fd, message, strlen(message));
    close(fd);
}

static void ordinary_debug_bytes(const unsigned char *bytes, size_t size) {
    int fd;
    if (!ordinary_debug_enabled()) return;
    fd = open("/tmp/fresh-debug", O_WRONLY | O_APPEND | O_CLOEXEC);
    if (fd < 0) return;
    (void)!write(fd, bytes, size);
    close(fd);
}

static void ordinary_debug_parent_state(int failure, int reaped, int stdout_eof, int stderr_eof,
                                        int channel_hup, int got_capsule, int proof_sent, int status) {
    char message[256];
    int length;
    if (!ordinary_debug_enabled()) return;
    length = snprintf(message, sizeof(message),
                      "parent: state failure=%d reaped=%d stdout_eof=%d stderr_eof=%d channel_hup=%d got_capsule=%d proof_sent=%d status=%d\n",
                      failure, reaped, stdout_eof, stderr_eof, channel_hup, got_capsule, proof_sent, status);
    if (length > 0) ordinary_debug(message);
}

static int fail_argument(void) {
    static const char message[] = "fresh compiler: ERROR ARGUMENT input\n";
    (void)!write(STDERR_FILENO, message, sizeof(message) - 1);
    return 1;
}

static int matches_name(const char *entry, const char *name) {
    size_t length = strlen(name);
    return strncmp(entry, name, length) == 0 && entry[length] == '=';
}

static int matches_prefix(const char *entry, const char *prefix) {
    return strncmp(entry, prefix, strlen(prefix)) == 0;
}

static int sanitize_environment(char **child_env, int strict_boundary) {
    static char path[] = "PATH=/usr/bin:/bin";
    static char locale[] = "LC_ALL=C";
    static char language[] = "LANG=C";
    static char home[] = "HOME=/nonexistent";
    static char temporary[] = "TMPDIR=/tmp";
    static const char *forbidden[] = {
        "ALIGNC", "ALIGN_LLM_TOOLCHAIN_MANIFEST", "ALIGN_LLM_TOOLCHAIN_MANIFEST_SHA256",
        "ALIGN_LLM_WORK_PARENT", "CARGO_HOME", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_COUNT", "GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES", "RUSTC", "RUSTFLAGS", "GCONV_PATH", "LOCPATH",
        "MALLOC_TRACE", "MALLOC_CHECK_", "MALLOC_PERTURB_",
    };
    char *align_repo = NULL;
    int index;
    int output = 0;

    for (index = 0; environ[index] != NULL; ++index) {
        char *entry = environ[index];
        size_t forbidden_index;
        if (strict_boundary && !matches_name(entry, "PATH") &&
            !matches_name(entry, "LC_ALL") && !matches_name(entry, "LANG") &&
            !matches_name(entry, "HOME") && !matches_name(entry, "TMPDIR") &&
            !matches_name(entry, "ALIGN_REPO")) {
            return -1;
        }
        if (matches_name(entry, "ALIGN_REPO")) {
            if (align_repo != NULL) {
                return -1;
            }
            align_repo = entry;
            continue;
        }
        if (matches_prefix(entry, "LD_") || matches_prefix(entry, "GLIBC_") ||
            matches_prefix(entry, "PYTHON")) {
            return -1;
        }
        if ((matches_name(entry, "MAKEFLAGS") || matches_name(entry, "GNUMAKEFLAGS") ||
             matches_name(entry, "MAKEOVERRIDES")) &&
            strchr(entry, '=')[1] != '\0') {
            return -1;
        }
        for (forbidden_index = 0;
             forbidden_index < sizeof(forbidden) / sizeof(forbidden[0]); ++forbidden_index) {
            if (matches_name(entry, forbidden[forbidden_index])) {
                return -1;
            }
        }
    }
    child_env[output++] = path;
    child_env[output++] = locale;
    child_env[output++] = language;
    child_env[output++] = home;
    child_env[output++] = temporary;
    if (align_repo != NULL) {
        child_env[output++] = align_repo;
    }
    child_env[output] = NULL;
    return 0;
}

static int close_unexpected_descriptors(void) {
    return syscall(SYS_close_range, 3U, 9U, 0U) < 0 ||
                   syscall(SYS_close_range, 12U, UINT_MAX, 0U) < 0
               ? -1
               : 0;
}

static int memfd(const char *name) {
    return (int)syscall(SYS_memfd_create, name, MFD_ALLOW_SEALING | MFD_CLOEXEC);
}

static int write_all(int fd, const unsigned char *data, size_t size) {
    while (size != 0) {
        ssize_t written = write(fd, data, size);
        if (written <= 0) {
            return -1;
        }
        data += (size_t)written;
        size -= (size_t)written;
    }
    return 0;
}

static int seal_fd(int fd) {
    if (lseek(fd, 0, SEEK_SET) < 0 || fcntl(fd, F_ADD_SEALS, REQUIRED_SEALS) < 0) {
        return -1;
    }
    return fcntl(fd, F_GET_SEALS) == REQUIRED_SEALS ? 0 : -1;
}

static int snapshot_payload(void) {
    int fd = memfd("align-llm-supervisor-payload");
    if (fd < 0 || write_all(fd, supervisor_payload, supervisor_payload_len) < 0 ||
        seal_fd(fd) < 0 || dup2(fd, 11) < 0 || fcntl(11, F_SETFD, 0) < 0) {
        if (fd >= 0) {
            close(fd);
        }
        return -1;
    }
    if (fd != 11) {
        close(fd);
    }
    return 0;
}

/* Minimal SHA-256 used only for the native supervisor's 32-byte admission
 * ticket/proof construction.  The signed image and capsule wire validators
 * remain the authoritative Python implementation after the native parent
 * boundary. */
struct sha256_state {
    uint32_t h[8];
    uint64_t bits;
    unsigned char block[64];
    size_t used;
};

static uint32_t sha256_rotr(uint32_t value, unsigned count) {
    return (value >> count) | (value << (32U - count));
}

static const uint32_t sha256_k[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU, 0x59f111f1U,
    0x923f82a4U, 0xab1c5ed5U, 0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U, 0xe49b69c1U, 0xefbe4786U,
    0x0fc19dc6U, 0x240ca1ccU, 0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U,
    0x06ca6351U, 0x14292967U, 0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U, 0xa2bfe8a1U, 0xa81a664bU,
    0xc24b8b70U, 0xc76c51a3U, 0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU,
    0x5b9cca4fU, 0x682e6ff3U, 0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
};

static void sha256_compress(struct sha256_state *state, const unsigned char *block) {
    uint32_t words[64];
    uint32_t a, b, c, d, e, f, g, h;
    size_t index;
    for (index = 0; index < 16; ++index) {
        words[index] = ((uint32_t)block[index * 4] << 24U) |
                       ((uint32_t)block[index * 4 + 1] << 16U) |
                       ((uint32_t)block[index * 4 + 2] << 8U) |
                       (uint32_t)block[index * 4 + 3];
    }
    for (index = 16; index < 64; ++index) {
        uint32_t s0 = sha256_rotr(words[index - 15], 7U) ^ sha256_rotr(words[index - 15], 18U) ^
                       (words[index - 15] >> 3U);
        uint32_t s1 = sha256_rotr(words[index - 2], 17U) ^ sha256_rotr(words[index - 2], 19U) ^
                       (words[index - 2] >> 10U);
        words[index] = words[index - 16] + s0 + words[index - 7] + s1;
    }
    a = state->h[0]; b = state->h[1]; c = state->h[2]; d = state->h[3];
    e = state->h[4]; f = state->h[5]; g = state->h[6]; h = state->h[7];
    for (index = 0; index < 64; ++index) {
        uint32_t s1 = sha256_rotr(e, 6U) ^ sha256_rotr(e, 11U) ^ sha256_rotr(e, 25U);
        uint32_t choose = (e & f) ^ ((~e) & g);
        uint32_t temp1 = h + s1 + choose + sha256_k[index] + words[index];
        uint32_t s0 = sha256_rotr(a, 2U) ^ sha256_rotr(a, 13U) ^ sha256_rotr(a, 22U);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temp2 = s0 + majority;
        h = g; g = f; f = e; e = d + temp1; d = c; c = b; b = a; a = temp1 + temp2;
    }
    state->h[0] += a; state->h[1] += b; state->h[2] += c; state->h[3] += d;
    state->h[4] += e; state->h[5] += f; state->h[6] += g; state->h[7] += h;
}

static void sha256_init(struct sha256_state *state) {
    static const uint32_t initial[8] = {
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U,
    };
    memcpy(state->h, initial, sizeof(initial));
    state->bits = 0;
    state->used = 0;
}

static void sha256_update(struct sha256_state *state, const unsigned char *data, size_t size) {
    while (size != 0) {
        size_t count = 64U - state->used;
        if (count > size) count = size;
        memcpy(state->block + state->used, data, count);
        state->used += count;
        state->bits += (uint64_t)count * 8U;
        data += count;
        size -= count;
        if (state->used == 64U) {
            sha256_compress(state, state->block);
            state->used = 0;
        }
    }
}

static void sha256_final(struct sha256_state *state, unsigned char output[32]) {
    size_t index;
    uint64_t bits = state->bits;
    state->block[state->used++] = 0x80U;
    while (state->used != 56U) {
        if (state->used == 64U) {
            sha256_compress(state, state->block);
            state->used = 0;
        }
        state->block[state->used++] = 0;
    }
    for (index = 0; index < 8; ++index) {
        state->block[56U + index] = (unsigned char)(bits >> (56U - index * 8U));
    }
    sha256_compress(state, state->block);
    for (index = 0; index < 8; ++index) {
        output[index * 4] = (unsigned char)(state->h[index] >> 24U);
        output[index * 4 + 1] = (unsigned char)(state->h[index] >> 16U);
        output[index * 4 + 2] = (unsigned char)(state->h[index] >> 8U);
        output[index * 4 + 3] = (unsigned char)state->h[index];
    }
}

static int sha256_fd(int fd, unsigned char output[32], size_t limit) {
    unsigned char buffer[8192];
    struct sha256_state state;
    size_t total = 0;
    ssize_t count;
    if (lseek(fd, 0, SEEK_SET) < 0) return -1;
    sha256_init(&state);
    while ((count = read(fd, buffer, sizeof(buffer))) > 0) {
        total += (size_t)count;
        if (total > limit) return -1;
        sha256_update(&state, buffer, (size_t)count);
    }
    if (count < 0) return -1;
    sha256_final(&state, output);
    return lseek(fd, 0, SEEK_SET) == 0 ? 0 : -1;
}

static int set_cloexec(int fd, int value) {
    int flags = fcntl(fd, F_GETFD);
    if (flags < 0) return -1;
    if (value) flags |= FD_CLOEXEC; else flags &= ~FD_CLOEXEC;
    return fcntl(fd, F_SETFD, flags);
}

static int copy_sealed_file(const char *path, const char *name, int target, size_t limit) {
    int source = -1;
    int destination = -1;
    struct stat value;
    struct stat after;
    unsigned char buffer[8192];
    ssize_t count;
    size_t total = 0;
    source = open(path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (source < 0 || fstat(source, &value) < 0 || !S_ISREG(value.st_mode) ||
        value.st_uid != 0 || (value.st_mode & 0777) != 0444 || value.st_nlink != 1 ||
        value.st_size < 0 || (uintmax_t)value.st_size > limit) goto error;
    destination = memfd(name);
    if (destination < 0) goto error;
    while ((count = read(source, buffer, sizeof(buffer))) > 0) {
        total += (size_t)count;
        if (total > limit || write_all(destination, buffer, (size_t)count) < 0) goto error;
    }
    if (count < 0 || total != (size_t)value.st_size || fstat(source, &after) < 0 ||
        after.st_dev != value.st_dev || after.st_ino != value.st_ino || after.st_mode != value.st_mode ||
        after.st_uid != value.st_uid || after.st_nlink != value.st_nlink || after.st_size != value.st_size ||
        seal_fd(destination) < 0) goto error;
    if (destination != target && dup2(destination, target) < 0) goto error;
    if (destination != target) close(destination);
    close(source);
    return target;
error:
    if (source >= 0) close(source);
    if (destination >= 0) close(destination);
    return -1;
}

static int read_fd_bytes(int fd, unsigned char **result, size_t *size, size_t limit) {
    struct stat value;
    unsigned char *buffer;
    size_t offset = 0;
    ssize_t count;
    if (fstat(fd, &value) < 0 || !S_ISREG(value.st_mode) || value.st_size < 0 ||
        (uintmax_t)value.st_size > limit) return -1;
    buffer = malloc((size_t)value.st_size + 1U);
    if (buffer == NULL) return -1;
    while (offset < (size_t)value.st_size) {
        count = pread(fd, buffer + offset, (size_t)value.st_size - offset, (off_t)offset);
        if (count <= 0) {
            free(buffer);
            return -1;
        }
        offset += (size_t)count;
    }
    if (pread(fd, buffer + offset, 1, (off_t)offset) > 0) {
        free(buffer);
        return -1;
    }
    buffer[offset] = 0;
    *result = buffer;
    *size = offset;
    return 0;
}

static int hex_digest(const unsigned char digest[32], char output[65]) {
    static const char digits[] = "0123456789abcdef";
    size_t index;
    for (index = 0; index < 32U; ++index) {
        output[index * 2] = digits[digest[index] >> 4U];
        output[index * 2 + 1] = digits[digest[index] & 0x0fU];
    }
    output[64] = '\0';
    return 0;
}

static int json_string_field(const unsigned char *raw, size_t size, const char *key,
                             char *output, size_t capacity, size_t *matches) {
    size_t key_size = strlen(key);
    size_t index;
    *matches = 0;
    for (index = 0; index + key_size + 2U <= size; ++index) {
        size_t cursor;
        size_t written = 0;
        if (raw[index] != '"' || memcmp(raw + index + 1U, key, key_size) != 0 ||
            raw[index + key_size + 1U] != '"') continue;
        cursor = index + key_size + 2U;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size || raw[cursor++] != ':') return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size || raw[cursor++] != '"') return -1;
        while (cursor < size) {
            unsigned char character = raw[cursor++];
            if (character == '"') break;
            if (character == '\\' || character < 0x20U) return -1;
            if (written + 1U >= capacity) return -1;
            output[written++] = (char)character;
        }
        if (cursor == 0 || raw[cursor - 1U] != '"') return -1;
        output[written] = '\0';
        ++*matches;
        if (*matches > 1U) return -1;
    }
    return *matches == 1U ? 0 : -1;
}

static int json_read_string(const unsigned char *raw, size_t size, size_t *position,
                            char *output, size_t capacity) {
    size_t cursor = *position;
    size_t written = 0;
    if (cursor >= size || raw[cursor++] != '"') return -1;
    while (cursor < size) {
        unsigned char character = raw[cursor++];
        if (character == '"') {
            output[written] = '\0';
            *position = cursor;
            return 0;
        }
        if (character == '\\' || character < 0x20U || written + 1U >= capacity) return -1;
        output[written++] = (char)character;
    }
    return -1;
}

static int json_skip_string(const unsigned char *raw, size_t size, size_t *position) {
    size_t cursor = *position;
    if (cursor >= size || raw[cursor++] != '"') return -1;
    while (cursor < size) {
        unsigned char character = raw[cursor++];
        if (character == '"') {
            *position = cursor;
            return 0;
        }
        if (character == '\\' || character < 0x20U) return -1;
    }
    return -1;
}

static int json_skip_value(const unsigned char *raw, size_t size, size_t *position) {
    size_t cursor = *position;
    if (cursor >= size) return -1;
    if (raw[cursor] == '"') return json_skip_string(raw, size, position);
    if (raw[cursor] == '{' || raw[cursor] == '[') {
        size_t depth = 0;
        int quoted = 0;
        int escaped = 0;
        for (; cursor < size; ++cursor) {
            unsigned char character = raw[cursor];
            if (quoted) {
                if (escaped) escaped = 0;
                else if (character == '\\') escaped = 1;
                else if (character == '"') quoted = 0;
                continue;
            }
            if (character == '"') quoted = 1;
            else if (character == '{' || character == '[') ++depth;
            else if (character == '}' || character == ']') {
                if (depth == 0U) return -1;
                if (--depth == 0U) {
                    *position = cursor + 1U;
                    return 0;
                }
            }
        }
        return -1;
    }
    {
        size_t start = cursor;
        while (cursor < size && raw[cursor] != ',' && raw[cursor] != '}' && raw[cursor] != ']') ++cursor;
        if (cursor == start) return -1;
        *position = cursor;
    }
    return 0;
}

static int json_top_level_string_field(const unsigned char *raw, size_t size, const char *key,
                                       char *output, size_t capacity, size_t *matches) {
    size_t cursor = 0;
    char key_value[256];
    *matches = 0;
    if (size < 2U || raw[cursor++] != '{') return -1;
    while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                             raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
    if (cursor >= size || raw[cursor] == '}') return -1;
    for (;;) {
        size_t value_start;
        if (json_read_string(raw, size, &cursor, key_value, sizeof(key_value)) < 0) return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size || raw[cursor++] != ':') return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size) return -1;
        value_start = cursor;
        if (strcmp(key_value, key) == 0) {
            if (json_read_string(raw, size, &cursor, output, capacity) < 0) return -1;
            ++*matches;
            if (*matches > 1U) return -1;
        } else if (raw[cursor] == '"') {
            if (json_skip_string(raw, size, &cursor) < 0) return -1;
        } else if (json_skip_value(raw, size, &cursor) < 0) {
            return -1;
        }
        if (cursor <= value_start) return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size) return -1;
        if (raw[cursor] == '}') {
            ++cursor;
            return cursor == size && *matches == 1U ? 0 : -1;
        }
        if (raw[cursor++] != ',') return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size || raw[cursor] == '}') return -1;
    }
}

static int json_nested_object_string_field(const unsigned char *raw, size_t size,
                                           const char *object_key, const char *key,
                                           char *output, size_t capacity, size_t *matches) {
    size_t cursor = 0;
    char key_value[256];
    if (size < 2U || raw[cursor++] != '{') return -1;
    while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                             raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
    if (cursor >= size || raw[cursor] == '}') return -1;
    for (;;) {
        size_t value_start;
        if (json_read_string(raw, size, &cursor, key_value, sizeof(key_value)) < 0) return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size || raw[cursor++] != ':') return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size) return -1;
        value_start = cursor;
        if (strcmp(key_value, object_key) == 0) {
            if (raw[cursor] != '{' || json_skip_value(raw, size, &cursor) < 0) return -1;
            return json_top_level_string_field(raw + value_start, cursor - value_start, key,
                                               output, capacity, matches);
        }
        if (json_skip_value(raw, size, &cursor) < 0) return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size) return -1;
        if (raw[cursor] == '}') return -1;
        if (raw[cursor++] != ',') return -1;
        while (cursor < size && (raw[cursor] == ' ' || raw[cursor] == '\n' ||
                                 raw[cursor] == '\r' || raw[cursor] == '\t')) ++cursor;
        if (cursor >= size || raw[cursor] == '}') return -1;
    }
}

static int base64_value(unsigned char value) {
    if (value >= 'A' && value <= 'Z') return (int)value - 'A';
    if (value >= 'a' && value <= 'z') return (int)value - 'a' + 26;
    if (value >= '0' && value <= '9') return (int)value - '0' + 52;
    if (value == '-') return 62;
    if (value == '_') return 63;
    return -1;
}

static int decode_base64url(const char *encoded, unsigned char **result, size_t *size,
                            size_t limit) {
    size_t encoded_size = strlen(encoded);
    size_t output_size;
    size_t input = 0;
    size_t output = 0;
    unsigned char *buffer;
    if (encoded_size == 0 || encoded_size % 4U == 1U || encoded_size > (limit * 4U) / 3U + 4U)
        return -1;
    output_size = (encoded_size * 3U) / 4U;
    if (encoded_size % 4U == 2U) output_size = (encoded_size / 4U) * 3U + 1U;
    if (encoded_size % 4U == 3U) output_size = (encoded_size / 4U) * 3U + 2U;
    if (output_size > limit) return -1;
    buffer = malloc(output_size + 1U);
    if (buffer == NULL) return -1;
    while (input < encoded_size) {
        int a = base64_value((unsigned char)encoded[input++]);
        int b;
        int c = 0;
        int d = 0;
        if (a < 0 || input >= encoded_size) goto error;
        b = base64_value((unsigned char)encoded[input++]);
        if (b < 0) goto error;
        buffer[output++] = (unsigned char)((a << 2) | (b >> 4));
        if (input < encoded_size) {
            c = base64_value((unsigned char)encoded[input++]);
            if (c < 0) goto error;
            if (output < output_size) buffer[output++] = (unsigned char)((b << 4) | (c >> 2));
        }
        if (input < encoded_size) {
            d = base64_value((unsigned char)encoded[input++]);
            if (d < 0) goto error;
            if (output < output_size) buffer[output++] = (unsigned char)((c << 6) | d);
        }
        if (input == encoded_size && encoded_size % 4U == 2U && (b & 0x0f) != 0) goto error;
        if (input == encoded_size && encoded_size % 4U == 3U && (c & 0x03) != 0) goto error;
    }
    if (output != output_size) goto error;
    buffer[output] = 0;
    *result = buffer;
    *size = output;
    return 0;
error:
    free(buffer);
    return -1;
}

static int find_manifest_binding(const unsigned char *raw, size_t size, char *digest,
                                 size_t capacity) {
    static const char target[] = "\"target\": \"/usr/local/libexec/align-llm/request6-adoption-entrypoint\"";
    size_t index;
    size_t found = 0;
    const unsigned char *object = NULL;
    size_t object_size = 0;
    for (index = 0; index + sizeof(target) - 1U <= size; ++index) {
        if (memcmp(raw + index, target, sizeof(target) - 1U) != 0) continue;
        ++found;
        if (found != 1U) return -1;
        object = raw + index;
        while (object > raw && object[-1] != '{') --object;
        if (object == raw) return -1;
        --object;
        {
            size_t cursor = (size_t)(object - raw);
            int depth = 0;
            int quoted = 0;
            int escaped = 0;
            for (; cursor < size; ++cursor) {
                unsigned char character = raw[cursor];
                if (quoted) {
                    if (escaped) escaped = 0;
                    else if (character == '\\') escaped = 1;
                    else if (character == '"') quoted = 0;
                    continue;
                }
                if (character == '"') quoted = 1;
                else if (character == '{') ++depth;
                else if (character == '}' && --depth == 0) {
                    object_size = cursor + 1U - (size_t)(object - raw);
                    break;
                }
            }
        }
    }
    if (found != 1U || object == NULL || object_size == 0U) return -1;
    {
        size_t matches;
        char source[256];
        char target_value[256];
        char kind[32];
        char binding_manifest_digest[65];
        if (json_top_level_string_field(object, object_size, "source", source, sizeof(source), &matches) < 0 ||
            strcmp(source, "/usr/local/libexec/align-llm/request6-adoption-entrypoint") != 0 ||
            json_top_level_string_field(object, object_size, "target", target_value, sizeof(target_value), &matches) < 0 ||
            strcmp(target_value, source) != 0 ||
            json_top_level_string_field(object, object_size, "kind", kind, sizeof(kind), &matches) < 0 ||
            strcmp(kind, "file") != 0 ||
            json_top_level_string_field(object, object_size, "manifest_sha256", binding_manifest_digest,
                              sizeof(binding_manifest_digest), &matches) < 0 ||
            json_nested_object_string_field(object, object_size, "manifest", "sha256", digest,
                                            capacity, &matches) < 0) {
            return -1;
        }
    }
    return 0;
}

static int static_pie_elf(int fd) {
    unsigned char header[64];
    uint16_t type;
    uint16_t machine;
    if (pread(fd, header, sizeof(header), 0) != (ssize_t)sizeof(header) ||
        memcmp(header, "\x7f" "ELF", 4) != 0 || header[4] != 2 || header[5] != 1 ||
        header[6] != 1) return -1;
    type = (uint16_t)header[16] | ((uint16_t)header[17] << 8U);
    machine = (uint16_t)header[18] | ((uint16_t)header[19] << 8U);
    return type == 3U && machine == 62U ? 0 : -1;
}

static int ordinary_preflight(void) {
    struct stat attestation;
    struct stat manifest;
    struct stat dispatcher;
    unsigned char digest[32];
    unsigned char *attestation_raw = NULL;
    unsigned char *manifest_raw = NULL;
    unsigned char *predicate_raw = NULL;
    size_t attestation_size = 0;
    size_t manifest_size = 0;
    size_t predicate_size = 0;
    char encoded_payload[131072];
    char field[256];
    char manifest_digest[65];
    char supervisor_digest[65];
    char dispatcher_digest[65];
    char actual_digest[65];
    size_t matches;
    int self_fd = -1;
    ordinary_debug("preflight: start\n");
    if (fstat(6, &attestation) < 0 || fstat(8, &manifest) < 0 || fstat(14, &dispatcher) < 0 ||
        !S_ISREG(attestation.st_mode) || !S_ISREG(manifest.st_mode) || !S_ISREG(dispatcher.st_mode) ||
        attestation.st_nlink != 0 || manifest.st_nlink != 0 ||
        (fcntl(6, F_GET_SEALS) != REQUIRED_SEALS) || (fcntl(8, F_GET_SEALS) != REQUIRED_SEALS) ||
        dispatcher.st_uid != 0 || (dispatcher.st_mode & 0777) != 0755 ||
        attestation.st_size <= 0 || attestation.st_size > 262144 ||
        manifest.st_size <= 0 || manifest.st_size > 67108864) {
        return -1;
    }
    ordinary_debug("preflight: fd checks passed\n");
    if (static_pie_elf(14) < 0 || read_fd_bytes(6, &attestation_raw, &attestation_size, 262144) < 0 ||
        read_fd_bytes(8, &manifest_raw, &manifest_size, 67108864) < 0) goto failure;
    ordinary_debug("preflight: input bytes read\n");
    self_fd = open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
    if (self_fd < 0 || sha256_fd(self_fd, digest, 16U * 1024U * 1024U) < 0) goto failure;
    close(self_fd);
    self_fd = -1;
    hex_digest(digest, actual_digest);
    if (json_string_field(attestation_raw, attestation_size, "payloadType", field, sizeof(field), &matches) < 0 ||
        strcmp(field, "https://align-llm.dev/attestations/runner-image/v1") != 0 ||
        json_string_field(attestation_raw, attestation_size, "payload", encoded_payload, sizeof(encoded_payload), &matches) < 0 ||
        json_string_field(attestation_raw, attestation_size, "keyid", field, sizeof(field), &matches) < 0 ||
        strcmp(field, "align-llm-runner-image-v1") != 0 ||
        json_string_field(attestation_raw, attestation_size, "sig", field, sizeof(field), &matches) < 0) goto failure;
    ordinary_debug("preflight: attestation parsed\n");
    if (decode_base64url(field, &predicate_raw, &predicate_size, 64U) < 0 || predicate_size != 64U) goto failure;
    free(predicate_raw);
    predicate_raw = NULL;
    if (decode_base64url(encoded_payload, &predicate_raw, &predicate_size, 65536U) < 0) goto failure;
    if (json_string_field(predicate_raw, predicate_size, "supervisor_path", field, sizeof(field), &matches) < 0 ||
        strcmp(field, "/usr/local/libexec/align-llm/fresh-supervise") != 0 ||
        json_string_field(predicate_raw, predicate_size, "manifest_path", field, sizeof(field), &matches) < 0 ||
        strcmp(field, "/usr/local/share/align-llm/fresh-toolchain.json") != 0 ||
        json_string_field(predicate_raw, predicate_size, "supervisor_sha256", supervisor_digest, sizeof(supervisor_digest), &matches) < 0 ||
        strcmp(supervisor_digest, actual_digest) != 0 ||
        json_string_field(predicate_raw, predicate_size, "manifest_sha256", manifest_digest, sizeof(manifest_digest), &matches) < 0 ||
        sha256_fd(8, digest, 67108864U) < 0 || hex_digest(digest, actual_digest) != 0 ||
        strcmp(manifest_digest, actual_digest) != 0 ||
        find_manifest_binding(manifest_raw, manifest_size, dispatcher_digest, sizeof(dispatcher_digest)) < 0 ||
        sha256_fd(14, digest, 16U * 1024U * 1024U) < 0 || hex_digest(digest, actual_digest) != 0 ||
        strcmp(dispatcher_digest, actual_digest) != 0) goto failure;
    ordinary_debug("preflight: success\n");
    free(attestation_raw);
    free(manifest_raw);
    free(predicate_raw);
    return 0;
failure:
    ordinary_debug("preflight: failure\n");
    if (self_fd >= 0) close(self_fd);
    free(attestation_raw);
    free(manifest_raw);
    free(predicate_raw);
    return -1;
}

static int wait_preflight(pid_t pid, int output_fd, int error_fd) {
    struct pollfd fds[2] = {{output_fd, POLLIN, 0}, {error_fd, POLLIN, 0}};
    struct timespec start;
    int status = 0;
    int closed[2] = {0, 0};
    int output = 0;
    int failure = 0;
    int reaped = 0;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (;;) {
        struct timespec now;
        int poll_result;
        pid_t waited = 0;
        if (!reaped) {
            waited = waitpid(pid, &status, WNOHANG);
            if (waited == pid) {
                reaped = 1;
                if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) failure = 1;
            } else if (waited < 0 && errno != EINTR) {
                failure = 1;
            }
        }
        while (!closed[0] || !closed[1]) {
            unsigned char discard[8192];
            ssize_t count = read(closed[0] ? error_fd : output_fd, discard, sizeof(discard));
            int index = closed[0] ? 1 : 0;
            if (count > 0) {
                output = 1;
                continue;
            }
            if (count == 0) {
                closed[index] = 1;
                break;
            }
            if (errno == EINTR) continue;
            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
            failure = 1;
            closed[index] = 1;
            break;
        }
        if (reaped && closed[0] && closed[1]) break;
        clock_gettime(CLOCK_MONOTONIC, &now);
        if ((now.tv_sec - start.tv_sec) > ORDINARY_PREFLIGHT_SECONDS ||
            ((now.tv_sec - start.tv_sec) == ORDINARY_PREFLIGHT_SECONDS &&
             now.tv_nsec >= start.tv_nsec)) failure = 1;
        if (failure && !reaped) {
            if (kill(pid, SIGKILL) < 0 && errno != ESRCH) failure = 1;
        }
        if (failure && reaped) {
            if (!closed[0]) { close(output_fd); closed[0] = 1; }
            if (!closed[1]) { close(error_fd); closed[1] = 1; }
            break;
        }
        fds[0].fd = closed[0] ? -1 : output_fd;
        fds[0].events = POLLIN;
        fds[0].revents = 0;
        fds[1].fd = closed[1] ? -1 : error_fd;
        fds[1].events = POLLIN;
        fds[1].revents = 0;
        poll_result = poll(fds, 2, 20);
        if (poll_result < 0 && errno != EINTR) failure = 1;
    }
    if (!closed[0]) close(output_fd);
    if (!closed[1]) close(error_fd);
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    return !failure && output == 0 && WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
}

static int run_ordinary_preflight(void) {
    int output_pipe[2] = {-1, -1};
    int error_pipe[2] = {-1, -1};
    pid_t child;
    if (pipe2(output_pipe, O_CLOEXEC | O_NONBLOCK) < 0) goto failure;
    if (pipe2(error_pipe, O_CLOEXEC | O_NONBLOCK) < 0) goto failure;
    child = fork();
    if (child < 0) goto failure;
    if (child == 0) {
        int null_fd = open("/dev/null", O_RDONLY | O_CLOEXEC);
        struct rlimit limits = {64, 64};
        struct rlimit file_limit = {0, 0};
        if (null_fd < 0 || dup2(null_fd, STDIN_FILENO) < 0 || dup2(output_pipe[1], STDOUT_FILENO) < 0 ||
            dup2(error_pipe[1], STDERR_FILENO) < 0 || prctl(PR_SET_PDEATHSIG, SIGKILL) < 0) _exit(127);
        if (setrlimit(RLIMIT_NOFILE, &limits) < 0 || setrlimit(RLIMIT_FSIZE, &file_limit) < 0) _exit(127);
        if (null_fd > STDERR_FILENO) close(null_fd);
        close(output_pipe[0]); close(output_pipe[1]); close(error_pipe[0]); close(error_pipe[1]);
        if (syscall(SYS_close_range, 3U, 5U, 0U) < 0 || syscall(SYS_close_range, 7U, 7U, 0U) < 0 ||
            syscall(SYS_close_range, 9U, 13U, 0U) < 0 ||
            syscall(SYS_close_range, 15U, UINT_MAX, 0U) < 0) _exit(127);
        _exit(ordinary_preflight() == 0 ? 0 : 1);
    }
    close(output_pipe[1]); close(error_pipe[1]);
    return wait_preflight(child, output_pipe[0], error_pipe[0]);
failure:
    if (output_pipe[0] >= 0) close(output_pipe[0]);
    if (output_pipe[1] >= 0) close(output_pipe[1]);
    if (error_pipe[0] >= 0) close(error_pipe[0]);
    if (error_pipe[1] >= 0) close(error_pipe[1]);
    return -1;
}

static int ordinary_environment(char **child_env, char **align_entry) {
    static char path[] = "PATH=/usr/bin:/bin";
    static char locale[] = "LC_ALL=C";
    static char language[] = "LANG=C";
    static char home[] = "HOME=/nonexistent";
    static char temporary[] = "TMPDIR=/tmp";
    static const char *names[] = {"PATH", "LC_ALL", "LANG", "HOME", "TMPDIR", "ALIGN_REPO"};
    static const char *values[] = {"/usr/bin:/bin", "C", "C", "/nonexistent", "/tmp", NULL};
    int seen[6] = {0, 0, 0, 0, 0, 0};
    int index;
    *align_entry = NULL;
    for (index = 0; environ[index] != NULL; ++index) {
        int found = 0;
        int name_index;
        for (name_index = 0; name_index < 6; ++name_index) {
            size_t name_size = strlen(names[name_index]);
            if (strncmp(environ[index], names[name_index], name_size) != 0 ||
                environ[index][name_size] != '=') continue;
            if (seen[name_index] != 0 ||
                (values[name_index] != NULL && strcmp(environ[index] + name_size + 1, values[name_index]) != 0) ||
                (values[name_index] == NULL && environ[index][name_size + 1] == '\0')) return -1;
            seen[name_index] = 1;
            found = 1;
            if (name_index == 5) *align_entry = environ[index];
            break;
        }
        if (!found) return -1;
    }
    for (index = 0; index < 6; ++index) if (seen[index] == 0) return -1;
    child_env[0] = path;
    child_env[1] = locale;
    child_env[2] = language;
    child_env[3] = home;
    child_env[4] = temporary;
    child_env[5] = *align_entry;
    child_env[6] = NULL;
    return 0;
}

static int canonical_absolute(const char *path) {
    size_t length;
    size_t index;
    if (path == NULL || path[0] != '/') return -1;
    length = strlen(path);
    if (length < 2U || length >= PATH_MAX || path[length - 1U] == '/') return -1;
    for (index = 1; index < length; ++index) {
        unsigned char value = (unsigned char)path[index];
        if (value < 0x20U || value == 0x7fU ||
            (value == '/' && index + 1U < length && path[index + 1U] == '/')) return -1;
        if (value == '.' && (index == 1U || path[index - 1U] == '/') &&
            (index + 1U == length || path[index + 1U] == '/' ||
             (path[index + 1U] == '.' && (index + 2U == length || path[index + 2U] == '/')))) return -1;
    }
    return 0;
}

static int append_text(char *output, size_t capacity, size_t *used, const char *text) {
    size_t length = strlen(text);
    if (*used + length + 1U > capacity) return -1;
    memcpy(output + *used, text, length);
    *used += length;
    output[*used] = '\0';
    return 0;
}

static int relative_path(const char *project, const char *align, char *output, size_t capacity) {
    const char *project_cursor = project + 1;
    const char *align_cursor = align + 1;
    const char *project_remainder;
    const char *align_remainder;
    size_t project_count;
    size_t project_common_end = 1U;
    size_t align_common_end = 1U;
    size_t used = 0;
    size_t index;
    if (canonical_absolute(project) < 0 || canonical_absolute(align) < 0) return -1;
    while (*project_cursor != '\0' && *align_cursor != '\0') {
        const char *project_end = strchr(project_cursor, '/');
        const char *align_end = strchr(align_cursor, '/');
        size_t project_size = project_end == NULL ? strlen(project_cursor) : (size_t)(project_end - project_cursor);
        size_t align_size = align_end == NULL ? strlen(align_cursor) : (size_t)(align_end - align_cursor);
        if (project_size != align_size || memcmp(project_cursor, align_cursor, project_size) != 0) break;
        project_common_end = (size_t)((project_end == NULL ? project + strlen(project) : project_end) - project);
        align_common_end = (size_t)((align_end == NULL ? align + strlen(align) : align_end) - align);
        project_cursor = project_end == NULL ? project_cursor + project_size : project_end + 1;
        align_cursor = align_end == NULL ? align_cursor + align_size : align_end + 1;
        if (project_end == NULL || align_end == NULL) break;
    }
    project_remainder = project + project_common_end;
    if (*project_remainder == '/') ++project_remainder;
    align_remainder = align + align_common_end;
    if (*align_remainder == '/') ++align_remainder;
    if (*project_remainder != '\0') {
        project_count = 1U;
        for (index = 0; project_remainder[index] != '\0'; ++index)
            if (project_remainder[index] == '/') ++project_count;
    } else project_count = 0;
    for (index = 0; index < project_count; ++index) {
        if (used != 0U && append_text(output, capacity, &used, "/") < 0) return -1;
        if (append_text(output, capacity, &used, "..") < 0) return -1;
    }
    if (*align_remainder != '\0') {
        if (used != 0U && append_text(output, capacity, &used, "/") < 0) return -1;
        if (append_text(output, capacity, &used, align_remainder) < 0) return -1;
    }
    return used == 0U ? -1 : 0;
}

static int open_align_root(const char *absolute) {
    char *cursor;
    int current = 17;
    if (canonical_absolute(absolute) < 0) return -1;
    cursor = (char *)absolute + 1;
    while (*cursor != '\0') {
        char component[NAME_MAX + 1];
        char *end = strchr(cursor, '/');
        size_t length = end == NULL ? strlen(cursor) : (size_t)(end - cursor);
        int next;
        if (length == 0U || length > NAME_MAX) return -1;
        memcpy(component, cursor, length);
        component[length] = '\0';
        next = openat(current, component, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (next < 0) return -1;
        if (current != 17) close(current);
        current = next;
        cursor = end == NULL ? cursor + length : end + 1;
    }
    if (dup2(current, 18) < 0 || set_cloexec(18, 1) < 0) {
        if (current != 18) close(current);
        return -1;
    }
    if (current != 18) close(current);
    return 0;
}

static int create_nonce(unsigned char nonce[ORDINARY_TICKET_BYTES]) {
    int fd = memfd("align-llm-ordinary-adoption-nonce");
    size_t offset = 0;
    ssize_t count;
    if (fd < 0) return -1;
    while (offset < ORDINARY_TICKET_BYTES) {
        count = syscall(SYS_getrandom, nonce + offset, ORDINARY_TICKET_BYTES - offset, 0U);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { close(fd); return -1; }
        offset += (size_t)count;
    }
    if (write_all(fd, nonce, ORDINARY_TICKET_BYTES) < 0 || seal_fd(fd) < 0 ||
        dup2(fd, 15) < 0 || set_cloexec(15, 1) < 0) {
        close(fd);
        return -1;
    }
    if (fd != 15) close(fd);
    return 0;
}

static int set_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL);
    return flags < 0 ? -1 : fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

static int capture_stream(int fd, unsigned char *buffer, size_t *used, int *overflow, int *eof) {
    unsigned char chunk[8192];
    for (;;) {
        ssize_t count = read(fd, chunk, sizeof(chunk));
        if (count > 0) {
            if (*used + (size_t)count > ORDINARY_STREAM_LIMIT) *overflow = 1;
            else { memcpy(buffer + *used, chunk, (size_t)count); *used += (size_t)count; }
            continue;
        }
        if (count == 0) { *eof = 1; return 0; }
        if (errno == EINTR) continue;
        if (errno == EAGAIN || errno == EWOULDBLOCK) return 0;
        return -1;
    }
}

static int expected_dispatcher_result(int status, const unsigned char *stdout_buffer, size_t stdout_size,
                                      const unsigned char *stderr_buffer, size_t stderr_size) {
    static const char *phases[] = {"input", "toolchain", "revision", "build", "fixture", "cleanup", "unobserved"};
    char expected[96];
    size_t phase;
    if (!WIFEXITED(status)) return -1;
    if (WEXITSTATUS(status) == 0)
        return stdout_size == 25U && memcmp(stdout_buffer, "json-scan adoption: PASS\n", 25U) == 0 && stderr_size == 0U ? 0 : -1;
    if (WEXITSTATUS(status) < 1 || WEXITSTATUS(status) > 7 || stdout_size != 0U) return -1;
    phase = (size_t)WEXITSTATUS(status) - 1U;
    if (snprintf(expected, sizeof(expected), "json-scan adoption: ERROR %s\n", phases[phase]) < 0) return -1;
    return strlen(expected) == stderr_size && memcmp(stderr_buffer, expected, stderr_size) == 0 ? 0 : -1;
}

static int ordinary_parent_loop(pid_t child, int channel_fd, int stdout_fd, int stderr_fd,
                                const unsigned char ticket[32], const unsigned char nonce[32]) {
    unsigned char stdout_buffer[ORDINARY_STREAM_LIMIT];
    unsigned char stderr_buffer[ORDINARY_STREAM_LIMIT];
    unsigned char capsule_digest[32];
    unsigned char proof[32];
    unsigned char ticket_digest[32];
    struct sha256_state proof_state;
    struct timespec start;
    size_t stdout_size = 0;
    size_t stderr_size = 0;
    int stdout_eof = 0;
    int stderr_eof = 0;
    int got_capsule = 0;
    int proof_sent = 0;
    int channel_hup = 0;
    int overflow = 0;
    int status = 0;
    int reaped = 0;
    int failure = 0;
    if (set_nonblocking(stdout_fd) < 0 || set_nonblocking(stderr_fd) < 0) {
        close(stdout_fd);
        close(stderr_fd);
        return -1;
    }
    if (send(channel_fd, ticket, 32U, MSG_NOSIGNAL) != 32) {
        ordinary_debug("parent: ticket send failed\n");
        close(stdout_fd);
        close(stderr_fd);
        return -1;
    }
    ordinary_debug("parent: loop start\n");
    clock_gettime(CLOCK_MONOTONIC, &start);
    while (!reaped || !stdout_eof || !stderr_eof || !channel_hup) {
        struct pollfd fds[3];
        nfds_t nfds = 0;
        struct timespec now;
        int poll_result;
        pid_t waited = 0;
        if (!reaped) {
            waited = waitpid(child, &status, WNOHANG);
            if (waited == child) {
                reaped = 1;
                ordinary_debug("parent: dispatcher reaped\n");
            }
            else if (waited < 0 && errno != EINTR) {
                ordinary_debug("parent: waitpid error\n");
                failure = 1;
            }
        }
        if (!stdout_eof) fds[nfds++] = (struct pollfd){stdout_fd, POLLIN, 0};
        if (!stderr_eof) fds[nfds++] = (struct pollfd){stderr_fd, POLLIN, 0};
        fds[nfds++] = (struct pollfd){channel_fd, POLLIN, 0};
        poll_result = poll(fds, nfds, 1000);
        if (poll_result < 0 && errno != EINTR) {
            ordinary_debug("parent: poll error\n");
            failure = 1;
        }
        if (!stdout_eof && capture_stream(stdout_fd, stdout_buffer, &stdout_size, &overflow, &stdout_eof) < 0) {
            ordinary_debug("parent: stdout read error\n");
            failure = 1;
        }
        if (!stderr_eof && capture_stream(stderr_fd, stderr_buffer, &stderr_size, &overflow, &stderr_eof) < 0) {
            ordinary_debug("parent: stderr read error\n");
            failure = 1;
        }
        if (poll_result > 0) {
            unsigned char packet[33];
            struct msghdr message;
            struct iovec vector;
            ssize_t received;
            memset(&message, 0, sizeof(message));
            vector.iov_base = packet;
            vector.iov_len = sizeof(packet);
            message.msg_iov = &vector;
            message.msg_iovlen = 1;
            received = recvmsg(channel_fd, &message, MSG_DONTWAIT);
            if (received == 0) {
                channel_hup = 1;
                ordinary_debug("parent: channel hup\n");
            }
            else if (received < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) {
                ordinary_debug("parent: recv error\n");
                failure = 1;
            }
            else if (received > 0) {
                if (got_capsule || received != 32 || (message.msg_flags & MSG_TRUNC)) {
                    ordinary_debug("parent: invalid capsule packet\n");
                    failure = 1;
                }
                else {
                    memcpy(capsule_digest, packet, 32U);
                    got_capsule = 1;
                    ordinary_debug("parent: capsule received\n");
                }
            }
        }
        if (channel_hup && !got_capsule) failure = 1;
        if (got_capsule && !proof_sent && !failure) {
            sha256_init(&proof_state);
            sha256_update(&proof_state, ticket, 32U);
            sha256_final(&proof_state, ticket_digest);
            sha256_init(&proof_state);
            sha256_update(&proof_state, (const unsigned char *)"align-llm/ordinary-adoption/worker-admission/v2\0", sizeof("align-llm/ordinary-adoption/worker-admission/v2\0") - 1U);
            sha256_update(&proof_state, ticket_digest, 32U);
            sha256_update(&proof_state, nonce, 32U);
            sha256_update(&proof_state, capsule_digest, 32U);
            sha256_final(&proof_state, proof);
            if (send(channel_fd, proof, 32U, MSG_NOSIGNAL) != 32) {
                ordinary_debug("parent: proof send error\n");
                failure = 1;
            }
            else {
                proof_sent = 1;
                ordinary_debug("parent: proof sent\n");
            }
        }
        clock_gettime(CLOCK_MONOTONIC, &now);
        if ((now.tv_sec - start.tv_sec) > ORDINARY_WORKER_SECONDS ||
            ((now.tv_sec - start.tv_sec) == ORDINARY_WORKER_SECONDS && now.tv_nsec >= start.tv_nsec)) failure = 1;
        if (failure) break;
        if (reaped && channel_hup && stdout_eof && stderr_eof) break;
    }
    ordinary_debug("parent: loop end\n");
    ordinary_debug_parent_state(failure, reaped, stdout_eof, stderr_eof, channel_hup, got_capsule, proof_sent, status);
    if (failure || !reaped || !stdout_eof || !stderr_eof || !channel_hup || !got_capsule || !proof_sent ||
        expected_dispatcher_result(status, stdout_buffer, stdout_size, stderr_buffer, stderr_size) < 0) {
        ordinary_debug("parent: failure state\n");
        if (stderr_size != 0) ordinary_debug_bytes(stderr_buffer, stderr_size);
        if (!reaped) {
            kill(child, SIGKILL);
            while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
        }
        close(stdout_fd);
        close(stderr_fd);
        return -1;
    }
    close(stdout_fd);
    close(stderr_fd);
    if (write_all(STDOUT_FILENO, stdout_buffer, stdout_size) < 0 ||
        write_all(STDERR_FILENO, stderr_buffer, stderr_size) < 0) return -1;
    return WEXITSTATUS(status) == 0 ? 0 : 1;
}

static int random_bytes(unsigned char *buffer, size_t size) {
    size_t offset = 0;
    while (offset < size) {
        ssize_t count = syscall(SYS_getrandom, buffer + offset, size - offset, 0U);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return -1;
        offset += (size_t)count;
    }
    return 0;
}

static void ordinary_dispatcher_child(int child_socket, int stdout_write, int stderr_write,
                                      char **child_env, const char *absolute, const char *relative) {
    char *arguments[] = {
        (char *)"request6-adoption-entrypoint", (char *)"--mode", (char *)"ordinary-adoption",
        (char *)"--project-root-fd", (char *)"4", (char *)"--image-attestation-fd", (char *)"6",
        (char *)"--manifest-fd", (char *)"8", (char *)"--align-repo-root-fd", (char *)"18",
        (char *)"--align-repo-absolute", (char *)absolute, (char *)"--align-repo-relative", (char *)relative,
        (char *)"--invocation-nonce-fd", (char *)"15", (char *)"--supervisor-channel-fd", (char *)"16", NULL,
    };
    int null_fd = open("/dev/null", O_RDONLY | O_CLOEXEC);
    if (null_fd < 0 || dup2(null_fd, STDIN_FILENO) < 0 || dup2(child_socket, 16) < 0 ||
        dup2(stdout_write, STDOUT_FILENO) < 0 || dup2(stderr_write, STDERR_FILENO) < 0 ||
        prctl(PR_SET_PDEATHSIG, SIGKILL) < 0 || getppid() <= 1) _exit(127);
    if (null_fd > STDERR_FILENO) close(null_fd);
    if (child_socket != 16) close(child_socket);
    if (stdout_write != STDOUT_FILENO) close(stdout_write);
    if (stderr_write != STDERR_FILENO) close(stderr_write);
    if (set_cloexec(4, 0) < 0 || set_cloexec(6, 0) < 0 || set_cloexec(8, 0) < 0 ||
        set_cloexec(15, 0) < 0 || set_cloexec(16, 0) < 0 || set_cloexec(18, 0) < 0 ||
        chdir("/proc/self/fd/4") < 0 || syscall(SYS_close_range, 3U, 3U, 0U) < 0 ||
        syscall(SYS_close_range, 5U, 5U, 0U) < 0 || syscall(SYS_close_range, 7U, 7U, 0U) < 0 ||
        syscall(SYS_close_range, 9U, 13U, 0U) < 0 || syscall(SYS_close_range, 17U, 17U, 0U) < 0 ||
        syscall(SYS_close_range, 19U, UINT_MAX, 0U) < 0) _exit(127);
    (void)syscall(SYS_execveat, 14, "", arguments, child_env, AT_EMPTY_PATH);
    _exit(127);
}

static int ordinary_supervise(char **child_env, const char *absolute) {
    char project_path[PATH_MAX];
    char relative[PATH_MAX];
    unsigned char nonce[ORDINARY_TICKET_BYTES];
    unsigned char ticket[ORDINARY_TICKET_BYTES];
    int dispatcher_fd = -1;
    int project_fd = -1;
    int root_fd = -1;
    int socket_pair[2] = {-1, -1};
    int output_pipe[2] = {-1, -1};
    int error_pipe[2] = {-1, -1};
    pid_t child = -1;
    int result = -1;
    if (canonical_absolute(absolute) < 0 ||
        copy_sealed_file(IMAGE_ATTESTATION_PATH, "align-llm-image-attestation", 6, 262144U) < 0 ||
        copy_sealed_file(MANIFEST_PATH, "align-llm-fresh-manifest", 8, 67108864U) < 0) goto cleanup;
    dispatcher_fd = open(ORDINARY_DISPATCHER_PATH, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (dispatcher_fd < 0) goto cleanup;
    {
        struct stat value;
        if (fstat(dispatcher_fd, &value) < 0 || !S_ISREG(value.st_mode) || value.st_uid != 0 ||
            value.st_nlink != 1 || (value.st_mode & 0777) != 0755 || value.st_size <= 0 ||
            (uintmax_t)value.st_size > 16U * 1024U * 1024U || dup2(dispatcher_fd, 14) < 0 ||
            set_cloexec(14, 1) < 0) goto cleanup;
    }
    if (dispatcher_fd != 14) { close(dispatcher_fd); dispatcher_fd = 14; }
    if (run_ordinary_preflight() < 0) {
        ordinary_debug("supervise: preflight failed\n");
        goto cleanup;
    }
    ordinary_debug("supervise: preflight passed\n");
    project_fd = open(".", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (project_fd < 0 || dup2(project_fd, 4) < 0 || set_cloexec(4, 1) < 0) goto cleanup;
    if (project_fd != 4) { close(project_fd); project_fd = 4; }
    if (getcwd(project_path, sizeof(project_path)) == NULL || relative_path(project_path, absolute, relative, sizeof(relative)) < 0) goto cleanup;
    root_fd = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root_fd < 0 || dup2(root_fd, 17) < 0 || set_cloexec(17, 1) < 0) goto cleanup;
    if (root_fd != 17) { close(root_fd); root_fd = 17; }
    if (open_align_root(absolute) < 0 || close(17) < 0) goto cleanup;
    root_fd = -1;
    if (create_nonce(nonce) < 0 || random_bytes(ticket, sizeof(ticket)) < 0) goto cleanup;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, socket_pair) < 0 ||
        dup2(socket_pair[0], 16) < 0 || set_cloexec(16, 1) < 0) goto cleanup;
    if (socket_pair[0] != 16) { close(socket_pair[0]); socket_pair[0] = 16; }
    if (pipe2(output_pipe, O_CLOEXEC | O_NONBLOCK) < 0 || pipe2(error_pipe, O_CLOEXEC | O_NONBLOCK) < 0) goto cleanup;
    child = fork();
    if (child < 0) goto cleanup;
    if (child == 0) ordinary_dispatcher_child(socket_pair[1], output_pipe[1], error_pipe[1], child_env, absolute, relative);
    close(socket_pair[1]); socket_pair[1] = -1;
    close(output_pipe[1]); output_pipe[1] = -1;
    close(error_pipe[1]); error_pipe[1] = -1;
    close(14); dispatcher_fd = -1;
    result = ordinary_parent_loop(child, 16, output_pipe[0], error_pipe[0], ticket, nonce);
    ordinary_debug(result == 0 ? "supervise: parent loop passed\n" : "supervise: parent loop failed\n");
    output_pipe[0] = -1;
    error_pipe[0] = -1;
cleanup:
    if (child > 0 && result < 0) {
        if (kill(child, SIGKILL) < 0 && errno != ESRCH) result = -1;
        while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
    }
    for (int fd = 0; fd < 2; ++fd) {
        if (socket_pair[fd] >= 0) close(socket_pair[fd]);
    }
    for (int fd = 0; fd < 2; ++fd) {
        if (output_pipe[fd] >= 0) close(output_pipe[fd]);
        if (error_pipe[fd] >= 0) close(error_pipe[fd]);
    }
    for (int fd = 4; fd <= 18; ++fd) {
        if (fd == 5 || fd == 7 || fd == 9 || fd == 10 || fd == 11 || fd == 12 || fd == 13 || fd == 14 || fd == 17) continue;
        close(fd);
    }
    return result;
}

int main(int argc, char **argv) {
    char *child_argv[16];
    char *child_env[7];
    char *align_entry = NULL;
    int self_fd;
    int index;
    if (argc == 3 && strcmp(argv[1], "--mode") == 0 && strcmp(argv[2], "ordinary-adoption") == 0) {
        int ordinary_status;
        if (ordinary_environment(child_env, &align_entry) < 0 || align_entry == NULL ||
            strlen(align_entry + strlen("ALIGN_REPO=")) >= PATH_MAX) return fail_argument();
        ordinary_status = ordinary_supervise(child_env, align_entry + strlen("ALIGN_REPO="));
        if (ordinary_status < 0) return fail();
        return ordinary_status;
    }
    int strict_boundary = argc >= 3 && strcmp(argv[1], "--mode") == 0 &&
                          strcmp(argv[2], "ordinary-adoption-boundary") == 0;

    if (sanitize_environment(child_env, strict_boundary) < 0) {
        return fail_argument();
    }
    if (argc > 10) {
        return fail_argument();
    }
    if (snapshot_payload() < 0) {
        return fail();
    }
    self_fd = open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
    if (self_fd < 0 || dup2(self_fd, 10) < 0 || fcntl(10, F_SETFD, 0) < 0) {
        if (self_fd >= 0) {
            close(self_fd);
        }
        return fail();
    }
    if (self_fd != 10) {
        close(self_fd);
    }
    child_argv[0] = (char *)PYTHON_PATH;
    child_argv[1] = "-I";
    child_argv[2] = "-B";
    child_argv[3] = "/proc/self/fd/11";
    child_argv[4] = "--embedded-self-fd";
    child_argv[5] = "10";
    for (index = 1; index < argc; ++index) {
        child_argv[index + 5] = argv[index];
    }
    child_argv[argc + 5] = NULL;
    if (close_unexpected_descriptors() < 0) {
        return fail();
    }
    execve(PYTHON_PATH, child_argv, child_env);
    return fail();
}
