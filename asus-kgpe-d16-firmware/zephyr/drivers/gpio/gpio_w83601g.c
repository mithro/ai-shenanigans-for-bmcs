/*
 * Winbond W83601G I2C GPIO expander driver for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * The KGPE-D16 uses two W83601G expanders (U27 @0x18, U28 @0x19) on the BMC's
 * I2C5 engine to drive the DIMM error LEDs. This driver exposes each expander as
 * a single 16-pin Zephyr GPIO controller: Port 1 = pins 0..7, Port 2 = pins
 * 8..15. Register map (CR-indexed, from the faithful QEMU model
 * hw/gpio/w83601g.c — a write is [CR index, data...] auto-incrementing, a read
 * is write-index-then-read):
 *
 *   Port 1: CR00 input · CR01 output-data · CR03 I/O-config (1=input, 0=output)
 *   Port 2: CR08 input · CR09 output-data · CR0B I/O-config
 *   CR20 chip-ID high (0x60)
 *
 * Reset leaves both ports all-input (CR03=0xFF, CR0B=0x7F), so a pin must be
 * switched to output (its I/O-config bit cleared) before the output-data write
 * appears on the pad — modelled exactly, and handled by pin_configure() here.
 *
 * All register access is over the Zephyr I2C API (i2c_reg_{read,write}_byte_dt),
 * so this driver rides the AST2050 I2C master (drivers/i2c/i2c_aspeed_g3.c) —
 * no MMIO of its own. Output writes go through a per-device 16-bit software
 * shadow of the two output-data registers.
 */

#define DT_DRV_COMPAT winbond_w83601g_gpio

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/gpio/gpio_utils.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>

/* CR indices (hw/gpio/w83601g.c). */
#define W601_CR_P1_IN    0x00U
#define W601_CR_P1_OUT   0x01U
#define W601_CR_P1_IOCFG 0x03U
#define W601_CR_P2_IN    0x08U
#define W601_CR_P2_OUT   0x09U
#define W601_CR_P2_IOCFG 0x0BU

#define W601_PINS 16U   /* Port 1 (0..7) + Port 2 (8..15) */

struct gpio_w83601g_config {
	struct gpio_driver_config common;
	struct i2c_dt_spec i2c;
};

struct gpio_w83601g_data {
	struct gpio_driver_data common;
	struct k_mutex lock;    /* serialises the read-modify-write I2C sequences */
	uint16_t out_shadow;    /* [15:8]=Port2 CR09, [7:0]=Port1 CR01 */
};

/* Per-port register selectors for a pin (pin < 8 => Port 1, else Port 2). */
static inline uint8_t reg_out(gpio_pin_t pin)
{
	return (pin < 8U) ? W601_CR_P1_OUT : W601_CR_P2_OUT;
}
static inline uint8_t reg_in(gpio_pin_t pin)
{
	return (pin < 8U) ? W601_CR_P1_IN : W601_CR_P2_IN;
}
static inline uint8_t reg_iocfg(gpio_pin_t pin)
{
	return (pin < 8U) ? W601_CR_P1_IOCFG : W601_CR_P2_IOCFG;
}

/* Write the shadow byte(s) covering `mask` back to the expander. */
static int w601_flush_out(const struct device *dev, uint16_t mask)
{
	const struct gpio_w83601g_config *cfg = dev->config;
	struct gpio_w83601g_data *data = dev->data;
	int ret = 0;

	if (mask & 0x00FFU) {
		ret = i2c_reg_write_byte_dt(&cfg->i2c, W601_CR_P1_OUT,
					    data->out_shadow & 0xFFU);
	}
	if (ret == 0 && (mask & 0xFF00U)) {
		ret = i2c_reg_write_byte_dt(&cfg->i2c, W601_CR_P2_OUT,
					    (data->out_shadow >> 8) & 0xFFU);
	}
	return ret;
}

static int gpio_w83601g_pin_configure(const struct device *dev, gpio_pin_t pin,
				      gpio_flags_t flags)
{
	const struct gpio_w83601g_config *cfg = dev->config;
	struct gpio_w83601g_data *data = dev->data;
	uint8_t iocfg_reg, iocfg, local;
	int ret;

	if (pin >= W601_PINS) {
		return -EINVAL;
	}
	/* No internal pulls / open-drain modelled on this expander. */
	if (flags & (GPIO_PULL_UP | GPIO_PULL_DOWN | GPIO_SINGLE_ENDED)) {
		return -ENOTSUP;
	}

	iocfg_reg = reg_iocfg(pin);
	local = (uint8_t)(pin & 7U);

	k_mutex_lock(&data->lock, K_FOREVER);

	ret = i2c_reg_read_byte_dt(&cfg->i2c, iocfg_reg, &iocfg);
	if (ret != 0) {
		goto out;
	}

	if (flags & GPIO_OUTPUT) {
		if (flags & GPIO_OUTPUT_INIT_HIGH) {
			data->out_shadow |= BIT(pin);
		} else if (flags & GPIO_OUTPUT_INIT_LOW) {
			data->out_shadow &= ~BIT(pin);
		}
		/* Push the output value first, then enable the driver (clear the
		 * I/O-config bit: 0 = output), so no wrong level is driven.
		 */
		ret = w601_flush_out(dev, BIT(pin));
		if (ret == 0) {
			ret = i2c_reg_write_byte_dt(&cfg->i2c, iocfg_reg,
						    iocfg & ~BIT(local));
		}
	} else {
		/* Input (or disconnected): set the I/O-config bit (1 = input). */
		ret = i2c_reg_write_byte_dt(&cfg->i2c, iocfg_reg,
					    iocfg | BIT(local));
	}

out:
	k_mutex_unlock(&data->lock);
	return ret;
}

