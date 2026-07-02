# Dell PowerEdge C410X - Component Datasheets

Datasheets for all ICs identified in the Dell PowerEdge C410X BMC firmware
reverse engineering. Downloaded from manufacturer websites using
[`download_datasheets.py`](download_datasheets.py).

---

## I2C Bus Topology

The AST2050 BMC manages all peripherals over 7 I2C buses. This diagram shows
how every I2C device connects:

```
AST2050 BMC
│
├── Bus 0xF0 ─── 16x INA219 current/power monitors (addr 0x40-0x4F)
│                 └─ One per PCIe slot, measures GPU power draw
│
├── Bus 0xF1 ─┬─ PCA9544A 4-ch mux (addr 0x70)
│             │   ├── Ch 0 → ADT7462 #1 (addr 0x58)  ─ fans 1-4, voltages, temps
│             │   └── Ch 1 → ADT7462 #2 (addr 0x5C)  ─ fans 5-8, voltages, temps
│             │
│             └─ PCA9555 #5 (addr 0x20)  ─ PSU management, fan status LEDs
│
├── Bus 0xF2 ─── AT24C256 EEPROM (addr 0x50)  ─ FRU data (serial, part number)
│
├── Bus 0xF3 ─── PEX8696 + PEX8647 PCIe switches (SMBus management)
│
├── Bus 0xF4 ─┬─ PCA9548 #1 8-ch mux (addr 0x70)
│             │   ├── Ch 0-7 → TMP75 slots 1-8 (addr 0x5C each)
│             │
│             └─ PCA9548 #2 8-ch mux (addr 0x71)
│                 └── Ch 0-7 → TMP75 slots 9-16 (addr 0x5C each)
│
├── Bus 0xF5 ─── (PMBus to 4x hot-swap PSUs)
│
└── Bus 0xF6 ─┬─ PCA9555 #1 (addr 0x20)  ─ Card presence detect (16 slots)
              ├─ PCA9555 #2 (addr 0x21)  ─ Per-slot power-good feedback
              ├─ PCA9555 #3 (addr 0x22)  ─ Attention buttons + slot power control
              ├─ PCA9555 #4 (addr 0x23)  ─ MRL (Manual Retention Latch) sensors
              └─ LM75 (addr 0x4F)        ─ Front board ambient temperature
```

---

## Datasheets by Component

### BMC SoC

| Datasheet | Part | Qty | Manufacturer | Description |
|-----------|------|-----|-------------|-------------|
| [AST2050_AST1100_Datasheet.pdf](AST2050_AST1100_Datasheet.pdf) | AST2050 / AST1100 | 1 | Aspeed | ARM926EJ-S @ 266 MHz integrated BMC SoC with VGA, I2C, GPIO, Ethernet, USB, SPI |

### Temperature & Fan Control

| Datasheet | Part | Qty | I2C Bus | I2C Addr | Description |
|-----------|------|-----|---------|----------|-------------|
| [ADT7462_Datasheet.pdf](ADT7462_Datasheet.pdf) | ADT7462 | 2 | 0xF1 | 0x58, 0x5C | Temperature/voltage monitor + 4-ch PWM fan controller |
| [TMP75_Datasheet.pdf](TMP75_Datasheet.pdf) | TMP75 | 16 | 0xF4 | 0x5C (×16 via mux) | Per-slot digital temperature sensor, 0.0625°C resolution |
| [LM75_Datasheet.pdf](LM75_Datasheet.pdf) | LM75 | 1 | 0xF6 | 0x4F | Front board ambient temperature sensor |

### Power Monitoring

| Datasheet | Part | Qty | I2C Bus | I2C Addr | Description |
|-----------|------|-----|---------|----------|-------------|
| [INA219_Datasheet.pdf](INA219_Datasheet.pdf) | INA219 | 16 | 0xF0 | 0x40–0x4F | Zero-drift bidirectional current/power monitor per GPU slot |

### I2C Multiplexers

| Datasheet | Part | Qty | I2C Bus | I2C Addr | Description |
|-----------|------|-----|---------|----------|-------------|
| [PCA9544A_Datasheet.pdf](PCA9544A_Datasheet.pdf) | PCA9544A | 1 | 0xF1 | 0x70 | 4-channel I2C mux with interrupt logic, routes to ADT7462 pair |
| [PCA9548A_Datasheet.pdf](PCA9548A_Datasheet.pdf) | PCA9548A | 2 | 0xF4 | 0x70, 0x71 | 8-channel I2C switch with reset, routes to 16× TMP75 sensors |

