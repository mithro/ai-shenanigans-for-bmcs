# AST2050 / AST1100 I2C / SMBus Controller — Datasheet Extract

Source: **ASPEED AST2050/AST1100 A3 Datasheet, V1.05** (dated May 25, 2010).
File: `datasheets/aspeed/AST2050_AST1100_A3_Datasheet_V1.05.pdf`
(Note: the task referenced `datasheets/AST2050_..._V1.05.pdf`; the actual in-repo
path is under `datasheets/aspeed/`. Copies also live under
`asus-kgpe-d16-firmware/datasheets/` and `dell-c410x-firmware/datasheets/`.)

Purpose: authoritative reference for a **faithful QEMU model** of the AST2050
I2C/SMBus controller. OpenBMC uses these buses for LM75/TMP75 temperature
sensors, 24Cxx EEPROMs, PSU/PMBus, INA219 power monitors, PCA9555 GPIO
expanders, and PCA954x muxes — see the reverse-engineered C410X topology in
`dell-c410x-firmware/aspeed-bmc-dell-c410x.dts`.

Every value below carries a datasheet page cite. Where the datasheet is silent,
this is stated explicitly and the `hwreg.h` / C410X-dts fallback is used. The
printed page numbers equal the physical PDF page numbers, so `Read` the PDF at
the pages cited directly.

Base address: **I2C/SMBus global block = 0x1E78_A000** (physical address =
base + offset), stated verbatim in §31.1 (p.327) and the §31.4 header (p.334).

### hwreg.h has NOTHING for I2C — the datasheet is the sole authority

`asus-kgpe-d16-firmware/hwreg.h` lines 146-149 are just an empty comment banner:

```c
/*---------------------------------------------------------------
 *   I2C Controllers Register
 *  ------------------------------------------------------------
 */
```

There is **no** `AST_I2C_BASE` and no register defines. The base `0x1E78A000`
is inferred from the SoC peripheral-slot family (GPIO 0x…0000, RTC 0x…1000,
Timer 0x…2000, UART1 0x…3000, UART2 0x…4000, WDT 0x…5000, PWM 0x…6000,
VUART 0x…7000, PUART 0x…8000, LPC 0x…9000, **I2C 0x…A000**, PECI 0x…B000) and
confirmed by both the datasheet and the C410X `.dts` per-engine `reg` bases.
So every offset and bitfield below comes from the datasheet, not hwreg.h.

---

## 0. Where it lives in the datasheet

| What | Chapter / Section | Page |
|---|---|---|
| Feature summary | §1.3.15 I2C/SMBus/FML Serial Interface Controller | p.23 (ToC) |
| Functional overview | §2.15 I2C/SMBus Serial Interface Controller | p.33 (ToC) |
| **Overview + base address** | §31.1 | **p.327** |
| Features (Master/Slave/SMBus/FML/General) | §31.2 | p.327-328 |
| Timing definition (SCL freq formula, AC timing) | §31.3 | p.329-332 |
| **Clock setting table** (divisor → BaseClock/tCKHigh/tCKLow) | §31.3.1 | **p.333** |
| **Register map** (address definition, global + device regs) | §31.4 | **p.334-343** |
| Software programming guide (init, master/slave flow, reset, bus-lock) | §31.5 | p.344-347 |
| Software programming examples (worked master Tx/Rx sequences) | §31.6 | p.348-356 |
| High-speed (>1 MHz) mode programming | §31.6.14 | p.354-356 |

---

## 1. How many bus engines, and the per-engine base-address arithmetic

### 1.1 Seven engines (§31.1 p.327, §31.2.5 p.328, §31.4.1 p.334)

- §31.1 (p.327, verbatim): *"I2C/SMBus Controller implements **one set of global
  registers and 7 sets of device registers** to program the various functions
  supported by AST2050 / AST1100. Each register has its own specific offset
  value to derive its physical address location."*
- §31.2.5 General (p.328): *"Support totally **7 I2C/SMBus devices**. Device #1
  and #2 can be configured to FML or Alertable SMBus device."*

So the AST2050 has **7 I2C/SMBus channels** ("devices" in datasheet language,
"engines"/"buses" in Linux/QEMU language). This matches the C410X `.dts`
header note (line 18-19): *"The AST2050 has 7 I2C engines (vs 14 on AST2400)"*
and its closing note (line 1128-1129): *"the AST2050 only has engines 0-6."*

### 1.2 Global region + seven 64-byte device blocks + shared pool (§31.4.1 Address Definition, p.334)

The controller is **one MMIO region** = a global register block, then seven
back-to-back 64-byte (0x40) per-device blocks, then a 256-byte shared pool
buffer. Verbatim table (p.334):

