/*
 * AST2050 (G3) W83795G FAN-CONTROL smoke test — DEVICE-MATRIX row 16 (write side).
 * SPDX-License-Identifier: Apache-2.0
 *
 * The read side (fan RPM / temp) is covered by w83795_smoke. This exercises the
 * BMC's fan-DRIVING capability (schematic §10.2 "write FANCTL1-8 PWM"): it writes
 * the PWM-output duty for fan1 (bank 2, reg 0x10 = PWM1) over raw I2C and then
 * reads fan1's tach back through the w83795 sensor driver, checking the RPM
 * TRACKS the duty. In the QEMU model (hw/sensor/w83795.c) a PWM-duty write drives
 * the matching fan tach (RPM = duty * 27); a higher duty must yield a higher RPM
 * and a lower duty a lower RPM.
 *
 * Target: W83795G @0x2F on I2C engine 1 (i2c1). Raw writes go through the i2c1
 * controller; RPM reads go through the sensor driver (SENSOR_CHAN_RPM = fan1).
 * On real silicon the write reaches the chip's PWM output; whether the physical
 * fan1 tach then tracks depends on the live fan + SmartFan config, so this
 * validates ZQ (QEMU); silicon fan-response is a live-hardware follow-on.
 *
 * W83795G paging: reg 0x00 = BANKSEL; PWM1..8 are bank 2 regs 0x10..0x17; fan
 * tachs are bank 0. We select bank 2, write the duty, restore bank 0 (so the
 * sensor driver's next fetch reads the fan cleanly), then fetch + read RPM.
 */

#include <stdbool.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define I2C_NODE      DT_NODELABEL(i2c1)
#define W83795_NODE   DT_NODELABEL(w83795)
#define W83795_ADDR   0x2F
#define W83795_BANKSEL 0x00
#define W83795_PWM1    0x10   /* bank 2 */

BUILD_ASSERT(DT_NODE_HAS_STATUS(I2C_NODE, okay), "i2c1 must be enabled");
BUILD_ASSERT(DT_NODE_HAS_STATUS(W83795_NODE, okay), "w83795 must be enabled");

/* Write fan1's PWM duty (bank 2, PWM1) then restore bank 0. Returns 0 on OK. */
static int set_pwm1(const struct device *i2c, uint8_t duty)
{
	uint8_t to_bank2[2] = { W83795_BANKSEL, 0x02 };
	uint8_t pwm[2]      = { W83795_PWM1, duty };
	uint8_t to_bank0[2] = { W83795_BANKSEL, 0x00 };
	int ret;

	ret = i2c_write(i2c, to_bank2, sizeof(to_bank2), W83795_ADDR);
	if (ret == 0) {
		ret = i2c_write(i2c, pwm, sizeof(pwm), W83795_ADDR);
	}
	if (ret == 0) {
		ret = i2c_write(i2c, to_bank0, sizeof(to_bank0), W83795_ADDR);
	}
	return ret;
}

/* Fetch + read fan1 RPM through the sensor driver. Returns RPM, or -1 on error. */
static int read_rpm(const struct device *dev)
{
	struct sensor_value rpm;

	if (sensor_sample_fetch(dev) != 0) {
		return -1;
	}
	if (sensor_channel_get(dev, SENSOR_CHAN_RPM, &rpm) != 0) {
		return -1;
	}
	return rpm.val1;
}

int main(void)
{
	const struct device *i2c = DEVICE_DT_GET(I2C_NODE);
	const struct device *w83795 = DEVICE_DT_GET(W83795_NODE);
	int base, high, low;

	printk("W83795 fanctl smoke: boot\n");

	if (!device_is_ready(i2c) || !device_is_ready(w83795)) {
		printk("W83795 fanctl: device(s) not ready\n");
		return 0;
	}

	base = read_rpm(w83795);

	/* Drive fan1 hard (duty 0x80): expect ~0x80*27 = 3456 rpm. */
	if (set_pwm1(i2c, 0x80) != 0) {
		printk("W83795 fanctl: PWM1=0x80 write FAIL\n");
		return 0;
	}
	high = read_rpm(w83795);

	/* Drive fan1 low (duty 0x40): expect ~0x40*27 = 1728 rpm. */
	if (set_pwm1(i2c, 0x40) != 0) {
		printk("W83795 fanctl: PWM1=0x40 write FAIL\n");
		return 0;
	}
	low = read_rpm(w83795);

	printk("W83795 fanctl: baseline=%d rpm, PWM=0x80 -> %d rpm, PWM=0x40 -> %d rpm\n",
	       base, high, low);

	/*
	 * PASS = the fan tach TRACKS the PWM duty: high-duty RPM lands near 3456
	 * (0x80*27) and low-duty near 1728 (0x40*27, ±~10% for the tach-count
	 * rounding), and high > low. That proves the BMC drove the fan, not just
	 * stored a byte.
	 */
	bool ok = (high >= 3100 && high <= 3800) &&
		  (low >= 1500 && low <= 1950) &&
		  (high > low);

	printk("W83795 FANCTL RESULT: %s\n", ok ? "PASS" : "FAIL");
	return 0;
}
