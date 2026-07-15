# Consolidated OpenBMC feature demo — REAL AST2050 silicon (2026-07-15)

Full OpenBMC (NFS-root, `openbmc-hwpass`) booted on the real ASUS KGPE-D16 /
Aspeed AST2050 over P2A, running **kernel `6.6.70-dirty` = `uImage-kgpe-d16-jfif`**
(this session's kernel: patch 0006 video JFIF wrapping + the G3 clock / i2c /
w83795-hwmon / KCS-LPC-clock patches). Features exercised **together** on one live
boot, mostly over **IPMI-over-LAN** (RMCP+/`lanplus`) from the RPi4 bridge →
BMC `192.168.66.2`. Raw transcript: [`consolidated-silicon-demo.txt`](consolidated-silicon-demo.txt).

| Feature | Demonstrated on silicon | Evidence |
|---|---|---|
| **F5 IPMI over LAN** (remote) | ✅ `ipmitool -I lanplus` mc info answered | Manufacturer 2623 **ASUSTek**, Product **0x0d16** (KGPE-D16), IPMI 2.0 |
| **F5b host-KCS IPMI** | ✅ `phosphor-ipmi-kcs@ipmi-kcs3` + `phosphor-ipmi-host` **active** | `systemctl is-active` = active |
| **F1 system identification** | ✅ FRU inventory over LAN | Board **ASUSTeK KGPE-D16**, serial `KGPED16-OPENBMC-0001`, PN `90-MSVDR0-G0UAY0Z` |
| **F3 sensors** | ✅ 18 sensors, **live values** | FAN1 **2700 RPM**, CPU_DIODE **52.12 °C**, P12V **13.76 V**, P5V/P3V3 3.26 V, VBAT 3.33 V (W83795 over G3 i2c) |
| **F2 chassis power** | ✅ chassis status read over LAN | System Power off, Restore Policy always-off |
| **F4 Serial-over-LAN** | ✅ SOL config over LAN | Enabled=true, Force Encryption, ADMINISTRATOR |
| **F8 KVM video** | ✅ (separate boot) `/dev/video0` → directly-decodable JPEG | [`../real-hw-video/silicon-direct-jpeg.png`](../real-hw-video/silicon-direct-jpeg.png) |
| **BMC State** | ✅ `xyz.openbmc_project.State.BMC` **active** | `systemctl is-active` = active |

Live sensor values (fan RPM, CPU temp, voltage rails) confirm the G3 i2c timing
fix (patch 0005) + the W83795 modern-hwmon registration (patch 0003) work on
silicon — the readings are no longer `ns`.

## Rig notes (for reproduction)

- **Host access** (P2A boot): `sshpass -p systemrescue ssh root@192.168.77.138`
  from the Pi; culvert at `/root/culvert-g3` (snapshot cached at Pi
  `~/culvert-g3-snapshot.tgz`). Boot: `ddr2-init-p2a.py` → `p2a-image-boot.py
  --image tmp/raptor-uboot.bin` → `linux-boot.py … --no-initrd` with the NFS-root
  bootargs.
- **NFS export fix applied** (`/srv/nfs/openbmc-hwpass`): the image ships an empty
  stub `etc/default/obmc/gpio/gpio_defs.json`, so the legacy
  `org.openbmc.control.Power@.service` (`power_control.exe`) crash-loops and its
  coredumps storm the NFS root (load → 9, SSH banner-timeouts). Masked the `@0`
  **instance** (`ln -s /dev/null …/org.openbmc.control.Power@0.service`) and set
  coredump `Storage=none`. NB: do **not** mask the `@` *template* — that disturbs
  the unit graph and delays `dropbear`.
- **64 MB reality**: the full image is heavy for 64 MB; the box is slow during the
  systemd startup storm (SSH refused/late for ~30 s) but settles (~24 MB
  available). Query IPMI **over LAN** for reliability rather than `-I open` on the
  BMC. `-I open` (host-local KCS) belongs on the **x86 host**, not the BMC.
