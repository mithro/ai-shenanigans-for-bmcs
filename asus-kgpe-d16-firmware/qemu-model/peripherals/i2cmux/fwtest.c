/* KGPE-D16 I2C mux fabric (QU9/QU5/U23) firmware test — engine I2C2 + GPIO.
 *
 * Proves the board fabric between the BMC's I2C2 engine (QEMU bus index 1)
 * and the DIMM SPD/TSOD buses, as decoded from the schematic netlist
 * (schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md):
 *
 *   - QU9's enable is inverted SYS_PWRGD: with the host OFF the whole fabric
 *     is disconnected — every probe NAKs. The BMC has NO enable GPIO.
 *   - QU5 routes the common to Y0/Y2/Y3 by S1:S0 = GPIOF5:GPIOF4; the select
 *     nets have 4.7k pull-ups, so the idle/undriven state is 11 (bank E-H).
 *   - The rig population is one DIMM in slot A2: SPD 0x51 + TSOD 0x19 on
 *     bank Y2 (S1:S0 = 10), per the SA-strap map (fabric doc §5b).
 *
 * Sequence: host off → probe NAKs; power the host on via the modeled
 * sequencer (A4 reclaim + POWERUP_N pulse, same as peripherals/power); idle
 * selects = Y3 (empty) → 0x51 still NAKs; drive GPIOF4 low → Y2 → SPD 0x51
 * and TSOD 0x19 ACK, absent 0x50 NAKs; read SPD byte 0 = 0x92 (the DDR3 SPD
 * header); force the host off → the fabric vanishes again. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define GPIO_DATA_AD (GPIO_BASE + 0x00u)
#define GPIO_DIR_AD  (GPIO_BASE + 0x04u)
#define GPIO_DATA_EH (GPIO_BASE + 0x20u)
#define GPIO_DIR_EH  (GPIO_BASE + 0x24u)
#define SCU74 0x74u

#define A4_BIT 4    /* GPIOA4 bmc-ctl-lockout-n  (A-D)  */
#define B1_BIT 9    /* GPIOB1 power-up-req-n     (A-D)  */
#define B6_BIT 14   /* GPIOB6 reset-req-n        (A-D)  */
#define F0_BIT 8    /* GPIOF0 power-down-req-n   (E-H)  */
#define H2_BIT 26   /* GPIOH2 power-state-in     (E-H)  */
#define F4_BIT 12   /* GPIOF4 AST_I2CS0 (QU5 S0) (E-H)  */
#define F5_BIT 13   /* GPIOF5 AST_I2CS1 (QU5 S1) (E-H)  */

/* Engine block for QEMU bus index e: I2C2 is index 1. */
#define BUS(e)      (I2C_BASE + 0x40u * ((e) + 1u))
#define I2C2        BUS(1)
#define FUN_CTRL    0x00
#define INTR_CTRL   0x0C
#define INTR_STS    0x10
#define CMD         0x14
#define BYTE_BUF    0x20
#define MASTER_EN   0x01u
#define CMD_START   0x01u
#define CMD_TX      0x02u
#define CMD_RX      0x08u
#define CMD_RX_LAST 0x10u
#define CMD_STOP    0x20u
#define STS_TX_ACK  0x01u
#define STS_TX_NAK  0x02u
#define STS_RX_DONE 0x04u
#define INTR_EN_ALL (STS_TX_ACK | STS_TX_NAK | STS_RX_DONE)

const char fwtest_name[] = "i2cmux";

static void reg_setbit(u32 addr, int bit, int val)
{
    u32 v = readl(addr);
    if (val) {
        v |= (1u << bit);
    } else {
        v &= ~(1u << bit);
    }
    writel(addr, v);
}

static u32 wait_sts(u32 base, u32 want)
{
    u32 sts = 0, i;
    for (i = 0; i < 200000u; i++) {
        sts = readl(base + INTR_STS);
        if (sts & want) {
            break;
        }
    }
    return sts;
}

/* 1 iff a 7-bit address ACKs an addr+W probe on engine `base`. */
static u32 i2c_addr_acks(u32 base, u32 dev7)
{
    writel(base + FUN_CTRL, MASTER_EN);
    writel(base + INTR_CTRL, INTR_EN_ALL);
    writel(base + INTR_STS, 0xFFFFFFFFu);
    writel(base + BYTE_BUF, (dev7 << 1) | 0u);
    writel(base + CMD, CMD_START);
    u32 sts = wait_sts(base, STS_TX_ACK | STS_TX_NAK);
    writel(base + CMD, CMD_STOP);
    writel(base + INTR_STS, 0xFFFFFFFFu);
    return (sts & STS_TX_ACK) ? 1u : 0u;
}

