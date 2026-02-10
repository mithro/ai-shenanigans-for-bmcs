# Dell PowerEdge C410X BMC Firmware - Reverse Engineering Analysis

## Executive Summary

The Dell PowerEdge C410X is a 3U PCIe expansion chassis (not a server) housing up to
16 GPU cards connected to 1-8 host servers via iPass cables. Its Baseboard Management
Controller (BMC) is based on an **Aspeed AST2050** SoC running **Avocent MergePoint**
firmware (built by Avocent, now Vertiv).

This document covers the reverse engineering of BMC firmware version **1.35** (build
7466, dated March 10, 2014).

---

## 1. Hardware Platform

### BMC SoC: Aspeed AST2050

**Identification Evidence:**
- U-Boot banner: `Board: AST2050`
- U-Boot version: `U-Boot 1.2.0 (Oct 27 2010 - 14:05:52) Avocent (0.2.3) EVB`
- Firmware image filename pattern: `firmimg.ast2050`
- Kernel version: `2.6.23.1-ASPEED-v.0.11` (ARM)
- USB driver: `g_ast2050_udc.ko` (AST2050 USB Device Controller)
- Fan register references: `AST2050_FAN_BASE_REG`
- Video driver references: `AST2050_VIDEO_RINGDESCRIPTOR`
- SDR header contains `AST1100v` (AST1100 is the package variant of AST2050)

**AST2050 Key Specifications:**
- ARM926EJ-S CPU core @ 266 MHz
- 32-bit DDR2/DDR3 memory controller
- Integrated 2D VGA (for KVM)
- SPI NOR flash interface
- GPIO controller (multiple banks: A-H, I-L, M-P, Q-T)
- Multi-bus I2C controller (up to 14 buses)
- PWM/Fan tachometer controller
- PECI (Platform Environment Control Interface)
- Dual 10/100 Ethernet MACs
- LPC bus interface (KCS for IPMI)
- USB 2.0 host and device controllers
- Watchdog timer
- Hardware crypto engine

### Flash Memory Layout (SPI NOR)

From U-Boot environment variables:

| Region       | Start Address | Size     | Description                  |
|--------------|---------------|----------|------------------------------|
| U-Boot       | 0x14000000    | ~1 MB    | Bootloader                   |
| Environment  | 0x14020000    | 0x10000  | U-Boot env variables         |
| Kernel       | 0x14100000    | 0x200000 | Linux kernel (gzip, uImage)  |
| RootFS       | 0x14300000    | 0xD00000 | SquashFS root filesystem     |
| Alt RootFS   | 0x10000000    | -        | Secondary rootfs partition   |

Total flash: Detected as STM25P64/STM25P128/S25FL128P/MX25L128D/W25X64 (8-16 MB SPI)

### System Memory

- 96 MB RAM allocated to Linux: `mem=96M`
- Kernel loaded at: `0x41400000`
- RootFS loaded at: `0x42600000`

### Boot Configuration

```
bootargs=root=/dev/mtdblock3 mem=96M console=ttyS0
bootcmd=fwu boot
baudrate=115200
console=ttyS0
```

### Network Interfaces

| Interface | MAC Default        | Type         | Notes                        |
|-----------|--------------------|--------------|------------------------------|
| MAC0      | 00:C0:A8:12:34:56  | RMII_PHY     | Dedicated BMC NIC (eth0)     |
| MAC1      | 00:C0:A8:12:34:57  | (configurable) | Network sharing (eth1)     |

MAC interface types: `0x01: RMII_PHY`, `0x02: INTEL_NCSI`, `0x10: MII_PHY`, `0x20: GMII_PHY`

---

## 2. Firmware Structure

### PEC File Format (_DCSI_ Header)

The `.pec` firmware image uses Dell/Avocent's `_DCSI_` container format:

| Offset | Size  | Field                          | Value (v1.35)            |
|--------|-------|--------------------------------|--------------------------|
| 0x0000 | 6     | Magic                          | `_DCSI_`                 |
| 0x000B | 15    | Product Name                   | `PowerEdge C410X`        |
| 0x001B | 9     | Platform                       | `PowerEdge`              |
| 0x0025 | 4     | Version                        | `1.35`                   |
| 0x002A | 4     | Vendor Signature               | `AVCT` (Avocent)         |
| 0x002F | 12    | Build Timestamp                | `140310120000`           |
| 0x0070 | 4     | Section Marker                 | `AEVB` (Avocent EVB)     |
| 0x0258 | 64    | uImage Header                  | Linux kernel             |
| 0x0298 | ~1.6M | gzip compressed kernel         | vmlinux.bin              |
| 0x18A258 | ~8.3M | SquashFS v3.1 rootfs         | 889 inodes, 128K blocks  |
| 0x9E06CC | ~30K | U-Boot bootloader              | v1.2.0 Avocent           |

### Kernel

- **Format:** uImage (ARM Linux)
- **Load address:** 0x40008000
- **Entry point:** 0x40008000
- **Compression:** gzip
- **Image name:** `arm-linux`
- **Created:** 2010-10-27 (kernel from 2010, rootfs updated in 2014)
- **Decompressed size:** ~3.3 MB

### Root Filesystem

- **Type:** SquashFS v3.1, little endian
- **Size:** ~8.6 MB (8,643,566 bytes)
- **Inodes:** 889
- **Block size:** 128 KB
- **Created:** 2014-03-10

Directory structure:
```
/
├── avct/scripts/        # Avocent utility scripts (cert, file ops)
├── bin/                 # Core binaries (busybox, IPMICmd, MemAccess)
├── dev/                 # Device nodes
├── etc/
│   ├── default/
│   │   ├── certs/       # SSL certificates
│   │   ├── ipmi/evb/    # IPMI config, SDR, FRU, IO tables
│   │   └── networking/  # Network defaults
│   ├── ifplugd/         # Ethernet hotplug
│   ├── init.d/          # Init scripts
│   ├── pam.d/           # PAM config
│   ├── ssh/             # SSH host keys
│   ├── sysapps_script/  # Service start/stop scripts
│   ├── sysconfig/       # Network config (iBMCnet.sh)
│   └── udhcpc/          # DHCP client scripts
├── flash/data0/         # JFFS2 persistent storage mount
├── lib/
│   ├── modules/         # Kernel modules (.ko files)
│   ├── rsyslog/         # Rsyslog plugins
│   └── security/        # PAM modules
├── sbin/                # System daemons and tools
├── usr/
│   ├── local/
│   │   ├── bin/         # App binaries (appweb, ssh, dataserver)
│   │   ├── etc/         # App config (dataserver, appweb)
│   │   ├── lib/         # App libraries
│   │   └── www/         # BMC Web UI (HTML/JS/CSS)
│   └── sbin/            # Network utilities
└── var/                 # Runtime data
```

---

## 3. Kernel Modules (Hardware Drivers)

All modules compiled for `2.6.23.1-ASPEED-v.0.11`:

