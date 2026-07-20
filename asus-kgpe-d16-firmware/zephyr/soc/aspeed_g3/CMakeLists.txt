# SPDX-License-Identifier: Apache-2.0

add_subdirectory(${SOC_SERIES})

# ARM926EJ-S reuses the AArch32 (cortex_a_r) linker script, per upstream
# PR #103557's sam9 SoC.
set(SOC_LINKER_SCRIPT
    ${ZEPHYR_BASE}/include/zephyr/arch/arm/cortex_a_r/scripts/linker.ld
    CACHE INTERNAL "")
