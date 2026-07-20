/*
 * ASPEED AST2050 (G3) GPIO controller driver for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal but functional GPIO driver for the AST2050 (ARM926EJ-S, G3 legacy
 * register layout) BMC SoC. The controller lives at 0x1E780000 and groups its
 * pins into 32-pin "sets" (ABCD, EFGH, ...). Because a Zephyr GPIO port is a
 * single 32-bit word, each set is one devicetree node / one Zephyr GPIO port,
 * whose "reg" points directly at that set's data-value register:
 *
 *     data value  = reg + 0x00   (Rd: input level, Wr: output write latch)
 *     direction   = reg + 0x04   (0 = input, 1 = output)
 *
 * Register offsets taken from the QEMU G3/AST2400 model
 * hw/gpio/aspeed_gpio.c (the AST2050 shares this layout), cross-checked against
 * the Linux gpio-aspeed.c bank table:
 *
 *   QEMU aspeed_gpio.c: GPIO_ABCD_DATA_VALUE (0x000), GPIO_ABCD_DIRECTION
 *   (0x004) at lines 72-73; the per-set data/direction pairs for EFGH (0x020/
 *   0x024, lines 80-81), IJKL (0x070/0x074, lines 99-100), MNOP (0x078/0x07C,
 *   lines 101-102), QRST (0x080/0x084, lines 103-104), UVWX (0x088/0x08C, lines
 *   105-106) and YZAAAB (0x1E0/0x1E4, lines 183-184). The GPIO_VAL_VALUE (0x00)
 *   / GPIO_VAL_DIR (0x04) split within each bank matches Linux gpio-aspeed.c
 *   lines 190-191, and the bank base addresses match its aspeed_gpio_banks[]
 *   table (lines 99-172).
 *
 * MMIO is reached at its PHYSICAL address via the static identity MMU region
 * added in soc/aspeed_g3/ast2050/soc.c (mirroring the UART/VIC/timer regions). We
 * deliberately do NOT use the DEVICE_MMIO_MAP path: under CONFIG_MMU on this
 * brand-new ARM926 arm_mmu, z_phys_map returns a virtual base the MMU does not
 * translate back to 0x1E780000 (see the console.c comment for the same issue).
 *
 * Reads/writes are 32-bit (sys_read32/sys_write32): the QEMU model only accepts
 * 4-byte accesses (aspeed_gpio_ops.valid.min/max_access_size = 4).
 *
 * Output writes go through a per-bank software shadow of the write latch (the
 * "dcache" pattern from Linux gpio-aspeed.c): the data-value register reads back
 * the *input-sampled* line level, not the last-written value (aspeed_gpio.c /
 * gpio-aspeed.c note at lines 83-92), so a naive read-modify-write of that
 * register could momentarily disturb sibling output pins. Shadowing the latch
 * avoids that.
 *
 * Interrupts (#177): edge/level GPIO interrupts via the per-bank GPIO_*_INT_*
 * registers wired to the single G3 VIC source 20 (soc/aspeed_g3/ast2050/vic.c).
 * pin_interrupt_configure / manage_callback / get_pending_int are implemented;
 * because the whole controller shares ONE VIC source across all sets, a single
 * shared ISR (with a per-set registry) services them and W1C-clears INT_STATUS.
 */

#define DT_DRV_COMPAT aspeed_ast2050_gpio

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/gpio/gpio_utils.h> /* GPIO_PORT_PIN_MASK_FROM_DT_INST */
#include <zephyr/irq.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/sys/util.h>

/* Per-bank register offsets from the node's reg base (the data-value reg). */
#define GPIO_G3_DATA       0x00U /* Rd: input level, Wr: output write latch */
#define GPIO_G3_DIR        0x04U /* 0 = input, 1 = output */
/*
 * Per-set interrupt registers (offsets from the set's data-value reg base, so
 * ABCD INT_STATUS = 0x018, EFGH = 0x038, ... matching hw/gpio/aspeed_gpio.c).
 * int_trigger = INT_SENS_2:1:0 selects the condition (aspeed_evaluate_irq):
 *   0 falling edge · 1 rising edge · 2 level-low · 3 level-high · >=4 both edges.
 * INT_STATUS is write-1-to-clear.
 */
#define GPIO_G3_INT_ENABLE 0x08U
#define GPIO_G3_INT_SENS_0 0x0CU
#define GPIO_G3_INT_SENS_1 0x10U
#define GPIO_G3_INT_SENS_2 0x14U
#define GPIO_G3_INT_STATUS 0x18U

/*
 * The WHOLE GPIO controller raises ONE VIC source (20, "GPIO hi-level", memory
 * map §10) for all sets — not one per set. So a single shared ISR services
 * every set (registry below), and the ISR clears INT_STATUS (W1C) to de-assert
 * the level source.
 */
