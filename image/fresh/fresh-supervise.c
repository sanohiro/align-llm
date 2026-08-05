#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <linux/memfd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
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

extern char **environ;

static int fail(void) {
    static const char message[] = "fresh compiler: ERROR TRUST supervisor\n";
    (void)!write(STDERR_FILENO, message, sizeof(message) - 1);
    return 1;
}

static int fail_argument(void) {
    static const char message[] = "fresh compiler: ERROR ARGUMENT input\n";
    (void)!write(STDERR_FILENO, message, sizeof(message) - 1);
    return 1;
}

static int has_loader_injection(void) {
    return getenv("LD_AUDIT") != NULL || getenv("LD_LIBRARY_PATH") != NULL ||
           getenv("LD_PRELOAD") != NULL;
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

int main(int argc, char **argv) {
    char *child_argv[16];
    int self_fd;
    int index;

    if (has_loader_injection()) {
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
    execve(PYTHON_PATH, child_argv, environ);
    return fail();
}
