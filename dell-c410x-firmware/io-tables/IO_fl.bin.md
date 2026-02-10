# IO_fl.bin -- Master Hardware IO Table

## What This File Does

IO_fl.bin is the master hardware inventory for the BMC. It describes **every piece of
hardware** the BMC can talk to: GPIO pins, I2C devices, LEDs, fans, power supplies,
communication interfaces, and non-volatile storage. Each entry says "here is a device,
this is how to access it, and this is the driver that knows how to talk to it."

The file contains 192 entries organized by device type. When the firmware needs to
toggle a GPIO pin, read a fan speed, or turn on an LED, it looks up the entry in this
table to find the right driver and hardware address.

| Property | Value |
|----------|-------|
| **Location on BMC filesystem** | `/etc/default/ipmi/evb/IO_fl.bin` |
| **bmcsetting section name** | `[IOTABLE]` |
| **Size** | 2,456 bytes |
| **Loading function in fullfw** | `HWInitIOTableV3()` at address 0x00079a48 |

## File Structure

The file has three parts:

```
Bytes 0-3:      Header (version number and entry count hint)
Bytes 4-151:    Dispatch table (37 slots, 4 bytes each)
Bytes 152-2455: Entry table (192 entries, 12 bytes each)
```

### Header

- **Byte 0** = 0x03: This is version 3 of the IO table format
- **Byte 1** = 0x00: Reserved
- **Bytes 2-3** = 150 (little-endian): A hint about the number of entries. The actual
  entry count (192) is larger; the firmware calculates the real count from the file size.

### Dispatch Table -- Finding Entries by Device Type

The dispatch table is an array of 37 slots, one per device type. Each slot is 4 bytes
and says "entries for this device type start at index X and there are Y of them":

```c
struct { uint16_t count; uint16_t start_index; }
```

For example, the slot for "LED Control" (type 24) says count=34, start=154, meaning
LED entries are at indices 154 through 187 in the entry table.

Not all 37 type slots are used. Types 3, 4, 7, 8, 15-17, 19, 21-22, and 25-35 have
count=0 and contain no entries.

### Entry Table -- 192 Hardware Descriptors

Each entry is 12 bytes describing one hardware resource:

```c
struct io_entry {
    uint16_t  address_or_mask;    // Hardware address, bitmask, or flags
    uint16_t  register_or_bus;    // Register offset or bus routing info
    uint16_t  port_or_config;     // Port selector or device configuration
    uint32_t  driver_pointer;     // Address of the IOAPI driver vtable in firmware RAM
    uint16_t  device_id;          // Logical device identifier or I2C address
};
```

The meaning of each field depends on the device type. For GPIO entries, `address_or_mask`
is a bit mask selecting which pin. For I2C entries, it might encode an I2C address. The
`driver_pointer` always points to a specific IOAPI driver structure in the fullfw binary.

## Device Types and What They Control

### Communication Interfaces

**Type 0 -- IPMB Channel** (1 entry)

IPMB (Intelligent Platform Management Bus) is the I2C-based communication bus between
the BMC and other management controllers. The single entry configures the BMC's I2C
slave address as 0x20, which is the standard address for the primary BMC.

**Type 1 -- IPMB Sub-channels** (7 entries)

Seven virtual sub-channels within the IPMB interface. These allow the firmware to
multiplex different message types (normal commands, bridged messages, etc.) over the
single physical IPMB bus.

**Type 2 -- KCS Interfaces** (2 entries)

KCS (Keyboard Controller Style) is how software on the host server sends IPMI commands
to the BMC through a shared I/O port region:

| Entry | Interface | I/O Base | Notes |
|-------|-----------|----------|-------|
| 8 | Hardware KCS | 0x0CA2 | Physical I/O port shared with host CPU |
| 9 | Virtual KCS | (software) | Software-based IPMI channel for internal use |

**Type 5 -- LAN** (1 entry)