| Module                    | Size   | Author      | Function                          |
|---------------------------|--------|-------------|-----------------------------------|
| aess_gpiodrv.ko           | 29 KB  | Taiyi Kuo   | GPIO controller driver            |
| aess_i2cdrv.ko            | 62 KB  | -           | Multi-bus I2C with IPMB support   |
| aess_fansensordrv.ko      | 18 KB  | Steven Lai  | Fan tachometer sensor reading     |
| aess_pwmdrv.ko            | 14 KB  | Steven Lai  | PWM duty cycle control for fans   |
| aess_pecisensordrv.ko     | 23 KB  | Ken Lin     | PECI temperature sensor           |
| aess_kcsdrv.ko            | -      | -           | KCS IPMI interface (LPC bus)      |
| aess_memdrv.ko            | -      | -           | Physical memory access (/dev/mem) |
| aess_biospostdrv.ko       | -      | -           | BIOS POST code capture            |
| aess_eventhandlerdrv.ko   | -      | -           | Event/interrupt handling          |
| aess_dynairqdrv.ko        | -      | -           | Dynamic IRQ routing               |
| aess_cryptodrv.ko         | -      | -           | Hardware crypto engine            |
| aess_video.ko             | -      | -           | Video capture for KVM             |
| ncsi_protocol.ko          | -      | -           | NC-SI sideband network mgmt       |
| bonding.ko                | -      | -           | Network interface bonding         |
| g_ast2050_udc.ko          | -      | -           | USB Device Controller             |
| g_composite.ko            | -      | -           | USB composite gadget              |
| g_kbdmouse.ko             | -      | -           | USB keyboard/mouse emulation      |
| g_mass_storage.ko         | -      | -           | USB virtual media                 |
| vkcs.ko                   | -      | -           | Virtual KVM Console Server        |

**Module load order** (from `I_SYS_Drv.sh`):
1. `aess_eventhandlerdrv.ko`
2. `vkcs.ko`
3. `aess_kcsdrv.ko`
4. `aess_memdrv.ko`
5. `aess_biospostdrv.ko`
6. `aess_gpiodrv.ko`
7. `aess_dynairqdrv.ko`
8. `aess_i2cdrv.ko`
9. `aess_pecisensordrv.ko`
10. `aess_cryptodrv.ko`
11. `aess_fansensordrv.ko`
12. `aess_pwmdrv.ko`

---

## 4. Aspeed AST2050 Pin/Peripheral Allocation

### GPIO Controller

The AST2050 GPIO controller is at base address `0x1E780000`. The GPIO pins are
organized in banks of 8 pins (A-H, I-L, M-P, Q-T).

The firmware accesses GPIO through the `aess_gpiodrv.ko` kernel module via
`/dev/aess_gpiodrv`. GPIO operations found in the firmware:

**On-Chip GPIO** (`G_sONCHIP_GPIO_IOAPI`):
- Used directly via `mcddGPIOInit`, `mcddGPIORead`, `mcddGPIOWrite`
- Interrupt support: edge/level configurable per pin
- Reset-tolerant configuration available

**I2C GPIO Expander** (`G_sPCA9555_I2CGPIO_IOAPI`):
- PCA9555 I/O expander chips on I2C bus
- Used for: GPU presence detection, GPU attention buttons, PSU presence/fault
- Functions: `PCA9555GPIOInit`, `PCA9555GPIOSet`, `PCA9555GPIOGet`, `PCA9555GPIOClear`

#### GPIO Functions Identified from Firmware

| Function                        | Type       | Description                           |
|---------------------------------|------------|---------------------------------------|
| `get_mode_cfg_ipass_gpio`       | On-chip    | Read iPass port configuration mode    |
| `io_expander_gpu_present`       | PCA9555    | Read GPU presence in 16 slots         |
| `io_expander_gpu_attention`     | PCA9555    | Read GPU attention button status      |
| `io_expander_psu_present_fail`  | PCA9555    | Read PSU presence and failure status  |
| `GPU_PWR_LED_Green`             | On-chip    | GPU power LED green control           |
| `GPU_PWR_LED_Amber`             | On-chip    | GPU power LED amber control           |
| `led_gpu_power`                 | On-chip    | GPU power status LED control          |
| `ID_Switch_Button`              | On-chip    | Chassis ID button detect              |
| `ID_Switch_Trigger`             | On-chip    | Chassis ID LED trigger                |
| `Power_Switch_Trigger`          | On-chip    | Power button event                    |

### I2C Bus Configuration

The AST2050 I2C controller base is at `0x1E78A000` with 0x40 byte stride per bus.
The firmware references **7 I2C buses** (I2C0 through I2C6):

