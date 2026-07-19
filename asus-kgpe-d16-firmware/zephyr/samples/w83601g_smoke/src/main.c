/*
 * AST2050 (G3) W83601G DIMM-LED expander smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Exercises the PROPER Zephyr GPIO driver drivers/gpio/gpio_w83601g.c on the U27
 * expander (@0x18 on the BMC's I2C5 engine = DT i2c4), through the standard
 * gpio_* API (not raw I2C):
 *
 *  - INPUT path: gpio_port_get_raw() reads the two input registers (CR00/CR08).
 *    The kgpe-d16-bmc machine seeds U27's Port-1 input latch to 0x0f and Port-2
 *    to 0x00 (hw/arm/aspeed.c), so the 16-pin port reads back 0x000f.
 *  - OUTPUT path: gpio_pin_configure(pin, OUTPUT_HIGH) makes a pin an output and
 *    drives it high (the driver clears the CR03 direction bit + writes CR01).
 *    We cross-check the driver's write landed by reading CR01 back over raw I2C
 *    (the QEMU model keeps CR00 a static input latch, so an output value is not
 *    reflected there — hence the CR01 cross-check for the output assertion).
 *
 * A PASS proves the gpio_w83601g driver binds and both directions work over the
 * AST2050 I2C master (i2c_aspeed_g3.c) on engine 4.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define W601_NODE DT_NODELABEL(w83601g_u27)
#define I2C_NODE  DT_NODELABEL(i2c4)
#define W601_ADDR 0x18U
#define CR_P1_OUT 0x01U
#define TEST_PIN  3

BUILD_ASSERT(DT_NODE_HAS_STATUS(W601_NODE, okay),
	     "w83601g_u27 (winbond,w83601g-gpio) must be enabled");

int main(void)
{
	const struct device *gpio = DEVICE_DT_GET(W601_NODE);
	const struct device *i2c = DEVICE_DT_GET(I2C_NODE);
	gpio_port_value_t inval = 0;
	uint8_t cr01 = 0;
	int ret_in, ret_cfg;

	if (!device_is_ready(gpio)) {
		printk("W83601G smoke: gpio device not ready\n");
		return 0;
	}

	/* INPUT: read all 16 pins via the driver -> U27 seeds 0x000f. */
	ret_in = gpio_port_get_raw(gpio, &inval);

	/* OUTPUT: drive Port-1 pin 3 high via the driver, then cross-check CR01. */
	ret_cfg = gpio_pin_configure(gpio, TEST_PIN, GPIO_OUTPUT_HIGH);
	(void)i2c_reg_read_byte(i2c, W601_ADDR, CR_P1_OUT, &cr01);

	printk("W83601G gpio: port_get=0x%04x (want 0x000f)  set pin%d high -> CR01=0x%02x\n",
	       (unsigned int)inval, TEST_PIN, cr01);

	if (ret_in == 0 && inval == 0x000f && ret_cfg == 0 && (cr01 & BIT(TEST_PIN))) {
		printk("W83601G RESULT: PASS\n");
	} else {
		printk("W83601G RESULT: FAIL\n");
	}

	return 0;
}
