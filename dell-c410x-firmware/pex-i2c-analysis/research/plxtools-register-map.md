# Cross-Reference: Firmware Registers vs plxtools Definitions

Cross-reference of all PEX8696/PEX8647 registers discovered during Dell C410X BMC
firmware reverse engineering with public documentation from plxtools, the Broadcom
PLX SDK, the PCIe Base Specification, and Linux kernel headers.

---

## 1. Sources Consulted

| Source | Location | Description |
|--------|----------|-------------|
| plxtools pex8696.yaml | [github.com/mithro/plxtools](https://github.com/mithro/plxtools/blob/main/src/plxtools/devices/definitions/pex8696.yaml) | PEX8696 device definition with EEPROM and basic registers |
| plxtools i2c.py | [github.com/mithro/plxtools](https://github.com/mithro/plxtools/blob/main/src/plxtools/backends/i2c.py) | I2C backend with PLX I2C protocol implementation |
| plxtools switchdb | [github.com/mithro/plxtools](https://github.com/mithro/plxtools/blob/main/src/plxtools/switchdb/_plx_devices.py) | PEX8696 device metadata (96-lane, 24-port, Gen2, has NT) |
| PLX SDK PciRegs.h | [github.com/xiallc/broadcom_pci_pcie_sdk](https://github.com/xiallc/broadcom_pci_pcie_sdk/blob/master/Include/PciRegs.h) | Standard PCI/PCIe register definitions |
| PLX SDK RegDefs.c | [github.com/xiallc/broadcom_pci_pcie_sdk](https://github.com/xiallc/broadcom_pci_pcie_sdk/blob/master/Samples/PlxCm/RegDefs.c) | PLX chip register name/offset tables |
| Linux kernel pci_regs.h | [github.com/torvalds/linux](https://github.com/torvalds/linux/blob/master/include/uapi/linux/pci_regs.h) | Standard PCIe register bit field definitions |
| Linux kernel pciehp_hpc.c | [github.com/torvalds/linux](https://github.com/torvalds/linux/blob/master/drivers/pci/hotplug/pciehp_hpc.c) | PCIe hot-plug controller driver (uses slot registers) |
| PEX8xxx I2C kernel patches | [patchwork.kernel.org](https://patchwork.kernel.org/patch/5000551/) | Linux I2C driver for PLX PEX8xxx switches (2014) |
| Broadcom PEX8696 product page | [broadcom.com](https://www.broadcom.com/products/pcie-switches-retimers/pcie-switches/pex8696) | Official product brief |

---

## 2. Register Classification Summary

### 2.1 Classification Key

- **PCIe Standard** -- Register defined in the PCI Express Base Specification,
  accessible at a fixed offset from a standard PCIe capability structure.
- **PLX Proprietary** -- Register specific to PLX/Broadcom PEX switches, not
  defined in any public PCIe specification. Located in the PLX vendor-specific
  extended configuration space (offsets >= 0x200, or within PLX VS capability).
- **PLX-Modified Standard** -- A standard PCIe register whose bit fields are
  extended or reinterpreted by PLX.

### 2.2 All Discovered Registers

| Byte Addr | DWORD | Classification | Register Name | Chip |
|-----------|-------|---------------|---------------|------|
| 0x07C | 0x1F | PCIe Standard | Slot Capabilities Register | PEX8696 |
| 0x080 | 0x20 | PCIe Standard | Slot Control / Slot Status Register | PEX8696 |
| 0x204 | 0x81 | PLX Proprietary | Port Control Mask (VS1 Capability) | PEX8696 |
| 0x228 | 0x8A | PLX Proprietary | Hot-Plug LED / MRL Control | PEX8696 |
| 0x234 | 0x8D | PLX Proprietary | Hot-Plug Power Controller Control | PEX8696/PEX8647 |
| 0x380 | 0xE0 | PLX Proprietary | Port/Lane Configuration (lower) | PEX8696 |
| 0x384 | 0xE1 | PLX Proprietary | Port/Lane Configuration (upper) | PEX8696 |
| 0x3AC | 0xEB | PLX Proprietary | NT Bridge Setup | PEX8696 |
| 0xB90 | 0x2E4 | PLX Proprietary | SerDes Equalization Coefficient 1 | PEX8696 |
| 0xB9C | 0x2E7 | PLX Proprietary | SerDes Equalization Coefficient 2 | PEX8696 |
| 0xBA4 | 0x2E9 | PLX Proprietary | SerDes De-emphasis 1 | PEX8696 |
| 0xBA8 | 0x2EA | PLX Proprietary | SerDes De-emphasis 2 | PEX8696 |
| 0x1DC | 0x77 | PLX Proprietary | Port Merging / Aggregation Control | PEX8647 |

**Result:** 2 registers are PCIe standard; 11 registers are PLX proprietary.

---

## 3. PCIe Standard Registers

### 3.1 Register 0x07C -- Slot Capabilities (PCIe Spec)

**PLX SDK confirmation:** The PLX SDK `RegDefs.c` file (`Pci8500[]` array) defines
offset 0x07C as:

```c
{0x07C, "PCIe Cap: Slot Capabilities"},
```

This confirms register 0x07C is the standard PCIe Slot Capabilities register.

**PCIe Capability base:** In PLX PEX8500/8600 series switches, the PCIe Express
Capability structure starts at offset **0x068** in the per-port configuration space.
The Slot Capabilities register is at offset +0x14 from the capability base:
`0x068 + 0x014 = 0x07C`.

**Linux kernel definition:**

```c
#define PCI_EXP_SLTCAP          0x14    /* Slot Capabilities */
#define PCI_EXP_SLTCAP_ABP     0x00000001 /* Attention Button Present */
#define PCI_EXP_SLTCAP_PCP     0x00000002 /* Power Controller Present */
#define PCI_EXP_SLTCAP_MRLSP   0x00000004 /* MRL Sensor Present */
#define PCI_EXP_SLTCAP_AIP     0x00000008 /* Attention Indicator Present */
#define PCI_EXP_SLTCAP_PIP     0x00000010 /* Power Indicator Present */
#define PCI_EXP_SLTCAP_HPS     0x00000020 /* Hot-Plug Surprise */
#define PCI_EXP_SLTCAP_HPC     0x00000040 /* Hot-Plug Capable */
#define PCI_EXP_SLTCAP_SPLV    0x00007f80 /* Slot Power Limit Value */
#define PCI_EXP_SLTCAP_SPLS    0x00018000 /* Slot Power Limit Scale */
#define PCI_EXP_SLTCAP_EIP     0x00020000 /* Electromechanical Interlock */
#define PCI_EXP_SLTCAP_NCCS    0x00040000 /* No Command Completed Support */
#define PCI_EXP_SLTCAP_PSN     0xfff80000 /* Physical Slot Number */
```

**Firmware usage:** The firmware reads 0x07C and clears bit 18 (byte 2, bit 2).
However, bit 18 in Slot Capabilities would be `PCI_EXP_SLTCAP_EIP` (Electromechanical
Interlock Present) -- a read-only hardware capability bit. This is inconsistent with
a read-modify-write pattern. PLX likely repurposes or overlays this bit position with
a proprietary "write protect" function when accessed via I2C, or the register at 0x07C
in the I2C address space may not directly map to the same offset in PCI configuration
space. The PLX SDK's placement at this offset confirms the standard naming, but the
firmware's use of bit 18 as a writable "write protect" control strongly suggests a
**PLX-modified standard** interpretation.

**Firmware function:** `pex8696_un_protect_reg` (at 0x0002FC74)
- Reads register 0x07C via I2C
- Clears bit 18 (byte offset 2, bit 2) to remove write protection
- Writes the modified value back

**plxtools coverage:** Not yet documented in pex8696.yaml. The YAML file currently
only defines `eeprom_ctrl` (0x260), `eeprom_data` (0x264), `vendor_device_id` (0x00),
and `port_control` (0x208).

### 3.2 Register 0x080 -- Slot Control / Slot Status (PCIe Spec)

**PLX SDK confirmation:** The PLX SDK `RegDefs.c` file defines:

```c
{0x080, "PCIe Cap: Slot Status | Slot Control"},
```

This confirms 0x080 is the combined Slot Control (lower 16 bits) and Slot Status
(upper 16 bits) register. In the PCIe specification, the 32-bit DWORD at this
offset contains two 16-bit registers packed together.

**PCIe Capability base calculation:** `0x068 + 0x018 = 0x080` (Slot Control is
at offset +0x18 from the PCIe capability base).

**Linux kernel Slot Control bit definitions (lower 16 bits):**

```c
#define PCI_EXP_SLTCTL          0x18    /* Slot Control */
#define PCI_EXP_SLTCTL_ABPE    0x0001  /* Attention Button Pressed Enable */
#define PCI_EXP_SLTCTL_PFDE    0x0002  /* Power Fault Detected Enable */
#define PCI_EXP_SLTCTL_MRLSCE  0x0004  /* MRL Sensor Changed Enable */
#define PCI_EXP_SLTCTL_PDCE    0x0008  /* Presence Detect Changed Enable */
#define PCI_EXP_SLTCTL_CCIE    0x0010  /* Command Completed Interrupt Enable */
#define PCI_EXP_SLTCTL_HPIE    0x0020  /* Hot-Plug Interrupt Enable */
#define PCI_EXP_SLTCTL_AIC     0x00C0  /* Attention Indicator Control [7:6] */
#define PCI_EXP_SLTCTL_PIC     0x0300  /* Power Indicator Control [9:8] */
#define PCI_EXP_SLTCTL_PCC     0x0400  /* Power Controller Control [10] */
#define PCI_EXP_SLTCTL_EIC     0x0800  /* Electromechanical Interlock Ctrl */
#define PCI_EXP_SLTCTL_DLLSCE  0x1000  /* Data Link Layer State Changed En */
```

**Slot Control indicator encoding:**

| Value | Attention Indicator [7:6] | Power Indicator [9:8] |
|-------|---------------------------|----------------------|
| 00b   | Reserved                  | Reserved             |
| 01b   | On                        | On                   |
| 10b   | Blink                     | Blink                |
| 11b   | Off                       | Off                  |

**Linux kernel Slot Status bit definitions (upper 16 bits, at offset +0x1A):**

```c
#define PCI_EXP_SLTSTA          0x1A    /* Slot Status */
#define PCI_EXP_SLTSTA_ABP     0x0001  /* Attention Button Pressed */
#define PCI_EXP_SLTSTA_PFD     0x0002  /* Power Fault Detected */
#define PCI_EXP_SLTSTA_MRLSC   0x0004  /* MRL Sensor Changed */
#define PCI_EXP_SLTSTA_PDC     0x0008  /* Presence Detect Changed */
#define PCI_EXP_SLTSTA_CC      0x0010  /* Command Completed */
#define PCI_EXP_SLTSTA_MRLSS   0x0020  /* MRL Sensor State */
#define PCI_EXP_SLTSTA_PDS     0x0040  /* Presence Detect State */
#define PCI_EXP_SLTSTA_EIS     0x0080  /* Electromechanical Interlock */
#define PCI_EXP_SLTSTA_DLLSC   0x0100  /* Data Link Layer State Changed */
```

**Firmware usage:** The firmware accesses register 0x080 as a 32-bit DWORD via I2C.
It modifies byte offset 1 (bits [15:8] of the register value), which corresponds
to the upper byte of the Slot Control register:

```
Byte 1, bits [1:0] = Slot Control bits [9:8] = Power Indicator Control
Byte 1, bit 2      = Slot Control bit [10]   = Attention Indicator / PCC
```

The firmware sets Power Indicator = ON (01b) and clears the Attention Indicator
bit during power-on. During power-off, it sets Power Indicator = OFF (11b).

**Firmware functions:**
- `pex8696_slot_power_on_reg` (0x0002F7C4) -- Phase 1: set PIC=On, clear AIC
- `pex8696_slot_power_ctrl` (0x000332AC) -- runtime power on/off
- `all_slot_power_off_reg` (0x000336B4) -- set PIC=Off for all slots

**plxtools coverage:** Not yet documented in pex8696.yaml.

---

## 4. PLX Proprietary Registers

### 4.1 Register 0x204 -- Port Control Mask (VS1 Capability Area)

**Classification:** PLX Proprietary

**Address space:** Offset 0x204 is within the PLX Vendor-Specific 1 (VS1) extended
capability region. PLX PEX8600-series switches place vendor-specific registers
starting at offset 0x200 in each port's configuration space.

**plxtools reference:** The plxtools pex8696.yaml defines a `port_control` register
at offset 0x208 with a port_stride of 0x1000:

```yaml
port_control:
    offset: 0x208
    size: 4
    access: rw
    description: "Port Control Register"
    per_port: true
    port_stride: 0x1000
    fields:
      port_enable:
        bit: 0
        description: "Port enable"
      port_type:
        bits: [1, 2]
        description: "Port type (0=DS, 1=US, 2=NT)"
```

Register 0x204 is at the adjacent offset (one DWORD before 0x208) and is likely a
**port configuration/mask** register closely related to port_control. In the firmware,
it is used as a control mask during port reconfiguration operations.

**Firmware usage:** Accessed during multi-host mode switching to mask or filter
port operations. See `pex-multihost.md` analysis for details.

**plxtools coverage:** Partially covered (0x208 is defined; 0x204 is not).

### 4.2 Register 0x228 -- Hot-Plug LED / MRL Control

**Classification:** PLX Proprietary

**Address space:** Deep in the VS1 capability region (offset 0x228 = DWORD 0x8A).

**Firmware usage:** In the slot power-on sequence, the firmware performs a
read-modify-write on register 0x228:

```
Read register 0x228 (DWORD index 0x8A)
Set bit 21 (byte offset 2, bit 5)
Write back
```

Bit 21 appears to control the hot-plug LED enable or MRL (Manual Retention Latch)
sensor state. Setting this bit during power-on enables the hot-plug LED indication
for the slot.

**Firmware functions:**
- `pex8696_slot_power_on_reg` (0x0002F7C4) -- Phase 3: set bit 21
- `pex8696_slot_power_ctrl` (0x000332AC) -- runtime slot control

**plxtools coverage:** Not documented.

**Known documentation:** No public PLX documentation describes this register.
The register address (0x228) falls within the PLX vendor-specific hot-plug extension
area. PLX PEX8600/8700 series switches implement hardware-assisted hot-plug with
proprietary register extensions beyond the standard PCIe hot-plug registers.

### 4.3 Register 0x234 -- Hot-Plug Power Controller Control

**Classification:** PLX Proprietary

**Address space:** VS1 capability region (offset 0x234 = DWORD 0x8D).

**Firmware usage (PEX8696):** The power-on sequence performs a pulsed control:

```
Read register 0x234 (DWORD index 0x8D)
Set bit 0 of byte 0 (= bit 0 of 32-bit value)
Write back                                     -- assert power control
Sleep 100ms
Clear bit 0 of byte 0
Write back                                     -- de-assert power control
```

Bit 0 functions as a **Power Controller Control** trigger. The pulse pattern
(assert, wait, de-assert) is characteristic of hardware power sequencing triggers
in PLX switches. This bit initiates the hardware-managed power-on sequence for
the downstream port, controlling the physical power supply to the PCIe slot.

**Firmware usage (PEX8647):** In the PEX8647, register 0x234 is also accessed
during multi-host mode configuration. The function `pex8647_cfg_multi_host_8`
writes this register as part of host port select / hot-plug control for 8:1 mode.

**Linux kernel I2C patch reference:** The kernel patch for PLX PEX8xxx I2C driver
(from 2014, patchwork.kernel.org) included example register accesses at offsets
0x230, 0x234, and 0x238, confirming this address range is commonly used for PLX
configuration. No bit-level definitions were provided.

**plxtools coverage:** Not documented.

### 4.4 Registers 0x380/0x384 -- Port/Lane Configuration

**Classification:** PLX Proprietary

**Address space:** Deep in PLX proprietary configuration space (DWORD 0xE0/0xE1).

**Firmware usage:** These registers are written (not read-modify-written) during
multi-host mode switching to reconfigure the lane-to-port assignment:

**4:1 / 8:1 mode values:**

| Register | Byte Addr | Value written |
|----------|-----------|---------------|
| DWORD 0xE1 | 0x384 | 0x00100000 |
| DWORD 0xE0 | 0x380 | 0x11011100 |

**2:1 mode values:**

| Register | Byte Addr | Value written |
|----------|-----------|---------------|
| DWORD 0xE1 | 0x384 | 0x00101100 |
| DWORD 0xE0 | 0x380 | 0x11010000 |

The register values encode lane-to-port assignments. Each nibble likely represents
the configuration of a 4-lane port group. The patterns suggest:
- 0x0 = port disabled or default routing
- 0x1 = single-width downstream port
- 0x11 = aggregated port pair

These registers are written to station 0, port 0 (the upstream/management port),
confirming they are global port configuration registers rather than per-port.

**Firmware functions:**
- `pex8696_cfg_multi_host_4` (0x00036CD4) -- writes 4:1/8:1 values
- `pex8696_cfg_multi_host_2` (0x00036BEC) -- writes 2:1 values

**plxtools coverage:** Not documented.

### 4.5 Register 0x3AC -- NT Bridge Setup

**Classification:** PLX Proprietary

**Address space:** VS1 capability region (DWORD 0xEB).

**Firmware usage:** Accessed during multi-host configuration for NT (Non-Transparent)
bridge setup. The PEX8696 supports NT bridging (`has_nt: True` in plxtools switchdb)
which is used in multi-root I/O virtualisation configurations.

**Broadcom documentation:** The document "Non-Transparent Bridging Using PEX 8696/80/64"
(docs.broadcom.com) describes NT bridge configuration for the PEX8600 series, though
the specific register-level details require an NDA to access.

**plxtools coverage:** Not documented. The plxtools switchdb confirms PEX8696 has
NT capability (`has_nt=True`).

### 4.6 Registers 0xB90 / 0xB9C / 0xBA4 / 0xBA8 -- SerDes Equalization

**Classification:** PLX Proprietary

**Address space:** Very deep in proprietary space (DWORD 0x2E4 to 0x2EA). These
registers are in the SerDes (Serializer/Deserializer) PHY configuration area.

**Firmware usage:** During PEX8696 initialisation (function `pex8696_cfg` at
0x00037F28), the firmware writes SerDes equalization and de-emphasis values:

| Register | DWORD | Purpose |
|----------|-------|---------|
| 0xB90 | 0x2E4 | SerDes equalization coefficient 1 |
| 0xB9C | 0x2E7 | SerDes equalization coefficient 2 |
| 0xBA4 | 0x2E9 | SerDes de-emphasis 1 |
| 0xBA8 | 0x2EA | SerDes de-emphasis 2 |

PCIe Gen2 equalization involves transmitter de-emphasis and receiver equalization
to maintain signal integrity at 5 GT/s. PLX switches provide per-port SerDes tuning
registers to optimize signal quality for different board trace lengths and
topologies.

The Dell C410X firmware writes specific SerDes values tuned for its backplane
PCB trace characteristics. This is essential because the 16 GPU slots connect
through varying trace lengths on the backplane.

**plxtools coverage:** Not documented.

### 4.7 Register 0x1DC (PEX8647) -- Port Merging / Aggregation

**Classification:** PLX Proprietary

**Address space:** VS1 capability region (DWORD 0x77). PEX8647-specific.

**Firmware usage:** Used during 8:1 multi-host mode configuration in
`pex8647_cfg_multi_host_8`. The register controls port merging to create
wider aggregated links from multiple physical ports. In 8:1 mode, individual
x8 host ports are merged to form fewer, wider links that each serve 8 GPUs.

The PEX8647 is a 48-lane, 3-port PCIe Gen2 switch used for the upstream/host
connections. The switchdb records: `total_lanes=48, max_ports=3`.

**plxtools coverage:** No PEX8647 definition file exists in plxtools. Only
PEX8696, PEX8733, and PEX880xx have YAML definitions.

---

## 5. plxtools Cross-Reference Summary

### 5.1 Registers Matched by plxtools

| Register | plxtools Name | plxtools Offset | Match? |
|----------|--------------|-----------------|--------|
| 0x208 (port_control) | port_control | 0x208 | Adjacent to firmware's 0x204 |
| 0x260 (EEPROM ctrl) | eeprom_ctrl | 0x260 | Not used by hot-plug firmware |
| 0x264 (EEPROM data) | eeprom_data | 0x264 | Not used by hot-plug firmware |
| 0x000 (Vendor/Device ID) | vendor_device_id | 0x00 | Used by plxtools i2c.py for detection |

### 5.2 Firmware Registers NOT in plxtools

The following registers discovered in the firmware are **not yet documented** in
the plxtools pex8696.yaml definition:

| Byte Addr | DWORD | Purpose | Suggested plxtools Name |
|-----------|-------|---------|------------------------|
| 0x07C | 0x1F | Slot Capabilities / Write Protect | `slot_capabilities` |
| 0x080 | 0x20 | Slot Control / Status | `slot_control_status` |
| 0x204 | 0x81 | Port Control Mask | `port_control_mask` |
| 0x228 | 0x8A | Hot-Plug LED / MRL Control | `hp_led_mrl_ctrl` |
| 0x234 | 0x8D | Hot-Plug Power Controller | `hp_power_ctrl` |
| 0x380 | 0xE0 | Lane Config (lower) | `lane_config_lo` |
| 0x384 | 0xE1 | Lane Config (upper) | `lane_config_hi` |
| 0x3AC | 0xEB | NT Bridge Setup | `nt_bridge_setup` |
| 0xB90 | 0x2E4 | SerDes EQ Coeff 1 | `serdes_eq_coeff_1` |
| 0xB9C | 0x2E7 | SerDes EQ Coeff 2 | `serdes_eq_coeff_2` |
| 0xBA4 | 0x2E9 | SerDes De-emphasis 1 | `serdes_deemph_1` |
| 0xBA8 | 0x2EA | SerDes De-emphasis 2 | `serdes_deemph_2` |

### 5.3 plxtools I2C Protocol Confirmation

The plxtools `i2c.py` backend confirms the I2C access protocol used by the firmware:

```python
# Write 16-bit register address (big-endian)
addr_high = (offset >> 8) & 0xFF
addr_low = offset & 0xFF

# Write address, then read 4 bytes
bus.write_i2c_block_data(self.address, addr_high, [addr_low])
data = bus.read_i2c_block_data(self.address, addr_high, 4)

# Convert from little-endian bytes to int
result = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
```

The firmware uses a slightly different protocol -- the PLX I2C command protocol
with a 4-byte command header (command byte, station/port byte, byte enables,
register index) rather than the simpler 2-byte address protocol in plxtools.
Both approaches ultimately access the same 32-bit registers. The PLX command
protocol provides additional features:
- Station/port addressing (to select which port's registers to access)
- Byte enable masking (to selectively modify specific bytes)
- Explicit read (0x04) and write (0x03) commands

The plxtools protocol uses direct 16-bit register addressing without the PLX
command layer, which works for global registers but may not support per-port
register access in the same way.

---

## 6. PLX SDK Cross-Reference

### 6.1 Register Names from PLX SDK RegDefs.c

The PLX SDK `RegDefs.c` file (from the `Pci8500[]` register set, which covers
PEX8500/8600/8696 series switches) provides official names for registers:

```c
REGISTER_SET Pci8500[] =
{
    // ... standard PCI Type 1 header ...
    {0x068, "PCI Express Capability | Next Item Pointer | Capability ID"},
    {0x06C, "PCIe Cap: Device Capabilities"},
    {0x070, "PCIe Cap: Device Status | Device Control"},
    {0x074, "PCIe Cap: Link Capabilities"},
    {0x078, "PCIe Cap: Link Status | Link Control"},
    {0x07C, "PCIe Cap: Slot Capabilities"},
    {0x080, "PCIe Cap: Slot Status | Slot Control"},
    // ...
};
```

This confirms:
- **PCIe Capability base = 0x068** for PEX8500/8600/8696
- **0x07C = Slot Capabilities** (0x068 + 0x14)
- **0x080 = Slot Status | Slot Control** (0x068 + 0x18)

### 6.2 PLX 8000-Series IRQ Register Offsets (from SDK PlxChipFn.c)

The PLX SDK driver source reveals family-specific register bases:

```c
switch (pdx->Key.PlxChip & 0xFF00) {
    case 0x8500:
        OffsetIrqBase = pdx->Offset_RegBase + 0x90;
        break;
    case 0x8600:  // PEX8696 is in this family
    case 0x8700:
    case 0x9700:
        OffsetIrqBase = pdx->Offset_RegBase + 0xC4C;
        break;
}
```

For PEX8696 (family 0x8600), the NT IRQ registers are at base + 0xC4C,
and link error interrupt registers are at base + 0xFE0/0xFE4.

---

## 7. PEX8696 Configuration Space Layout (Reconstructed)

Based on all sources, the PEX8696 per-port configuration space can be laid out as:

```
Offset    Description                          Source
------    -----------------------------------  --------
0x000     PCI Type 1 Header (standard)         PCIe Spec
  0x000     Device ID | Vendor ID              PLX SDK
  0x004     Status | Command                   PLX SDK
  ...       (standard Type 1 header)
  0x034     Extended Capability Pointer         PLX SDK
  0x03C     Bridge Control | INT Pin | INT Line PLX SDK

0x040     Power Management Capability          PLX SDK
0x048     MSI Capability                        PLX SDK

0x068     PCIe Express Capability               PLX SDK
  0x068     PCIe Cap ID | Next Cap Ptr          PLX SDK
  0x06C     Device Capabilities                 PLX SDK
  0x070     Device Status | Device Control      PLX SDK
  0x074     Link Capabilities                   PLX SDK
  0x078     Link Status | Link Control          PLX SDK
  0x07C     Slot Capabilities                   PLX SDK + Firmware
  0x080     Slot Status | Slot Control          PLX SDK + Firmware

0x100     PCIe Extended Configuration Space     PCIe Spec
  0x100     Serial Number Capability            PLX SDK
  0x138     Power Budgeting Capability          PLX SDK
  0x148     Virtual Channel Capability          PLX SDK
  0xFB4     Advanced Error Reporting            PLX SDK

0x200     PLX Vendor-Specific (VS1) Registers   Firmware RE
  0x204     Port Control Mask                   Firmware RE
  0x208     Port Control Register               plxtools
  0x228     Hot-Plug LED / MRL Control          Firmware RE
  0x234     Hot-Plug Power Controller Control   Firmware RE

0x380     PLX Port/Lane Configuration           Firmware RE
  0x380     Lane Config (lower)                 Firmware RE
  0x384     Lane Config (upper)                 Firmware RE
  0x3AC     NT Bridge Setup                     Firmware RE

0xB90     PLX SerDes PHY Configuration          Firmware RE
  0xB90     SerDes EQ Coefficient 1             Firmware RE
  0xB9C     SerDes EQ Coefficient 2             Firmware RE
  0xBA4     SerDes De-emphasis 1                Firmware RE
  0xBA8     SerDes De-emphasis 2                Firmware RE

0xC4C     PLX NT IRQ Registers                  PLX SDK
0xFE0     PLX Link Error IRQ Registers          PLX SDK
```

---

## 8. Recommendations for plxtools

Based on this cross-reference, the following register definitions should be added
to the plxtools `pex8696.yaml` file:

1. **Slot Capabilities (0x07C)** -- Standard PCIe register, important for
   querying hot-plug capabilities before attempting slot power operations.

2. **Slot Control/Status (0x080)** -- Standard PCIe register, essential for
   power indicator control and slot power management.

3. **HP Power Controller Control (0x234)** -- PLX proprietary, the primary
   mechanism for triggering hardware power-on/power-off of downstream slots.

4. **Lane Configuration (0x380/0x384)** -- PLX proprietary, required for
   multi-host mode switching and port reconfiguration.

5. **SerDes registers (0xB90-0xBA8)** -- PLX proprietary, needed for signal
   integrity tuning on different PCB layouts.

The I2C backend should also be extended to support the PLX 4-byte command protocol
(with station/port addressing and byte enable masks) for per-port register access,
as the current 2-byte address protocol only works for global registers.
