/*
 * Nuvoton/Winbond W83795G hardware-monitor sensor driver for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal I2C-CLIENT sensor driver for the W83795G "H/W monitoring IC" on the
 * ASUS KGPE-D16 / AST2050 BMC. It runs on top of the AST2050 (G3) I2C master
 * (drivers/i2c/i2c_aspeed_g3.c) purely through the Zephyr I2C API against the
 * bus device named by the devicetree parent (i2c-parent); it does NO MMIO of
 * its own. The chip is at 7-bit address 0x2F on I2C engine 1 (DT node i2c1,
 * register block 0x1E78A080); the same address a raw i2c_write_read already
 * proved reachable in samples/i2c_smoke.
 *
 * REGISTER MODEL — all register/bank/formula facts below are read from the QEMU
 * device model this driver is validated against,
 * asus-kgpe-d16-firmware/qemu-firmware/qemu/qemu/hw/sensor/w83795.c (cited by
 * line number), and corroborated by the mainline Linux driver
 * drivers/hwmon/w83795.c:
 *
 *   Bank switching — register 0x00 is the bank-select register; its low 3 bits
 *   pick the active bank. The measurement windows all live in BANK 0. QEMU
 *   w83795_do_write() lines 266-268: `if (reg == W83795_REG_BANKSEL) { s->bank
 *   = data; ... }`; reads only decode the measurement window when
 *   `bank == 0` (w83795_do_read() line 219). We therefore write 0x00 -> reg
 *   0x00 at the start of every fetch so a prior bank switch can't misdirect us.
 *
 *   Chip ID — register 0xFE returns a constant 0x79 regardless of bank, QEMU
 *   w83795_do_read() lines 207-208 (`case W83795_REG_CHIPID: return 0x79;`);
 *   this is the real chip's ID that Linux w83795_detect() checks.
 *
 *   Shared VRLSB latch — register 0x3C. On a measurement-register read the model
 *   latches that register's low bits into VRLSB (w83795_do_read() lines 240-242:
 *   `s->vrlsb = s->lsb0[reg]; return s->meas0[reg];`), and a subsequent read of
 *   0x3C returns them (lines 235-236). So a full reading is ALWAYS two ordered
 *   single-byte reads: the measurement high byte, then 0x3C, with NOTHING in
 *   between (any other measurement read would re-latch VRLSB). 0x3C is not
 *   itself a measurement register, so reading it does not disturb the latch.
 *
 *   FAN — fan1 tach high byte is at 0x2E (W83795_FAN_FIRST, fan index 0), QEMU
 *   w83795_load_defaults() line 184 seeds it via w83795_set_fan(s, 0x2E, 2641).
 *   The 12-bit tach count is split high8 = count[11:4] in the fan register and
 *   low4 = count[3:0] in VRLSB[7:4] (w83795_set_fan() lines 111-119:
 *   `cnt = 1350000/rpm; meas0 = (cnt>>4)&0xff; lsb0 = (cnt&0xf)<<4`). Rebuild:
 *       count = (high << 4) | (vrlsb >> 4)
 *   and the count->RPM formula is the inverse of that seeding:
 *       rpm   = 1350000 / count
 *   (count 0x000/0xFFF == stopped/unpopulated -> report 0 RPM, matching the
 *   model's `cnt = 0xfff` sentinel at lines 114-116).
 *
 *   TEMPERATURE — the CPU thermal-diode (temp0) high byte is at 0x21, QEMU
 *   w83795_load_defaults() line 177 seeds it via w83795_set_temp(s, 0x21,
 *   50500) = 50.5 degC. The value is a signed whole-degree byte plus
 *   quarter-degrees in VRLSB[7:6] (w83795_set_temp() lines 122-132:
 *   `meas0 = (int8_t)whole; lsb0 = (quarters & 0x3) << 6`). Rebuild:
 *       milli_degC = whole*1000 + (vrlsb >> 6)*250
 *   (whole is signed; the quarter term is a small positive addend, matching the
 *   model's own encoding — accurate for the seeded positive readings).
 *
 * Exposed channels: SENSOR_CHAN_RPM (fan1) and SENSOR_CHAN_DIE_TEMP (temp0).
 */

