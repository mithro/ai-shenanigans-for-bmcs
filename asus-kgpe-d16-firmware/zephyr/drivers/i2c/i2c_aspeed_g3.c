/*
 * ASPEED AST2050 (G3) I2C master controller driver for Zephyr.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal but functional, POLLED (interrupt-free) I2C master for the AST2050
 * (ARM926EJ-S, G3 legacy register layout) BMC SoC. The I2C block lives at
 * controller base 0x1E78A000 and is a 0x40-byte global register block followed
 * by up to 7 per-engine (per-bus) 0x40-byte register blocks. Each devicetree
 * node models one engine; the node's "reg" points at that engine's per-bus
 * block (base 0x1E78A000 + 0x40 * (engine + 1)). We never touch the global
 * block: the AST2050 powers up in legacy "old mode" (I2C_CTRL_GLOBAL[REG_MODE]
 * = 0) and we leave it there, which is what these per-bus offsets assume.
 *
 * Register offsets within a per-bus block (legacy old mode) come from the QEMU
 * G3/AST2400 model include/hw/i2c/aspeed_i2c.h:
 *   REG32(I2CD_FUN_CTRL,   0x00)  line 77
 *   REG32(I2CD_AC_TIMING1, 0x04)  line 92
 *   REG32(I2CD_AC_TIMING2, 0x08)  line 93
 *   REG32(I2CD_INTR_CTRL,  0x0C)  line 94
 *   REG32(I2CD_INTR_STS,   0x10)  line 95
 *   REG32(I2CD_CMD,        0x14)  line 114
 *   REG32(I2CD_DEV_ADDR,   0x18)  line 141
 *   REG32(I2CD_BYTE_BUF,   0x20)  line 149  (TX in [7:0], RX in [15:8], l.150-151)
 * cross-checked against the vendor U-Boot arch-aspeed/aspeed_i2c.h (I2C_BASE
 * 0x1E78A000, per-engine stride 0x40, same offsets) and Linux
 * drivers/i2c/busses/i2c-aspeed.c.
 *
 * Command bits (I2CD_CMD, aspeed_i2c.h SHARED_FIELD lines 135-140; identical to
 * Linux i2c-aspeed.c lines 105-116 and vendor aspeed_i2c.h lines 55-59):
 *   M_START_CMD BIT(0), M_TX_CMD BIT(1), M_RX_CMD BIT(3),
 *   M_S_RX_CMD_LAST BIT(4), M_STOP_CMD BIT(5).
 * Status bits (I2CD_INTR_STS, aspeed_i2c.h lines 107-113; vendor lines 62-65):
 *   TX_ACK BIT(0), TX_NAK BIT(1), RX_DONE BIT(2), NORMAL_STOP BIT(4),
 *   ABNORMAL BIT(5).
 *
 * IMPORTANT G3 gotcha 1 - INTR_CTRL must enable the status bits we poll.
 * In legacy old mode the QEMU model (and real silicon) masks the interrupt
 * status register by the interrupt-enable mask after every command:
 *   aspeed_i2c.c aspeed_i2c_bus_raise_interrupt() lines 68-73:
 *     bus->regs[reg_intr_sts] &= (intr_ctrl | ALWAYS_ENABLE);
 * so any status bit NOT enabled in INTR_CTRL is cleared before we can poll it.
 * We therefore enable TX_ACK|TX_NAK|RX_DONE|NORMAL_STOP|ABNORMAL in init. We do
 * NOT wire the shared I2C IRQ (VIC source 12): the VIC leaves it masked, so the
 * asserted line is harmless. Interrupt-driven operation is a follow-up.
 *
 * IMPORTANT G3 gotcha 2 - the whole 7-engine I2C block powers up HELD IN RESET.
 * SCU04[2] ("System Reset Control", I2C/SMBus controller reset) resets to 1 on
 * the AST2050 (datasheet default; QEMU ast2400 SYS_RST_CTRL reset value
 * 0xFFCFFEDC and the G3 table 0x000FFE5C both have BIT(2) set). While held, the
 * I2C register file is inert (reads return 0, writes drop) - see
 * hw/arm/aspeed_ast2400.c aspeed_2050_i2c_rst(). Zephyr boots bare-metal (no
 * U-Boot runs), so this driver de-asserts SCU04[2] itself (unlocking the SCU
 * first), exactly like the vendor U-Boot i2c_init() does
 * (raptor-uboot/drivers/i2c/aspeed_i2c.c lines 22-24).
 *
 * IMPORTANT G3 gotcha 4 - I2C channels 5/6/7 need their SCU74 pin-mux bit set.
 * On the AST2050, only I2C/SMBUS 1-4 have DEDICATED I2C pads; SDA5/SCL5, SDA6/
 * SCL6 and SDA7/SCL7 are MULTIPLEXED pins (datasheet pin list shows them with a
 * "/" suffix). The multi-function pin table selects the I2C function only when
 * the matching SCU74 bit is 1:
 *   A13 SDA5 / B13 SCL5  <- SCU74[12]=1   (I2C/SMBUS 5)
 *   C12 SDA6 / D12 SCL6  <- SCU74[13]=1   (I2C/SMBUS 6)
 *   A12 SDA7 / B12 SCL7  <- SCU74[14]=1   (I2C/SMBUS 7)
 * BOARD CAVEAT (KGPE-D16): pad A12 is wired as GPIOH2 = STA_LINE_POWER (the host
 * power-state feedback the BMC reads), so SCU74[14] MUST stay 0 and I2C/SMBUS 7
 * (channel 7) is NOT available on this board — enabling it would repurpose A12
 * away from GPIOH2 and break power-state sensing. This driver only sets the bit
 * for an instantiated DT node, and there is intentionally no channel-7 node.
 * (AST2050/AST1100 A3 datasheet V1.05, multi-function pin control table: e.g.
 * "A13 GPIOC6 MII2DIO SCU74[20]=1  SDA5 SCU74[12]=1  GPIOC6  Others".) Without
 * this, a byte clocked out on one of these engines never reaches the pads and the
 * master times out with no ACK - which is exactly what happened on real silicon
 * to the I2C5 FRU EEPROM (0x54) and W83601G expanders (0x18/0x19) while the
 * W83795 on I2C2 (dedicated pads) worked. The vendor U-Boot i2c_init() does the
 * same thing for the AST2050: SCU74 |= 0x5000 (bits 12+14 = channels 5+7)
 * (raptor-uboot/drivers/i2c/aspeed_i2c.c lines 26-28). We set only the bit for
 * the engine actually being initialised, derived from its register base. Channels
 * 1-4 (dedicated pads) need no pin-mux. (Note MII2DIO/MII2DC on A13/B13 are a
 * HIGHER-priority Function 1 gated by SCU74[20]; it resets to 0 on this board so
 * SCU74[12] selects SDA5 - the same assumption the vendor blanket-OR relies on.)
 *
 * IMPORTANT G3 gotcha 3 - the AC-timing register 1 (I2CD04) MUST be programmed.
 * On the AST2050/AST1100 (G3) I2CD04 resets to X (undefined; datasheet §31.4.3
 * "Init = X"), so the bus-free/START/STOP timing (tBUF/tHDSTA/tACST) runs on
 * power-up garbage and the master FSM wedges on tHDSTA. We program the vendor
 * value 0x77743335 ("Fix timing for EEPROM 100Khz") from the Raptor AST2050
 * U-Boot arch-aspeed/aspeed_i2c.h line 32 - its top three nibbles are the
 * tBUF=tHDSTA=tACST=7 fix that the kernel patch
 * kernel/patches/0005-i2c-aspeed-program-full-ac-timing.patch and Linux
 * i2c-aspeed.c aspeed_i2c_init_clk() apply
 * (ASPEED_I2CD_TIME_{TBUF,THDSTA,TACST}_MASK = GENMASK(31,28)/(27,24)/(23,20)).
 * The lower nibbles (4/3/3/3/5) are that driver's SCL_high/SCL_low/base-divisor
 * for 100 kHz off the AST2050 APB clock. (In QEMU the AC timing does not gate
 * the functional FSM, but programming it is correct for real silicon.)
 *
 * MMIO is reached at its PHYSICAL address via the static identity MMU regions
 * added in soc/aspeed/ast2050/soc.c (the I2C controller page 0x1E78A000 and the
 * SCU page 0x1E6E2000), mirroring the UART/VIC/timer/GPIO regions. We
 * deliberately do NOT use the DEVICE_MMIO_MAP path: under CONFIG_MMU on this
 * brand-new ARM926 arm_mmu, z_phys_map returns a virtual base the MMU does not
 * translate back (see the console.c / gpio_aspeed_g3.c comments). All accesses
 * are 32-bit sys_read32/sys_write32.
 *
 * Follow-ups (not implemented): interrupt-driven transfers via the per-engine
 * INTR regs + G3 VIC (soc/aspeed/ast2050/vic.c); the pool-buffer/DMA fast paths;
 * per-speed AC-timing divider computation from the APB clock; 10-bit addressing;
 * multi-master arbitration handling; bus recovery.
 */