The BMC's Ethernet interface, used for remote IPMI-over-LAN access (RMCP/RMCP+).

**Type 6 -- UART/Serial** (1 entry)

The serial port, used for Serial Over LAN (SOL) which lets administrators access the
host server's serial console remotely through the BMC.

### Non-Volatile Storage

**Type 9 -- EEPROM and FRU** (2 entries)

| Entry | Storage | Details |
|-------|---------|---------|
| 12 | Physical EEPROM | 24Cxx I2C EEPROM at address 0xA0 on bus 0xF2 (stores FRU data: chassis model, serial number, part numbers) |
| 13 | Virtual FRU | NVRAM-based FRU storage for data that doesn't fit in the physical EEPROM |

**Type 10 -- SDR Repository** (1 entry)

4KB region storing IPMI Sensor Data Records -- the metadata describing all 72 sensors
(names, units, thresholds, conversion formulas).

**Type 11 -- SEL Repository** (1 entry)

8KB region for the System Event Log. When a sensor crosses a threshold or a hardware
event occurs, the BMC records it here with a timestamp.

**Type 12 -- Persistent Storage** (1 entry)

12KB general-purpose NVRAM for runtime configuration that persists across reboots
(network settings, user accounts, etc.).

### Fan and Temperature Monitoring

**Type 13 -- ADT7462 Fan/Temperature Controllers** (8 entries)

The C410X has two Analog Devices ADT7462 chips for thermal management. Each ADT7462
can monitor temperatures and control fan speeds. They sit on I2C bus 0xF1, behind a
PCA9544A 4-channel I2C multiplexer at address 0x70.

| Entry | Chip | Mux Select | Channel | Function |
|-------|------|------------|---------|----------|
| 17 | ADT7462 #1 | 0xB0 | A (0xAA) | Board region 1 -- Remote Temp 1 + fan tach |
| 18 | ADT7462 #1 | 0xB0 | B (0xAB) | Board region 1 -- Remote Temp 2 |
| 19 | ADT7462 #1 | 0xB0 | C (0xAC) | Board region 1 -- Local Temp |
| 20 | ADT7462 #1 | 0xB0 | D (0xAD) | Board region 1 -- additional channel |
| 21 | ADT7462 #2 | 0xB8 | A (0xAA) | Board region 2 -- Remote Temp 1 + fan tach |
| 22 | ADT7462 #2 | 0xB8 | B (0xAB) | Board region 2 -- Remote Temp 2 |
| 23 | ADT7462 #2 | 0xB8 | C (0xAC) | Board region 2 -- Local Temp |
| 24 | ADT7462 #2 | 0xB8 | D (0xAD) | Board region 2 -- additional channel |

To read ADT7462 #1, the firmware first writes to the PCA9544A mux at 0x70 to select
the 0xB0 channel, then reads from the ADT7462's registers.

### GPIO Pins -- The Largest Section

**Type 14 -- Sensor/GPIO** (118 entries)

This is by far the biggest section, with 118 entries covering all GPIO pins used by
the BMC. There are two kinds:

#### AST2050 On-Chip GPIO (38 entries)

These are pins directly on the BMC SoC. Each entry specifies:
- **Which pin**: a bitmask (e.g., 0x0010 = bit 4 within the port group)
- **What register**: data (read/write the pin), direction (input/output), interrupt enable, or interrupt sense
- **Which port group**: GPIOA-D, GPIOE-H, GPIOI-L, or GPIOM-P

The AST2050's GPIO registers live at base address 0x1E780000:

| Port Group | Firmware Code | Register Offset | Entries | Usage |
|------------|--------------|-----------------|---------|-------|
| GPIOA-D | 0x4000 | +0x000 | 10 pins | Interrupt-driven inputs: hardware alerts, sensor events |
| GPIOE-H | 0x4002 | +0x020 | 7 pins | Mixed: I2C device interrupts, status signals |
| GPIOI-L | 0x4004 | +0x070 | 16 pins | PCIe/system status monitoring data lines |
| GPIOM-P | 0x4006 | +0x078 | 5 pins | System control outputs (power, resets) |

