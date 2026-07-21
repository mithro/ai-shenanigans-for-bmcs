# HPE Intelligent Modular PDU — firmware reverse engineering

The HPE Intelligent Modular PDU (iPDU) is a rack power-distribution unit whose
Core Unit controller is a **Digi NS9360** (ARM926EJ-S) — *not* an Aspeed BMC
like the rest of this repo. Its stock firmware is **Digi NET+OS** (a
ThreadX-based RTOS with the RomPager embedded web server), not Linux, so the
open-firmware path for this board is a **U-Boot port** (`uboot-port/`), not
OpenBMC/u-bmc. Almost nothing from the AST2050 directories applies here.

Three vendor firmware versions were obtained and reverse-engineered: the Digi
`bootHdr` image format, the LZSS2 compression, NET+OS internals, and a security
assessment of the RomPager web interface.

## Start here

- [`STATUS.md`](STATUS.md) — completed work and open items.
- [`ANALYSIS.md`](ANALYSIS.md) — board IC inventory, NS9360 I/O assignment,
  and firmware internals.
- [`RESOURCES.md`](RESOURCES.md) — firmware and datasheet sources.
- [`HEADERS-J1-J6.md`](HEADERS-J1-J6.md) — the J1/J6 debug & programming
  headers (JTAG/serial access to the board).

## Firmware RE tooling

All scripts are **stdlib-only, PEP 723** Python — run with
`uv run hpe-ipdu-firmware/<script>.py`:

- `extract_firmware.py` / `decompress_firmware.py` — unpack the Digi `bootHdr`
  image and undo the LZSS2 compression.
- `parse_header.py`, `identify_crc.py`, `identify_crc_reveng.py` — image
  format and checksum identification.
- `analyse_firmware_map.py`, `analyse_decompressed.py`,
  `analyse_deep_binary.py`, `disasm_payload.py`, `trace_bsp_init.py`,
  `extract_gpio_init.py` — firmware layout, disassembly, and BSP/GPIO init
  tracing.
- `analyse_serial_ports.py`, `analyse_interconnect.py`,
  `analyse_stick_protocol.py`, `analyse_maxq3180.py`,
  `analyse_display_mcu.py`, `analyse_nvram.py` — per-peripheral protocol
  analysis (extension-bar "stick" bus, MAXQ3180 power-measurement AFE, display
  MCU, NVRAM layout).
- `compare_firmware_versions.py` — diffs the three obtained versions.
- `extract_web_ui.py` / `assess_rompager_vuln.py` — RomPager web UI extraction
  and security assessment.

## U-Boot port (`uboot-port/`)

The plans and working tree for the open-firmware replacement:

- [`uboot-port/PLAN-INCREMENTAL-PORT.md`](uboot-port/PLAN-INCREMENTAL-PORT.md)
  — hardware-tested phased build.
- [`uboot-port/PLAN-FULL-FEATURED-PORT.md`](uboot-port/PLAN-FULL-FEATURED-PORT.md)
  — QEMU-first build.
- [`uboot-port/REFERENCE-MATERIAL.md`](uboot-port/REFERENCE-MATERIAL.md) —
  the hardware spec digest.
- Submodules: `uboot-port/u-boot` ([mithro/u-boot](https://github.com/mithro/u-boot)
  branch `hpe-ipdu-port`), `uboot-port/qemu/qemu-10.0.7`
  ([mithro/qemu](https://github.com/mithro/qemu) branch `ns9360-machine` — an
  NS9360 machine model), plus vendored Digi NS9750/NS9360 U-Boot and
  `mach-ns9xxx` Linux references under `uboot-port/reference/`.

## Reference

`datasheets/` vendors the NS9360 datasheet + hardware reference, the MAXQ3180
AFE, the ICS1893 PHY, and the TMP89FM42 display-MCU datasheets.
