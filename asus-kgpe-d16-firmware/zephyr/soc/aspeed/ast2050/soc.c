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

	/* G3 counter-style RTC (0x1e781000, drivers/rtc/rtc_aspeed_g3.c) — device
	 * memory, statically mapped like the other SFR blocks so the driver reaches
	 * its 0x20-byte register block at the physical address with the MMU on. */
	MMU_REGION_FLAT_ENTRY("rtc", 0x1e781000, 0x1000,
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
	/*
	 * Invalidate the I-cache, D-cache, and TLBs before z_arm_mmu_init turns
	 * the MMU + caches on (this hook runs with them still off, and no U-Boot
	 * runs here to have done it).
	 *
	 * On silicon the ARM926EJ-S caches/TLBs power up with UNDEFINED contents
	 * — a hardware reset does not clear them. Without this invalidate, when
	 * z_arm_mmu_init enables the D-cache, data reads can hit stale garbage
	 * cache lines instead of DRAM. Observed on the real AST2050 (JTAG boot):
	 * _isr_wrapper loaded the _current_cpu pointer *(0x40002578) — which is
	 * 0x4000c21c in the JTAG-loaded DRAM, verified byte-for-byte — back as
	 * 0x8000001f, then took a section-translation data abort on 0x80000030
	 * (CP15 FAR) and spun in z_arm_data_abort at __start. QEMU boots the same
	 * image because it does not model cache *contents* (reads always hit
	 * memory); this invalidate is a harmless no-op there and makes the boot
	 * correct on real hardware too.
	 *
	 * ARM926EJ-S CP15 (ARMv5TE), Rd ignored (SBZ):
	 *   c7,c7,0   invalidate I-cache + D-cache
	 *   c8,c7,0   invalidate I-TLB + D-TLB
	 *   c7,c10,4  drain write buffer
	 */
	uint32_t sbz = 0U;

	__asm__ volatile(
		"mcr p15, 0, %0, c7, c7, 0\n\t"  /* invalidate I+D cache */
		"mcr p15, 0, %0, c8, c7, 0\n\t"  /* invalidate I+D TLB   */
		"mcr p15, 0, %0, c7, c10, 4\n\t" /* drain write buffer   */
		:
		: "r"(sbz)
		: "memory");
}
