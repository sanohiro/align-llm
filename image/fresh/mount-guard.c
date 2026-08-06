#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <linux/capability.h>
#include <linux/mount.h>
#include <linux/stat.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#define MAX_MOUNTPOINTS 32

extern char **environ;

static int mount_id(const char *path, unsigned long long *value) {
    struct statx result;
    memset(&result, 0, sizeof(result));
    if (syscall(SYS_statx, AT_FDCWD, path, AT_SYMLINK_NOFOLLOW, STATX_MNT_ID, &result) < 0 ||
        (result.stx_mask & STATX_MNT_ID) == 0) {
        return -1;
    }
    *value = result.stx_mnt_id;
    return 0;
}

static int apply_no_symlink_follow(const char *path) {
    struct mount_attr attributes;
    unsigned long long before;
    unsigned long long after;
    memset(&attributes, 0, sizeof(attributes));
    attributes.attr_set = MOUNT_ATTR_NOSYMFOLLOW;
    if (mount_id(path, &before) < 0) {
        dprintf(STDERR_FILENO, "DIAGNOSTIC mount-guard statx-before path=%s errno=%d %s\n", path, errno, strerror(errno));
        return -1;
    }
    if (syscall(SYS_mount_setattr, AT_FDCWD, path, 0, &attributes, sizeof(attributes)) < 0) {
        dprintf(STDERR_FILENO, "DIAGNOSTIC mount-guard mount-setattr path=%s errno=%d %s\n", path, errno, strerror(errno));
        return -1;
    }
    if (mount_id(path, &after) < 0) {
        dprintf(STDERR_FILENO, "DIAGNOSTIC mount-guard statx-after path=%s errno=%d %s\n", path, errno, strerror(errno));
        return -1;
    }
    if (before != after) {
        dprintf(STDERR_FILENO, "DIAGNOSTIC mount-guard mount-id path=%s before=%llu after=%llu\n", path, before, after);
        return -1;
    }
    return 0;
}

static int drop_capabilities(void) {
    struct __user_cap_header_struct header;
    struct __user_cap_data_struct data[2];
    memset(&header, 0, sizeof(header));
    memset(data, 0, sizeof(data));
    header.version = _LINUX_CAPABILITY_VERSION_3;
    header.pid = 0;
    data[0].effective = 1U << CAP_SETFCAP;
    data[0].permitted = 1U << CAP_SETFCAP;
    if (syscall(SYS_capset, &header, data) < 0 || prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0) {
        return -1;
    }
    return 0;
}

static int namespace_self_test(void) {
    struct stat marker;
    int descriptor;
    static const char byte = 'x';

    if (lstat("/target/lower-marker", &marker) < 0 || !S_ISREG(marker.st_mode)) {
        return 11;
    }
    descriptor = open("/target/upper-marker", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (descriptor < 0 || write(descriptor, &byte, 1) != 1 || close(descriptor) < 0) {
        if (descriptor >= 0) {
            close(descriptor);
        }
        return 12;
    }
    descriptor = open("/tools/write-probe", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (descriptor >= 0 || errno != EROFS) {
        if (descriptor >= 0) {
            close(descriptor);
        }
        return 13;
    }
    if (symlink("/target/lower-marker", "/target/tmp/link") < 0) {
        return 14;
    }
    descriptor = open("/target/tmp/link", O_RDONLY | O_CLOEXEC);
    if (descriptor >= 0 || errno != ELOOP) {
        if (descriptor >= 0) {
            close(descriptor);
        }
        return 15;
    }
    if (unlink("/target/tmp/link") < 0) {
        return 16;
    }
    return 0;
}

int main(int argc, char **argv) {
    const char *mountpoints[MAX_MOUNTPOINTS];
    int count = 0;
    int command_index = -1;
    int index;

    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        static const char version[] = "align-llm mount-guard 1.0.0\n";
        return write(STDOUT_FILENO, version, sizeof(version) - 1) == (ssize_t)(sizeof(version) - 1)
                   ? 0
                   : 1;
    }
    if (argc == 2 && strcmp(argv[1], "--namespace-self-test") == 0) {
        return namespace_self_test();
    }
    if (argc < 5 || strcmp(argv[1], "--no-symlink-follow") != 0) {
        return 2;
    }
    for (index = 2; index < argc; ++index) {
        if (strcmp(argv[index], "--") == 0) {
            command_index = index + 1;
            break;
        }
        if (argv[index][0] != '/' || argv[index][1] == '\0' || count == MAX_MOUNTPOINTS) {
            return 2;
        }
        for (int previous = 0; previous < count; ++previous) {
            if (strcmp(mountpoints[previous], argv[index]) == 0) {
                return 2;
            }
        }
        mountpoints[count++] = argv[index];
    }
    if (count == 0 || command_index < 0 || command_index >= argc ||
        argv[command_index][0] != '/') {
        return 2;
    }
    for (index = 0; index < count; ++index) {
        if (apply_no_symlink_follow(mountpoints[index]) < 0) {
            return 1;
        }
    }
    if (drop_capabilities() < 0) {
        return 1;
    }
    execve(argv[command_index], &argv[command_index], environ);
    return 1;
}