#define GPIO_G3_IRQ      20
#define GPIO_G3_IRQ_PRIO 0

/* One Aspeed "set" is a single 32-bit Zephyr GPIO port. */
#define GPIO_G3_PINS_PER_BANK 32U

struct gpio_aspeed_g3_config {
	/* gpio_driver_config must be first (carries port_pin_mask). */
	struct gpio_driver_config common;
	mem_addr_t base;
};

struct gpio_aspeed_g3_data {
	/* gpio_driver_data must be first. */
	struct gpio_driver_data common;
	struct k_spinlock lock;
	/* Software shadow of the output write latch for this bank. */
	uint32_t out_shadow;
	/* Registered interrupt callbacks for this set. */
	sys_slist_t callbacks;
};

/*
 * Shared-ISR registry: one VIC source (20) covers all GPIO sets, but each set
 * is a separate Zephyr device, so a naive per-instance IRQ_CONNECT would drop
 * one set's interrupts. Every set registers here at init; the single ISR
 * services whichever set(s) latched a pending interrupt.
 */
#define GPIO_G3_MAX_SETS 8
static const struct device *gpio_g3_isr_devs[GPIO_G3_MAX_SETS];
static uint8_t gpio_g3_isr_count;
static bool gpio_g3_irq_connected;

static void gpio_aspeed_g3_isr(const void *unused)
{
	ARG_UNUSED(unused);

	for (uint8_t i = 0U; i < gpio_g3_isr_count; i++) {
		const struct device *dev = gpio_g3_isr_devs[i];
		const struct gpio_aspeed_g3_config *cfg = dev->config;
		struct gpio_aspeed_g3_data *data = dev->data;
		uint32_t status = sys_read32(cfg->base + GPIO_G3_INT_STATUS);

		if (status != 0U) {
			/* W1C the serviced bits (de-asserts the level VIC source), then
			 * dispatch — clear-before-dispatch so an edge that re-fires during
			 * the callback is not lost.
			 */
			sys_write32(status, cfg->base + GPIO_G3_INT_STATUS);
			gpio_fire_callbacks(&data->callbacks, dev, status);
		}
	}
}

static int gpio_aspeed_g3_pin_configure(const struct device *dev,
					gpio_pin_t pin, gpio_flags_t flags)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;
	struct gpio_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key;
	uint32_t mask;
	uint32_t dir;

	if (pin >= GPIO_G3_PINS_PER_BANK) {
		return -EINVAL; /* bounds-check BEFORE BIT(pin) (shift-UB if >= 32) */
	}
	mask = BIT(pin);

	/* This minimal model exposes no internal pull resistors and no
	 * open-drain / open-source (single-ended) output stage.
	 */
	if (flags & (GPIO_PULL_UP | GPIO_PULL_DOWN)) {
		return -ENOTSUP;
	}
	if (flags & GPIO_SINGLE_ENDED) {
		return -ENOTSUP;
	}

	key = k_spin_lock(&data->lock);
	dir = sys_read32(cfg->base + GPIO_G3_DIR);

	if (flags & GPIO_OUTPUT) {
		if (flags & GPIO_OUTPUT_INIT_HIGH) {
			data->out_shadow |= mask;
		} else if (flags & GPIO_OUTPUT_INIT_LOW) {
			data->out_shadow &= ~mask;
		}
		/*
		 * Direction first (make it an output), THEN the value: the G3
		 * controller only latches a data-value write into the pad once the
		 * pin is an output. This matches the QEMU model, whose direction
		 * write re-runs the update using the current data_value, so the
		 * value must be written after the pin is already an output for the
		 * requested init level to appear on read-back.
		 */
		sys_write32(dir | mask, cfg->base + GPIO_G3_DIR);
		sys_write32(data->out_shadow, cfg->base + GPIO_G3_DATA);
	} else {
		/* Input, or "disconnected": there is no tri-state, so park the
		 * pin as an input (its output latch is left untouched).
		 */
		sys_write32(dir & ~mask, cfg->base + GPIO_G3_DIR);
	}

	k_spin_unlock(&data->lock, key);
	return 0;
}

static int gpio_aspeed_g3_port_get_raw(const struct device *dev,
				       gpio_port_value_t *value)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;

	/* Data-value register returns the input-sampled level of every pin
	 * (for outputs this reflects the driven value once settled).
	 */
	*value = sys_read32(cfg->base + GPIO_G3_DATA);
	return 0;
}

static int gpio_aspeed_g3_port_set_masked_raw(const struct device *dev,
					      gpio_port_pins_t mask,
					      gpio_port_value_t value)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;
	struct gpio_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key = k_spin_lock(&data->lock);

	data->out_shadow = (data->out_shadow & ~mask) | (value & mask);
	sys_write32(data->out_shadow, cfg->base + GPIO_G3_DATA);

	k_spin_unlock(&data->lock, key);
	return 0;
}

