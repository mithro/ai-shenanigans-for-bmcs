/* PWM/Tachometer firmware test — AST2050 @ 0x1E786000.
 *
 * 4 PWM outputs + 16 fan-tach inputs (datasheet §28; see DATASHEET-PWM.md).
 * PTCR00 general control ([0]master clk, [11:8]PWM A-D enable, [31:16]tach en),
 * PTCR08/0C duty (8-bit rise/fall, 1/256), PTCR2C result (R: [31]full [19:0]value).
 * RPM = (24e6*60)/(2*TachoValue*TachoClkDiv). Nothing exists >= 0x40. OpenBMC uses
 * this for fan control/monitor. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define PTCR00 0x00
#define PTCR08 0x08
#define PTCR2C 0x2C

const char fwtest_name[] = "pwm";

void fwtest_run(void)
{
    fwt_reg("ptcr00.reset", PWM_BASE + PTCR00);

    /* PTCR00 RW: master clock enable (b0) + PWM channel A enable (b8) */
    writel(PWM_BASE + PTCR00, 0x00000101u);
    u32 v = fwt_reg("ptcr00.rw", PWM_BASE + PTCR00);
    fwt_check("ptcr00.master_en", v & 1u, 1u);
    fwt_check("ptcr00.pwmA_en", (v >> 8) & 1u, 1u);

    /* duty register RW */
    writel(PWM_BASE + PTCR08, 0x00007F00u);
    fwt_check("duty.rw", readl(PWM_BASE + PTCR08) & 0x0000FF00u, 0x00007F00u);
}