#define DT_DRV_COMPAT aspeed_ast2050_i2c

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/sys/util.h>

/* Per-engine register offsets from the node's reg base (aspeed_i2c.h). */
#define I2CD_FUN_CTRL   0x00U
#define I2CD_AC_TIMING1 0x04U
#define I2CD_AC_TIMING2 0x08U
#define I2CD_INTR_CTRL  0x0CU
#define I2CD_INTR_STS   0x10U
#define I2CD_CMD        0x14U
#define I2CD_DEV_ADDR   0x18U
#define I2CD_BYTE_BUF   0x20U

/* I2CD_FUN_CTRL bits. */
#define I2CD_MASTER_EN  BIT(0)

/* I2CD_CMD master command bits. */
#define I2CD_M_START_CMD    BIT(0)
#define I2CD_M_TX_CMD       BIT(1)
#define I2CD_M_RX_CMD       BIT(3)
#define I2CD_M_RX_CMD_LAST  BIT(4) /* NACK the byte just received */
#define I2CD_M_STOP_CMD     BIT(5)

/* I2CD_INTR_STS / INTR_CTRL bits. */
#define I2CD_INTR_TX_ACK      BIT(0)
#define I2CD_INTR_TX_NAK      BIT(1)
#define I2CD_INTR_RX_DONE     BIT(2)
#define I2CD_INTR_NORMAL_STOP BIT(4)
#define I2CD_INTR_ABNORMAL    BIT(5)

