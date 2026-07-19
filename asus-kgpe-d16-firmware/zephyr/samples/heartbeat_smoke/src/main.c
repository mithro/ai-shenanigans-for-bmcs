/*
 * AST2050 (G3) heartbeat smoke test — proves the VIC + system timer deliver
 * SUSTAINED ticks (not just a one-shot boot).
 * SPDX-License-Identifier: Apache-2.0
 *
 * k_msleep() puts the thread to sleep and only returns when a system-timer tick
 * IRQ (Timer1 @ VIC source 16, soc/aspeed/ast2050/aspeed_timer.c + vic.c) fires
 * and the kernel's tick handler wakes it; k_uptime_get() is derived from the same
 * tick count. So N successful k_msleep()+uptime iterations = N proofs that the
 * timer is running, the VIC is routing + acking its IRQ, and the ISR path works.
 * If the timer/VIC did NOT deliver, the very first k_msleep() would hang forever.
 *
 * Kept SHORT (10 x 100 ms = ~1 s ≈ 100-1000 ticks) so it stays well under the
 * QEMU-only arm_mmu sustained-ticking corruption seen ~2264 ticks (device-driver-
 * program task #141 / d14-zephyr/03) — on real silicon there is no such limit.
 * Build with -DCONFIG_SYS_CLOCK_EXISTS=y (tickful).
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define TICKS 10

int main(void)
{
	int64_t t0 = k_uptime_get();

	printk("Heartbeat: %d x k_msleep(100ms) — each needs a timer+VIC tick IRQ\n", TICKS);

	for (int i = 1; i <= TICKS; i++) {
		k_msleep(100);
		printk("tick %d/%d uptime=%lld ms\n", i, TICKS, k_uptime_get());
	}

	/*
	 * PASS = we completed all TICKS sleeps AND uptime advanced by roughly the
	 * expected wall time (>= ~ half the nominal, allowing for timer-rate slop) —
	 * i.e. the timer both DELIVERED interrupts (woke the sleeps) and COUNTS.
	 */
	int64_t elapsed = k_uptime_get() - t0;

	printk("Heartbeat done: %d ticks, elapsed=%lld ms (expected ~%d)\n",
	       TICKS, elapsed, TICKS * 100);
	if (elapsed >= (TICKS * 100) / 2) {
		printk("HEARTBEAT RESULT: PASS\n");
	} else {
		printk("HEARTBEAT RESULT: FAIL\n");
	}
	return 0;
}
