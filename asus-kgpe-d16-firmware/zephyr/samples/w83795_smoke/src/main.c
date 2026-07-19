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
 * PASS is PLATFORM-AGNOSTIC (so this is a real both-sides test): both channel reads
 * must SUCCEED and return a physically PLAUSIBLE value — not an exact match to the
 * QEMU seed, because on real silicon the values are live. In QEMU the model seeds a
 * constant fan1=2641 rpm (w83795_load_defaults() w83795_set_fan(s,0x2E,2641)) and
 * temp0=50.5 C (w83795_set_temp(s,0x21,50500)); on the real AST2050 the W83795G
 * returns the live fan RPM / thermal-diode temperature (e.g. ~2600 rpm / ~58 C,
 * drifting between reads). The old exact-match (fan1==2641) false-FAILed on silicon
 * despite reading the real chip correctly — a QEMU-specific gate, now removed.
 */

#include <stdbool.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define W83795_NODE   DT_NODELABEL(w83795)

/* Plausible physical bounds spanning the QEMU seed and live silicon. */
#define W83795_RPM_MIN  100
#define W83795_RPM_MAX  30000
#define W83795_TEMP_MIN 0
#define W83795_TEMP_MAX 125

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

	bool fan_ok = (rpm.val1 >= W83795_RPM_MIN && rpm.val1 <= W83795_RPM_MAX);
	bool temp_ok = (temp.val1 >= W83795_TEMP_MIN && temp.val1 <= W83795_TEMP_MAX);

	printk("W83795 fan1=%d rpm (ok=%d) temp0=%d.%03d C (ok=%d)\n",
	       rpm.val1, fan_ok, temp.val1, temp.val2 / 1000, temp_ok);
	printk("W83795 RESULT: %s\n", (fan_ok && temp_ok) ? "PASS" : "FAIL");

	return 0;
}