static int gpio_w83601g_port_get_raw(const struct device *dev,
				     gpio_port_value_t *value)
{
	const struct gpio_w83601g_config *cfg = dev->config;
	struct gpio_w83601g_data *data = dev->data;
	uint8_t p1, p2;
	int ret;

	k_mutex_lock(&data->lock, K_FOREVER);
	ret = i2c_reg_read_byte_dt(&cfg->i2c, W601_CR_P1_IN, &p1);
	if (ret == 0) {
		ret = i2c_reg_read_byte_dt(&cfg->i2c, W601_CR_P2_IN, &p2);
	}
	k_mutex_unlock(&data->lock);

	if (ret != 0) {
		return ret;
	}
	*value = (gpio_port_value_t)(((uint16_t)p2 << 8) | p1);
	return 0;
}

static int gpio_w83601g_port_set_masked_raw(const struct device *dev,
					    gpio_port_pins_t mask,
					    gpio_port_value_t value)
{
	struct gpio_w83601g_data *data = dev->data;
	int ret;

	k_mutex_lock(&data->lock, K_FOREVER);
	data->out_shadow = (data->out_shadow & ~mask) | (value & mask);
	ret = w601_flush_out(dev, mask);
	k_mutex_unlock(&data->lock);
	return ret;
}

static int gpio_w83601g_port_set_bits_raw(const struct device *dev,
					  gpio_port_pins_t pins)
{
	struct gpio_w83601g_data *data = dev->data;
	int ret;

	k_mutex_lock(&data->lock, K_FOREVER);
	data->out_shadow |= pins;
	ret = w601_flush_out(dev, pins);
	k_mutex_unlock(&data->lock);
	return ret;
}

static int gpio_w83601g_port_clear_bits_raw(const struct device *dev,
					    gpio_port_pins_t pins)
{
	struct gpio_w83601g_data *data = dev->data;
	int ret;

	k_mutex_lock(&data->lock, K_FOREVER);
	data->out_shadow &= ~pins;
	ret = w601_flush_out(dev, pins);
	k_mutex_unlock(&data->lock);
	return ret;
}

static int gpio_w83601g_port_toggle_bits(const struct device *dev,
					 gpio_port_pins_t pins)
{
	struct gpio_w83601g_data *data = dev->data;
	int ret;

	k_mutex_lock(&data->lock, K_FOREVER);
	data->out_shadow ^= pins;
	ret = w601_flush_out(dev, pins);
	k_mutex_unlock(&data->lock);
	return ret;
}

static const struct gpio_driver_api gpio_w83601g_api = {
	.pin_configure = gpio_w83601g_pin_configure,
	.port_get_raw = gpio_w83601g_port_get_raw,
	.port_set_masked_raw = gpio_w83601g_port_set_masked_raw,
	.port_set_bits_raw = gpio_w83601g_port_set_bits_raw,
	.port_clear_bits_raw = gpio_w83601g_port_clear_bits_raw,
	.port_toggle_bits = gpio_w83601g_port_toggle_bits,
};

static int gpio_w83601g_init(const struct device *dev)
{
	const struct gpio_w83601g_config *cfg = dev->config;

	if (!i2c_is_ready_dt(&cfg->i2c)) {
		return -ENODEV;
	}
	/* Shadow starts 0 (both output-data registers reset to 0x00). */
	return 0;
}

#define GPIO_W83601G_INIT(inst)                                                \
	static struct gpio_w83601g_data gpio_w83601g_data_##inst;              \
	static const struct gpio_w83601g_config gpio_w83601g_config_##inst = { \
		.common = {                                                    \
			.port_pin_mask =                                       \
				GPIO_PORT_PIN_MASK_FROM_DT_INST(inst),         \
		},                                                             \
		.i2c = I2C_DT_SPEC_INST_GET(inst),                             \
	};                                                                     \
	static int gpio_w83601g_init_##inst(const struct device *dev)          \
	{                                                                      \
		k_mutex_init(&gpio_w83601g_data_##inst.lock);                  \
		return gpio_w83601g_init(dev);                                 \
	}                                                                      \
	DEVICE_DT_INST_DEFINE(inst, gpio_w83601g_init_##inst, NULL,            \
			      &gpio_w83601g_data_##inst,                       \
			      &gpio_w83601g_config_##inst, POST_KERNEL,        \
			      CONFIG_GPIO_W83601G_INIT_PRIORITY,               \
			      &gpio_w83601g_api);

DT_INST_FOREACH_STATUS_OKAY(GPIO_W83601G_INIT)
