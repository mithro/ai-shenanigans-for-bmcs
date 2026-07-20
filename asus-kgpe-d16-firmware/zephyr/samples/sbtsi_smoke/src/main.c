/*
 * AST2050 (G3) AMD SB-TSI CPU-temperature sensor smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Exercises the SB-TSI sensor driver (drivers/sensor/sbtsi/sbtsi.c) end to end:
 * sensor_sample_fetch() then sensor_channel_get() for the CPU die temperature
 * (SENSOR_CHAN_DIE_TEMP), and prints a clear PASS/FAIL line. The driver reaches
 * the chip over the AST2050 (G3) I2C master via the Zephyr I2C API; console
 * output goes through the M0 polling UART backend (soc/aspeed_g3/ast2050/console.c),
 * so no extra console config is needed.
 *
 * Target: the AMD SB-TSI at 7-bit address 0x4C (socket P0) on I2C engine 3
 * (devicetree node sbtsi, child of i2c3 @ 0x1E78A100). The kgpe-d16-bmc QEMU
 * machine wires it there (hw/arm/aspeed.c kgpe_d16_bmc_i2c_init lines 619-638).
 *
 * DETERMINISTIC EXPECTATION (from QEMU hw/arm/aspeed.c + hw/sensor/sbtsi.c):
 * PASS is PLATFORM-AGNOSTIC (a real both-sides test): the read must SUCCEED and
 * the CPU die temperature must be physically PLAUSIBLE — not an exact match to the
 * QEMU seed, because on real silicon the AMD SB-TSI returns the live CPU
 * temperature. In QEMU the model seeds a constant 45.500 C (hw/arm/aspeed.c seeds
 * P0 @0x4C to 45500 mC → TEMP_INT=45, TEMP_DEC=0x80 → val1=45 val2=500000). On the
 * real AST2050 the host CPU must be POWERED (SB-TSI is a CPU-integrated sensor on
 * I2C engine 3); with it on, the driver reads the live die temp (drifting).
 */

#include <stdbool.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define SBTSI_NODE     DT_NODELABEL(sbtsi)

/* Plausible AMD CPU die-temp bounds spanning the QEMU seed and live silicon. */
#define SBTSI_TEMP_MIN 0
#define SBTSI_TEMP_MAX 125

BUILD_ASSERT(DT_NODE_HAS_STATUS(SBTSI_NODE, okay),
	     "sbtsi (amd,sbtsi on i2c3) must be enabled");

int main(void)
{
	const struct device *dev = DEVICE_DT_GET(SBTSI_NODE);
	struct sensor_value temp;
	bool pass;
	int ret;

	if (!device_is_ready(dev)) {
		printk("SBTSI smoke: device not ready\n");
		return 0;
	}

	ret = sensor_sample_fetch(dev);
	if (ret != 0) {
		printk("SBTSI sample_fetch FAIL (err %d)\n", ret);
		return 0;
	}

	ret = sensor_channel_get(dev, SENSOR_CHAN_DIE_TEMP, &temp);
	if (ret != 0) {
		printk("SBTSI channel_get DIE_TEMP FAIL (err %d)\n", ret);
		return 0;
	}

	pass = (temp.val1 >= SBTSI_TEMP_MIN && temp.val1 <= SBTSI_TEMP_MAX);
	printk("SBTSI temp=%d.%03d C (ok=%d)\n",
	       temp.val1, temp.val2 / 1000, pass);
	printk("SBTSI RESULT: %s\n", pass ? "PASS" : "FAIL");

	return 0;
}
