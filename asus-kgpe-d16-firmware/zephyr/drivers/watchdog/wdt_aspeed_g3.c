/*
 * ASPEED AST2050 (G3) watchdog timer driver for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal but functional watchdog driver for the AST2050 (ARM926EJ-S, G3 legacy
 * register layout) BMC SoC. The AST2050 integrates ONE 32-bit programmable WDT
 * at 0x1E785000 (the AST2400/G4 grew a second at 0x1E785020; the kgpe-d16-bmc
 * QEMU SoC models wdts_num = 1 - hw/arm/aspeed_ast2400.c line 958). It is a
 * down-counter that, on reaching zero, resets the SoC.
 *
 * The 0x20-byte register block and its offsets come from the QEMU G3/AST2400
 * model hw/watchdog/wdt_aspeed.c, cross-checked against the vendor hwreg.h
 * (AST_WDT_BASE 0x1E785000) and the project WDT analysis
 * (qemu-model/peripherals/wdt/DOC.md):
 *
 *   WDT_STATUS       0x00  R  current down-counter        (wdt_aspeed.c line 23)
 *   WDT_RELOAD_VALUE 0x04  RW value reloaded into counter (wdt_aspeed.c line 24)
 *   WDT_RESTART      0x08  W  write magic to reload/kick  (wdt_aspeed.c line 25)
 *   WDT_CTRL         0x0C  RW control                     (wdt_aspeed.c line 26)
 *
 * WDT_CTRL bits (wdt_aspeed.c lines 27-33; DOC.md section 1):
 *   [0] ENABLE                      (BIT(0),  line 33)
 *   [1] RESET_SYSTEM (reset on t/o) (BIT(1),  line 32)
 *   [2] WDT_INTR                    (BIT(2),  line 31)
 *   [3] WDT_EXT                     (BIT(3),  line 30)
 *   [4] 1MHZ_CLK (0 = PCLK, 1 = 1 MHz reference)  (BIT(4), line 29)
 *   [6:5] reset mode: 0b00 = SoC, 0b01 = full-chip (0x1<<5, lines 27-28)
 *
 * Kick / restart magic 0x4755 (wdt_aspeed.c line 53 WDT_RESTART_MAGIC; hwreg.h
 * WDT_CNT_RESTART_REG; fwtest.c WDT_MAGIC). Writing it to WDT_RESTART reloads
 * the counter from WDT_RELOAD_VALUE and (if enabled) re-arms the timer
 * (wdt_aspeed.c lines 176-181).
 *
 * CLOCK SOURCE - we set the 1 MHz reference (WDT_CTRL[4] = 1), NOT PCLK. This is
 * deliberate and makes the timeout PCLK-INDEPENDENT and identical in QEMU and on
 * silicon:
 *   - QEMU's aspeed_wdt_reload() uses `reload_ns = RELOAD * 1000` when CTRL[4] is
 *     set (wdt_aspeed.c lines 120-125), i.e. 1 count = 1 us, regardless of the
 *     modelled pclk_freq. In the PCLK path it instead divides by pclk_freq, which
 *     QEMU HARDCODES to 24 MHz (PCLK_HZ, line 283/299) - but the real AST2050
 *     PCLK is 66 MHz (the reload reset value 0x03EF1480 = 66,000,000 = 1 s @66 MHz,
 *     DOC.md/DATASHEET-TIMER.md), a known ~2.75x rate error (task #55). Choosing
 *     the 1 MHz reference sidesteps that entirely.
 * So reload = timeout_ms * 1000 gives the requested timeout on BOTH targets.
 * (The Raptor U-Boot uses CTRL = 0x23 = ENABLE|RESET_SYSTEM|full-chip on the PCLK
 * clock; we use 0x33 = that value | 1MHZ_CLK. The reset-system + full-chip choice
 * mirrors Raptor; the added 1 MHz bit is the only difference.)
 *
 * QEMU reset path: at timer expiry aspeed_wdt_timer_expired() calls
 * watchdog_perform_action() UNLESS SCU reg 0x04 bit0 (SDRAM reset) is set
 * (wdt_aspeed.c lines 265-281). That bit is clear in the G3 SCU reset default
 * (0x000FFE5C), so the fire path is live and no SCU touch is needed here (unlike
 * the I2C block, the WDT is not held in a SoC reset domain). With QEMU's default
 * watchdog action (reset) and NO -no-reboot, that reboots the machine and Zephyr
 * runs from the top again.
 *
 * MMIO is reached at its PHYSICAL address via the static identity MMU region
 * added in soc/aspeed_g3/ast2050/soc.c ("wdt" 0x1e785000), mirroring the UART/VIC/
 * timer/GPIO/I2C regions. We deliberately do NOT use the DEVICE_MMIO_MAP path:
 * under CONFIG_MMU on this brand-new ARM926 arm_mmu, z_phys_map returns a virtual
 * base the MMU does not translate back (see the console.c / gpio_aspeed_g3.c /
 * i2c_aspeed_g3.c comments). All accesses are 32-bit sys_read32/sys_write32 (the
 * QEMU model only accepts 4-byte accesses, aspeed_wdt_ops.valid.min/max = 4).
 *
 * HOUSE RULE (learned from the GPIO build): the API type + config macros used in
 * the static initializer (struct wdt_driver_api, DEVICE_DT_INST_DEFINE,
 * WDT_FLAG_*, the wdt_timeout_cfg layout) all come from
 * <zephyr/drivers/watchdog.h>, which is #included below.
 *
 * Follow-ups (not implemented): the pre-timeout interrupt callback via WDT_CTRL[2]
 * (WDT_INTR) wired to the G3 VIC (soc/aspeed_g3/ast2050/vic.c) - so install_timeout
 * rejects a non-NULL callback; the windowed (min > 0) lower bound; reset-width /
 * external-reset (WDT18) pulse shaping; per-target reset-scope selection.
 */

