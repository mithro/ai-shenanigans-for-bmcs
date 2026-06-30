# PCIe Hot-Plug Registers and Dell C410X Firmware Mapping

This document maps the standard PCIe hot-plug registers from the PCI Express Base
Specification to the register accesses observed in the Dell C410X BMC firmware, and
documents how PLX extends the standard registers with proprietary hot-plug features.

---

## 1. PCIe Express Capability Structure

### 1.1 Capability Base Offset

In PLX PEX8500/8600/8696 series switches, the PCIe Express Capability structure
is located at offset **0x068** in each port's configuration space. This is confirmed
by the PLX SDK `RegDefs.c` file:

```c
{0x068, "PCI Express Capability | Next Item Pointer | Capability ID"},
```

The PCIe Express Capability structure has a fixed layout defined by the PCIe Base
Specification. All offsets below are relative to the capability base (0x068).

### 1.2 Complete Register Layout

Source: PCI Express Base Specification Rev 3.0, Section 7.8; Linux kernel
`include/uapi/linux/pci_regs.h`.

| Offset from Base | Absolute Offset | Size | Register Name |
|-----------------|-----------------|------|---------------|
| +0x00 | 0x068 | 2 | PCIe Capabilities Register |
| +0x02 | 0x06A | 2 | (upper half of capability DWORD) |
| +0x04 | 0x06C | 4 | Device Capabilities |
| +0x08 | 0x070 | 2 | Device Control |
| +0x0A | 0x072 | 2 | Device Status |
| +0x0C | 0x074 | 4 | Link Capabilities |
| +0x10 | 0x078 | 2 | Link Control |
| +0x12 | 0x07A | 2 | Link Status |
| **+0x14** | **0x07C** | **4** | **Slot Capabilities** |
| **+0x18** | **0x080** | **2** | **Slot Control** |
| **+0x1A** | **0x082** | **2** | **Slot Status** |
| +0x1C | 0x084 | 2 | Root Control |
| +0x1E | 0x086 | 2 | Root Capabilities |
| +0x20 | 0x088 | 4 | Root Status |

**Bold** entries are the hot-plug related registers accessed by the firmware.

Note: When accessed as 32-bit DWORDs via I2C (as the firmware does), register
0x080 contains Slot Control in the lower 16 bits and Slot Status in the upper
16 bits.

---

## 2. Slot Capabilities Register (0x07C)

### 2.1 Standard Definition

**PCIe Spec Reference:** Section 7.8.9
**Absolute Offset:** 0x07C (PLX PEX8696)
**Size:** 32 bits
**Access:** Read-Only (per PCIe spec)

| Bits | Field | Description |
|------|-------|-------------|
| 0 | ABP | Attention Button Present |
| 1 | PCP | Power Controller Present |
| 2 | MRLSP | MRL Sensor Present |
| 3 | AIP | Attention Indicator Present |
| 4 | PIP | Power Indicator Present |
| 5 | HPS | Hot-Plug Surprise |
| 6 | HPC | Hot-Plug Capable |
| 14:7 | SPLV | Slot Power Limit Value |
| 16:15 | SPLS | Slot Power Limit Scale |
| 17 | EIP | Electromechanical Interlock Present |
| 18 | NCCS | No Command Completed Support |
| 31:19 | PSN | Physical Slot Number |

### 2.2 Firmware Usage of 0x07C

The firmware reads and writes register 0x07C in `pex8696_un_protect_reg`, specifically
modifying **bit 18** (byte offset 2, bit 2):

```
Read:   I2C cmd=0x04, station/port=<varies>, enables=0x3C, reg=0x1F
Modify: Clear bit 2 of byte[2] (= bit 18 of 32-bit value)
Write:  I2C cmd=0x03, same addressing, modified value
```

### 2.3 PLX Write-Protect Extension

In the standard PCIe specification, bit 18 of Slot Capabilities is **NCCS**
(No Command Completed Support), a read-only hardware capability bit. However,
the firmware treats this bit as a **writable write-protect control**.

