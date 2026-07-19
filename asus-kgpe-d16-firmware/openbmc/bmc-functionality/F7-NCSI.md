# F7 — "Piggybacking on the host's network interface" (NC-SI): ground truth

**Board:** ASUS KGPE-D16, Aspeed **AST2050** (G3) BMC.
**Feature as requested:** *"Piggybacking on the host's network interface"* — classically
**NC-SI** (Network Controller Sideband Interface): the BMC shares the *host's* NIC
over a sideband channel instead of having its own PHY.

> 🛑 **RETRACTED / SUPERSEDED (2026-07-18, reaffirmed 2026-07-19). NC-SI IS WIRED
> ON THIS BOARD.** The authoritative schematic (`AST2050-BMC-WIRING.md` §7 +
> `pinmaps/QU1_pins.md`) shows the AST2050 **MAC2 RMII2 sideband** (A5/B5/B6/C4/D4/
> D5) bussed to *both* Intel 82574L host NICs (LU1/LU2) — the classic NC-SI
> topology. Every statement in the body below that says NC-SI is "not wired",
> "absent", or "does not exist on this board" is **WRONG** and applies at most to
> **MAC channel 1** (the dedicated management PHY). The body is kept for its
> MAC1/register detail but is **not** the board verdict. The correct, authoritative
> status lives in **D07** (DEVICE-MATRIX.md row 11 / FULL-TASK-LIST.md C2): NC-SI
> QEMU-modeled ✅, silicon hard-but-not-blocked. Do not cite this doc's "absent"
> language.

**Bottom line (faithfulness first — MAC1-scoped, see correction):**

> **The KGPE-D16 BMC does NOT use NC-SI.** It has its **own dedicated Ethernet PHY
> (RTL8201CP) on an RMII link**, with its own MAC address and its own IP
> (`192.168.66.2` on real HW), sitting on the **same physical Ethernet segment** as
> the host's NICs. NC-SI sideband is **not wired on this board.**
>
> NC-SI *is* a capability of the AST2050 **SoC**, but only as a **software protocol
> running over the RMII link** (Aspeed's `ncsi_protocol.ko` / vendor `aspeednic`),
> gated by a **software scratch-register hint** — it is **not a MAC hardware feature**
> and there is **no NC-SI register block** in the G3 MAC. A *different* board that uses
> the same SoC — the **Dell C410X** — is where the vendor stack takes an NC-SI path.

This document establishes that ground truth with datasheet + Raptor + firmware
citations, states the honest engineering path taken, and records the QEMU
demonstration of what the board *actually* does.

---

## ⚠️ 2026-07-18 CORRECTION — the "not wired" verdict was MAC1-scoped; MAC2's NC-SI sideband IS wired (REOPENED as D07)

A netlist-level schematic trace
(`../../schematic-wiring/AST2050-BMC-WIRING.md` §7) shows this document's
board-wide conclusion **"NC-SI sideband is not wired on this board" is WRONG for
MAC channel 2**. Every piece of §1's evidence (DTS `&mac0`, Raptor
`CONFIG_MAC1_PHY_SETTING`, the Redfish `"Physical"` interface) is **MAC1/mac0**
evidence; nothing in it examined the second channel's balls. The schematic does:

* **RMII2 balls A5/B5 (RXD0/RXD1), B6 (CRSDV), C4/D4 (TXD0/TXD1), D5 (TXEN)
  bus to BOTH Intel 82574L host NICs (`LU1` = LAN1, `LU2` = LAN2)** as a
  **multi-drop sideband** — exactly the classic NC-SI topology this document
  said the board did not have. (`RMII2RXER` is unconnected.)
* The **50 MHz RMII reference clock is sourced externally by the board clock
  generator `CU2`** (nothing for the BMC — or a QEMU model — to generate).
* **LU1/LU2 are powered from `+3V3_AUX`** (netlist trace:
  `../../schematic-wiring/I2C-MUX-FABRIC-ARBITRATION.md` §5), so the sideband is
  electrically alive — and testable — **with the host powered off**.

