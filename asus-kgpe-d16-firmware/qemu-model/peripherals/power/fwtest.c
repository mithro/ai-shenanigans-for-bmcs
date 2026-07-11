/* KGPE-D16 (AST2050) host power-control firmware test — GPIO @ 0x1E780000.
 *
 * Exercises the board power-sequencer glue modeled in the Aspeed GPIO device
 * (hw/gpio/aspeed_gpio.c aspeed_gpio_kgpe_d16_pwrseq). The BMC drives three
 * active-low request lines and reads one power-state input, per Raptor's
 * asus_power.sh (see HW-WIRING-power-sensors.md §1.2):
 *
 *   GPIOB1 CTL_REQ_POWERUP_N   (bank B pin1 -> GPIO00/04 bit 9)  power-on req
 *   GPIOB6 CTL_REQ_RESET_N     (bank B pin6 -> GPIO00/04 bit 14) warm-reset req
 *   GPIOF0 CTL_REQ_POWERDOWN_N (bank F pin0 -> GPIO20/24 bit 8)  force-off req
 *   GPIOH2 STA_LINE_POWER      (bank H pin2 -> GPIO20    bit 26) 1=on input
 *
 * All request lines are active low; the modeled host-power state is a set/reset
 * latch (POWERUP sets, POWERDOWN clears, RESET leaves unchanged) reflected on
 * GPIOH2. This is the QEMU half of the "Redfish -> state-manager -> GPIO ->
 * power-state" loop; the SAME .elf can run on the real AST2050 over the RPi rig
 * to prove the wiring end to end. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define GPIO_DATA_AD (GPIO_BASE + 0x00u)  /* banks A-D data value */
#define GPIO_DIR_AD  (GPIO_BASE + 0x04u)  /* banks A-D direction (1=out) */
#define GPIO_DATA_EH (GPIO_BASE + 0x20u)  /* banks E-H data value */
#define GPIO_DIR_EH  (GPIO_BASE + 0x24u)  /* banks E-H direction (1=out) */

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

void fwtest_run(void)
{
    /* Directions: B1,B6 outputs (A-D dir bits 9,14); F0 output (E-H dir bit 8);
     * H2 input (E-H dir bit 26 = 0). */
    writel(GPIO_DIR_AD, readl(GPIO_DIR_AD) | (1u << B1_BIT) | (1u << B6_BIT));
    writel(GPIO_DIR_EH, (readl(GPIO_DIR_EH) | (1u << F0_BIT)) & ~(1u << H2_BIT));

    /* De-assert every active-low request line (drive high). */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N   = 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1 */

    /* Host is OFF out of reset: GPIOH2 reads 0. */
    fwt_reg("h2.reset", GPIO_DATA_EH);
    fwt_check("power.off_at_reset", reg_getbit(GPIO_DATA_EH, H2_BIT), 0);

    /* --- Power ON (asus_power.sh on) --- */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 0);   /* RESET_N     = 0 */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 0);   /* POWERUP_N   = 0  -> engages power */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N   = 1  (release; latch holds) */
    fwt_reg("h2.after_on", GPIO_DATA_EH);
    fwt_check("power.on_after_powerup", reg_getbit(GPIO_DATA_EH, H2_BIT), 1);

    /* --- Warm RESET (asus_power.sh reset): host stays ON --- */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 0);   /* RESET_N     = 0  -> pulse reset */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N stays 1 */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    fwt_reg("h2.after_reset", GPIO_DATA_EH);
    fwt_check("power.on_after_reset", reg_getbit(GPIO_DATA_EH, H2_BIT), 1);

    /* --- Power OFF (asus_power.sh off) --- */
    reg_setbit(GPIO_DATA_AD, B6_BIT, 1);   /* RESET_N     = 1 */
    reg_setbit(GPIO_DATA_AD, B1_BIT, 1);   /* POWERUP_N   = 1 */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 0);   /* POWERDOWN_N = 0  -> forces off */
    reg_setbit(GPIO_DATA_EH, F0_BIT, 1);   /* POWERDOWN_N = 1  (release) */
    fwt_reg("h2.after_off", GPIO_DATA_EH);
    fwt_check("power.off_after_powerdown", reg_getbit(GPIO_DATA_EH, H2_BIT), 0);
}
