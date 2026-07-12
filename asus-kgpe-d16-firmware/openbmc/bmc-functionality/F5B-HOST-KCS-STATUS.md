# F5b — Host-side IPMI over LPC KCS (local host <-> BMC channel)

Sibling of F5 (which proved the **remote** half: `netipmid` RMCP+/LAN, in QEMU
*and* on the real AST2050 at 64 MB). This task delivers the **local** half — a
host OS/BIOS talking IPMI to the BMC over the AST2050 **LPC KCS** interface on the
same board.

- **M1** (branch `claude/bmc-f5b-hostkcs`): the BMC-side channel is alive — DTS
  `kcs@2c` → `/dev/ipmi-kcs3` → `ast-kcs-bmc` bound → faithful G3 LPC model
  serviced the driver. See §3.
- **M2** (branch `claude/bmc-kcs-m2`, 2026-07-12): a **genuine host->BMC IPMI Get
  Device ID transaction** over the KCS channel, answered by `ipmid` — enabled by
  a faithful KCS OBF/IBF/C-D state machine + an honest QOM host-drive back-channel
  added to the QEMU G3 LPC model. See §5.

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
host --LPC I/O--> KCS (/dev/ipmi-kcs3) --> kcsbridged (phosphor-ipmi-kcs@ipmi-kcs3)
                                       --> ipmid (same D-Bus command router as netipmid)
