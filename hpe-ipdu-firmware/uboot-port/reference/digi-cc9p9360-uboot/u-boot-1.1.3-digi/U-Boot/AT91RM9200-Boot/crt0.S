@ r0 -> start of flash
@ r1 -> where to load data
@ r2 -> start of program

	.text
	.align
	.global main,_main

main:
_main:
	# copy .data section
	ldr r3, =_etext
	ldr r4, =_sdata
	ldr r5, =_edata
	subs r5, r5, r4
	bl copydata

	# clear .bss section
	ldr r4, =_sbss
	ldr r5, =_ebss
	subs r5, r5, r4
	mov r0, #0
	bl clearbss
	
	# and jump to the kernel
	b boot

copydata:
	subs r5, r5, #4
	ldr r6, [r3], #4
	str r6, [r4], #4
	bne copydata
	mov pc, lr

clearbss:
	subs r5, r5, #4
	str r0, [r3], #4
	bne clearbss
	mov pc, lr