/*
 * Enable exactly the status sources we poll so they survive the post-command
 * INTR_STS masking (file header, gotcha 1). Clearing status = write these bits.
 */
#define I2CD_INTR_ENABLE                                                        \
	(I2CD_INTR_TX_ACK | I2CD_INTR_TX_NAK | I2CD_INTR_RX_DONE |              \
	 I2CD_INTR_NORMAL_STOP | I2CD_INTR_ABNORMAL)

/* I2CD_BYTE_BUF: RX byte is in bits [15:8]. */
#define I2CD_RX_BUF_SHIFT 8

/*
 * Vendor G3 AC timing #1 for ~100 kHz: 0x77743335 (Raptor AST2050 U-Boot
 * arch-aspeed/aspeed_i2c.h line 32, "Fix timing for EEPROM 100Khz"). See the
 * file header, gotcha 3. AC timing #2 = 0 disables the SCL/SDA timeouts
 * (Linux ASPEED_NO_TIMEOUT_CTRL, i2c-aspeed.c line 63).
 */
#define I2CD_AC_TIMING1_VENDOR 0x77743335U
#define I2CD_AC_TIMING2_VENDOR 0x0U

/*
 * SCU (System Control Unit) - de-assert the SoC-level I2C reset (SCU04[2]) that
 * holds all 7 G3 I2C engines inert at power-on (file header, gotcha 2). SCU
 * writes to protected registers require the write-unlock key in SCU00 first.
 */
