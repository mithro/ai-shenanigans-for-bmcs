/*
 * ASPEED AST2050 (G3) counter-style RTC driver for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * The AST2050 (ARM926EJ-S, G3 legacy register layout) integrates a compact
 * COUNTER-style RTC at 0x1E781000 (datasheet §24) — distinct from the BCD/CMOS
 * aspeed RTC of the AST2400/G4. Register block (from the faithful QEMU G3 model
 * hw/misc/aspeed_rtc_ast2050.c:19-25):
 *
 *   0x00  COUNTER  (RO live count: packed [31:24]=day [23:16]=hour
 *                   [15:8]=min [7:0]=sec — binary, not BCD)
 *   0x08  RELOAD   (RW: the value loaded into COUNTER on a RESTART)
 *   0x0C  CONTROL  ([0] = enable)
 *   0x10  RESTART  (W: write 0x5A → COUNTER := RELOAD  — "load")
 *   0x14  RESET    (W: write 0x99 → clear all registers)
 *
 * So a time is set by writing the packed value to RELOAD, pulsing RESTART with
 * the 0x5A magic to latch it into the live COUNTER, and enabling via CONTROL[0];
 * it is read back straight from COUNTER. The counter holds only the time-of-day
 * plus day-of-month (no month/year) — a hardware limitation of this counter-
 * style RTC — so get_time populates tm_sec/min/hour/mday and leaves the calendar
 * fields cleared.
 *
 * The QEMU G3 model is register-accurate for this load/read path but does NOT
 * yet auto-advance the counter at 1 Hz (a deferred behavioural add-on, per
 * aspeed_rtc_ast2050.c:6-8), so a set→load→get round-trip returns the value set
 * — which is exactly what the rtc_smoke sample validates.
 *
 * MMIO is reached at its physical address via the static identity MMU region
 * added in soc/aspeed/ast2050/soc.c (mirroring the uart5/vic/timer/wdt regions);
 * accesses are 32-bit (the QEMU model's valid.min/max_access_size = 4).
 */

#define DT_DRV_COMPAT aspeed_ast2050_rtc

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/rtc.h>
#include <zephyr/sys/sys_io.h>

/* Register offsets from the node reg base (hw/misc/aspeed_rtc_ast2050.c:19-25). */
#define RTC_G3_COUNTER 0x00U
#define RTC_G3_RELOAD  0x08U
#define RTC_G3_CONTROL 0x0CU
#define RTC_G3_RESTART 0x10U
#define RTC_G3_RESET   0x14U

#define RTC_G3_CTRL_ENABLE BIT(0)       /* CONTROL[0] */
#define RTC_G3_RESTART_MAGIC 0x5AU      /* RESTART: latch RELOAD → COUNTER */
#define RTC_G3_RESET_MAGIC   0x99U      /* RESET: clear all registers      */

struct rtc_aspeed_g3_config {
	mem_addr_t base;
};

static int rtc_aspeed_g3_set_time(const struct device *dev,
				  const struct rtc_time *timeptr)
{
	const struct rtc_aspeed_g3_config *cfg = dev->config;
	uint32_t counter;

	if (timeptr == NULL) {
		return -EINVAL;
	}
	/* Range-check the fields the counter can hold (binary, one byte each). */
	if (timeptr->tm_sec > 59 || timeptr->tm_min > 59 ||
	    timeptr->tm_hour > 23 || timeptr->tm_mday < 1 || timeptr->tm_mday > 31) {
		return -EINVAL;
	}

	counter = ((uint32_t)timeptr->tm_mday << 24) |
		  ((uint32_t)timeptr->tm_hour << 16) |
		  ((uint32_t)timeptr->tm_min << 8) |
		  ((uint32_t)timeptr->tm_sec);

	/* Program RELOAD, latch it into the live COUNTER with the RESTART magic,
	 * then enable the counter (CONTROL[0]).
	 */
	sys_write32(counter, cfg->base + RTC_G3_RELOAD);
	sys_write32(RTC_G3_RESTART_MAGIC, cfg->base + RTC_G3_RESTART);
	sys_write32(RTC_G3_CTRL_ENABLE, cfg->base + RTC_G3_CONTROL);

	return 0;
}

static int rtc_aspeed_g3_get_time(const struct device *dev,
				  struct rtc_time *timeptr)
{
	const struct rtc_aspeed_g3_config *cfg = dev->config;
	uint32_t counter;

	if (timeptr == NULL) {
		return -EINVAL;
	}

	counter = sys_read32(cfg->base + RTC_G3_COUNTER);

	timeptr->tm_sec = (int)(counter & 0xFFU);
	timeptr->tm_min = (int)((counter >> 8) & 0xFFU);
	timeptr->tm_hour = (int)((counter >> 16) & 0xFFU);
	timeptr->tm_mday = (int)((counter >> 24) & 0xFFU);

	/* The G3 counter carries no calendar (month/year); report them cleared. */
	timeptr->tm_mon = 0;
	timeptr->tm_year = 0;
	timeptr->tm_wday = -1;
	timeptr->tm_yday = -1;
	timeptr->tm_nsec = 0;

	return 0;
}

static const struct rtc_driver_api rtc_aspeed_g3_api = {
	.set_time = rtc_aspeed_g3_set_time,
	.get_time = rtc_aspeed_g3_get_time,
};

static int rtc_aspeed_g3_init(const struct device *dev)
{
	/* Nothing to program at init: the loader/QEMU leaves the block usable and
	 * set_time enables it. (No clock gate to release for the G3 RTC.)
	 */
	ARG_UNUSED(dev);
	return 0;
}

#define RTC_ASPEED_G3_INIT(inst)                                               \
	static const struct rtc_aspeed_g3_config rtc_aspeed_g3_config_##inst = { \
		.base = (mem_addr_t)DT_INST_REG_ADDR(inst),                    \
	};                                                                     \
	DEVICE_DT_INST_DEFINE(inst, rtc_aspeed_g3_init, NULL, NULL,             \
			      &rtc_aspeed_g3_config_##inst, POST_KERNEL,       \
			      CONFIG_RTC_INIT_PRIORITY, &rtc_aspeed_g3_api);

DT_INST_FOREACH_STATUS_OKAY(RTC_ASPEED_G3_INIT)