This is a **PLX proprietary extension**: PLX switches overlay the standard
Slot Capabilities register with additional writable bits when accessed via I2C.
Specifically:

| Bit | Standard Meaning | PLX Extension |
|-----|-----------------|---------------|
| 18 | NCCS (read-only) | **Write Protect Enable** (read-write via I2C) |

When bit 18 is **set** (1), the port's vendor-specific registers (0x200+) are
write-protected. Clearing bit 18 removes the protection, allowing the BMC to
modify hot-plug control, lane configuration, and other proprietary registers.

**Sequence requirement:** The firmware always calls `pex8696_un_protect_reg`
(which clears bit 18) **before** any register modifications in the VS1 area.

This dual-purpose approach (standard read-only from PCIe, writable via I2C) is
consistent with PLX's architecture: the I2C interface provides a management
path with elevated privileges compared to the PCIe bus.

---

## 3. Slot Control Register (0x080, lower 16 bits)

### 3.1 Standard Definition

**PCIe Spec Reference:** Section 7.8.10
**Absolute Offset:** 0x080 (lower 16 bits of DWORD)
**Size:** 16 bits
**Access:** Read-Write

| Bits | Mask | Field | Description |
|------|------|-------|-------------|
| 0 | 0x0001 | ABPE | Attention Button Pressed Enable |
| 1 | 0x0002 | PFDE | Power Fault Detected Enable |
| 2 | 0x0004 | MRLSCE | MRL Sensor Changed Enable |
| 3 | 0x0008 | PDCE | Presence Detect Changed Enable |
| 4 | 0x0010 | CCIE | Command Completed Interrupt Enable |
| 5 | 0x0020 | HPIE | Hot-Plug Interrupt Enable |
| 7:6 | 0x00C0 | AIC | Attention Indicator Control |
| 9:8 | 0x0300 | PIC | Power Indicator Control |
| 10 | 0x0400 | PCC | Power Controller Control |
| 11 | 0x0800 | EIC | Electromechanical Interlock Control |
| 12 | 0x1000 | DLLSCE | Data Link Layer State Changed Enable |
| 15:13 | -- | RsvdP | Reserved |

### 3.2 Indicator Control Encoding

The AIC and PIC fields use a 2-bit encoding:

| Value | Meaning |
|-------|---------|
| 00b | Reserved |
| 01b | **On** |
| 10b | Blink |
| 11b | **Off** |

### 3.3 Power Controller Control (PCC)

Bit 10 (PCC) controls the slot power:

| Value | Meaning |
|-------|---------|
| 0 | Power On (slot powered) |
| 1 | Power Off (slot not powered) |

**Important:** In the standard PCIe spec, PCC=0 means power ON and PCC=1 means
power OFF. This is a "power off control" semantics, not a "power on control."

### 3.4 Firmware Usage of Slot Control

The firmware accesses register 0x080 as a full 32-bit DWORD via I2C. It modifies
specific bits in **byte offset 1** (bits [15:8] of the DWORD), which corresponds
to the upper byte of the Slot Control register.

#### Power-On Sequence (pex8696_slot_power_on_reg)

```
Read register 0x080
Modify byte[1]:
  bits [1:0] = 01  (= Slot Control bits [9:8] = PIC = ON)
  bit 2 = 0        (= Slot Control bit [10] = AIC/PCC cleared)
Write back
```

Mapping to standard bit fields:

| Byte[1] Bits | Slot Control Bits | Field | Value Set | Meaning |
|--------------|-------------------|-------|-----------|---------|
| [1:0] | [9:8] | PIC | 01b | Power Indicator = On |
| [2] | [10] | PCC | 0 | Power Controller = On (power slot) |

#### Power-Off Sequence (all_slot_power_off_reg)

```
Read register 0x080
Modify byte[1]:
  bits [1:0] = 11  (= PIC = OFF)
  bit 2 = 1        (= PCC = Power Off)
Write back
```

