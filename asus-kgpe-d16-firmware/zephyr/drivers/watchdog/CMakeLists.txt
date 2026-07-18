# SPDX-License-Identifier: Apache-2.0

zephyr_library()
zephyr_library_sources_ifdef(CONFIG_WDT_ASPEED_G3 wdt_aspeed_g3.c)
