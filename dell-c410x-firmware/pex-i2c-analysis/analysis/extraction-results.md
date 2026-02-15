# Firmware Extraction Results

Extracted from `dell-c410x-firmware/backup/c410xbmc135.zip` on 2026-02-16.

**Source:** `C410XBMC135/fw_img/BM3P135.pec` (10,385,880 bytes)
**SquashFS:** Found at offset `0x0018A258` in the .pec file (889 inodes)
**Tool:** `dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py`

## Primary Target: fullfw

```
File: fullfw
Size: 1,240,476 bytes (1.2 MB)
MD5:  7203fba7055c7f7a29eb64e1ac96199d
Type: ELF 32-bit LSB executable, ARM, version 1 (ARM),
      dynamically linked, interpreter /lib/ld-linux.so.2,
      for GNU/Linux 2.4.3, not stripped
```

### ELF Header

```
  Magic:   7f 45 4c 46 01 01 01 61 00 00 00 00 00 00 00 00
  Class:                             ELF32
  Data:                              2's complement, little endian
  Version:                           1 (current)
  OS/ABI:                            ARM
  ABI Version:                       0
  Type:                              EXEC (Executable file)
  Machine:                           ARM
  Version:                           0x1
  Entry point address:               0xacbc
  Start of program headers:          52 (bytes into file)
  Start of section headers:          1031700 (bytes into file)
  Flags:                             0x202, GNU EABI, software FP
  Size of this header:               52 (bytes)
  Size of program headers:           32 (bytes)
  Number of program headers:         6
  Size of section headers:           40 (bytes)
  Number of section headers:         27
  Section header string table index: 24
```

**Key observation:** The binary is **not stripped**, meaning it retains symbol names.
This is critical for reverse engineering -- we can identify functions like
`pex8696_slot_power_on`, `pex8696_hp_ctrl`, etc. directly from the symbol table.

### Identical copies in sbin/

The following files are identical to `fullfw` (same MD5 `7203fba7055c7f7a29eb64e1ac96199d`):
- `sbin/fullfw` (1,240,476 bytes)
- `sbin/ipmiSystemCallAgent` (1,240,476 bytes)
- `sbin/ipmi_monitor` (1,240,476 bytes)

This is the Avocent MergePoint pattern: a single binary installed under multiple
names, using `argv[0]` to determine its role (fullfw, IPMI system call agent,
or IPMI monitor).

## All Extracted sbin/ Binaries

| File | Size (bytes) | MD5 | Stripped? |
|------|-------------|-----|-----------|
| HDimg.sh | 1,085 | `0183f4c59d3cb937dad3be73e1b5ba4a` | (shell script) |
| SerRedir | 9,020 | `ba387d099921be60cdb6c7cc2a86614a` | stripped |
| aim | 56,705 | `d9d95ff8c80979ffa0a6fb4a61ece836` | not stripped |
| aim_config_get_bool | 3,940 | `51b1a1c59ac4c7f566b0f0aafe718c72` | stripped |
| aim_config_get_int | 3,904 | `983237014616eca3e8a9faebc01c6e57` | stripped |
| aim_config_get_int64 | 3,924 | `4be58ca3b4163bf35e20e8cbee8c8d33` | stripped |
| aim_config_get_str | 3,908 | `a2c6c1bb1d92c8a844f7b66b19743911` | stripped |
| aim_config_get_str_n | 4,052 | `f7f3b63c4e852def49b12b7c89c00182` | stripped |
| aim_config_set_bool | 4,184 | `9443a000019ba45661b52b9f79346615` | stripped |
| aim_config_set_int | 4,272 | `8f0d1bcf00fea28ef8db98416465ea11` | stripped |
| aim_config_set_int64 | 4,312 | `11300a322adc9d919fef0425ba2134a4` | stripped |
| aim_config_set_str | 4,064 | `2b81ddbfedea175f99038cfe2f15baf4` | stripped |
| aim_config_set_str_n | 6,543 | `46c0a103fb89a7f563e6913f653d9b08` | not stripped |
| alertmgr | 19,864 | `08b12a20ebc1caa1d0dd1b3383116d4f` | stripped |
| avct_control | 15,736 | `d7652827f92b6ac9db741c1445bb7715` | stripped |
| avct_server | 226,432 | `40341820a94faa18e94cba9dd46be112` | stripped |
| avctfwupdate | 10,455 | `9fda4ad2732697260b6e111dd773132b` | not stripped |
| dhcp6c | 180,933 | `25e9875d63aefcb41d97724ae9fa5790` | not stripped |
| dosfsck | 53,661 | `287c8bfa76025b7d0ee70c901a75f16f` | not stripped |
| ethtool | 111,381 | `56ddbf8d7af34a07a03fedf44a2145b6` | not stripped |
| fsck.msdos | 53,661 | `287c8bfa76025b7d0ee70c901a75f16f` | not stripped |
| fsck.vfat | 53,661 | `287c8bfa76025b7d0ee70c901a75f16f` | not stripped |
| fullfw | 1,240,476 | `7203fba7055c7f7a29eb64e1ac96199d` | not stripped |
| fwu | 77,105 | `981c1db1d62e96441603d3fe90ddc834` | not stripped |
| ifenslave | 23,323 | `9ca1b207f31dc68c49549e1663aa76f4` | not stripped |
| ifplugd | 31,133 | `d7f55c3583e27260d9e98a0b2961b6ee` | not stripped |
| ifplugstatus | 15,106 | `d67b7c7164c3b242b63b1b747c4598f4` | not stripped |
| ip6tables | 648,432 | `454f7c3737032729c51ac5339effd686` | stripped (static) |
| ipmiSystemCallAgent | 1,240,476 | `7203fba7055c7f7a29eb64e1ac96199d` | not stripped |
| ipmi_gateway | 15,819 | `f13713b2914819c5691f884dbc635757` | not stripped |
| ipmi_monitor | 1,240,476 | `7203fba7055c7f7a29eb64e1ac96199d` | not stripped |
| iptables | 653,988 | `1cad2508392ceedb40bffc1b665cdb37` | stripped (static) |
| mkdosfs | 32,553 | `688faf8380763d40923eea372b2a6203` | not stripped |
| mkfs.msdos | 32,553 | `688faf8380763d40923eea372b2a6203` | not stripped |
| mkfs.vfat | 32,553 | `688faf8380763d40923eea372b2a6203` | not stripped |
| msmtp | 94,972 | `54d00b9a2ffb3d37bab3e1bfc3b5e596` | not stripped |
| sm | 138,392 | `4be40a5a1f73e314d9876e268ccf967d` | stripped |
| snmptrap | 9,176 | `41c43464eb73a4341318b3fb16cd6f6f` | stripped |
| waitforaim | 4,572 | `da14f978f7d88cf7f2a947ff3933ec01` | stripped |
| waitforsm | 7,250 | `fdd7fbf01e1a1adfd09f93e51bcf8877` | not stripped |
| watchdog | 7,019 | `d9aca9828a1f91ea38c56bc6fd5c6020` | not stripped |

