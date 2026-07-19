/*
 * AMD SB-TSI (Side-Band Temperature Sensor Interface) CPU thermal sensor driver
 * for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal I2C-CLIENT sensor driver for the AMD processor's SB-TSI thermal
 * interface as reached by the ASUS KGPE-D16 / AST2050 BMC. It runs on top of the
 * AST2050 (G3) I2C master (drivers/i2c/i2c_aspeed_g3.c) purely through the Zephyr
 * I2C API against the bus device named by the devicetree parent (i2c-parent); it
 * does NO MMIO of its own. On the KGPE-D16 the two CPU sockets present one SB-TSI
 * each on I2C engine 3 (DT node i2c3, register block 0x1E78A100): 0x4C = socket
 * P0, 0x4D = socket P1 (hw/arm/aspeed.c kgpe_d16_bmc_i2c_init lines 619-638).
 *
 * REGISTER MODEL — all register/encoding facts below are read from the QEMU
 * device model this driver is validated against,
 * asus-kgpe-d16-firmware/qemu-firmware/qemu/qemu/hw/sensor/sbtsi.c (cited by line
 * number), and corroborated by the mainline Linux driver
 * drivers/hwmon/sbtsi_temp.c:
 *
 *   Registers (sbtsi.c lines 37-45) — TEMP_INT 0x01 (RO, integer degrees C),
 *   STATUS 0x02, CONFIG 0x03 (RO, bit5 = read order), TEMP_DEC 0x10 (fraction),
 *   plus RW high/low limit registers we do not use.
 *
 *   Encoding — Temperature = TEMP_INT*1000 + (TEMP_DEC>>5)*125 millidegrees C
 *   (sbtsi.c header lines 18-19, realised by sbtsi_update_temp() lines 69-71:
 *   `regs[TEMP_INT] = t/1000; regs[TEMP_DEC] = ((t%1000)/125) << 5`). TEMP_DEC
 *   bits[7:5] hold the fraction in 0.125 C steps (SBTSI_TEMP_DEC_SHIFT = 5,
 *   sbtsi.c lines 42 / 47-49). SB-TSI is an *unsigned* AMD Tctl offset,
 *   0..255.875 C, so TEMP_INT is read as a plain uint8 — it is NOT sign-extended
 *   like the W83795's signed diode byte.
 *
 *   Read order — CONFIG (0x03) bit5 says whether the integer or the decimal
 *   register must be read first for an atomic reading: reading the leading
 *   register latches the trailing one on real silicon (Linux sbtsi_temp.c
 *   sbtsi_read() lines 88-99). The QEMU model does not latch (sbtsi_receive_byte()
 *   lines 116-124 just returns regs[pointer]), so either order returns the seeded
 *   value there; we still honour CONFIG to stay faithful to hardware. The model
 *   resets CONFIG to 0x00 = int-first (sbtsi.c line 157).
 *
 * Exposed channel: SENSOR_CHAN_DIE_TEMP (CPU die temperature).
 */

#define DT_DRV_COMPAT amd_sbtsi

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

/* Register map (subset used here) — matches QEMU hw/sensor/sbtsi.c lines 37-45. */
#define SBTSI_REG_TEMP_INT 0x01U /* RO: integer CPU temperature, degrees C   */
#define SBTSI_REG_CONFIG   0x03U /* RO: bit5 = read order (int/dec first)     */
#define SBTSI_REG_TEMP_DEC 0x10U /* fraction in bits[7:5], 0.125 degC steps   */

/* CONFIG bit5: 0 = read TEMP_INT first, 1 = read TEMP_DEC first (sbtsi.c L39). */
#define SBTSI_CONFIG_READ_ORDER BIT(5)
/* Fraction lives in TEMP_DEC[7:5]; each step is 0.125 degC (sbtsi.c L47-49). */
#define SBTSI_TEMP_DEC_SHIFT 5

struct sbtsi_config {
	struct i2c_dt_spec i2c;
};

struct sbtsi_data {
	uint8_t temp_int; /* whole degrees, unsigned 0..255 (AMD Tctl offset) */
	uint8_t temp_dec; /* raw TEMP_DEC; fraction is bits[7:5]              */
};

