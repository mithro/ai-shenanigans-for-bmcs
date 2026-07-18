/*
 * ASPEED AST2050 (G3) SoC init — ARM926EJ-S.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal Milestone-0 SoC layer: an MMU flat-map for the UART SFR window so
 * the NS16550 console is reachable, plus the vector page. The DRAM/console
 * are already brought up by the JTAG/U-Boot bring-up (silicon) or the QEMU
 * machine, so no clock/DDR init is needed here for M0.
 */

#include <soc.h>
#include <zephyr/arch/arm/mmu/arm_mmu.h>
#include <zephyr/init.h>
#include <zephyr/kernel.h>

static const struct arm_mmu_region mmu_regions[] = {
	MMU_REGION_ENTRY("vectors", CONFIG_KERNEL_VM_BASE, 0, 0x1000,
			 MT_STRONGLY_ORDERED | MPERM_R | MPERM_X),

	/* Whole 64 MB DDR2 window, flat-mapped cacheable-normal, so the kernel
	 * image + stacks are reachable once the MMU turns on. */
	MMU_REGION_FLAT_ENTRY("dram", 0x40000000, 0x04000000,
			      MT_NORMAL | MPERM_R | MPERM_W | MPERM_X),

	/*
	 * UART5 (0x1e784000) flat-mapped as device memory so the M0 polling
	 * console (console.c) can reach the SFRs at their physical address with
	 * the MMU on. This is a STATIC region installed at boot (like dram /
	 * vectors) and is reliable, unlike the dynamic ns16550 DEVICE_MMIO_MAP
	 * path: under CONFIG_MMU that path's z_phys_map returns a virtual base
	 * (observed 0x1e7ff000) that the ARM926 arm_mmu does not translate back
	 * to 0x1e784000, so the ns16550 console busy-polls an unimplemented
	 * address and never prints. The identity region sits well outside the
	 * kernel VM window (0x40000000+8M), so it does not collide with the
	 * device-VA allocator. Kept narrow (one 1 MB section covers it).
	 */
	MMU_REGION_FLAT_ENTRY("uart5", 0x1e784000, 0x1000,
			      MT_DEVICE | MPERM_R | MPERM_W),

	/* M1: the G3 VIC (0x1e6c0000, vic.c) and the timer block (0x1e782000,
	 * aspeed_timer.c) — device memory, statically mapped like the UART so
	 * IRQ setup + the system tick work with the MMU on. */
	MMU_REGION_FLAT_ENTRY("vic", 0x1e6c0000, 0x1000,
			      MT_DEVICE | MPERM_R | MPERM_W),
	MMU_REGION_FLAT_ENTRY("timer", 0x1e782000, 0x1000,
			      MT_DEVICE | MPERM_R | MPERM_W),

	/* G3/AST2400-compatible GPIO controller (0x1e780000, drivers/gpio/
	 * gpio_aspeed_g3.c) — device memory, statically mapped like the UART/VIC/
	 * timer so the driver's MMIO reads/writes reach the SFRs at their physical
	 * address with the MMU on. One 0x1000 page covers all GPIO bank registers
	 * (the highest, set YZAAAB, ends at 0x1e7801e7). */
	MMU_REGION_FLAT_ENTRY("gpio", 0x1e780000, 0x1000,
			      MT_DEVICE | MPERM_R | MPERM_W),

	/* G3/AST2400-compatible I2C controller (0x1e78a000, drivers/i2c/
	 * i2c_aspeed_g3.c) — device memory, statically mapped like the others so
	 * the driver reaches the global block + all 7 per-engine register blocks
	 * (engine 6 ends at 0x1e78a1ff) at their physical address with the MMU
	 * on. One 0x1000 page covers the whole controller. */
	MMU_REGION_FLAT_ENTRY("i2c", 0x1e78a000, 0x1000,
			      MT_DEVICE | MPERM_R | MPERM_W),

	/* SCU / System Control Unit (0x1e6e2000) — device memory. The I2C driver
	 * writes SCU04[2] to de-assert the reset hold that keeps all 7 I2C
	 * engines inert at power-on (and SCU00 to unlock the SCU first); on
	 * bare-metal Zephyr no U-Boot runs to do this. One 0x1000 page. */
	MMU_REGION_FLAT_ENTRY("scu", 0x1e6e2000, 0x1000,
			      MT_DEVICE | MPERM_R | MPERM_W),

	/* G3/AST2400-compatible watchdog timer (0x1e785000, drivers/watchdog/
	 * wdt_aspeed_g3.c) — device memory, statically mapped like the others. The
	 * other 0x1e78xxxx regions are separate 4 KB pages (uart5 0x1e784000, gpio
	 * 0x1e780000), so 0x1e785000 is NOT already covered — its own page is
	 * needed. One 0x1000 page covers the 0x20-byte WDT block. */
	MMU_REGION_FLAT_ENTRY("wdt", 0x1e785000, 0x1000,
			      MT_DEVICE | MPERM_R | MPERM_W),
};

const struct arm_mmu_config mmu_config = {
	.num_regions = ARRAY_SIZE(mmu_regions),
	.mmu_regions = mmu_regions,
};

void soc_early_init_hook(void)
{
	/* AST2050 SCU/DDR/console are pre-initialised by the loader (U-Boot on
	 * silicon, the machine in QEMU); nothing to do at M0.
	 */
}

/* Called from reset.S before prep_c. MMU/caches are still off here. */
void soc_reset_hook(void)
{
}
