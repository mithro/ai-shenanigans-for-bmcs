# Controlling the KGP(M)E-D16 rig — BIOS & system access

Operational reference for driving the ASUS KGP(M)E-D16 host (AMIBIOS8) and its
BIOS **remotely**, two ways:

1. **Serial console over COM1 — preferred.** Once BIOS console redirection is on,
   the whole firmware UI (POST, Setup, boot loader) is on the comm port. No video,
   no keyboard hardware needed.
2. **Virtual USB keyboard + Magewell video — fallback / bootstrap.** An Orange Pi
   in USB-gadget mode is a real keyboard to the host; a Magewell HDMI capture is
   the screen. This is how redirection was first enabled, and the way in if serial
   is ever misconfigured.

The bring-up story (how this was first made to work) is in
[`BIOS-SERIAL-CONSOLE-BRINGUP.md`](BIOS-SERIAL-CONSOLE-BRINGUP.md); the BIOS
option analysis is in [`BIOS-CONFIG-WITHOUT-MENU.md`](BIOS-CONFIG-WITHOUT-MENU.md).

---

## 1. Topology

```
              +---------------------------- ASUS KGP(M)E-D16 host (x86 Opteron) --------------------+
              |                                                            AST2050 BMC (separate)    |
  USB kbd <---+ USB  <==== HID boot keyboard   (opi /dev/hidg0)                                      |
  USB net <---+ USB  <==== ECM usb-ethernet    (opi usb0 .2 / host .1)                               |
  VGA/HDMI --->  video ===> Magewell capture    (rpi4 /dev/video0)                                   |
  COM1 3F8h --> serial ===> PL2303 USB-serial   (rpi4 /dev/serial-com1)  <=== BIOS redirects here    |
  AC in   <---- mains  <=== Tasmota smart plug   (au-plug-10)                                         |
              +-------------------------------------------------------------------------------------+
                     |                    |                        |                    |
                opi1pc-a             rpi4-asus-...            rpi4-asus-...         au-plug-10
              (USB gadget)          (Magewell video)        (COM1 serial)        (mains power)
```

### Control hosts (SSH)
| Alias | FQDN | Role |
|---|---|---|
| `opi`  | `opi1pc-a.iot.welland.mithis.com` | Orange Pi, USB-gadget = emulated keyboard + ECM net |
| `rpi4` | `rpi4-asus-aspeed2050-dev.iot.welland.mithis.com` | Magewell video, COM1 serial, BMC UART, power |

Both log in as **`tim`** with passwordless `sudo`. Use the persistent-mux SSH
config so calls are fast/reliable (see `tmp/hw-access/ssh_config`):

```
Host *
    ControlMaster auto
    ControlPath /home/tim/.ssh/cm/%C
    ControlPersist 30m
    BatchMode yes
    StrictHostKeyChecking accept-new
Host opi
    HostName opi1pc-a.iot.welland.mithis.com
    User tim
Host rpi4
    HostName rpi4-asus-aspeed2050-dev.iot.welland.mithis.com
    User tim
```
Then `ssh -F tmp/hw-access/ssh_config opi …` / `… rpi4 …`. If a muxed channel
ever hangs, reset it with `ssh -F … -O exit rpi4` and reconnect (don't give up —
retry).

### rpi4 device map
| Node | Points at | Use |
|---|---|---|
| `/dev/serial-com1` → `ttyUSB1` | **ASUS COM1 (3F8h/IRQ4)** | BIOS serial redirection target |
| `/dev/video0` | Magewell HDMI capture (720×576 YUYV) | see the screen |
| `/dev/serial-bmc-console` → `ttyAMA0` | AST2050 BMC UART | BMC console (separate work) |
| `/dev/serial-ulx3s` / `spispy` → `ttyUSB0` | SPI-flash tooling | flashing (separate work) |

---

## 2. Shared daemons & locks — avoiding multi-reader/writer races

Each physical resource has **exactly one owner**; clients never open the device
directly. This is what stops two sessions (or two tools) from fighting over a tty,
a v4l2 node, or the HID gadget.

