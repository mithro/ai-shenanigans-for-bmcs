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
 * IMPORTANT silicon behaviour (datasheet §24.4 "Operation"): the RESTART load is
 * ASYNCHRONOUS — writing 0x5A does not update COUNTER instantly; the reload is
 * synchronised to the RTC clock and "needs about 0~3 seconds", during which the
 * restart-status bit CONTROL[5] reads 1 and then auto-clears to 0 when the load
 * has finished (datasheet: RTC10 "After write cycle finish, RTC0C[5] will auto
 * reset to zero"; §24.4.3 "Waiting Restart finished, wait until RTC0C.bit[5]=0").
 * So set_time MUST POLL CONTROL[5] until it clears before the COUNTER is valid —
 * otherwise a get_time immediately after reads the stale (power-on 0x0) counter.
 * This was found on real silicon: without the poll the counter read back 0x0.
 *
 * FAITHFULNESS NOTE: the QEMU G3 model (hw/misc/aspeed_rtc_ast2050.c) loads
 * COUNTER SYNCHRONOUSLY on the 0x5A write and does not model the 0~3 s busy /
 * CONTROL[5] status, so the pre-poll driver PASSED in QEMU but FAILED on silicon.
 * Making the QEMU model reproduce the async load + CONTROL[5] is tracked
 * separately so a future driver that skips the poll fails in QEMU too. The model
 * also does not yet auto-advance the counter at 1 Hz; on silicon the counter DOES
 * run once enabled, so a set→(poll)→get may legitimately read a few seconds past
 * the set value — the rtc_smoke sample allows for that.
 *
 * MMIO is reached at its physical address via the static identity MMU region
 * added in soc/aspeed_g3/ast2050/soc.c (mirroring the uart5/vic/timer/wdt regions);
 * accesses are 32-bit (the QEMU model's valid.min/max_access_size = 4).
 */

#define DT_DRV_COMPAT aspeed_ast2050_rtc

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/rtc.h>
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/sys/util.h>

/*
 * SCU (System Control Unit) — select the RTC clock source. SCU08[16] chooses the
 * RTC clock: 0 = 32.768 kHz source (datasheet default, Init 0xE3F00070 → bit16 =
 * 0), 1 = the internal 24 MHz oscillator. This board has NO external 32 kHz
 * crystal (datasheet §24: "not necessary to include an external 32 KHz clock
 * oscillator ... RTC isn't equipped with any power-cut layout"). SILICON RESULT:
 * with bit16 = 0 the RTC has no clock — the RESTART load never completes and the
 * counter reads back 0x0. Setting bit16 = 1 makes the RTC LOAD AND RUN on silicon
 * (proven: counter loads the set value and advances). SCU08 is a protected
 * register, so unlock SCU00 first.
 *
 * OPEN (honest) — NOT real-time yet: the RTC's fixed prescaler targets a 32.768
 * kHz input (÷32768 → 1 Hz), so feeding the 24 MHz source runs the second counter
 * FAST (the datasheet labels bit16 "for test only"); on silicon a set→get reads
 * tens of "seconds" of drift and the second field exceeds 59. The real-time 1 Hz
 * path is bit16 = 0, but the internally-derived 32.768 kHz is not running on this
 * board — root cause still open (the datasheet says no external crystal is needed,
 * so something else gates the internal 32 kHz; check the vendor Linux RTC/clk
 * init). Until resolved this driver picks bit16 = 1 so the block is functional
 * (set/load/read/run all verified on silicon); real-time accuracy is tracked
 * separately. See device-driver-program task "RTC set/latch ... faithfulness".
 */
#define SCU_G3_BASE         0x1E6E2000U
#define SCU_G3_PROT_KEY     0x00U
#define SCU_G3_CLK_SEL      0x08U       /* SCU08 Clock Selection Register */
#define SCU_G3_UNLOCK_MAGIC 0x1688A8A8U
#define SCU08_RTC_CLK_24M   BIT(16)     /* 1 = RTC clock from internal 24 MHz osc */

/* Register offsets from the node reg base (hw/misc/aspeed_rtc_ast2050.c:19-25). */
#define RTC_G3_COUNTER 0x00U
#define RTC_G3_RELOAD  0x08U
#define RTC_G3_CONTROL 0x0CU
#define RTC_G3_RESTART 0x10U
#define RTC_G3_RESET   0x14U

#define RTC_G3_CTRL_ENABLE  BIT(0)      /* CONTROL[0]: RTC enable          */
#define RTC_G3_CTRL_RESTART BIT(5)      /* CONTROL[5]: restart busy (1=loading, auto-clears) */
#define RTC_G3_RESTART_MAGIC 0x5AU      /* RESTART: latch RELOAD → COUNTER */
#define RTC_G3_RESET_MAGIC   0x99U      /* RESET: clear all registers      */

/*
 * Alarm. RTC04 (0x04) holds the alarm time-of-day. IMPORTANT: RTC04 is
 * FIELD-packed (datasheet §24: hour[16:12] / min[11:6] / sec[5:0]) — NOT
 * byte-packed like the COUNTER read path. This was PROVEN on real silicon
 * (2026-07-21, evidence d14-zephyr/28): programming the alarm hour byte-packed
 * at bits[23:16] read back as 0 and the alarm never fired, because hour=12 landed
 * in reserved bits above bit16; the field-packed hour[16:12] stayed 0. (The
 * COUNTER set/get could not expose this — sec values <60 fit both layouts with no
 * wrap; #186.) CONTROL[1:3] are the per-field alarm enables; the alarm fires (VIC
 * source 26) when every ENABLED field of RTC04 matches the live COUNTER's field.
 * Day-alarm (CONTROL[4]) is not exposed — RTC04 has no day field (field-packed is
 * 17 bits) and the counter's "day" is a free-running up-counter — so sec/min/hour
 * only.
 */
#define RTC_G3_ALARM          0x04U
/* RTC04 field-packed encode/decode. */
#define RTC_G3_ALARM_ENC(hour, min, sec)                                       \
	((((uint32_t)(hour) & 0x1fU) << 12) |                                  \
	 (((uint32_t)(min)  & 0x3fU) << 6)  |                                  \
	  ((uint32_t)(sec)  & 0x3fU))
#define RTC_G3_ALARM_SEC_OF(r)   ((int)((r) & 0x3fU))
#define RTC_G3_ALARM_MIN_OF(r)   ((int)(((r) >> 6) & 0x3fU))
#define RTC_G3_ALARM_HOUR_OF(r)  ((int)(((r) >> 12) & 0x1fU))
#define RTC_G3_CTRL_ALARM_SEC  BIT(1)
#define RTC_G3_CTRL_ALARM_MIN  BIT(2)
#define RTC_G3_CTRL_ALARM_HOUR BIT(3)
#define RTC_G3_CTRL_ALARM_MASK (RTC_G3_CTRL_ALARM_SEC | RTC_G3_CTRL_ALARM_MIN | \
				RTC_G3_CTRL_ALARM_HOUR)

/*
 * VIC source 26 = RTC alarm (memory map §10; edge/falling in the RE'd G3 VIC
 * map, soc/aspeed_g3/ast2050/vic.c). Hardcoded like the GPIO driver's source
 * 20 — the G3 VIC is not modelled as a DT interrupt-controller, so IRQs are
 * connected by number. The framework's z_soc_irq_eoi() clears the latched edge,
 * so the ISR only services the alarm.
 */
#define RTC_G3_IRQ            26
#define RTC_G3_IRQ_PRIO       0
#define RTC_G3_ALARM_ID       0         /* single hardware alarm */
#define RTC_G3_ALARM_FIELDS   (RTC_ALARM_TIME_MASK_SECOND | \
			       RTC_ALARM_TIME_MASK_MINUTE | \
			       RTC_ALARM_TIME_MASK_HOUR)

