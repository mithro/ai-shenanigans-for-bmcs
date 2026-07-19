# Out-of-tree module CMake entry point (referenced by zephyr/module.yml
# build.cmake = ".").  Contributes the AST2050 driver subdirectories on top of
# the SoC/board files that are pulled in via soc_root/board_root/dts_root.
# SPDX-License-Identifier: Apache-2.0

add_subdirectory_ifdef(CONFIG_GPIO_ASPEED_G3 drivers/gpio)
add_subdirectory_ifdef(CONFIG_I2C_ASPEED_G3 drivers/i2c)
add_subdirectory_ifdef(CONFIG_WDT_ASPEED_G3 drivers/watchdog)
add_subdirectory_ifdef(CONFIG_W83795 drivers/sensor/w83795)
add_subdirectory_ifdef(CONFIG_SBTSI drivers/sensor/sbtsi)
