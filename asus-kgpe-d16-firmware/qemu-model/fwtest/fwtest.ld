/* Link AST2050 bare-metal tests to run from DRAM base (0x40000000).
 * QEMU -kernel loads the ELF by its program headers and jumps to _start.
 * Apache-2.0. */
ENTRY(_start)

SECTIONS
{
    . = 0x40000000;

    .text : {
        KEEP(*(.text.start))
        *(.text*)
        *(.rodata*)
        *(.glue_7) *(.glue_7t)
    }

    .data : {
        *(.data*)
    }

    . = ALIGN(8);
    _bss_start = .;
    .bss : {
        *(.bss*)
        *(COMMON)
    }
    . = ALIGN(8);
    _bss_end = .;

    /* 64 KiB stack above BSS. */
    . = . + 0x10000;
    . = ALIGN(8);
    _stack_top = .;

    /DISCARD/ : { *(.ARM.exidx*) *(.comment) *(.note*) }
}
