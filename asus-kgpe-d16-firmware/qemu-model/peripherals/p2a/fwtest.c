/* P2A / PCI-to-AHB bridge — AST2050 (see DATASHEET-P2A.md).
 *
 * The culvert `p2a` backdoor is HOST-side: the host PCI master reaches BMC AHB via
 * PCI-slave BAR1 (P2A00 @ MMIOBASE+0xF000 enable, P2A04 remap base;
 * AHB=(P2A04[31:16]<<16)|offset). Enabled by SCU2C[8]=0 (enable PCI-slave->AHB).
 * From the BMC (ARM/AHB) side this test can only observe the AHB-side pieces: the
 * A2P bridge region (0x1E720000), the SCU2C enable bit, and the PCI identity
 * (SCU30/34/38, vendor 0x1A03 ASPEED). The full backdoor needs a host PCI master
 * (culvert) — validated on silicon (HW-VALIDATION-CHECKLIST). Apache-2.0. */
#include "harness.h"
#include "ast2050.h"
#define A2P_BASE 0x1E720000u
const char fwtest_name[] = "p2a";
void fwtest_run(void)
{
    fwt_reg("a2p.bridge", A2P_BASE);
    u32 misc2c = fwt_reg("scu.misc2c", SCU_BASE + 0x2C);
    fwt_kv("scu2c.pci_slave_ahb_en", ((misc2c >> 8) & 1u) ? 0u : 1u); /* bit8=0 -> en */
    u32 pci0 = fwt_reg("pci.vendev", SCU_BASE + 0x30);
    fwt_reg("pci.class", SCU_BASE + 0x38);
    /* PCI vendor id must be ASPEED 0x1A03 (faithful; SCU30 low half) */
    fwt_check("pci.vendor_aspeed", pci0 & 0xFFFFu, 0x1A03u);
}
