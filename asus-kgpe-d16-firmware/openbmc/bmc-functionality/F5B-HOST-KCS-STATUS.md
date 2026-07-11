# F5b — Host-side IPMI over LPC KCS (local host <-> BMC channel)

Sibling of F5 (which proved the **remote** half: `netipmid` RMCP+/LAN, in QEMU
*and* on the real AST2050 at 64 MB). This task delivers the **local** half — a
host OS/BIOS talking IPMI to the BMC over the AST2050 **LPC KCS** interface on the
same board — and honestly bounds how far a BMC-only QEMU machine can carry it.

Branch `claude/bmc-f5b-hostkcs` (off `claude/bmc-functionality`).

---

## 1. Ground truth — the AST2050 LPC KCS (datasheet + models)

**LPC controller @ `0x1E789000`**, IRQ = **VIC #8** (AST2050/AST1100 A3 datasheet
§30 p.311, §10 Table 36 p.99; distilled in
`qemu-model/peripherals/lpc/DATASHEET-LPC.md`). "The definition of BMC related
registers, from offset 0x00 to 0x7C, are basically compatible with … H8S/2168"
(datasheet p.312) — so the KCS programming model is **H8S/2168**, three channels,
each an **IDRn / ODRn / STRn** register triple plus a host I/O-address register:

| Channel | IDR (host->BMC) | ODR (BMC->host) | STR (status, RO) |
|--|--|--|--|
| 1 | 0x24 | 0x30 | 0x3C |
| 2 | 0x28 | 0x34 | 0x40 |
| 3 | **0x2C** | **0x38** | **0x44** |

**These offsets are identical on the AST2400 (G4).** Mainline
`drivers/char/ipmi/kcs_bmc_aspeed.c` (v6.6.70) defines `LPC_IDR1=0x024 …
LPC_STR3=0x044` — byte-for-byte the AST2050 layout. So **channels 1-3 need no
G3-specific driver**: the AST2400 KCS driver *is* the AST2050 KCS driver for these
channels. Channel enable is `HICR0` (bit7 `LPC3E` for ch3); `HICR4` bit2 `KCSENBL`
selects KCS (vs BT) on channel 3; `LADR3H/L` (0x14/0x18) set the host I/O port.

**BT is different, and is NOT usable via mainline on the G3.** On the AST2050 the
IPMI **BT** block is at offsets **0x48-0x68** (H8S layout, datasheet p.316-318),
but mainline's `aspeed,ast2400-ibt-bmc` / `bt-bmc.c` hardcode the AST2400 **0x140**
offset. `0x140` is beyond the G3 SoC's LPC register file (the QEMU model window is
`0x00-0x9F`, `ASPEED_LPC_AST2050_NR_REGS = 0xA0/4`) and unimplemented on real
AST2050 silicon. **=> KCS is the only mainline-drivable host-IPMI channel on this
SoC.** (A faithful G3 `bt-bmc` at 0x48-0x68 would be a separate driver + model
effort; out of scope here.)

### What the QEMU model implements (`qemu/hw/misc/aspeed_lpc_ast2050.c`)

A **register-file** model at the G3 layout: HICR/LADR/KCS-data registers are RW;
the KCS **status** registers STR1-3 are **read-only** (reset 0); `LADR12L` resets
to `0x60`; accesses are **4-byte only** (`valid.min/max_access_size = 4` — the APB
register file is 32-bit-wide, matching the DTS `reg-io-width = <4>`). It is
instantiated as `lpc-g3` / `TYPE_ASPEED_LPC_AST2050` in `hw/arm/aspeed_ast2400.c`,
MMIO-mapped at `0x1E789000`, single IRQ -> VIC #8. It does **not** implement the
KCS OBF/IBF state machine or an LPC host peer — see §5 (M2).

---

## 2. The gap, and the fix (this branch)

The KGPE-D16 DTB inherited `lpc@1e789000` from `aspeed-g4.dtsi` with only
`lpc-ctrl` / `lpc-snoop` children — **no KCS node** — so the kernel bound no KCS
driver and created no `/dev/ipmi-kcs*`. And the built kernel had
`CONFIG_IPMI_KCS_BMC_CDEV_IPMI` **off** (the KCS core + aspeed driver were on, but
not the char-device client), so even a bound channel would expose no `/dev` node.

