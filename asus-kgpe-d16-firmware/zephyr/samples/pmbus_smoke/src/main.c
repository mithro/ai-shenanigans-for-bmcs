/*
 * AST2050 (G3) PSU PMBus smoke test — DEVICE-MATRIX row 24.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Reads the server PSU over PMBus on the BMC's I2C1 engine and checks the +12 V
 * main-rail voltage, proving the Zephyr I2C stack talks PMBus to the modeled
 * supply. Console output goes through the M0 polling UART backend
 * (soc/aspeed_g3/ast2050/console.c); only CONFIG_I2C is needed in prj.conf.
 *
 * Target: connector PSUSMB1 (schematic §10.2, balls A15/B15 = SDA1/SCL1) on
 * I2C engine 0 (devicetree node i2c0, block 0x1E78A040 = schematic "I2C1").
 * The kgpe-d16-bmc QEMU machine wires a generic PMBus PSU there at 7-bit
 * address 0x58 (hw/arm/aspeed.c: i2c_slave_create_simple(get_bus(&soc->i2c, 0),
 * "pmbus-psu", 0x58); modeled by hw/sensor/pmbus_psu.c). On real silicon the
 * far end is whatever supply is plugged into PSUSMB1 (rig-gated — needs a PSU on
 * the bench; DEVICE-MATRIX #165), so this validates ZQ; ZS stays rig-gated.
 *
 * Registers read (PMBus 1.2):
 *   VOUT_MODE (0x20)  read-byte  -> 0x17: linear, 5-bit signed exponent = -9.
 *   READ_VOUT (0x8B)  read-word  -> 0x1800: ULINEAR16 mantissa; the value is
 *                     mantissa * 2^exp = 0x1800 * 2^-9 = 6144 / 512 = 12.000 V.
 *   PMBUS_REVISION (0x98) read-byte -> 0x22: PMBus revision 1.2 (context).
 * These are FIXED nominal values in the model (pmbus_psu.c pmbus_psu_exit_reset
 * seeds read_vout = pmbus_data2linear_mode(12, -9)), so the result is fully
 * deterministic and needs no host-power sequencing.
 *
 * Each read is the standard SMBus "write command byte, repeated-START, read N"
 * transaction (i2c_write_read) the AST2050 I2C master FSM supports.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define PMBUS_NODE        DT_NODELABEL(i2c0)  /* engine 0 @ 0x1E78A040 = I2C1 */
#define PSU_ADDR          0x58                /* conventional server-PSU PMBus */
#define PMBUS_VOUT_MODE   0x20U
#define PMBUS_READ_VOUT   0x8BU
#define PMBUS_REVISION    0x98U

BUILD_ASSERT(DT_NODE_HAS_STATUS(PMBUS_NODE, okay),
	     "i2c0 (aspeed,ast2050-i2c engine 0) must be enabled");

/* Sign-extend the low 5 bits of VOUT_MODE into the ULINEAR16 exponent. */
static int vout_exponent(uint8_t vout_mode)
{
	int exp = vout_mode & 0x1F;

	if (exp & 0x10) {
		exp -= 0x20;           /* 5-bit two's-complement */
	}
	return exp;
}

int main(void)
{
	const struct device *i2c = DEVICE_DT_GET(PMBUS_NODE);
	uint8_t cmd, mode = 0, rev = 0;
	uint8_t vout[2] = {0, 0};
	int ret, exp;
	uint32_t raw, mv;

	printk("PMBUS smoke: boot\n");

	if (!device_is_ready(i2c)) {
		printk("PMBUS smoke: i2c0 not ready\n");
		return 0;
	}

	cmd = PMBUS_VOUT_MODE;
	ret = i2c_write_read(i2c, PSU_ADDR, &cmd, 1, &mode, 1);
	if (ret != 0) {
		printk("PMBUS VOUT_MODE read FAIL (err %d)\n", ret);
		return 0;
	}

	cmd = PMBUS_READ_VOUT;
	ret = i2c_write_read(i2c, PSU_ADDR, &cmd, 1, vout, 2);
	if (ret != 0) {
		printk("PMBUS READ_VOUT read FAIL (err %d)\n", ret);
		return 0;
	}

	cmd = PMBUS_REVISION;
	ret = i2c_write_read(i2c, PSU_ADDR, &cmd, 1, &rev, 1);
	if (ret != 0) {
		printk("PMBUS REVISION read FAIL (err %d)\n", ret);
		return 0;
	}

	raw = (uint32_t)vout[0] | ((uint32_t)vout[1] << 8);  /* ULINEAR16, LE */
	exp = vout_exponent(mode);
	/* value = raw * 2^exp volts; exp is negative here (-9). Compute mV. */
	if (exp < 0) {
		mv = (raw * 1000U) >> (-exp);
	} else {
		mv = (raw * 1000U) << exp;
	}

	printk("PMBUS VOUT_MODE=0x%02x exp=%d READ_VOUT raw=0x%04x -> %u mV; REVISION=0x%02x\n",
	       mode, exp, raw, mv, rev);

	/* PASS = the PSU reports its +12 V main rail (11.5-12.5 V window). */
	if (mv >= 11500U && mv <= 12500U) {
		printk("PMBUS RESULT: PASS (+12V rail = %u mV)\n", mv);
	} else {
		printk("PMBUS RESULT: FAIL (vout %u mV out of range)\n", mv);
	}
	return 0;
}
