#define _GNU_SOURCE

#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

typedef long (*syscall_function)(long, ...);
typedef int (*pthread_affinity_function)(pthread_t, size_t, const cpu_set_t *);
static pthread_affinity_function real_pthread_affinity;

__attribute__((visibility("hidden"))) syscall_function
    decklite_real_syscall;
__attribute__((visibility("hidden"))) bool decklite_affinity_enabled;

static int target_cpu = -1;
static cpu_set_t initial_allowed;
static cpu_set_t policy_selected;
static bool restricted_policy;

static bool select_custom_cores(cpu_set_t *selected, const cpu_set_t *allowed,
                                const char *list) {
    CPU_ZERO(selected);
    if (list == NULL || *list == '\0') return false;
    while (*list != '\0') {
        if (*list < '0' || *list > '9') return false;
        char *end;
        errno = 0;
        unsigned long cpu = strtoul(list, &end, 10);
        if (errno != 0 || cpu >= CPU_SETSIZE || (*end != ',' && *end != '\0')) return false;
        if (CPU_ISSET((int)cpu, allowed)) CPU_SET((int)cpu, selected);
        if (*end == '\0') break;
        list = end + 1;
        if (*list == '\0') return false;
    }
    return CPU_COUNT(selected) != 0;
}

/* Select every performance tier above the efficiency tier, not only the
 * single fastest core. Capacity is preferable; max frequency is a fallback
 * on Android kernels that do not expose cpu_capacity. */
static bool select_big_cores(cpu_set_t *selected, const cpu_set_t *allowed,
                             const char *metric) {
    long count = sysconf(_SC_NPROCESSORS_CONF);
    unsigned long scores[CPU_SETSIZE] = {0};
    unsigned long minimum = ~0UL, maximum = 0;
    if (count < 1 || count > CPU_SETSIZE) return false;
    for (int cpu = 0; cpu < count; ++cpu) {
        char path[160];
        snprintf(path, sizeof(path), "/sys/devices/system/cpu/cpu%d/%s", cpu, metric);
        FILE *input = fopen(path, "r");
        if (input == NULL) return false;
        int scanned = fscanf(input, "%lu", &scores[cpu]);
        fclose(input);
        if (scanned != 1 || scores[cpu] == 0) return false;
        if (scores[cpu] < minimum) minimum = scores[cpu];
        if (scores[cpu] > maximum) maximum = scores[cpu];
    }
    if (minimum == maximum) return false;
    CPU_ZERO(selected);
    for (int cpu = 0; cpu < count; ++cpu) {
        if (scores[cpu] > minimum && CPU_ISSET(cpu, allowed)) CPU_SET(cpu, selected);
    }
    return CPU_COUNT(selected) != 0;
}

#if defined(__aarch64__)
_Static_assert(SYS_sched_setaffinity == 122,
    "AArch64 sched_setaffinity syscall number changed");
#endif

static void resolve_syscall(void) {
    void *symbol = dlsym(RTLD_NEXT, "syscall");

    _Static_assert(sizeof(decklite_real_syscall) == sizeof(symbol),
        "function and data pointers must have equal size");
    memcpy(&decklite_real_syscall, &symbol, sizeof(decklite_real_syscall));
    symbol = dlsym(RTLD_NEXT, "pthread_setaffinity_np");
    memcpy(&real_pthread_affinity, &symbol, sizeof(real_pthread_affinity));
}

static bool cpu_zero_only(size_t size, const cpu_set_t *set) {
    const unsigned char *bytes = (const unsigned char *)set;

    if (set == NULL || size == 0 || (bytes[0] & 1U) == 0) {
        return false;
    }
    if ((bytes[0] & ~1U) != 0) {
        return false;
    }
    for (size_t index = 1; index < size; ++index) {
        if (bytes[index] != 0) {
            return false;
        }
    }
    return true;
}