**Two changes:**

1. `qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts` — add the KCS channel-3 node:
   ```dts
   &lpc {
       kcs3: kcs@2c {
           compatible = "aspeed,ast2400-kcs-bmc-v2";
           reg = <0x2c 0x1>, <0x38 0x1>, <0x44 0x1>;   /* IDR3 / ODR3 / STR3 */
           aspeed,lpc-io-reg = <0xca2>;                /* IPMI SMS system interface */
           interrupts = <8>;                           /* LPC = VIC #8 */
           status = "okay";
       };
   };
   ```
2. `qemu-firmware/kernel/kgpe-d16.config` — add `CONFIG_IPMI_KCS_BMC_CDEV_IPMI=y`
   so the driver creates `/dev/ipmi-kcs3`.

Channel 3 / port `0xca2` is the classic IPMI **SMS "system interface"** (data
`0xca2`, status+command `0xca3`) — the OpenBMC convention for the host-IPMI KCS.

---

## 3. QEMU demonstration — M1 (BMC-side channel alive)

`f5b-host-kcs-test.py` boots the D16 kernel + BusyBox initramfs on the faithful
`kgpe-d16-bmc` machine **at the real 64 MB DRAM size**, SSHes in, and collects the
evidence below (full capture in `evidence/host-kcs/host-kcs.txt`).

```
# uname
Linux kgpe-d16-bmc 6.6.70-dirty ... armv5tejl GNU/Linux

# /dev node created by the kernel
crw-------  1 root root 10, 127  /dev/ipmi-kcs3

# device-tree node
path=/sys/firmware/devicetree/base/ahb/apb/lpc@1e789000/kcs@2c
compatible=aspeed,ast2400-kcs-bmc-v2   status=okay
reg= 00 00 00 2c  00 00 00 01  00 00 00 38  00 00 00 01  00 00 00 44  00 00 00 01

# driver bound (ast-kcs-bmc holds the device)
/sys/bus/platform/drivers/ast-kcs-bmc/1e78902c.kcs
    -> .../1e789000.lpc/1e78902c.kcs

# kernel log
ast-kcs-bmc 1e78902c.kcs: Initialised IPMI client for channel 3
ast-kcs-bmc 1e78902c.kcs: Initialised channel 3 at 0xca2

# BMC-side reads of the LPC registers the driver programmed in the faithful model
HICR0 (0x1e789000) = 0x00000080   -> bit7 LPC3E  : channel 3 enabled
HICR4 (0x1e789010) = 0x00000004   -> bit2 KCSENBL: KCS mode on channel 3
LADR3H(0x1e789014) = 0x0000000C   \  0x0CA2 = host I/O port 0xca2
LADR3L(0x1e789018) = 0x000000A2   /
STR3  (0x1e789044) = 0x00000000   -> KCS status read-only (model keeps it 0)

# from-BMC-side KCS poke: write ODR3, read it back (Slave-RW output register)
devmem 0x1e789038 32 0x5a ; devmem 0x1e789038 32  -> 0x0000005a
```

**PASS gate (all met):** `/dev/ipmi-kcs3` present **and** `ast-kcs-bmc` bound to
`kcs@2c` **and** `HICR0.LPC3E` set (the driver drove the faithful model) **and**
the BMC-side ODR3 poke reads back — all at **64 MB**.

This proves the **complete BMC-side host-IPMI KCS channel** against the faithful
G3 LPC model: the mainline driver probes the DTS node, creates the char device the
OpenBMC host-IPMI bridge opens, and every register access it issues is serviced by
the model exactly as the datasheet specifies (channel-enable, KCS-mode, host-port,
read-only status, RW output register, 32-bit APB access width).

---

## 4. OpenBMC daemon layer — honest status (F-IMG2 follow-up)

The complete host path is:
```
host --LPC I/O--> KCS (/dev/ipmi-kcs3) --> kcsbridge (org.openbmc.HostIpmi)
                                       --> ipmid (same D-Bus command router as netipmid)
```
The BMC-side command handling is **identical to LAN** — once a KCS bridge opens
`/dev/ipmi-kcs3` and feeds `ipmid`, every command F5 proved over LAN also answers
the host. `ipmid` (`phosphor-ipmi-host`) is present in the F0 image and proven up
by F5 over LAN.

