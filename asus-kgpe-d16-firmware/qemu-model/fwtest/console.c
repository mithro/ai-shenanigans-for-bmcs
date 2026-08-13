/* UART console + report protocol implementation. See console.h. Apache-2.0. */
#include "console.h"

/* 16550-compatible register offsets (byte registers, 32-bit stride). */
#define UART_THR 0x00u   /* write: transmit holding (DLAB=0)                 */
#define UART_DLL 0x00u   /* divisor low (DLAB=1)                             */
#define UART_IER 0x04u   /* interrupt enable (DLAB=0)                        */
#define UART_DLH 0x04u   /* divisor high (DLAB=1)                            */
#define UART_FCR 0x08u   /* FIFO control (write)                            */
#define UART_LCR 0x0Cu   /* line control                                    */
#define UART_LSR 0x14u   /* line status                                     */
#define LSR_THRE (1u << 5)  /* transmit holding register empty             */

/*
 * Divisor for real silicon. The AST2050 UART reference is 24 MHz / 13 =
 * 1.8462 MHz; divisor = clk / (16 * baud). QEMU's 16550 ignores the divisor
 * (it transmits on every THR write), so this only matters on hardware. Default
 * 115200 -> divisor 1 (1.8462e6 / (16*115200) ~= 1.0). Overridable at build.
 */
#ifndef FWT_UART_DIVISOR
#define FWT_UART_DIVISOR 1u
#endif

void console_init(void)
{
    writel(UART_CONSOLE_BASE + UART_IER, 0x00);
    writel(UART_CONSOLE_BASE + UART_LCR, 0x83);            /* DLAB=1, 8N1    */
    writel(UART_CONSOLE_BASE + UART_DLL, FWT_UART_DIVISOR & 0xff);
    writel(UART_CONSOLE_BASE + UART_DLH, (FWT_UART_DIVISOR >> 8) & 0xff);
    writel(UART_CONSOLE_BASE + UART_LCR, 0x03);            /* DLAB=0, 8N1    */
    writel(UART_CONSOLE_BASE + UART_FCR, 0x07);            /* enable+clear   */
}

void con_putc(char c)
{
    while (!(readl(UART_CONSOLE_BASE + UART_LSR) & LSR_THRE))
        ;
    writel(UART_CONSOLE_BASE + UART_THR, (unsigned char)c);
}

void con_puts(const char *s)
{
    for (; *s; s++) {
        if (*s == '\n')
            con_putc('\r');
        con_putc(*s);
    }
}

void con_puthex32(u32 v)
{
    static const char hex[] = "0123456789abcdef";
    int i;
    for (i = 28; i >= 0; i -= 4)
        con_putc(hex[(v >> i) & 0xf]);
}

static u32 s_checks;
static u32 s_fails;

void fwt_begin(const char *name)
{
    s_checks = 0;
    s_fails = 0;
    con_puts("[FWT] begin ");
    con_puts(name);
    con_putc('\n');
}

u32 fwt_reg(const char *label, u32 addr)
{
    u32 v = readl(addr);
    con_puts("[FWT] reg ");
    con_puts(label);
    con_putc(' ');
    con_puthex32(addr);
    con_puts(" = ");
    con_puthex32(v);
    con_putc('\n');
    return v;
}

void fwt_kv(const char *key, u32 val)
{
    con_puts("[FWT] kv ");
    con_puts(key);
    con_puts(" = ");
    con_puthex32(val);
    con_putc('\n');
}

void fwt_check(const char *label, u32 got, u32 want)
{
    s_checks++;
    con_puts("[FWT] check ");
    con_puts(label);
    if (got == want) {
        con_puts(" PASS got=");
    } else {
        s_fails++;
        con_puts(" FAIL got=");
    }
    con_puthex32(got);
    con_puts(" want=");
    con_puthex32(want);
    con_putc('\n');
}

void fwt_end(const char *name)
{
    con_puts("[FWT] end ");
    con_puts(name);
    con_puts(" checks=");
    con_puthex32(s_checks);
    con_puts(" fails=");
    con_puthex32(s_fails);
    con_putc('\n');
    con_puts("[FWT] halt\n");
}
