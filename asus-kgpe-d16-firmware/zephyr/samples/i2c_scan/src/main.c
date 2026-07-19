/*
 * AST2050 (G3) I2C bus scanner — FRU EEPROM address resolver.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Probes the board-inventory bus (I2C5 = DT i2c4 = engine 4 @ 0x1E78A140) across
 * 7-bit addresses 0x50..0x57 and reports which ones ACK. This settles the FRU
 * EEPROM (U25, Holtek HT24LC08) address question:
 *   - schematic-wiring docs list 0x50-0x53 (the A2=GND base range),
 *   - the zephyr dts + prior silicon fru_smoke read used 0x54 (A2/E2=VCC).
 * A 24C08 (8 Kbit) has ONE external address pin A2 plus 2 internal block-select
 * bits, so A2=GND => it answers at 0x50-0x53 and A2=VCC => 0x54-0x57 (never both).
 * Whichever quartet ACKs here is ground truth (the hardware is the authority).
 *
 * Probe = a 1-byte i2c_read of each address. The aspeed_g3 master driver returns
 * -ENXIO when the address byte is NAKed (drivers/i2c/i2c_aspeed_g3.c: TX_NAK ->
 * -ENXIO) and 0 on ACK, so ret distinguishes present/absent unambiguously. The
 * driver applies the SCU74[12] I2C5 pin-mux at init (needed for engine 4).
 * Console goes through the M0 polling UART backend (no UART config needed).
 */

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define SCAN_NODE  DT_NODELABEL(i2c4) /* engine 4 @ 0x1E78A140 = board-inventory I2C5 */
#define SCAN_LO    0x50
#define SCAN_HI    0x57

BUILD_ASSERT(DT_NODE_HAS_STATUS(SCAN_NODE, okay),
	     "i2c4 (aspeed,ast2050-i2c engine 4) must be enabled");

int main(void)
{
	const struct device *i2c = DEVICE_DT_GET(SCAN_NODE);
	int acks = 0;
	int lo_quartet = 0; /* 0x50-0x53 ACK count */
	int hi_quartet = 0; /* 0x54-0x57 ACK count */

	if (!device_is_ready(i2c)) {
		printk("I2C scan: device not ready\n");
		printk("SCAN RESULT: FAIL\n");
		return 0;
	}

	for (uint8_t addr = SCAN_LO; addr <= SCAN_HI; addr++) {
		uint8_t b = 0;
		int ret = i2c_read(i2c, &b, 1, addr);

		printk("I2C5 addr=0x%02x %s (ret=%d)\n",
		       addr, ret == 0 ? "ACK" : "--", ret);

		if (ret == 0) {
			acks++;
			if (addr <= 0x53) {
				lo_quartet++;
			} else {
				hi_quartet++;
			}
		}
	}

	printk("I2C5 scan: %d device(s) ACK in 0x50-0x57 (lo 0x50-53=%d, hi 0x54-57=%d)\n",
	       acks, lo_quartet, hi_quartet);
	if (hi_quartet > 0 && lo_quartet == 0) {
		printk("FRU-ADDR: 0x54-0x57 (A2/E2=VCC) — dts 0x54 is correct, schematic 0x50-0x53 is the base range\n");
	} else if (lo_quartet > 0 && hi_quartet == 0) {
		printk("FRU-ADDR: 0x50-0x53 (A2=GND) — schematic correct, dts 0x54 is WRONG\n");
	} else {
		printk("FRU-ADDR: inconclusive (see per-address lines above)\n");
	}

	/* PASS = the scan ran and the master returned defined per-address results. */
	printk("SCAN RESULT: PASS\n");
	return 0;
}