| Byte[1] Bits | Slot Control Bits | Field | Value Set | Meaning |
|--------------|-------------------|-------|-----------|---------|
| [1:0] | [9:8] | PIC | 11b | Power Indicator = Off |
| [2] | [10] | PCC | 1 | Power Controller = Off (remove power) |

---

## 4. Slot Status Register (0x082, upper 16 bits of DWORD at 0x080)

### 4.1 Standard Definition

**PCIe Spec Reference:** Section 7.8.11
**Absolute Offset:** 0x082 (upper 16 bits of DWORD at 0x080)
**Size:** 16 bits
**Access:** Read-Only and Write-1-to-Clear (RW1C)

| Bits | Mask | Field | Description | Access |
|------|------|-------|-------------|--------|
| 0 | 0x0001 | ABP | Attention Button Pressed | RW1C |
| 1 | 0x0002 | PFD | Power Fault Detected | RW1C |
| 2 | 0x0004 | MRLSC | MRL Sensor Changed | RW1C |
| 3 | 0x0008 | PDC | Presence Detect Changed | RW1C |
| 4 | 0x0010 | CC | Command Completed | RW1C |
| 5 | 0x0020 | MRLSS | MRL Sensor State | RO |
| 6 | 0x0040 | PDS | Presence Detect State | RO |
| 7 | 0x0080 | EIS | Electromechanical Interlock Status | RO |
| 8 | 0x0100 | DLLSC | Data Link Layer State Changed | RW1C |

### 4.2 Firmware Usage of Slot Status

The firmware reads the Slot Status bits (upper 16 bits of register 0x080) during
`pex8696_slot_power_ctrl` to check slot presence and detect events. When writing
back the full DWORD, it preserves the upper 16 bits to avoid accidentally clearing
RW1C status bits, though the read-modify-write pattern used for the Slot Control
bits inherently reads the current Slot Status state.

The Dell C410X BMC also uses IPMI sensor callbacks (via `RawIOIdxTblGetIdx` and
`RawIRQEnable`/`RawIRQDisable`) to handle hot-plug events, indicating that the
PEX8696 drives interrupt signals to the AST2050 BMC in response to Slot Status
change events.

---

## 5. PLX Proprietary Hot-Plug Extensions

Beyond the standard PCIe registers, PLX PEX8600/8696 switches implement proprietary
hot-plug extensions in the vendor-specific configuration space (offsets 0x200+).

### 5.1 Register 0x228 -- Hot-Plug LED / MRL Control

**Offset:** 0x228 (DWORD index 0x8A)
**Size:** 32 bits
**Access:** Read-Write (via I2C)
**Classification:** PLX Proprietary

| Bit | Firmware Use | Probable Function |
|-----|-------------|-------------------|
| 21 | Set during power-on | Hot-Plug LED Enable / MRL Sensor Override |

This register extends the standard hot-plug functionality. While the PCIe Slot
Control register provides basic indicator control (AIC/PIC fields), the PLX
extension at 0x228 appears to provide additional LED control and MRL sensor
configuration specific to PLX's hardware-assisted hot-plug implementation.

**Firmware access pattern:**
```
Read 0x228
Set bit 21 (byte[2] |= 0x20)
Write back
```

### 5.2 Register 0x234 -- Hot-Plug Power Controller Control

**Offset:** 0x234 (DWORD index 0x8D)
**Size:** 32 bits
**Access:** Read-Write (via I2C)
**Classification:** PLX Proprietary

| Bit | Firmware Use | Probable Function |
|-----|-------------|-------------------|
| 0 | Pulsed (set, wait 100ms, clear) | Hardware Power Sequence Trigger |

This is the **primary mechanism** for triggering hardware-managed power sequencing
in the PLX switch. Unlike the standard PCIe PCC bit (which is a simple on/off
toggle), the PLX power controller control at 0x234 uses a **pulse pattern**:

1. Read current register value
2. Assert bit 0 (set to 1)
3. Write back -- triggers hardware power controller
4. Wait ~100ms for power supply stabilisation
5. Clear bit 0 (set to 0)
6. Write back -- release trigger

This pulse-triggered mechanism is fundamentally different from the standard PCIe
PCC bit. The PLX hardware responds to the rising edge of bit 0 by initiating
its internal power sequencing state machine, which manages inrush current control,
voltage ramp timing, and power good monitoring.

**Why both registers are needed:**

The firmware modifies **both** the standard Slot Control (0x080) and the PLX
proprietary power controller (0x234) during a power-on operation:

1. **0x080 (Slot Control):** Sets the power indicator (PIC = ON) and power
   controller (PCC = 0 = powered). This updates the standard PCIe state visible
   to the host operating system.

2. **0x234 (PLX HP Power Ctrl):** Pulses bit 0 to trigger the actual hardware
   power sequencing. This performs the physical power-on operation.

The standard register tells the PCIe subsystem "this slot should be powered"
while the proprietary register actually activates the power hardware.

### 5.3 Register 0x07C Bit 18 -- Write Protection

As documented in Section 2.3, PLX extends the standard Slot Capabilities register
with a writable write-protection bit at position 18 when accessed via I2C. This
must be cleared before modifying any proprietary registers.

**Hot-plug sequence with write protection:**

```
1. Clear write-protect:     Read/modify/write 0x07C, clear bit 18
2. Set indicators:          Read/modify/write 0x080, PIC=On, PCC=0
3. Trigger power sequence:  Read/modify/write 0x234, pulse bit 0
4. Enable HP LED:           Read/modify/write 0x228, set bit 21
```

---

## 6. Complete Hot-Plug Register Access Timeline

The following table shows the complete sequence of register accesses for a single
slot power-on operation, as performed by the Dell C410X firmware:

### 6.1 Power-On Sequence

| Step | Register | DWORD | Op | Bit Changes | Purpose |
|------|----------|-------|----|-------------|---------|
| 1a | 0x07C | 0x1F | Read | -- | Read current slot capabilities / write-protect |
| 1b | 0x07C | 0x1F | Write | Clear bit 18 | Remove write protection |
| 2a | 0x080 | 0x20 | Read | -- | Read current slot control / status |
| 2b | 0x080 | 0x20 | Write | PIC=01b, PCC=0 | Set power indicator ON, enable power |
| 3a | 0x234 | 0x8D | Read | -- | Read HP power controller |
| 3b | 0x234 | 0x8D | Write | Set bit 0 | Assert power trigger |
| 3c | -- | -- | Sleep | 100ms | Wait for power ramp |
| 3d | 0x234 | 0x8D | Write | Clear bit 0 | De-assert power trigger |
| 4a | 0x228 | 0x8A | Read | -- | Read HP LED / MRL control |
| 4b | 0x228 | 0x8A | Write | Set bit 21 | Enable hot-plug LED |

**Total:** 4 I2C reads + 5 I2C writes = 9 I2C transactions per slot

### 6.2 Power-Off Sequence

| Step | Register | DWORD | Op | Bit Changes | Purpose |
|------|----------|-------|----|-------------|---------|
| 1a | 0x080 | 0x20 | Read | -- | Read current slot control / status |
| 1b | 0x080 | 0x20 | Write | PIC=11b, PCC=1 | Set power indicator OFF, disable power |

**Total:** 1 I2C read + 1 I2C write = 2 I2C transactions per slot

The power-off sequence is much simpler: it only modifies the standard Slot Control
register. No write-protection removal is needed (the register at 0x080 is a standard
PCIe register, not a VS1 register), and the PLX hardware power controller is not
pulsed -- setting PCC=1 is sufficient to remove power.

---

## 7. Standard vs PLX Hot-Plug Comparison

### 7.1 Standard PCIe Hot-Plug (OS-driven)

In a typical PCIe system, the operating system manages hot-plug:

```
Host OS:
  1. Write PCC=0 to Slot Control    -> Power on
  2. Poll Slot Status for PDS       -> Wait for presence
  3. Wait for DLLSC                 -> Link trained
  4. Enumerate device               -> Assign resources
```

### 7.2 PLX PEX8696 Hot-Plug (BMC-driven via I2C)

In the Dell C410X, the BMC drives hot-plug instead of the host OS:

```
BMC (via I2C):
  1. Un-protect registers (0x07C)   -> Allow VS1 writes
  2. Set indicators (0x080)         -> Update standard state
  3. Pulse power controller (0x234) -> Trigger PLX hardware power
  4. Enable HP LED (0x228)          -> Activate indicator LED
  5. GPIO pulse                     -> Assert attention signal
```

The key difference is that the BMC operates entirely through the I2C sideband
interface, bypassing the PCIe bus. This allows the BMC to:
- Power on slots before any host is connected
- Control slots across all 4 PEX8696 switches simultaneously
- Implement staggered power-on (4 groups of 4 slots) for inrush control
- Manage slots independently of any host operating system

### 7.3 Why PLX Proprietary Registers Are Needed

The standard PCIe Slot Control register provides the PCC bit for power control,
but the PLX switches require the additional proprietary register (0x234) for
several reasons:

1. **Hardware power sequencing:** The PLX power controller implements a full
   hardware state machine with inrush current limiting, voltage ramp control,
   and power-good monitoring. This cannot be triggered by the standard PCC bit
   alone when accessed via I2C.

2. **I2C management path:** When accessed via I2C (rather than PCIe), the PLX
   switch treats register writes differently. The standard PCC bit update via I2C
   changes the reported state but may not trigger the hardware power controller.
   The pulse on 0x234 bit 0 explicitly triggers the hardware.

3. **Write protection:** PLX adds write protection (bit 18 of 0x07C) to prevent
   accidental modification of downstream port registers. This protection layer
   does not exist in standard PCIe.

---

## 8. PCIe Spec to Firmware Mapping Table

Final summary mapping all hot-plug related firmware accesses to their PCIe spec
or PLX proprietary origins:

| Firmware Access | PCIe Spec Name | PCIe Spec Section | PLX Extension? |
|----------------|---------------|-------------------|----------------|
| Reg 0x07C, bit 18 clear | Slot Capabilities | 7.8.9 | Yes -- write-protect overlay |
| Reg 0x080, bits [9:8] = PIC | Slot Control, Power Indicator | 7.8.10 | No -- standard |
| Reg 0x080, bit [10] = PCC | Slot Control, Power Controller | 7.8.10 | No -- standard |
| Reg 0x080, bits [7:6] = AIC | Slot Control, Attention Indicator | 7.8.10 | No -- standard |
| Reg 0x228, bit 21 | N/A | N/A | Yes -- PLX proprietary |
| Reg 0x234, bit 0 pulse | N/A | N/A | Yes -- PLX proprietary |

---

## 9. References

- PCI Express Base Specification Revision 3.0, November 2010 -- Sections 7.8.9
  through 7.8.11 (Slot Capabilities, Slot Control, Slot Status)
- Linux kernel `include/uapi/linux/pci_regs.h` -- PCI_EXP_SLTCAP, PCI_EXP_SLTCTL,
  PCI_EXP_SLTSTA bit field definitions
- Linux kernel `drivers/pci/hotplug/pciehp_hpc.c` -- Standard PCIe hot-plug
  controller driver implementation
- PLX SDK `Samples/PlxCm/RegDefs.c` -- PEX8500 register names and offsets
- PLX SDK `Include/PciRegs.h` -- PCI/PCIe register definitions
- plxtools `src/plxtools/devices/definitions/pex8696.yaml` -- PEX8696 device
  definition (partial register coverage)
- plxtools `src/plxtools/backends/i2c.py` -- PLX I2C protocol implementation
- IDT Application Note AN-538 "Hot Plug Implementation on IDT PCI Express
  Switches" -- General PCIe switch hot-plug implementation reference
