# Driving the KGP(M)E-D16 BIOS over serial (via emulated USB keyboard)

**Goal:** change the ASUS KGP(M)E-D16 BIOS settings so that (a) all POST/boot
messages appear on the **COM1 serial port**, and (b) the BIOS Setup menu can be
navigated **entirely over the comm port** — no Magewell video + no USB keyboard
needed once redirection is on.

To *make* that change we drive the BIOS the hard way first: an **emulated USB
keyboard** (opi1pc-a in USB-gadget mode) types into the BIOS while the
**Magewell** HDMI capture on the rpi4 lets us see the screen. Once console
redirection is enabled and saved, the serial port replaces both.

## Infrastructure / topology

```
                 +---------------------- ASUS KGP(M)E-D16 (AST2050 BMC) ---------------------+
                 |  host x86 (Opteron)                              BMC (AST2050)            |
   USB kbd  <----+  USB port  <=== emulated HID boot keyboard                                |
   USB net  <----+  USB port  <=== ECM ethernet (192.168.222.1 host / .2 opi)               |
   HDMI     ----->  VGA/HDMI  ===> Magewell capture                                          |
   COM1     ----->  serial    ===> FTDI USB-serial                                           |
                 +----------------------------------------------------------------------------+
                        |                    |                         |
                   opi1pc-a             rpi4-asus-...            rpi4-asus-...
                 (/dev/hidg0)          (/dev/video0)          (/dev/serial-com1)
                 USB gadget board       Magewell HDMI            FTDI = ASUS COM1
```

### Access (SSH multiplex config)
`tmp/hw-access/ssh_config` — persistent ControlMaster so ssh calls are fast/reliable.
- `ssh -F tmp/hw-access/ssh_config opi …`  → opi1pc-a (Orange Pi, USB gadget)
- `ssh -F tmp/hw-access/ssh_config rpi4 …` → rpi4-asus-aspeed2050-dev (Magewell + serial + power)

### opi1pc-a — USB gadget (the emulated keyboard)
- UDC: `musb-hdrc.4.auto` (Allwinner sunxi MUSB OTG @ `1c19000.usb`), **bound/active**.
- configfs gadget `gadget`: composite `0x1d6b:0x0104`, functions **hid.usb0 + ecm.usb0**.
- **hid.usb0 is a BIOS-compatible boot keyboard**: `protocol=1` (keyboard),
  `subclass=1` (**boot**), `report_length=8`, report descriptor = the standard
  63-byte boot-keyboard descriptor (8-byte reports: modifiers, reserved, 6 keycodes).
- Write 8-byte HID reports to **`/dev/hidg0`** to send keystrokes.
- ECM side: opi `usb0 = 192.168.222.2/24`; ASUS host expected at `192.168.222.1`
  (gives a network path into the host OS when Linux is up).
- Passwordless sudo available; packages installable.

### rpi4-asus-aspeed2050-dev — eyes, serial, power
- `/dev/video0` — Magewell HDMI capture (the screen).
- `/dev/serial-com1` → `ttyUSB1` — **ASUS host COM1** (target for redirection).
- `/dev/serial-bmc-console` → `ttyAMA0` — AST2050 BMC UART.
- `/dev/serial-ulx3s`/`spispy` → `ttyUSB0` — SPI flash tooling.
- Power control over the ASUS (Tasmota plug) + passwordless sudo.

## Progress log

### 2026-07-10 00:21 UTC — baseline / access established
- SSH mux config created; both bridges reachable (opi1pc-a, rpi4-asus-…), reuse ~0.5s.
- Confirmed opi1pc-a already exposes a **BIOS-compatible boot-protocol keyboard**
  on `/dev/hidg0` (+ ECM ethernet), bound to the UDC.
- Confirmed rpi4 has Magewell `/dev/video0` and ASUS COM1 on `/dev/serial-com1`.
- ECM neighbour `192.168.222.1` (ASUS host) shows **FAILED** → host not currently
  driving the USB link, i.e. probably **not in Linux right now**. Next: read the
  Magewell + COM1 to establish the live screen state before doing anything.

### 2026-07-10 00:30 UTC — ASUS is ON, in SystemRescue Linux
- Magewell frame (720×576 text console) clearly shows **`SystemRescue 13.01
  (x86_64)` … `sysrescue login: root (autologin)` … `[root@sysrescue ~]#`** on
  tty6 → the host **is netbooted to Linux** with a root shell.