/*
 * Bound on the CONTROL[5] restart-busy poll. The load "needs about 0~3 seconds"
 * (datasheet §24.4.3), synchronised to the RTC clock; the loop exits the instant
 * hardware clears the bit, so this bound only caps the pathological "never
 * clears" case (e.g. the RTC clock not running) before we fail loud with
 * -ETIMEDOUT. Sized generously to cover several seconds of MMIO polling.
 */
#define RTC_G3_RESTART_POLL 0x2000000U

struct rtc_aspeed_g3_config {
	mem_addr_t base;
};

struct rtc_aspeed_g3_data {
	/*
	 * Serialises the CONTROL read-modify-write shared between the alarm ISR
	 * (which the Zephyr contract does NOT auto-disable — see the ISR) and
	 * process-context alarm ops, and guards the callback/pending state. A
	 * spinlock (not a mutex): the critical sections are a couple of MMIO
	 * accesses, and one holder is the hard-IRQ ISR.
	 */
	struct k_spinlock lock;
#if defined(CONFIG_RTC_ALARM)
	rtc_alarm_callback alarm_cb;
	void *alarm_user_data;
	bool alarm_pending;
#endif
};

#if defined(CONFIG_RTC_ALARM)
/* Single RTC instance; the ISR recovers the device from this (mirrors the GPIO
 * driver's shared-ISR device registry). Set in init before irq_enable().
 */