Most GPIOA-D pins are configured with interrupt enable, meaning the BMC gets notified
immediately when these signals change (rather than having to poll).

#### PCA9555 I2C GPIO Expanders (80 entries)

The C410X needs far more GPIO pins than the AST2050 provides natively, so it uses five
PCA9555 chips. Each PCA9555 is a 16-bit I2C GPIO expander (two 8-bit ports). These
are the workhorses for managing the 16 PCIe slots:

| I2C Bus | 7-bit Address | 8-bit Address | Function |
|---------|---------------|---------------|----------|
| 0xF6 | 0x20 | 0x40 | **PCIe slots 1-8 presence detect** -- Port 0 and Port 1 pins map to individual slot PRSNT# signals |
| 0xF6 | 0x21 | 0x42 | **PCIe slots 9-16 presence detect** -- same layout for the upper 8 slots |
| 0xF6 | 0x22 | 0x44 | **PCIe slot power control** -- output pins enable/disable 12V power to each slot |
| 0xF6 | 0x23 | 0x46 | **PCIe slot status and LEDs** -- drives per-slot indicator LEDs and reads status signals |
| 0xF1 | 0x20 | 0x40 | **Additional status/control** -- miscellaneous GPIO for system management |

Each PCA9555 entry specifies:
- A **bit mask** (0x01-0x80) selecting which of the 8 pins in a port
- A **register selector**: 0x0000 for output, 0x0008 for input, 0x000a for direction config
- A **port selector**: Port 0 or Port 1 within the PCA9555

### Power Management

**Type 18 -- OEM Power Control** (1 entry)

Controls the system power state (power on, power off, power cycle). This is how
IPMI Chassis Control commands get translated into physical power actions.

**Type 31 -- PMBus Power Supplies** (4 entries)

The C410X supports 4 hot-swappable power supplies that communicate over PMBus (a
protocol built on I2C for power supply management). Each entry configures one PSU:

| Entry | PSU | Notes |
|-------|-----|-------|
| 188 | PSU 1 | PMBus capabilities bitmask 0x01FE |
| 189 | PSU 2 | Same configuration |
| 190 | PSU 3 | Same configuration |
| 191 | PSU 4 | Different address encoding (last PSU slot) |

### I2C Multiplexer Control

**Type 20 -- PCA9544A I2C Mux** (4 entries)

Four entries configuring the PCA9544A 4-channel I2C multiplexer at 7-bit address 0x70
(8-bit 0xE0). This mux sits on bus 0xF1 and routes to the ADT7462 thermal management
chips and other devices. Each entry represents one mux channel:

| Entry | Channel | Downstream Devices |
|-------|---------|-------------------|
| 144 | 0 | ADT7462 #1 (via mux address 0xB0) |
| 145 | 1 | Additional I2C segment |
| 146 | 2 | Additional I2C segment |
| 147 | 3 | ADT7462 #2 (via mux address 0xB8), different config |

### Interrupt Handling

**Type 23 -- IRQ/Interrupt** (6 entries)

Six hardware interrupt sources that the BMC monitors for asynchronous events:

| Entry | Interrupt Source | Purpose |
|-------|-----------------|---------|
| 148 | GPIO index 0x15 | PCA9555 interrupt (card presence change) |
| 149 | GPIO index 0x1E | Hardware event notification |
| 150 | GPIO index 0x11 | Hardware event notification |
| 151 | GPIO index 0x13 | Hardware event notification |
| 152 | GPIO index 0x3E | Hardware event notification |
| 153 | GPIO index 0x00 | Primary system interrupt |