| Resource | Owner (single) | How clients READ | How clients WRITE |
|---|---|---|---|
| COM1 `/dev/serial-com1` | **`seriald.py`** (systemd `kgpe-seriald.service`) | read the log file `~/hw-capture/com1.log` (`serialscreen.py` / `tail -f`) — any number of readers | write to the daemon's TX FIFO `~/hw-capture/com1.tx` (via `serialkey.py`) |
| USB keyboard `/dev/hidg0` | whoever holds the `flock` | — (no readers) | `keysend.py`, serialised by an exclusive `flock(/run/hidg0.lock)` |
| Magewell `/dev/video0` | whoever holds the `flock` | read the PNG a grab produced | `grabframe.sh`, serialised by `flock(~/.video0.lock)` |
| Power `au-plug-10` | Tasmota (stateless HTTP) | `cm?cmnd=Power` | `cm?cmnd=Power%20ON/OFF/TOGGLE` — idempotent, no lock needed |

**Why a daemon for serial but a lock for keyboard/camera?** The serial port must be
read *continuously* (you can't miss POST bytes), so a persistent daemon owns it and
publishes a log that many readers share; a FIFO gives a single, ordered write path.
The keyboard and camera are touched *intermittently*, so a mutual-exclusion `flock`
(one operation at a time) is the right, simpler tool — no daemon required.

### The serial daemon (`seriald.py` / `kgpe-seriald.service`)
Owns `/dev/serial-com1` @115200 8N1: RX → timestamped `~/hw-capture/com1.log`,
and forwards anything from the FIFO `~/hw-capture/com1.tx` → the port TX.
```sh
# already installed & enabled on rpi4; manage with:
ssh -F … rpi4 'systemctl status kgpe-seriald.service'
ssh -F … rpi4 'sudo systemctl restart kgpe-seriald.service'   # e.g. after changing baud
```
> **Never** run a second reader on `/dev/serial-com1` (no `cat`, no extra logger) —
> two readers race for bytes. Read `com1.log` instead. `serialkey.py --direct` (which
> opens the tty) is a *fallback only*; with the daemon running, always use the FIFO.

---

## 3. Method 1 (preferred): the serial console over COM1

BIOS redirection is configured (Server → Remote Access) to:
`Remote Access=Enabled, Serial port=COM1 (3F8h/IRQ4), Mode=115200 8,n,1,
Flow=None, Redirection After BIOS POST=Always, Terminal Type=VT100,
VT-UTF8 Combo Key Support=Enabled`. So COM1 carries POST, Setup, and the boot loader.

### See the screen
The daemon logs raw VT100; reconstruct the 80×25 screen with `serialscreen.py`
(a plain escape-strip is unreadable because AMIBIOS paints at absolute positions):
```sh
ssh -F … rpi4 'python3 ~/rig-tools/serialscreen.py ~/hw-capture/com1.log --from-last-clear'
ssh -F … rpi4 'tail -f ~/hw-capture/com1.log'    # raw live stream
```

### Type / drive the BIOS  (`serialkey.py`, writes via the daemon FIFO)
```sh
ssh -F … rpi4 'python3 ~/rig-tools/serialkey.py press DEL'          # (spam during POST) enter Setup
ssh -F … rpi4 'python3 ~/rig-tools/serialkey.py press RIGHT'        # next menu tab
ssh -F … rpi4 'python3 ~/rig-tools/serialkey.py press DOWN DOWN ENTER'  # move + open item/popup
ssh -F … rpi4 'python3 ~/rig-tools/serialkey.py press ESC'         # cancel / back
ssh -F … rpi4 'python3 ~/rig-tools/serialkey.py press F10 ENTER'   # Save & Exit (F10 = AMI ESC-0 combo)
ssh -F … rpi4 'python3 ~/rig-tools/serialkey.py type "115200"'     # type into a field
```
Key encodings (Terminal Type = VT100): arrows `ESC[A/B/C/D`, Enter `CR`, `ESC`,
Tab, `DEL`=`0x7F`; **F1–F12 = `ESC 1`…`ESC 0`, `ESC !`, `ESC @`** (the AMI combo
keys, enabled by *VT-UTF8 Combo Key Support*). See `serialkey.py --help`.

### Entering Setup over serial — timing matters
The setup key is only accepted during a short POST window, and this board first
**waits on the BMC ~100–130 s** (`BMC is booting…` then `BMC failed …`) before the
prompt. So **spam** DEL across the window:
```sh
ssh -F … rpi4 'for i in $(seq 1 120); do \
    python3 ~/rig-tools/serialkey.py --delay 90 press DEL DEL DEL DEL DEL DEL DEL DEL DEL DEL; done &'
# watch it land, then STOP the spammer (bracket trick so pkill doesn't match itself):
ssh -F … rpi4 'python3 ~/rig-tools/serialscreen.py ~/hw-capture/com1.log --from-last-clear'
ssh -F … rpi4 'pkill -f "[s]erialkey.py"'
```

### Worked example — change a setting entirely over serial
```sh
# (during POST) enter Setup by spamming DEL as above, then:
serialkey press RIGHT RIGHT ENTER    # Main -> Advanced -> Server -> Remote Access
serialkey press DOWN ENTER           # open a field's change-popup
serialkey press UP ENTER             # pick a value
serialkey press F10 ENTER            # Save & Exit
# verify with serialscreen after each step.
```

---

## 4. Method 2 (fallback): virtual USB keyboard + Magewell

Use this to *bootstrap* (e.g. if serial redirection is disabled) or to see the
real VGA output. The Orange Pi presents a **BIOS-compatible boot keyboard**
(`hid.usb0`: protocol=1, subclass=1, 8-byte reports) on `/dev/hidg0`, auto-created
at boot by `usb-gadget.service` → `/usr/local/sbin/usb-gadget-setup.sh` (ansible).

### Type on the host (works in Linux *and* the BIOS)
```sh
ssh -F … opi "sudo python3 ~/rig-tools/keysend.py type 'ls -la'"
ssh -F … opi "sudo python3 ~/rig-tools/keysend.py press DEL"                 # enter Setup
ssh -F … opi "sudo python3 ~/rig-tools/keysend.py press DOWN DOWN ENTER"
ssh -F … opi "sudo python3 ~/rig-tools/keysend.py combo CTRL ALT DEL"        # reboot
ssh -F … opi "sudo python3 ~/rig-tools/keysend.py script 'type:reboot|press:ENTER'"
```
`keysend.py` runs as root (needs `/dev/hidg0`) and takes an exclusive `flock`, so
concurrent invocations serialise instead of interleaving reports.

### See the screen (Magewell → PNG)
```sh
ssh -F … rpi4 '~/rig-tools/grabframe.sh ~/hw-capture/frame.png'   # flock-serialised
scp -F … rpi4:hw-capture/frame.png ./frame.png                    # pull + view
```
First v4l2 frame is often flagged corrupt / warns `VIDIOC_QBUF`; `grabframe.sh`
grabs several and keeps the last, so the PNG is still good.

### Related: the ECM USB-network link
The gadget also exposes USB-ethernet: opi `usb0 = 192.168.222.2/24`, host expected
at `192.168.222.1`. The host side isn't auto-configured (SystemRescue doesn't bring
up its usb0), so to use it, configure the host NIC (`ip addr add 192.168.222.1/24
dev usb0 && ip link set usb0 up`) — then `ssh`/`ping` between opi and host works.
Handy for a reliable shell into the host without screen-OCR.