| Bus  | Base Address | Primary Use                                    |
|------|-------------|------------------------------------------------|
| I2C0 | 0x1E78A000  | Temperature sensors, misc                      |
| I2C1 | 0x1E78A040  | Temperature/voltage sensors                    |
| I2C2 | 0x1E78A080  | PCA9548 mux -> PEX8696 switch, GPU sensors     |
| I2C3 | 0x1E78A0C0  | PCA9548 mux -> INA219 current sensors          |
| I2C4 | 0x1E78A100  | PCA9555 GPIO expanders (GPU/PSU presence)      |
| I2C5 | 0x1E78A140  | PMBus PSU communication                        |
| I2C6 | 0x1E78A180  | IPMB (IPMI bus for inter-BMC communication)    |

### I2C Device Map

Devices identified through firmware string analysis:

| Device Chip  | I2C Address(es) | Bus    | Function                              |
|--------------|-----------------|--------|---------------------------------------|
| **TMP100**   | Various         | I2C0/1 | Board temperature sensors (7 zones)   |
| **LM75**     | Various         | I2C0/1 | Temperature sensor (alt chip)         |
| **ADT7473**  | Various         | I2C0/1 | Temperature sensor + fan control      |
| **ADT7462**  | Various         | I2C0/1 | Temp/voltage/fan monitor combo        |
| **W83792**   | Various         | I2C0/1 | Hardware monitoring IC                |
| **INA219**   | Various x16     | I2C3   | Per-GPU current/power sensor (16x)    |
| **PCA9548**  | Various         | I2C2/3 | 8-channel I2C mux (for GPU buses)     |
| **PCA9544**  | Various         | I2C2   | 4-channel I2C mux                     |
| **PCA9555**  | Various x3+     | I2C4   | 16-bit I/O expander (GPIO)            |
| **PEX8696**  | Via I2C         | I2C2   | PLX/Microsemi PCIe switch config      |
| **PEX8647**  | Via I2C         | I2C2   | PLX PCIe switch (secondary)           |
| **PSU (PMBus)** | 0x58-0x5F    | I2C5   | Power supply units (up to 4)          |
| **EEPROM**   | 0x50+           | I2C0   | MAC address and board config storage  |

#### INA219 Current Sensors (16x for GPU Power)

Each GPU slot has a dedicated Texas Instruments INA219 high-side current/power
monitor connected via PCA9548 I2C mux on I2C bus 3. These provide:
- Shunt voltage measurement (proportional to current)
- Bus voltage measurement
- Power calculation

Functions: `OEMINA219Init`, `OEMINA219Read`, `OEMINA219WriteDrv`, `get_INA219_addr`,
`get_INA219_index`, `write_ina219_register`, `read_ina219_register`

#### PMBus PSU Communication

Power supply units communicate via PMBus protocol on I2C bus 5. The firmware
reads the following PMBus status registers per PSU:

| PMBus Command          | Description                    |
|------------------------|--------------------------------|
| STATUS_BYTE            | Summary status                 |
| STATUS_WORD            | Extended status (2 bytes)      |
| STATUS_VOUT            | Output voltage status          |
| STATUS_IOUT            | Output current status          |
| STATUS_INPUT           | Input status                   |
| STATUS_TEMPERATURE     | Temperature status             |
| STATUS_CML             | Communication/logic status     |
| STATUS_MFR_SPECIFIC    | Manufacturer specific status   |
| STATUS_FANS_1_2        | Fan 1/2 status                 |
| STATUS_FANS_3_4        | Fan 3/4 status                 |
| STATUS_OTHER           | Other status bits              |
| CLEAR_FAULTS           | Clear all fault bits           |

### PWM/Fan Tachometer

The PWM/Fan tachometer controller is at AST2050 base `0x1E789000`:

- **PWM channels:** Configurable frequency and duty cycle
- **Fan tach channels:** RPM measurement from tachometer inputs
- **Fan sensor registers:** `AST2050_FAN_BASE_REG` + offsets 0x00-0x24
  - +0x00 through +0x1C: Individual fan speed registers (8 fans)
  - Additional control/status registers

### PECI Interface

The PECI controller is at `0x1E78B000`:
- Used for reading CPU die temperatures from connected host servers
- Functions: `aess_pecisensordrv.ko` kernel module
- Configurable client address and command codes

### UART Configuration

| Port   | Address     | Function              | Baud Rate |
|--------|-------------|-----------------------|-----------|
| UART0  | 0x1E783000  | Serial console        | 115200    |
| UART1  | 0x1E784000  | SOL (Serial Over LAN) | Various   |

Console: `ttyS0` at 115200 bps, vt100 terminal type

### SCU (System Control Unit) / Pin Muxing

The SCU at `0x1E6E2000` controls pin muxing. The firmware accesses `/dev/mem` to
configure pin functions. Key SCU registers:

| Register    | Address      | Function                    |
|-------------|--------------|-----------------------------|
| SCU80       | 0x1E6E2080   | Multi-function Pin Ctrl 1   |
| SCU84       | 0x1E6E2084   | Multi-function Pin Ctrl 2   |
| SCU88       | 0x1E6E2088   | Multi-function Pin Ctrl 3   |
| SCU8C       | 0x1E6E208C   | Multi-function Pin Ctrl 4   |
| SCU90       | 0x1E6E2090   | Multi-function Pin Ctrl 5   |
| SCU94       | 0x1E6E2094   | Multi-function Pin Ctrl 6   |
| SCU70       | 0x1E6E2070   | Hardware Strap              |

---

## 5. PCIe Switch Fabric

### Switch ICs

The C410X uses two PLX/Microsemi PCIe switch ICs:

1. **PEX8696** - Primary 96-lane PCIe switch
   - Controls all 16 GPU slot power
   - Hot-plug controller for each slot
   - Configured via I2C through PCA9548 mux
   - Functions: `pex8696_slot_power_on`, `pex8696_all_slot_power_off`,
     `pex8696_hp_ctrl`, `pex8696_hp_on`, `pex8696_hp_off`,
     `pex8696_cfg_multi_host_2`, `pex8696_cfg_multi_host_4`

2. **PEX8647** - Secondary PCIe switch
   - Multi-host mode configuration
   - Functions: `pex8647_cfg_multi_host_2_4`, `pex8647_cfg_multi_host_8`,
     `pex8647_multi_host_mode_cfg`

### GPU Power Sequencing

Power is applied to GPUs in groups to prevent inrush current issues:

| Sequence Step | Slots         | Function                     |
|---------------|---------------|------------------------------|
| Step 1        | 1, 5, 9, 13   | `gpu_power_on_1_5_9_13`     |
| Step 2        | 2, 6, 10, 14  | `gpu_power_on_2_6_10_14`    |
| Step 3        | 3, 7, 11, 15  | `gpu_power_on_3_7_11_15`    |
| Step 4        | 4, 8, 12, 16  | `gpu_power_on_4_8_12_16`    |

Power management functions:
- `Start_GPU_Power_Sequence` - Orchestrates the staggered power-on
- `all_gpu_power_off` / `all_slot_power_off` - Emergency power down
- `gpu_force_power_off` / `gpu_force_power_off_reg` - Force power off
- `gpu_over_protect` / `gpu_un_protect` - Over-power protection
- `slot_power_off` / `gpu_slot_power_off` - Individual slot power control
- `Slot_Pwr_Btn_Trigger` / `OEM_Cmd_Slot_Pwr_Btn` - Per-slot power button
- `powermgmt_int_power_on_delay` - Configurable delay between groups

### Port Mapping (iPass to PCIe)