When one of these GPIO pins triggers, the BMC's interrupt handler runs the appropriate
service routine to determine what changed and take action (e.g., log a card removal
event to the System Event Log).

### LED Control

**Type 24 -- LEDs** (34 entries)

34 LEDs for front-panel status indication. Each entry configures one LED with:
- A **mode** encoded in the first field: 0x0000 = steady on/off, 0x0404 = blinking, 0x0101 = alternate blink pattern
- A **logical LED index** identifying which physical LED

Most LEDs (entries 156-180) are straightforward steady-state indicators. Two LEDs
(entries 154-155) default to blinking mode, suggesting they indicate active/fault status.
The last few entries include alternate configurations for LEDs that have multiple modes
(e.g., a health LED that blinks amber for warning and steady green for OK).

## IOAPI Driver Reference

Every entry points to an IOAPI driver structure (a vtable of function pointers) in the
fullfw binary. These are the 19 distinct drivers used:

| Driver (symbol in fullfw) | Purpose | Entries Using It |
|---------------------------|---------|-----------------|
| `G_sONCHIP_GPIO_IOAPI` | Read/write AST2050 GPIO pins | 38 |
| `G_sPCA9555_I2CGPIO_IOAPI` | Read/write PCA9555 I2C GPIO expander pins | 80 |
| `G_sONCHIP_LED_IOAPI` | Control front-panel LEDs | 34 |
| `G_sOEMADT7462_I2CFAN_IOAPI` | Talk to ADT7462 thermal management chips | 8 |
| `G_sONCHIP_Generic_ISRAPI` | Register interrupt service routines | 6 |
| `G_sOEMPCA9544_I2CSWITCH_IOAPI` | Control PCA9544A I2C multiplexer | 4 |
| `G_sPMBus_PSU_IOAPI` | Communicate with PSUs over PMBus | 4 |
| `G_sONCHIP_IPMB_IOAPI` | IPMB messaging (I2C slave) | 1 |
| `G_sONCHIP_KCS_IOAPI` | Hardware KCS interface | 1 |
| `G_sONCHIP_VKCS_IOAPI` | Virtual/software KCS interface | 1 |
| `G_sONCHIP_vDrvLAN_IOAPI` | Ethernet networking | 1 |
| `G_sONCHIP_UART_IOAPI` | Serial port / SOL | 1 |
| `G_sEE24Cxx_EEPROM_IOAPI` | Read/write I2C EEPROM | 1 |
| `G_sONCHIP_vDrvFRU_IOAPI` | Virtual FRU data storage | 1 |
| `G_sONCHIP_vDrvSDR_IOAPI` | Sensor Data Record repository | 1 |
| `G_sONCHIP_vDrvSEL_IOAPI` | System Event Log repository | 1 |
| `G_sONCHIP_vDrvPS_IOAPI` | Persistent NVRAM storage | 1 |
| `G_sOEMPower_vDrvPOWER_IOAPI` | System power control | 1 |
| (null -- virtual entries) | IPMB sub-channel placeholders | 7 |

## How the Firmware Uses This Table

When the firmware starts, `HWInitIOTableV3()` memory-maps the entire file using
`MakeMemFileV2()` (which adds a 16-byte in-memory header wrapper). Two global pointers
are set:

- `G_sIOTableHeaderVer3Ptr` (at 0x00110b98): points to the start of the in-memory buffer
- `G_sIOTablePtr` (at 0x00110b9c): points to the first entry (at offset +0x98 from the header)

When code needs to access hardware of a given type (say, type 13 for ADT7462), it reads
the dispatch table at `type * 4` bytes from the start, gets the count and start index,
then iterates through entries starting at `G_sIOTablePtr + start_index * 12`.

Each entry's `driver_pointer` field is a RAM address pointing to the IOAPI vtable, which
contains function pointers for operations like `init()`, `read()`, `write()`, and
`close()`. The firmware calls through these pointers to perform the actual hardware I/O.
