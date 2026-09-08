/* Preserve every non-target syscall argument exactly.  Wine performs affinity
 * changes through glibc's variadic syscall entry point on AArch64. */

    .text
    .p2align 2
    .global syscall
    .type syscall, %function
    .hidden decklite_real_syscall
    .hidden decklite_affinity_enabled
    .hidden decklite_intercept_sched_setaffinity

syscall:
    adrp x8, decklite_affinity_enabled
    ldrb w8, [x8, #:lo12:decklite_affinity_enabled]
    cbz w8, 1f
    cmp x0, #122
    b.ne 1f
    mov x0, x1
    mov x1, x2
    mov x2, x3
    b decklite_intercept_sched_setaffinity

1:
    adrp x8, decklite_real_syscall
    ldr x8, [x8, #:lo12:decklite_real_syscall]
    cbz x8, 2f
    br x8

2:
    mov x0, #-1
    ret

    .size syscall, .-syscall
    .section .note.GNU-stack,"",%progbits