The chassis connects 8 iPass cables from host servers to 16 PCIe slots via
the PEX8696/PEX8647 switch fabric. Mapping is controlled via OEM IPMI command:

**IPMI Command:** NetFn `0x34`, Cmd `0xC8`

Port mapping modes:

**1:4 Mode (default):**
```
iPass1 <-> PCIe 1, 15    iPass5 <-> PCIe 2, 16
iPass2 <-> PCIe 3, 13    iPass6 <-> PCIe 4, 14
iPass3 <-> PCIe 5, 11    iPass7 <-> PCIe 6, 12
iPass4 <-> PCIe 7, 9     iPass8 <-> PCIe 8, 10
```

**1:2 Mode (per iPass pair):**
```
iPass1 <-> PCIe 1, 2, 15, 16    iPass5 <-> None
iPass2 <-> PCIe 3, 4, 13, 14    iPass6 <-> None
iPass3 <-> PCIe 5, 6, 11, 12    iPass7 <-> None
iPass4 <-> PCIe 7, 8, 9, 10     iPass8 <-> None
```

**1:8 Mode (per iPass group):**
```
iPass1 <-> PCIe 1,2,3,4,13,14,15,16    iPass2-6 <-> None
iPass3 <-> PCIe 5,6,7,8,9,10,11,12     iPass4,7,8 <-> None
```

Internal codename: **"Titanium"**

---

## 6. IPMI Sensor Definitions (76 Sensors)

### Temperature Sensors (23 total)

| Sensor ID | Name          | Entity            | Thresholds (approx)     |
|-----------|---------------|-------------------|--------------------------|
| 0x01      | FB Temp       | System Board #1   | Warn: 75C, Fail: 80C    |
| 0x02      | Board Temp 1  | System Board #2   | Warn: 75C, Fail: 80C    |
| 0x03      | Board Temp 2  | System Board #3   | Warn: 75C, Fail: 80C    |
| 0x04      | Board Temp 3  | System Board #4   | Warn: 75C, Fail: 80C    |
| 0x05      | Board Temp 4  | System Board #5   | Warn: 75C, Fail: 80C    |
| 0x06      | Board Temp 5  | System Board #6   | Warn: 75C, Fail: 80C    |
| 0x07      | Board Temp 6  | System Board #7   | Warn: 75C, Fail: 80C    |
| 0x08-0x17 | PCIe 1-16 Temp | Add-in Card #1-16 | Warn: 90C, Fail: 95C   |

### GPU Power Sensors (16 total)

| Sensor ID | Name          | Entity             | Unit | Notes              |
|-----------|---------------|--------------------|------|--------------------|
| 0x50-0x5F | PCIe 1-16 Watt | Add-in Card #17-32 | W  | Via INA219 sensors |

### PSU Power Sensors (4 total)

| Sensor ID | Name          | Entity           | Unit | Notes              |
|-----------|---------------|------------------|------|--------------------|
| 0x60-0x63 | PSU 1-4 Watt  | Power Supply #1-4 | W   | Via PMBus          |

### Fan Sensors (8 total)

| Sensor ID | Name    | Entity   | Unit | Thresholds                  |
|-----------|---------|----------|------|-----------------------------|
| 0x80-0x87 | FAN1-8  | Fan #1-8 | RPM  | Warn min: 1080, Fail: 870   |

### Discrete Sensors (21 total)

| Sensor ID  | Name           | Entity             | Type           |
|------------|----------------|--------------------|----------------|
| 0xA0-0xAF  | PCIe 1-16      | Add-in Card #33-48 | Presence/Status |
| 0x30-0x33  | PSU 1-4        | Power Supply #5-8  | Presence/Status |
| 0x34       | Sys Pwr Monitor | System Board #7   | Power state     |

---

## 7. Software Architecture

### Boot Sequence

