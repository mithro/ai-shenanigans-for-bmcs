/*
 * AST2050 (G3) W83795G sensor smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Exercises the W83795 sensor driver (drivers/sensor/w83795/w83795.c) end to
 * end: sensor_sample_fetch() then sensor_channel_get() for a fan (SENSOR_CHAN_RPM)
 * and the CPU thermal diode (SENSOR_CHAN_DIE_TEMP), and prints a clear PASS/FAIL
 * line. The driver reaches the chip over the AST2050 (G3) I2C master via the
 * Zephyr I2C API; console output goes through the M0 polling UART backend
 * (soc/aspeed/ast2050/console.c), so no extra console config is needed.
 *
 * Target: the Nuvoton/Winbond W83795G at 7-bit address 0x2F on I2C engine 1
 * (devicetree node w83795, child of i2c1 @ 0x1E78A080). The kgpe-d16-bmc QEMU
 * machine wires it there (hw/arm/aspeed.c kgpe_d16_bmc_i2c_init).
 *
 * DETERMINISTIC EXPECTATION (all from QEMU hw/sensor/w83795.c seeding):
 *   fan1  = 2641 rpm  -- w83795_load_defaults() line 184 seeds fan reg 0x2E via
 *                        w83795_set_fan(s, 0x2E, 2641): count = 1350000/2641 =
 *                        511, and the driver inverts it as 1350000/511 = 2641.
 *   temp0 = 50.500 C  -- w83795_load_defaults() line 177 seeds temp reg 0x21 via
 *                        w83795_set_temp(s, 0x21, 50500) = 50.5 degC.
 * Both are constant in the model, so the printed values are fully predictable.
 * PASS requires fan1 == 2641 rpm.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define W83795_NODE   DT_NODELABEL(w83795)
#define W83795_EXPECT_RPM 2641

BUILD_ASSERT(DT_NODE_HAS_STATUS(W83795_NODE, okay),
	     "w83795 (nuvoton,w83795 on i2c1) must be enabled");

int main(void)
{
	const struct device *dev = DEVICE_DT_GET(W83795_NODE);
	struct sensor_value rpm, temp;
	int ret;

	if (!device_is_ready(dev)) {
		printk("W83795 smoke: device not ready\n");
		return 0;
	}

	ret = sensor_sample_fetch(dev);
	if (ret != 0) {
		printk("W83795 sample_fetch FAIL (err %d)\n", ret);
		return 0;
	}

	ret = sensor_channel_get(dev, SENSOR_CHAN_RPM, &rpm);
	if (ret != 0) {
		printk("W83795 channel_get RPM FAIL (err %d)\n", ret);
		return 0;
	}

	ret = sensor_channel_get(dev, SENSOR_CHAN_DIE_TEMP, &temp);
	if (ret != 0) {
		printk("W83795 channel_get DIE_TEMP FAIL (err %d)\n", ret);
		return 0;
	}

	printk("W83795 fan1=%d rpm temp0=%d.%03d C (expect fan1=%d) %s\n",
	       rpm.val1, temp.val1, temp.val2 / 1000, W83795_EXPECT_RPM,
	       (rpm.val1 == W83795_EXPECT_RPM) ? "PASS" : "FAIL");

	return 0;
}
