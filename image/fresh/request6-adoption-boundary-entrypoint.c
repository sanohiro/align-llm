#define _GNU_SOURCE

#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/memfd.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
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

extern char **environ;

static int fail_input(void) {
    static const char message[] = "json-scan adoption: ERROR input\n";
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
    int fd = memfd("align-llm-request6-boundary");
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

static int allowed_descriptor(int fd) {
    return fd == STDIN_FILENO || fd == STDOUT_FILENO || fd == STDERR_FILENO || fd == 4 ||
           fd == 6 || fd == 8 || fd == 14 || fd == 18;
}

static int descriptor_set_is_exact(void) {
    DIR *directory = opendir("/proc/self/fd");
    struct dirent *entry;
    int directory_fd;
    if (directory == NULL) {
        return -1;
    }
    directory_fd = dirfd(directory);
    while ((entry = readdir(directory)) != NULL) {
        char *end = NULL;
        long value;
        if (entry->d_name[0] == '.') {
            continue;
        }
        value = strtol(entry->d_name, &end, 10);
        if (end == entry->d_name || *end != '\0' || value < 0 || value > INT_MAX) {
            closedir(directory);
            return -1;
        }
        if ((int)value == directory_fd) {
            continue;
        }
        if (!allowed_descriptor((int)value)) {
            closedir(directory);
            return -1;
        }
    }
    if (closedir(directory) < 0) {
        return -1;
    }
    return 0;
}

static int matches_name(const char *entry, const char *name, const char *value) {
    size_t name_length = strlen(name);
    size_t value_length = strlen(value);
    size_t entry_length = strlen(entry);
    return entry_length == name_length + 1 + value_length &&
           strncmp(entry, name, name_length) == 0 && entry[name_length] == '=' &&
           strcmp(entry + name_length + 1, value) == 0;
}

static int environment_is_exact(void) {
    static const char *names[] = {"PATH", "LC_ALL", "LANG", "HOME", "TMPDIR"};
    static const char *values[] = {"/usr/bin:/bin", "C", "C", "/nonexistent", "/tmp"};
    int seen[5] = {0, 0, 0, 0, 0};
    int index;
    for (index = 0; environ[index] != NULL; ++index) {
        int found = 0;
        int name_index;
        for (name_index = 0; name_index < 5; ++name_index) {
            if (matches_name(environ[index], names[name_index], values[name_index])) {
                if (seen[name_index] != 0) {
                    return -1;
                }
                seen[name_index] = 1;
                found = 1;
                break;
            }
        }
        if (!found) {
            return -1;
        }
    }
    for (index = 0; index < 5; ++index) {
        if (seen[index] == 0) {
            return -1;
        }
    }
    return 0;
}

static int close_unexpected_descriptors(void) {
    return syscall(SYS_close_range, 3U, 3U, 0U) < 0 ||
                   syscall(SYS_close_range, 5U, 5U, 0U) < 0 ||
                   syscall(SYS_close_range, 7U, 7U, 0U) < 0 ||
                   syscall(SYS_close_range, 9U, 10U, 0U) < 0 ||
                   syscall(SYS_close_range, 12U, 17U, 0U) < 0 ||
                   syscall(SYS_close_range, 19U, UINT_MAX, 0U) < 0
               ? -1
               : 0;
}

int main(int argc, char **argv) {
    char *child_argv[32];
    int index;

    if (argc < 2 || argc > 20 || strcmp(argv[0], "request6-adoption-boundary-entrypoint") != 0 ||
        environment_is_exact() < 0 ||
        descriptor_set_is_exact() < 0 || snapshot_payload() < 0 ||
        close_unexpected_descriptors() < 0) {
        return fail_input();
    }
    child_argv[0] = (char *)PYTHON_PATH;
    child_argv[1] = (char *)"-I";
    child_argv[2] = (char *)"-B";
    child_argv[3] = (char *)"/proc/self/fd/11";
    for (index = 1; index < argc; ++index) {
        child_argv[index + 3] = argv[index];
    }
    child_argv[argc + 3] = NULL;
    execve(PYTHON_PATH, child_argv, environ);
    return fail_input();
}
