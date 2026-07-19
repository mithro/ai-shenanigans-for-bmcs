# SPDX-License-Identifier: Apache-2.0

zephyr_library()
zephyr_library_sources_ifdef(CONFIG_GPIO_ASPEED_G3 gpio_aspeed_g3.c)
zephyr_library_sources_ifdef(CONFIG_GPIO_W83601G gpio_w83601g.c)