## Extracted Kernel Modules (lib/modules/)

| Module | Size (bytes) | MD5 | Description |
|--------|-------------|-----|-------------|
| aess_biospostdrv.ko | 20,668 | `e8f3366acd5f3ebbe923d39832a24f42` | BIOS POST code driver |
| aess_cryptodrv.ko | 28,456 | `664b8a8d6b8db5ef2deccc698fad9261` | Crypto engine driver |
| aess_dynairqdrv.ko | 23,792 | `444186097f0ff3d69be0d8b5a443f7e0` | Dynamic IRQ driver |
| aess_eventhandlerdrv.ko | 13,288 | `17ff9b3c61ae8380e1a9735a290f5d3d` | Event handler driver |
| aess_fansensordrv.ko | 18,132 | `00e055c65475e0f8f94e23e03e50f04d` | Fan sensor driver |
| aess_gpiodrv.ko | 29,012 | `97f2b812ccae1f74f42fec6899cbf30c` | GPIO driver |
| aess_i2cdrv.ko | 61,980 | `b1ce11cfb762937533c7f359a74a97cc` | **I2C driver (key for PEX analysis)** |
| aess_kcsdrv.ko | 45,424 | `46f5b934d5b41fb2b9bce2828a344185` | KCS (Keyboard Controller Style) driver |
| aess_memdrv.ko | 22,104 | `522f89cb5c9f452f2a2b72faea6859b9` | Memory driver |
| aess_pecisensordrv.ko | 22,528 | `e4240ad1b952444bf5a30f4b4d526be8` | PECI sensor driver |
| aess_pwmdrv.ko | 14,108 | `1c0b2805d2ef3f1a8313da51f0209435` | PWM driver |
| aess_video.ko | 47,812 | `197a888de2c59ebda0a957a3c55a8e1b` | AST2050 video driver |
| bonding.ko | 118,980 | `b5f8c9d433c30f0cc14b7b0fba732190` | Network bonding |
| g_ast2050_udc.ko | 26,324 | `0383a38239dce4d69d857fc672ac8282` | AST2050 USB Device Controller |
| g_composite.ko | 23,228 | `e5deb953370e03e5f21bf4f7becd294f` | USB Composite gadget |
| g_kbdmouse.ko | 24,296 | `82e93a9d4596ebca860f85316bb66797` | USB HID keyboard/mouse gadget |
| g_mass_storage.ko | 46,412 | `c8f4b51933da4b0cf4d814c96cd363dd` | USB Mass Storage gadget |
| ncsi_protocol.ko | 16,956 | `faada1cd4a2634da3daeab451ee93022` | NC-SI (Network Controller Sideband Interface) |
| vkcs.ko | 7,420 | `47ef11c1d7080e1fbe0c1d6d035bc909` | Virtual KCS driver |

## Notes

- All binaries are 32-bit ARM ELF, compiled for GNU/Linux 2.4.3
- The `fullfw` binary uses software floating point (Flags: 0x202)
- `aess_i2cdrv.ko` is the AST2050 I2C engine driver used by fullfw to talk to the PEX switches
- The `sm` binary (138 KB, stripped) is likely the "Session Manager" for the Avocent management interface
- `aim` is the Avocent Infrastructure Manager
- `avct_server` (226 KB) is the Avocent server process for remote management

## Regeneration

To regenerate these files:
```bash
uv run dell-c410x-firmware/pex-i2c-analysis/tools/extract_fullfw.py
```