**But the staged F0 image ships the host-IPMI *BT* bridge (`btbridged`), not the
KCS bridge (`kcsbridge`)** — `/export/openbmc-full/usr/bin/` has `btbridged` and no
`kcsbridge`/`phosphor-ipmi-kcs`. This is the known `BUILD-NOTES.md` note 1: the
runtime provider knob (`PREFERRED_RPROVIDER_virtual-obmc-host-ipmi-hw`) defaulted
to the quanta-q71l BT choice. And per §1, **BT can't be faithfully wired on the G3
anyway** (0x140 vs 0x48). So today no userspace daemon binds `/dev/ipmi-kcs3`.

Per this task's guidance, that is **documented as an F-IMG2 follow-up, not a
rebuild here**: switch the image to `kcsbridge` with the one-line
`local.conf` knob already staged in BUILD-NOTES, then unmask
`phosphor-ipmi-kcs@...` / wire it to `/dev/ipmi-kcs3`. `ipmid` is unchanged. This
is a ~5-min cached OpenBMC rebuild owned by the image task, and needs no model,
DTS, or kernel change beyond what this branch lands.

---

## 5. M2 — full host <-> BMC round-trip (the honest boundary)

Exchanging a real IPMI *message* over KCS needs something driving the **host** (LPC
I/O-port) side of the channel. The `kgpe-d16-bmc` machine models **only the BMC**:
there is no host CPU, and the LPC model is a register file with **no OBF/IBF
handshake state machine**. Concretely, if a test writes `IDR3` from the AHB/BMC
side (e.g. via `devmem` or the P2A/iLPC backdoor), the model just stores the byte;
it does **not** set `STR3.IBF`, so the kernel's KCS driver — which waits on IBF —
never sees a "host" byte. A from-AHB poke therefore cannot carry a KCS transaction
through the current model, and **faking one would misrepresent the hardware**.

A genuine host<->BMC KCS round-trip in QEMU needs **either**:
- (a) extend `aspeed_lpc_ast2050.c` with the KCS **OBF/IBF/C-D state machine** plus
  a host-side back-channel a test can drive as the LPC peer (a faithful model
  refinement the model header already flags), **or**
- (b) a paired host-CPU QEMU machine / **real silicon**, where the powered host is
  the KCS peer.

Delivered here is the honest **M1** bar (option (b) of the task brief): device
present + driver bound + faithful model serviced the driver **and** a from-BMC-side
KCS register poke — without a fabricated host transaction.

---

## 6. Real-hardware status (deferred to F-HWPASS)

On real silicon the **host CPU (when the KGPE-D16 is powered on) is the KCS peer**,
so the real-HW demo is a full host-side `ipmitool`:
- from the running host OS: `ipmitool -I open` (host talks to its BMC), or
- from the BMC side: `ipmitool -I kcs` against `/dev/ipmi-kcs3`.

This depends on the **host being powered** (ties to F2) and on the OpenBMC image
shipping `kcsbridge` (§4). It is **non-disruptive-only** and must be coordinated on
the Pi's `HARDWARE-COORDINATION.md`; the consolidated real-HW boot (F-HWPASS) can
add a host-side KCS check once the host is up. Not run in this task.

Note the DTS/kernel changes here are the **same artifacts** used on the real board
(the KGPE-D16 DTB + kernel), so the `/dev/ipmi-kcs3` channel proven in QEMU is
exactly what appears on silicon; only the host-side peer differs.

---

## 7. Files

- `qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts` — `&lpc/kcs@2c` node (added).
- `qemu-firmware/kernel/kgpe-d16.config` — `CONFIG_IPMI_KCS_BMC_CDEV_IPMI=y` (added).
- `openbmc/bmc-functionality/f5b-host-kcs-test.py` — the QEMU M1 test.
- `openbmc/bmc-functionality/evidence/host-kcs/host-kcs.txt` — captured evidence.
- `.github/workflows/d16-qemu-stack.yml` — `host-kcs` CI job (device + driver + model poke).
