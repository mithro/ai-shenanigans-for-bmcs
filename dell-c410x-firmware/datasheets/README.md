# Dell PowerEdge C410X - Component Datasheets

Datasheets for all ICs identified in the Dell PowerEdge C410X BMC firmware
reverse engineering. These were downloaded from manufacturer websites using
`download_datasheets.py`.

## BMC SoC

| File | Part | Manufacturer | Description | Role in C410X |
|------|------|-------------|-------------|---------------|
| `AST2050_AST1100_Datasheet.pdf` | AST2050 / AST1100 | Aspeed Technology | ARM926EJ-S @ 266 MHz, integrated BMC SoC | Main BMC controller - manages all chassis functions |

## Temperature Sensors

| File | Part | Manufacturer | Description | Role in C410X |
|------|------|-------------|-------------|---------------|
| `ADT7462_Datasheet.pdf` | ADT7462 | ON Semi (formerly Analog Devices) | Flexible temperature, voltage monitor & fan controller | 2x on main board (via PCA9544A mux on bus 0xF1) |
| `TMP75_Datasheet.pdf` | TMP75 | Texas Instruments | Digital temperature sensor, I2C, TMP100-compatible | 16x per-slot temperature monitoring (via PCA9548 mux on bus 0xF4) |
| `LM75_Datasheet.pdf` | LM75 | Texas Instruments | Digital temperature sensor, I2C | 1x front board temperature sensor (bus 0xF6, addr 0x4F) |

## Power Monitoring

| File | Part | Manufacturer | Description | Role in C410X |
|------|------|-------------|-------------|---------------|
| `INA219_Datasheet.pdf` | INA219 | Texas Instruments | Zero-drift bidirectional current/power monitor, I2C | 16x per-slot GPU power consumption monitoring (bus 0xF0) |

## I2C Multiplexers

| File | Part | Manufacturer | Description | Role in C410X |
|------|------|-------------|-------------|---------------|
| `PCA9544A_Datasheet.pdf` | PCA9544A | NXP (via TI) | 4-channel I2C-bus multiplexer with interrupt logic | 1x routes to 2x ADT7462 chips (bus 0xF1, addr 0x70) |
| `PCA9548A_Datasheet.pdf` | PCA9548A | NXP (via TI) | 8-channel I2C-bus switch with reset | 2x routes to 16x TMP75 sensors (bus 0xF4, addr 0x70/0x71) |

## GPIO Expanders

| File | Part | Manufacturer | Description | Role in C410X |
|------|------|-------------|-------------|---------------|
| `PCA9555_Datasheet.pdf` | PCA9555 | NXP / TI | 16-bit I2C GPIO expander with interrupt | 5x total: slot presence, power-good, attention buttons, power control, MRL sensors, PSU management, fan LEDs |

## Non-Volatile Storage

| File | Part | Manufacturer | Description | Role in C410X |
|------|------|-------------|-------------|---------------|
| `AT24C256_Datasheet.pdf` | AT24C256 | Atmel (Microchip) | 256Kbit (32KB) I2C EEPROM | FRU data storage (bus 0xF2, addr 0x50) |

## SPI NOR Flash

The BMC's U-Boot bootloader supports multiple SPI flash chips. The actual chip
installed varies by board revision. All are 64Mbit or 128Mbit SPI NOR devices.

| File | Part | Manufacturer | Description |
|------|------|-------------|-------------|
| `M25P64_Datasheet.pdf` | M25P64 (STM25P64) | STMicro / Micron | 64Mbit SPI NOR, 50MHz |
| `M25P128_Datasheet.pdf` | M25P128 (STM25P128) | STMicro / Micron | 128Mbit SPI NOR, 50MHz |
| `S25FL128P_Datasheet.pdf` | S25FL128P | Spansion / Cypress / Infineon | 128Mbit 3.0V SPI Flash, 104MHz |
| `MX25L12835F_Datasheet.pdf` | MX25L12835F (MX25L128D) | Macronix | 128Mbit 3V SPI Flash, dual/quad I/O |
| `W25X64_Datasheet.pdf` | W25X64 | Winbond | 64Mbit SPI Flash, dual output |

## PCIe Switches

Full datasheets for PLX/Broadcom PCIe switches are under NDA. Only product
briefs are publicly available.

| File | Part | Manufacturer | Description | Role in C410X |
|------|------|-------------|-------------|---------------|
| `PEX8696_ProductBrief.pdf` | PEX8696 | PLX / Broadcom | 96-lane PCIe Gen2 switch, up to 24 ports | Primary switch - fans out to 16 GPU slots |
| `PEX8647_ProductBrief.pdf` | PEX8647 | PLX / Broadcom | 48-lane PCIe Gen2 switch, 3 x16 ports | Secondary switch - upstream to host servers |

## Re-downloading

To re-download all datasheets:

```sh
uv run python download_datasheets.py
```

The script skips files that already exist. Delete a PDF to re-download it.
