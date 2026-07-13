/* KGPE-D16 (AST2050) host power-control firmware test — GPIO @ 0x1E780000.
 *
 * Exercises the board power-sequencer glue modeled in the Aspeed GPIO device
 * (hw/gpio/aspeed_gpio.c aspeed_gpio_kgpe_d16_pwrseq). The BMC drives three
 * active-low request lines and reads one power-state input, per Raptor's
 * asus_power.sh (see HW-WIRING-power-sensors.md §1.2), and must first reclaim
 * a BMC-in-control gate line:
 *
 *   GPIOA4 ASUS_BMC_CTL_LOCKOUT_N (bank A pin4 -> GPIO00/04 bit 4)  in-ctrl gate
 *   GPIOB1 CTL_REQ_POWERUP_N   (bank B pin1 -> GPIO00/04 bit 9)  power-on req
 *   GPIOB6 CTL_REQ_RESET_N     (bank B pin6 -> GPIO00/04 bit 14) warm-reset req
 *   GPIOF0 CTL_REQ_POWERDOWN_N (bank F pin0 -> GPIO20/24 bit 8)  force-off req
 *   GPIOH2 STA_LINE_POWER      (bank H pin2 -> GPIO20    bit 26) 1=on input
 *
 * All request lines are active low; the modeled host-power state is a set/reset
 * latch (POWERUP sets, POWERDOWN clears, RESET leaves unchanged) reflected on
 * GPIOH2.
 *
 * HARDWARE FINDING (verified 2026-07-13 on the real AST2050): the board only
 * honours CTL_REQ_POWERUP_N while GPIOA4 (ASUS_BMC_CTL_LOCKOUT_N) is driven
 * HIGH as a real GPIO output ("BMC in control"). A4's pad defaults to the
 * PHYLINK alt-function (SCU74[25]=1), so a stock image cannot power the host
 * ON — only force it OFF. This test proves both halves: a power-up WITHOUT the
 * A4 reclaim is IGNORED (host stays off), and the SAME sequence AFTER driving
 * A4 high powers the host on.
 *
 * This is the QEMU half of the "Redfish -> state-manager -> GPIO ->
 * power-state" loop; the SAME .elf can run on the real AST2050 over the RPi rig
 * to prove the wiring end to end. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define GPIO_DATA_AD (GPIO_BASE + 0x00u)  /* banks A-D data value */
#define GPIO_DIR_AD  (GPIO_BASE + 0x04u)  /* banks A-D direction (1=out) */
#define GPIO_DATA_EH (GPIO_BASE + 0x20u)  /* banks E-H data value */
#define GPIO_DIR_EH  (GPIO_BASE + 0x24u)  /* banks E-H direction (1=out) */

#define SCU74 0x74u                        /* SCU multi-function pin control  */

#define A4_BIT 4   /* GPIOA4 bmc-ctl-lockout-n in GPIO00/04 */
#define B1_BIT 9   /* GPIOB1 power-up-req-n   in GPIO00/04 */
#define B6_BIT 14  /* GPIOB6 reset-req-n      in GPIO00/04 */
#define F0_BIT 8   /* GPIOF0 power-down-req-n in GPIO20/24 */
#define H2_BIT 26  /* GPIOH2 power-state-in   in GPIO20    */

const char fwtest_name[] = "power";

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

static int reg_getbit(u32 addr, int bit)
{
    return (readl(addr) >> bit) & 1u;
}

/* Run the exact asus_power.sh power-ON pulse (POWERUP_N low with RESET_N low
 * then both released). Whether it engages the host depends on the A4 gate. */
static void pulse_power_up(void)
{
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 0);   /* RESET_N     = 0 */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 0);   /* POWERUP_N   = 0  -> requests power */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N   = 1  (release; latch holds) */
}

/* Reclaim GPIOA4 as a driven-high output = "BMC in control". On silicon A4's
 * pad defaults to the PHYLINK alt-function (SCU74[25]=1); clear it so A4 is a
 * real GPIO, then drive it high. The QEMU model gates purely on the GPIO A4
 * output state, so the SCU write is a no-op there but keeps this .elf faithful
 * to what the real AST2050 requires. */
static void reclaim_gpioa4(void)
{
    writel(SCU_BASE + SCU_PROTECT, 0x1688A8A8u);  /* unlock the SCU */
    reg_setbit(SCU_BASE + SCU74, 25, 0);          /* SCU74[25]=0 -> A4 = GPIO */
    reg_setbit(GPIO_DIR_AD, A4_BIT, 1);           /* A4 direction = out */
    reg_setbit(GPIO_DATA_AD, A4_BIT, 1);          /* A4 data = 1 (drive high) */
}

void fwtest_run(void)
{
    /* Directions: B1,B6 outputs (A-D dir bits 9,14); F0 output (E-H dir bit 8);
     * H2 input (E-H dir bit 26 = 0). A4 is deliberately left as an input
     * (NOT driven) for now so the "stock image" negative case is exercised. */
    writel(GPIO_DIR_AD, readl(GPIO_DIR_AD) | (1u << B1_BIT) | (1u << B6_BIT));
    writel(GPIO_DIR_EH, (readl(GPIO_DIR_EH) | (1u << F0_BIT)) & ~(1u << H2_BIT));

    /* De-assert every active-low request line (drive high). */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N   = 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1 */

    /* Host is OFF out of reset: GPIOH2 reads 0. */
    fwt_reg("h2.reset", GPIO_DATA_EH);
    fwt_check("power.off_at_reset", reg_getbit(GPIO_DATA_EH, H2_BIT), 0);

    /* --- NEGATIVE (faithfulness): power-up with A4 NOT reclaimed is IGNORED ---
     * The stock-image case: A4 is still the PHYLINK alt-func / not a driven-high
     * output, so the board ignores POWERUP_N and the host stays OFF. */
    pulse_power_up();
    fwt_reg("h2.no_a4", GPIO_DATA_EH);
    fwt_check("power.on_blocked_without_a4", reg_getbit(GPIO_DATA_EH, H2_BIT), 0);

    /* --- Reclaim GPIOA4 high ("BMC in control"), then the SAME pulse works --- */
    reclaim_gpioa4();
    pulse_power_up();
    fwt_reg("h2.after_a4", GPIO_DATA_EH);
    fwt_check("power.on_after_a4_reclaim", reg_getbit(GPIO_DATA_EH, H2_BIT), 1);

    /* --- Warm RESET (asus_power.sh reset): host stays ON --- */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 0);   /* RESET_N     = 0  -> pulse reset */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N stays 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    fwt_reg("h2.after_reset", GPIO_DATA_EH);
    fwt_check("power.on_after_reset", reg_getbit(GPIO_DATA_EH, H2_BIT), 1);

    /* --- Power OFF (asus_power.sh off): force-off wins regardless of A4 --- */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N   = 1 */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 0);   /* POWERDOWN_N = 0  -> forces off */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1  (release) */
    fwt_reg("h2.after_off", GPIO_DATA_EH);
    fwt_check("power.off_after_powerdown", reg_getbit(GPIO_DATA_EH, H2_BIT), 0);

    /* --- Power ON again (A4 still held high): the classic on_after_powerup --- */
    pulse_power_up();
    fwt_reg("h2.after_on", GPIO_DATA_EH);
    fwt_check("power.on_after_powerup", reg_getbit(GPIO_DATA_EH, H2_BIT), 1);
}
