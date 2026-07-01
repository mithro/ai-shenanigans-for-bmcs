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
is referenced by a **direct literal** in exactly **2** places (verified by
scanning the image for the 4-byte constant `0xc03523a4`):
- `0x139be8` — the reader (`0x1399a8`).
- `0x139d84` — a **cleanup/release**, NOT a setter. Traced `0xa5768`
  (`0xc001a374 = bl 0xa5768`): it takes `(r0=&global, r1=refcount_ptr)`, does
  `spin_lock (0x30c60); [r1]--; r5=*global; if [r1]==0 *global=0; spin_unlock
  (0x30ba0); if r5!=0 { *(r5+0x64)=0; bl 0x9e060 /*free*/ }`. i.e. a
  down/refcount-release helper. **So neither direct reference WRITES the global.**

**Key correction:** the AIM global must therefore be set via a **computed
address** (a base struct pointer + `0x3a4`), so a plain literal scan misses it.
Next: find the base — e.g. the AIM subsystem struct that lives at
`0xc0352000`(±) and is written during an AIM `initcall`; search for `str rX,
[rBASE, #0x3a4]` or an `add rX, rBASE, #0x3a4` near an AIM init. Alternatively
set a QEMU watchpoint on physical addr of `0xc03523a4` (virt−0xC0000000 =
`0x3523a4`) and see which code writes it (or confirm nothing does → the field is
only ever populated in the *NCSI* probe path, which the Dell build takes on real
HW but which fails silently under QEMU — see hypothesis 1/2).

Also note a **second, non-fatal** `0x1399a8` call at `0xc001a810`
(`r1=292 / 0x124`, result -> `[r4+0x104]`) — only logs, doesn't gate eth0.

## RUNTIME FINDINGS (gdb-multiarch hardware watchpoint) — corrects the above

Technique (works despite MMU: QEMU matches watchpoints by *virtual* address):
`qemu … -S -gdb tcp::11234`, then `gdb-multiarch -batch`:
`set architecture arm; target remote :11234; watch *(unsigned int*)0xc03523a4`,
with `commands` that dump `$pc/$sp` + `x/24xw $sp` on the non-zero write.

Results:
- Two writes to the fc pointer `0xc03523a4`: (1) value 0 at pc `0xc000813c`
  (BSS clear, early), (2) value **0xc5793220** at pc `0xc00ad6fc`.
- pc `0xc00ad6fc` = **`0xa56fc`**: the store `streq r5,[r4]` at `0xa56f8` inside
  **`0xa5678`** — a **lazy get-or-create singleton getter**: `lock; if [fc]==0 {
  alloc (bl 0x87cd8); [fc]=new }`. So the fc IS created, not perpetually null.
- The getter's return address on the stack is **`0x1399e8`** — i.e. the reader
  `0x1399a8` itself calls `bl 0xa5678` at `0x1399e4` to create/get the fc, THEN
  (`0x1399fc+`) re-reads and checks `[fc]`, `[fc+20]`, `[[fc+20]+56]`.
- The fc-create fires BEFORE `Set MAC0` (serial only at "Machine: ASPEED-AST2050").

**So the `-EFAULT` is NOT "fc is null".** The fc exists; the failure is
`[fc+0x20]==0` or `[[fc+0x20]+0x38]==0` — the fc's **sub-structure chain is not
populated** under QEMU. Something that runs on real HW to fill `fc->field20`
(and its `+0x38` field) does not run / fails under QEMU.

### RESULT: fc+0x20 is an empty list_head; nothing registers into it

Watchpoint on `fc+0x20` (0xc5793240, deterministic boot) caught exactly TWO
writes: `0` (pc 0xc016eeb0, alloc-zero) then `0xc5793240` (pc **0xc00a5970**) —
the value equals the field's own address, i.e. `INIT_LIST_HEAD(&fc->list)`.
**No third write** → the list stays EMPTY through the ftgmac probe. The reader
does `r1=[fc+0x20]` (=self for an empty list) then `r6=[r1+0x38]` = `[fc+0x58]`
=0 → `-EFAULT`. So eth0 fails because **no AIM component has registered an entry
into `fc->list` yet** when the built-in ftgmac driver probes.

This matches the userspace symptom `waitforsm: aim_config_get_int failed, SM did
not start`: the whole AESS framework is only partially up under QEMU. The list is
populated on real HW by an AESS component (one of the `aess_*.ko` set, or a
built-in init) that either doesn't run early enough or fails on a missing AST2050
device (video engine, KCS, PECI, fan/PWM sensors, legacy SMC flash, crypto…).
**This is the "near-complete AST2050 peripheral emulation" C4 always required:**
faithful completion = model the AST2050 blocks the AESS framework depends on so
its init runs and registers into `fc->list` before the ftgmac probe. Trace the
registrant by watching for the (absent) 3rd write to `fc+0x20` under a *fuller*
peripheral model, or find the `list_add(&fc->list, …)` call site statically.

### (superseded) trace who populates fc->field20 (+0x38)
The fc is a heap object (address varies per boot, e.g. 0xc5793220). Set a
watchpoint on `fc+0x20` after the create: break at `0xa56f8` (create), read
`$r5` (=fc), then `watch *(unsigned int*)($r5+0x20)` and continue to find the
writer. That writer is the AIM component whose (missing) hardware dependency is
the true C4 root cause — model that device (faithful fix), or, if it is a
pure-software init that merely needs to run, ensure its initcall/module runs
before the ftgmac probe.

## Eliminations (narrow the faithful-fix target)

- **Legacy SMC flash is NOT the cause of the eth0/AESS failure.** `SPI Flash ID :
  0x0` prints AFTER `Set MAC0 Address` (the ftgmac probe) in the boot log, so the
  flash-driver init runs *after* the AESS failure that blocks eth0. (Modelling the
  SMC is still worthwhile for the *unpatched* kernel, but it won't register eth0.)
- **No AESS registrant is visible before the ftgmac probe.** The boot log between
  `Machine: ASPEED-AST2050` and `Set MAC0` shows only standard subsystems
  (Security/LSM, NET family 16/2, TCP, squashfs/JFFS2/fuse, io-sched, MTD, serial,
  RAMDISK/loop/nbd). So whatever populates `fc->list` is an **invisible very-early
  `__initcall`** (core_initcall/arch level) inside the AESS core — it emits no
  console output. That AESS-core init is the true target: find it (search the
  `.initcall*.init` sections for a fn that calls the getter `0xa5678` + a
  `list_add` writing `fc+0x20`/`fc+0x24`), determine its hardware dependency, and
  model that device. This is the faithful fix; it is deep because the AESS core is
  proprietary and silent.

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
