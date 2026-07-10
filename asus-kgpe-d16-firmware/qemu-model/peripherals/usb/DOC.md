# USB 2.0 device / virtual hub — AST2050 faithfulness doc

**Base 0x1E6A0000, VIC INT#5.** A USB2.0 **device / virtual-hub** controller — the path
for BMC **virtual media / virtual keyboard/mouse** (OpenBMC). Full detail:
**[`DATASHEET-USB.md`](DATASHEET-USB.md)**.

## 1. Key facts

- HUB00 root control + 7 device blocks + a 21-endpoint pool with DMA descriptors.
- **The AST2050 has NO EHCI host at 0x1E6A1000** — that is an AST2400+ feature. All
  virtual media/HID goes through the device/vhub controller at 0x1E6A0000.

## 2. QEMU faithfulness — UNMODELLED + a PHANTOM EHCI

`peripherals/usb/fwtest.c`:
- ✗ the device/vhub at **0x1E6A0000 reads 0** and is not writable — **not modelled**.
- ✗ **0x1E6A1000 reads `0x01000020`** — QEMU exposes an **EHCI host controller the
  AST2050 does not have** (an AST2400 feature leaking through the SoC model).

So OpenBMC virtual media cannot be verified, and the machine exposes a phantom EHCI.

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
| 3 | QEMU model | ☐ new UDC/vhub + remove phantom EHCI (§3) |
| 4 | integration test (`../../integration/test_usb.py`) | ◐ checks xfail until §3 |