---

## 5. Power on/off sequencing

Mains power to the ASUS host is a **Tasmota smart plug `au-plug-10`**
(`au-plug-10.iot.welland.mithis.com`, Tasmota 13.1, no auth). Control via HTTP;
`Power` with no argument is a read-only query:
```sh
H=http://au-plug-10.iot.welland.mithis.com
curl -s "$H/cm?cmnd=Power"           # -> {"POWER":"ON"} | {"POWER":"OFF"}  (query)
curl -s "$H/cm?cmnd=Power%20ON"      # apply AC
curl -s "$H/cm?cmnd=Power%20OFF"     # remove AC
curl -s "$H/cm?cmnd=Power%20TOGGLE"  # cold power-cycle
```
(`PowerOnState:3` = the plug restores its last relay state after its *own* power loss.)

### Cold bring-up order
1. **Control devices first.** `rpi4` (Magewell/serial/power) and `opi` (USB gadget)
   should be up *before* the host powers on, so the emulated keyboard + video are
   present when the host enumerates USB. The opi recreates the gadget automatically
   at each boot (`usb-gadget.service`); confirm `/dev/hidg0` exists and the UDC is
   bound: `ssh -F … opi 'cat /sys/kernel/config/usb_gadget/gadget/UDC'`.
2. **Confirm the serial daemon** owns COM1: `systemctl is-active kgpe-seriald.service`.
3. **Apply AC**: `curl "$H/cm?cmnd=Power%20ON"`. The board POSTs (it powers on when
   AC is applied — governed by BIOS *Restore on AC Power Loss*; leave the plug ON and
   use `reboot`/Ctrl-Alt-Del for warm cycles to avoid the DRAM re-train delay).
