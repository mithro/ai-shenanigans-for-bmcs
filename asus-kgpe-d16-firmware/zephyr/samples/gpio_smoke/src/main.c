/*
 * AST2050 (G3) GPIO smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Validates the aspeed,ast2050-gpio driver's device-ready + configure + REAL-
 * register read path on a genuine AST2050 GPIO register, on both QEMU and real
 * silicon. Console output goes through the M0 polling UART backend
 * (soc/aspeed_g3/ast2050/console.c), so no UART/console config is needed beyond
 * CONFIG_GPIO in prj.conf.
 *
 * Test pin: GPIOH2 = bit 26 of the EFGH set (devicetree node gpio1, "Extended
 * GPIO Data Value" register @ 0x1E780020 — a REAL AST2050 register per datasheet
 * §23.3). On the KGPE-D16, GPIOH2 is STA_LINE_POWER, a bonded INPUT (standby /
 * I2C-bus power-rail sense — schematic §11). We read it: this exercises the
 * driver's real-register access on silicon with ZERO board side effects (a pure
 * read cannot perturb the board).
 *
 * WHY READ-ONLY, and why NOT the old GPIOI0 pin:
 *  - The previous version drove GPIOI0 (set IJKL @0x1E780070). That register
 *    DOES NOT EXIST on the AST2050 — the datasheet GPIO map has only ABCD@0x00
 *    and EFGH@0x20 (IJKL/MNOP/QRST/UVWX/YZAAAB are an AST2400/G4 addition).
 *    QEMU idealized the phantom register (readback=1) but silicon has nothing
 *    there (readback=0) — the #163 "reads back 0" symptom. Removing the phantom
 *    gpio2..gpio6 nodes (ast2050.dtsi) fixes the root cause.
 *  - An OUTPUT write-readback needs a bonded pin that is safe to DRIVE (nothing
 *    external drives it back — contention can damage silicon). The only bonded
 *    ABCD/EFGH pins we can currently name are the power-sequencer control lines
 *    (A4/B1/B6/F0), which power_smoke already drives to prove the OUTPUT path
 *    with observable board effects. A dedicated safe-to-drive output (a bonded
 *    NC pin or a BMC-driven LED) needs the §11 GPIO map (#136) to identify — so
 *    the full write-readback on a bonded output is deferred there. The OUTPUT
 *    path is covered by power_smoke; this sample covers the real-register read.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define GPIO_SMOKE_NODE DT_NODELABEL(gpio1) /* EFGH set @ 0x1E780020 (real) */
#define GPIO_SMOKE_PIN  26                  /* GPIOH2 = STA_LINE_POWER (bonded input) */

BUILD_ASSERT(DT_NODE_HAS_STATUS(GPIO_SMOKE_NODE, okay),
	     "gpio1 (aspeed,ast2050-gpio EFGH set) must be enabled");

int main(void)
{
	const struct device *gpio = DEVICE_DT_GET(GPIO_SMOKE_NODE);
	int ret;
	int val;

	if (!device_is_ready(gpio)) {
		printk("GPIO smoke: device not ready\n");
		printk("GPIO RESULT: FAIL\n");
		return 0;
	}

	ret = gpio_pin_configure(gpio, GPIO_SMOKE_PIN, GPIO_INPUT);
	if (ret != 0) {
		printk("GPIO smoke: configure-input failed (%d)\n", ret);
		printk("GPIO RESULT: FAIL\n");
		return 0;
	}

	val = gpio_pin_get_raw(gpio, GPIO_SMOKE_PIN);
	printk("GPIO gpio1(EFGH)/pin26 GPIOH2 read=%d\n", val);

	/*
	 * PASS = the driver reached a real register and returned a DEFINED logic
	 * level (0 or 1). A negative value means the read call itself failed. The
	 * specific level is board-power-state dependent (STA_LINE_POWER: 0 at deep
	 * S5 ~4W, 1 once the standby/I2C rail is up) and is characterised in
	 * power_smoke / #162 — it is not a pass/fail criterion here.
	 */
	if (val == 0 || val == 1) {
		printk("GPIO RESULT: PASS\n");
	} else {
		printk("GPIO RESULT: FAIL\n");
	}

	return 0;
}