static int gpio_aspeed_g3_port_set_bits_raw(const struct device *dev,
					    gpio_port_pins_t pins)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;
	struct gpio_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key = k_spin_lock(&data->lock);

	data->out_shadow |= pins;
	sys_write32(data->out_shadow, cfg->base + GPIO_G3_DATA);

	k_spin_unlock(&data->lock, key);
	return 0;
}

static int gpio_aspeed_g3_port_clear_bits_raw(const struct device *dev,
					      gpio_port_pins_t pins)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;
	struct gpio_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key = k_spin_lock(&data->lock);

	data->out_shadow &= ~pins;
	sys_write32(data->out_shadow, cfg->base + GPIO_G3_DATA);

	k_spin_unlock(&data->lock, key);
	return 0;
}

static int gpio_aspeed_g3_port_toggle_bits(const struct device *dev,
					   gpio_port_pins_t pins)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;
	struct gpio_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key = k_spin_lock(&data->lock);

	data->out_shadow ^= pins;
	sys_write32(data->out_shadow, cfg->base + GPIO_G3_DATA);

	k_spin_unlock(&data->lock, key);
	return 0;
}

static int gpio_aspeed_g3_pin_interrupt_configure(const struct device *dev,
						  gpio_pin_t pin,
						  enum gpio_int_mode mode,
						  enum gpio_int_trig trig)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;
	struct gpio_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key;
	uint32_t bit;
	int sens; /* ASPEED int_trigger (SENS_2:1:0); -1 = disable */

	if (pin >= GPIO_G3_PINS_PER_BANK) {
		return -EINVAL; /* bounds-check before BIT(pin) (shift-UB if >= 32) */
	}
	bit = BIT(pin);

	if (mode == GPIO_INT_MODE_DISABLED) {
		sens = -1;
	} else if (mode == GPIO_INT_MODE_EDGE) {
		switch (trig) {
		case GPIO_INT_TRIG_LOW:  sens = 0; break; /* falling edge */
		case GPIO_INT_TRIG_HIGH: sens = 1; break; /* rising edge  */
		case GPIO_INT_TRIG_BOTH: sens = 4; break; /* both edges   */
		default: return -ENOTSUP;
		}
	} else { /* GPIO_INT_MODE_LEVEL */
		switch (trig) {
		case GPIO_INT_TRIG_LOW:  sens = 2; break; /* level low  */
		case GPIO_INT_TRIG_HIGH: sens = 3; break; /* level high */
		default: return -ENOTSUP;
		}
	}

	key = k_spin_lock(&data->lock);
	if (sens < 0) {
		sys_write32(sys_read32(cfg->base + GPIO_G3_INT_ENABLE) & ~bit,
			    cfg->base + GPIO_G3_INT_ENABLE);
		/*
		 * Also clear any already-latched status for this pin (symmetry with
		 * the enable path's stale-latch discard below). INT_STATUS and
		 * INT_ENABLE are independent: gating ENABLE does not retroactively
		 * clear a latched bit, so without this a sibling pin's later
		 * interrupt would re-deliver this disabled pin (the shared ISR
		 * reads/clears/dispatches the whole INT_STATUS word).
		 */
		sys_write32(bit, cfg->base + GPIO_G3_INT_STATUS);
	} else {
		uint32_t s0 = sys_read32(cfg->base + GPIO_G3_INT_SENS_0);
		uint32_t s1 = sys_read32(cfg->base + GPIO_G3_INT_SENS_1);
		uint32_t s2 = sys_read32(cfg->base + GPIO_G3_INT_SENS_2);

		s0 = ((sens & 1) != 0) ? (s0 | bit) : (s0 & ~bit);
		s1 = ((sens & 2) != 0) ? (s1 | bit) : (s1 & ~bit);
		s2 = ((sens & 4) != 0) ? (s2 | bit) : (s2 & ~bit);
		sys_write32(s0, cfg->base + GPIO_G3_INT_SENS_0);
		sys_write32(s1, cfg->base + GPIO_G3_INT_SENS_1);
		sys_write32(s2, cfg->base + GPIO_G3_INT_SENS_2);
		/* Discard any stale latch for this pin, then enable it. */
		sys_write32(bit, cfg->base + GPIO_G3_INT_STATUS);
		sys_write32(sys_read32(cfg->base + GPIO_G3_INT_ENABLE) | bit,
			    cfg->base + GPIO_G3_INT_ENABLE);
	}
	k_spin_unlock(&data->lock, key);
	return 0;
}

static int gpio_aspeed_g3_manage_callback(const struct device *dev,
					  struct gpio_callback *cb, bool set)
{
	struct gpio_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key;
	int ret;

