#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <linux/memfd.h>
#include <limits.h>
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

int main(int argc, char **argv) {
    char *child_argv[16];
    char *child_env[7];
    int self_fd;
    int index;
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