1. **U-Boot** → Loads kernel + rootfs from SPI flash
2. **Linux kernel** → Mounts SquashFS rootfs as initrd
3. **rcS** → Sets up environment
4. **preinit.sh** → Mount tmpfs overlays, JFFS2 persistent storage, load drivers
5. **I_SYS_Drv.sh** → Load 12 kernel modules in order
6. **postinit.sh** → Start all BMC services

### Key Daemons

| Daemon      | Binary          | Function                              |
|-------------|-----------------|---------------------------------------|
| fullfw      | /sbin/fullfw    | Core IPMI engine (1.2MB, the biggest) |
| aim         | /sbin/aim       | Avocent Interface Manager             |
| alertmgr    | /sbin/alertmgr  | Event/alert manager                   |
| sm          | /sbin/sm        | Security manager (SSL/certs)          |
| osinet      | /usr/sbin/osinet | Network stack manager                |
| avct_server | /sbin/avct_server | KVM console server                  |
| fwu         | /sbin/fwu       | Firmware update manager               |
| appweb      | /usr/local/bin/appweb | Web server (BMC UI)             |
| dataserver  | /usr/local/bin/dataserver | Data API server              |
| sshd        | /usr/local/sbin/sshd | SSH daemon                       |

### I2C Device Driver API Layers

The firmware uses a layered I2C device driver architecture:

```
Application (fullfw)
    │
    ├── G_sOEMINA219_I2CADC_IOSAPI     (INA219 current sensor)
    ├── G_sOEMADT7473_I2CTEMP_IOSAPI   (ADT7473 temp sensor)
    ├── G_sOEMADT7462_I2CTEMP_IOSAPI   (ADT7462 temp/fan/voltage)
    ├── G_sOEMADT7462_I2CFAN_IOSAPI    (ADT7462 fan section)
    ├── G_sOEMADT7462_I2CADC_IOSAPI    (ADT7462 ADC section)
    ├── G_sOEMTMP100_I2CTEMP_IOSAPI    (TMP100 temp sensor)
    ├── G_sOEMW83792_I2CTEMP_IOSAPI    (Winbond W83792 monitoring)
    ├── G_sLM75_I2CTEMP_IOSAPI         (LM75 temp sensor)
    ├── G_sOEMPCA9544_I2CSWITCH_IOAPI  (PCA9544 4ch mux)
    ├── G_sOEMPCA9548_I2CSWITCH_IOAPI  (PCA9548 8ch mux)
    ├── G_sPCA9555_I2CGPIO_IOAPI       (PCA9555 GPIO expander)
    ├── G_sPMBus_PSU_IOAPI             (PMBus PSU interface)
    ├── G_sONCHIP_GPIO_IOAPI           (On-chip AST2050 GPIO)
    ├── G_sONCHIP_IPMB_IOAPI           (On-chip IPMB interface)
    ├── G_sGenericAnalog_I2CADC_IOSAPI  (Generic ADC)
    ├── G_sGenericAnalog_I2CFAN_IOSAPI  (Generic fan)
    ├── G_sGenericAnalog_I2CTEMP_IOSAPI (Generic temp)
    └── G_sGenericSensor_GPIO_IOSAPI    (Generic GPIO sensor)
         │
         ├── PI2CWriteRead (Private I2C bus access)
         ├── PI2CMuxWriteRead (I2C access through mux)
         └── I2CDrv* (kernel module interface)
              │
              └── /dev/aess_i2cdrv (kernel I2C driver)
```

### BMC Web API

The web UI communicates with the BMC via XML API at `/data`:

| Endpoint                  | Description                      |
|---------------------------|----------------------------------|
| `data?get=fans`           | Fan sensor readings              |
| `data?get=temperatures`   | Temperature sensor readings      |
| `data?get=voltages`       | Voltage sensor readings          |
| `data?get=gpu`            | GPU power consumption            |
| `data?get=powerSupplies`  | PSU status (location, wattage)   |
| `data?get=powerlimit,powerreading` | Total power consumption  |
| `data?set=pwState:N`      | Power control (0=off,1=on,2=cycle) |
| `data?set=setPortMap(...)` | Configure iPass port mapping    |
| `data?set=DoCmd(4,52,200,X,Y)` | Raw IPMI OEM port map command |