#define DT_DRV_COMPAT aspeed_ast2050_wdt

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/watchdog.h>
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/sys/util.h>

/* Register offsets from the node's reg base (wdt_aspeed.c lines 23-26). */
#define WDT_G3_STATUS       0x00U /* R: current down-counter */
#define WDT_G3_RELOAD_VALUE 0x04U /* RW: value reloaded into the counter */
#define WDT_G3_RESTART      0x08U /* W: write the magic to reload/kick */
#define WDT_G3_CTRL         0x0CU /* RW: control */

/* WDT_CTRL bits (wdt_aspeed.c lines 27-33; DOC.md section 1). */
#define WDT_G3_CTRL_ENABLE               BIT(0)      /* line 33 */
#define WDT_G3_CTRL_RESET_SYSTEM         BIT(1)      /* line 32 */
#define WDT_G3_CTRL_WDT_INTR             BIT(2)      /* line 31: IRQ instead of reset */
#define WDT_G3_CTRL_1MHZ_CLK             BIT(4)      /* line 29: 1 = 1 MHz ref */
#define WDT_G3_CTRL_RESET_MODE_FULL_CHIP (0x1U << 5) /* line 28 */

/*
 * Run value (reset mode): enable + reset-on-timeout + full-chip reset mode + 1
 * MHz clock. = 0x33 = Raptor U-Boot's 0x23 (ENABLE|RESET_SYSTEM|full-chip on
 * PCLK) plus the 1MHZ_CLK bit (see file header, CLOCK SOURCE).
 */
#define WDT_G3_CTRL_RUN                                                         \
	(WDT_G3_CTRL_ENABLE | WDT_G3_CTRL_RESET_SYSTEM |                        \
	 WDT_G3_CTRL_1MHZ_CLK | WDT_G3_CTRL_RESET_MODE_FULL_CHIP)
BUILD_ASSERT(WDT_G3_CTRL_RUN == 0x33U, "G3 WDT run control must be 0x33");

/*
 * Run value (interrupt mode, WDT_CTRL[2]): enable + WDT_INTR + 1 MHz clock, NO
 * reset bits. Per the QEMU model (hw/watchdog/wdt_aspeed.c) and datasheet §27,
 * on expiry with WDT_INTR set the WDT raises its interrupt (G3 VIC source 27)
 * INSTEAD of resetting — a one-shot warning. = 0x15.
 */
#define WDT_G3_CTRL_RUN_INTR                                                    \
	(WDT_G3_CTRL_ENABLE | WDT_G3_CTRL_WDT_INTR | WDT_G3_CTRL_1MHZ_CLK)
BUILD_ASSERT(WDT_G3_CTRL_RUN_INTR == 0x15U, "G3 WDT intr-mode control must be 0x15");

/*
 * WDT timeout interrupt = G3 VIC source 27 (memory map §10; edge/rising in the
 * RE'd G3 VIC map, soc/aspeed_g3/ast2050/vic.c — like the timer source 16).
 * Hardcoded like the GPIO (20) / RTC-alarm (26) sources: the G3 VIC is not a DT
 * interrupt-controller, so IRQs are connected by number. The framework
 * z_soc_irq_eoi() clears the latched edge.
 */
#define WDT_G3_IRQ       27
#define WDT_G3_IRQ_PRIO  0

/* Restart/kick magic (wdt_aspeed.c line 53; hwreg.h; fwtest.c). */
#define WDT_G3_RESTART_MAGIC 0x4755U

