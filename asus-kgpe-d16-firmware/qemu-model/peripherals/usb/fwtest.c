/* USB2.0 device / virtual-hub controller — AST2050 @ 0x1E6A0000 (see DATASHEET-USB.md).
 *
 * The AST2050's ONLY USB block: a USB2.0 *device / virtual-hub* controller — the
 * BMC virtual-media / virtual-keyboard/mouse (KVM) datapath. The AST2050 has NO USB
 * *host* controller (no EHCI at 0x1E6A1000 — that is an AST2400+ block; datasheet §9
 * memory map p.97 shows one USB region, §10 gives IRQ INT#5). Modelled in QEMU as
 * aspeed.udc-ast2050 (register block, 0x000-0x2FF). This test walks the datasheet
 * §15.4 init/register map to confirm the HUB/DEV/EPP register file is present and RW,
 * and that no phantom EHCI exists. Full device semantics (enumeration/EP DMA) are
 * F8-KVM refinements. Apache-2.0. */
#include "harness.h"
#include "ast2050.h"
const char fwtest_name[] = "usb";

/* Register map (DATASHEET-USB.md §1) — base + offset. */
#define HUB00 (USB_UDC_BASE + 0x000)  /* Root Function Control & Status         */
#define HUB08 (USB_UDC_BASE + 0x008)  /* Interrupt Control / enables            */
#define HUB20 (USB_UDC_BASE + 0x020)  /* Device-controller Soft Reset Enable    */
#define HUB3C (USB_UDC_BASE + 0x03C)  /* EP1 hub status-change bitmap (host poll)*/
#define DEV00 (USB_UDC_BASE + 0x100)  /* Device #1 Function Enable Control      */
#define EPP00 (USB_UDC_BASE + 0x200)  /* Programmable Endpoint #0 config        */
#define EHCI  (USB_UDC_BASE + 0x1000) /* AST2400+ EHCI cap (absent on the G3)   */

void fwtest_run(void)
{
    /* The device/vhub register file is present at 0x1E6A0000. */
    fwt_reg("hub00.root", HUB00);

    /* §15.4 init: release PHY reset (HUB00[11]) + enable upstream port (HUB00[0]).
     * HUB00 is RW (root function control). */
    writel(HUB00, (1u << 11) | (1u << 0));
    fwt_check("hub00.rw", readl(HUB00) & ((1u << 11) | 1u), (1u << 11) | 1u);

    /* HUB08 interrupt enables (bus-reset/EP int enables) — RW. */
    writel(HUB08, (1u << 6) | (1u << 0));   /* Bus-Reset int + EP0 SETUP-ACK int */
    fwt_check("hub08.irq_en.rw", readl(HUB08) & 0x41u, 0x41u);

    /* HUB20 device-controller soft-reset holds — RW (release the root hub +
     * device-1 controllers out of reset). */
    writel(HUB20, 0x0u);
    fwt_check("hub20.reset.rw", readl(HUB20), 0x0u);

    /* DEV00 (device #1): set downstream device address + enable device port. */
    writel(DEV00, (0x03u << 8) | (1u << 0));  /* addr=3, enable device port */
    fwt_check("dev00.enable.rw", readl(DEV00) & 0x0301u, 0x0301u);

    /* EPP00 (endpoint pool #0): Interrupt-In (HID kbd/mouse), EP#1, device port 1,
     * enable — the vKVM HID endpoint (datasheet §15.3.4). */
    writel(EPP00, (0x1u << 8) | (0x4u << 4) | (0x1u << 1) | 1u);
    fwt_check("epp00.hid_cfg.rw", readl(EPP00) & 0x01FEu, (0x1u << 8) | (0x4u << 4) | (0x1u << 1));

    /* HUB3C status-change bitmap: signal "device #1 plugged" (bit1) so the host
     * would re-enumerate the virtual device (datasheet §15.3.2). RW here. */
    writel(HUB3C, (1u << 1));
    fwt_check("hub3c.plug.rw", readl(HUB3C) & 0x2u, 0x2u);

    /* Faithfulness: NO EHCI host on the AST2050 — 0x1E6A1000 is unmapped, reads 0
     * (the AST2400 EHCI cap word 0x01000020 must NOT appear). */
    fwt_reg("ehci1000", EHCI);
}
