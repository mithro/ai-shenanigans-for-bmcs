# AST2050 peripheral modelling for the C4 vendor firmware (QEMU)

Goal (user directive, 2026‑07‑01): *model every AST2050 peripheral the proprietary
Dell C410X firmware uses (and eventually every AST2050 peripheral), under the
`kgpe-d16-bmc` QEMU machine.* This document is the data‑driven inventory + the
**corrected** eth0/C4 diagnosis.

All kernel addresses are into the **decompressed** vendor kernel `kernel.bin`
(carved by `proprietary/extract-c410x.py` then `gunzip`), linked at **0xC0008000**
(file_off = vaddr − 0xC0008000). Disassemble with `arm-linux-gnueabi-objdump -D
-b binary -m arm`. Runtime facts come from `gdb-multiarch` against live QEMU
(`-S -gdb tcp::11234`); watchpoints/breakpoints match by *virtual* address.

## 1. Data‑driven peripheral inventory (`-d unimp,guest_errors`)

Boot of the patched flash to userspace, logging every unmodelled/rejected MMIO
access (`tmp/c4/unimp.log`, 28 563 lines). Aggregated:

| Count | Source | Meaning | Functional? |
|------:|--------|---------|-------------|
| 14 710 | `aspeed_vic_read` offset **0x14** | AST2050 legacy `INTR_DIS` read | **noise** — RMW works with 0 |
| 7 128 | `aspeed_vic_read` offset **0x38** | AST2050 legacy `INTR_EDGE_CLR` read | **noise** — RMW works with 0 |
| 6 492 | `aspeed_ast2400_scu_write` "SCU is locked!" | write w/o unlock key | **noise** — ast2400 path logs but does **not** `return` (unlike ast2500), write still applies |
| ~79 | `aspeed.io` offset **0x0a0xxx** = **0x1E6A0000** | **USB2.0 Virtual‑Hub / Device Controller (UDC)** | gap: reads 0, writes dropped |
| ~110 | `aspeed.video` = **0x1E700000** | **Video Engine (KVM capture)** | gap: reads 0, writes dropped |
| 2 | `do_phy_write` offset 9 | MDIO PHY reg 9 | minor |
| 4 | `aspeed_timer` pulse mode | unsupported pulse mode | noise |

### AST2050 legacy VIC register map (authoritative)
From the Raptor kernel `arch/arm/plat-aspeed/include/plat/regs-intr.h` (the
`#else`/non‑`NEW_VIC` block — the vendor firmware uses this):
`0x00 IRQ_STS, 0x04 FIQ_STS, 0x08 RAW_STS, 0x0C SEL, 0x10 EN, 0x14 DIS,
0x18 SW_EN, 0x1C SW_CLR, 0x24 SENSE, 0x28 BOTH_EDGE, 0x2C EVENT, 0x38 EDGE_CLR`.
The QEMU `hw/intc/aspeed_vic.c` implements the *newer* semantics (0x14 =
write‑only enable‑clear; **no** 0x38 read; 0x38 write aliases edge‑clear). Reads
of 0x14/0x38 hit the "Bad register" default and return 0. The vendor IRQ code
(`ast_mask_irq`, `IRQ_EDGE_CLEAR`) does `readl|=bit;writel` — returning 0 makes
the RMW touch only its own bit, so it is **functionally correct**; the 21 838
messages are pure log noise. A *faithful* model would add `0x14`→disable‑mask and
`0x38`→edge‑status reads (deferred: low value).

### Unmodelled peripherals (genuine gaps)
- **USB2.0 UDC** `0x1E6A0000` (AST_USB20_BASE) — one‑time init pokes (not a hot
  poll), so not a boot blocker; needed for USB virtual‑media faithfulness.
- **Video Engine** `0x1E700000` (AST_VIDEO_BASE) — the `aess_video.ko` module +
  `avct_init_video_capture` drive it; needed for KVM faithfulness.

## 2. eth0 / C4 — CORRECTED diagnosis (the pre‑compaction RE was WRONG)

**The pre‑compaction `AIM-ETH0-RE.md` conclusion is disproven by runtime tracing.**
It claimed the ftgmac probe fails because an AESS/AIM registry list is empty and
returns `-EFAULT`. Ground truth (gdb breakpoints on the live patched kernel):

- The AESS `ctrlflag` call (`0x13a190`→core `0x1399a8`, registry `0xc035e040`,
  a **debugfs**‑based AIM file framework) **returns a valid pointer** `0xc5fe24b8`.
- The probe takes the **success‑continue** path (`0xc001a7d0`), never `-ENODEV`.
- The whole probe function `0xc001a404`–`0xc001a834` **returns 0 (success)**.
- The pre‑compaction watchpoint watched `fc+0x20`; the reader actually derefs
  `fc+0x14` (decimal 20) → `+0x38` (decimal 56), and `fc+0x14` **is** populated
  (=`0xc4cf6000`, written at pc `0xc00a59f0`). So that path is fine.

