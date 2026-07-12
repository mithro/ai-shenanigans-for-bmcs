/* I2C/SMBus firmware test — AST2050 @ 0x1E78A000.
 *
 * 7 I2C engines (datasheet §31; see DATASHEET-I2C.md). One MMIO region: global
 * regs 0x00-0x3F, then per-engine 64-byte blocks. QEMU bus N is at 0x1E78A000 +
 * 0x40*(N+1) (bus 0 = 0x1E78A040). Old Aspeed register layout: I2CD00 function
 * control (MASTER_EN b0), I2CD0C int-enable, I2CD10 int-status (TX_ACK b0, TX_NAK
 * b1, RX_DONE b2, W1C), I2CD14 command (START b0, TX b1, RX b3, RX_LAST b4, STOP
 * b5), I2CD20 byte buffer (TX low, RX [15:8]).
 *
 * The machine seeds an EEPROM at bus 0 / addr 0x50 (the Dell C410X MAC/board-
 * config store, present for the C4 vendor-firmware oracle). This test enables the
 * master, enables the ACK/NAK interrupts (I2CD0C) as real firmware does, and
 * proves the transaction path: a present device (0x50) ACKs, an unused address
 * (0x55) NAKs — exactly what a bare i2cdetect-style probe sees. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define I2C0        (I2C_BASE + 0x40)   /* bus 0 register block */
#define FUN_CTRL    0x00
#define INTR_CTRL   0x0C
#define INTR_STS    0x10
#define CMD         0x14
#define BYTE_BUF    0x20
#define MASTER_EN   0x01u
#define CMD_START   0x01u
#define CMD_TX      0x02u
#define CMD_STOP    0x20u
#define STS_TX_ACK  0x01u
#define STS_TX_NAK  0x02u
#define STS_RX_DONE 0x04u
/* I2CD0C interrupt-enable bits share I2CD10's bit layout (datasheet §31, I2CD0C
 * bits [2:0] = RX-done/TX-NAK/TX-ACK enable). Real firmware — Linux i2c-aspeed
 * (ASPEED_I2CD_INTR_TX_ACK|TX_NAK|RX_DONE in its INTR_CTRL write), U-Boot's
 * ast_i2c, and the Avocent vendor driver — enables these before *every* master
 * transfer, then polls I2CD10. The AST2050 latches the 9th-clock ACK/NAK into
 * I2CD10[0]/[1]; the controller surfaces the *enabled* sources, so a probe that
 * leaves I2CD0C=0 sees nothing. Enable them here to observe the ACK the way
 * firmware (and i2cdetect's kernel driver) does. */
#define INTR_EN_ALL (STS_TX_ACK | STS_TX_NAK | STS_RX_DONE)

const char fwtest_name[] = "i2c";

/* engine block for QEMU bus index e (e=0..6): 0x1E78A000 + 0x40*(e+1). */
#define BUS(e) (I2C_BASE + 0x40u * ((e) + 1u))

/* Return 1 if a 7-bit device address ACKs a write on engine block `base`. */
static u32 i2c_addr_acks(u32 base, u32 dev7)
{
    writel(base + FUN_CTRL, MASTER_EN);
    writel(base + INTR_CTRL, INTR_EN_ALL);         /* enable ACK/NAK like firmware */
    writel(base + INTR_STS, 0xFFFFFFFFu);          /* clear status */
    writel(base + BYTE_BUF, (dev7 << 1) | 0u);     /* addr + write */
    writel(base + CMD, CMD_START);                 /* START sends the addr byte */
    u32 sts = 0, i;
    for (i = 0; i < 200000u; i++) {
        sts = readl(base + INTR_STS);
        if (sts & (STS_TX_ACK | STS_TX_NAK)) {
            break;
        }
    }
    writel(base + CMD, CMD_STOP);
    writel(base + INTR_STS, 0xFFFFFFFFu);
    return (sts & STS_TX_ACK) ? 1u : 0u;
}

