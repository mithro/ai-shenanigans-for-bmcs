# IO_fl.bin - IO Hardware Mapping Table (Version 3)

## Overview

| Property | Value |
|----------|-------|
| **File** | `etc/default/ipmi/evb/IO_fl.bin` |
| **Size** | 2456 bytes (0x998) |
| **Format** | Binary, little-endian |
| **bmcsetting section** | `[IOTABLE]` |
| **Loading function** | `HWInitIOTableV3()` at 0x00079a48 in fullfw |
| **Global pointers** | `G_sIOTableHeaderVer3Ptr` (0x00110b98), `G_sIOTablePtr` (0x00110b9c) |

IO_fl.bin is the master hardware I/O configuration table for the Avocent MergePoint
IPMI engine. It maps every hardware peripheral the BMC manages (GPIO pins, I2C devices,
communication channels, LEDs, fans, PSUs) to its corresponding IOAPI driver structure,
along with the hardware addressing parameters needed to access each device.

## Binary Layout

```
Offset  Size    Content
------  ------  --------------------------------------------------
0x0000  4       Header (version, flags, entry hint)
0x0004  148     Dispatch table (37 entries x 4 bytes)
0x0098  2304    Entry table (192 entries x 12 bytes)
```

## Header (4 bytes)

```
Offset  Type   Value   Meaning
------  ----   -----   -------
0x00    u8     0x03    Table version (V3 format)
0x01    u8     0x00    Reserved
0x02    u16LE  0x0096  Entry count hint = 150 (informational; actual count is 192)
```

The `HWInitIOTableV3()` function memory-maps the entire file via `MakeMemFileV2()`,
stores the base pointer in `G_sIOTableHeaderVer3Ptr`, then computes the entry table
pointer as `G_sIOTablePtr = base + 0x98`. This +0x98 offset was confirmed from ARM
disassembly at 0x00079b80.

## Dispatch Table (148 bytes at 0x0004)

37 entries of 4 bytes each. Each entry maps a logical **IO Type ID** to a contiguous
range of entries in the entry table:

```c
struct dispatch_entry {
    uint16_t count;        // Number of entries for this type
    uint16_t start_index;  // Index of first entry in the entry table
};
```

### Active Type IDs

| Type ID | Count | Entries | IO Type Name | Primary IOAPI Driver |
|---------|-------|---------|-------------|---------------------|
| 0 | 1 | 0-0 | IPMB Channel | `G_sONCHIP_IPMB_IOAPI` |
| 1 | 7 | 1-7 | IPMB Sub-channels | (null - virtual) |
| 2 | 2 | 8-9 | KCS/VKCS | `G_sONCHIP_KCS_IOAPI` / `G_sONCHIP_VKCS_IOAPI` |
| 5 | 1 | 10-10 | LAN | `G_sONCHIP_vDrvLAN_IOAPI` |
| 6 | 1 | 11-11 | UART/Serial | `G_sONCHIP_UART_IOAPI` |
| 9 | 2 | 12-13 | EEPROM/FRU | `G_sEE24Cxx_EEPROM_IOAPI` / `G_sONCHIP_vDrvFRU_IOAPI` |
| 10 | 1 | 14-14 | SDR Repository | `G_sONCHIP_vDrvSDR_IOAPI` |
| 11 | 1 | 15-15 | SEL Repository | `G_sONCHIP_vDrvSEL_IOAPI` |
| 12 | 1 | 16-16 | Persistent Storage | `G_sONCHIP_vDrvPS_IOAPI` |
| 13 | 8 | 17-24 | Fan/Temp (ADT7462) | `G_sOEMADT7462_I2CFAN_IOAPI` |
| 14 | 118 | 25-142 | Sensor/GPIO | `G_sONCHIP_GPIO_IOAPI` / `G_sPCA9555_I2CGPIO_IOAPI` |
| 18 | 1 | 143-143 | OEM Power Control | `G_sOEMPower_vDrvPOWER_IOAPI` |
| 20 | 4 | 144-147 | I2C Mux (PCA9544) | `G_sOEMPCA9544_I2CSWITCH_IOAPI` |
| 23 | 6 | 148-153 | IRQ/Interrupt | `G_sONCHIP_Generic_ISRAPI` |
| 24 | 34 | 154-187 | LED Control | `G_sONCHIP_LED_IOAPI` |
| 31 | 4 | 188-191 | PMBus PSU | `G_sPMBus_PSU_IOAPI` |