#define SCU_G3_BASE          0x1E6E2000U
#define SCU_G3_PROT_KEY      0x00U
#define SCU_G3_SYS_RST_CTRL  0x04U
#define SCU_G3_MFP_CTL1      0x74U /* Multi-function Pin Control #1 (I2C5/6/7) */
#define SCU_G3_UNLOCK_MAGIC  0x1688A8A8U /* aspeed_scu.h ASPEED_SCU_PROT_KEY */
#define SCU_G3_RST_I2C       BIT(2)

/*
 * The I2C controller register file starts here; each engine's per-bus block is
 * at I2C_CTRL_BASE + 0x40 * channel, where channel = the datasheet I2C/SMBUS
 * number (1..N). We recover it from the node's reg base to pick the SCU74
 * pin-mux bit (file header, gotcha 4).
 */
#define I2C_CTRL_BASE        0x1E78A000U
#define I2C_ENGINE_STRIDE    0x40U
#define I2C_MUXED_CHAN_FIRST 5U  /* channels 5..7 have muxed pins (SCU74[12..14]) */
#define I2C_MUXED_CHAN_LAST  7U
#define SCU74_SDA5_BIT       12U /* SCU74[12] -> chan5, [13] -> chan6, [14] -> chan7 */

/*
 * Polling bound. In QEMU the status is set synchronously by the CMD store, so
 * the first read already sees it; on real silicon a 100 kHz byte is ~90 us, so
 * this generous count (matching the vendor LOOP_COUNT 0x100000) always covers a
 * single byte/command before we fail loud with -ETIMEDOUT.
 */
#define I2CD_POLL_COUNT 0x100000

struct i2c_aspeed_g3_config {
	mem_addr_t base;
};

struct i2c_aspeed_g3_data {
	/*
	 * A MUTEX (not a spinlock): a transfer busy-polls for completion up to
	 * I2CD_POLL_COUNT per phase, and k_spin_lock() disables interrupts for its
	 * whole held duration. Holding it across the poll would freeze the system
	 * tick / scheduler / watchdog for the length of every transfer. A mutex
	 * serialises concurrent transfers (thread context only — no ISM path) while
	 * leaving interrupts enabled during the poll.
	 */
	struct k_mutex lock;
};

/* One-time (idempotent) release of the shared SCU04[2] I2C reset hold. */
static void i2c_aspeed_g3_scu_release(void)
{
	uint32_t rst;

	/* Unlock the SCU (harmless if already unlocked, e.g. the QEMU -kernel
	 * boot path), then clear the I2C reset-hold bit, preserving the rest.
	 */
	sys_write32(SCU_G3_UNLOCK_MAGIC, SCU_G3_BASE + SCU_G3_PROT_KEY);
	rst = sys_read32(SCU_G3_BASE + SCU_G3_SYS_RST_CTRL);
	sys_write32(rst & ~SCU_G3_RST_I2C, SCU_G3_BASE + SCU_G3_SYS_RST_CTRL);
}

/*
 * Route the multiplexed I2C pins to their I2C function for channels 5/6/7
 * (file header, gotcha 4). Idempotent OR of the matching SCU74 bit; channels
 * 1-4 have dedicated pads and need nothing. `base` is the engine's per-bus
 * register block, from which we recover the datasheet channel number.
 */
static void i2c_aspeed_g3_pinmux(mem_addr_t base)
{
	uint32_t channel = (uint32_t)((base - I2C_CTRL_BASE) / I2C_ENGINE_STRIDE);
	uint32_t bit, mfp;

	if (channel < I2C_MUXED_CHAN_FIRST || channel > I2C_MUXED_CHAN_LAST) {
		return; /* dedicated I2C pads - no pin-mux required */
	}

	bit = BIT(SCU74_SDA5_BIT + (channel - I2C_MUXED_CHAN_FIRST));

	/* SCU protected register: unlock first (idempotent), then set the bit. */
	sys_write32(SCU_G3_UNLOCK_MAGIC, SCU_G3_BASE + SCU_G3_PROT_KEY);
	mfp = sys_read32(SCU_G3_BASE + SCU_G3_MFP_CTL1);
	sys_write32(mfp | bit, SCU_G3_BASE + SCU_G3_MFP_CTL1);
}