**Status: the "architecturally ABSENT / not wired on this board" verdict is
REOPENED as task D07** (`../../device-driver-program/TASKLIST.md` § D07):
QEMU MAC2 + NC-SI-responder 82574L model, Linux `net/ncsi` bring-up (DTS mac2
node currently `status="disabled"`, no `use-ncsi`; `CONFIG_NET_NCSI` not built —
recipe in §6 below), then silicon validation. **Implementation has not started.**
`SILICON-STATUS.md` #9 is updated to match.

What in this document **remains true** (the correction does not touch it):

* **MAC1 is a dedicated-PHY management port** (RTL8201-family PHY at `U5`) —
  all of §1 stands, *scoped to MAC1*. (Note the schematic identifies `U5` as an
  **RTL8201N-GR on MII wiring**, vs this doc's RTL8201CP/RMII — a PHY-variant /
  interface-mode discrepancy tracked under task D06, not resolved here.)
* **The G3 MAC has no NC-SI hardware block** — NC-SI is a software protocol over
  an ordinary RMII link (§2–§3). The schematic finding changes *which board
  wiring exists* for that software to run over, not the SoC facts.
* **SCU40[15:14] (and [13:12] for MAC2) are software scratch hints, not hardware
  straps** (§2). Raptor sets `CONFIG_MAC2_PHY_SETTING 0` too — the vendor
  firmware did not *use* the ch.2 sideband, but non-use is not non-wiring.

The historical analysis below is kept intact, annotated
`⚠️ [MAC1-scoped — see 2026-07-18 correction]` where superseded.

---

## 1. Ground truth: dedicated RTL8201CP PHY, not NC-SI ⚠️ [MAC1-scoped — see 2026-07-18 correction]

Three independent primary sources agree. NC-SI is **not** wired on the KGPE-D16.

### 1.1 The reconstructed device tree — dedicated PHY, RMII

`asus-kgpe-d16-firmware/qemu-firmware/dts/aspeed-bmc-asus-kgpe-d16.dts` (lines 154–167):

```dts
&mac0 {
	status = "okay";
	/*
	 * AST2050 (G3) MAC ... phy-mode=rmii
	 * with the real RTL8201CP PHY (no fixed-link) -- matching the real board.
	 * ...
	 */
	phy-mode = "rmii";
};
```

There is **no `use-ncsi`** property and **no NC-SI channel node**. `phy-mode = "rmii"`
with a real downstream PHY is the mainline binding for a **dedicated NIC**; the NC-SI
binding (`use-ncsi;`, and optionally `mlx,multi-host` / channel count) is absent.

### 1.2 Raptor Engineering's real KGPE-D16 U-Boot — `Dedicated PHY (not NC-SI)`

Raptor's working AST2050 port is the project's faithfulness oracle for SoC bring-up.
Its U-Boot board config selects the **dedicated-PHY** MAC mode explicitly.

`asus-kgpe-d16-firmware/ast2050.h` (lines 228–247) documents the Aspeed convention and
the KGPE-D16's choice:

```c
/*
 * NOTICE: MAC1 and MAC2 now have their own seperate PHY configuration.
 * We use 2 bits for each MAC in the scratch register (D[15:11] in 0x1E6E2040) to
 * inform kernel driver.
 * The meanings of the 2 bits are:
 * 00(0): Dedicated PHY
 * 01(1): ASPEED's EVA + INTEL's NC-SI PHY chip EVA
 * 10(2): ASPEED's MAC is connected to NC-SI PHY chip directly
 * ...
 */
#define CONFIG_MAC1_PHY_SETTING		0   // <-- 0 = Dedicated PHY
#define CONFIG_MAC2_PHY_SETTING		0
```

And the summary in `RAPTOR-UBOOT-ANALYSIS.md` (line 367) states it plainly:

```
CONFIG_MAC1_PHY_SETTING  0           // Dedicated PHY (not NC-SI)
```

So Raptor's real board sets the MAC1 PHY-mode scratch hint to **0 = Dedicated PHY**.
Not NC-SI.

### 1.3 The AST2050 datasheet — the MAC has no NC-SI hardware

