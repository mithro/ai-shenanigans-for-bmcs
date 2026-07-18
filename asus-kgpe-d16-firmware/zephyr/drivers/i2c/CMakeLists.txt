# SPDX-License-Identifier: Apache-2.0

zephyr_library()
zephyr_library_sources_ifdef(CONFIG_I2C_ASPEED_G3 i2c_aspeed_g3.c)