__attribute__((constructor)) static void initialize_affinity_shim(void) {
    const char *enabled = getenv("DECKLITE_REMAP_CPU0");
    const char *requested = getenv("DECKLITE_AFFINITY_CPU");
    const char *policy = getenv("DECKLITE_WINE_CPU_POLICY");
    cpu_set_t allowed;

    resolve_syscall();
    decklite_affinity_enabled = enabled != NULL && strcmp(enabled, "1") == 0;
    if (!decklite_affinity_enabled || decklite_real_syscall == NULL) {
        return;
    }
    CPU_ZERO(&allowed);
    if (decklite_real_syscall(
            SYS_sched_getaffinity, 0, sizeof(allowed), &allowed) < 0) {
        decklite_affinity_enabled = false;
        return;
    }
    if (requested != NULL && *requested != '\0') {
        char *end = NULL;
        long cpu = strtol(requested, &end, 10);
        if (end != requested && *end == '\0' && cpu >= 0 &&
                cpu < CPU_SETSIZE && CPU_ISSET((int)cpu, &allowed)) {
            target_cpu = (int)cpu;
        }
    }
    memcpy(&initial_allowed, &allowed, sizeof(initial_allowed));
    if (policy != NULL) {
        cpu_set_t selected, candidates, applied;
        bool found = false;
        /* An inherited sched affinity is not the Android cpuset boundary.
         * Steam/FEX or a formerly offline CPU can leave the parent narrowed.
         * Select from the machine, then let the kernel intersect with its
         * current cpuset/online restrictions and read back the effective set.
         * No cgroup, hotplug or thermal setting is changed here. */
        CPU_ZERO(&candidates);
        for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) CPU_SET(cpu, &candidates);
        if (strcmp(policy, "big") == 0) {
            found = select_big_cores(&selected, &candidates, "cpu_capacity") ||
                select_big_cores(&selected, &candidates, "cpufreq/cpuinfo_max_freq");
            if (!found) {
                /* Unknown/homogeneous topology: all kernel-permitted CPUs. */
                long count = sysconf(_SC_NPROCESSORS_CONF);
                CPU_ZERO(&selected);
                if (count > 0 && count <= CPU_SETSIZE) {
                    for (int cpu = 0; cpu < count; ++cpu) CPU_SET(cpu, &selected);
                } else {
                    memcpy(&selected, &allowed, sizeof(selected));
                }
                found = true;
            }
        } else if (strcmp(policy, "custom") == 0) {
            found = select_custom_cores(&selected, &candidates, getenv("DECKLITE_WINE_CPUS"));
        }
        if (found) {
            /* All subsequent Wine threads inherit this mask. If the kernel
             * rejects it (e.g. a cpuset changed), retain its allowed set. */
            if (decklite_real_syscall(SYS_sched_setaffinity, 0, sizeof(selected), &selected) == 0) {
                CPU_ZERO(&applied);
                if (decklite_real_syscall(SYS_sched_getaffinity, 0, sizeof(applied), &applied) == 0) {
                    memcpy(&initial_allowed, &applied, sizeof(initial_allowed));
                } else {
                    memcpy(&initial_allowed, &selected, sizeof(initial_allowed));
                }
                /* sched_getaffinity can omit a temporarily inactive core.
                 * Keep the requested policy, not that transient snapshot,
                 * for later calls; the kernel still enforces availability. */
                memcpy(&policy_selected, &selected, sizeof(policy_selected));
                restricted_policy = true;
            }
        }
    }
}

static const cpu_set_t *remap_mask(size_t size, const cpu_set_t *set,
                                 cpu_set_t *replacement) {
    if (!decklite_affinity_enabled || size == 0 || set == NULL ||
            size > sizeof(*replacement) ||
            (!restricted_policy && !cpu_zero_only(size, set))) {
        return set;
    }
    memcpy(replacement, restricted_policy ? &policy_selected : &initial_allowed,
           sizeof(*replacement));
    if (restricted_policy) {
        bool nonempty = false;
        for (size_t index = 0; index < size; ++index) {
            nonempty |= ((const unsigned char *)set)[index] != 0;
        }
        if (!nonempty) return set; /* Preserve the kernel's empty-mask error. */
        /* big/custom means every selected core stays available, including
         * prime cores. Wine/FEX must not reduce it to an intersecting subset.
         * Policy=all or REMAP_CPU0=0 retains explicit application affinity. */
    } else if (target_cpu >= 0) {
        CPU_ZERO(replacement);
        CPU_SET(target_cpu, replacement);
    }
    /* A caller can supply a smaller mask than cpu_set_t. Never silently
     * truncate an expanded mask and accidentally narrow its affinity. */
    for (size_t index = size; index < sizeof(*replacement); ++index) {
        if (((const unsigned char *)replacement)[index] != 0) {
            return set;
        }
    }
    return replacement;
}

__attribute__((visibility("hidden"), used, noinline)) long
decklite_intercept_sched_setaffinity(long process, size_t size, const cpu_set_t *set) {
    cpu_set_t replacement;
    if (decklite_real_syscall == NULL) {
        errno = ENOSYS;
        return -1;
    }
    return decklite_real_syscall(
        SYS_sched_setaffinity, process, size, remap_mask(size, set, &replacement));
}

int pthread_setaffinity_np(pthread_t thread, size_t size, const cpu_set_t *set) {
    cpu_set_t replacement;
    if (real_pthread_affinity == NULL) return ENOSYS;
    return real_pthread_affinity(thread, size, remap_mask(size, set, &replacement));
}

int sched_setaffinity(pid_t process, size_t size, const cpu_set_t *set) {
    return (int)decklite_intercept_sched_setaffinity(process, size, set);
}

#if !defined(__aarch64__)
#error "The diagnostic syscall forwarder currently supports AArch64 only"
#endif
