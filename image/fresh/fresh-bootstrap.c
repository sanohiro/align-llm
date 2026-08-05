#define _GNU_SOURCE

#include <fcntl.h>
#include <linux/memfd.h>
#include <limits.h>
#include <stddef.h>
#include <sys/syscall.h>
#include <unistd.h>

#include "bootstrap_payload.inc"

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
    static const char message[] = "fresh compiler: ERROR TRUST supervisor\n";
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

static int close_unexpected_descriptors(void) {
    return syscall(SYS_close_range, 3U, 3U, 0U) < 0 ||
                   syscall(SYS_close_range, 7U, 9U, 0U) < 0 ||
                   syscall(SYS_close_range, 12U, UINT_MAX, 0U) < 0
               ? -1
               : 0;
}

int main(int argc, char **argv) {
    char *child_argv[12];
    char *child_env[] = {
        "PATH=/usr/bin:/bin",
        "LC_ALL=C",
        "LANG=C",
        "HOME=/nonexistent",
        "TMPDIR=/tmp",
        NULL,
    };
    int payload_fd;
    int self_fd;
    int index;
    const int seals = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL;

    if (argc != 3) {
        return fail();
    }
    payload_fd = memfd("align-llm-bootstrap-payload");
    if (payload_fd < 0 || write_all(payload_fd, bootstrap_payload, bootstrap_payload_len) < 0 ||
        lseek(payload_fd, 0, SEEK_SET) < 0 || fcntl(payload_fd, F_ADD_SEALS, seals) < 0 ||
        fcntl(payload_fd, F_GET_SEALS) != REQUIRED_SEALS || dup2(payload_fd, 11) < 0 ||
        fcntl(11, F_SETFD, 0) < 0) {
        if (payload_fd >= 0) {
            close(payload_fd);
        }
        return fail();
    }
    if (payload_fd != 11) {
        close(payload_fd);
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
