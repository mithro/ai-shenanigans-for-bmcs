/*
 * ASPEED AST2050 (G3) VIC — ARM_CUSTOM_INTERRUPT_CONTROLLER glue for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Milestone 1: real access to the compact single-bank G3 VIC at 0x1e6c0000
 * (datasheet §16). The register layout and the SENSE/DUAL/EVENT init constants
 * are the same ones reverse-engineered for the Linux irq-aspeed-g3-vic driver
 * (JTAG-confirmed on silicon) — 32 sources, one bank. The cortex_a_r
 * isr_wrapper calls z_soc_irq_get_active() to find the source, dispatches the
 * Zephyr ISR table entry, then calls z_soc_irq_eoi().
 *
 * Timer1 (source 16) is configured by these constants as EDGE / single /
 * RISING (sense0/dual0/event1) — which is exactly how the faithful QEMU G3
 * timer model and real silicon deliver it (one rising-edge pulse per expiry,
 * latched in the VIC raw status). eoi clears that latched edge.
 */

#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/sys_io.h>

#define G3VIC_BASE		0x1e6c0000u

#define G3VIC_IRQ_STATUS	0x00
#define G3VIC_FIQ_STATUS	0x04
#define G3VIC_RAW_STATUS	0x08
#define G3VIC_INT_SELECT	0x0c	/* 0 = IRQ, 1 = FIQ */
#define G3VIC_INT_ENABLE	0x10	/* write 1 = enable */
#define G3VIC_INT_ENABLE_CLR	0x14	/* write 1 = disable */
#define G3VIC_SOFT_INT		0x18
#define G3VIC_SOFT_INT_CLR	0x1c
#define G3VIC_INT_SENSE		0x24	/* 1 = level, 0 = edge */
#define G3VIC_INT_DUAL_EDGE	0x28	/* 1 = both edges */
#define G3VIC_INT_EVENT		0x2c	/* edge: 1 = rising, 0 = falling */
#define G3VIC_EDGE_CLR		0x38	/* write 1 = clear latched edge */

/* Reset defaults RE'd for the G3 VIC (irq-aspeed-g3-vic): timer src 16 is
 * edge/single/rising, matching the G3 timer's one-pulse-per-expiry delivery.
 */
#define G3VIC_SENSE_INIT	0x903897feU
#define G3VIC_DUAL_EDGE_INIT	0x07c00000U
#define G3VIC_EVENT_INIT	0x983f97feU

static inline uint32_t vic_rd(uint32_t off)
{
	return sys_read32(G3VIC_BASE + off);
}

static inline void vic_wr(uint32_t off, uint32_t val)
{
	sys_write32(val, G3VIC_BASE + off);
}

void z_soc_irq_init(void)
{
	/* All sources -> IRQ (not FIQ), all masked. */
	vic_wr(G3VIC_INT_SELECT, 0);
	vic_wr(G3VIC_INT_ENABLE_CLR, 0xffffffffU);
	/* Program the RE'd edge/level/polarity map, then clear any latched edge. */
	vic_wr(G3VIC_INT_SENSE, G3VIC_SENSE_INIT);
	vic_wr(G3VIC_INT_DUAL_EDGE, G3VIC_DUAL_EDGE_INIT);
	vic_wr(G3VIC_INT_EVENT, G3VIC_EVENT_INIT);
	vic_wr(G3VIC_EDGE_CLR, 0xffffffffU);
	vic_wr(G3VIC_SOFT_INT_CLR, 0xffffffffU);
}

void z_soc_irq_enable(unsigned int irq)
{
	if (irq < 32) {
		/*
		 * Clear any latched/pending edge for this source BEFORE unmasking it,
		 * so enabling an IRQ cannot immediately fire on a stale edge — e.g. a
		 * prior boot's timer edge, or the glitch a peripheral latches on its own
		 * enable transition. This mirrors Raptor's init_delay_timer, which
		 * writes VIC EDGE_CLR for the timer source before enabling it. Without
		 * it, on real silicon the timer's edge fired the instant its IRQ was
		 * unmasked, mid-kernel-init, and crashed the boot. Harmless for level
		 * sources (their bit is not latched by EDGE_CLR).
		 */
		vic_wr(G3VIC_EDGE_CLR, BIT(irq));
		vic_wr(G3VIC_INT_ENABLE, BIT(irq));
	}
}

