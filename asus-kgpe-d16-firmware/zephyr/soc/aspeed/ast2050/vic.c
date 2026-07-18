/*
 * ASPEED AST2050 (G3) VIC glue for ARM_CUSTOM_INTERRUPT_CONTROLLER.
 * SPDX-License-Identifier: Apache-2.0
 *
 * MILESTONE 0: minimal stubs so the ARM926 kernel links and boots to main()
 * with interrupts effectively off (the polling NS16550 console needs no IRQs).
 * MILESTONE 1 replaces these with real access to the compact G3 VIC at
 * 0x1e6c0000 (datasheet §16; the register layout is already reverse-engineered
 * for the Linux irq-aspeed-g3-vic driver — SENSE/DUAL/EVENT + enable/status).
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>

void z_soc_irq_init(void)
{
	/* M0: leave the VIC in its reset state (all sources masked). */
}

void z_soc_irq_enable(unsigned int irq)
{
	ARG_UNUSED(irq);
}

void z_soc_irq_disable(unsigned int irq)
{
	ARG_UNUSED(irq);
}

int z_soc_irq_is_enabled(unsigned int irq)
{
	ARG_UNUSED(irq);
	return 0;
}

void z_soc_irq_priority_set(unsigned int irq, unsigned int prio,
			    unsigned int flags)
{
	ARG_UNUSED(irq);
	ARG_UNUSED(prio);
	ARG_UNUSED(flags);
}

unsigned int z_soc_irq_get_active(void)
{
	/* M0: no VIC readout yet -> report spurious. */
	return CONFIG_NUM_IRQS;
}

void z_soc_irq_eoi(unsigned int irq)
{
	ARG_UNUSED(irq);
}