Types 3, 4, 7, 8, 15-17, 19, 21-22, 25-30, 32-35 are unused (count=0).

## Entry Table (2304 bytes at 0x0098)

192 entries, each 12 bytes:

```c
struct io_table_entry_v3 {
    uint16_t  param_a;      // bytes 0-1: bitmask, flags, or I2C address
    uint16_t  param_b;      // bytes 2-3: register offset or bus routing
    uint16_t  param_c;      // bytes 4-5: port group selector or device config
    uint32_t  ioapi_ptr;    // bytes 6-9: pointer to IOAPI driver vtable (LE)
    uint16_t  param_d;      // bytes 10-11: logical IO index or I2C address encoding
};
```

Field meanings are context-dependent based on the IOAPI driver type.

## IOAPI Driver Structures

Each IOAPI struct is a vtable of function pointers in the `.rodata` section of fullfw:

| Address | Symbol | Size | Driver Purpose |
|---------|--------|------|---------------|
| 0x000f76f0 | `G_sONCHIP_GPIO_IOAPI` | 16 | AST2050 on-chip GPIO control |
| 0x000f7804 | `G_sONCHIP_Generic_ISRAPI` | 4 | Interrupt service registration |
| 0x000fc330 | `G_sEE24Cxx_EEPROM_IOAPI` | 20 | 24Cxx I2C EEPROM read/write |
| 0x000fc354 | `G_sPCA9555_I2CGPIO_IOAPI` | 16 | PCA9555 I2C GPIO expander |
| 0x000fc374 | `G_sONCHIP_LED_IOAPI` | 12 | LED control (on/off/blink) |
| 0x000fc3b8 | `G_sPMBus_PSU_IOAPI` | 24 | PMBus power supply management |
| 0x000fcba4 | `G_sOEMPCA9544_I2CSWITCH_IOAPI` | 12 | PCA9544A I2C mux switching |
| 0x000fcbec | `G_sOEMADT7462_I2CFAN_IOAPI` | 16 | ADT7462 fan/temperature controller |
| 0x000fcc3c | `G_sOEMPower_vDrvPOWER_IOAPI` | 28 | System power on/off/cycle |
| 0x000fcf08 | `G_sONCHIP_vDrvLAN_IOAPI` | 60 | Ethernet LAN (MAC/IP/link) |
| 0x000fcf44 | `G_sONCHIP_vDrvPS_IOAPI` | 20 | Persistent storage (NVRAM) |
| 0x000fcfa8 | `G_sONCHIP_vDrvSDR_IOAPI` | 20 | Sensor Data Record repository |
| 0x000fd00c | `G_sONCHIP_vDrvFRU_IOAPI` | 20 | Field Replaceable Unit storage |
| 0x000fd0d4 | `G_sONCHIP_vDrvSEL_IOAPI` | 20 | System Event Log storage |
| 0x000fd1fc | `G_sONCHIP_IPMB_IOAPI` | 16 | IPMB messaging channel |
| 0x000fd20c | `G_sONCHIP_KCS_IOAPI` | 16 | KCS (Keyboard Controller Style) |
| 0x000fd21c | `G_sONCHIP_VKCS_IOAPI` | 16 | Virtual KCS channel |
| 0x000fd258 | `G_sONCHIP_UART_IOAPI` | 84 | UART/serial with routing mux |

## Detailed Entry Decode by Type

### Type 0: IPMB Channel (Entry 0)

| Entry | param_a | param_b | param_c | IOAPI | param_d | Notes |
|-------|---------|---------|---------|-------|---------|-------|
| 0 | 0x0020 | 0x0000 | 0x0000 | IPMB | 0x0000 | BMC IPMB address 0x20 |

