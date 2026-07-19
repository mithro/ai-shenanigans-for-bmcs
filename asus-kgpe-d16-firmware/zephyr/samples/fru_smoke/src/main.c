/*
 * AST2050 (G3) FRU EEPROM smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Reads the board FRU EEPROM (U25, HT24LC08 @0x54 on the BMC's I2C5 engine =
 * DT i2c4 = QEMU bus 4) through the Zephyr in-tree at2x EEPROM driver, which in
 * turn drives the AST2050 I2C master driver (drivers/i2c/i2c_aspeed_g3.c) on a
 * THIRD engine (after engine 1 / W83795 and engine 3 / SB-TSI). The QEMU machine
 * models the FRU blank (0xff) as ASUS shipped it, so a successful read of 0xff
 * is the PASS: it proves the full eeprom→i2c stack reaches engine 4 and the
 * device ACKs.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/eeprom.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define FRU_SMOKE_NODE DT_NODELABEL(fru_eeprom)

BUILD_ASSERT(DT_NODE_HAS_STATUS(FRU_SMOKE_NODE, okay),
	     "fru_eeprom (atmel,at24 on i2c4) must be enabled");

int main(void)
{
	const struct device *eeprom = DEVICE_DT_GET(FRU_SMOKE_NODE);
	uint8_t buf[4] = {0};
	size_t size;
	int ret;

	if (!device_is_ready(eeprom)) {
		printk("FRU smoke: device not ready\n");
		return 0;
	}

	size = eeprom_get_size(eeprom);

	ret = eeprom_read(eeprom, 0, buf, sizeof(buf));
	if (ret != 0) {
		printk("FRU smoke: eeprom_read failed (%d)\n", ret);
		return 0;
	}

	printk("FRU eeprom size=%u read[0..3]=%02x %02x %02x %02x\n",
	       (unsigned int)size, buf[0], buf[1], buf[2], buf[3]);

	/* Blank as shipped: every byte 0xff. */
	if (buf[0] == 0xff && buf[1] == 0xff && buf[2] == 0xff && buf[3] == 0xff) {
		printk("FRU RESULT: PASS\n");
	} else {
		printk("FRU RESULT: FAIL\n");
	}

	return 0;
}
