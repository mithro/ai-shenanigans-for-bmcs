/*
 * AST2050 Milestone-0 polling console.
 * SPDX-License-Identifier: Apache-2.0
 *
 * A minimal printk backend that writes UART5 (0x1e784000) at its PHYSICAL
 * address, reached via the static identity MMU region in soc.c. This exists
 * only for M0 bring-up: it sidesteps the ns16550 + CONFIG_MMU DEVICE_MMIO_MAP
 * path, whose z_phys_map hands the driver a virtual base the ARM926 arm_mmu
 * does not translate back to 0x1e784000 (the console then busy-polls an
 * unimplemented address and never prints). The UART is already configured for
 * 115200-8N1 by the loader (U-Boot on silicon, the machine model in QEMU), so
 * this backend only polls THRE and writes THR - no divisor/line setup.
 *
 * Registers use the AST2050 4-byte stride (reg-shift = 2): THR at +0x00,
 * LSR at +0x14, matching the dts serial@1e784000 node and the bare-metal
 * fwtests that print at this base.
 *
 * Once the ARM926 device-MMIO mapping is fixed upstream (or a maps-identity
 * DEVICE_MMIO option lands), the standard ns16550 UART console replaces this.
 */

#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/sys/printk-hooks.h>
#include <zephyr/sys/libc-hooks.h>
#include <zephyr/sys/util.h>

#define UART5_PHYS_BASE  0x1e784000u
#define UART_REG_THR     0x00u          /* transmit holding (reg 0 << 2) */
#define UART_REG_LSR     0x14u          /* line status     (reg 5 << 2) */
#define UART_LSR_THRE    BIT(5)         /* transmit holding register empty */

/*
 * BYTE-wide accesses at the reg-shift=2 stride. The AST2050 16550 (both real
 * silicon and the QEMU serial_mm model) is addressed one byte per register at
 * the shifted offset; a 32-bit access is mishandled (QEMU splits it and the
 * THR write never reaches the chardev). The Linux ns16550 driver uses the same
 * size-1 accesses.
 */
static inline volatile uint8_t *uart_reg(uint32_t off)
{
	return (volatile uint8_t *)(UART5_PHYS_BASE + off);
}

static void ast2050_putc(unsigned char c)
{
	while (!(*uart_reg(UART_REG_LSR) & UART_LSR_THRE)) {
		/* spin until the holding register is empty */
	}
	*uart_reg(UART_REG_THR) = c;
}

static int ast2050_console_out(int c)
{
	if (c == '\n') {
		ast2050_putc('\r');
	}
	ast2050_putc((unsigned char)c);
	return c;
}

static int ast2050_console_init(void)
{
	/* printk (kernel/banner) and printf/stdout (application, e.g. the
	 * hello_world sample) both route to the polling UART backend. */
	__printk_hook_install(ast2050_console_out);
	__stdout_hook_install(ast2050_console_out);
	return 0;
}

/*
 * PRE_KERNEL_1 priority 0: install the hook before the boot banner and any
 * other early printk output, so the very first characters reach the UART.
 */
SYS_INIT(ast2050_console_init, PRE_KERNEL_1, 0);
