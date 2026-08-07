#define _GNU_SOURCE

#include <fcntl.h>
#include <linux/memfd.h>
#include <limits.h>
#include <stddef.h>
#include <sys/syscall.h>
#include <unistd.h>

#include "dispatcher_payload.inc"

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

static int fail(void) {
    static const char message[] = "json-scan adoption: ERROR toolchain\n";
    (void)!write(STDERR_FILENO, message, sizeof(message) - 1);
    return 1;
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

static int snapshot_payload(void) {
    int fd = memfd("align-llm-request6-dispatcher");
    if (fd < 0 || write_all(fd, dispatcher_payload, dispatcher_payload_len) < 0 ||
        lseek(fd, 0, SEEK_SET) < 0 || fcntl(fd, F_ADD_SEALS, REQUIRED_SEALS) < 0 ||
        fcntl(fd, F_GET_SEALS) != REQUIRED_SEALS || dup2(fd, 11) < 0 ||
        fcntl(11, F_SETFD, 0) < 0) {
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

static int close_unexpected_descriptors(void) {
    return syscall(SYS_close_range, 3U, 3U, 0U) < 0 ||
                   syscall(SYS_close_range, 5U, 5U, 0U) < 0 ||
                   syscall(SYS_close_range, 7U, 7U, 0U) < 0 ||
                   syscall(SYS_close_range, 9U, 10U, 0U) < 0 ||
                   syscall(SYS_close_range, 12U, 14U, 0U) < 0 ||
                   syscall(SYS_close_range, 17U, 17U, 0U) < 0 ||
                   syscall(SYS_close_range, 19U, UINT_MAX, 0U) < 0
               ? -1
               : 0;
}

int main(int argc, char **argv) {
    char *child_argv[32];
    char *child_env[] = {
        "PATH=/usr/bin:/bin",
        "LC_ALL=C",
        "LANG=C",
        "HOME=/nonexistent",
        "TMPDIR=/tmp",
        NULL,
    };
    int index;

    if (argc < 2 || argc > 28 || snapshot_payload() < 0 || close_unexpected_descriptors() < 0) {
        return fail();
    }
    child_argv[0] = (char *)PYTHON_PATH;
    child_argv[1] = (char *)"-I";
    child_argv[2] = (char *)"-B";
    child_argv[3] = (char *)"/proc/self/fd/11";
    for (index = 1; index < argc; ++index) {
        child_argv[index + 3] = argv[index];
    }
    child_argv[argc + 3] = NULL;
    execve(PYTHON_PATH, child_argv, child_env);
    return fail();
}
