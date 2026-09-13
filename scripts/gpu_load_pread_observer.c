/* Test-only pread observation and fault injection for the GPU load-smoke owners.
 *
 * The loader's Align `file.pread` operation asks libc for the buffer capacity, so the
 * only useful regression witness is the count passed to the native pread call.  This
 * interposer records payload reads for one fixture path and can alter one such read
 * without changing the production loader or the shipped native ABI.
 */

#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#else
#define _GNU_SOURCE 1
#endif

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#if defined(__APPLE__)
#include <dlfcn.h>
#include <sys/fcntl.h>
#else
#include <dlfcn.h>
#endif

#if defined(__APPLE__)
/* Keep the replacee's lazy binding first in this tiny interposer. */
extern ssize_t pread(int, void *, size_t, off_t);
__attribute__((used)) static void *align_test_pread_import = (void *) pread;
extern ssize_t __pread_nocancel(int, void *, size_t, off_t);
#endif

typedef ssize_t (*align_test_pread_fn)(int, void *, size_t, off_t);

enum align_test_mode {
    ALIGN_TEST_MODE_NONE = 0,
    ALIGN_TEST_MODE_SHORT = 1,
    ALIGN_TEST_MODE_ZERO = 2,
    ALIGN_TEST_MODE_ERROR = 3,
};

#if !defined(__APPLE__)
static align_test_pread_fn align_test_real_pread;
#endif
#if !defined(__APPLE__)
static _Thread_local int align_test_resolving;
#endif
static int align_test_log_fd = -1;
static char align_test_target[PATH_MAX];
static off_t align_test_payload_offset;
static enum align_test_mode align_test_fault_mode;
static atomic_int align_test_fault_used;

