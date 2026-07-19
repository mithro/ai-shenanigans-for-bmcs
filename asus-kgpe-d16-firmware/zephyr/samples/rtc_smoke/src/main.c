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

#define RTC_SMOKE_NODE DT_NODELABEL(rtc0)

BUILD_ASSERT(DT_NODE_HAS_STATUS(RTC_SMOKE_NODE, okay),
	     "rtc0 (aspeed,ast2050-rtc) must be enabled");

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
	 * Compare with a small FORWARD tolerance, not exact-match: on real silicon
	 * the counter runs at 1 Hz once enabled, so between the load completing and
	 * this read it may legitimately have ticked a few seconds; in QEMU the model
	 * does not advance, so delta is exactly 0. A negative delta or a day mismatch
	 * means the value was NOT loaded (the pre-poll silicon bug read back 0x0).
	 */
	int set_tod = set.tm_hour * 3600 + set.tm_min * 60 + set.tm_sec;
	int got_tod = got.tm_hour * 3600 + got.tm_min * 60 + got.tm_sec;
	int delta = got_tod - set_tod;

	printk("RTC set=%02d:%02d:%02d day=%d  get=%02d:%02d:%02d day=%d  (delta=%ds)\n",
	       set.tm_hour, set.tm_min, set.tm_sec, set.tm_mday,
	       got.tm_hour, got.tm_min, got.tm_sec, got.tm_mday, delta);

	if (got.tm_mday == set.tm_mday && delta >= 0 && delta <= 10) {
		printk("RTC RESULT: PASS\n");
	} else {
		printk("RTC RESULT: FAIL\n");
	}

	return 0;
}
