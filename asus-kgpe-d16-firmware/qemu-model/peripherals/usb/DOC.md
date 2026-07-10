# USB 2.0 device / virtual hub — AST2050 faithfulness doc

**Base 0x1E6A0000, VIC INT#5.** A USB2.0 **device / virtual-hub** controller — the path
for BMC **virtual media / virtual keyboard/mouse** (OpenBMC). Full detail:
**[`DATASHEET-USB.md`](DATASHEET-USB.md)**.

## 1. Key facts

- HUB00 root control + 7 device blocks + a 21-endpoint pool with DMA descriptors.
- **The AST2050 has NO EHCI host at 0x1E6A1000** — that is an AST2400+ feature. All
  virtual media/HID goes through the device/vhub controller at 0x1E6A0000.

## 2. QEMU faithfulness — phantom EHCI REMOVED; device/vhub still unmodelled

`peripherals/usb/fwtest.c`:
- ☑ the device/vhub at **0x1E6A0000 is modelled** (2026-07-10): a G3-only
  `aspeed.udc-ast2050` register block (HUB00 root control + device blocks + EP
  pool), created in the SoC realize for `silicon_rev == AST2050_A1_SILICON_REV`.
  HUB00 is RW; `test_udc_modelled` now PASSES. Full USB device semantics
  (enumeration, endpoint DMA, virtual-media transport) are refinements.
- ☑ **0x1E6A1000 now reads 0** — the **phantom EHCI has been removed** (2026-07-10):
  `hw/arm/aspeed_ast2400.c` gates EHCI creation off when `silicon_rev ==
  AST2050_A1_SILICON_REV`, so the faithful G3 SoC no longer instantiates the
  AST2400 EHCI hosts at 0x1E6A1000/0x1E6A3000. `test_no_phantom_ehci` now PASSES
  (no longer xfail).

Remaining: the device/vhub at 0x1E6A0000 is still unmodelled, so OpenBMC virtual
media can't yet be exercised.

## 3. Faithful-model plan (large, oracle-gated)

Model the `aspeed.usb-vhub-ast2050` device controller at 0x1E6A0000 (root + device
blocks + EP pool) for virtual media/HID, and **remove the EHCI host at 0x1E6A1000** from
the G3 SoC (it should not exist). Both must keep the legacy boots green (the vendor
firmware pokes the UDC once at init — AST2050-PERIPHERAL-MODELING §1) — oracle-gated.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ (documents unmodelled UDC + phantom EHCI) |
| 2 | doc (this + `DATASHEET-USB.md`) | ☑ |
| 3 | QEMU model | ◐ **phantom EHCI removed + UDC register block modelled** (☑); full USB device semantics ☐ |
| 4 | integration test (`../../integration/test_usb.py`) | ☑ `test_no_phantom_ehci` + `test_udc_modelled` PASS |