### The real gate (runtime‑verified)
Inside the ftgmac probe, after `alloc_etherdev` (`0xc001a434`) and MAC setup:
```
0xc001a5b0  ldr  r3,[r5,#0x19c]       ; r5=netdev priv; r3=cfg (= priv+0x3a0)
0xc001a5b4  ldr  r2,=0x225
0xc001a5b8  ldrb r3,[r3,r2]           ; flag = cfg[0x225]  ("MAC enabled")
0xc001a5bc  cmp  r3,#0
0xc001a5c0  bne  0xc001a5d0           ; flag!=0 -> register_netdevice (0x1c272c)
0xc001a5c4  mov  r0,r5
0xc001a5c8  bl   0x1c1f84             ; flag==0 -> free_netdev, SILENTLY skip
0xc001a5cc  b    0xc001a670
```
Runtime: `cfg[0x225] == 0x00` for **both** MAC0 and MAC1 → both netdevs freed →
no eth0/eth1, **no error message**. This exactly matches the symptom
(`Set MAC%d Address` prints, then `ip: cannot find device "eth0"`).

### Where the flag comes from
`cfg` (priv+0x3a0, a 0x228‑byte struct) is filled from the **"MAC information"**
read: `0xc001a524  bl 0x1a9fe0(id, buf, 8)` with id **0x24008 (MAC0)** /
**0x24010 (MAC1)**; on failure it prints **"Fail to get the MAC information!"**.
`0x1a9fe0`→`0x1a8354` decodes the id against a platform‑config register
(`[global+0x10c] & 0xf`, `& 0x70`) and reads the MAC info (I²C EEPROM path). The
8‑byte blob carries the MAC **and** the enable byte at `+0x225`.

`proprietary/patch-c410x-mac.py` injects the MAC *bytes* (so `Set MAC0 Address`
prints) but does **not** set the enable byte — hence eth0 still never registers.

### Verified: forcing the flag is not sufficient
Forcing `r3=1` at `0xc001a5bc` (gdb) for both MACs still yields
`ip: cannot find device "eth0"`. So `register_netdevice` needs the *valid config
data* the MAC‑info read should populate (netdev_ops/`+0x38`,`+0xac` set on the
register path, plus the loaded blob) — not just the gate bit. The faithful fix is
therefore to make the **MAC‑info source real**, not to poke the flag.

## 3. Faithful‑fix path for C4 (next steps)
1. Fully decode `0x1a8354`'s id→(I²C bus/addr/offset) mapping for id 0x24008/0x24010
   under this board's platform‑config value; confirm the bus/address at runtime by
   tracing the I²C engine access (or the SMC/EEPROM path it actually takes).
2. Seed that source (the machine already seeds an EEPROM at I²C 0x50) with a blob
   whose MAC **and** enable byte are correct, so `0x1a9fe0` returns 0, `cfg` is
   fully populated, `cfg[0x225]!=0`, and `register_netdevice` succeeds.
3. Re‑verify: `eth0` registers, slirp hostfwd `:8080→80` serves the appweb GUI.
4. Independently, model USB2.0 UDC + Video Engine for general faithfulness.

## 4. Reproduction
```sh
# diagnostic boot with unimplemented-access logging
tmp/qemu-dev/build/qemu-system-arm -M kgpe-d16-bmc -m 128 -display none \
  -serial file:tmp/c4/diag_serial.log -nic user,model=ftgmac100,hostfwd=tcp::8080-:80 \
  -drive file=tmp/c4/flash-patched.img,format=raw,if=mtd -no-reboot \
  -D tmp/c4/unimp.log -d unimp,guest_errors
# runtime gate check (gdb): see proprietary/re-tools/gate.gdb / force.gdb
```

## 5. VERIFIED: the enable byte is the gate (register_netdevice now runs)

Corrected `patch-c410x-mac.py` (blob byte 6 = enable = 1; `0x125c0` gate branch
left intact) and rebuilt the flash (`flash-fixed.img`). Result:
- `cfg[0x225]` is now non-zero → the probe takes the **register path** and
  **`register_netdevice` is now called** (confirmed in the boot trace) — it was
  never reached before. **This validates the corrected diagnosis end-to-end.**
- However the boot then **oopses** during netdev registration: `rtnl_fill_ifinfo`
  jumps to a bad PC `0x4e497210`; crash registers point into the ftgmac priv
  (`r10=0xc57ad9e0`, priv≈`0xc57ad800`). So the ftgmac netdev registers but with a
  corrupt callback (e.g. `dev->get_stats`) / priv state — a **ftgmac100 hardware
  / driver-setup** issue that only manifests once the MAC is actually brought up
  (it was masked before because the MAC was force-disabled).

### Remaining work for C4 (now precise)
The gate is solved; the last blocker is the ftgmac bring-up itself under QEMU.
Next: trace why the registered ftgmac netdev has a bad `get_stats`/priv — either a
setup step skipped by the synthetic MAC-info blob, or an ftgmac100 register the
QEMU model returns 0 for that the vendor driver uses to size/populate the netdev
(DMA rings, stats block). Modelling that ftgmac100 detail (or supplying the full
real MAC-info blob via the I²C EEPROM) is the final step to a live eth0 + appweb.