static void i2c_aspeed_g3_hw_init(mem_addr_t base)
{
	i2c_aspeed_g3_scu_release();
	i2c_aspeed_g3_pinmux(base);

	/* Mirror the vendor U-Boot i2c_init() ordering. */
	sys_write32(0, base + I2CD_FUN_CTRL);                     /* controller off */
	sys_write32(I2CD_AC_TIMING1_VENDOR, base + I2CD_AC_TIMING1);
	sys_write32(I2CD_AC_TIMING2_VENDOR, base + I2CD_AC_TIMING2);
	sys_write32(I2CD_INTR_ENABLE, base + I2CD_INTR_STS);      /* clear status */
	sys_write32(I2CD_MASTER_EN, base + I2CD_FUN_CTRL);        /* master mode */
	sys_write32(I2CD_INTR_ENABLE, base + I2CD_INTR_CTRL);     /* latch status */
}

/* Poll INTR_STS until any of `bits` is set; return the matched bits or -ETIMEDOUT. */
static int i2c_aspeed_g3_wait(mem_addr_t base, uint32_t bits)
{
	for (uint32_t i = 0; i < I2CD_POLL_COUNT; i++) {
		uint32_t sts = sys_read32(base + I2CD_INTR_STS);

		if (sts & bits) {
			return (int)(sts & bits);
		}
	}
	return -ETIMEDOUT;
}

static inline void i2c_aspeed_g3_clear_status(mem_addr_t base)
{
	sys_write32(I2CD_INTR_ENABLE, base + I2CD_INTR_STS);
}

/* (Repeated) START + address byte. `read` selects the R/W direction bit. */
static int i2c_aspeed_g3_start(mem_addr_t base, uint16_t addr, bool read)
{
	uint32_t abyte = ((uint32_t)addr << 1) | (read ? 1U : 0U);
	int sts;

	sys_write32(abyte, base + I2CD_BYTE_BUF);
	sys_write32(I2CD_M_START_CMD | I2CD_M_TX_CMD, base + I2CD_CMD);

	sts = i2c_aspeed_g3_wait(base, I2CD_INTR_TX_ACK | I2CD_INTR_TX_NAK);
	if (sts < 0) {
		return sts;
	}
	i2c_aspeed_g3_clear_status(base);
	if (sts & I2CD_INTR_TX_NAK) {
		return -ENXIO; /* no device acknowledged the address */
	}
	return 0;
}

static int i2c_aspeed_g3_write_bytes(mem_addr_t base, const uint8_t *buf,
				     uint32_t len)
{
	for (uint32_t j = 0; j < len; j++) {
		int sts;

		sys_write32(buf[j], base + I2CD_BYTE_BUF);
		sys_write32(I2CD_M_TX_CMD, base + I2CD_CMD);

		sts = i2c_aspeed_g3_wait(base, I2CD_INTR_TX_ACK | I2CD_INTR_TX_NAK);
		if (sts < 0) {
			return sts;
		}
		i2c_aspeed_g3_clear_status(base);
		if (sts & I2CD_INTR_TX_NAK) {
			return -EIO; /* byte not acknowledged */
		}
	}
	return 0;
}

static int i2c_aspeed_g3_read_bytes(mem_addr_t base, uint8_t *buf, uint32_t len)
{
	for (uint32_t j = 0; j < len; j++) {
		uint32_t cmd = I2CD_M_RX_CMD;
		int sts;

		if (j == len - 1U) {
			cmd |= I2CD_M_RX_CMD_LAST; /* NACK the final byte */
		}
		sys_write32(cmd, base + I2CD_CMD);

		sts = i2c_aspeed_g3_wait(base, I2CD_INTR_RX_DONE);
		if (sts < 0) {
			return sts;
		}
		buf[j] = (sys_read32(base + I2CD_BYTE_BUF) >> I2CD_RX_BUF_SHIFT) &
			 0xFFU;
		i2c_aspeed_g3_clear_status(base);
	}
	return 0;
}

