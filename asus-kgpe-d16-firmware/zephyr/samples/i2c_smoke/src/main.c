/*
 * AST2050 (G3) I2C smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Does ONE deterministic register read against a device the kgpe-d16-bmc QEMU
 * machine actually models, and prints a clear PASS/FAIL line. Console output
 * goes through the M0 polling UART backend (soc/aspeed/ast2050/console.c), so
 * no UART/console config is needed beyond CONFIG_I2C in prj.conf.
 *
 * Target: the Nuvoton/Winbond W83795G hardware monitor at 7-bit address 0x2F on
 * I2C engine 1 (devicetree node i2c1, register block 0x1E78A080). The machine
 * wires it there (hw/arm/aspeed.c kgpe_d16_bmc_i2c_init:
 * i2c_slave_create_simple(get_bus(&soc->i2c, 1), "w83795", 0x2f)).
 *
 * Register: CHIP_ID (0xFE). The QEMU w83795 model returns a CONSTANT 0x79 for
 * this register regardless of the bank-select state (hw/sensor/w83795.c
 * w83795_do_read(): `case W83795_REG_CHIPID: return 0x79;`), which is also the
 * real chip's ID that the Linux w83795 driver's detect() checks. That makes the
 * expected value fully predictable from the model, independent of prior state.
 *
 * The transaction is a standard "write register pointer, repeated-START, read
 * one byte" (i2c_write_read): msg0 = write {0xFE} (no STOP), msg1 = read 1 byte
 * (RESTART | STOP) — exactly the sequence the vendor U-Boot i2c_read_byte()
 * issues and that the AST2050 I2C master FSM supports.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define I2C_SMOKE_NODE  DT_NODELABEL(i2c1) /* engine 1 @ 0x1E78A080 */
#define W83795_ADDR     0x2F
#define W83795_REG_CID  0xFE               /* CHIP_ID */
#define W83795_CID_VAL  0x79               /* modelled + real chip-ID value */

BUILD_ASSERT(DT_NODE_HAS_STATUS(I2C_SMOKE_NODE, okay),
	     "i2c1 (aspeed,ast2050-i2c engine 1) must be enabled");

int main(void)
{
	const struct device *i2c = DEVICE_DT_GET(I2C_SMOKE_NODE);
	uint8_t reg = W83795_REG_CID;
	uint8_t val = 0;
	int ret;

	if (!device_is_ready(i2c)) {
		printk("I2C smoke: device not ready\n");
		return 0;
	}

	ret = i2c_write_read(i2c, W83795_ADDR, &reg, 1, &val, 1);
	if (ret != 0) {
		printk("I2C read dev=0x%02x reg=0x%02x FAIL (err %d)\n",
		       W83795_ADDR, W83795_REG_CID, ret);
		return 0;
	}

	printk("I2C read dev=0x%02x reg=0x%02x val=0x%02x (expect 0x%02x) %s\n",
	       W83795_ADDR, W83795_REG_CID, val, W83795_CID_VAL,
	       (val == W83795_CID_VAL) ? "PASS" : "FAIL");

	return 0;
}
