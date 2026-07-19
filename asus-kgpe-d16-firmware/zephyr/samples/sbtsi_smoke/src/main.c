/*
 * AST2050 (G3) AMD SB-TSI CPU-temperature sensor smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Exercises the SB-TSI sensor driver (drivers/sensor/sbtsi/sbtsi.c) end to end:
 * sensor_sample_fetch() then sensor_channel_get() for the CPU die temperature
 * (SENSOR_CHAN_DIE_TEMP), and prints a clear PASS/FAIL line. The driver reaches
 * the chip over the AST2050 (G3) I2C master via the Zephyr I2C API; console
 * output goes through the M0 polling UART backend (soc/aspeed/ast2050/console.c),
 * so no extra console config is needed.
 *
 * Target: the AMD SB-TSI at 7-bit address 0x4C (socket P0) on I2C engine 3
 * (devicetree node sbtsi, child of i2c3 @ 0x1E78A100). The kgpe-d16-bmc QEMU
 * machine wires it there (hw/arm/aspeed.c kgpe_d16_bmc_i2c_init lines 619-638).
 *
 * DETERMINISTIC EXPECTATION (from QEMU hw/arm/aspeed.c + hw/sensor/sbtsi.c):
 *   temp = 45.500 C -- hw/arm/aspeed.c line 628 seeds P0 (0x4C) to 45500 mC and
 *                      sets it via the "temperature" property (line 635), which
 *                      drives sbtsi_update_temp() (sbtsi.c lines 60-72):
 *                        TEMP_INT = 45500/1000        = 45
 *                        TEMP_DEC = ((45500%1000)/125) << 5 = 4 << 5 = 0x80
 *                      The driver rebuilds 45*1000000 + (0x80>>5)*125000 =
 *                      45500000 micro-degrees -> val1 = 45, val2 = 500000.
 * The seed is constant in the model, so the printed value is fully predictable.
 * PASS requires temp == {val1 = 45, val2 = 500000} (45.500 C).
 */

#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define SBTSI_NODE        DT_NODELABEL(sbtsi)
#define SBTSI_EXPECT_VAL1 45     /* whole degrees C           */
#define SBTSI_EXPECT_VAL2 500000 /* micro-degrees (0.500 C)   */

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

	pass = (temp.val1 == SBTSI_EXPECT_VAL1) && (temp.val2 == SBTSI_EXPECT_VAL2);
	printk("SBTSI temp=%d.%03d C (expect %d) %s\n",
	       temp.val1, temp.val2 / 1000, SBTSI_EXPECT_VAL1,
	       pass ? "PASS" : "FAIL");

	return 0;
}