/* Random-read one byte at `off` from EEPROM `dev7`; 0x100 on any NAK. */
static u32 i2c_read_byte(u32 base, u32 dev7, u32 off)
{
    writel(base + FUN_CTRL, MASTER_EN);
    writel(base + INTR_CTRL, INTR_EN_ALL);
    writel(base + INTR_STS, 0xFFFFFFFFu);

    writel(base + BYTE_BUF, (dev7 << 1) | 0u);        /* START, addr+W */
    writel(base + CMD, CMD_START);
    if (!(wait_sts(base, STS_TX_ACK | STS_TX_NAK) & STS_TX_ACK)) {
        goto nak;
    }
    writel(base + INTR_STS, 0xFFFFFFFFu);

    writel(base + BYTE_BUF, off);                     /* word address    */
    writel(base + CMD, CMD_TX);
    if (!(wait_sts(base, STS_TX_ACK | STS_TX_NAK) & STS_TX_ACK)) {
        goto nak;
    }
    writel(base + INTR_STS, 0xFFFFFFFFu);

    writel(base + BYTE_BUF, (dev7 << 1) | 1u);        /* rep-START, addr+R */
    writel(base + CMD, CMD_START);
    if (!(wait_sts(base, STS_TX_ACK | STS_TX_NAK) & STS_TX_ACK)) {
        goto nak;
    }
    writel(base + INTR_STS, 0xFFFFFFFFu);

    writel(base + CMD, CMD_RX | CMD_RX_LAST);         /* read + NAK last  */
    if (!(wait_sts(base, STS_RX_DONE) & STS_RX_DONE)) {
        goto nak;
    }
    u32 val = (readl(base + BYTE_BUF) >> 8) & 0xFFu;
    writel(base + CMD, CMD_STOP);
    writel(base + INTR_STS, 0xFFFFFFFFu);
    return val;

nak:
    writel(base + CMD, CMD_STOP);
    writel(base + INTR_STS, 0xFFFFFFFFu);
    return 0x100u;
}

static void pulse_power_up(void)
{
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);
    reg_setbit(GPIO_DATA_AD, B6_BIT, 0);
    reg_setbit(GPIO_DATA_AD, B1_BIT, 0);
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);
}

static void reclaim_gpioa4(void)
{
    writel(SCU_BASE + SCU_PROTECT, 0x1688A8A8u);
    reg_setbit(SCU_BASE + SCU74, 25, 0);
    reg_setbit(GPIO_DIR_AD, A4_BIT, 1);
    reg_setbit(GPIO_DATA_AD, A4_BIT, 1);
}

void fwtest_run(void)
{
    /* Release the I2C controller from its SCU04[2] power-up reset-hold. */
    writel(SCU_BASE + SCU_PROTECT, 0x1688A8A8u);
    writel(SCU_BASE + SCU_RESET, readl(SCU_BASE + SCU_RESET) & ~(1u << 2));

    /* Power-sequencer request lines idle (as peripherals/power). */
    writel(GPIO_DIR_AD, readl(GPIO_DIR_AD) | (1u << B1_BIT) | (1u << B6_BIT));
    writel(GPIO_DIR_EH,
           (readl(GPIO_DIR_EH) | (1u << F0_BIT)) & ~(1u << H2_BIT));
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);

    /* --- Host OFF: QU9 is open — the DIMM SPD does not exist on the bus.
     *     (The W83795G at 0x2f sits DIRECTLY on I2C2, before the fabric,
     *     so it must ACK regardless of host power.) --- */
    fwt_check("hostoff.spd_naks", i2c_addr_acks(I2C2, 0x51), 0);
    fwt_check("hostoff.hwmon_acks", i2c_addr_acks(I2C2, 0x2f), 1);

    /* --- Power the host on (A4 reclaim + POWERUP_N pulse). --- */
    reclaim_gpioa4();
    pulse_power_up();

    /* --- Idle selects: the 4.7k pull-ups leave S1:S0 = 11 -> bank Y3
     *     (DIMM E-H), which is EMPTY on the rig -> 0x51 still NAKs. --- */
    fwt_check("hoston.y3_empty", i2c_addr_acks(I2C2, 0x51), 0);

    /* --- Route to bank Y2 (DIMM A-D): S1:S0 = 10 -> drive GPIOF4 low. --- */
    reg_setbit(GPIO_DIR_EH, F4_BIT, 1);
    reg_setbit(GPIO_DATA_EH, F4_BIT, 0);
    fwt_check("y2.spd_acks", i2c_addr_acks(I2C2, 0x51), 1);
    fwt_check("y2.tsod_acks", i2c_addr_acks(I2C2, 0x19), 1);
    fwt_check("y2.empty_slot_naks", i2c_addr_acks(I2C2, 0x50), 0);

    /* --- Data path: SPD byte 0 is the DDR3 header 0x92 (bytes-used/CRC
     *     coverage), byte 2 is the memory type 0x0B = DDR3. --- */
    fwt_kv("spd.b0", i2c_read_byte(I2C2, 0x51, 0));
    fwt_kv("spd.b2", i2c_read_byte(I2C2, 0x51, 2));
    fwt_check("spd.header", i2c_read_byte(I2C2, 0x51, 0), 0x92);
    fwt_check("spd.ddr3", i2c_read_byte(I2C2, 0x51, 2), 0x0B);

    /* --- Back to Y3: the same addresses vanish (routing, not caching). --- */
    reg_setbit(GPIO_DATA_EH, F4_BIT, 1);
    fwt_check("y3.spd_gone", i2c_addr_acks(I2C2, 0x51), 0);
    reg_setbit(GPIO_DATA_EH, F4_BIT, 0);

    /* --- Force the host OFF: QU9 opens mid-session, fabric vanishes. --- */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 0);
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);
    fwt_check("hostoff2.spd_naks", i2c_addr_acks(I2C2, 0x51), 0);
    fwt_check("hostoff2.hwmon_acks", i2c_addr_acks(I2C2, 0x2f), 1);
}
