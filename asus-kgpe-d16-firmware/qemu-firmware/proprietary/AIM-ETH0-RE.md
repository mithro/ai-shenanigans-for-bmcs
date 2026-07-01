# C4 eth0 registration — proprietary AIM-framework RE (continuation notes)

Goal: make the Dell C410X vendor kernel register `eth0` under the `kgpe-d16-bmc`
QEMU machine so its (already-running) `appweb` web service is reachable via slirp
hostfwd — the last step of C4. This must be a **faithful** fix (model the missing
hardware / satisfy the real dependency), not a firmware forgery.

All addresses are into the **decompressed** vendor kernel Image (`kernel.bin`,
carved by `extract-c410x.py` then `gunzip`), linked at **0xC0008000**
(file_offset = vaddr − 0xC0008000). Disassemble with
`arm-linux-gnueabi-objdump -D -b binary -m arm`.

## Solved this session

- **machid** 0x232b (find-machid.py), **16 MB flash**, `ignore_memory_
  transaction_failures`, **RAM-disk root**, **tmpfs /flash** wrapper, **OABI
  vendor busybox/libs** — the firmware boots fully to a running BMC (appweb
  launched).
- **MAC-read blocker** (`patch-c410x-mac.py`): the driver read its MAC via I2C
  from `0x24008`/`0x24010` (bus/addr/offset encoding) and bailed with
  `Fail to get the MAC information!`. Patched the success/fail branch to inject
  00:e0:81:12:34:56. Now the driver runs `Set MAC0 Address` / `Set MAC1 Address`.
  (Note: patch-c410x-mac.py is a stopgap for RE; the faithful fix is to model the
  I2C MAC device at the decoded bus/addr — decode `0x1a8354`'s use of `r1`.)

## The remaining blocker: AIM framework, traced call chain

The ftgmac probe (the function at **0xc001a4a0–0xc001a834**, which reads the MAC
and stores it to `dev->dev_addr` at `dev+0x13c`) then, at **0xc001a6f0**, does:

```
0xc001a6f0  bl 0x139bf8            ; returns non-zero OK (netdev alloc?) -> stored [r4]
0xc001a708  ldrb r5,[r4,r6]        ; r5 = type index
0xc001a70c  mov r3,#2              ; hardcoded selector = 2
0xc001a72c  ldrls pc,[pc,r3<<2]    ; jump table -> entry 2 = 0xc001a774
0xc001a774  bl 0x13a190            ; -> wraps bl 0x1399a8 (AIM)
0xc001a7a4  str r0,[array+r5*4+4]  ; store AIM result
0xc001a7b0  ldr r3,[array+r5*4+4]
0xc001a7b4  cmp r3,#0
0xc001a7b8  bne 0xc001a7d0         ; if AIM result != 0 continue; else -> ...
0xc001a7bc  printk; mvn r1,#18 (-ENODEV)   ; the FAIL path
```

`0x1399a8` returns 0 because its AIM global is not initialised:

```
0x1399a8: r8 = *0x139be8 = 0xc03523a4    ; address of the AIM global-pointer var
          r1 = [r8]                      ; = *0xc03523a4  (the AIM struct pointer)
          if r1==0 -> -EFAULT            ; <-- NULL here under QEMU
          r1 = [r1+20]; if 0 -> -EFAULT
          r6 = [r1+56]; if 0 -> -EFAULT
```

The AIM global var `0xc03523a4` is in **BSS** (beyond the file; zero at boot). It
is referenced in exactly **2** places (verified by scanning for the literal):
- `0x139be8` — the reader (`0x1399a8`).
- `0x139d84` — the setter: at `0xc001a370` (`ldr r0,[pc]@0x139d84 = 0xc03523a4;
  ldr r1,[pc]@0x139d88 = 0x142; bl 0xa5768`). So **`0xa5768(&AIM_global, 0x142)`
  is the only code that can set the AIM global.** `0xa5768` is also called widely
  elsewhere — likely a generic register/publish helper.

Also note a **second, non-fatal** `0x1399a8` call at `0xc001a810`
(`r1=292 / 0x124`, result -> `[r4+0x104]`) — only logs, doesn't gate eth0.

## Hypotheses to test next (in priority order)

1. **Initcall ordering.** The ftgmac probe is built-in and runs at kernel boot
   (`Set MAC0` prints before userspace). If the function that calls
   `0xa5768(&AIM_global,…)` (the setter, around `0xc001a300`) is a later
   `initcall` than the ftgmac probe, the AIM global is still NULL at probe time.
   → Find the setter function's entry + its `.initcall` level vs the ftgmac
   driver's. If ordering, the faithful fix is subtle (the vendor relied on a
   specific probe/module order); consider whether the driver is meant to be a
   *module* loaded after AIM init (check the firmware init scripts for an
   `insmod` of the NIC driver — if present, load order under QEMU differs).
2. **Legacy SMC flash dependency.** Boot logs `SPI Flash ID : 0x0 / This flash
   type [0x0] doesn't support now` — the vendor `ast2050_smc` driver reads the
   flash ID from the legacy SMC controller at **0x16000000** (which this
   AST2400-based machine does NOT model — reads return 0 via
   ignore_memory_transaction_failures). If AIM init loads its component
   registry/config from the SPI flash, the flash failure leaves the AIM global
   sub-structures NULL. → Model the legacy AST2050 SMC controller (regs at
   0x16000000, flash window at 0x10000000/0x14000000, a real JEDEC ID) as a
   QEMU device on `kgpe-d16-bmc`; this is the most likely single faithful fix and
   also removes the ast2050_smc_init abort that `ignore_memory_transaction_
   failures` currently papers over.
3. **`0xa5768` semantics.** Disassemble `0xa5768` — confirm it stores a non-NULL
   struct to `*0xc03523a4` and what it depends on (a `kmalloc`, a device handle,
   or a hardware read). Trace what fills `AIM_global[+20]` and `[+20][+56]`.

## Faithful-fix candidates (not firmware patches)

- Model the **legacy SMC** (hypothesis 2) — most promising; self-contained QEMU
  device work; also lets the *unpatched* kernel read its flash.
- Model the **I2C MAC device** at the address `0x1a8354` decodes from `0x24008`
  (removes the need for `patch-c410x-mac.py`).
- If ordering (hypothesis 1) — arrange for the NIC driver to init after AIM (e.g.
  match the vendor's module-load order), no binary patching.

## Repro / acceptance

`web-test.py --qemu … --flash <flash-patched.img>` boots and polls the forwarded
port; today it returns FAIL (no eth0). Success = an HTTP response from appweb.
`patch-c410x-mac.py` + `build-c410x-initramfs.py` + `mkflash-c410x.py` assemble
the current best boot (firmware fully up, MAC set, eth0 pending on the above).
