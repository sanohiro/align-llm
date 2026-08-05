#define _GNU_SOURCE

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
    execve(TOOL_TARGET, arguments, environ);
    return 1;
}