static int i2c_aspeed_g3_stop(mem_addr_t base)
{
	int sts;

	sys_write32(I2CD_M_STOP_CMD, base + I2CD_CMD);
	sts = i2c_aspeed_g3_wait(base, I2CD_INTR_NORMAL_STOP);
	i2c_aspeed_g3_clear_status(base);
	if (sts < 0) {
		return sts;
	}
	return 0;
}

static int i2c_aspeed_g3_transfer(const struct device *dev, struct i2c_msg *msgs,
				  uint8_t num_msgs, uint16_t addr)
{
	const struct i2c_aspeed_g3_config *cfg = dev->config;
	struct i2c_aspeed_g3_data *data = dev->data;
	mem_addr_t base = cfg->base;
	int ret = 0;

	if (num_msgs == 0) {
		return 0;
	}

	k_mutex_lock(&data->lock, K_FOREVER);
	i2c_aspeed_g3_clear_status(base); /* drop any stale status from before */

	for (uint8_t i = 0; i < num_msgs; i++) {
		struct i2c_msg *msg = &msgs[i];
		bool read = (msg->flags & I2C_MSG_READ) != 0;
		bool do_start = (i == 0) || (msg->flags & I2C_MSG_RESTART) != 0;

		if (do_start) {
			ret = i2c_aspeed_g3_start(base, addr, read);
			if (ret != 0) {
				break;
			}
		}

		if (read) {
			ret = i2c_aspeed_g3_read_bytes(base, msg->buf, msg->len);
		} else {
			ret = i2c_aspeed_g3_write_bytes(base, msg->buf, msg->len);
		}
		if (ret != 0) {
			break;
		}

		if (msg->flags & I2C_MSG_STOP) {
			ret = i2c_aspeed_g3_stop(base);
			if (ret != 0) {
				break;
			}
		}
	}

	if (ret != 0) {
		/* Best-effort STOP to release the bus after a failed transfer. */
		(void)i2c_aspeed_g3_stop(base);
	}

	k_mutex_unlock(&data->lock);
	return ret;
}

static int i2c_aspeed_g3_configure(const struct device *dev, uint32_t dev_config)
{
	const struct i2c_aspeed_g3_config *cfg = dev->config;

	if ((dev_config & I2C_MODE_CONTROLLER) == 0) {
		return -ENOTSUP; /* target (slave) mode not implemented */
	}
	if (dev_config & I2C_ADDR_10_BITS) {
		return -ENOTSUP; /* 7-bit addressing only */
	}
	/*
	 * The AC timing is fixed to the vendor ~100 kHz value; computing a
	 * per-speed divider from the APB clock is a follow-up, so only Standard
	 * mode is honoured. Re-run the hardware init to restore a known state.
	 */
	if (I2C_SPEED_GET(dev_config) != I2C_SPEED_STANDARD) {
		return -ENOTSUP;
	}

	i2c_aspeed_g3_hw_init(cfg->base);
	return 0;
}

static const struct i2c_driver_api i2c_aspeed_g3_api = {
	.configure = i2c_aspeed_g3_configure,
	.transfer = i2c_aspeed_g3_transfer,
};

static int i2c_aspeed_g3_init(const struct device *dev)
{
	const struct i2c_aspeed_g3_config *cfg = dev->config;
	struct i2c_aspeed_g3_data *data = dev->data;

	k_mutex_init(&data->lock);
	i2c_aspeed_g3_hw_init(cfg->base);
	return 0;
}

#define I2C_ASPEED_G3_INIT(inst)                                               \
	static struct i2c_aspeed_g3_data i2c_aspeed_g3_data_##inst;             \
	static const struct i2c_aspeed_g3_config i2c_aspeed_g3_config_##inst = {\
		.base = (mem_addr_t)DT_INST_REG_ADDR(inst),                    \
	};                                                                     \
	I2C_DEVICE_DT_INST_DEFINE(inst, i2c_aspeed_g3_init, NULL,               \
				  &i2c_aspeed_g3_data_##inst,                  \
				  &i2c_aspeed_g3_config_##inst, POST_KERNEL,   \
				  CONFIG_I2C_INIT_PRIORITY, &i2c_aspeed_g3_api);

DT_INST_FOREACH_STATUS_OKAY(I2C_ASPEED_G3_INIT)
