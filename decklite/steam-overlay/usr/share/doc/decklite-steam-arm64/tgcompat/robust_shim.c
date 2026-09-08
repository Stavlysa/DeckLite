#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <linux/futex.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

typedef long (*syscall_function)(long, ...);

__attribute__((visibility("hidden"))) syscall_function tgcompat_real_syscall;
__attribute__((visibility("hidden"))) bool tgcompat_robust_list_enabled;
__attribute__((visibility("hidden"))) bool
    tgcompat_userfaultfd_enosys_enabled;

/* Valve Proton 11's temporary UFFD header uses ARM32's number on AArch64. */
#define PROTON_ARM64_USERFAULTFD_SYSCALL 374

#if defined(__aarch64__)
_Static_assert(SYS_get_robust_list == 100,
    "AArch64 robust-list syscall number changed");
#ifdef SYS_userfaultfd
_Static_assert(SYS_userfaultfd == 282,
    "AArch64 userfaultfd syscall number changed");
#endif
#endif

struct pthread_compatible_robust_list {
    struct robust_list *previous;
    struct robust_list_head head;
};

static _Thread_local struct pthread_compatible_robust_list synthetic_list;
static _Thread_local bool synthetic_list_initialized;

static void resolve_syscall(void) {
    void *symbol = dlsym(RTLD_NEXT, "syscall");

    _Static_assert(sizeof(tgcompat_real_syscall) == sizeof(symbol),
        "function and data pointers must have equal size");
    memcpy(&tgcompat_real_syscall, &symbol, sizeof(tgcompat_real_syscall));
}

__attribute__((constructor)) static void initialize_robust_shim(void) {
    const char *value = getenv("TGCOMPAT_ROBUST_LIST");
    const char *userfaultfd_value = getenv("TGCOMPAT_USERFAULTFD_ENOSYS");

    tgcompat_robust_list_enabled =
        value != NULL && strcmp(value, "1") == 0;
    tgcompat_userfaultfd_enosys_enabled = userfaultfd_value != NULL &&
        strcmp(userfaultfd_value, "1") == 0;
    resolve_syscall();
}

static struct robust_list_head *current_synthetic_head(void) {
    _Static_assert(offsetof(struct pthread_compatible_robust_list, head) ==
            sizeof(struct robust_list *),
        "the pthread predecessor must immediately precede the robust head");

    if (!synthetic_list_initialized) {
        synthetic_list.previous = &synthetic_list.head.list;
        synthetic_list.head.list.next = &synthetic_list.head.list;
        synthetic_list.head.futex_offset = -32;
        synthetic_list.head.list_op_pending = NULL;
        synthetic_list_initialized = true;
    }
    return &synthetic_list.head;
}

__attribute__((visibility("hidden"), used, noinline)) long
tgcompat_emulate_get_robust_list(
        long process, struct robust_list_head **head, size_t *length) {
    int saved_errno = errno;

    if (process != 0) {
        return 1;
    }
    if (head == NULL || length == NULL) {
        errno = EFAULT;
        return -1;
    }
    *head = current_synthetic_head();
    *length = sizeof(**head);
    errno = saved_errno;
    return 0;
}

#if defined(__aarch64__)

__attribute__((visibility("hidden"), used, noinline)) long
tgcompat_syscall_enosys(void) {
    errno = ENOSYS;
    return -1;
}

#else

static long forward_syscall(long number, va_list arguments) {
    long argument1 = va_arg(arguments, long);
    long argument2 = va_arg(arguments, long);
    long argument3 = va_arg(arguments, long);
    long argument4 = va_arg(arguments, long);
    long argument5 = va_arg(arguments, long);
    long argument6 = va_arg(arguments, long);

    if (tgcompat_real_syscall == NULL) {
        errno = ENOSYS;
        return -1;
    }
    return tgcompat_real_syscall(number, argument1, argument2, argument3,
        argument4, argument5, argument6);
}

__attribute__((visibility("default"))) long syscall(long number, ...) {
    va_list arguments;
    long result;

    va_start(arguments, number);
    if (tgcompat_userfaultfd_enosys_enabled &&
            (number == PROTON_ARM64_USERFAULTFD_SYSCALL
#ifdef SYS_userfaultfd
            || number == SYS_userfaultfd
#endif
            )) {
        errno = ENOSYS;
        va_end(arguments);
        return -1;
    }
    if (tgcompat_robust_list_enabled && number == SYS_get_robust_list) {
        va_list emulation_arguments;
        long process;
        struct robust_list_head **head;
        size_t *length;

        va_copy(emulation_arguments, arguments);
        process = va_arg(emulation_arguments, long);
        head = va_arg(emulation_arguments, struct robust_list_head **);
        length = va_arg(emulation_arguments, size_t *);
        result = tgcompat_emulate_get_robust_list(process, head, length);
        va_end(emulation_arguments);
        if (result != 1) {
            va_end(arguments);
            return result;
        }
    }
    result = forward_syscall(number, arguments);
    va_end(arguments);
    return result;
}

#endif