### GPIO Expanders

| Datasheet | Part | Qty | I2C Bus | I2C Addr | Function |
|-----------|------|-----|---------|----------|----------|
| [PCA9555_Datasheet.pdf](PCA9555_Datasheet.pdf) | PCA9555 | 5 | 0xF1, 0xF6 | 0x20–0x23 | 16-bit I2C GPIO expander |

PCA9555 instance assignments:

| Instance | Bus | Addr | Port 0 (pins 0–7) | Port 1 (pins 8–15) |
|----------|-----|------|--------------------|---------------------|
| #1 | 0xF6 | 0x20 | Card presence slots 1–8 | Card presence slots 9–16 |
| #2 | 0xF6 | 0x21 | Power-good slots 1–8 | Power-good slots 9–16 |
| #3 | 0xF6 | 0x22 | Attention buttons slots 1–8 | Slot power enable slots 1–8 |
| #4 | 0xF6 | 0x23 | MRL sensors slots 1–8 | MRL sensors slots 9–16 |
| #5 | 0xF1 | 0x20 | PSU presence/status | Fan status LEDs |

### Non-Volatile Storage

| Datasheet | Part | Qty | I2C Bus | I2C Addr | Description |
|-----------|------|-----|---------|----------|-------------|
| [AT24C256_Datasheet.pdf](AT24C256_Datasheet.pdf) | AT24C256 | 1 | 0xF2 | 0x50 | 256Kbit (32 KB) I2C EEPROM storing FRU data |

### SPI NOR Flash

The BMC boots from SPI flash. U-Boot auto-detects the installed chip. The
actual part varies by board revision — all are 64 or 128 Mbit SPI NOR.

| Datasheet | Part | Manufacturer | Capacity | Max Clock |
|-----------|------|-------------|----------|-----------|
| [M25P64_Datasheet.pdf](M25P64_Datasheet.pdf) | M25P64 (STM25P64) | STMicro / Micron | 64 Mbit | 50 MHz |
| [M25P128_Datasheet.pdf](M25P128_Datasheet.pdf) | M25P128 (STM25P128) | STMicro / Micron | 128 Mbit | 50 MHz |
| [S25FL128P_Datasheet.pdf](S25FL128P_Datasheet.pdf) | S25FL128P | Spansion / Infineon | 128 Mbit | 104 MHz |
| [MX25L12835F_Datasheet.pdf](MX25L12835F_Datasheet.pdf) | MX25L12835F (MX25L128D) | Macronix | 128 Mbit | 133 MHz |
| [W25X64_Datasheet.pdf](W25X64_Datasheet.pdf) | W25X64 | Winbond | 64 Mbit | 104 MHz |

### PCIe Switches

Full PLX/Broadcom datasheets are under NDA. Only product briefs are publicly
available.

| Datasheet | Part | Manufacturer | Lanes | Ports | Role in C410X |
|-----------|------|-------------|-------|-------|---------------|
| [PEX8696_ProductBrief.pdf](PEX8696_ProductBrief.pdf) | PEX8696 | PLX / Broadcom | 96 | up to 24 | Primary — fans out to 16 GPU slots |
| [PEX8647_ProductBrief.pdf](PEX8647_ProductBrief.pdf) | PEX8647 | PLX / Broadcom | 48 | 3 ×16 | Secondary — upstream to host servers via iPass |

---

## Summary

| Category | ICs | Total Instances |
|----------|-----|-----------------|
| BMC SoC | AST2050 | 1 |
| Temperature sensors | ADT7462, TMP75, LM75 | 19 |
| Power monitors | INA219 | 16 |
| I2C muxes | PCA9544A, PCA9548A | 3 |
| GPIO expanders | PCA9555 | 5 |
| EEPROM | AT24C256 | 1 |
| SPI flash | M25P64/M25P128/S25FL128P/MX25L12835F/W25X64 | 1 (varies) |
| PCIe switches | PEX8696, PEX8647 | 2 |
| **Total** | **13 unique parts** | **48 ICs** |

## Re-downloading

```sh
uv run python download_datasheets.py
```

The script skips files that already exist. Delete a PDF to force re-download.
