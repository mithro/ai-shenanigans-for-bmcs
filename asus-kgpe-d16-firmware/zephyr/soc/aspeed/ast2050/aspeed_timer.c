/*
 * ASPEED AST2050 (G3) system timer for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Milestone 1: a minimal tickful system clock built on Timer1 of the AST2050
 * timer block (0x1e782000, datasheet §17). Timer1 down-counts from RELOAD on
 * the 1 MHz external clock and raises VIC source 16 once per expiry (single
 * rising-edge pulse on the G3 — see vic.c and the faithful QEMU model), then
 * auto-reloads. The ISR announces one kernel tick; the VIC eoi clears the edge.
 *
 * Tickful only (CONFIG_TICKLESS_KERNEL=n) — this is the smallest correct system
 * clock that unblocks the scheduler / app thread. A tickless variant can be
 * added later by reprogramming RELOAD per timeout.
 */

#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/irq.h>
#include <zephyr/drivers/timer/system_timer.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/spinlock.h>

#define TIMER_BASE		0x1e782000u
/* Timer1 register block (each timer is 0x10 apart; Timer1 at +0x00). */
#define T1_STATUS		0x00	/* current count (down), RO */
#define T1_RELOAD		0x04
#define T1_MATCH1		0x08
#define T1_MATCH2		0x0c
#define TIMER_CTRL		0x30	/* shared; Timer1 = bits [3:0] */

/* Control bits for Timer1 (bit position within the 4-bit field). */
#define T1_CTRL_ENABLE		BIT(0)
#define T1_CTRL_EXT_CLOCK	BIT(1)	/* 1 MHz external clock */
#define T1_CTRL_OVERFLOW_INT	BIT(2)
#define T1_CTRL_PULSE		BIT(3)

#define TIMER_IRQ		16
#define TIMER_IRQ_PRIO		0

#define CYC_PER_TICK	\
	(CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC / CONFIG_SYS_CLOCK_TICKS_PER_SEC)

static struct k_spinlock lock;
/* Monotonic cycle count: advanced by CYC_PER_TICK on each announced tick. */
static volatile uint32_t announced_cycles;

static inline uint32_t tmr_rd(uint32_t off)
{
	return sys_read32(TIMER_BASE + off);
}

static inline void tmr_wr(uint32_t off, uint32_t val)
{
	sys_write32(val, TIMER_BASE + off);
}

static void aspeed_timer_isr(const void *arg)
{
	ARG_UNUSED(arg);

	k_spinlock_key_t key = k_spin_lock(&lock);

	announced_cycles += CYC_PER_TICK;
	k_spin_unlock(&lock, key);

	/* Tickful: one tick per expiry. The VIC eoi (edge clear) is done by the
	 * arch isr_wrapper after this returns.
	 */
	sys_clock_announce(1);
}

uint32_t sys_clock_elapsed(void)
{
	/* Tickful driver announces every tick -> no unannounced whole ticks. */
	return 0;
}

uint32_t sys_clock_cycle_get_32(void)
{
	k_spinlock_key_t key = k_spin_lock(&lock);
	/* Down-counter: elapsed within the current period = RELOAD - count. */
	uint32_t count = tmr_rd(T1_STATUS);
	uint32_t elapsed = (count <= CYC_PER_TICK) ? (CYC_PER_TICK - count) : 0;
	uint32_t ret = announced_cycles + elapsed;

	k_spin_unlock(&lock, key);
	return ret;
}

static int sys_clock_driver_init(void)
{
	uint32_t ctrl;

	/* Disable Timer1 while configuring (clear its 4-bit field). */
	ctrl = tmr_rd(TIMER_CTRL) & ~0xfU;
	tmr_wr(TIMER_CTRL, ctrl);

	tmr_wr(T1_RELOAD, CYC_PER_TICK);
	tmr_wr(T1_MATCH1, 0);
	tmr_wr(T1_MATCH2, 0);
	/* The counter loads from RELOAD on the enable transition below; STATUS
	 * (0x00) is the read-only live count, so there is nothing to pre-load. */

	IRQ_CONNECT(TIMER_IRQ, TIMER_IRQ_PRIO, aspeed_timer_isr, NULL, 0);
	irq_enable(TIMER_IRQ);

	/* Enable on the 1 MHz external clock with overflow interrupt (level-mode
	 * counter, single rising-edge pulse to the VIC per expiry). */
	ctrl |= (T1_CTRL_ENABLE | T1_CTRL_EXT_CLOCK | T1_CTRL_OVERFLOW_INT);
	tmr_wr(TIMER_CTRL, ctrl);

	return 0;
}

SYS_INIT(sys_clock_driver_init, PRE_KERNEL_2,
	 CONFIG_SYSTEM_CLOCK_INIT_PRIORITY);