### IPMI Device Information

| Field              | Value                |
|--------------------|----------------------|
| Device ID          | 0x20                 |
| Device Revision    | 0x01                 |
| Firmware Major     | 0x01                 |
| Firmware Minor     | 0x35 (v1.35)         |
| IPMI Version       | 0x02 (IPMI 2.0)      |
| Manufacturer ID    | 0x0FA2 (Dell)        |
| Product ID         | 0x0200               |
| Firmware ID        | QOSA1012             |

---

## 8. IPMI Configuration Files

### IO Table Files

These binary files in `/etc/default/ipmi/evb/` define the sensor-to-hardware mapping:

| File              | Size    | Purpose                              |
|-------------------|---------|--------------------------------------|
| IO_fl.bin         | 2,456 B | I/O mapping: sensor to register/bus  |
| IS_fl.bin         | 1,590 B | Sensor initialization parameters     |
| IX_fl.bin         | 344 B   | Sensor index cross-reference         |
| FunctionTable.bin | -       | OEM function dispatch table          |
| oemdef.bin        | 1,710 B | OEM defaults (users, network, etc.)  |
| NVRAM_SDR00.dat   | 3,946 B | Sensor Data Record repository        |
| NVRAM_FRU00.dat   | -       | Field Replaceable Unit data          |
| NVRAM_SEL00.dat   | -       | System Event Log (empty default)     |
| NVRAM_Storage00.dat | -     | IPMI persistent storage              |
| NVRAM_PrivateStorage00.dat | - | OEM private storage              |
| ID_devid.bin      | -       | Device ID response data              |
| FI_fwid.bin       | -       | Firmware ID string (QOSA1012)        |
| bmcsetting        | -       | BMC config (NIC, UART, file paths)   |

### Platform IDs

From `sysid_mapping.lst` and `MemAccess PLATFORM_ID`:

| ID  | Name      | Notes                               |
|-----|-----------|--------------------------------------|
| 240 | Bluefish  | Production platform variant?         |
| 242 | Sneetch   | Production platform variant?         |
| 255 | EVB       | Evaluation board (default firmware)  |

---

## 9. FRU Data

| Field         | Value              |
|---------------|--------------------|
| Manufacturer  | Dell Inc.          |
| Product Name  | PowerEdge C410X    |
| Board Mfg     | Dell Inc.          |

---

## 10. Security Notes

- **Default credentials:** `root` / `root` (found in oemdef.bin)
- **SNMP community:** `public`
- SSH daemon with key generation
- SSL/TLS certificate support
- Two-factor authentication support (tfaValidateUser.sh)
- iptables/ip6tables firewall support
- OpenSSL 0.9.8 (old, known vulnerabilities)
- glibc 2.3.6 (old)

---

## 11. Files Downloaded

| File                                    | Size     | Description               |
|-----------------------------------------|----------|---------------------------|
| c410xbmc135.zip                         | 10.4 MB  | BMC firmware v1.35        |
| c410xbmc134.exe                         | 21.3 MB  | BMC firmware v1.34 (PE32) |
| c410xbmc128.exe                         | 10.5 MB  | BMC firmware v1.28 (PE32) |
| pec410xbmc110.exe                       | 10.7 MB  | BMC firmware v1.10 (PE32) |
| esm_firmware_dell_0132_naa_c410x_bmc.zip | 10.4 MB | BMC firmware v1.32 (ESM)  |
| c410x_scripts.tar.gz                    | 3.5 KB   | Port map + FW upgrade     |
| health_monitor.tar.gz                   | 582 KB   | NVIDIA health monitor     |
