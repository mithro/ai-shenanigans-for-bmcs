/*
 * AST2050 (G3) watchdog TIMEOUT-INTERRUPT smoke test (#189).
 * SPDX-License-Identifier: Apache-2.0
 *
 * The G3 WDT is one-stage: WDT_CTRL[2] (WDT_INTR) makes it raise its interrupt
 * (G3 VIC source 27) on timeout INSTEAD of resetting the SoC. The Zephyr driver
 * maps WDT_FLAG_RESET_NONE + a callback onto that mode. This proves the whole
 * path: install(interrupt) -> setup(arm) -> timeout -> VIC-27 -> ISR -> callback.
 *
 * We do NOT feed, so the WDT times out (~200 ms) and the callback runs exactly
 * once (WDT_INTR is one-shot: the hardware fires the IRQ instead of resetting and
 * does not re-arm). Then we disable the WDT so it stays quiet.
 *
 * WAIT MECHANISM: we wait for the callback by HALTING the CPU (WFI, via
 * k_cpu_atomic_idle), not k_msleep/k_busy_wait: the guest system tick / cycle
 * counter is not reliable on this brand-new ARM926 port (the arm_mmu ticking
 * gap). On CPU halt QEMU warps virtual time to the WDT timer deadline, fires it,
 * and wakes the CPU on VIC-27 — deterministic and tick-independent, exactly how
 * a real consumer waits. Contrast the reset-mode wdt_smoke, which observes the
 * reset across a reboot and needs no wait.
 *
 * PASS: "WDT-INTR RESULT: PASS" once the callback has fired.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/watchdog.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define WDT_NODE      DT_NODELABEL(wdt0) /* aspeed,ast2050-wdt @ 0x1E785000 */
#define WDT_INTR_MS   200U               /* timeout window */

BUILD_ASSERT(DT_NODE_HAS_STATUS(WDT_NODE, okay),
	     "wdt0 (aspeed,ast2050-wdt) must be enabled");

static volatile uint32_t wdt_intr_fires;

static void wdt_intr_cb(const struct device *dev, int channel_id)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(channel_id);
	wdt_intr_fires++;
}

int main(void)
{
	const struct device *wdt = DEVICE_DT_GET(WDT_NODE);
	struct wdt_timeout_cfg cfg = {
		.window = { .min = 0U, .max = WDT_INTR_MS },
		.callback = wdt_intr_cb,
		.flags = WDT_FLAG_RESET_NONE, /* interrupt-only -> WDT_INTR / VIC-27 */
	};
	int channel;
	int ret;

	printk("WDT-INTR smoke: boot\n");

	if (!device_is_ready(wdt)) {
		printk("WDT-INTR RESULT: FAIL (device not ready)\n");
		return 0;
	}

	channel = wdt_install_timeout(wdt, &cfg);
	if (channel < 0) {
		printk("WDT-INTR RESULT: FAIL (install_timeout %d)\n", channel);
		return 0;
	}

	ret = wdt_setup(wdt, 0);
	if (ret != 0) {
		printk("WDT-INTR RESULT: FAIL (setup %d)\n", ret);
		return 0;
	}
	printk("WDT armed %u ms in interrupt mode, NOT feeding\n", WDT_INTR_MS);

	/* Wait for the timeout interrupt by halting the CPU (see file header). */
	{
		unsigned int key = irq_lock();

		for (uint32_t i = 0; i < 1000U && wdt_intr_fires == 0U; i++) {
			k_cpu_atomic_idle(key);
			key = irq_lock();
		}
		irq_unlock(key);
	}

	printk("wdt intr fires=%u\n", wdt_intr_fires);
	if (wdt_intr_fires > 0U) {
		printk("WDT-INTR RESULT: PASS (timeout -> VIC-27 -> callback, no reset)\n");
	} else {
		printk("WDT-INTR RESULT: FAIL (no callback within wait)\n");
	}

	/*
	 * Regression for the #189 review finding: after a one-shot interrupt fires
	 * the WDT stays `installed`, so disable() must still succeed (not -EFAULT)
	 * and clear the install so a re-install works — the documented "disable then
	 * install again" escalation contract.
	 */
	ret = wdt_disable(wdt);
	channel = wdt_install_timeout(wdt, &cfg);
	printk("after fire: disable=%d reinstall=%d\n", ret, channel);
	if (ret == 0 && channel >= 0) {
		printk("WDT-INTR-REINSTALL: PASS (disable+reinstall after fire)\n");
	} else {
		printk("WDT-INTR-REINSTALL: FAIL (disable=%d reinstall=%d)\n",
		       ret, channel);
	}

	/* Leave the WDT stopped so it stays quiet after the test. */
	(void)wdt_disable(wdt);

	return 0;
}
