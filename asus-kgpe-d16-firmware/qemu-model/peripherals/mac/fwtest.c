/* MAC (ftgmac100) firmware test — AST2050 MAC1 @ 0x1E660000.
 *
 * Faraday FTGMAC100, RMII (SCU70[8:6]=100) + external RTL8201CP 10/100 PHY.
 * Datasheet detail in DATASHEET-MAC.md. This is a register-level test (the MAC is
 * a DMA engine; full TX/RX needs descriptor rings + a net backend, exercised by
 * the boot tests). It checks: MACCR is RW and decodes to the culvert capture; the
 * descriptor-ring base registers store the FULL [31:4] address (a flagged
 * faithfulness point — datasheet prints [27:4] but real DRAM@0x40000000 needs the
 * high bits); and it observes the MDIO/PHY id (which reveals the modelled PHY).
 *
 * NOTE: run standalone (not during a boot), so poking MAC regs is harmless.
 * Apache-2.0.
 */
#include "harness.h"
#include "ast2050.h"

#define MAC_ISR    0x00
#define MAC_MADR   0x08
#define NPTXR_BADR 0x20
#define RXR_BADR   0x24
#define MAC_MACCR  0x50
#define MAC_PHYCR  0x60
#define MAC_PHYDAT 0x64

#define MACCR_CAP  0x0002D51Fu   /* culvert real-HW Linux capture */

const char fwtest_name[] = "mac";

/* MDIO read of PHY register `reg` at address `ad` via PHYCR/PHYDATA. */
static u32 mdio_read(u32 ad, u32 reg)
{
    /* PHYCR: MDC_CYCTHR[5:0]=0x34, PHYAD[20:16], REGAD[25:21], MIIRD bit26. */
    writel(MAC1_BASE + MAC_PHYCR,
           0x34u | (ad << 16) | (reg << 21) | (1u << 26));
    u32 i;
    for (i = 0; i < 100000u && (readl(MAC1_BASE + MAC_PHYCR) & (1u << 26)); i++) {
    }
    return (readl(MAC1_BASE + MAC_PHYDAT) >> 16) & 0xffff;
}

void fwtest_run(void)
{
    fwt_reg("maccr.reset", MAC1_BASE + MAC_MACCR);
    fwt_reg("isr",         MAC1_BASE + MAC_ISR);

    /* --- MACCR is RW and holds the real captured value --- */
    writel(MAC1_BASE + MAC_MACCR, MACCR_CAP);
    fwt_check("maccr.rw", readl(MAC1_BASE + MAC_MACCR), MACCR_CAP);
    /* decode a couple of bits for the record */
    fwt_kv("maccr.speed100", (MACCR_CAP >> 19) & 1u);   /* 0 in the capture */
    fwt_kv("maccr.fulldup",  (MACCR_CAP >> 8) & 1u);

    /* --- descriptor-ring base regs must store the FULL [31:4] address --- */
    writel(MAC1_BASE + RXR_BADR,   0x41B10000u);
    writel(MAC1_BASE + NPTXR_BADR, 0x41B20000u);
    fwt_check("rxr_badr.full", readl(MAC1_BASE + RXR_BADR),   0x41B10000u);
    fwt_check("nptxr_badr.full", readl(MAC1_BASE + NPTXR_BADR), 0x41B20000u);

    /* --- MDIO/PHY: observe the modelled PHY id at addresses 0 and 1 --- */
    fwt_kv("phy0.id2", mdio_read(0, 2));
    fwt_kv("phy0.id3", mdio_read(0, 3));
    fwt_kv("phy1.id2", mdio_read(1, 2));
    fwt_kv("phy0.bmsr", mdio_read(0, 1));   /* BMSR: link/caps */
}
