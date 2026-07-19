/*
 * AST2050 (G3) W83601G DIMM-LED expander smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Exercises the PROPER Zephyr GPIO driver drivers/gpio/gpio_w83601g.c on the U27
 * expander (@0x18 on the BMC's I2C5 engine = DT i2c4), through the standard
 * gpio_* API (not raw I2C):
 *
 *  - INPUT path: gpio_port_get_raw() reads the two input registers (CR00/CR08).
 *    We only require the read to SUCCEED (the chip ACKs) — the value differs by
 *    platform: the kgpe-d16-bmc QEMU machine seeds U27's Port-1 input latch to
 *    0x0f (hw/arm/aspeed.c) so it reads 0x000f, whereas the real chip reflects
 *    live pin states, so a specific value is NOT part of the pass gate.
 *  - OUTPUT path (the portable, platform-agnostic proof): drive Port-1 pin 3
 *    HIGH then LOW via gpio_pin_configure() and confirm CR01 bit 3 follows both
 *    ways (read back over raw I2C). A register that tracks both a 1 and a 0
 *    write proves the chip really ACKs+holds writes over the bus — this holds
 *    identically on QEMU and on silicon (the QEMU model keeps CR00 a static
 *    input latch that does not reflect outputs, so we check CR01 directly).
 *
 * A PASS proves the gpio_w83601g driver binds and read+write both work over the
 * AST2050 I2C master (i2c_aspeed_g3.c) on engine 4 — on QEMU AND real hardware.
 * (This is also the regression test for the SCU74[12] I2C5 pin-mux fix: without
 * it the real chip never ACKs and every access times out.)
 */

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define I2C_NODE  DT_NODELABEL(i2c4)
#define CR_P1_OUT 0x01U
#define TEST_PIN  3

BUILD_ASSERT(DT_NODE_HAS_STATUS(DT_NODELABEL(w83601g_u27), okay),
	     "w83601g_u27 (winbond,w83601g-gpio) must be enabled");
BUILD_ASSERT(DT_NODE_HAS_STATUS(DT_NODELABEL(w83601g_u28), okay),
	     "w83601g_u28 (winbond,w83601g-gpio) must be enabled");

/*
 * Validate one W83601G expander: the input read must ACK (value is platform-
 * specific), and driving pin 3 HIGH then LOW must be reflected in CR01 bit 3
 * both ways. Returns true on a full pass. `i2c`/`addr` are used for the raw CR01
 * cross-check (QEMU keeps CR00 a static input latch that ignores outputs).
 */
static bool test_expander(const struct device *gpio, const struct device *i2c,
			  uint8_t addr, const char *tag)
{
	gpio_port_value_t inval = 0;
	uint8_t cr01_hi = 0, cr01_lo = 0;
	int ret_in, ret_hi, ret_lo, ret_rd_hi, ret_rd_lo;
	bool out_ok;

	if (!device_is_ready(gpio)) {
		printk("W83601G %s: gpio device not ready\n", tag);
		return false;
	}

	ret_in = gpio_port_get_raw(gpio, &inval);

	ret_hi = gpio_pin_configure(gpio, TEST_PIN, GPIO_OUTPUT_HIGH);
	ret_rd_hi = i2c_reg_read_byte(i2c, addr, CR_P1_OUT, &cr01_hi);
	ret_lo = gpio_pin_configure(gpio, TEST_PIN, GPIO_OUTPUT_LOW);
	ret_rd_lo = i2c_reg_read_byte(i2c, addr, CR_P1_OUT, &cr01_lo);

	/* Every read/write must succeed. Checking the CR01 read return codes is
	 * essential: cr01_lo defaults to 0, and a FAILED low read would leave it 0
	 * — indistinguishable from a genuine "pin low" — so a discarded error could
	 * fake a PASS (fail loud, never hide an incomplete result).
	 */
	out_ok = (ret_hi == 0) && (ret_rd_hi == 0) && (cr01_hi & BIT(TEST_PIN)) &&
		 (ret_lo == 0) && (ret_rd_lo == 0) && !(cr01_lo & BIT(TEST_PIN));

	printk("W83601G %s @0x%02x: port_get=0x%04x (ret=%d)  pin%d high->CR01=0x%02x(r%d)  low->CR01=0x%02x(r%d)\n",
	       tag, addr, (unsigned int)inval, ret_in, TEST_PIN, cr01_hi, ret_rd_hi,
	       cr01_lo, ret_rd_lo);

	return (ret_in == 0) && out_ok;
}

int main(void)
{
	const struct device *i2c = DEVICE_DT_GET(I2C_NODE);
	bool u27_ok = test_expander(DEVICE_DT_GET(DT_NODELABEL(w83601g_u27)), i2c,
				    0x18U, "U27");
	bool u28_ok = test_expander(DEVICE_DT_GET(DT_NODELABEL(w83601g_u28)), i2c,
				    0x19U, "U28");

	if (u27_ok && u28_ok) {
		printk("W83601G RESULT: PASS\n");
	} else {
		printk("W83601G RESULT: FAIL\n");
	}

	return 0;
}
