/*
 * AST2050 (G3) RTC smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Sets a known time on the counter-style RTC (drivers/rtc/rtc_aspeed_g3.c),
 * reads it back, and prints a clear PASS/FAIL. The QEMU G3 RTC model is
 * register-accurate for the load/read path but does not auto-advance the
 * counter, so a set->load->get round-trip returns exactly what was set — which
 * is what this validates. The G3 counter carries sec/min/hour/day only (no
 * calendar), so only those fields are checked.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/rtc.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/sys_io.h>

/* #192 diagnostic: raw MMIO to localize why the alarm IRQ (VIC 26) doesn't fire
 * on silicon. Both regions are identity-mapped by the SoC (rtc/vic drivers). */
#define RTC_REG_BASE  0x1E781000U
#define RTC_REG_COUNTER (RTC_REG_BASE + 0x00U)
#define RTC_REG_ALARM   (RTC_REG_BASE + 0x04U)
#define RTC_REG_CONTROL (RTC_REG_BASE + 0x0CU)
#define G3VIC_BASE      0x1E6C0000U
#define G3VIC_RAW_STATUS (G3VIC_BASE + 0x08U) /* raw (pre-mask) IRQ status */
#define G3VIC_IRQ_STATUS (G3VIC_BASE + 0x00U) /* post-mask/enable IRQ status */

#define RTC_SMOKE_NODE DT_NODELABEL(rtc0)

BUILD_ASSERT(DT_NODE_HAS_STATUS(RTC_SMOKE_NODE, okay),
	     "rtc0 (aspeed,ast2050-rtc) must be enabled");

#if defined(CONFIG_RTC_ALARM)
static volatile uint32_t alarm_fires;

static void rtc_alarm_cb(const struct device *dev, uint16_t id, void *user_data)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(id);
	ARG_UNUSED(user_data);
	alarm_fires++;
}

/*
 * Alarm half of the smoke (#187): set a base time, register a callback, arm the
 * alarm a few seconds ahead, and confirm it fires. The QEMU G3 RTC model
 * advances the COUNTER on its own (QEMU timer, ~732x on this crystal-less board,
 * #158) and raises VIC source 26 on an RTC04 match — so we BUSY-POLL (keeping
 * the CPU running so QEMU virtual time advances) rather than k_msleep, which
 * would depend on the guest system tick. The +5 s alarm is reached in ~7 ms of
 * counter time.
 */
static void rtc_alarm_test(const struct device *rtc)
{
	uint16_t sup = 0, gmask = 0;
	struct rtc_time base = {
		.tm_sec = 0, .tm_min = 0, .tm_hour = 12, .tm_mday = 7,
	};
	struct rtc_time alarm = base;
	struct rtc_time galarm = {0};
	int ret;

	if (rtc_alarm_get_supported_fields(rtc, 0, &sup) != 0) {
		printk("RTC-ALARM RESULT: FAIL (get_supported_fields)\n");
		return;
	}
	printk("alarm supported-fields mask=0x%02x\n", sup);

	/* Re-plant a known base time, then arm hour:min:sec = 12:00:05. */
	if (rtc_set_time(rtc, &base) != 0) {
		printk("RTC-ALARM RESULT: FAIL (set base time)\n");
		return;
	}
	alarm.tm_sec = 5;
	alarm_fires = 0;

	ret = rtc_alarm_set_callback(rtc, 0, rtc_alarm_cb, NULL);
	if (ret != 0) {
		printk("RTC-ALARM RESULT: FAIL (set_callback %d)\n", ret);
		return;
	}
	ret = rtc_alarm_set_time(rtc, 0,
				 RTC_ALARM_TIME_MASK_SECOND |
				 RTC_ALARM_TIME_MASK_MINUTE |
				 RTC_ALARM_TIME_MASK_HOUR, &alarm);
	if (ret != 0) {
		printk("RTC-ALARM RESULT: FAIL (set_time %d)\n", ret);
		return;
	}

	/* Confirm the arm read back. */
	if (rtc_alarm_get_time(rtc, 0, &gmask, &galarm) == 0) {
		printk("alarm armed at %02d:%02d:%02d mask=0x%02x\n",
		       galarm.tm_hour, galarm.tm_min, galarm.tm_sec, gmask);
	}

	/*
	 * Wait for the alarm by HALTING the CPU (WFI), via k_cpu_atomic_idle(), not
	 * a spin loop or k_busy_wait(). Rationale:
	 *  - a tight spin never yields, so QEMU's main loop can't fire the virtual
	 *    alarm timer -> VIC-26 may never arrive (a QEMU TCG scheduling artifact,
	 *    not a silicon behaviour — the real comparator can't be starved);
	 *  - k_busy_wait()/k_msleep() depend on the guest system tick / cycle
	 *    counter, which is not reliable on this brand-new ARM926 port.
	 * When the guest WFIs, QEMU (all CPUs halted) WARPS virtual time forward to
	 * the next timer deadline, fires the alarm timer, and wakes the CPU on VIC-26
	 * — deterministic. k_cpu_atomic_idle() atomically re-enables IRQs and WFIs,
	 * closing the check-then-sleep lost-wakeup window. Bounded so a broken alarm
	 * fails loudly rather than hanging.
	 */
	{
		unsigned int key = irq_lock();

		for (uint32_t i = 0; i < 1000U && alarm_fires == 0U; i++) {
			k_cpu_atomic_idle(key);
			key = irq_lock();
		}
		irq_unlock(key);
	}

	/* #192 diagnostic: localize the alarm-IRQ path (RTC assert vs VIC route). */
	printk("DIAG counter=%08x rtc04=%08x ctrl=%08x vic_raw=%08x vic_sts=%08x\n",
	       sys_read32(RTC_REG_COUNTER), sys_read32(RTC_REG_ALARM),
	       sys_read32(RTC_REG_CONTROL), sys_read32(G3VIC_RAW_STATUS),
	       sys_read32(G3VIC_IRQ_STATUS));

	printk("alarm fires=%u\n", alarm_fires);
	if (alarm_fires > 0U) {
		printk("RTC-ALARM RESULT: PASS (armed -> VIC22 -> callback)\n");
	} else {
		printk("RTC-ALARM RESULT: FAIL (no callback within busy-poll)\n");
	}

	/*
	 * Regression for the #187 review finding: rtc_set_time() must NOT silently
	 * disarm an armed alarm (its CONTROL write is an RMW that preserves the
	 * alarm-enable bits). Re-arm, plant a base time (12:00:00, so the 12:00:05
	 * alarm has not matched yet), and confirm the arm survived.
	 */
	(void)rtc_alarm_set_time(rtc, 0,
				 RTC_ALARM_TIME_MASK_SECOND |
				 RTC_ALARM_TIME_MASK_MINUTE |
				 RTC_ALARM_TIME_MASK_HOUR, &alarm);
	(void)rtc_set_time(rtc, &base);
	gmask = 0xFFFF;
	if (rtc_alarm_get_time(rtc, 0, &gmask, &galarm) == 0) {
		printk("after set_time, alarm mask=0x%02x\n", gmask);
		if (gmask == (RTC_ALARM_TIME_MASK_SECOND | RTC_ALARM_TIME_MASK_MINUTE |
			      RTC_ALARM_TIME_MASK_HOUR)) {
			printk("RTC-ALARM-PRESERVE: PASS (set_time kept the alarm armed)\n");
		} else {
			printk("RTC-ALARM-PRESERVE: FAIL (set_time disarmed the alarm)\n");
		}
	}

	/* Disarm (mask 0) — proves the disable path and stops further fires. */
	rtc_alarm_set_time(rtc, 0, 0, NULL);
}
#endif /* CONFIG_RTC_ALARM */