/*
 * 1 MHz clock source: 1 counter tick = 1 us, so reload = timeout_ms * 1000. This
 * holds in QEMU (RELOAD * 1000 ns, wdt_aspeed.c lines 123-124) and on silicon
 * (real 1 MHz reference), independent of the PCLK rate.
 */
#define WDT_G3_TICKS_PER_MS 1000U

struct wdt_aspeed_g3_config {
	mem_addr_t base;
};

struct wdt_aspeed_g3_data {
	struct k_spinlock lock;
	uint32_t reload_ticks; /* programmed into WDT_RELOAD_VALUE by setup() */
	bool installed;
	bool enabled;
	bool interrupt_mode;   /* true: fire VIC-27 IRQ (WDT_INTR) instead of reset */
	wdt_callback_t callback; /* pre-timeout callback, interrupt mode only */
};

/* Single WDT instance; the ISR recovers the device from this file-static (set in
 * init before irq_enable), mirroring the GPIO/RTC drivers. */
static const struct device *wdt_g3_isr_dev;

static int wdt_aspeed_g3_install_timeout(const struct device *dev,
					 const struct wdt_timeout_cfg *cfg)
{
	struct wdt_aspeed_g3_data *data = dev->data;
	uint64_t ticks;

	/* One hardware timeout / one channel; reject a second install. */
	if (data->installed) {
		return -ENOMEM;
	}
	/* Not a windowed watchdog: no lower feed bound. */
	if (cfg->window.min != 0U) {
		return -ENOTSUP;
	}
	/*
	 * The G3 WDT is one-stage: on timeout it EITHER resets the SoC (WDT_CTRL
	 * reset bits) OR raises its interrupt (WDT_CTRL[2] = WDT_INTR) — never both
	 * (it is not a 2-stage pre-timeout-then-reset watchdog). So map:
	 *   WDT_FLAG_RESET_NONE + callback  -> interrupt mode (VIC-27 fires the cb);
	 *   WDT_FLAG_RESET_SOC/CPU_CORE     -> reset mode (callback must be NULL,
	 *                                      since no IRQ fires to call it).
	 * A callback with a reset flag would silently never run on this hardware, so
	 * reject it (fail loud) rather than pretend to support 2-stage.
	 */
	if (cfg->flags == WDT_FLAG_RESET_NONE) {
		if (cfg->callback == NULL) {
			return -ENOTSUP; /* interrupt mode is pointless with no callback */
		}
		data->interrupt_mode = true;
	} else if (cfg->flags == WDT_FLAG_RESET_SOC ||
		   cfg->flags == WDT_FLAG_RESET_CPU_CORE) {
		if (cfg->callback != NULL) {
			return -ENOTSUP; /* no 2-stage: reset mode fires no IRQ */
		}
		data->interrupt_mode = false;
	} else {
		return -ENOTSUP;
	}
	if (cfg->window.max == 0U) {
		return -EINVAL;
	}

	ticks = (uint64_t)cfg->window.max * WDT_G3_TICKS_PER_MS;
	if (ticks == 0U || ticks > 0xFFFFFFFFULL) {
		return -EINVAL; /* timeout does not fit the 32-bit reload register */
	}

	data->reload_ticks = (uint32_t)ticks;
	data->callback = cfg->callback;
	data->installed = true;
	return 0; /* channel 0 */
}

static int wdt_aspeed_g3_setup(const struct device *dev, uint8_t options)
{
	const struct wdt_aspeed_g3_config *cfg = dev->config;
	struct wdt_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key;

	/*
	 * The G3 WDT free-runs; it cannot pause while the CPU is halted in sleep
	 * or by the debugger, so any such request is refused rather than silently
	 * ignored (fail loud).
	 */
	if (options != 0U) {
		return -ENOTSUP;
	}
	if (!data->installed) {
		return -EINVAL; /* no timeout installed */
	}

	key = k_spin_lock(&data->lock);
	/* Reload value first, kick to load the counter, then enable + arm in the
	 * selected mode (interrupt -> VIC-27 on timeout; reset -> reset the SoC). */
	sys_write32(data->reload_ticks, cfg->base + WDT_G3_RELOAD_VALUE);
	sys_write32(WDT_G3_RESTART_MAGIC, cfg->base + WDT_G3_RESTART);
	sys_write32(data->interrupt_mode ? WDT_G3_CTRL_RUN_INTR : WDT_G3_CTRL_RUN,
		    cfg->base + WDT_G3_CTRL);
	data->enabled = true;
	k_spin_unlock(&data->lock, key);
	return 0;
}