4. **POST sequence** (watch on `com1.log`): `BMC is booting, please wait …` →
   (~100–130 s) `BMC failed …` (the AST2050 BMC is worked on separately; the host
   BIOS continues past it) → memory/PCI init → `Press <ESC> to boot` / Setup window
   → PXE (Intel Boot Agent → PXELINUX) → SystemRescue.
5. To **stop in Setup**, spam DEL over serial (or the USB keyboard) across step 4's
   window. Otherwise it network-boots.

### Reboot without a cold cycle
- Warm reboot from the OS: `keysend … script 'type:reboot|press:ENTER'` or
  `keysend … combo CTRL ALT DEL`.
- From Setup: `serialkey press F10 ENTER` (save+reset) or the Exit menu.

---

## 6. Netboot (PXE) context

The host network-boots **SystemRescue** (no local OS). Servers run on `rpi4` as
systemd services on the host-facing NIC (`192.168.77.1`); host gets `192.168.77.138`:
| Service | What |
|---|---|
| `host-pxe.service` | dnsmasq DHCP+TFTP on `eth-host` (`--tftp-no-blocksize` for the Intel Boot Agent) |
| `host-pxe-http.service` | `python3 -m http.server 8080` serving the SystemRescue rootfs |
| `bmc-tftp.service` | dnsmasq TFTP on `eth-bmc` for AST2050 U-Boot/Linux (separate BMC work) |

To also get the **OS console on serial** (so even reboots are serial-only), add
`console=ttyS0,115200` to the PXELINUX `APPEND` in the host-pxe config on `rpi4`
(`/srv/pxe/…`). Not required for BIOS control; optional convenience.

---

## 7. Gotchas / troubleshooting

- **Serial silent despite redirection "on"** → check the *port*: redirection must be
  **COM1 (3F8h)**, which is what `/dev/serial-com1` is wired to (COM2/2F8h is not
  captured). Baud must match the daemon (115200).
- **`pkill -f serialkey.py` returns SSH exit 255** → it matched its *own* argv and
  killed its shell. Use the bracket trick: `pkill -f "[s]erialkey.py"` (same for
  `[k]eysend.py`, `[s]eq`).
- **A muxed SSH channel hangs / exit 255** → `ssh -F … -O exit <host>` to drop the
  master, then reconnect. Keep retrying connectivity; it always comes back.
- **`ffmpeg … VIDIOC_QBUF: Bad file descriptor` / first frame corrupt** → harmless;
  `grabframe.sh` already grabs several frames and keeps the last.
- **Can't enter Setup** → you're outside the POST window; the board waits ~100 s on
  the BMC first. Spam the key continuously across the whole window.
- **Nothing changes when driving serial** → assume a *timing/setup* problem before
  suspecting hardware: raise `serialkey --delay`, re-check the daemon is active, and
  confirm you're reading `com1.log` (not a stale render).

---

## 8. Cheat sheet
```sh
CFG=tmp/hw-access/ssh_config                    # persistent-mux SSH config
# --- serial (preferred) ---
ssh -F $CFG rpi4 'python3 ~/rig-tools/serialscreen.py ~/hw-capture/com1.log --from-last-clear'  # view
ssh -F $CFG rpi4 'python3 ~/rig-tools/serialkey.py press DEL'         # drive (FIFO -> seriald)
# --- usb keyboard + video (fallback) ---
ssh -F $CFG opi  "sudo python3 ~/rig-tools/keysend.py press DEL"      # type (flock)
ssh -F $CFG rpi4 '~/rig-tools/grabframe.sh ~/hw-capture/f.png'        # screenshot (flock)
# --- power ---
curl -s "http://au-plug-10.iot.welland.mithis.com/cm?cmnd=Power"     # query / ON / OFF / TOGGLE
# --- daemon health ---
ssh -F $CFG rpi4 'systemctl is-active kgpe-seriald.service'
ssh -F $CFG opi  'cat /sys/kernel/config/usb_gadget/gadget/UDC'       # keyboard gadget bound?
```
