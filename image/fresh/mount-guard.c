#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <linux/capability.h>
#include <linux/mount.h>
#include <linux/stat.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sched.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#define MAX_MOUNTPOINTS 32
#define USERNS_PATH_BYTES 64

extern char **environ;

static int write_all(int descriptor, const char *data, size_t size) {
    size_t offset = 0;
    while (offset < size) {
        ssize_t count = write(descriptor, data + offset, size - offset);
        if (count < 0) {
            if (errno == EINTR) {
                continue;
            }
            return -1;
        }
        if (count == 0) {
            return -1;
        }
        offset += (size_t)count;
    }
    return 0;
}

static int write_proc_file(pid_t pid, const char *name, const char *data) {
    char path[USERNS_PATH_BYTES];
    int length = snprintf(path, sizeof(path), "/proc/%ld/%s", (long)pid, name);
    int descriptor;
    if (length < 0 || (size_t)length >= sizeof(path)) {
        errno = ENAMETOOLONG;
        return -1;
    }
    descriptor = open(path, O_WRONLY | O_CLOEXEC);
    if (descriptor < 0) {
        return -1;
    }
    if (write_all(descriptor, data, strlen(data)) < 0) {
        close(descriptor);
        return -1;
    }
    if (close(descriptor) < 0) {
        return -1;
    }
    return 0;
}

static void kill_and_reap(pid_t pid) {
    if (pid <= 0) {
        return;
    }
    if (kill(pid, SIGKILL) < 0 && errno != ESRCH) {
        return;
    }
    while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {
    }
}

static int prepare_validation_userns(char *path, size_t path_size, pid_t *helper_pid) {
    int ready[2];
    pid_t parent_pid;
    pid_t child;
    char status;
    ssize_t count;
    int length;
    int descriptor;

    if (pipe2(ready, O_CLOEXEC) < 0) {
        return -1;
    }
    parent_pid = getpid();
    child = fork();
    if (child < 0) {
        close(ready[0]);
        close(ready[1]);
        return -1;
    }
    if (child == 0) {
        int setgroups;
        close(ready[0]);
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) < 0 || getppid() != parent_pid ||
            syscall(SYS_unshare, CLONE_NEWUSER) < 0) {
            close(ready[1]);
            _exit(1);
        }
        setgroups = open("/proc/self/setgroups", O_WRONLY | O_CLOEXEC);
        if (setgroups < 0 || write_all(setgroups, "deny\n", 5) < 0) {
            if (setgroups >= 0) close(setgroups);
            close(ready[1]);
            _exit(1);
        }
        if (close(setgroups) < 0 || write_all(ready[1], "R", 1) < 0) {
            close(ready[1]);
            _exit(1);
        }
        close(ready[1]);
        for (;;) {
            pause();
        }
    }

    close(ready[1]);
    do {
        count = read(ready[0], &status, 1);
    } while (count < 0 && errno == EINTR);
    close(ready[0]);
    if (count != 1 || status != 'R' || write_proc_file(child, "uid_map", "0 0 1\n") < 0 ||
        write_proc_file(child, "gid_map", "0 0 1\n") < 0) {
        kill_and_reap(child);
        return -1;
    }

    length = snprintf(path, path_size, "/proc/%ld/ns/user", (long)child);
    if (length < 0 || (size_t)length >= path_size) {
        kill_and_reap(child);
        errno = ENAMETOOLONG;
        return -1;
    }
    descriptor = open(path, O_RDONLY | O_CLOEXEC);
    if (descriptor < 0) {
        kill_and_reap(child);
        return -1;
    }
    if (close(descriptor) < 0 || setenv("ALIGN_LLM_VALIDATION_USERNS_PATH", path, 1) < 0) {
        kill_and_reap(child);
        return -1;
    }
    *helper_pid = child;
    return 0;
}

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
    if (mount_id(path, &before) < 0 ||
        syscall(SYS_mount_setattr, AT_FDCWD, path, 0, &attributes, sizeof(attributes)) < 0 ||
        mount_id(path, &after) < 0 || before != after) {
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
    int prepare_userns = 0;
    pid_t helper_pid = -1;
    char userns_path[USERNS_PATH_BYTES];
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
        if (strcmp(argv[index], "--prepare-validation-userns") == 0) {
            if (prepare_userns) {
                return 2;
            }
            prepare_userns = 1;
            continue;
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
    if (prepare_userns && prepare_validation_userns(
            userns_path, sizeof(userns_path), &helper_pid) < 0) {
        return 1;
    }
    if (drop_capabilities() < 0) {
        kill_and_reap(helper_pid);
        return 1;
    }
    execve(argv[command_index], &argv[command_index], environ);
    kill_and_reap(helper_pid);
    return 1;
}
