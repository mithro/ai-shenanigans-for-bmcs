/*
 * AST2050 (G3) GPIO INTERRUPT smoke test — DEVICE-MATRIX rows 27-33 (edge/level
 * interrupt sub-capability, #177).
 * SPDX-License-Identifier: Apache-2.0
 *
 * Proves the Zephyr GPIO driver's interrupt path (per-bank INT regs → the single
 * G3 VIC source 20 → shared ISR → gpio callback) works end to end. It configures
 * GPIOH2 (STA_LINE_POWER, gpio1/EFGH pin 26) for an edge interrupt, registers a
 * callback, then drives the host power ON so GPIOH2 transitions 0→1 and the
 * interrupt fires.
 *
 * GPIOH2 is an INPUT the QEMU kgpe-d16 pwrseq latch drives (0 = host off,
 * 1 = powered), so powering the host on is a clean, deterministic input edge to
 * trip the interrupt with — no external stimulus needed. The same power-sequence
 * GPIOs as power_smoke/spd_smoke bring the host up.
 *
 * PASS = the GPIO callback fired with GPIOH2 in its pin mask (so the driver
 * programmed INT_SENS/INT_ENABLE, the model raised VIC 20 on the edge, the shared
 * ISR read INT_STATUS + dispatched, and the callback ran). On real silicon the
 * same edge is produced by the PSU actually coming up (host-gated).
 */

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/sys/util.h>

#define GPIO_ABCD DT_NODELABEL(gpio0)
#define GPIO_EFGH DT_NODELABEL(gpio1)

#define PIN_A4 4    /* gpio0: BMC-in-control */
#define PIN_B1 9    /* gpio0: power-up#      */
#define PIN_B6 14   /* gpio0: reset#         */
#define PIN_F0 8    /* gpio1: force-off#     */
#define PIN_H2 26   /* gpio1: STA_LINE_POWER (in, the interrupt source) */

#define SCU_BASE         0x1E6E2000U
#define SCU_PROT_KEY     0x00U
#define SCU_MFP_CTL1     0x74U
#define SCU_UNLOCK_MAGIC 0x1688A8A8U
#define SCU74_A4_PHYLINK BIT(25)

#define PULSE_US 200000

BUILD_ASSERT(DT_NODE_HAS_STATUS(GPIO_ABCD, okay), "gpio0 must be enabled");
BUILD_ASSERT(DT_NODE_HAS_STATUS(GPIO_EFGH, okay), "gpio1 must be enabled");

static volatile int h2_irq_count;
static volatile gpio_port_pins_t h2_irq_pins;
static struct gpio_callback h2_cb;

static void h2_edge_cb(const struct device *dev, struct gpio_callback *cb,
		       gpio_port_pins_t pins)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(cb);
	h2_irq_count++;
	h2_irq_pins |= pins;
}

static void reclaim_a4(void)
{
	uint32_t v;

	sys_write32(SCU_UNLOCK_MAGIC, SCU_BASE + SCU_PROT_KEY);
	v = sys_read32(SCU_BASE + SCU_MFP_CTL1);
	sys_write32(v & ~SCU74_A4_PHYLINK, SCU_BASE + SCU_MFP_CTL1);
}

int main(void)
{
	const struct device *abcd = DEVICE_DT_GET(GPIO_ABCD);
	const struct device *efgh = DEVICE_DT_GET(GPIO_EFGH);
	int ret, h2_before, h2_after;
	bool pass;

	printk("GPIO-IRQ smoke: boot\n");

	if (!device_is_ready(abcd) || !device_is_ready(efgh)) {
		printk("GPIO-IRQ: gpio device(s) not ready\n");
		return 0;
	}

	/* Arm GPIOH2 as an edge-interrupt input BEFORE the host powers on. */
	ret = gpio_pin_configure(efgh, PIN_H2, GPIO_INPUT);
	if (ret != 0) {
		printk("GPIO-IRQ: cfg H2 input failed %d\n", ret);
		return 0;
	}
	gpio_init_callback(&h2_cb, h2_edge_cb, BIT(PIN_H2));
	ret = gpio_add_callback(efgh, &h2_cb);
	if (ret != 0) {
		printk("GPIO-IRQ: add_callback failed %d\n", ret);
		return 0;
	}
	ret = gpio_pin_interrupt_configure(efgh, PIN_H2, GPIO_INT_EDGE_BOTH);
	if (ret != 0) {
		printk("GPIO-IRQ: pin_interrupt_configure failed %d (interrupts unsupported?)\n", ret);
		return 0;
	}
	h2_before = gpio_pin_get_raw(efgh, PIN_H2);

	/* Power the host ON so GPIOH2 transitions 0 -> 1 (the interrupt edge). */
	reclaim_a4();
	gpio_pin_configure(abcd, PIN_A4, GPIO_OUTPUT_HIGH);
	gpio_pin_configure(efgh, PIN_F0, GPIO_OUTPUT_HIGH);
	gpio_pin_configure(abcd, PIN_B6, GPIO_OUTPUT_HIGH);
	gpio_pin_configure(abcd, PIN_B1, GPIO_OUTPUT_HIGH);

	gpio_pin_set_raw(abcd, PIN_B6, 0);
	gpio_pin_set_raw(abcd, PIN_B1, 0);
	k_busy_wait(PULSE_US);
	gpio_pin_set_raw(abcd, PIN_B6, 1);
	gpio_pin_set_raw(abcd, PIN_B1, 1);
	k_busy_wait(PULSE_US);

	h2_after = gpio_pin_get_raw(efgh, PIN_H2);

	printk("GPIO-IRQ: H2 %d->%d, callbacks=%d pins=0x%08x\n",
	       h2_before, h2_after, h2_irq_count, (uint32_t)h2_irq_pins);

	/*
	 * PASS = the callback fired at least once AND its pin mask includes H2.
	 * (h2_after==1 corroborates the host powered on; the load-bearing check is
	 * that the EDGE produced an interrupt + callback.)
	 */
	pass = (h2_irq_count > 0) && ((h2_irq_pins & BIT(PIN_H2)) != 0U);

	/* Restore: force host OFF, disarm the interrupt. */
	gpio_pin_interrupt_configure(efgh, PIN_H2, GPIO_INT_DISABLE);
	gpio_pin_set_raw(efgh, PIN_F0, 0);
	k_busy_wait(PULSE_US);
	gpio_pin_set_raw(efgh, PIN_F0, 1);

	printk("GPIO-IRQ RESULT: %s\n", pass ? "PASS" : "FAIL");
	return 0;
}