| Offset range | Size (bytes) | Description |
|---|---|---|
| `0x000-0x03F` | 64 | Global Register |
| `0x040-0x07F` | 64 | Device 1 |
| `0x080-0x0BF` | 64 | Device 2 |
| `0x0C0-0x0FF` | 64 | Device 3 |
| `0x100-0x13F` | 64 | Device 4 |
| `0x140-0x17F` | 64 | Device 5 |
| `0x180-0x1BF` | 64 | Device 6 |
| `0x1C0-0x1FF` | 64 | Device 7 |
| `0x200-0x2FF` | 256 | Buffer Pool |

**Exact channel base-address arithmetic** (datasheet 1-indexed "Device *d*",
*d* = 1…7):

```
device_base(d)  = 0x1E78_A000 + 0x40 * d           # d = 1..7
                = Global(0x000) + 64*d
```

Equivalently, with the Linux/QEMU/C410X 0-indexed "engine *e*" (*e* = 0…6):

```
engine_base(e)  = 0x1E78_A040 + 0x40 * e           # e = 0..6  (device d = e+1)
```

- Global registers:  0x1E78_A000
- Device 1 / engine 0: 0x1E78_A040
- Device 2 / engine 1: 0x1E78_A080
- Device 3 / engine 2: 0x1E78_A0C0
- Device 4 / engine 3: 0x1E78_A100  ← **C410X firmware bus 0xF3 (PEX8696/PEX8647)**
- Device 5 / engine 4: 0x1E78_A140
- Device 6 / engine 5: 0x1E78_A180  (unused on C410X)
- Device 7 / engine 6: 0x1E78_A1C0
- Buffer Pool (shared): 0x1E78_A200 (256 bytes)

Every one of these bases is corroborated by the C410X `.dts` per-engine comments
(`&i2c0` → `0x1E78A040`, `&i2c1` → `0x1E78A080`, `&i2c2` → `0x1E78A0C0`,
`&i2c3` → `0x1E78A100`, `&i2c4` → `0x1E78A140`, `&i2c6` → `0x1E78A1C0`).

> **Off-by-one to keep straight in the model:** the datasheet numbers devices
> **1-7**; the `.dts` / Linux / QEMU number engines **0-6**. `&i2c3` (firmware
> "bus 3" / 0xF3, carrying the PEX PCIe-switch I2C traffic) is datasheet
> **Device #4** at offset `0x100`. Interrupt bits, however, are per *device*
> (see I2CG00 below): Device #4 = I2CG00 bit 3.

---

## 2. Global registers (§31.4.2, p.334-335)

Two global registers only, at offsets `0x00` and `0x04`.

### I2CG00 — Device Interrupt Status Register — offset `0x00`, Init = 0 (p.334)

Read-only interrupt *summary* across all 7 devices. **Not** write-to-clear —
you clear the per-device I2CD10 instead. (§31.4.2 note, p.334.)

| Bit | R/W | Field |
|---|---|---|
| 31:7 | - | Reserved (0) |
| 6 | R | I2C/SMBus **Device #7** interrupt (1 = interrupt occurs) |
| 5 | R | I2C/SMBus **Device #6** interrupt |
| 4 | R | I2C/SMBus **Device #5** interrupt |
| 3 | R | I2C/SMBus **Device #4** interrupt |
| 2 | R | I2C/SMBus **Device #3** interrupt |
| 1 | R | I2C/SMBus/FML **Device #2** interrupt |
| 0 | R | I2C/SMBus/FML **Device #1** interrupt |

Interrupt-handler flow (§31.5.7 p.345): read I2CG00 to find which device fired,
then read that device's I2CD10, service it, then write '1' to clear the flag(s)
in I2CD10.

### I2CG04 — I2C6/I2C7 Pin Multiplexing Setting Register — offset `0x04`, Init = 0 (p.335)

AST2050-specific pin-mux for the shared SCL6/SDA6/SCL7/SDA7 balls and the
FML/Alert alternate functions of I2C1/I2C2. This register has **no analogue in
later "new register mode" parts** — model it as an AST2050/AST2400-era global.

| Bit | R/W | Field |
|---|---|---|
| 31:2 | - | Reserved (0) |
| 1:0 | RW | Pin multiplexing: `00` = 7 set I2C; `01` = 6 set I2C + 2 Alert for I2C1/I2C2; `10` = 6 set I2C + 1 FML for I2C1; `11` = 5 set I2C + 2 FML for I2C1/I2C2 |

Pin-name mux table (p.335): SCL6/FLBINTCKEX2, SDA6/FLBSD2, SCL7/ALT1/FLBINTCKEX1,
SDA7/ALT2/FLBSD1 remap per the 2-bit selection. *"The pin mux defines the
functionality of I2C1, I2C2, I2C6 and I2C7."*

---

## 3. Per-device register map (§31.4.3, p.335-344)

