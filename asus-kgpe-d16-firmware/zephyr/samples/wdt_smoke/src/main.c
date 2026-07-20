/*
 * AST2050 (G3) watchdog smoke test.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Proves the WDT actually RESETS the SoC. The signal is observed across the
 * reset in the boot log, so the QEMU harness must run WITHOUT -no-reboot (and
 * with QEMU's default watchdog action = reset) so the fire path reboots the
 * machine instead of halting it. Console output goes through the M0 polling UART
 * backend (soc/aspeed_g3/ast2050/console.c); no console config beyond
 * CONFIG_WATCHDOG in prj.conf is needed.
 *
 * Sequence each boot:
 *   1. print "WDT smoke: boot"                         <- appears once per boot
 *   2. install a 500 ms timeout, wdt_setup()           (arms the WDT)
 *   3. feed 3x at ~150 ms spacing, printing "WDT alive N" (N=1..3)
 *   4. print "WDT armed, not feeding, expect reset"
 *   5. stop feeding and idle -> ~500 ms later the WDT fires -> SoC reset
 *   6. QEMU reboots -> Zephyr banner + step 1 run AGAIN
 *
 * PROOF THE RESET FIRED — QEMU (has a backing flash image, so it REBOOTS):
 *   - the line "WDT smoke: boot" appears >= 2 times, OR
 *   - the Zephyr banner "*** Booting Zephyr OS" appears >= 2 times, AND
 *   - a second "WDT smoke: boot" appears AFTER "WDT armed, not feeding, expect
 *     reset".
 * The reset intentionally re-runs main(), so left running it reboots in a loop
 * (each cycle ~1 s in QEMU); a ~4 s capture window catches at least two boots.
 * If the WDT did NOT reset, only ONE "WDT smoke: boot" is ever printed and the
 * program idles forever after "WDT armed, not feeding, expect reset".
 * Measured: 6 boots in a 6 s window (see evidence d14-zephyr/18-wdt-silicon.txt).
 *
 * PROOF THE RESET FIRED — REAL AST2050 silicon (the BMC SPI flash is NOT wired,
 * so a SoC reset canNOT reboot into Zephyr — there is nothing at the reset
 * vector to run). The signature is therefore different from QEMU:
 *   (1) the console shows exactly ONE cycle (banner .. "expect reset") then goes
 *       SILENT at the ~500 ms timeout, AND
 *   (2) a JTAG halt afterwards shows the CPU has LEFT Zephyr: Undefined-instr
 *       mode with PC in the flash-mapped low region (NOT 0x40xxxxxx DRAM) and a
 *       stale Zephyr sp_und — i.e. the SoC reset and is now faulting on the empty
 *       flash bus. Observable (1) alone is ambiguous (an idle for(;;) is also
 *       silent); (2) is what makes it a rigorous reset proof.
 * Both silicon observables captured in evidence d14-zephyr/18-wdt-silicon.txt.
 */

#include <zephyr/device.h>
#include <zephyr/drivers/watchdog.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define WDT_SMOKE_NODE   DT_NODELABEL(wdt0) /* aspeed,ast2050-wdt @ 0x1E785000 */
#define WDT_SMOKE_MS     500U               /* timeout window */
#define WDT_SMOKE_FEEDS  3                  /* number of pre-reset kicks */
#define WDT_SMOKE_FEED_MS 150U              /* spacing between kicks (< 500 ms) */

BUILD_ASSERT(DT_NODE_HAS_STATUS(WDT_SMOKE_NODE, okay),
	     "wdt0 (aspeed,ast2050-wdt) must be enabled");

int main(void)
{
	const struct device *wdt = DEVICE_DT_GET(WDT_SMOKE_NODE);
	struct wdt_timeout_cfg cfg = {
		.window = { .min = 0U, .max = WDT_SMOKE_MS },
		.callback = NULL,
		.flags = WDT_FLAG_RESET_SOC,
	};
	int channel;
	int ret;

	printk("WDT smoke: boot\n");

	if (!device_is_ready(wdt)) {
		printk("WDT smoke: device not ready\n");
		return 0;
	}

	channel = wdt_install_timeout(wdt, &cfg);
	if (channel < 0) {
		printk("WDT smoke: install_timeout failed (%d)\n", channel);
		return 0;
	}

	ret = wdt_setup(wdt, 0);
	if (ret != 0) {
		printk("WDT smoke: setup failed (%d)\n", ret);
		return 0;
	}
	printk("WDT armed for %u ms, feeding %dx\n", WDT_SMOKE_MS, WDT_SMOKE_FEEDS);

	for (int i = 1; i <= WDT_SMOKE_FEEDS; i++) {
		k_msleep(WDT_SMOKE_FEED_MS);
		ret = wdt_feed(wdt, channel);
		if (ret != 0) {
			printk("WDT smoke: feed failed (%d)\n", ret);
			return 0;
		}
		printk("WDT alive %d\n", i);
	}

	printk("WDT armed, not feeding, expect reset\n");

	/* Idle and let the WDT time out (~500 ms after the last feed). The WDT is
	 * a hardware timer, so it fires and resets the SoC even while the CPU is
	 * idle here; QEMU then reboots and main() runs from the top again. */
	for (;;) {
		k_msleep(1000);
	}

	return 0;
}
