#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifndef TOOL_TARGET
#error TOOL_TARGET must be defined
#endif

extern char **environ;

#ifdef TOOL_BWRAP_FORWARDER
#ifndef CLOSE_RANGE_CLOEXEC
#define CLOSE_RANGE_CLOEXEC (1U << 2)
#endif

static int parse_fd(const char *value, int *result) {
    char *end;
    const char *cursor;
    unsigned long parsed;

    if (value == NULL || value[0] == '\0') {
        return -1;
    }
    for (cursor = value; cursor[0] != '\0'; ++cursor) {
        if (cursor[0] < '0' || cursor[0] > '9') {
            return -1;
        }
    }
    errno = 0;
    parsed = strtoul(value, &end, 10);
    if (errno != 0 || end[0] != '\0' || parsed > INT_MAX) {
        return -1;
    }
    *result = (int)parsed;
    return 0;
}

static int parse_fd_path(const char *value, int *result) {
    static const char prefix[] = "/proc/self/fd/";

    if (strncmp(value, prefix, sizeof(prefix) - 1U) != 0) {
        return 0;
    }
    return parse_fd(value + sizeof(prefix) - 1U, result) == 0 ? 1 : -1;
}

static int append_fd(int *descriptors, size_t *count, size_t capacity, int descriptor) {
    if (descriptor <= 2 || *count >= capacity) {
        return -1;
    }
    descriptors[*count] = descriptor;
    *count += 1U;
    return 0;
}

static int prepare_bwrap_descriptors(int argc, char **argv) {
    int *descriptors;
    size_t capacity = (size_t)argc;
    size_t count = 0U;
    int index;
    size_t descriptor_index;

    descriptors = calloc(capacity, sizeof(int));
    if (descriptors == NULL) {
        return -1;
    }
    for (index = 1; index < argc; ++index) {
        int descriptor;
        int parsed;

        if (strcmp(argv[index], "--") == 0) {
            break;
        }
        if (strcmp(argv[index], "--bind-fd") == 0 ||
            strcmp(argv[index], "--ro-bind-fd") == 0) {
            if (index + 1 >= argc || parse_fd(argv[index + 1], &descriptor) != 0 ||
                append_fd(descriptors, &count, capacity, descriptor) != 0) {
                free(descriptors);
                return -1;
            }
            continue;
        }
        if (strcmp(argv[index], "--userns") == 0) {
            if (index + 1 >= argc || parse_fd(argv[index + 1], &descriptor) != 0 ||
                append_fd(descriptors, &count, capacity, descriptor) != 0) {
                free(descriptors);
                return -1;
            }
            continue;
        }
        if (strcmp(argv[index], "--overlay-src") == 0) {
            if (index + 1 >= argc) {
                free(descriptors);
                return -1;
            }
            parsed = parse_fd_path(argv[index + 1], &descriptor);
            if (parsed < 0 || (parsed > 0 && append_fd(descriptors, &count, capacity, descriptor) != 0)) {
                free(descriptors);
                return -1;
            }
            continue;
        }
        if (strcmp(argv[index], "--overlay") == 0) {
            int offset;

            if (index + 2 >= argc) {
                free(descriptors);
                return -1;
            }
            for (offset = 1; offset <= 2; ++offset) {
                parsed = parse_fd_path(argv[index + offset], &descriptor);
                if (parsed < 0 ||
                    (parsed > 0 && append_fd(descriptors, &count, capacity, descriptor) != 0)) {
                    free(descriptors);
                    return -1;
                }
            }
        }
    }
    if (syscall(SYS_close_range, 3U, UINT_MAX, CLOSE_RANGE_CLOEXEC) < 0) {
        free(descriptors);
        return -1;
    }
    for (descriptor_index = 0U; descriptor_index < count; ++descriptor_index) {
        int flags = fcntl(descriptors[descriptor_index], F_GETFD);

        if (flags < 0 || fcntl(descriptors[descriptor_index], F_SETFD, flags & ~FD_CLOEXEC) < 0) {
            free(descriptors);
            return -1;
        }
    }
    free(descriptors);
    return 0;
}
#endif

int main(int argc, char **argv) {
    char **arguments;
    int index;

    if (argc < 1) {
        return 2;
    }
    arguments = calloc((size_t)argc + 1, sizeof(char *));
    if (arguments == NULL) {
        return 1;
    }
    arguments[0] = (char *)TOOL_TARGET;
    for (index = 1; index < argc; ++index) {
        arguments[index] = argv[index];
    }
#ifdef TOOL_BWRAP_FORWARDER
    if (prepare_bwrap_descriptors(argc, argv) != 0) {
        return 1;
    }
#else
    if (syscall(SYS_close_range, 3U, UINT_MAX, 0U) < 0) {
        return 1;
    }
#endif
    execve(TOOL_TARGET, arguments, environ);
    return 1;
}
