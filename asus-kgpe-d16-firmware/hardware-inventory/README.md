# KGPE-D16 — live hardware/firmware inventory

First **live, running-OS** inventory of the actual board (as opposed to the
datasheet / firmware-binary analysis elsewhere in the repo). Captured
**2026-07-08** from the board **PXE-booted into SystemRescue** (Linux 6.18) via
the Raspberry Pi bridge, collected over SSH. The raw command outputs are the
other files in this directory; this README summarises them. Every claim cites the
file it came from.

## Board / firmware
- **ASUSTeK KGP(M)E-D16**, Rev 1.xxG, board S/N `141236749400034` — `bios-baseboard.txt`.
- BIOS: **American Megatrends (AMI) v3309, 2016-06-16**, ROM **2 MiB**, *"Firmware
  ROM is socketed"*, SMBIOS 2.6 — `bios-baseboard.txt`.

## CPU / chipset
- **16-core AMD Opteron**, single CPU populated (socket CPU1; 16 logical CPUs) — `cpu.txt`.
- Northbridge **AMD RD890 / SR5690** `[1002:5a10]` + IOMMU `[1002:5a23]`;
  Southbridge **SP5100 (SB7x0/8x0)** — SATA `[1002:4390]` AHCI, USB OHCI/EHCI —
  `lspci-verbose.txt`. Matches the SR5690/SP5100 noted in `../../../resources.md`.

## Memory
- **1× 4 GiB DDR3-800 registered** in **DIMM_A2** (Ramaxel `RMR5030EF68F9W1600`,
  1 rank); all other slots *No Module Installed* — `memory.txt`.

## Networking
- **2× Intel 82574L Gigabit `[8086:10d3]`** (host LAN, PCI `02:00.0` + `03:00.0`) —
  `pci-aspeed.txt` / `lspci-tree.txt`. Their PXE ROM is **Intel Boot Agent GE
  v1.3.24** (the one whose >512-byte TFTP bug the bridge's `tftp-no-blocksize`
  works around). An iPXE option-ROM for these would be `808610d3`.

## BMC — ASPEED AST2050
- On PCI as **ASPEED Graphics Family `[1a03:2000]`** at **`01:01.0`**, driver
  `ast`, MMIO BAR0 **8 MB @ 0xf9000000** — `pci-aspeed.txt`. That BAR is the
  **P2A (PCIe→AHB)** doorway culvert uses to reach the BMC silicon.
- IPMI **KCS declared at I/O `0xCA2`** (DMI type 38) but **the BMC does not
  answer** — `ipmi_si` reports *"Interface detection failed"* — `ipmi-dmi.txt`.
- **Four-way confirmation the AST2050 has no functional firmware running:** no BMC
  network traffic, no BMC serial output, no IPMI-over-LAN, no in-band KCS response.
  Consistent with the open-firmware / spispy bring-up being the plan.

## Sensors
- Hardware monitor = **Nuvoton W83795G** on the **SP5100 SMBus** (`i2c-piix4` @
  0x0b00, I²C addr 0x2f); CPU temp via **k10temp** — `sensors.txt`. Fan1 ~2600 RPM,
  other fan headers unpopulated.

## Serial
- Host **COM1** (rear serial = `/dev/ttyS0` on the host) → PL2303 → the Pi's
  **`/dev/serial-com1`** — **verified working**, 115200 8N1, clean round-trip.

## Files
| File | Contents |
|---|---|
| `system.txt` | uname, rescue OS, hostnamectl |
| `cpu.txt` | lscpu + /proc/cpuinfo |
| `memory.txt` | free + dmidecode -t memory (DIMMs) |
| `dmidecode-full.txt` | full SMBIOS/DMI |
| `bios-baseboard.txt` | BIOS/system/baseboard/chassis/processor DMI |
| `ipmi-dmi.txt` | DMI type 38 (IPMI) + ipmi dmesg |
| `lspci-verbose.txt` | `lspci -nnvvv` (full) |
| `lspci-tree.txt` | `lspci -tvnn` topology |
| `pci-aspeed.txt` | the AST2050 (1a03) PCI device + BARs |
| `lsusb.txt` | USB devices/topology |
| `dmesg.txt` | kernel boot log |
| `network.txt` | NICs + drivers |
| `storage.txt` | block devices + storage controllers |
| `sensors.txt` | lm-sensors (W83795G, k10temp) |
| `i2c.txt` | i2c device nodes (pre-modprobe) |
| `iomem-ioports.txt` | /proc/iomem + /proc/ioports (BMC KCS/LPC ranges) |
| `modules.txt` | loaded kernel modules |

## How it was captured
Board PXE-booted SystemRescue through the RPi bridge (dnsmasq + the
`tftp-no-blocksize` workaround for the Intel Boot Agent), inventory pulled over
SSH from the bridge. See `../../HARDWARE-ACCESS.md` for the access setup.