### Type 1: IPMB Sub-channels (Entries 1-7)

Virtual IPMB sub-channels (null driver). param_d encodes sub-channel ID:

| Entry | param_d | Notes |
|-------|---------|-------|
| 1 | 0x0001 | IPMB sub-channel 1 |
| 2 | 0x0002 | IPMB sub-channel 2 |
| 3 | 0x0003 | IPMB sub-channel 3 |
| 4 | 0x0404 | IPMB sub-channel 4 (special flags) |
| 5 | 0x0005 | IPMB sub-channel 5 |
| 6 | 0x0006 | IPMB sub-channel 6 |
| 7 | 0x0002 | IPMB sub-channel 7 (alias to 2) |

### Type 2: KCS (Entries 8-9)

| Entry | param_a | param_b | IOAPI | Notes |
|-------|---------|---------|-------|-------|
| 8 | 0x0000 | 0x0CA2 | KCS | Hardware KCS at I/O base 0x0CA2 |
| 9 | 0x0000 | 0x0000 | VKCS | Virtual KCS (software channel) |

### Type 5: LAN (Entry 10)

| Entry | param_a | IOAPI | Notes |
|-------|---------|-------|-------|
| 10 | 0xFF00 | LAN | Ethernet interface, mask 0xFF00 |

### Type 6: UART (Entry 11)

| Entry | param_a | param_b | IOAPI | param_d | Notes |
|-------|---------|---------|-------|---------|-------|
| 11 | 0xFFFF | 0x0001 | UART | 0x0110 | Serial port, config 0x0110 |

### Type 9: EEPROM/FRU Storage (Entries 12-13)

| Entry | param_a | param_b | param_c | IOAPI | param_d | Notes |
|-------|---------|---------|---------|-------|---------|-------|
| 12 | 0xF2A0 | 0x0400 | 0x0500 | EEPROM | 0x0204 | 24Cxx at I2C addr 0xA0, bus 0xF2, 1KB size |
| 13 | 0x0000 | 0x0000 | 0x0000 | vDrvFRU | 0x0240 | Virtual FRU storage in NVRAM |

### Type 10-12: NVRAM Repositories (Entries 14-16)

| Entry | param_a | IOAPI | param_d | Notes |
|-------|---------|-------|---------|-------|
| 14 | 0x1000 | vDrvSDR | 0x0280 | SDR Repository, 4KB |
| 15 | 0x2000 | vDrvSEL | 0x02A0 | SEL Repository, 8KB |
| 16 | 0x3000 | vDrvPS  | 0x0000 | Persistent Storage, 12KB |

### Type 13: ADT7462 Fan/Temperature Controllers (Entries 17-24)

The Dell C410X has **two ADT7462 chips** on I2C bus 0xF1, each behind a PCA9544A mux.
Each ADT7462 has 4 fan/temperature channels (sub-addresses 0xAA-0xAD).

| Entry | Bus (param_b) | Mux Addr | ADT7462 Addr (param_c) | I2C 7-bit | Notes |
|-------|---------------|----------|------------------------|-----------|-------|
| 17 | 0xF1B0 | 0xB0 (0x58) | 0xAA (0x55) | ADT7462 #1, Ch A | Board Temp 1, Fan 1-2 |
| 18 | 0xF1B0 | 0xB0 (0x58) | 0xAB (0x55+) | ADT7462 #1, Ch B | Board Temp 2 |
| 19 | 0xF1B0 | 0xB0 (0x58) | 0xAC (0x56) | ADT7462 #1, Ch C | Board Temp 3 |
| 20 | 0xF1B0 | 0xB0 (0x58) | 0xAD (0x56+) | ADT7462 #1, Ch D | |
| 21 | 0xF1B8 | 0xB8 (0x5C) | 0xAA (0x55) | ADT7462 #2, Ch A | Board Temp 4, Fan 5-6 |
| 22 | 0xF1B8 | 0xB8 (0x5C) | 0xAB (0x55+) | ADT7462 #2, Ch B | Board Temp 5 |
| 23 | 0xF1B8 | 0xB8 (0x5C) | 0xAC (0x56) | ADT7462 #2, Ch C | Board Temp 6 |
| 24 | 0xF1B8 | 0xB8 (0x5C) | 0xAD (0x56+) | ADT7462 #2, Ch D | param_d=0x04 (flag) |