void z_soc_irq_disable(unsigned int irq)
{
	if (irq < 32) {
		vic_wr(G3VIC_INT_ENABLE_CLR, BIT(irq));
	}
}

int z_soc_irq_is_enabled(unsigned int irq)
{
	if (irq >= 32) {
		return 0;
	}
	return !!(vic_rd(G3VIC_INT_ENABLE) & BIT(irq));
}

void z_soc_irq_priority_set(unsigned int irq, unsigned int prio,
			    unsigned int flags)
{
	/* The G3 VIC has no per-source priority; edge/level is fixed by the
	 * init map above. Nothing to program per-IRQ.
	 */
	ARG_UNUSED(irq);
	ARG_UNUSED(prio);
	ARG_UNUSED(flags);
}

unsigned int z_soc_irq_get_active(void)
{
	uint32_t status = vic_rd(G3VIC_IRQ_STATUS);
	unsigned int irq;

	if (status == 0) {
		return CONFIG_NUM_IRQS;		/* spurious */
	}
	irq = (unsigned int)__builtin_ctz(status);

	/*
	 * The Zephyr cortex_a_r isr_wrapper re-enables IRQs *before* dispatching the
	 * ISR (the GIC-style nested model, where the controller masks the active
	 * source by priority). The compact G3 VIC has NO priority masking, so we
	 * must quiesce the claimed source here, at claim time, or it re-asserts the
	 * instant IRQs re-enable and storms/recurses the CPU. How to quiesce depends
	 * on the trigger type (INT_SENSE: 1 = level, 0 = edge):
	 */
	if (vic_rd(G3VIC_INT_SENSE) & BIT(irq)) {
		/*
		 * LEVEL source (I2C/GPIO/UART-RX/MAC…): the line stays asserted until
		 * the ISR clears the device condition, so an edge-clear does nothing.
		 * MASK it now; z_soc_irq_eoi() re-enables it after the ISR. This is the
		 * mask-during-ISR model of Linux handle_level_irq() / the g3-vic
		 * driver's g3vic_mask_ack_irq — it prevents the immediate nested
		 * re-entry (and the duplicate post-unwind dispatch) that an unmasked
		 * still-asserted level line would cause.
		 */
		vic_wr(G3VIC_INT_ENABLE_CLR, BIT(irq));
	} else {
		/*
		 * EDGE source (e.g. the Timer1 tick): the pulse is latched in
		 * RAW_STATUS until EDGE_CLR. ACK it now, like Linux handle_edge_irq()'s
		 * ack-at-entry, so the latched edge can't re-storm when IRQs re-enable;
		 * an edge that re-triggers *during* the ISR re-latches and is handled by
		 * the next delivery (no ticks lost). No masking needed — EOI is a no-op
		 * for edge sources.
		 *
		 * QEMU never exposed the storm: its timer edge does not persist across
		 * the re-enable window. Silicon is the faithful oracle.
		 */
		vic_wr(G3VIC_EDGE_CLR, BIT(irq));
	}
	return irq;
}

void z_soc_irq_eoi(unsigned int irq)
{
	/*
	 * Re-enable a LEVEL source that z_soc_irq_get_active() masked at claim time
	 * (the ISR has now cleared the device condition, so the line has deasserted
	 * and re-enabling won't immediately re-fire; if a genuine new condition
	 * arose during the ISR, the still-asserted level fires again — no loss).
	 * EDGE sources were ACKed at claim and need nothing here: clearing the edge
	 * again would discard an edge that re-triggered while the ISR ran.
	 */
	if (irq < 32 && (vic_rd(G3VIC_INT_SENSE) & BIT(irq))) {
		vic_wr(G3VIC_INT_ENABLE, BIT(irq));
	}
}
