/*
 * AST2050 (G3) KGPE-D16 host power-control smoke test (Zephyr, bare-metal).
 * SPDX-License-Identifier: Apache-2.0
 *
 * Drives the ASUS KGPE-D16 host power sequence from Zephyr using the AST2050
 * GPIO driver (drivers/gpio/gpio_aspeed_g3.c) — the same request-line pulses the
 * OpenBMC `kgpe-power.sh` runs, ported to bare metal. Validates the BMC's host
 * power ON and force-OFF control (DEVICE-MATRIX row 27) end to end, reading the
 * STA_LINE_POWER feedback (GPIOH2) after each transition, and leaves the host in
 * the OFF state it was found in.
 *
 * Signals (schematic §1.2 / HW-WIRING-power-sensors.md; per-set Zephyr pin =
 * bank*8 + pin, sets ABCD = gpio0, EFGH = gpio1):
 *   GPIOA4  ASUS_BMC_CTL_LOCKOUT_N  gpio0 pin 4   out, HIGH = "BMC in control"
 *   GPIOB1  CTL_REQ_POWERUP_N       gpio0 pin 9   out, active-low power-up req
 *   GPIOB6  CTL_REQ_RESET_N         gpio0 pin 14  out, active-low warm-reset req
 *   GPIOF0  CTL_REQ_POWERDOWN_N     gpio1 pin 8   out, active-low force-off req
 *   GPIOH2  STA_LINE_POWER          gpio1 pin 26  in,  1 = host powered, 0 = off
 *
 * Power latch (hardware-verified 2026-07-13; modelled in QEMU
 * hw/gpio/aspeed_gpio.c aspeed_gpio_kgpe_d16_pwrseq): force-OFF (F0 low) always
 * wins; otherwise power-UP (B1 low) is honoured ONLY while A4 is a driven-HIGH
 * output ("BMC in control"). A4's pad defaults to the PHYLINK alt-function
 * (SCU74[25]=1); we clear that bit so A4 is a real GPIO output (the QEMU GPIO
 * model ignores the SCU write, silicon requires it — kgpe-power.sh setup_a4()).
 *
 * PASS = GPIOH2 observed 0 (found off) → 1 (after power-ON) → 0 (after force-OFF).
 * In QEMU the pwrseq latch flips synchronously; on silicon GPIOH2 follows the real
 * PSU (also visible as the au-plug meter stepping ~50 W → ~103 W → ~50 W).
 */

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/sys/util.h>

#define GPIO_ABCD DT_NODELABEL(gpio0)
#define GPIO_EFGH DT_NODELABEL(gpio1)

#define PIN_A4 4   /* gpio0 ABCD */
#define PIN_B1 9   /* gpio0 ABCD */
#define PIN_B6 14  /* gpio0 ABCD */
#define PIN_F0 8   /* gpio1 EFGH */
#define PIN_H2 26  /* gpio1 EFGH */

/* Reclaim GPIOA4 from its PHYLINK alt-function so it can be a GPIO output. */
#define SCU_BASE           0x1E6E2000U
#define SCU_PROT_KEY       0x00U
#define SCU_MFP_CTL1       0x74U
#define SCU_UNLOCK_MAGIC   0x1688A8A8U
#define SCU74_A4_PHYLINK   BIT(25)

/*
 * ~1 s request-line pulse width. k_busy_wait() spins on the cycle counter (no
 * scheduler/tick dependency, which is fragile on this brand-new ARM9 arm_mmu),
 * and unlike a slow MMIO busy-loop it stays cheap under QEMU. In QEMU the pwrseq
 * latch flips synchronously on the request-line write, so the exact width only
 * matters on silicon, where it must out-last the PSU request debounce.
 */
#define PULSE_US 1000000

static void busy_delay(void)
{
	k_busy_wait(PULSE_US);
}

static void reclaim_a4(void)
{
	uint32_t v;

	sys_write32(SCU_UNLOCK_MAGIC, SCU_BASE + SCU_PROT_KEY);
	v = sys_read32(SCU_BASE + SCU_MFP_CTL1);
	sys_write32(v & ~SCU74_A4_PHYLINK, SCU_BASE + SCU_MFP_CTL1);
}

/* Wrap a GPIO call: on failure print a diagnostic and flag *ok false (fail loud —
 * never let a masked config/write error fake a result on a live power path). */
static void chk(const char *what, int ret, bool *ok)
{
	if (ret != 0) {
		printk("  POWER: %s failed: %d\n", what, ret);
		*ok = false;
	}
}