	/*
	 * Take data->lock (which masks the shared GPIO IRQ on this single-core
	 * target) so the multi-step slist mutation in gpio_manage_callback cannot
	 * be preempted by the shared ISR walking the SAME list via
	 * gpio_fire_callbacks — every other accessor in this driver relies on the
	 * same lock to exclude the ISR.
	 */
	key = k_spin_lock(&data->lock);
	ret = gpio_manage_callback(&data->callbacks, cb, set);
	k_spin_unlock(&data->lock, key);
	return ret;
}

static uint32_t gpio_aspeed_g3_get_pending_int(const struct device *dev)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;

	return sys_read32(cfg->base + GPIO_G3_INT_STATUS);
}

static const struct gpio_driver_api gpio_aspeed_g3_api = {
	.pin_configure = gpio_aspeed_g3_pin_configure,
	.port_get_raw = gpio_aspeed_g3_port_get_raw,
	.port_set_masked_raw = gpio_aspeed_g3_port_set_masked_raw,
	.port_set_bits_raw = gpio_aspeed_g3_port_set_bits_raw,
	.port_clear_bits_raw = gpio_aspeed_g3_port_clear_bits_raw,
	.port_toggle_bits = gpio_aspeed_g3_port_toggle_bits,
	.pin_interrupt_configure = gpio_aspeed_g3_pin_interrupt_configure,
	.manage_callback = gpio_aspeed_g3_manage_callback,
	.get_pending_int = gpio_aspeed_g3_get_pending_int,
};

static int gpio_aspeed_g3_init(const struct device *dev)
{
	const struct gpio_aspeed_g3_config *cfg = dev->config;
	struct gpio_aspeed_g3_data *data = dev->data;

	/*
	 * The fixed base+0x08/0x0C/0x10/0x14/0x18 interrupt-register offsets used
	 * throughout this driver are ONLY correct for the ABCD (0x1E780000) and
	 * EFGH (0x1E780020) GPIO sets — the only two the AST2050 (G3) has. On the
	 * larger ASPEED parts (G4+) the IJKL/MNOP/... sets place their interrupt
	 * registers at NON-uniform offsets, so base+0x08 there would alias a
	 * neighbouring set's DATA/DIRECTION register and silently corrupt unrelated
	 * output pins. Refuse to bind to any other base so a mis-added DT node (or a
	 * copy-paste onto a G4 SoC) fails at init instead of corrupting hardware.
	 */
	if (cfg->base != (mem_addr_t)0x1E780000U &&
	    cfg->base != (mem_addr_t)0x1E780020U) {
		__ASSERT(false, "gpio_aspeed_g3: base %#lx unsupported — only the ABCD"
			 " (0x1E780000)/EFGH(0x1E780020) sets have the assumed int-reg"
			 " layout", (unsigned long)cfg->base);
		return -ENOTSUP;
	}

	/*
	 * Seed the output shadow from the current data-value register so a later
	 * read-modify-write set/clear preserves any output bits the loader
	 * (U-Boot / the QEMU machine) already configured.
	 */
	data->out_shadow = sys_read32(cfg->base + GPIO_G3_DATA);

	/* Mask all interrupts for this set until a caller configures a pin. */
	sys_write32(0U, cfg->base + GPIO_G3_INT_ENABLE);

	/* Register this set for the single shared GPIO ISR, and connect the one
	 * VIC source (20) exactly once across all sets. */
	if (gpio_g3_isr_count < GPIO_G3_MAX_SETS) {
		gpio_g3_isr_devs[gpio_g3_isr_count++] = dev;
	}
	if (!gpio_g3_irq_connected) {
		IRQ_CONNECT(GPIO_G3_IRQ, GPIO_G3_IRQ_PRIO, gpio_aspeed_g3_isr, NULL, 0);
		irq_enable(GPIO_G3_IRQ);
		gpio_g3_irq_connected = true;
	}
	return 0;
}

#define GPIO_ASPEED_G3_INIT(inst)                                              \
	static struct gpio_aspeed_g3_data gpio_aspeed_g3_data_##inst;           \
	static const struct gpio_aspeed_g3_config gpio_aspeed_g3_config_##inst = { \
		.common = {                                                    \
			.port_pin_mask =                                       \
				GPIO_PORT_PIN_MASK_FROM_DT_INST(inst),         \
		},                                                             \
		.base = (mem_addr_t)DT_INST_REG_ADDR(inst),                    \
	};                                                                     \
	DEVICE_DT_INST_DEFINE(inst, gpio_aspeed_g3_init, NULL,                  \
			      &gpio_aspeed_g3_data_##inst,                     \
			      &gpio_aspeed_g3_config_##inst, POST_KERNEL,      \
			      CONFIG_GPIO_INIT_PRIORITY, &gpio_aspeed_g3_api);

DT_INST_FOREACH_STATUS_OKAY(GPIO_ASPEED_G3_INIT)