static int sbtsi_sample_fetch(const struct device *dev, enum sensor_channel chan)
{
	const struct sbtsi_config *cfg = dev->config;
	struct sbtsi_data *data = dev->data;
	uint8_t config;
	int ret;

	if (chan != SENSOR_CHAN_ALL && chan != SENSOR_CHAN_DIE_TEMP) {
		return -ENOTSUP;
	}

	/*
	 * Honour the CONFIG read-order bit exactly like Linux sbtsi_temp.c: on
	 * real silicon reading the leading register latches the trailing one, so
	 * the two bytes must be read in the order the chip dictates. (The QEMU
	 * model does not latch, so either order returns the seeded value there.)
	 */
	ret = i2c_reg_read_byte_dt(&cfg->i2c, SBTSI_REG_CONFIG, &config);
	if (ret != 0) {
		return ret;
	}

	if (config & SBTSI_CONFIG_READ_ORDER) {
		ret = i2c_reg_read_byte_dt(&cfg->i2c, SBTSI_REG_TEMP_DEC,
					   &data->temp_dec);
		if (ret != 0) {
			return ret;
		}
		ret = i2c_reg_read_byte_dt(&cfg->i2c, SBTSI_REG_TEMP_INT,
					   &data->temp_int);
		if (ret != 0) {
			return ret;
		}
	} else {
		ret = i2c_reg_read_byte_dt(&cfg->i2c, SBTSI_REG_TEMP_INT,
					   &data->temp_int);
		if (ret != 0) {
			return ret;
		}
		ret = i2c_reg_read_byte_dt(&cfg->i2c, SBTSI_REG_TEMP_DEC,
					   &data->temp_dec);
		if (ret != 0) {
			return ret;
		}
	}

	return 0;
}

static int sbtsi_channel_get(const struct device *dev, enum sensor_channel chan,
			     struct sensor_value *val)
{
	struct sbtsi_data *data = dev->data;

	if (chan != SENSOR_CHAN_DIE_TEMP) {
		return -ENOTSUP;
	}

	/*
	 * whole degrees + TEMP_DEC[7:5] eighth-degrees (0.125 degC = 125000
	 * micro-degrees). SB-TSI encodes an *unsigned* Tctl offset (0..255.875
	 * degC), so temp_int is used as a uint8 — NOT sign-extended. Even so,
	 * build the reading in signed micro-degrees and split it canonically so
	 * val2 always carries the SAME SIGN as val1 (the Zephyr sensor_value
	 * contract), matching the W83795 gate-b fix. temp_int <= 255 and the
	 * fraction <= 7, so the product fits in int32 with no overflow
	 * (max 255875000).
	 */
	int32_t micro = (int32_t)data->temp_int * 1000000 +
			(int32_t)(data->temp_dec >> SBTSI_TEMP_DEC_SHIFT) * 125000;

	val->val1 = micro / 1000000;
	val->val2 = micro % 1000000;
	return 0;
}

static const struct sensor_driver_api sbtsi_api = {
	.sample_fetch = sbtsi_sample_fetch,
	.channel_get = sbtsi_channel_get,
};

static int sbtsi_init(const struct device *dev)
{
	const struct sbtsi_config *cfg = dev->config;

	if (!i2c_is_ready_dt(&cfg->i2c)) {
		return -ENODEV; /* parent I2C bus not ready */
	}
	return 0;
}

#define SBTSI_INIT(inst)                                                       \
	static struct sbtsi_data sbtsi_data_##inst;                            \
	static const struct sbtsi_config sbtsi_config_##inst = {               \
		.i2c = I2C_DT_SPEC_INST_GET(inst),                             \
	};                                                                     \
	SENSOR_DEVICE_DT_INST_DEFINE(inst, sbtsi_init, NULL,                   \
				     &sbtsi_data_##inst,                       \
				     &sbtsi_config_##inst, POST_KERNEL,        \
				     CONFIG_SENSOR_INIT_PRIORITY, &sbtsi_api);

DT_INST_FOREACH_STATUS_OKAY(SBTSI_INIT)