- ECM host side `192.168.222.1` still FAILED (host hasn't configured its USB NIC);
  COM1 silent (redirection not enabled yet). Both expected.
- Power: Tasmota plug **`au-plug-10`** (cold-cycle). rpi4 has ffmpeg + v4l2-ctl.
- Next: build reliable rig tooling (keysend on opi, frame-grab + serial logger on
  rpi4), then do a live keyboard test by typing into the root shell.

### 2026-07-10 00:35 UTC — rig tooling up; **emulated keyboard verified working**
- Deployed `keysend.py` (opi), `grabframe.sh` + `seriallog.py` (rpi4). Serial
  logger daemon running on `/dev/serial-com1` @115200.
- **Live keyboard test PASSED**: `keysend script 'press:ENTER|type:echo
  HID-KB-OK-1234|press:ENTER'` → Magewell frame shows `[root@sysrescue ~]# echo
  HID-KB-OK-1234`, the command output, and a fresh prompt. Host receives + acts
  on the emulated keystrokes. Boot-protocol descriptor already confirmed
  BIOS-compatible; functional BIOS test to follow at reboot.

## Plan
1. [x] Verify SSH access to opi1pc-a + rpi4; set up mux config.
2. [x] Confirm opi HID gadget is a boot-compatible keyboard on `/dev/hidg0`.
3. [x] Determine current ASUS state → ON, in SystemRescue Linux (Magewell).
4. [x] Set up daemons/helpers: keysend (opi), screen-grab (rpi4), serial-log (rpi4).
5. [x] Verify host sees the emulated keyboard + keystrokes register (Magewell).
6. [ ] Reboot; enter BIOS Setup using the emulated keyboard, confirmed via Magewell.
7. [ ] In BIOS: enable Console Redirection, baud/terminal, "Always after POST".
8. [ ] Save + reboot; verify POST/boot + Setup menu appear on `/dev/serial-com1`.
9. [ ] Confirm the BIOS menu is fully drivable over the comm port alone.

### 2026-07-10 00:48 UTC — full boot chain readable on COM1 via `serialscreen.py`
- Added `rig-tools/serialscreen.py` — a stdlib VT100 80×25 grid emulator that
  reconstructs the redirected screen from the raw log (AMIBIOS paints at absolute
  cursor positions, so a plain escape-strip is garbled; this renders it faithfully).
- Rendering `com1.log` shows the **entire boot** on the comm port: BIOS POST →
  **Intel(R) Boot Agent GE v1.3.24** (PXE OptROM) → **PXELINUX 4.07** →
  `Loading vmlinuz / sysresccd.img … ready` (CLIENT IP 192.168.77.138). So
  redirection carries through POST *and* the boot loader (the "Always" setting),
  and the board **network-boots SystemRescue** (PXE works too). This is exactly
  "see the BIOS/boot on the comm port without the Magewell".
- Next: build a serial *sender* (`serialkey.py`) and enter/drive Setup over COM1.

### 2026-07-10 00:46 UTC — ✅ **PRIMARY GOAL: boot messages now on the COM port**
- After F10 Save & Exit (CMOS written, board rebooted), the rpi4 serial logger on
  `/dev/serial-com1` @115200 immediately captured **live POST output** — VT100
  escape sequences (`ESC[21;00H`, colour `ESC[1;30;47m`) and the real POST text
  **`BMC is booting, please wait ...`** + the `3700` code. The Magewell VGA frame
  shows the identical text → **VGA and COM1 are now mirrored**. Redirection to
  COM1 works. (Raw sample in the log; `com1.log` 138 → 2557 B on the first POST.)
- Remaining: drive the **Setup menu over the comm port** (enter Setup + change a
  value using only serial) to close out "change BIOS settings just via the port".

### 2026-07-10 00:45 UTC — **entered BIOS via emulated keyboard; fixed redirection to COM1**
- Soft-rebooted host; POST showed `BMC is booting… / BMC failed …` (BMC being
  worked on separately — BIOS continues past it), then reached Setup. **DEL spam
  via the emulated keyboard entered AMIBIOS Setup** → the keyboard is
  **BIOS-compatible in the pre-OS environment** (not just in Linux). ✅
- Menu tabs: Main / Advanced / **Server** / Power / Boot / Tools / Exit. Remote
  Access lives under **Server → Remote Access Configuration** (not Advanced).
- **Found the root cause of the silent serial**: redirection was already
  `Enabled / 115200 8,n,1 / Flow=None / After-POST=Always`, but **Serial port
  number = COM2 (2F8h/IRQ3)** — while the FTDI capture is on **COM1 (3F8h/IRQ4)**
  (proved by the earlier `ttyS0` SERIALPROOF test). Redirection was working the
  whole time into an unmonitored port.
- **Changes made** (via emulated kbd + Magewell, ENTER-popup selection):
  - Serial port number: **COM2 → COM1** (now Base Address `3F8h, 4`).
  - Terminal Type: **VT-UTF8 → VT100** (cleanest for driving over serial).
- ⚠️ RTC read `Thu 11/12/2099`, time counting from `00:00:xx` → CMOS looks like it
  reset this boot (checksum-default?) despite the 2026-07-08 battery. Persistence
  across a *cold* cycle must be re-checked after this works.
- Next: **F10 Save & Exit**; the reboot's POST should now stream to COM1 @115200
  → the rpi4 serial logger. Then drive Setup over the comm port to prove the goal.

### 2026-07-10 00:37 UTC — **COM1 serial wire validated @115200**
- Typed (via emulated kbd) `stty -F /dev/ttyS0 115200 && echo SERIALPROOF-XYZ >
  /dev/ttyS0` on the host; the rpi4 serial logger captured
  `[10:01:48] SERIALPROOF-XYZ` → host COM1 (`ttyS0`) → rpi4 `/dev/serial-com1`
  works at **115200** (the baud we'll set for BIOS redirection). Whole path green:
  keyboard ✅, Magewell ✅, COM1 serial ✅, power = Tasmota `au-plug-10`.
- Next: reboot host (soft `reboot`, keeps the gadget attached), spam **DEL** to
  enter AMIBIOS Setup, navigate to Remote Access, enable redirection @115200 +
  "Always after POST".
