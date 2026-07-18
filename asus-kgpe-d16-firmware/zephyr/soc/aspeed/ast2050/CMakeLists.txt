# SPDX-License-Identifier: Apache-2.0

zephyr_sources(soc.c)
zephyr_sources(vic.c)
zephyr_sources(console.c)
zephyr_sources_ifdef(CONFIG_SYS_CLOCK_EXISTS aspeed_timer.c)
zephyr_include_directories(.)
