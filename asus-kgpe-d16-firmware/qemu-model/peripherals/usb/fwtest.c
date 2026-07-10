/* USB2.0 device / virtual-hub controller — AST2050 @ 0x1E6A0000 (see DATASHEET-USB.md).
 * Virtual media/keyboard/mouse path. AST2050 has NO EHCI host at 0x1E6A1000 (AST2400+).
 * Not modelled in QEMU (vhub unmodelled). Apache-2.0. */
#include "harness.h"
#include "ast2050.h"
const char fwtest_name[] = "usb";
void fwtest_run(void)
{
    fwt_reg("hub00.root", USB_UDC_BASE + 0x00);
    fwt_reg("ehci1000",   USB_UDC_BASE + 0x1000);   /* AST2400+ EHCI (absent on G3) */
    writel(USB_UDC_BASE + 0x00, 0x00000001u);
    fwt_check("hub00.rw", readl(USB_UDC_BASE + 0x00) & 1u, 1u);
}
