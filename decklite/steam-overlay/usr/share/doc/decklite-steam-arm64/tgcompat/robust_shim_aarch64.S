/* AArch64 syscall interposer for Wine/FEX. Non-target syscalls tail-branch to
 * glibc without reading or rewriting any argument registers or stack slots. */

    .text
    .p2align 2
    .global syscall
    .type syscall, %function
    .hidden tgcompat_real_syscall
    .hidden tgcompat_robust_list_enabled
    .hidden tgcompat_userfaultfd_enosys_enabled
    .hidden tgcompat_emulate_get_robust_list
    .hidden tgcompat_syscall_enosys

syscall:
    adrp x8, tgcompat_userfaultfd_enosys_enabled
    ldrb w8, [x8, #:lo12:tgcompat_userfaultfd_enosys_enabled]
    cbz w8, 1f
    cmp x0, #374
    b.eq tgcompat_syscall_enosys
    cmp x0, #282
    b.eq tgcompat_syscall_enosys

1:
    adrp x8, tgcompat_robust_list_enabled
    ldrb w8, [x8, #:lo12:tgcompat_robust_list_enabled]
    cbz w8, 2f
    cmp x0, #100
    b.ne 2f
    cbnz x1, 2f
    mov x0, x1
    mov x1, x2
    mov x2, x3
    b tgcompat_emulate_get_robust_list

2:
    adrp x8, tgcompat_real_syscall
    ldr x8, [x8, #:lo12:tgcompat_real_syscall]
    cbz x8, tgcompat_syscall_enosys
    br x8

    .size syscall, .-syscall
    .section .note.GNU-stack,"",%progbits