`asus-kgpe-d16-firmware/qemu-model/peripherals/mac/DATASHEET-MAC.md` §5 (lines 356–391),
cross-checked against `dell-c410x-firmware/datasheets/AST2050_AST1100_A3_Datasheet_V1.05.pdf`:

> **MAC interface strap is MII/RMII-only, no NCSI mode.** SCU70[8:6] (p.218) enumerates
> *only* `011`=MII(MAC#1), `100`=RMII(MAC#1), `110`=RMII(#1)+RMII(#2), `111`=Disable —
> **there is no NC-SI hardware mode**. The G3 MAC has **no NC-SI controller / NC-SI
> register block**; NC-SI on this SoC would be pure software over an RMII link (the
> vendor's `ncsi_protocol.ko`), not a MAC feature.

### 1.4 The running OpenBMC confirms it: `EthernetInterfaceType: "Physical"`

The integration branch's OpenBMC Redfish evidence
(`evidence/qemu/bmc-ethernet-iface0.json`) reports:

```json
"EthernetInterfaceType": "Physical",
```

A **Physical** interface (its own MAC/PHY), not an NC-SI-backed one. Consistent with
1.1–1.3.

---

## 2. The crucial two-register distinction (do not conflate these)

Reviewers sometimes see "NCSI" in the AST2050 SCU docs and conclude the board does
NC-SI. It does not. Two *different* SCU fields are involved and only one is a hardware
mode:

| Register | Field | Kind | Values | On KGPE-D16 |
|---|---|---|---|---|
| **SCU70** `0x1E6E2070` | **[8:6] MAC interface mode** | **Hardware strap** (`ROMA[8:6]`, p.44/218) | `011`=MII, `100`=RMII, `110`=RMII×2, `111`=Disable — **no NCSI value exists** | `100` = **RMII** |
| **SCU40** `0x1E6E2040` | **[15:14] MAC#1 PHY mode** | **Software scratch hint** (ASPEED SDK/VBIOS handshake, p.215–216) | `00`=Dedicate, `01`=NCSI EVA, `10`=Intel NCSI EVB | `00` = **Dedicated PHY** |

* **SCU70[8:6]** is the real electrical interface strap. It picks **MII vs RMII vs
  Disable**. **There is no NC-SI option in this field** — proving NC-SI is *not* a
  hardware operating mode of the G3 MAC
  (`DATASHEET-MAC.md` §5.2; `DATASHEET-SCU.md` §6, lines 395–424).
* **SCU40[15:14]** is a **software-defined scratch register** — U-Boot writes it purely
  to *tell the kernel driver* what kind of device is downstream of the RMII link
  (`ast2050.h` lines 230–247; `DATASHEET-SCU.md` §12, line 415). NC-SI, when a board
  uses it, runs entirely in **software** on top of the ordinary RMII link.

**KGPE-D16 = SCU70[8:6]=`100` (RMII) + SCU40[15:14]=`00` (Dedicated PHY) → its own
RTL8201CP PHY, no sideband.**

---

## 3. What "NC-SI on the AST2050" actually is

Because the G3 MAC has no NC-SI register block, NC-SI on this SoC is **not** hardware
offload. It is:

1. An ordinary **RMII** electrical link out of the MAC (same pins as a dedicated PHY);
2. Wired on the board to an **NC-SI-capable device** (an Intel/Broadcom host NIC's
   NC-SI channel, or an NC-SI PHY) instead of a plain PHY;
3. Driven by a **software** NC-SI protocol stack — Aspeed's vendor `aspeednic` /
   `ncsi_protocol.ko`, or mainline Linux `CONFIG_NET_NCSI` — that exchanges NC-SI
   control packets (EtherType `0x88F8`) over that link to claim a channel and learn the
   MAC address.

The KGPE-D16 does step (1) as RMII but wires it to a **dedicated PHY** (step 2 =
plain PHY), so no NC-SI software ever runs. The D16 kernel does **not** even build
`CONFIG_NET_NCSI` (verified: no `NCSI`/`NET_NCSI` symbol under
`asus-kgpe-d16-firmware/qemu-firmware/kernel/`).

### The Dell C410X contrast (same SoC, different board — do not over-claim)

The Dell C410X uses the same AST2050 but its **vendor MergePoint driver** takes a
software NC-SI path (`qemu-firmware/proprietary/README.md`: the Dell build selects the
NCSI branch and obtains its MAC that way; oemdef interface type `0x02 = INTEL_NCSI`).
Note the C410X DTS reconstruction *itself* corrected the interface from a first-guess
`use-ncsi` to `phy-mode rmii` after cross-checking U-Boot (`mac0intf=1 = RMII_PHY`,
`dell-c410x-firmware/STATUS.md`) — the RMII electrical link is shared with the NC-SI
software path. The C410X is out of scope for F7 (this is the KGPE-D16); it is cited
only to show the SoC *can* be used with NC-SI on a board that wires it that way — the
KGPE-D16 does not.

---

## 4. Honest path taken ⚠️ [MAC1-scoped — the "board not wired" premise is corrected 2026-07-18; QEMU-responder/faithfulness points still valid for MAC1]

Per the project rule (*QEMU must model the real AST2050/KGPE-D16 behaviour; the
hardware is the oracle; never fake a feature the hardware doesn't have*), the correct
deliverable is the honest combination of **(b)** reframe + **(a)** SoC-capability doc:

* **(b) Reframe "piggyback" to what the board actually does.** For the KGPE-D16,
  "sharing the host's network" means the BMC's **dedicated NIC on the same physical
  Ethernet** as the host — which is exactly the modelled and already-proven path
  (dedicated ftgmac100 + RTL PHY over RMII; DHCP; OpenBMC Redfish reachable). See §5.
* **(a) Document NC-SI as a SoC software-capability, not board-wired.** The AST2050 can
  do NC-SI *in software over RMII* (as the Dell C410X vendor stack does), enabled by
  `CONFIG_NET_NCSI` + a `use-ncsi;` DTS mac node + an NC-SI-capable link peer. On the
  KGPE-D16 this is **not wired**, so we do **not** enable it — doing so would fake a
  board feature that does not exist. See §6 for exactly what it would require.

We did **NOT** take path *(a-demo)* "bring up the BMC network over NC-SI in QEMU",
because it is unfaithful for this board **and** unsupported by the tooling:

* Our faithful G3 ftgmac100 model **correctly exposes no NC-SI hardware mode**
  (`DATASHEET-MAC.md` §5 mandates this), so there is no NC-SI mode bit to toggle.
* Our QEMU (submodule `a010d69`, `qemu-system-arm 10.0.7`) has **no NC-SI responder**:
  a tree-wide search of the QEMU source finds **zero** NC-SI handling in
  `hw/net/ftgmac100.c` (the only `ncsi` hits tree-wide are false positives in
  `backends/cryptodev.c` and an EtherType constant in `include/net/eth.h`). There is
  nothing in QEMU that would answer an NC-SI probe, so an "NC-SI comes up" demo would
  require *writing* an NC-SI responder — i.e. inventing a peer this board never talks to.

Faking NC-SI would violate faithfulness on three counts (board not wired, MAC has no
NC-SI block, no QEMU responder). The honest, evidence-backed finding **is** the
completion.

---

## 5. QEMU demonstration — the real KGPE-D16 network path (dedicated PHY)

Booted the faithful `kgpe-d16-bmc` machine (`qemu-system-arm 10.0.7`, submodule
`a010d69` — the consolidated integration QEMU with the G3 MAC + FAST_MODE fix + G3 VIC)
with the modern AST2050 kernel + BusyBox initramfs, `mem=64`,
`-nic user,model=ftgmac100,hostfwd=tcp::2222-:22`, `ip=dhcp`. The BMC's **own** NIC
comes up over the emulated RMII + MDIO PHY and joins the (slirp) network the host is on
— the true "piggyback via the board's dedicated NIC". Full log:
`evidence/qemu-ncsi/eth0-dedicated-phy-boot.log`. Key lines:

```
[    0.992603] ftgmac100 1e660000.ethernet: Read MAC address 52:54:00:12:34:56 from chip
[    1.029896] ftgmac100 1e660000.ethernet (uninitialized): Unsupported PHY mode rmii !
[    1.031110] RTL8211E Gigabit Ethernet 1e660000.ethernet--1:00: attached PHY driver
[    1.044955] ftgmac100 1e660000.ethernet eth0: irq 21, mapped at 6ffd2c71
[    1.321151] ftgmac100 1e660000.ethernet eth0: Link is Up - 100Mbps/Full - flow control rx/tx
[    1.388445] Sending DHCP requests ., OK
[    1.393881] IP-Config: Got DHCP answer from 10.0.2.2, my address is 10.0.2.15
...
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff
    inet 10.0.2.15/24 brd 10.0.2.255 scope global eth0
dropbear: listening on :22 (ssh in via the QEMU hostfwd port)
BMC-READY
```

What this proves, faithful to the board:

* The BMC has **its own MAC** read from the chip and its **own IP** via DHCP — a
  **dedicated NIC**, on the same L2 as the emulated host/slirp gateway `10.0.2.2`.
* The link is brought up via an **MDIO-attached PHY** (`attached PHY driver`) —
  the **dedicated-PHY** path. (QEMU's ftgmac100 MDIO model answers with an RTL PHY ID;
  the real board's PHY is the RTL8201CP — same *dedicated-PHY* topology, a cosmetic
  model-ID difference noted honestly.)
* **No NC-SI anywhere.** The word `ncsi`/`NCSI` never appears in the boot; there is no
  NC-SI channel probe, no `0x88F8` control exchange, no `ncsi_protocol`. The interface
  is up entirely through the dedicated PHY — direct runtime confirmation of §1–§3.

The existing OpenBMC-over-NFS run on this same machine goes further (bmcweb answers
Redfish over this dedicated NIC; `evidence/qemu/service-root.json`,
`bmc-ethernet-iface0.json` `"EthernetInterfaceType":"Physical"`). CI job
`d16-qemu-stack.yml :: boot-nfsroot` already exercises this eth0-up-over-slirp path end
to end; F7 adds a focused `f7-ncsi-dedicated-phy` job (§7) asserting the dedicated-PHY
bring-up **and the absence of NC-SI**.

Reproduce:

```sh
uv run asus-kgpe-d16-firmware/openbmc/bmc-functionality/f7-ncsi-evidence.py \
    --boot-log asus-kgpe-d16-firmware/openbmc/bmc-functionality/evidence/qemu-ncsi/eth0-dedicated-phy-boot.log
```

(The script also statically asserts the §1–§3 invariants against the DTS, `ast2050.h`,
the datasheet notes, and the QEMU MAC-model source — no build required.)

---

## 6. If the KGPE-D16 *did* wire NC-SI — what it would take (for completeness)

> ⚠️ **2026-07-18: the D16 DOES wire NC-SI — on MAC channel 2** (schematic §7; see
> the correction section). This "what it would take" list is therefore no longer
> hypothetical: it is the working recipe for task D07, with item 1 already
> satisfied by the board (RMII2 → LU1+LU2) and items 2–5 the open work (against
> **mac2**, not mac0 — MAC1 keeps its dedicated PHY).

Recorded so the difference is unambiguous. ~~**We do not do any of this** for the D16,
because the board is not wired for it~~ ⚠️ *[premise corrected 2026-07-18 — MAC2 is wired]*:

1. **Board:** route the MAC's RMII link to a host NIC's **NC-SI channel** (Intel/Broadcom)
   instead of the RTL8201CP. ~~(Physical wiring the KGPE-D16 does not have.)~~
   ⚠️ *[corrected 2026-07-18: the KGPE-D16 HAS this wiring on MAC2 — RMII2 balls
   A5/B5/B6/C4/D4/D5 multi-drop to both Intel 82574Ls, schematic §7]*
2. **U-Boot / straps:** set the MAC1 PHY-mode scratch `SCU40[15:14]` to `01`/`10`
   (NC-SI) instead of `00` (`CONFIG_MAC1_PHY_SETTING = 1|2`).
3. **DTS:** replace `phy-mode="rmii"` + PHY handle with `use-ncsi;` on the `&mac0` node
   (mainline `net/ncsi` binding).
4. **Kernel:** enable `CONFIG_NET_NCSI` (the D16 kernel does not build it today).
5. **QEMU (to demo):** add an **NC-SI responder** peer to `hw/net/ftgmac100.c` (our
   submodule has none) so the guest's NC-SI stack can claim a channel and learn a MAC.

~~Items 1–2 are the disqualifier: they describe a *different board*. NC-SI is **SoC-capable,
not board-wired on KGPE-D16.**~~ ⚠️ *[corrected 2026-07-18: item 1 is board-satisfied on
MAC2; NC-SI on the KGPE-D16 is SoC-capable AND board-wired — implementation is task D07]*

---

## 7. Real-hardware status (honest)

* **QEMU-proven:** the KGPE-D16's **dedicated-PHY** eth0 bring-up + DHCP (§5), and
  OpenBMC Redfish over that dedicated NIC (integration-branch evidence).
* **Real-HW-proven (from project memory / prior runs):** OpenBMC NFS-root boots on the
  physical AST2050 and `curl https://192.168.66.2/redfish/v1` returns
  `RedfishVersion 1.17.0` — over the board's **dedicated RTL8201CP NIC** at
  `192.168.66.2`, on the same physical Ethernet as the host. This *is* the board's
  "share the host's network" story, and it is real.
* **NC-SI on real HW:** ~~**not applicable / not present** — the board has no NC-SI
  sideband to characterise. This is a finding, not a gap.~~ ⚠️ *[corrected 2026-07-18:
  the MAC2 RMII2 sideband to LU1/LU2 exists and is aux-powered — silicon
  characterisation is an open D07 work item (needs 82574L NC-SI enable/EEPROM
  config; the datasheet is not in-repo)]*. No state-mutating hardware
  action was taken; the consolidated real-HW boot is owned by F-HWPASS.

---

## 8. Summary ⚠️ [rows 1 and "wiring" answers are MAC1-scoped — see 2026-07-18 correction]

| Question | Answer | Evidence |
|---|---|---|
| Does the KGPE-D16 BMC use NC-SI? | **No** (today's firmware, MAC1). ⚠️ *But the board WIRES it on MAC2 — reopened as D07 (2026-07-18)* | DTS `phy-mode=rmii` (§1.1); Raptor `CONFIG_MAC1_PHY_SETTING=0` (§1.2); schematic §7 (correction) |
| Is the NC-SI sideband wired on this board? | **Yes — MAC2/RMII2 multi-drop to both 82574Ls** (2026-07-18 correction) | `schematic-wiring/AST2050-BMC-WIRING.md` §7 |
| How does the BMC reach the network? | **Its own RTL8201CP PHY (RMII), own MAC/IP, same L2 as host.** | §1.4, §5, §7 |
| Does the AST2050 MAC have NC-SI hardware? | **No NC-SI register block.** SCU70[8:6] is MII/RMII-only. | Datasheet §1.3, §2 |
| Is NC-SI possible on the SoC at all? | **Yes — software over RMII**, if a board wires it (e.g. Dell C410X). | §3 |
| Can QEMU demonstrate NC-SI here? | **No responder in QEMU; and it would be unfaithful.** | §4 |
| What was demonstrated in QEMU? | **The real path:** dedicated-PHY eth0 up + DHCP, **zero NC-SI**. | §5 |

**"Piggybacking on the host's network interface" on the KGPE-D16 = a dedicated BMC NIC
sharing the host's physical Ethernet — which works. ~~True NC-SI sideband is a SoC
software capability that this board does not wire.~~** ⚠️ *[corrected 2026-07-18: the
board DOES wire the NC-SI sideband, on MAC2/RMII2 to both 82574Ls (schematic §7). True
NC-SI is a SoC software capability + board wiring that exist here but are not yet
implemented — task D07.]*