#define DT_DRV_COMPAT nuvoton_w83795

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

/* Register map (subset used here) — matches QEMU hw/sensor/w83795.c. */
#define W83795_REG_BANKSEL 0x00U /* bank select; low 3 bits pick the bank */
#define W83795_REG_TEMP0   0x21U /* CPU thermal-diode high byte (bank 0)  */
#define W83795_REG_FAN1    0x2EU /* fan1 tach high byte (bank 0)          */
#define W83795_REG_VRLSB   0x3CU /* shared measurement-LSB latch (bank 0) */
#define W83795_REG_CHIPID  0xFEU /* constant 0x79, bank-independent       */

#define W83795_BANK0       0x00U
#define W83795_CHIPID_VAL  0x79U

/* Tach count is 12-bit; stopped/unpopulated fans read this sentinel. */
#define W83795_FAN_COUNT_MAX 0xFFFU
/* count -> RPM: rpm = 1350000 / count (w83795.c w83795_set_fan(), line 113). */
#define W83795_FAN_DIVIDEND  1350000U

struct w83795_config {
	struct i2c_dt_spec i2c;
};

struct w83795_data {
	/*
	 * Serialises sample_fetch's multi-transaction measurement-reg -> VRLSB(0x3C)
	 * shared-latch read PAIRS (and the fan1/temp0 cache) against a concurrent
	 * fetch/get from another thread: any interleaved measurement read re-latches
	 * VRLSB, so an unlocked interleave silently pairs one field's high byte with
	 * another field's LSB.
	 */
	struct k_mutex lock;
	uint16_t fan1_count;   /* 12-bit tach count for fan1 (0 == invalid)  */
	int8_t temp0_whole;    /* temp0 whole degrees (signed)               */
	uint8_t temp0_quarter; /* temp0 quarter-degrees, 0..3 (VRLSB[7:6])   */
	uint8_t chipid;        /* last-read chip ID (expect 0x79)            */
};

/*
 * Read one measurement register's high byte, then its low bits from the shared
 * VRLSB register (0x3C). These MUST be consecutive single-byte reads with no
 * other measurement read in between (see the file header): the model latches
 * VRLSB on the high-byte read and returns it unchanged on the 0x3C read.
 */
static int w83795_read_meas(const struct i2c_dt_spec *i2c, uint8_t reg,
			    uint8_t *high, uint8_t *vrlsb)
{
	int ret = i2c_reg_read_byte_dt(i2c, reg, high);

	if (ret != 0) {
		return ret;
	}
	return i2c_reg_read_byte_dt(i2c, W83795_REG_VRLSB, vrlsb);
}

static int w83795_sample_fetch(const struct device *dev, enum sensor_channel chan)
{
	const struct w83795_config *cfg = dev->config;
	struct w83795_data *data = dev->data;
	uint8_t high, vrlsb;
	int ret;

	if (chan != SENSOR_CHAN_ALL && chan != SENSOR_CHAN_RPM &&
	    chan != SENSOR_CHAN_DIE_TEMP) {
		return -ENOTSUP;
	}

	/* Hold the lock across the WHOLE fetch so the measurement-reg -> VRLSB
	 * latched pairs (and the fan1/temp0 cache updates) cannot interleave with
	 * another thread's fetch/get and pick up a re-latched VRLSB. */
	k_mutex_lock(&data->lock, K_FOREVER);

	/* All measurement registers live in bank 0; select it explicitly so a
	 * prior bank switch cannot leave us reading the wrong window.
	 */
	ret = i2c_reg_write_byte_dt(&cfg->i2c, W83795_REG_BANKSEL, W83795_BANK0);
	if (ret != 0) {
		goto out;
	}

	/* Chip ID is bank-independent; cheap sanity value for the smoke test. */
	ret = i2c_reg_read_byte_dt(&cfg->i2c, W83795_REG_CHIPID, &data->chipid);
	if (ret != 0) {
		goto out;
	}

	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_RPM) {
		ret = w83795_read_meas(&cfg->i2c, W83795_REG_FAN1, &high, &vrlsb);
		if (ret != 0) {
			goto out;
		}
		/* 12-bit tach count: high[7:0] << 4 | VRLSB[7:4]. */
		data->fan1_count = ((uint16_t)high << 4) | (vrlsb >> 4);
	}

	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_DIE_TEMP) {
		ret = w83795_read_meas(&cfg->i2c, W83795_REG_TEMP0, &high, &vrlsb);
		if (ret != 0) {
			goto out;
		}
		data->temp0_whole = (int8_t)high;
		data->temp0_quarter = vrlsb >> 6; /* VRLSB[7:6] = quarter degrees */
	}
