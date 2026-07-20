/*
 * AST2050 (G3) DIMM SPD smoke test via the QU9/QU5/U23 I2C mux fabric —
 * DEVICE-MATRIX rows 17 (mux fabric) + 18 (DIMM SPD).
 * SPDX-License-Identifier: Apache-2.0
 *
 * Proves the Zephyr port can bring the DIMM SPD/TSOD bus into reach and read a
 * DIMM SPD EEPROM behind the board's I2C mux fabric — exercising the GPIO driver
 * (gpio_aspeed_g3, for both the host-power sequence AND the QU5 mux selects) and
 * the I2C driver (i2c_aspeed_g3) together.
 *
 * Topology (schematic §3/§10, hw/i2c/kgpe_d16_i2c_fabric.c): the BMC's I2C2
 * engine (devicetree node i2c1) reaches the DIMM SPD/TSOD buses through QU9 +
 * QU5 (74HC4052 dual 4-ch analog mux):
 *   - QU9 is gated by SYS_PWRGD: while the host is OFF the whole fabric is
 *     electrically disconnected, so NOTHING behind it is reachable. The DIMM
 *     SPD is powered only when the host is on — a real hardware constraint, not
 *     a bug. So this test must power the host ON first.
 *   - QU5's channel is S1:S0, driven by GPIOF4 (S0) / GPIOF5 (S1) with 4.7k
 *     pull-ups (read high unless driven low). Channels: Y0 aux, Y1 nc,
 *     Y2 = DIMM A-D SPD/TSOD, Y3 = DIMM E-H. Y2 = channel 2 = S1:S0 = 10.
 *   - While the host is on, U23 hands the BMC ownership of the selects.
 *
 * GPIO mapping (per-set pin = bank*8 + pin; ABCD = gpio0, EFGH = gpio1):
 *   Power seq: A4 (gpio0 p4) BMC-in-control, B1 (gpio0 p9) power-up#,
 *              B6 (gpio0 p14) reset#, F0 (gpio1 p8) force-off#,
 *              H2 (gpio1 p26) STA_LINE_POWER feedback.
 *   Mux:       GPIOF4 = gpio1 p12 (S0), GPIOF5 = gpio1 p13 (S1).
 *
 * DIMM: slot A2 only (bank Y2), a 4 GB DDR3 UDIMM (part "RMR5030EF68F9W1600"),
 * SPD EEPROM at 0x51. SPD bytes (JEDEC): [2] = 0x0B (DDR3), [3] = 0x02 (UDIMM).
 * On real silicon this needs the host powered so the DIMM rails are up AND a
 * populated DIMM (rig/host-gated, #150/#165); this validates ZQ. Restores the
 * host to OFF at the end.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/sys/util.h>

#define GPIO_ABCD    DT_NODELABEL(gpio0)
#define GPIO_EFGH    DT_NODELABEL(gpio1)

#define PIN_A4 4    /* gpio0: BMC-in-control */
#define PIN_B1 9    /* gpio0: power-up#     */
#define PIN_B6 14   /* gpio0: reset#        */
#define PIN_F0 8    /* gpio1: force-off#    */
#define PIN_H2 26   /* gpio1: STA_LINE_POWER (in) */
#define PIN_F4 12   /* gpio1: QU5 mux select S0 */
#define PIN_F5 13   /* gpio1: QU5 mux select S1 */

#define SCU_BASE         0x1E6E2000U
#define SCU_PROT_KEY     0x00U
#define SCU_MFP_CTL1     0x74U
#define SCU_UNLOCK_MAGIC 0x1688A8A8U
#define SCU74_A4_PHYLINK BIT(25)

#define SPD_BUS      DT_NODELABEL(i2c1)   /* engine 1 = schematic I2C2 */
#define SPD_ADDR     0x51
#define SPD_MEM_TYPE 0x02
#define SPD_MOD_TYPE 0x03
#define SPD_DDR3     0x0B
#define SPD_UDIMM    0x02

#define PULSE_US 200000  /* QEMU latch flips synchronously; silicon needs debounce */