void fwtest_run(void)
{
    /* --- SCU04[2] reset-hold: the G3 powers up with the whole 7-engine I2C
     *     controller HELD IN RESET (SCU04 reset default has bit2=1, datasheet
     *     §18 p205). While held, the register file is inert — writes are
     *     dropped. Real firmware (Raptor ast_scu_init_i2c(), mainline
     *     i2c-aspeed reset_control_deassert) must clear the bit first; do the
     *     same here, and assert the inert-while-held behaviour on the way. --- */
    writel(I2C0 + FUN_CTRL, MASTER_EN);                /* dropped: still held */
    fwt_check("held_in_reset.inert", readl(I2C0 + FUN_CTRL), 0);
    writel(SCU_BASE + SCU_PROTECT, 0x1688A8A8u);       /* unlock SCU          */
    writel(SCU_BASE + SCU_RESET,
           readl(SCU_BASE + SCU_RESET) & ~(1u << 2));  /* de-assert I2C reset */

    /* --- reset / RW on engine 0 --- */
    u32 fc = fwt_reg("fun_ctrl.reset", I2C0 + FUN_CTRL);
    fwt_reg("intr_ctrl.reset", I2C0 + INTR_CTRL);
    fwt_check("fun_ctrl.reset", fc, 0);
    writel(I2C0 + FUN_CTRL, MASTER_EN);
    fwt_check("master_en.rw", readl(I2C0 + FUN_CTRL) & MASTER_EN, MASTER_EN);

    /* --- the master engine executes a START command: it auto-clears the START
     *     bit and reports a transaction result. Enable the ACK/NAK interrupts
     *     first (I2CD0C) — the AST2050 latches the 9th-clock ACK/NAK into I2CD10,
     *     and firmware/i2cdetect always enables these before polling. Address
     *     0x55 is unused on bus 0, so the master samples NO ACK → TX_NAK. --- */
    writel(I2C0 + INTR_CTRL, INTR_EN_ALL);
    writel(I2C0 + INTR_STS, 0xFFFFFFFFu);
    writel(I2C0 + BYTE_BUF, (0x55u << 1) | 0u);     /* an unused address */
    writel(I2C0 + CMD, CMD_START);
    u32 sts = 0, i;
    for (i = 0; i < 200000u; i++) {
        sts = readl(I2C0 + INTR_STS);
        if (sts & (STS_TX_ACK | STS_TX_NAK)) {
            break;
        }
    }
    u32 cmd_after = readl(I2C0 + CMD);
    writel(I2C0 + CMD, CMD_STOP);
    writel(I2C0 + INTR_STS, 0xFFFFFFFFu);
    fwt_kv("cmd.after_start", cmd_after);   /* status/state field in [23:16] */
    fwt_kv("probe.sts", sts);
    fwt_check("start.autoclears", cmd_after & CMD_START, 0);   /* engine ran   */
    fwt_check("unused.naks", sts & STS_TX_NAK, STS_TX_NAK);    /* 0x55 → NAK    */

    /* --- Scan all 7 engine blocks for a device ACK at 0x50. The shared
     *     kgpe-d16-bmc machine carries ONE device at 0x50: an smbus_eeprom on
     *     bus 0 — the Dell C410X MAC/board-config store, seeded for the C4
     *     vendor-firmware oracle (dell-c410x-firmware/ANALYSIS.md §"EEPROM 0x50+
     *     I2C0"). It is NOT a KGPE-D16 board device — the KGPE-D16 has no
     *     attested probe-able BMC I2C EEPROM (its FRU is software-populated; see
     *     DOC.md §2.1). What THIS test proves is the shared AST2050 I2C *master
     *     engine* address-probe behaviour, which is silicon-faithful and common
     *     to both boards: bus 0 ACKs (the smbus_eeprom acknowledges the addr+W
     *     probe → the master latches TX_ACK into I2CD10[0], datasheet §31.5);
     *     buses 1-6 have no device at 0x50 → NAK → their bits stay 0. Record a
     *     per-bus bitmask so no result is lost. See DOC.md §2. --- */
    u32 e, mask = 0;
    for (e = 0; e < 7u; e++) {
        if (i2c_addr_acks(BUS(e), 0x50)) {
            mask |= (1u << e);
        }
    }
    fwt_kv("ack50.mask", mask);
    fwt_check("eeprom50.acks", mask & 1u, 1u);   /* bus 0 EEPROM ACKs a probe */
}