```
The BMC-side command handling is **identical to LAN** — once the KCS bridge opens
`/dev/ipmi-kcs3` and feeds `ipmid`, every command F5 proved over LAN also answers
the host. `ipmid` (`phosphor-ipmi-host`) is present in the image and proven up by
F5 over LAN **and now by M2 over KCS** (§5).

**Resolved (F-HWPASS merge).** The earlier F0 image shipped the host-IPMI *BT*
bridge (`btbridged`); the current image recipe installs **`kcsbridge`**
(`phosphor-ipmi-kcs`, with `phosphor-ipmi-bt` removed) — the correct choice per
§1 (BT is unfaithful on the G3: 0x140 vs 0x48). The staged
`/export/openbmc-hwpass` (`= Pi:/srv/nfs/openbmc-hwpass`) has
`/usr/libexec/kcsbridged` and `phosphor-ipmi-kcs@ipmi-kcs3.service` enabled in
`multi-user.target.wants`. M2's transaction test boots exactly this image and
confirms both `phosphor-ipmi-kcs@ipmi-kcs3` and `phosphor-ipmi-host` go active
and answer a host Get Device ID. No model/DTS/kernel change beyond this branch.

---

## 5. M2 — full host <-> BMC round-trip (DELIVERED 2026-07-12)

M1 left the honest boundary: a real IPMI *message* over KCS needs something
driving the **host** (LPC I/O-port) side, and the old LPC model was a register
file with **no OBF/IBF handshake**. That gap is now closed by extending the
faithful G3 model (option (a) of the task brief) — **not** by faking a host
transaction from the AHB side.

### 5.1 The faithful KCS state machine (`hw/misc/aspeed_lpc_ast2050.c`)

Implemented the H8S/2168-style handshake exactly as the STR1-3 access tables
specify (AST2050 A3 datasheet V1.05, **p.313-316**; the "defined by user" note is
p.315):

| Event | Model effect | Datasheet basis |
|--|--|--|
| host write to IDRn (data/cmd port) | IDRn latched, `STRn.IBF`=1, `C/D` = port | IDRn Host-W (p.315); STR bit1 IBF, bit3 C/D (p.315-316) |
| BMC read of IDRn | `IBF`=0 (receive completion) | IDRn Slave-R; IBF Slave-R hardware-managed |
| BMC write to ODRn | `STRn.OBF`=1 | ODRn Slave-RW (p.315); STR bit0 OBF |
| host read of ODRn (data port) | `OBF`=0 | ODRn Host-R; OBF Host-R |
| BMC write to STRn | bits 7:4,2 (DBU) set, `OBF` RW0C, `IBF`/`C/D` ignored | STR Slave access: DBU RW, OBF RW0C, IBF/C-D R (p.315-316) |
| BMC write to IDRn | dropped | IDRn is Slave-**R** / Host-W (p.315) |

`IBF` asserts the LPC line to **VIC #8** (high-level sensitive, §10 Table 36 p.99)
while the channel is enabled (HICR0 `LPCnE`; + HICR4 `KCSENBL` for ch3, p.313-314)
and its HICR2 `IBFIFn` receive-completion interrupt is enabled (p.313); a BMC IDRn
read deasserts it. There is **no OBE interrupt** on this silicon (the mainline
`kcs_bmc_aspeed` driver polls STR.OBF via a timer), so none is modelled — that
absence is itself faithful.

### 5.2 The honest host-drive back-channel

The `kgpe-d16-bmc` machine has no host CPU, so the **host half** of each channel
(the LPC I/O cycles a real BIOS/OS issues at the `LADRn` port pair) is exposed as
QOM properties on `/machine/soc/lpc-g3` — the same technique mainline
`hw/misc/aspeed_lpc.c` already uses to expose its KCS registers to tests, but
modelling the host's **two I/O ports** so the command/data (`C/D`) distinction a
real IPMI KCS transaction depends on is preserved:

| Property | Host operation modelled |
|--|--|
| `host-kcs<N>-data`   write | OUT to the KCS **data** port → IDRn, IBF=1, C/D=0 |
| `host-kcs<N>-data`   read  | IN from the **data** port → ODRn (clears OBF) |
| `host-kcs<N>-cmdsts` write | OUT to the KCS **command** port → IDRn, IBF=1, C/D=1 |
| `host-kcs<N>-cmdsts` read  | IN from the **status** port → STRn |

**Why this is honest:** the properties replace **only the physical LPC bus wires**
— nothing else. Every state transition they cause is the datasheet state machine
in §5.1; the BMC-visible side (IDR/ODR/STR MMIO, the VIC #8 IRQ) is unchanged real
silicon behaviour. Driving a channel the BMC has not enabled **fails loudly**
(`error_setg`), because on real hardware an unclaimed LPC I/O cycle is simply not
answered. This is the documented model refinement the header always flagged, now
built.

### 5.3 End-to-end demo — genuine host->BMC Get Device ID

`f5b-kcs-m2-transaction-test.py` boots the OpenBMC stack (the F-HWPASS image that
ships `kcsbridge` wired to `/dev/ipmi-kcs3`) over NFS on `kgpe-d16-bmc` **at
64 MB**, waits for `phosphor-ipmi-kcs@ipmi-kcs3` + `phosphor-ipmi-host` (ipmid) to
go active, then plays the **host** side of the IPMI v2.0 KCS SMS transfer flow
(§9.15) against port pair `0xca2/0xca3` and sends **Get Device ID** (netfn `0x06`,
cmd `0x01`) entirely through the QOM back-channel (one `qom-set` = one host OUT
cycle, one `qom-get` = one host IN cycle).

The full path exercised — **nothing on the BMC side is scripted**:

```
test (IPMI KCS host protocol, QMP = LPC wires)
  -> aspeed_lpc_ast2050 KCS state machine (IDR3/ODR3/STR3, VIC #8 IRQ)
    -> kernel kcs_bmc_aspeed / kcs_bmc_cdev_ipmi   (/dev/ipmi-kcs3)
      -> kcsbridged (phosphor-ipmi-kcs@ipmi-kcs3)   (D-Bus)
        -> ipmid (phosphor-ipmi-host)  = THE ANSWERING LAYER
      <- response bytes flow back through ODR3/OBF, one KCS READ cycle each
```

Captured result (QEMU, 64 MB, 2026-07-12; transaction wall time 3.8 s on the
emulated ARM926):

```
request  (host->BMC): 18 01          = netfn 0x06 (App) lun 0, cmd 0x01
response (BMC->host): 1c 01 00 01 01 00 00 02 8f 3f 0a 00 16 0d 00 00 00 00
  netfn 0x07 (App response), cmd 0x01, cc 0x00
  device_id 0x01  device_rev 0x01  fw_rev 0x00/0x00  ipmi_version 0x02 (2.0)
  additional_dev_support 0x8f
  manufacturer IANA 0x000a3f = 2623 = ASUSTeK   <- the image's dev_id.json
  product_id 0x0D16 = the KGPE-D16 board ID     <- (F-HWPASS populated IDs)
```

The byte trace (`evidence/host-kcs-m2/host-byte-trace.txt`) shows every LPC I/O
cycle and STR poll: `WRITE_START(0x61)` → per-byte IBF handshakes in WRITE state
→ `WRITE_END(0x62)` + last byte → state READ → 18 response bytes each pulled
through **OBF** with a `KCS_READ(0x68)` ack → state IDLE + dummy byte. The first
response byte appeared after ~178 status polls (~4 s) — that is `ipmid` actually
computing the answer. BMC-side journal (`evidence/host-kcs-m2/bmc-journal.txt`):
`Started Phosphor IPMI KCS DBus Bridge` (`Active: active (running)`,
`/usr/libexec/kcsbridged -c ipmi-kcs3`), `ipmid: New interface mapping:
xyz.openbmc_project.Ipmi.Channel.ipmi_kcs3 -> channel 15`, and `kcsbridged`
holding fd `8 -> /dev/ipmi-kcs3` at capture time. At transaction time ipmid logs
`No Object has implemented the interface: xyz.openbmc_project.State.BMC, NetFn:
0x6, Cmd: 0x1` (+ a `map::at` line) — its lookup of the BMC-state object for the
fw-rev "device available" bit, which is why `fw_rev1` bit7 can read 0x80 (busy)
on a boot where that query lands differently; the reply is complete and correct
either way.

A well-formed reply **cannot** be synthesised by the KCS char-device path on its
own (the kernel cdev only relays request bytes to userspace and returns the
userspace-supplied response), and the ASUSTeK/0x0D16 payload matches the image's
`dev_id.json` — so **`ipmid` answered**.

**Which bar:** the top bar — a real `ipmid` answered over the faithful KCS state
machine, not the kernel-only fallback.

### 5.4 Model-level test

`qemu-model/integration/test_lpc.py::TestKCS3HostHandshake` drives the same state
machine with no kernel — BMC side over qtest MMIO, host side over the QMP QOM
ports — and asserts every transition in the §5.1 table plus the VIC #8 line
(via the G3 VIC raw-status register). Runs in <1 s in CI.

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
exactly what appears on silicon; only the host-side peer differs. In QEMU the
peer is the faithful KCS state machine driven through the QOM back-channel (§5);
on silicon it is the real host CPU. Both exercise the identical BMC-side path
(model → `kcs_bmc_aspeed` → `kcsbridged` → `ipmid`), so the M2 demo is the same
transaction a powered host will run — with the LPC bus wires standing in for the
one piece the BMC-only machine cannot have.

---

## 7. Files

- `qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts` — `&lpc/kcs@2c` node (added).
- `qemu-firmware/kernel/kgpe-d16.config` — `CONFIG_IPMI_KCS_BMC_CDEV_IPMI=y` (added).
- `qemu-firmware/qemu/qemu/hw/misc/aspeed_lpc_ast2050.c` — the faithful KCS
  OBF/IBF/C-D state machine + `host-kcs<N>-{data,cmdsts}` QOM host ports (M2).
- `openbmc/bmc-functionality/f5b-host-kcs-test.py` — the QEMU **M1** test.
- `openbmc/bmc-functionality/f5b-kcs-m2-transaction-test.py` — the **M2**
  host->BMC Get Device ID transaction test (ipmid answers over KCS).
- `openbmc/bmc-functionality/f5_masked_daemons.py` — adds the `kcs` 64-MB profile.
- `openbmc/bmc-functionality/evidence/host-kcs/host-kcs.txt` — M1 evidence.
- `openbmc/bmc-functionality/evidence/host-kcs-m2/{host-byte-trace,bmc-journal}.txt`
  — M2 evidence (host I/O cycle trace + BMC-side journal).
- `qemu-model/integration/test_lpc.py` — `TestKCS3HostHandshake` (qtest+QMP model test).
- `.github/workflows/d16-qemu-stack.yml` — `host-kcs` job (M1 + model test) and
  `host-kcs-m2` job (the full transaction; graceful-skip if the kcsbridge rootfs
  asset is unpublished).
