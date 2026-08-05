#define _GNU_SOURCE

#include <limits.h>
#include <sys/syscall.h>
#include <stddef.h>
#include <stdlib.h>
#include <unistd.h>

#ifndef TOOL_TARGET
#error TOOL_TARGET must be defined
#endif

extern char **environ;

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
    if (syscall(SYS_close_range, 3U, UINT_MAX, 0U) < 0) {
        return 1;
    }
    execve(TOOL_TARGET, arguments, environ);
    return 1;
}