out:
	k_mutex_unlock(&data->lock);
	return ret;
}

static int w83795_channel_get(const struct device *dev, enum sensor_channel chan,
			      struct sensor_value *val)
{
	struct w83795_data *data = dev->data;
	uint16_t cnt;
	int8_t temp0_whole;
	uint8_t temp0_quarter;

	/* Snapshot the cache under the lock so a concurrent sample_fetch cannot
	 * tear a fan1/temp0 field between our reads of it. */
	k_mutex_lock(&data->lock, K_FOREVER);
	cnt = data->fan1_count;
	temp0_whole = data->temp0_whole;
	temp0_quarter = data->temp0_quarter;
	k_mutex_unlock(&data->lock);

	switch (chan) {
	case SENSOR_CHAN_RPM: {
		uint32_t rpm = (cnt == 0U || cnt >= W83795_FAN_COUNT_MAX)
				       ? 0U
				       : W83795_FAN_DIVIDEND / cnt;

		val->val1 = (int32_t)rpm;
		val->val2 = 0;
		return 0;
	}
	case SENSOR_CHAN_DIE_TEMP: {
		/*
		 * whole degrees + quarter-degrees (0.25 degC = 250000 micro).
		 * Build the value in signed micro-degrees and split canonically so
		 * val2 carries the SAME SIGN as val1 (the Zephyr sensor_value
		 * contract: -0.5 degC is {val1=0, val2=-500000}, not {-1, +500000}).
		 * temp0_whole is int8, temp0_quarter is 0..3, so the product fits in
		 * int32 with no overflow.
		 */
		int32_t micro = (int32_t)temp0_whole * 1000000 +
				(int32_t)temp0_quarter * 250000;

		val->val1 = micro / 1000000;
		val->val2 = micro % 1000000;
		return 0;
	}
	default:
		return -ENOTSUP;
	}
}

static const struct sensor_driver_api w83795_api = {
	.sample_fetch = w83795_sample_fetch,
	.channel_get = w83795_channel_get,
};

static int w83795_init(const struct device *dev)
{
	const struct w83795_config *cfg = dev->config;
	struct w83795_data *data = dev->data;

	if (!i2c_is_ready_dt(&cfg->i2c)) {
		return -ENODEV; /* parent I2C bus not ready */
	}
	k_mutex_init(&data->lock);
	return 0;
}

#define W83795_INIT(inst)                                                      \
	static struct w83795_data w83795_data_##inst;                          \
	static const struct w83795_config w83795_config_##inst = {             \
		.i2c = I2C_DT_SPEC_INST_GET(inst),                             \
	};                                                                     \
	SENSOR_DEVICE_DT_INST_DEFINE(inst, w83795_init, NULL,                  \
				     &w83795_data_##inst,                      \
				     &w83795_config_##inst, POST_KERNEL,       \
				     CONFIG_SENSOR_INIT_PRIORITY, &w83795_api);

DT_INST_FOREACH_STATUS_OKAY(W83795_INIT)