static void align_test_init(void) {
    const char *target = getenv("ALIGN_GPU_LOAD_PREAD_PATH");
    const char *log_path = getenv("ALIGN_GPU_LOAD_PREAD_LOG");
    const char *minimum = getenv("ALIGN_GPU_LOAD_PREAD_MIN_OFFSET");
    const char *mode = getenv("ALIGN_GPU_LOAD_PREAD_MODE");
    char *end = NULL;
    long long parsed = 0;

    if (target != NULL && target[0] != '\0') {
        (void) snprintf(align_test_target, sizeof(align_test_target), "%s", target);
    }
    if (minimum != NULL && minimum[0] != '\0') {
        parsed = strtoll(minimum, &end, 10);
        if (end != minimum && *end == '\0' && parsed >= 0) {
            align_test_payload_offset = (off_t) parsed;
        }
    }
    if (mode != NULL && strcmp(mode, "short") == 0) {
        align_test_fault_mode = ALIGN_TEST_MODE_SHORT;
    } else if (mode != NULL && strcmp(mode, "zero") == 0) {
        align_test_fault_mode = ALIGN_TEST_MODE_ZERO;
    } else if (mode != NULL && strcmp(mode, "error") == 0) {
        align_test_fault_mode = ALIGN_TEST_MODE_ERROR;
    } else {
        align_test_fault_mode = ALIGN_TEST_MODE_NONE;
    }
    if (log_path != NULL && log_path[0] != '\0') {
        align_test_log_fd = open(log_path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    }
}

#if !defined(__APPLE__)
static align_test_pread_fn align_test_resolve(void) {
    if (align_test_real_pread != NULL) {
        return align_test_real_pread;
    }
    if (align_test_resolving) {
        return NULL;
    }
    align_test_resolving = 1;
    *(void **) (&align_test_real_pread) = dlsym(RTLD_NEXT, "pread");
    align_test_resolving = 0;
    return align_test_real_pread;
}
#endif

static ssize_t align_test_real_call(int fd, void *buffer, size_t count, off_t offset) {
#if defined(__APPLE__)
    return __pread_nocancel(fd, buffer, count, offset);
#else
    align_test_pread_fn real_pread = align_test_resolve();
    if (real_pread == NULL) {
        errno = ENOSYS;
        return -1;
    }
    return real_pread(fd, buffer, count, offset);
#endif
}

static int align_test_fd_path(int fd, char *path, size_t capacity) {
#if defined(__APPLE__)
    if (capacity == 0 || fcntl(fd, F_GETPATH, path) == -1) {
        return 0;
    }
    path[capacity - 1] = '\0';
    return 1;
#else
    char link_path[64];
    ssize_t length;
    if (capacity == 0) {
        return 0;
    }
    if (snprintf(link_path, sizeof(link_path), "/proc/self/fd/%d", fd) < 0) {
        return 0;
    }
    length = readlink(link_path, path, capacity - 1);
    if (length < 0) {
        return 0;
    }
    path[length] = '\0';
    return 1;
#endif
}

static int align_test_path_equal(const char *left, const char *right) {
    if (strcmp(left, right) == 0) {
        return 1;
    }
#if defined(__APPLE__)
    if (strncmp(left, "/private/", 9) == 0 && strcmp(left + 8, right) == 0) {
        return 1;
    }
    if (strncmp(right, "/private/", 9) == 0 && strcmp(right + 8, left) == 0) {
        return 1;
    }
#endif
    return 0;
}

static int align_test_is_payload_fd(int fd, off_t offset) {
    char path[PATH_MAX];
    if (align_test_target[0] == '\0' || offset < align_test_payload_offset
        || !align_test_fd_path(fd, path, sizeof(path))) {
        return 0;
    }
    return align_test_path_equal(path, align_test_target);
}

static void align_test_record(size_t requested, off_t offset, ssize_t returned) {
    char line[128];
    int length;
    ssize_t written;
    if (align_test_log_fd < 0) {
        return;
    }
    length = snprintf(line, sizeof(line), "%zu %lld %lld\n", requested,
                      (long long) offset, (long long) returned);
    if (length <= 0 || (size_t) length >= sizeof(line)) {
        return;
    }
    written = write(align_test_log_fd, line, (size_t) length);
    (void) written;
}

static ssize_t align_test_call(int fd, void *buffer, size_t count, off_t offset) {
    ssize_t returned;
    int payload = 0;
    int inject = 0;

    if (align_test_target[0] == '\0') {
        align_test_init();
    }
    payload = align_test_is_payload_fd(fd, offset);
    if (payload && align_test_fault_mode != ALIGN_TEST_MODE_NONE) {
        int expected = 0;
        inject = atomic_compare_exchange_strong(&align_test_fault_used, &expected, 1);
    }
    if (inject && align_test_fault_mode == ALIGN_TEST_MODE_ZERO) {
        returned = 0;
    } else if (inject && align_test_fault_mode == ALIGN_TEST_MODE_ERROR) {
        errno = EIO;
        returned = -1;
    } else if (inject && align_test_fault_mode == ALIGN_TEST_MODE_SHORT && count > 1) {
        size_t short_count = count / 2;
        if (short_count == 0) {
            short_count = 1;
        }
        returned = align_test_real_call(fd, buffer, short_count, offset);
    } else {
        returned = align_test_real_call(fd, buffer, count, offset);
    }
    if (payload) {
        align_test_record(count, offset, returned);
    }
    return returned;
}

static ssize_t align_test_pread_replacement(int fd, void *buffer, size_t count, off_t offset) {
    return align_test_call(fd, buffer, count, offset);
}

#if defined(__APPLE__)
/* Darwin's two-level namespace requires the documented interpose table for direct bindings. */
#define DYLD_INTERPOSE(_replacement, _replacee) \
    __attribute__((used)) static struct { const void *replacement; const void *replacee; } \
    align_test_interpose_##_replacee \
    __attribute__((section("__DATA,__interpose"))) = { \
        (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee \
    };
DYLD_INTERPOSE(align_test_pread_replacement, pread)
#else
ssize_t pread(int fd, void *buffer, size_t count, off_t offset) {
    return align_test_pread_replacement(fd, buffer, count, offset);
}
#endif

#if !defined(__APPLE__)
ssize_t pread64(int fd, void *buffer, size_t count, off_t offset) {
    return align_test_call(fd, buffer, count, offset);
}
#endif
