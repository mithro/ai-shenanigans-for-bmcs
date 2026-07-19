/*
 * AST2050 (G3) W83601G DIMM-LED expander smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Drives the Winbond W83601G I2C GPIO expander (U27 @0x18) the way the BMC
 * firmware lights the DIMM error LEDs, over the AST2050 I2C master
 * (drivers/i2c/i2c_aspeed_g3.c) on engine 4 = schematic I2C5 = DT i2c4 (the same
 * engine the FRU EEPROM sits on). The W83601G is a CR-indexed expander (register
 * map from hw/gpio/w83601g.c): CR20 = chip-ID high (0x60), CR03 = Port-1 I/O
 * config (reset 0xFF all-input; clear a bit → that pin is an output), CR01 =
 * Port-1 output data, CR00 = Port-1 input.
 *
 * The LED-drive sequence validated here is exactly the silicon one
 * (scripts/w83601g-test.py): verify the chip-ID, make Port-1 outputs (CR03 = 0),
 * write a pattern to CR01, read it back, then restore reset defaults. A PASS
 * proves the expander is reachable + drivable from Zephyr over the I2C driver.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define I2C_NODE   DT_NODELABEL(i2c4)
#define W83601G_ADDR 0x18U

/* W83601G CR indices (hw/gpio/w83601g.c). */
#define CR_P1_IN    0x00U
#define CR_P1_OUT   0x01U
#define CR_P1_IOCFG 0x03U
#define CR_ID_HIGH  0x20U

#define W83601G_ID_HIGH 0x60U
#define LED_PATTERN     0x55U

BUILD_ASSERT(DT_NODE_HAS_STATUS(I2C_NODE, okay), "i2c4 must be enabled");

int main(void)
{
	const struct device *i2c = DEVICE_DT_GET(I2C_NODE);
	uint8_t id, iocfg_save, out;
	int ret;

	if (!device_is_ready(i2c)) {
		printk("W83601G smoke: i2c not ready\n");
		return 0;
	}

	/* 1. Identify: CR20 must read the chip-ID high 0x60. */
	ret = i2c_reg_read_byte(i2c, W83601G_ADDR, CR_ID_HIGH, &id);
	if (ret != 0) {
		printk("W83601G smoke: CR20 read failed (%d)\n", ret);
		return 0;
	}

	/* 2. Save CR03, make all Port-1 pins outputs (CR03 = 0x00). */
	ret = i2c_reg_read_byte(i2c, W83601G_ADDR, CR_P1_IOCFG, &iocfg_save);
	ret |= i2c_reg_write_byte(i2c, W83601G_ADDR, CR_P1_IOCFG, 0x00U);

	/* 3. Drive a pattern to CR01 and read it back. */
	ret |= i2c_reg_write_byte(i2c, W83601G_ADDR, CR_P1_OUT, LED_PATTERN);
	ret |= i2c_reg_read_byte(i2c, W83601G_ADDR, CR_P1_OUT, &out);

	/* 4. Restore reset defaults (CR03 back to all-input, CR01 = 0). */
	(void)i2c_reg_write_byte(i2c, W83601G_ADDR, CR_P1_OUT, 0x00U);
	(void)i2c_reg_write_byte(i2c, W83601G_ADDR, CR_P1_IOCFG, iocfg_save);

	printk("W83601G id(CR20)=0x%02x  LED CR01 set=0x%02x get=0x%02x\n",
	       id, LED_PATTERN, out);

	if (ret == 0 && id == W83601G_ID_HIGH && out == LED_PATTERN) {
		printk("W83601G RESULT: PASS\n");
	} else {
		printk("W83601G RESULT: FAIL\n");
	}

	return 0;
}
