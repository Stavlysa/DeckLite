#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <unistd.h>

typedef int (*flock_function)(int, int);

#if !defined(TGCOMPAT_FLOCK_TEST_FORCE_ENOSYS)
static flock_function real_flock;
#endif
static bool fcntl_fallback_enabled;

#if !defined(TGCOMPAT_FLOCK_TEST_FORCE_ENOSYS)
static void resolve_flock(void) {
    void *symbol = dlsym(RTLD_NEXT, "flock");

    _Static_assert(sizeof(real_flock) == sizeof(symbol),
        "function and data pointers must have equal size");
    memcpy(&real_flock, &symbol, sizeof(real_flock));
}
#endif

__attribute__((constructor)) static void initialize_flock_shim(void) {
    const char *value = getenv("TGCOMPAT_FLOCK_FCNTL");

    fcntl_fallback_enabled = value != NULL && strcmp(value, "1") == 0;
#if defined(TGCOMPAT_FLOCK_TEST_FORCE_ENOSYS)
    fcntl_fallback_enabled = true;
#else
    resolve_flock();
#endif
}

static int fcntl_flock(int descriptor, int operation) {
    struct flock lock = {
        .l_type = F_UNLCK,
        .l_whence = SEEK_SET,
        .l_start = 0,
        .l_len = 0,
        .l_pid = 0,
    };
    int command;
    int lock_operation = operation & ~LOCK_NB;

    if ((operation & ~(LOCK_SH | LOCK_EX | LOCK_UN | LOCK_NB)) != 0) {
        errno = EINVAL;
        return -1;
    }
    switch (lock_operation) {
    case LOCK_SH:
        lock.l_type = F_RDLCK;
        break;
    case LOCK_EX:
        lock.l_type = F_WRLCK;
        break;
    case LOCK_UN:
        lock.l_type = F_UNLCK;
        break;
    default:
        errno = EINVAL;
        return -1;
    }
    command = (operation & LOCK_NB) != 0 ? F_SETLK : F_SETLKW;
    return fcntl(descriptor, command, &lock);
}

__attribute__((visibility("default"))) int flock(int descriptor,
        int operation) {
    int result;

#if defined(TGCOMPAT_FLOCK_TEST_FORCE_ENOSYS)
    result = -1;
    errno = ENOSYS;
#else
    if (real_flock == NULL) {
        errno = ENOSYS;
        result = -1;
    } else {
        result = real_flock(descriptor, operation);
    }
#endif
    if (result < 0 && errno == ENOSYS && fcntl_fallback_enabled) {
        return fcntl_flock(descriptor, operation);
    }
    return result;
}