**I2C bus encoding**: param_b high byte (0xF1) = I2C bus ID, low byte = PCA9544A 8-bit
address used as a mux selector.

### Type 14: Sensor/GPIO (Entries 25-142) - 118 Entries

This is the largest section, containing all GPIO pins used for sensor monitoring.
It includes two driver types:

#### AST2050 On-Chip GPIO (38 entries, IOAPI = 0x000f76f0)

Entry format for on-chip GPIO:
- **param_a** = GPIO bit mask (single bit position, e.g., 0x0010 = bit 4)
- **param_b** = Register sub-offset within GPIO bank (0x0000=data, 0x0002=direction, 0x0008=int enable, 0x000a=int sense)
- **param_c** = GPIO port group: 0x4000=GPIOA-D, 0x4002=GPIOE-H, 0x4004=GPIOI-L, 0x4006=GPIOM-P
- **param_d** = Logical GPIO index

| Entry | Bit Mask | Register | Port Group | GPIO Index | Likely GPIO Pin |
|-------|----------|----------|------------|------------|-----------------|
| 25 | 0x0010 | 0x08 (IntEn) | 0x4000 (A-D) | 0x05 | GPIOA4 |
| 26 | 0x0020 | 0x08 (IntEn) | 0x4000 (A-D) | 0x08 | GPIOA5 |
| 27 | 0x0100 | 0x08 (IntEn) | 0x4000 (A-D) | 0x09 | GPIOB0 |
| 28 | 0x0200 | 0x08 (IntEn) | 0x4000 (A-D) | 0x0A | GPIOB1 |
| 29 | 0x0400 | 0x08 (IntEn) | 0x4000 (A-D) | 0x0B | GPIOB2 |
| 30 | 0x0800 | 0x08 (IntEn) | 0x4000 (A-D) | 0x0C | GPIOB3 |
| 31 | 0x1000 | 0x08 (IntEn) | 0x4000 (A-D) | 0x0D | GPIOB4 |
| 32 | 0x2000 | 0x08 (IntEn) | 0x4000 (A-D) | 0x0E | GPIOB5 |
| 33 | 0x4000 | 0x08 (IntEn) | 0x4000 (A-D) | 0x0F | GPIOB6 |
| 34 | 0x8000 | 0x08 (IntEn) | 0x4000 (A-D) | 0x11 | GPIOB7 |
| 35 | 0x0002 | 0x00 (Data) | 0x4002 (E-H) | 0x12 | GPIOE1 |
| 36 | 0x0004 | 0x08 (IntEn) | 0x4002 (E-H) | 0x13 | GPIOE2 |
| 37 | 0x0008 | 0x00 (Data) | 0x4002 (E-H) | 0x14 | GPIOE3 |
| 38 | 0x0010 | 0x0A (IntSense) | 0x4002 (E-H) | 0x20 | GPIOE4 |
| 39-54 | 0x0001-0x8000 | 0x00 (Data) | 0x4004 (I-L) | 0x21-0x30 | GPIOI0-GPIOL7 |
| 55 | 0x0001 | 0x00 (Data) | 0x4006 (M-P) | 0x31 | GPIOM0 |
| 56 | 0x0002 | 0x00 (Data) | 0x4006 (M-P) | 0x3C | GPIOM1 |
| 57 | 0x1000 | 0x00 (Data) | 0x4006 (M-P) | 0x3D | GPION4 |
| 58 | 0x2000 | 0x00 (Data) | 0x4006 (M-P) | 0x10 | GPION5 |
| 59 | 0x0001 | 0x00 (Data) | 0x4002 (E-H) | 0x15 | GPIOE0 |
| 60 | 0x0020 | 0x00 (Data) | 0x4002 (E-H) | 0x1E | GPIOE5 |
| 61 | 0x4000 | 0x00 (Data) | 0x4002 (E-H) | 0x3E | GPIOG6 |
| 62 | 0x4000 | 0x02 (Dir) | 0x4006 (M-P) | -- | GPIOO6 (direction setup) |

