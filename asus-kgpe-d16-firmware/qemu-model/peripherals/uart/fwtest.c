/* UART firmware test — AST2050 UART1 @0x1E783000, UART2/console @0x1E784000.
 *
 * The AST2050 UARTs are 16550-compatible (datasheet §; hwreg.h). The G3-specific
 * detail is the baud clock (24 MHz, optional /13 via SCU2C[12]) — a rate matter,
 * not a register one. This checks 16550 register behaviour: the scratch register
 * (0x1C) is RW, LSR reports transmit-ready, and an internal MCR[4] loopback echoes
 * THR->RBR. Loopback is exercised on UART1 (not the console) so it can't disturb
 * the [FWT] transcript on UART2. Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define RBR 0x00   /* read: receive buffer   */
#define THR 0x00   /* write: transmit hold   */
#define FCR 0x08
#define LCR 0x0C
#define MCR 0x10
#define LSR 0x14
#define SCR 0x1C   /* scratch (RW)           */
#define LSR_DR   (1u << 0)
#define LSR_THRE (1u << 5)
#define MCR_LOOP (1u << 4)

const char fwtest_name[] = "uart";

void fwtest_run(void)
{
    /* --- console UART (UART2): 16550 register presence (non-disruptive) --- */
    writel(UART5_BASE + SCR, 0xA5);
    fwt_check("con.scratch.a5", readl(UART5_BASE + SCR) & 0xff, 0xA5);
    writel(UART5_BASE + SCR, 0x5A);
    fwt_check("con.scratch.5a", readl(UART5_BASE + SCR) & 0xff, 0x5A);
    fwt_check("con.thre", (readl(UART5_BASE + LSR) >> 5) & 1u, 1u);

    /* --- UART1: MCR[4] internal loopback echoes a byte THR -> RBR --- */
    fwt_reg("uart1.scratch", UART1_BASE + SCR);   /* observe presence */
    writel(UART1_BASE + LCR, 0x03);               /* 8N1              */
    writel(UART1_BASE + FCR, 0x07);               /* enable+clear FIFO */
    writel(UART1_BASE + MCR, MCR_LOOP);           /* internal loopback */
    writel(UART1_BASE + THR, 0x42);
    u32 i;
    for (i = 0; i < 200000u && !(readl(UART1_BASE + LSR) & LSR_DR); i++) {
    }
    u32 rx = readl(UART1_BASE + RBR) & 0xff;
    fwt_kv("uart1.rx", rx);
    fwt_check("uart1.loopback", rx, 0x42);
}