int main(void)
{
	const struct device *rtc = DEVICE_DT_GET(RTC_SMOKE_NODE);
	struct rtc_time set = {
		.tm_sec = 30, .tm_min = 45, .tm_hour = 12, .tm_mday = 7,
	};
	struct rtc_time got = {0};
	int ret;

	if (!device_is_ready(rtc)) {
		printk("RTC smoke: device not ready\n");
		return 0;
	}

	ret = rtc_set_time(rtc, &set);
	if (ret != 0) {
		printk("RTC smoke: set_time failed (%d)\n", ret);
		return 0;
	}

	ret = rtc_get_time(rtc, &got);
	if (ret != 0) {
		printk("RTC smoke: get_time failed (%d)\n", ret);
		return 0;
	}

	/*
	 * Compare with a FORWARD-only test, NOT an exact match and NOT a tight
	 * window: in QEMU the model does not auto-advance so delta is exactly 0, but
	 * on real silicon this board clocks the RTC from the 24 MHz "test" source
	 * (no working 32.768 kHz path — rtc_aspeed_g3.c header / #158), so the second
	 * counter runs ~732x fast and a set→get legitimately reads TENS of seconds of
	 * drift (LOG 2026-07-19 observed 12:45:68, delta=38s). A tight upper bound
	 * (e.g. <=10) would false-FAIL that correct-but-fast hardware. The real
	 * failure signal this check protects against is the pre-poll bug where the
	 * counter was never loaded and read back 0x0 → day=0 and/or a NEGATIVE delta.
	 * So: same day + monotonic-forward is the pass; exact rate is out of scope.
	 */
	int set_tod = set.tm_hour * 3600 + set.tm_min * 60 + set.tm_sec;
	int got_tod = got.tm_hour * 3600 + got.tm_min * 60 + got.tm_sec;
	int delta = got_tod - set_tod;

	printk("RTC set=%02d:%02d:%02d day=%d  get=%02d:%02d:%02d day=%d  (delta=%ds)\n",
	       set.tm_hour, set.tm_min, set.tm_sec, set.tm_mday,
	       got.tm_hour, got.tm_min, got.tm_sec, got.tm_mday, delta);

	if (got.tm_mday == set.tm_mday && delta >= 0) {
		printk("RTC RESULT: PASS\n");
	} else {
		printk("RTC RESULT: FAIL\n");
	}

#if defined(CONFIG_RTC_ALARM)
	rtc_alarm_test(rtc);
#endif

	return 0;
}