The GPIO base register for the AST2050 is at 0x1E780000:
- Group 0x4000 (GPIOA-D): base + 0x000
- Group 0x4002 (GPIOE-H): base + 0x020
- Group 0x4004 (GPIOI-L): base + 0x070
- Group 0x4006 (GPIOM-P): base + 0x078

#### PCA9555 I2C GPIO Expander (80 entries, IOAPI = 0x000fc354)

Entry format for PCA9555:
- **param_a** = Bit mask within PCA9555 port (0x01-0x80, one bit per I/O pin)
- **param_b** = PCA9555 register: 0x0000=Output Port, 0x0008=Input Port, 0x000a=Config
- **param_c** = Port select: 0x4000=Port 0, 0x4002=Port 1, 0x0002=alternate mode
- **param_d** = I2C address encoding: high byte=bus ID (0xF6 or 0xF1), low byte=8-bit I2C addr

**PCA9555 Device Mapping:**

| param_d | I2C Bus | 8-bit Addr | 7-bit Addr | Device Function |
|---------|---------|------------|------------|-----------------|
| 0xF640 | Bus 0xF6 | 0x40 | 0x20 | PCA9555 #1 - PCIe slot presence (slots 1-8) |
| 0xF642 | Bus 0xF6 | 0x42 | 0x21 | PCA9555 #2 - PCIe slot presence (slots 9-16) |
| 0xF644 | Bus 0xF6 | 0x44 | 0x22 | PCA9555 #3 - PCIe slot power control |
| 0xF646 | Bus 0xF6 | 0x46 | 0x23 | PCA9555 #4 - PCIe slot status/LED |
| 0xF140 | Bus 0xF1 | 0x40 | 0x20 | PCA9555 #5 - Additional GPIO/status |

Each PCA9555 provides 16 GPIO lines (2 ports x 8 bits). With 5 devices, that's
80 I2C-based GPIO lines for PCIe slot management, in addition to the 38 on-chip GPIOs.

### Type 18: OEM Power Control (Entry 143)

| Entry | param_a | param_b | IOAPI | Notes |
|-------|---------|---------|-------|-------|
| 143 | 0xFFFF | 0x00FF | POWER | System power on/off/cycle controller |

### Type 20: PCA9544A I2C Mux (Entries 144-147)

4 I2C multiplexer channel configurations:

| Entry | param_a | param_b | param_d | Notes |
|-------|---------|---------|---------|-------|
| 144 | 0x00E0 | 0x0001 | 0x000C | Mux channel 0, 8-bit addr 0xE0 (7-bit 0x70) |
| 145 | 0x01E0 | 0x0001 | 0x000C | Mux channel 1 |
| 146 | 0x02E0 | 0x0001 | 0x000C | Mux channel 2 |
| 147 | 0x03E0 | 0x0001 | 0x0010 | Mux channel 3 (different config) |

param_a encodes: high byte = channel select, low byte = 8-bit I2C address of PCA9544A.
The PCA9544A at 7-bit address 0x70 (8-bit 0xE0) routes I2C buses to downstream
ADT7462, TMP100, and INA219 devices.

### Type 23: IRQ/Interrupt (Entries 148-153)

| Entry | param_a | param_b | param_d | Notes |
|-------|---------|---------|---------|-------|
| 148 | 0x0001 | 0x0120 | 0x0015 | IRQ for GPIO index 0x15 (PCA9555 interrupt) |
| 149 | 0x0001 | 0x0180 | 0x001E | IRQ for GPIO index 0x1E |
| 150 | 0x0001 | 0x0120 | 0x0011 | IRQ for GPIO index 0x11 |
| 151 | 0x0001 | 0x0020 | 0x0013 | IRQ for GPIO index 0x13 |
| 152 | 0x0001 | 0x0020 | 0x003E | IRQ for GPIO index 0x3E |
| 153 | 0x0001 | 0x0080 | 0x0000 | IRQ for GPIO index 0x00 (primary) |

