/*
 * AST2050 (G3) GPIO smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Configures one safe output pin, drives it high, reads the data register back,
 * and prints the result. Console output goes through the M0 polling UART
 * backend (soc/aspeed/ast2050/console.c), so no UART/console config is needed
 * beyond CONFIG_GPIO in prj.conf.
 *
 * Test pin: GPIOI0 = bit 0 of the IJKL set (devicetree node gpio2, base
 * 0x1E780070). Chosen because it is safe to toggle in the QEMU kgpe-d16-bmc
 * machine: only sets ABCD (A4/B1/B6) and EFGH (F0/F4/F5/H2) carry the board
 * power-sequencer / I2C-mux glue that the machine models, so a pin in set IJKL
 * has NO board wiring and cannot perturb host power. QEMU models set IJKL as
 * fully output-capable (aspeed_gpio.c ast2400_set_props[2] = {0xffffffff,
 * 0xffffffff}). Do NOT point this at GPIOA4 (power lockout) or the other power
 * lines.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define GPIO_SMOKE_NODE DT_NODELABEL(gpio2) /* IJKL set @ 0x1E780070 */
#define GPIO_SMOKE_PIN  0                   /* GPIOI0 */

BUILD_ASSERT(DT_NODE_HAS_STATUS(GPIO_SMOKE_NODE, okay),
	     "gpio2 (aspeed,ast2050-gpio IJKL set) must be enabled");

int main(void)
{
	const struct device *gpio = DEVICE_DT_GET(GPIO_SMOKE_NODE);
	int ret;
	int val;

	if (!device_is_ready(gpio)) {
		printk("GPIO smoke: device not ready\n");
		return 0;
	}

	ret = gpio_pin_configure(gpio, GPIO_SMOKE_PIN, GPIO_OUTPUT_HIGH);
	if (ret != 0) {
		printk("GPIO smoke: configure failed (%d)\n", ret);
		return 0;
	}

	val = gpio_pin_get_raw(gpio, GPIO_SMOKE_PIN);
	printk("GPIO set=1 read=%d\n", val);

	/* Also exercise clear + read-back so the full set/clear path is covered. */
	ret = gpio_pin_set_raw(gpio, GPIO_SMOKE_PIN, 0);
	if (ret == 0) {
		val = gpio_pin_get_raw(gpio, GPIO_SMOKE_PIN);
		printk("GPIO set=0 read=%d\n", val);
	}

	return 0;
}