BUILD_ASSERT(DT_NODE_HAS_STATUS(GPIO_ABCD, okay), "gpio0 (ABCD) must be enabled");
BUILD_ASSERT(DT_NODE_HAS_STATUS(GPIO_EFGH, okay), "gpio1 (EFGH) must be enabled");
BUILD_ASSERT(DT_NODE_HAS_STATUS(SPD_BUS, okay), "i2c1 (engine 1) must be enabled");

static void reclaim_a4(void)
{
	uint32_t v;

	sys_write32(SCU_UNLOCK_MAGIC, SCU_BASE + SCU_PROT_KEY);
	v = sys_read32(SCU_BASE + SCU_MFP_CTL1);
	sys_write32(v & ~SCU74_A4_PHYLINK, SCU_BASE + SCU_MFP_CTL1);
}

static int spd_read(const struct device *i2c, uint8_t off, uint8_t *val)
{
	return i2c_write_read(i2c, SPD_ADDR, &off, 1, val, 1);
}

int main(void)
{
	const struct device *abcd = DEVICE_DT_GET(GPIO_ABCD);
	const struct device *efgh = DEVICE_DT_GET(GPIO_EFGH);
	const struct device *i2c = DEVICE_DT_GET(SPD_BUS);
	uint8_t mem_type = 0, mod_type = 0;
	int host_on, ret_m, ret_t;
	bool pass = false;

	printk("SPD smoke: boot\n");

	if (!device_is_ready(abcd) || !device_is_ready(efgh) || !device_is_ready(i2c)) {
		printk("SPD smoke: gpio/i2c device(s) not ready\n");
		return 0;
	}

	/* Power the host ON so QU9 closes and the DIMM SPD bus comes into reach. */
	reclaim_a4();
	gpio_pin_configure(efgh, PIN_H2, GPIO_INPUT);
	gpio_pin_configure(abcd, PIN_A4, GPIO_OUTPUT_HIGH);   /* BMC in control */
	gpio_pin_configure(efgh, PIN_F0, GPIO_OUTPUT_HIGH);   /* force-off# high */
	gpio_pin_configure(abcd, PIN_B6, GPIO_OUTPUT_HIGH);   /* reset# high */
	gpio_pin_configure(abcd, PIN_B1, GPIO_OUTPUT_HIGH);   /* power-up# high */

	gpio_pin_set_raw(abcd, PIN_B6, 0);
	gpio_pin_set_raw(abcd, PIN_B1, 0);
	k_busy_wait(PULSE_US);
	gpio_pin_set_raw(abcd, PIN_B6, 1);
	gpio_pin_set_raw(abcd, PIN_B1, 1);
	k_busy_wait(PULSE_US);

	host_on = gpio_pin_get_raw(efgh, PIN_H2);
	printk("SPD: host power-on -> STA_LINE_POWER(H2)=%d (need 1 to reach the SPD bus)\n",
	       host_on);

	if (host_on == 1) {
		/* Route QU5 to Y2 (DIMM A-D): S0=0 (F4 low), S1=1 (F5 high). */
		gpio_pin_configure(efgh, PIN_F4, GPIO_OUTPUT_LOW);
		gpio_pin_configure(efgh, PIN_F5, GPIO_OUTPUT_HIGH);

		ret_m = spd_read(i2c, SPD_MEM_TYPE, &mem_type);
		ret_t = spd_read(i2c, SPD_MOD_TYPE, &mod_type);
		printk("SPD (Y2) byte2(devtype)=0x%02x byte3(modtype)=0x%02x (err %d/%d)\n",
		       mem_type, mod_type, ret_m, ret_t);

		pass = (ret_m == 0 && ret_t == 0 &&
			mem_type == SPD_DDR3 && mod_type == SPD_UDIMM);
	}

	/* Restore: force the host back OFF (leave the board as found). */
	gpio_pin_set_raw(efgh, PIN_F0, 0);
	k_busy_wait(PULSE_US);
	gpio_pin_set_raw(efgh, PIN_F0, 1);

	if (pass) {
		printk("SPD RESULT: PASS (DDR3 UDIMM SPD read via QU5-Y2, host-gated QU9)\n");
	} else {
		printk("SPD RESULT: FAIL\n");
	}
	return 0;
}