static int wdt_aspeed_g3_feed(const struct device *dev, int channel_id)
{
	const struct wdt_aspeed_g3_config *cfg = dev->config;

	if (channel_id != 0) {
		return -EINVAL; /* only channel 0 exists */
	}

	/* Kick: reload the counter from WDT_RELOAD_VALUE and re-arm the timer. */
	sys_write32(WDT_G3_RESTART_MAGIC, cfg->base + WDT_G3_RESTART);
	return 0;
}

static int wdt_aspeed_g3_disable(const struct device *dev)
{
	const struct wdt_aspeed_g3_config *cfg = dev->config;
	struct wdt_aspeed_g3_data *data = dev->data;
	k_spinlock_key_t key = k_spin_lock(&data->lock);

	/*
	 * Nothing to do only if the WDT is neither running NOR installed. After a
	 * one-shot interrupt-mode timeout the ISR clears `enabled` but leaves
	 * `installed` set, and the caller is expected (Zephyr API) to disable() then
	 * re-install; so a fired-but-still-installed WDT must still be cleaned up
	 * here — guarding on `!enabled` alone would leak `installed` and block every
	 * future install_timeout() with -ENOMEM.
	 */
	if (!data->enabled && !data->installed) {
		k_spin_unlock(&data->lock, key);
		return -EFAULT; /* not running and nothing installed */
	}

	/* Clear ENABLE (and everything else) -> QEMU deletes the timer. */
	sys_write32(0U, cfg->base + WDT_G3_CTRL);
	data->enabled = false;
	data->installed = false;
	data->interrupt_mode = false;
	data->callback = NULL;
	k_spin_unlock(&data->lock, key);
	return 0;
}

/*
 * WDT timeout-interrupt ISR (VIC source 27), interrupt mode only. On expiry with
 * WDT_INTR set the hardware raises the IRQ INSTEAD of resetting (one-shot: the
 * QEMU model timer_del's, and datasheet §27 fires once). We invoke the installed
 * pre-timeout callback; the framework z_soc_irq_eoi() clears the latched edge.
 */
static void wdt_aspeed_g3_isr(const void *unused)
{
	const struct device *dev = wdt_g3_isr_dev;
	struct wdt_aspeed_g3_data *data = dev->data;
	wdt_callback_t cb;

	ARG_UNUSED(unused);

	cb = data->callback;
	data->enabled = false; /* one-shot: WDT_INTR fired instead of resetting */

	if (cb != NULL) {
		cb(dev, 0);
	}
}

static const struct wdt_driver_api wdt_aspeed_g3_api = {
	.setup = wdt_aspeed_g3_setup,
	.disable = wdt_aspeed_g3_disable,
	.install_timeout = wdt_aspeed_g3_install_timeout,
	.feed = wdt_aspeed_g3_feed,
};

static int wdt_aspeed_g3_init(const struct device *dev)
{
	const struct wdt_aspeed_g3_config *cfg = dev->config;

	/*
	 * Ensure the WDT is disabled at boot so a stale enable (from the loader or
	 * a prior warm boot) cannot fire before the application installs a timeout
	 * and calls wdt_setup(). Harmless in QEMU where CTRL resets to 0.
	 */
	sys_write32(0U, cfg->base + WDT_G3_CTRL);

	/*
	 * Connect + unmask the VIC-27 timeout-interrupt line. The WDT only asserts
	 * it in interrupt mode (WDT_INTR set by setup()), so enabling it here is
	 * inert until an interrupt-mode timeout is armed. z_soc_irq_enable() clears
	 * any stale latched edge for this source before unmasking.
	 */
	wdt_g3_isr_dev = dev;
	IRQ_CONNECT(WDT_G3_IRQ, WDT_G3_IRQ_PRIO, wdt_aspeed_g3_isr, NULL, 0);
	irq_enable(WDT_G3_IRQ);
	return 0;
}

#define WDT_ASPEED_G3_INIT(inst)                                               \
	static struct wdt_aspeed_g3_data wdt_aspeed_g3_data_##inst;             \
	static const struct wdt_aspeed_g3_config wdt_aspeed_g3_config_##inst = {\
		.base = (mem_addr_t)DT_INST_REG_ADDR(inst),                    \
	};                                                                     \
	DEVICE_DT_INST_DEFINE(inst, wdt_aspeed_g3_init, NULL,                  \
			      &wdt_aspeed_g3_data_##inst,                      \
			      &wdt_aspeed_g3_config_##inst, POST_KERNEL,       \
			      CONFIG_KERNEL_INIT_PRIORITY_DEVICE,              \
			      &wdt_aspeed_g3_api);

DT_INST_FOREACH_STATUS_OKAY(WDT_ASPEED_G3_INIT)