static const struct device *rtc_g3_isr_dev;
#endif

static int rtc_aspeed_g3_set_time(const struct device *dev,
				  const struct rtc_time *timeptr)
{
	const struct rtc_aspeed_g3_config *cfg = dev->config;
	struct rtc_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key;
	uint32_t counter, ctrl;

	if (timeptr == NULL) {
		return -EINVAL;
	}
	/*
	 * Range-check the fields the counter can hold (binary, one byte each).
	 * struct rtc_time fields are signed (struct tm convention), so check the
	 * LOWER bounds too: a negative field cast to uint32_t below would sign-
	 * extend 1-bits up into the adjacent byte and silently corrupt the day
	 * (fail-loud: reject bad input rather than write a wrong time).
	 */
	if (timeptr->tm_sec < 0 || timeptr->tm_sec > 59 ||
	    timeptr->tm_min < 0 || timeptr->tm_min > 59 ||
	    timeptr->tm_hour < 0 || timeptr->tm_hour > 23 ||
	    timeptr->tm_mday < 1 || timeptr->tm_mday > 31) {
		return -EINVAL;
	}

	counter = ((uint32_t)timeptr->tm_mday << 24) |
		  ((uint32_t)timeptr->tm_hour << 16) |
		  ((uint32_t)timeptr->tm_min << 8) |
		  ((uint32_t)timeptr->tm_sec);

	/* Program RELOAD, pulse RESTART to latch it into the live COUNTER, enable
	 * the counter (CONTROL[0]), then WAIT for the asynchronous load to finish
	 * (CONTROL[5] auto-clears) — see the file header. Ordering follows the
	 * datasheet §24.4.3 initial sequence (reload → restart → enable → wait).
	 */
	sys_write32(counter, cfg->base + RTC_G3_RELOAD);
	sys_write32(RTC_G3_RESTART_MAGIC, cfg->base + RTC_G3_RESTART);
	/*
	 * RMW CONTROL: set ENABLE[0], preserve everything else — crucially the
	 * alarm-enable bits [1:4], so setting the time does NOT silently disarm an
	 * armed alarm (the Zephyr contract keeps an alarm armed until disabled via
	 * rtc_alarm_set_time). Never write 1 back to the RESTART status bit[5].
	 * Under data->lock: CONTROL is shared with the alarm ISR / alarm_set_time.
	 * (With no alarm armed the result is exactly ENABLE, as before.) The poll
	 * below stays outside the lock — it only reads.
	 */
	key = k_spin_lock(&data->lock);
	ctrl = sys_read32(cfg->base + RTC_G3_CONTROL);
	ctrl = (ctrl & ~RTC_G3_CTRL_RESTART) | RTC_G3_CTRL_ENABLE;
	sys_write32(ctrl, cfg->base + RTC_G3_CONTROL);
	k_spin_unlock(&data->lock, key);

	for (uint32_t i = 0; i < RTC_G3_RESTART_POLL; i++) {
		if ((sys_read32(cfg->base + RTC_G3_CONTROL) &
		     RTC_G3_CTRL_RESTART) == 0U) {
			return 0; /* reload latched into COUNTER */
		}
	}
	return -ETIMEDOUT; /* restart never completed (RTC clock not running?) */
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

#if defined(CONFIG_RTC_ALARM)

/*
 * Alarm ISR (VIC source 26). Per the Zephyr RTC contract the alarm stays ARMED
 * (recurring) until disabled via rtc_alarm_set_time(mask=0) — so, unlike the
 * Linux one-shot handler, we do NOT clear the CONTROL alarm-enable bits here.
 * We just deliver the event; the framework's z_soc_irq_eoi() clears the latched
 * VIC edge, and the next COUNTER==RTC04 match re-latches a fresh edge.
 */
static void rtc_aspeed_g3_isr(const void *unused)
{
	const struct device *dev = rtc_g3_isr_dev;
	struct rtc_aspeed_g3_data *data = dev->data;
	rtc_alarm_callback cb;
	void *user_data;
	k_spinlock_key_t key;

	ARG_UNUSED(unused);

	key = k_spin_lock(&data->lock);
	cb = data->alarm_cb;
	user_data = data->alarm_user_data;
	if (cb == NULL) {
		/* No callback: latch pending for rtc_alarm_is_pending(). */
		data->alarm_pending = true;
	}
	k_spin_unlock(&data->lock, key);

	/* Contract: invoking the callback clears the pending status. Call it
	 * OUTSIDE the lock (it may re-enter the driver, e.g. to disarm).
	 */
	if (cb != NULL) {
		cb(dev, RTC_G3_ALARM_ID, user_data);
	}
}

static int rtc_aspeed_g3_alarm_get_supported_fields(const struct device *dev,
						    uint16_t id, uint16_t *mask)
{
	ARG_UNUSED(dev);

	if (id != RTC_G3_ALARM_ID || mask == NULL) {
		return -EINVAL;
	}
	*mask = RTC_G3_ALARM_FIELDS;
	return 0;
}

static int rtc_aspeed_g3_alarm_set_time(const struct device *dev, uint16_t id,
					uint16_t mask, const struct rtc_time *timeptr)
{
	const struct rtc_aspeed_g3_config *cfg = dev->config;
	struct rtc_aspeed_g3_data *data = dev->data;
	uint32_t reg = 0U, ctrl_bits = 0U, ctrl;
	k_spinlock_key_t key;

	if (id != RTC_G3_ALARM_ID) {
		return -EINVAL;
	}
	if ((mask & ~(uint16_t)RTC_G3_ALARM_FIELDS) != 0U) {
		return -EINVAL; /* unsupported field requested */
	}
	if (mask != 0U && timeptr == NULL) {
		return -EINVAL;
	}

	/* Build RTC04 + the CONTROL enable bits from ONLY the enabled fields
	 * (the others are don't-care in hardware). Range-check the enabled ones.
	 */
	if (mask & RTC_ALARM_TIME_MASK_SECOND) {
		if (timeptr->tm_sec < 0 || timeptr->tm_sec > 59) {
			return -EINVAL;
		}
		reg |= RTC_G3_ALARM_ENC(0, 0, timeptr->tm_sec);
		ctrl_bits |= RTC_G3_CTRL_ALARM_SEC;
	}
	if (mask & RTC_ALARM_TIME_MASK_MINUTE) {
		if (timeptr->tm_min < 0 || timeptr->tm_min > 59) {
			return -EINVAL;
		}
		reg |= RTC_G3_ALARM_ENC(0, timeptr->tm_min, 0);
		ctrl_bits |= RTC_G3_CTRL_ALARM_MIN;
	}
	if (mask & RTC_ALARM_TIME_MASK_HOUR) {
		if (timeptr->tm_hour < 0 || timeptr->tm_hour > 23) {
			return -EINVAL;
		}
		reg |= RTC_G3_ALARM_ENC(timeptr->tm_hour, 0, 0);
		ctrl_bits |= RTC_G3_CTRL_ALARM_HOUR;
	}

	key = k_spin_lock(&data->lock);
	if (mask != 0U) {
		sys_write32(reg, cfg->base + RTC_G3_ALARM);
	}
	/* RMW CONTROL: replace the alarm-enable bits, preserve everything else
	 * (notably ENABLE[0]); never write 1 back to the RESTART status bit[5].
	 */
	ctrl = sys_read32(cfg->base + RTC_G3_CONTROL);
	ctrl = (ctrl & ~(RTC_G3_CTRL_ALARM_MASK | RTC_G3_CTRL_RESTART)) | ctrl_bits;
	sys_write32(ctrl, cfg->base + RTC_G3_CONTROL);
	data->alarm_pending = false; /* (dis)arming clears any stale pending */
	k_spin_unlock(&data->lock, key);

	return 0;
}

static int rtc_aspeed_g3_alarm_get_time(const struct device *dev, uint16_t id,
					uint16_t *mask, struct rtc_time *timeptr)
{
	const struct rtc_aspeed_g3_config *cfg = dev->config;
	uint32_t reg, ctrl;

	if (id != RTC_G3_ALARM_ID || mask == NULL || timeptr == NULL) {
		return -EINVAL;
	}

	reg = sys_read32(cfg->base + RTC_G3_ALARM);
	ctrl = sys_read32(cfg->base + RTC_G3_CONTROL);

	*timeptr = (struct rtc_time){0};
	timeptr->tm_sec = RTC_G3_ALARM_SEC_OF(reg);   /* RTC04 field-packed */
	timeptr->tm_min = RTC_G3_ALARM_MIN_OF(reg);
	timeptr->tm_hour = RTC_G3_ALARM_HOUR_OF(reg);
	timeptr->tm_wday = -1;
	timeptr->tm_yday = -1;

	*mask = 0U;
	if (ctrl & RTC_G3_CTRL_ALARM_SEC) {
		*mask |= RTC_ALARM_TIME_MASK_SECOND;
	}
	if (ctrl & RTC_G3_CTRL_ALARM_MIN) {
		*mask |= RTC_ALARM_TIME_MASK_MINUTE;
	}
	if (ctrl & RTC_G3_CTRL_ALARM_HOUR) {
		*mask |= RTC_ALARM_TIME_MASK_HOUR;
	}
	return 0;
}

static int rtc_aspeed_g3_alarm_is_pending(const struct device *dev, uint16_t id)
{
	struct rtc_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key;
	bool pending;

	if (id != RTC_G3_ALARM_ID) {
		return -EINVAL;
	}
	key = k_spin_lock(&data->lock);
	pending = data->alarm_pending;
	data->alarm_pending = false; /* is_pending clears the status */
	k_spin_unlock(&data->lock, key);

	return pending ? 1 : 0;
}

static int rtc_aspeed_g3_alarm_set_callback(const struct device *dev, uint16_t id,
					    rtc_alarm_callback callback, void *user_data)
{
	struct rtc_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key;

	if (id != RTC_G3_ALARM_ID) {
		return -EINVAL;
	}
	key = k_spin_lock(&data->lock);
	data->alarm_cb = callback;
	data->alarm_user_data = user_data;
	k_spin_unlock(&data->lock, key);

	return 0;
}

#endif /* CONFIG_RTC_ALARM */

static const struct rtc_driver_api rtc_aspeed_g3_api = {
	.set_time = rtc_aspeed_g3_set_time,
	.get_time = rtc_aspeed_g3_get_time,
#if defined(CONFIG_RTC_ALARM)
	.alarm_get_supported_fields = rtc_aspeed_g3_alarm_get_supported_fields,
	.alarm_set_time = rtc_aspeed_g3_alarm_set_time,
	.alarm_get_time = rtc_aspeed_g3_alarm_get_time,
	.alarm_is_pending = rtc_aspeed_g3_alarm_is_pending,
	.alarm_set_callback = rtc_aspeed_g3_alarm_set_callback,
#endif
};

static int rtc_aspeed_g3_init(const struct device *dev)
{
	uint32_t clk;

	/* Point the RTC at the internal 24 MHz-derived clock (this board has no
	 * external 32 kHz crystal — see the SCU08 comment above). Idempotent; unlock
	 * the SCU first (harmless if already unlocked, e.g. the QEMU boot path).
	 */
	sys_write32(SCU_G3_UNLOCK_MAGIC, SCU_G3_BASE + SCU_G3_PROT_KEY);
	clk = sys_read32(SCU_G3_BASE + SCU_G3_CLK_SEL);
	sys_write32(clk | SCU08_RTC_CLK_24M, SCU_G3_BASE + SCU_G3_CLK_SEL);

#if defined(CONFIG_RTC_ALARM)
	/* Connect + unmask the VIC-26 alarm line. The alarm only asserts once a
	 * CONTROL[1:3] enable is set (alarm_set_time), so enabling it here is inert
	 * until an alarm is armed. z_soc_irq_enable() clears any stale latched edge
	 * for this source before unmasking.
	 */
	rtc_g3_isr_dev = dev;
	IRQ_CONNECT(RTC_G3_IRQ, RTC_G3_IRQ_PRIO, rtc_aspeed_g3_isr, NULL, 0);
	irq_enable(RTC_G3_IRQ);
#else
	ARG_UNUSED(dev);
#endif

	return 0;
}

#define RTC_ASPEED_G3_INIT(inst)                                               \
	static const struct rtc_aspeed_g3_config rtc_aspeed_g3_config_##inst = { \
		.base = (mem_addr_t)DT_INST_REG_ADDR(inst),                    \
	};                                                                     \
	static struct rtc_aspeed_g3_data rtc_aspeed_g3_data_##inst;             \
	DEVICE_DT_INST_DEFINE(inst, rtc_aspeed_g3_init, NULL,                   \
			      &rtc_aspeed_g3_data_##inst,                      \
			      &rtc_aspeed_g3_config_##inst, POST_KERNEL,       \
			      CONFIG_RTC_INIT_PRIORITY, &rtc_aspeed_g3_api);

DT_INST_FOREACH_STATUS_OKAY(RTC_ASPEED_G3_INIT)
