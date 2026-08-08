#define _GNU_SOURCE

#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/memfd.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#include "namespace_payload.inc"

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
    static const char message[] = "json-scan adoption: ERROR toolchain\n";
    (void)!write(STDERR_FILENO, message, sizeof(message) - 1U);
    return 2;
}

static int memfd(const char *name) {
    return (int)syscall(SYS_memfd_create, name, MFD_ALLOW_SEALING | MFD_CLOEXEC);
}

static int write_all(int fd, const unsigned char *data, size_t size) {
    while (size != 0U) {
        ssize_t count = write(fd, data, size);
        if (count <= 0) return -1;
        data += (size_t)count;
        size -= (size_t)count;
    }
    return 0;
}

static int descriptor_set_is_exact(void) {
    DIR *directory = opendir("/proc/self/fd");
    struct dirent *entry;
    int directory_fd;
    if (directory == NULL) return -1;
    directory_fd = dirfd(directory);
    while ((entry = readdir(directory)) != NULL) {
        char *end = NULL;
        long value;
        if (entry->d_name[0] == '.') continue;
        value = strtol(entry->d_name, &end, 10);
        if (end == entry->d_name || *end != '\0' || value < 0 || value > INT_MAX) {
            closedir(directory);
            return -1;
        }
        if ((int)value == directory_fd) continue;
        if (value != STDIN_FILENO && value != STDOUT_FILENO && value != STDERR_FILENO && value != 16) {
            closedir(directory);
            return -1;
        }
    }
    return closedir(directory) < 0 ? -1 : 0;
}

static int environment_is_exact(void) {
    static const char *names[] = {"PATH", "ALIGN_REPO", "CARGO_NET_OFFLINE", "HOME", "LANG", "LC_ALL",
                                  "MAKEFLAGS", "GNUMAKEFLAGS", "MAKEOVERRIDES", "PYTHONDONTWRITEBYTECODE", "TMPDIR"};
    static const char *values[] = {"/usr/bin:/bin", "/private-align", "true", "/nonexistent", "C", "C", "", "", "", "1", "/tmp"};
    int seen[11] = {0};
    int index;
    for (index = 0; environ[index] != NULL; ++index) {
        int found = 0;
        int name_index;
        for (name_index = 0; name_index < 11; ++name_index) {
            size_t length = strlen(names[name_index]);
            if (strncmp(environ[index], names[name_index], length) != 0 || environ[index][length] != '=') continue;
            if (seen[name_index] != 0 || strcmp(environ[index] + length + 1, values[name_index]) != 0) return -1;
            seen[name_index] = 1;
            found = 1;
            break;
        }
        if (!found) return -1;
    }
    for (index = 0; index < 11; ++index) if (seen[index] == 0) return -1;
    return 0;
}

static int close_unexpected_descriptors(void) {
    return syscall(SYS_close_range, 3U, 15U, 0U) < 0 ||
                   syscall(SYS_close_range, 17U, UINT_MAX, 0U) < 0
               ? -1
               : 0;
}

int main(int argc, char **argv) {
    char *child_argv[32];
    char *child_env[] = {
        (char *)"PATH=/usr/bin:/bin", (char *)"ALIGN_REPO=/private-align", (char *)"CARGO_NET_OFFLINE=true",
        (char *)"HOME=/nonexistent", (char *)"LANG=C", (char *)"LC_ALL=C", (char *)"MAKEFLAGS=",
        (char *)"GNUMAKEFLAGS=", (char *)"MAKEOVERRIDES=", (char *)"PYTHONDONTWRITEBYTECODE=1",
        (char *)"TMPDIR=/tmp", NULL,
    };
    int index;
    if (argc < 2 || argc > 20 || strcmp(argv[0], "/usr/bin/adoption-namespace") != 0 ||
        !environment_is_exact() || descriptor_set_is_exact() < 0 || close_unexpected_descriptors() < 0) return fail();
    child_argv[0] = (char *)PYTHON_PATH;
    child_argv[1] = (char *)"-I";
    child_argv[2] = (char *)"-B";
    child_argv[3] = (char *)"/proc/self/fd/11";
    for (index = 1; index < argc; ++index) child_argv[index + 3] = argv[index];
    child_argv[argc + 3] = NULL;
    {
        int fd = memfd("align-llm-adoption-namespace");
        if (fd < 0 || write_all(fd, namespace_payload, namespace_payload_len) < 0 ||
            lseek(fd, 0, SEEK_SET) < 0 || fcntl(fd, F_ADD_SEALS, REQUIRED_SEALS) < 0 ||
            fcntl(fd, F_GET_SEALS) != REQUIRED_SEALS || dup2(fd, 11) < 0 || fcntl(11, F_SETFD, 0) < 0) {
            if (fd >= 0) close(fd);
            return fail();
        }
        if (fd != 11) close(fd);
    }
    execve(PYTHON_PATH, child_argv, child_env);
    return fail();
}