param_b likely encodes the interrupt vector/priority configuration.

### Type 24: LED Control (Entries 154-187)

34 LEDs with various configurations:

| Entry | param_a | param_d | Notes |
|-------|---------|---------|-------|
| 154 | 0x0404 | 0x01 | LED 1 (blink mode) |
| 155 | 0x0404 | 0x02 | LED 2 (blink mode) |
| 156-180 | 0x0000 | 0x03-0x1E | LEDs 3-30 (steady mode) |
| 181 | 0x0000 | 0x53 | LED 83 (special/OEM) |
| 182 | 0x0000 | 0x0B | LED 11 (duplicate entry) |
| 183-184 | 0x0404 | 0x0D | LED 13 (blink, 2 entries) |
| 185 | 0x0101 | 0x01 | LED 1 (alternate blink) |
| 186 | 0x0000 | 0x01 | LED 1 (steady mode alias) |
| 187 | 0x0101 | 0x01B2 | LED 0x1B2 (special) |

param_a LED modes: 0x0000=steady, 0x0404=blink, 0x0101=alternate blink.

### Type 31: PMBus PSU (Entries 188-191)

4 power supply units on PMBus:

| Entry | param_a | param_d | Notes |
|-------|---------|---------|-------|
| 188 | 0x01FE | 0x11B2 | PSU 1 - PMBus addr encoding in param_d |
| 189 | 0x01FE | 0x21B2 | PSU 2 |
| 190 | 0x01FE | 0x31B2 | PSU 3 |
| 191 | 0x01FE | 0xCFE2 | PSU 4 (different encoding) |

param_a = 0x01FE: bitmask for PMBus capabilities. param_d high nibble selects
the PSU unit (1-3 for first three, 0xC for the fourth).

## Hardware Topology Summary

```
AST2050 BMC SoC
├── On-chip GPIO (38 pins across 4 port groups)
│   ├── GPIOA-D: Interrupt-enabled sensor inputs
│   ├── GPIOE-H: Mixed input/output
│   ├── GPIOI-L: 16 data lines (PCIe/system status)
│   └── GPIOM-P: System control outputs
├── IPMB (I2C-based, address 0x20)
├── KCS Interface (I/O base 0x0CA2) + Virtual KCS
├── Ethernet LAN
├── UART Serial Port
├── NVRAM Storage (SDR 4KB + SEL 8KB + PS 12KB)
├── 24Cxx EEPROM (I2C addr 0xA0, bus 0xF2)
├── PCA9544A I2C Mux (7-bit 0x70, bus 0xF1)
│   ├── Channel 0-2: ADT7462 #1 (mux 0xB0) → 4 fan/temp channels
│   └── Channel 3:   ADT7462 #2 (mux 0xB8) → 4 fan/temp channels
├── PCA9555 I2C GPIO Expanders (80 additional pins)
│   ├── Bus 0xF6, addr 0x20: PCIe slot presence (1-8)
│   ├── Bus 0xF6, addr 0x21: PCIe slot presence (9-16)
│   ├── Bus 0xF6, addr 0x22: PCIe slot power control
│   ├── Bus 0xF6, addr 0x23: PCIe slot status/LED
│   └── Bus 0xF1, addr 0x20: Additional GPIO/status
├── 34 LEDs
├── OEM Power Controller
├── 4x PMBus PSUs
└── 6 IRQ/Interrupt Lines
```

## Further Investigation

- [ ] Map GPIO logical indices to specific Dell C410X board functions (PCIe slot
  presence, power good signals, etc.)
- [ ] Decode PCA9555 pin assignments to specific PCIe slots
- [ ] Determine exact PMBus addresses from param_d encoding
- [ ] Cross-reference IRQ entries with AST2050 interrupt controller registers
- [ ] Compare LED indices with Dell C410X front panel LED layout
