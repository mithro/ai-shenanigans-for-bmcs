/* Minimal ARM926EJ-S reset stub for AST2050 bare-metal tests.
 *
 * Loaded into DRAM (0x40000000) via `qemu-system-arm -kernel test.elf`, which
 * enters at _start with the MMU and caches off. We set a stack, zero BSS, and
 * call fwtest_main(); on return we spin. Apache-2.0.
 */
    .section .text.start, "ax"
    .arm
    .global _start
_start:
    ldr     sp, =_stack_top

    /* zero .bss */
    ldr     r0, =_bss_start
    ldr     r1, =_bss_end
    mov     r2, #0
1:  cmp     r0, r1
    strlo   r2, [r0], #4
    blo     1b

    bl      fwtest_main

2:  b       2b
    .pool