/* Sample GPIOH2 n times at ~1 s spacing, printing each, and return the OR of all
 * samples (1 if it was ever high). Lets us watch STA_LINE_POWER settle after a
 * transition instead of reading it once too early. A negative read (errno) flags
 * *ok false rather than being silently treated as "not high". */
static int h2_trajectory(const struct device *efgh, const char *phase, int n,
			 bool *ok)
{
	int seen = 0;

	for (int i = 0; i < n; i++) {
		int v;

		busy_delay();
		v = gpio_pin_get_raw(efgh, PIN_H2);
		if (v < 0) {
			printk("  POWER: H2 read %s failed: %d\n", phase, v);
			*ok = false;
			v = 0;
		}
		seen |= (v == 1);
		printk("  H2 %s t+%ds = %d\n", phase, i + 1, v);
	}
	return seen;
}

int main(void)
{
	const struct device *abcd = DEVICE_DT_GET(GPIO_ABCD);
	const struct device *efgh = DEVICE_DT_GET(GPIO_EFGH);
	int h2_start, on_seen, off_seen;
	bool io_ok = true;

	if (!device_is_ready(abcd) || !device_is_ready(efgh)) {
		printk("POWER smoke: gpio device(s) not ready\n");
		return 0;
	}

	/* Feedback line: STA_LINE_POWER as input. */
	chk("cfg H2 input", gpio_pin_configure(efgh, PIN_H2, GPIO_INPUT), &io_ok);
	h2_start = gpio_pin_get_raw(efgh, PIN_H2);
	if (h2_start < 0) {
		printk("  POWER: H2 start read failed: %d\n", h2_start);
		io_ok = false;
		h2_start = -1;
	}
	printk("POWER: H2 start=%d\n", h2_start);

	/* Reclaim A4 and drive it high = BMC in control. */
	reclaim_a4();
	chk("cfg A4", gpio_pin_configure(abcd, PIN_A4, GPIO_OUTPUT_HIGH), &io_ok);

	/* De-assert all three active-low request lines (drive high). */
	chk("cfg F0", gpio_pin_configure(efgh, PIN_F0, GPIO_OUTPUT_HIGH), &io_ok);
	chk("cfg B6", gpio_pin_configure(abcd, PIN_B6, GPIO_OUTPUT_HIGH), &io_ok);
	chk("cfg B1", gpio_pin_configure(abcd, PIN_B1, GPIO_OUTPUT_HIGH), &io_ok);

	/* Power-ON: pulse reset + power-up low, hold, release (kgpe-power.sh on). */
	chk("B6=0", gpio_pin_set_raw(abcd, PIN_B6, 0), &io_ok);
	chk("B1=0", gpio_pin_set_raw(abcd, PIN_B1, 0), &io_ok);
	busy_delay();
	chk("B6=1", gpio_pin_set_raw(abcd, PIN_B6, 1), &io_ok);
	chk("B1=1", gpio_pin_set_raw(abcd, PIN_B1, 1), &io_ok);
	on_seen = h2_trajectory(efgh, "post-ON ", 3, &io_ok);

	/* Force-OFF: pulse power-down low, release (kgpe-power.sh off). Restores the
	 * host to OFF and lets us watch whether STA_LINE_POWER falls. */
	chk("F0=0", gpio_pin_set_raw(efgh, PIN_F0, 0), &io_ok);
	busy_delay();
	chk("F0=1", gpio_pin_set_raw(efgh, PIN_F0, 1), &io_ok);
	off_seen = h2_trajectory(efgh, "post-OFF", 6, &io_ok);

	/* Two things to learn: does force-OFF drive the real PSU off (checked out of
	 * band via the au-plug W draw), and does GPIOH2 TRACK the power state. PASS
	 * requires the full documented trajectory 0 (found off) -> 1 (after ON) -> 0
	 * (after OFF) AND every GPIO op to have succeeded — if H2 was already high at
	 * start we cannot claim the power-ON control worked, and a masked I/O error
	 * must not fake a PASS. If H2 stays high across a real power-down it senses a
	 * standby rail, not host-on (see #162).
	 */
	printk("POWER: io_ok=%d H2 start=%d ever-high post-ON=%d post-OFF=%d\n",
	       io_ok, h2_start, on_seen, off_seen);
	if (io_ok && h2_start == 0 && on_seen && !off_seen) {
		printk("POWER RESULT: PASS (GPIOH2 tracks host power)\n");
	} else {
		printk("POWER RESULT: FAIL (io_ok=%d start=%d on=%d off=%d)\n",
		       io_ok, h2_start, on_seen, off_seen);
	}

	return 0;
}