All offsets below are **relative to `device_base(d)`** (e.g. add `0x100` for
`&i2c3`/Device #4). Sixteen device registers in the 64-byte block; the highest
used offset is `0x28`. Reset column: `X` = undefined at reset, `0` = zero.

| Offset | Name | Init | Purpose |
|---|---|---|---|
| `0x00` | **I2CD00** Function Control Register | 0 | Master/slave enable, address-response enables, FML/direct-drive/1T-drive |
| `0x04` | **I2CD04** Clock & AC Timing Control #1 | X | Base-clock divisors, tCKHigh/tCKLow, tBUF/tHDSTA/tACST/tHDDAT, timeout divisor |
| `0x08` | **I2CD08** Clock & AC Timing Control #2 | X | SCL-low timeout cycles |
| `0x0C` | **I2CD0C** Interrupt Control Register | 0 | Per-event interrupt enables |
| `0x10` | **I2CD10** Interrupt Status Register | 0 | Per-event status; **write-1-to-clear** |
| `0x14` | **I2CD14** Command / Status Register | 0 | Master start/tx/rx/stop command bits + bus/line status |
| `0x18` | **I2CD18** Slave Device Address Register | X | 7-bit own slave address |
| `0x1C` | **I2CD1C** Pool Buffer Control Register | X | Pool base ptr, Tx/Rx end addr, actual-received ptr |
| `0x20` | **I2CD20** Transmit/Receive Byte Buffer | X | 8-bit Tx byte + 8-bit Rx byte (byte-buffer mode) |
| `0x24` | **I2CD24** DMA Mode Control (Device #1/#2 only) | X | DMA buffer base + size |
| `0x28` | **I2CD28** DMA Mode Status (Device #1/#2 only) | X | Last DMA byte count |

### 3.1 I2CD00 — Function Control Register — offset `0x00`, Init = 0 (p.335-336)

This is the **master-enable / slave-enable** register.

| Bit | R/W | Field |
|---|---|---|
| 31:16 | - | Reserved (0) |
| 15 | RW | Disable multi-master capability (master only). 1 = single-master, ignore arbitration-lost check |
| 14 | RW | Enable SCL direct drive mode (master only). 0 = open-drain + external pull-up; 1 = always drive (extension of bit[7]) |
| 13:12 | RW | Clock-cycle selection for slowing FML master clock (2/3/4/5 APB cycles). **Device #1/#2 only**, reserved elsewhere |
| 11 | RW | Enable slow-down FML master clock. **Device #1/#2 only** |
| 10 | RW | Receiving data mode: 0 = filter SCL/SDA (glitch <1 APB clk removed); 1 = sample (synchronize) |
| 9 | RW | Data sequence: 0 = MSB-first, 1 = LSB-first |
| 8 | RW | Enable SDA to actively drive high for 1T (1 APB clk before tri-state) — higher transfer rate |
| 7 | RW | Enable SCL to actively drive high for 1T (**master only**) — higher transfer rate |
| 6 | RW | Enable FML function mode. **Device #1/#2 only**, reserved elsewhere |
| 5 | RW | Enable I2C/SMBus Device Default Address (`1100_001`) response |
| 4 | RW | Enable I2C/SMBus Device Alert Address (`0001_100`) response |
| 3 | RW | Enable I2C/SMBus ARP Host Address (`0001_000`) response |
| 2 | RW | Enable I2C/SMBus General Call Address (`0000_0000`) response |
| 1 | RW | **Enable slave function** |
| 0 | RW | **Enable master function** |

**Reset semantics (note, p.336):** whenever *both* master (bit 0) and slave
(bit 1) are disabled simultaneously, HW resets that device's I2CD0C (int
enable), I2CD10 (int status) and I2CD14 (command). This is the documented soft
reset (§31.5.8, p.346): write I2CD00[1:0]=0 to reset, then re-enable. A faithful
model **must** implement this side-effect.

### 3.2 I2CD04 — Clock & AC Timing Control Register #1 — offset `0x04`, Init = X (p.337-338)

This is the **clock divider / AC-timing** register. `Init = X` (undefined),
so firmware must always program it. Base Clocks #1/#2 are divided from the
**APB bus clock (PCLK)**.

| Bit | RW | Field | Encoding |
|---|---|---|---|
| 31:28 | RW | tBUF — bus-free between Stop and Start | `0000`=1×BaseClk#1 … `0111`=8×BaseClk#1, `1000`=1×BaseClk#2 … `1111`=8×BaseClk#2 |
| 27:24 | RW | tHDSTA — hold time of master Start | same encoding as tBUF |
| 23:20 | RW | tACST — setup/hold of master Start/Stop | same encoding; must be set to **max(tSUSTA, tHDSTAr, tSUSTO)** |
| 18:16 | RW | tCKHigh — master SCL clock-high pulse width | 000..111; effective cycles depend on FML enable + BaseClk#1 divisor (table p.337) |
| 14:12 | RW | tCKLow — master SCL clock-low pulse width | `000`=1 … `111`=8 cycles of BaseClk#1 |
| 11:10 | RW | tHDDAT — data hold time | Master: `00`=1,`01`=2,`10`=3,`11`=4; Slave: `00`=0,`01`=1,`10`=2,`11`=3 (units of BaseClk#1) |
| 9:8 | RW | Timeout base-clock divisor (from APB) | `00`=÷16384, `01`=÷65536, `10`=÷262144, `11`=÷1048576 |
| 7:4 | RW | **Base Clock #2 divisor** (from APB) | `0000`=÷2, `0001`=÷4, `0010`=÷8 … `1111`=÷65536 |
| 3:0 | RW | **Base Clock #1 divisor** (from APB) | `0000`=÷1, `0001`=÷2, `0010`=÷4 … `1111`=÷32768 |

tCKHigh detail (p.337): the effective high-pulse count depends on whether FML is
enabled and on the BaseClk#1 divisor (`I2CD04[3:0]`). For FML-disabled,
divisor=0: `000`→3 … `111`→10 cycles of BaseClk#1; divisor=1: `000`→1.5 …;
divisor>1: `000`→1 … `111`→8.

### 3.3 I2CD08 — Clock & AC Timing Control Register #2 — offset `0x08`, Init = X (p.338)

| Bit | RW | Field |
|---|---|---|
| 31:3 | - | Reserved |
| 2:0 | RW | Cycles of clock-low timeout (tTimeOut): `000` = no timeout control; `001` = 1-2 cycles of the timeout base clock … `111` = 7-8 cycles. (One cycle of uncertainty since the timeout counter free-runs.) |

### 3.4 I2CD0C — Interrupt Control (enable) Register — offset `0x0C`, Init = 0 (p.338-339)

`0` = disable, `1` = enable, per bit.

| Bit | Field |
|---|---|
| 31:14 | Reserved (0) |
| 13 | Enable Bus Recover Done interrupt |
| 12 | Enable SMBus Device Alert interrupt |
| 11 | Enable SMBus ARP Host Address Detection interrupt |
| 10 | Enable SMBus Device Alert Response Address Detection interrupt |
| 9 | Enable SMBus Device Default Address Detection interrupt |
| 8 | Enable General Call Address Detection interrupt |
| 7 | Enable Slave Address Received Match interrupt |
| 6 | Enable SCL clock-low timeout interrupt |
| 5 | Enable abnormal Start/Stop condition detection interrupt (bus condition detected at an illegal transfer state) |
| 4 | Enable normal Stop condition detection interrupt (master: Stop issued; slave: Stop detected) |
| 3 | Enable master arbitration loss interrupt |
| 2 | Enable Receive Done interrupt (master: expected bytes received or buffer full; slave: buffer full or terminated + last ACK/NACK returned + data received) |
| 1 | Enable Transmit with NACK Returned interrupt |
| 0 | Enable Transmit Done with ACK Returned interrupt |

### 3.5 I2CD10 — Interrupt Status Register — offset `0x10`, Init = 0 — **write-1-to-clear** (p.339-340)

Same bit layout as I2CD0C bits 13:0. **"WC" = cleared by writing '1'.** Firmware
clears by writing `0xFFFFFFFF`. This is the register polled during a transfer.

| Bit | Status (all "WC") |
|---|---|
| 13 | Bus Recover Done |
| 12 | SMBus Device Alert |
| 11 | SMBus ARP Host Address Detection |
| 10 | SMBus Device Alert Response Address Detection |
| 9 | SMBus Device Default Address Detection |
| 8 | General Call Address Detection |
| 7 | Slave Address Received Match |
| 6 | SCL clock-low timeout |
| 5 | Abnormal Start/Stop Condition Detection |
| 4 | Normal Stop Condition Detection |
| 3 | Master Arbitration Loss |
| 2 | **Receive Done** (S/W must clear to allow next receive; in byte-buffer mode may set concurrently with bits[11:7]) |
| 1 | **Transmit with NACK Returned** |
| 0 | **Transmit Done with ACK Returned** |

### 3.6 I2CD14 — Command / Status Register — offset `0x14`, Init = 0 (p.340-342)

**The heart of the master state machine.** Upper bits are read-only status
(much of it debug-only); lower bits are the command bits firmware writes to
issue START/TX/RX/STOP.

| Bit | R/W | Field |
|---|---|---|
| 31:29 | - | Reserved (0) |
| 28 | R | SDA_OE (debug) |
| 27 | R | SDA_O (debug) |
| 26 | R | SCL_OE (debug) |
| 25 | R | SCL_O (debug) |
| 24:23 | R | Transfer Mode **Timing Stage** (debug): `00`=T0 `01`=T1 `10`=T2 `11`=T3 |
| 22:19 | R | Transfer Mode **State Machine** (debug): `0000`=IDLE, `1000`=MACTIVE, `1001`=MSTART, `1010`=MSTARTR, `1011`=MSTOP, `1100`=MTXD, `1101`=MRXACK, `1110`=MRXD, `1111`=MTXACK, `0001`=SWAIT, `0100`=SRXD, `0101`=STXACK, `0110`=STXD, `0111`=SRXACK, `0011`=RECOVER |
| 18 | R | Sampled SCL line state |
| 17 | R | Sampled SDA line state |
| 16 | R | **Bus Busy Status**: 0 = idle, 1 = busy / not meeting idle timing |
| 15 | RW | SDA_OE output direct control (GPIO mode; only when master+slave both disabled — bus-lock recovery) |
| 14 | RW | SDA_O output direct control |
| 13 | RW | SCL_OE output direct control |
| 12 | RW | SCL_O output direct control |
| 11 | RW | **Enable Bus Recover Command** (0=NOP, 1=issue; issues 1-8 SCL cycles to unlock SDA; state machine must be IDLE) |
| 10 | RW | Enable issuing I2C/SMBus Slave Alert signal (Device #1/#2 only; auto-cleared after addr match) |
| 9 | RW | Enable Master/Slave Receive from DMA Buffer (Device #1/#2 only; auto-cleared when done) |
| 8 | RW | Enable Master/Slave Transmit from DMA Buffer (Device #1/#2 only; auto-cleared) |
| 7 | RW | Enable Master/Slave Receive Data Buffer (Pool) (auto-cleared) |
| 6 | RW | Enable Master/Slave Transmit Data Buffer (Pool) (auto-cleared) |
| 5 | RW | **Master Stop Command** (0=NOP, 1=issue; auto-cleared; master mode only) — **4th priority** |
| 4 | RW | **Master/Slave Receive Command Last** (0 = continue with ACK, 1 = end with NACK) |
| 3 | RW | **Master Receive Command** (0=NOP, 1=fire; auto-cleared on RX full / Stop / Repeated-Start) — **3rd priority** |
| 2 | RW | **Slave Transmit Command** (0=NOP, 1=fire; auto-cleared on TX-empty / bus contention) |
| 1 | RW | **Master Transmit Command** (0=NOP, 1=fire; auto-cleared on TX-empty / bus contention) — **2nd priority** |
| 0 | RW | **Master Start Command** (0=NOP, 1=issue Start / Repeated-Start; auto-cleared; executes only when master enabled and bus idle) — **1st priority** |

**Command priority (note, p.342):** when multiple command bits are set at once,
HW executes them in order (1) Master Start, (2) Master Transmit, (3) Slave
Transmit *or* Master Receive, (4) Master Stop. HW auto-clears each command when
finished, and clears **all** commands on Master Arbitration Loss or invalid
Start/Stop. **Master and Slave commands cannot be set at the same time.**

### 3.7 I2CD18 — Slave Device Address Register — offset `0x18`, Init = X (p.342)

| Bit | RW | Field |
|---|---|---|
| 31:7 | - | Reserved (0) |
| 6:0 | RW | **Slave Device Address** (7-bit; controller supports 7-bit addressing only, §31.2.2 p.327) |

### 3.8 I2CD1C — Pool Buffer Control Register — offset `0x1C`, Init = X (p.343)

Manages the shared 256-byte pool buffer (0x1E78_A200) for this device.
Addresses are in 4-byte (double-word) units.

| Bit | RW | Field |
|---|---|---|
| 31:24 | R | Actual Received Pool Buffer Address Pointer (received byte count = (this − base)×4 + 1; 0 ⇒ 256 bytes) |
| 23:16 | RW | Receive Pool Buffer End Address (rx size = (end − base)×4 + 1) |
| 15:8 | RW | Transmit Data Buffer End Address (tx count = (end − base)×4 + 1) |
| 7:6 | - | Reserved |
| 5:0 | RW | Buffer Base Address Pointer (start of Tx/Rx region, double-word unit; shared by Tx and Rx since Tx has priority) |

### 3.9 I2CD20 — Transmit/Receive Byte Buffer Register — offset `0x20`, Init = X (p.343)

The **byte-buffer** data path (used when neither Pool nor DMA is enabled).

| Bit | RW | Field |
|---|---|---|
| 31:16 | - | Reserved |
| 15:8 | R | **Receive Byte Buffer** (the received data byte) |
| 7:0 | RW | **Transmit Byte Buffer** (the byte to send — including the addr+R/W byte) |

Note (§31.6.9, p.352): in slave mode, the first received byte is the address
byte; its LSB `I2CD20[8]` = R/W direction (0 = master writes to us, 1 = master
reads from us).

### 3.10 I2CD24 / I2CD28 — DMA Mode Control / Status (Device #1/#2 only) — offsets `0x24`/`0x28`, Init = X (p.343-344)

| Reg / Bit | RW | Field |
|---|---|---|
| I2CD24 [27:12] | RW | DMA Buffer Base Address (from SDRAM, 4K-byte boundary) |
| I2CD24 [11:0] | RW | DMA Buffer Size (bytes). Tx: byte boundary (0=1 byte …). Rx: 8-byte boundary (0=1 byte needs 8-byte buffer, 8=9 bytes needs 16-byte buffer …) |
| I2CD28 [11:0] | R | Last accessed DMA address / last received byte count. Tx-done ⇒ = DMA_Buffer_Size; Rx-done ⇒ max addr = DMA_Buffer_Size + 1 |

**Only Device #1 and #2** have DMA (max 4 KB shared from SDRAM). Devices #3-#7
have byte-buffer + pool only. (§31.2.5 p.328, §31.5.9 p.346.)

---

## 4. Master transaction flow (§31.5.4 p.345, §31.6 p.348-352)

### 4.1 Initialization sequence (§31.5.1, p.344)

1. Write **I2CD00** = enable-function setting (set bit 0 for master).
2. Write **I2CD04** (clock divisor + AC timing).
3. Write **I2CD08** (timeout).
4. Write **I2CD10** = `0xFFFFFFFF` (clear any pending interrupt status).
5. Write **I2CD0C** = interrupt-enable setting.
6. Master and slave mode may be enabled individually or concurrently.

### 4.2 The four master command primitives (§31.5.4, p.345)

In master mode there are exactly four command types, applied per their priority:

1. **Transmit Start** (I2CD14 bit 0): HW generates a Start pattern when the bus
   is idle.
2. **Transmit Data** (I2CD14 bit 1): transmits until the Tx buffer is empty,
   arbitration is lost, or an invalid bus condition occurs.
3. **Receive Data** (I2CD14 bit 3): receives until the Rx buffer is full,
   transmission stopped by a NACK response, or an invalid bus condition. The
   **Receive Data Last** control (bit 4 = 1 → NACK) ends the receive cycle.
4. **Transmit Stop** (I2CD14 bit 5): generates a Stop pattern.

The four command bits can be combined in one write as long as they follow the
priority ordering — that is how a whole `START → addr → data → STOP` is issued
in a single register write.

### 4.3 Worked example — Master Transmit 1 byte (§31.6.2, p.348)

1. `I2CD00 = 0x00000001` — enable master function.
2. Program AC timing. Example: PCLK = 50 MHz, target 100 kHz →
   `50MHz/100kHz = 500 = 32×16` → BaseClk#1 divisor `Div(5)` (÷32),
   tCKLow(7)=8, tCKHigh(7)=8 → ≈ 97.7 kHz. **`I2CD04 = 0x77777355`**,
   `I2CD08 = 0x00000000`.
3. `I2CD10 = 0xFFFFFFFF` — clear interrupt status.
4. `I2CD0C = 0x000000BF` — enable interrupts.
5. `I2CD20 = 0x000000DD` — the byte to transmit (this is the addr+W byte, or data).
6. **Fire the command via I2CD14** — pick per how the transaction is framed:
   - `I2CD14 = 0x00000023` → Start → Tx Byte → Stop  (bits 0,1,5)
   - `I2CD14 = 0x00000003` → Start → Tx Byte → Waiting  (bits 0,1) — leaves bus held for more
   - `I2CD14 = 0x00000002` → Waiting → Tx Byte → Waiting  (bit 1)
   - `I2CD14 = 0x00000022` → Waiting → Tx Byte → Stop  (bits 1,5)
7. **Poll I2CD10** for the result:
   - bit[0]=1 → transmit finished OK (**ACK received**)
   - bit[1]=1 → transmit FAIL, **NACK returned**
   - bit[3]=1 → master arbitration lost (all commands stopped/halted)
   - bit[4]=1 → transmit finished and Stop issued
   - bit[5]=1 → transmit FAIL, invalid Stop condition (all commands halted)
   - bit[6]=1 → SCL-low timeout
8. `I2CD10 = 0xFFFFFFFF` — clear status.

So a typical OpenBMC sensor read = **Master Transmit (addr+W, register index)**
then **Repeated-Start + Master Receive (addr+R, N bytes with NACK on last)**;
see §31.6.8 "Master Transmit 1 Byte and then Receive 1 Byte" (p.352):
`I2CD14 = 0x3B` = Start → Tx Byte → Rx Byte → Stop.

### 4.4 How a byte is transmitted / received, and ACK/NAK handling

- **A transmitted byte** (Figure 72 "Master Tx/Rx Timing", p.331): TxData drives
  SDA during tHDDAT then holds through the SCL low/high window; TxACK is the
  slave's acknowledge sampled by the master. The controller does
  **automatic ACK/NACK generation for receive and detection for transmit**
  (§31.2.1 p.327): on transmit, HW samples the 9th-clock ACK and reports it as
  I2CD10 bit[0] (ACK) vs bit[1] (NACK); on receive, HW auto-generates ACK unless
  **Receive Command Last** (I2CD14 bit 4) = 1, which sends NACK to terminate.
- **Repeated-Start** uses the same Master Start Command (bit 0) mid-transaction
  (state MSTARTR); a "Waiting → … → Waiting" command leaves the bus held so the
  next command can Repeated-Start.
- Master Receive worked example (§31.6.5, p.350):
  `I2CD14 = 0x08` (Rx → TxACK → Waiting, keep reading),
  `0x18` (Rx → TxNACK → Waiting, last byte),
  `0x38` (Rx → TxNACK → Stop, last byte + Stop). Poll I2CD10 bit[2] = Receive
  Done; read the data from I2CD20[15:8].

### 4.5 Buffer / pool / DMA variants of the command word

Same START/STOP framing, different data path (§31.6.3-31.6.7):
- **Pool mode:** set I2CD1C base/end pointers, then OR in I2CD14 bit[6] (Tx pool)
  / bit[7] (Rx pool). E.g. `I2CD14 = 0x63` = Start → Tx Buffer → Stop.
- **DMA mode (Device #1/#2):** set I2CD24 base/size, then OR in bit[8] (Tx DMA)
  / bit[9] (Rx DMA). E.g. `I2CD14 = 0x123` = Start → Tx DMA → Stop;
  final byte count in I2CD28[11:0].

### 4.6 Bus-lock recovery (§31.5.11, p.346-347)

Two mechanisms a faithful model should be aware of: **Auto Recover** (I2CD14
bit[11]=1 issues 1-8 recovery SCL clocks; check I2CD14[18:17]) and **GPIO mode**
(I2CD14 bits[15:12] directly drive SCL_O/SCL_OE/SDA_O/SDA_OE — only valid when
both master and slave are disabled). Bus-lock diagnosis reads I2CD14[18:17]:
`10` = SDA lock (recoverable), `11` = no lock (S/W error).

---

## 5. Bus timing / clock source (§31.3 p.329, §31.6.1 p.348)

- **SCL frequency formula** (§31.3, p.329):
  `Freq_SCL = Freq_CoreClock / (t_BaseCyc × (t_CKLow + t_CKHigh))`
  with `t_BaseCyc = 1,2,4,8,…,32768`, `t_CKLow = 1..8`, `t_CKHigh = 1..8`.
  All AC timing is referenced to the Base Clock, so larger CKLow/CKHigh give
  better AC-timing resolution.
- **Clock source = APB bus clock (PCLK)**, itself derived from the H-PLL. The
  clock-rate calculation (§31.6.1, p.348) reads:
  - **H-PLL frequency** from `SCU70[11:9]` (000=266, 001=233, 010=200, 011=166,
    100=133, 101=100, 110=300, **111=24 MHz**).
  - **PCLK** from `SCU08[25:23]` (000=H-PLL/2, 001=/4, 010=/6, 011=/8, 100=/10,
    101=/12, 110=/14, 111=/16).
  - `divider_ratio = PCLK / desired_I2C_rate`; from it derive the BaseClk#1/#2
    divisors `I2CD04[3:0]`/`[7:4]` and the SCL high/low counts
    `I2CD04[18:16]`/`[14:12]`.
- **Data Bit Rate = Core Clock Frequency / Clock Divisor** (§31.3.1 Clock Setting
  Table, p.333) — a lookup table mapping Divisor → (BaseClock, tCKHigh, tCKLow).
  Range: **0.5 Kbps – 8 Mbps if core clock = 50 MHz** (§31.2.1 p.327).
- **High-speed mode (>1 MHz)** requires PCLK > 33 MHz and a per-packet speed
  change (send high-speed master code 0x08-0x0F at normal speed, then switch);
  I2CD00[8:7]=`11` sharpens the rising edge (§31.6.14, p.354-356). This section
  was added in datasheet V1.05 (the only functional I2C change in that revision).

Reset value of I2CD04/I2CD08 is `X` (undefined) — firmware must program clock/
timing before use; a faithful model should not assume a sane default rate.

---

## 6. AST2050-vs-newer differences a faithful model MUST capture

This is the **OLD Aspeed I2C register layout** — the same family later described
by the Linux `aspeed,ast2400-i2c-bus` binding and QEMU's legacy `aspeed_i2c`
"old register mode". Key facts to preserve, and how the AST2050 differs from
AST2400/2500/2600:

1. **Channel count is 7, not 14/16.** AST2050 = **7 devices** (§31.1 p.327,
   §31.4.1 p.334). AST2400 (G4) and AST2500 (G5) expose **14** I2C buses;
   AST2600 exposes up to **16**. A model of the AST2050 must instantiate exactly
   7 engines and stop the address decode at Device 7 (`0x1FF`). The C410X `.dts`
   note (line 1127-1129): *"I2C engines 7-13 exist in the AST2400 dtsi but the
   AST2050 only has engines 0-6."*

2. **Old register layout: global block + 0x40-strided device blocks + shared
   256-byte pool.** Global regs at `0x00`/`0x04`, Device *d* at `0x40×d`, pool
   buffer at `0x200` (§31.4.1 p.334). Per-device register offsets are the
   *old-mode* set (I2CD00…I2CD28 at `0x00`-`0x28`). The AST2500 keeps this old
   layout **but adds a "new register mode"** (a completely different per-bus
   register set); the AST2600 is essentially new-mode-only with a per-bus
   `0x80`-strided block and a separate global control at offset `0x00`/`0x0C`
   with buffer/DMA moved. **The AST2050 has NO new register mode** — there is no
   mode-select bit and no new-mode register file. Model it strictly as old mode.

3. **The global I2CG04 pin-mux register (offset 0x04)** for SCL6/SDA6/SCL7/SDA7
   and the FML/Alert alternates is an AST2050/AST2400-era global that does not
   exist on the newer parts (which move muxing into SCU pinctrl). It has only
   the one 2-bit field (§31.4.2 p.335).

4. **FML and DMA are Device #1/#2 only.** On AST2050, only devices 1 and 2 can
   be FML controllers and only they have the DMA-buffer path (I2CD24/I2CD28) and
   the SMBus slave-alert issue command (I2CD14 bit 10) (§31.2.4/§31.2.5 p.328,
   §31.4.3 p.336/341/343). The FML slow-down fields (I2CD00[13:12],[11],[6]) are
   reserved on devices 3-7. Newer parts generalize DMA across more buses.

5. **7-bit addressing only** (§31.2.2 p.327; I2CD18[6:0]). No 10-bit addressing.

6. **The command register (I2CD14) IS the master engine.** START/TX/RX/STOP are
   individual write-1 command bits with a fixed HW priority
   (Start > MasterTx > SlaveTx/MasterRx > Stop) and HW auto-clear; the transfer
   state machine (I2CD14[22:19]) and timing stage ([24:23]) are exposed only as
   debug read-back. A faithful model must reproduce the auto-clear-on-completion
   and clear-all-on-arbitration-loss behavior, plus the "both master+slave
   disabled ⇒ soft-reset I2CD0C/I2CD10/I2CD14" side effect (§31.4.3 note p.336,
   §31.5.8 p.346).

7. **Interrupt model:** a read-only global summary (I2CG00, 7 device bits) plus
   per-device write-1-to-clear status (I2CD10). This matches the old
   `aspeed_i2c` model; the newer "new mode" splits interrupt bits differently.

8. **Base address 0x1E78_A000** is stable across AST2050→AST2400→AST2500 (the
   `0x1E78_xxxx` peripheral block); the AST2600 relocates the I2C block. For the
   AST2050 target, `0x1E78_A000` is correct and matches every C410X `.dts`
   engine `reg`.

### Practical mapping to the OpenBMC / C410X sensor topology

From `dell-c410x-firmware/aspeed-bmc-dell-c410x.dts`, the reverse-engineered use
of the 7 engines (all "old mode" master transactions), for cross-checking a
model driven by real firmware traffic:

| DTS engine (`reg`) | Datasheet device / offset | Firmware bus | Devices attached |
|---|---|---|---|
| `&i2c0` 0x1E78A040 | Device 1 / `0x040` | 0xF0 | 16× INA219 power monitors (0x40-0x4F) |
| `&i2c1` 0x1E78A080 | Device 2 / `0x080` | 0xF1 | PCA9555 (0x20), PCA9544 mux (0x70) → 2× ADT7462 |
| `&i2c2` 0x1E78A0C0 | Device 3 / `0x0C0` | 0xF2 | 24C256 FRU EEPROM (0x50) |
| `&i2c3` 0x1E78A100 | **Device 4 / `0x100`** | 0xF3 | PEX8696/PEX8647 PCIe switches (raw I2C) |
| `&i2c4` 0x1E78A140 | Device 5 / `0x140` | 0xF4 | 2× PCA9548 mux (0x70/0x71) → 16× TMP75/LM75 |
| — (unused) | Device 6 / `0x180` | 0xF5 | not used on C410X |
| `&i2c6` 0x1E78A1C0 | Device 7 / `0x1C0` | 0xF6 | 4× PCA9555 (0x20-0x23), LM75 (0x4F) |

LM75/TMP75 sensors, 24Cxx EEPROMs, PMBus PSUs and PCA9555/PCA954x devices are
all standard 7-bit I2C slaves reached by exactly the master-Tx/Rx command
sequences in §4 above — so a faithful AST2050 I2C model that implements I2CD00
(enable), I2CD04/08 (clock), I2CD14 (start/tx/rx/stop + priority + auto-clear),
I2CD10 (WC status/interrupts), I2CD18 (own slave addr), and the byte + pool
buffers is sufficient to drive the full OpenBMC hwmon stack.
