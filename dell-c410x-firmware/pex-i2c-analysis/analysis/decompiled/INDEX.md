# Decompiled PEX/I2C Functions

Decompiled from Dell C410X BMC firmware (`fullfw` ARM ELF binary).

## Summary

- **Total exported:** 45 functions
- **Failed:** 0 functions
- **Binary:** fullfw (ARM 32-bit LE, not stripped)
- **Processor:** ARM:LE:32:v5t (ARM926EJ-S / ARMv5TEJ)

## Functions by Category

### PEX8696 Register Access

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `read_pex8696_register` | `0x0002ebf0` | 296 | [read_pex8696_register_0002ebf0.c](read_pex8696_register_0002ebf0.c) |
| `read_pex8696_register` | `0x000326ec` | 296 | [read_pex8696_register_000326ec.c](read_pex8696_register_000326ec.c) |
| `read_pex8696_register` | `0x0003675c` | 276 | [read_pex8696_register_0003675c.c](read_pex8696_register_0003675c.c) |
| `write_pex8696_register` | `0x0002ead4` | 276 | [write_pex8696_register_0002ead4.c](write_pex8696_register_0002ead4.c) |
| `write_pex8696_register` | `0x000325d0` | 276 | [write_pex8696_register_000325d0.c](write_pex8696_register_000325d0.c) |
| `write_pex8696_register` | `0x0003687c` | 276 | [write_pex8696_register_0003687c.c](write_pex8696_register_0003687c.c) |

### PEX8696 Slot Power

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `all_slot_power_off` | `0x0002f2fc` | 272 | [all_slot_power_off.c](all_slot_power_off.c) |
| `all_slot_power_off_reg` | `0x0002f188` | 360 | [all_slot_power_off_reg.c](all_slot_power_off_reg.c) |
| `pex8696_slot_power_ctrl` | `0x000332ac` | 676 | [pex8696_slot_power_ctrl.c](pex8696_slot_power_ctrl.c) |
| `pex8696_slot_power_on` | `0x0002fa90` | 440 | [pex8696_slot_power_on.c](pex8696_slot_power_on.c) |
| `pex8696_slot_power_on_reg` | `0x0002f7c4` | 700 | [pex8696_slot_power_on_reg.c](pex8696_slot_power_on_reg.c) |

### PLX EEPROM

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `read_plx_eeprom` | `0x000dd6cc` | 268 | [read_plx_eeprom.c](read_plx_eeprom.c) |
| `write_plx_eeprom` | `0x000dd7f0` | 364 | [write_plx_eeprom.c](write_plx_eeprom.c) |

### PEX8647 Register Access

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `read_pex8647_register` | `0x00036998` | 296 | [read_pex8647_register.c](read_pex8647_register.c) |
| `write_pex8647_register` | `0x00036ad0` | 276 | [write_pex8647_register.c](write_pex8647_register.c) |

### GPU Power Sequencing

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `gpu_power_on_1_5_9_13` | `0x000304b0` | 136 | [gpu_power_on_1_5_9_13.c](gpu_power_on_1_5_9_13.c) |
| `gpu_power_on_2_6_10_14` | `0x00030420` | 136 | [gpu_power_on_2_6_10_14.c](gpu_power_on_2_6_10_14.c) |
| `gpu_power_on_3_7_11_15` | `0x00030390` | 136 | [gpu_power_on_3_7_11_15.c](gpu_power_on_3_7_11_15.c) |
| `gpu_power_on_4_8_12_16` | `0x00030300` | 136 | [gpu_power_on_4_8_12_16.c](gpu_power_on_4_8_12_16.c) |
| `Start_GPU_Power_Sequence` | `0x00033ae8` | 184 | [Start_GPU_Power_Sequence.c](Start_GPU_Power_Sequence.c) |

### I2C Transport

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `PI2CMuxWriteRead` | `0x000256c4` | 264 | [PI2CMuxWriteRead.c](PI2CMuxWriteRead.c) |
| `PI2CWriteRead` | `0x000253c4` | 760 | [PI2CWriteRead.c](PI2CWriteRead.c) |

### PEX8696 Hot-Plug Control

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `pex8696_hp_ctrl` | `0x00031454` | 228 | [pex8696_hp_ctrl.c](pex8696_hp_ctrl.c) |
| `pex8696_hp_off` | `0x000312ec` | 232 | [pex8696_hp_off.c](pex8696_hp_off.c) |
| `pex8696_hp_on` | `0x00031184` | 232 | [pex8696_hp_on.c](pex8696_hp_on.c) |

### PEX Register Dump

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `dump_PEX8696_reg` | `0x00037a98` | 192 | [dump_PEX8696_reg.c](dump_PEX8696_reg.c) |

### PEX Address Mapping

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `get_PEX8696_addr_port` | `0x0002e66c` | 160 | [get_PEX8696_addr_port_0002e66c.c](get_PEX8696_addr_port_0002e66c.c) |
| `get_PEX8696_addr_port` | `0x000317e4` | 312 | [get_PEX8696_addr_port_000317e4.c](get_PEX8696_addr_port_000317e4.c) |
| `get_PEX8696_addr_port` | `0x00037f7c` | 352 | [get_PEX8696_addr_port_00037f7c.c](get_PEX8696_addr_port_00037f7c.c) |

### PEX8696 Multi-Host

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `multi_host_mode_set` | `0x00038230` | 312 | [multi_host_mode_set.c](multi_host_mode_set.c) |
| `pex8647_cfg_multi_host_2_4` | `0x00036ef0` | 296 | [pex8647_cfg_multi_host_2_4.c](pex8647_cfg_multi_host_2_4.c) |
| `pex8647_cfg_multi_host_8` | `0x00036dbc` | 296 | [pex8647_cfg_multi_host_8.c](pex8647_cfg_multi_host_8.c) |
| `pex8647_multi_host_mode_cfg` | `0x00037944` | 312 | [pex8647_multi_host_mode_cfg.c](pex8647_multi_host_mode_cfg.c) |
| `pex8696_cfg_multi_host_2` | `0x00036bec` | 220 | [pex8696_cfg_multi_host_2.c](pex8696_cfg_multi_host_2.c) |
| `pex8696_cfg_multi_host_4` | `0x00036cd4` | 220 | [pex8696_cfg_multi_host_4.c](pex8696_cfg_multi_host_4.c) |
| `pex8696_multi_host_mode_cfg` | `0x00037768` | 448 | [pex8696_multi_host_mode_cfg.c](pex8696_multi_host_mode_cfg.c) |
| `pex8696_multi_host_mode_reg_set` | `0x00037420` | 388 | [pex8696_multi_host_mode_reg_set.c](pex8696_multi_host_mode_reg_set.c) |

### Other

| Function | Address | Size (bytes) | File |
|----------|---------|-------------|------|
| `pex8696_all_slot_off` | `0x000375b8` | 288 | [pex8696_all_slot_off.c](pex8696_all_slot_off.c) |
| `pex8696_all_slot_power_off` | `0x0003836c` | 192 | [pex8696_all_slot_power_off.c](pex8696_all_slot_power_off.c) |
| `pex8696_cfg` | `0x000372ac` | 356 | [pex8696_cfg.c](pex8696_cfg.c) |
| `pex8696_dump` | `0x000371b8` | 240 | [pex8696_dump.c](pex8696_dump.c) |
| `pex8696_un_protect` | `0x0002fdf8` | 248 | [pex8696_un_protect.c](pex8696_un_protect.c) |
| `pex8696_un_protect_reg` | `0x0002fc74` | 372 | [pex8696_un_protect_reg.c](pex8696_un_protect_reg.c) |
| `read_pex_register` | `0x000dd0f8` | 296 | [read_pex_register.c](read_pex_register.c) |
| `write_pex_register` | `0x000dd230` | 276 | [write_pex_register.c](write_pex_register.c) |

## All Functions (Alphabetical)

| # | Function | Address | Size (bytes) | File |
|---|----------|---------|-------------|------|
| 1 | `all_slot_power_off` | `0x0002f2fc` | 272 | [all_slot_power_off.c](all_slot_power_off.c) |
| 2 | `all_slot_power_off_reg` | `0x0002f188` | 360 | [all_slot_power_off_reg.c](all_slot_power_off_reg.c) |
| 3 | `dump_PEX8696_reg` | `0x00037a98` | 192 | [dump_PEX8696_reg.c](dump_PEX8696_reg.c) |
| 4 | `get_PEX8696_addr_port` | `0x0002e66c` | 160 | [get_PEX8696_addr_port_0002e66c.c](get_PEX8696_addr_port_0002e66c.c) |
| 5 | `get_PEX8696_addr_port` | `0x000317e4` | 312 | [get_PEX8696_addr_port_000317e4.c](get_PEX8696_addr_port_000317e4.c) |
| 6 | `get_PEX8696_addr_port` | `0x00037f7c` | 352 | [get_PEX8696_addr_port_00037f7c.c](get_PEX8696_addr_port_00037f7c.c) |
| 7 | `gpu_power_on_1_5_9_13` | `0x000304b0` | 136 | [gpu_power_on_1_5_9_13.c](gpu_power_on_1_5_9_13.c) |
| 8 | `gpu_power_on_2_6_10_14` | `0x00030420` | 136 | [gpu_power_on_2_6_10_14.c](gpu_power_on_2_6_10_14.c) |
| 9 | `gpu_power_on_3_7_11_15` | `0x00030390` | 136 | [gpu_power_on_3_7_11_15.c](gpu_power_on_3_7_11_15.c) |
| 10 | `gpu_power_on_4_8_12_16` | `0x00030300` | 136 | [gpu_power_on_4_8_12_16.c](gpu_power_on_4_8_12_16.c) |
| 11 | `multi_host_mode_set` | `0x00038230` | 312 | [multi_host_mode_set.c](multi_host_mode_set.c) |
| 12 | `pex8647_cfg_multi_host_2_4` | `0x00036ef0` | 296 | [pex8647_cfg_multi_host_2_4.c](pex8647_cfg_multi_host_2_4.c) |
| 13 | `pex8647_cfg_multi_host_8` | `0x00036dbc` | 296 | [pex8647_cfg_multi_host_8.c](pex8647_cfg_multi_host_8.c) |
| 14 | `pex8647_multi_host_mode_cfg` | `0x00037944` | 312 | [pex8647_multi_host_mode_cfg.c](pex8647_multi_host_mode_cfg.c) |
| 15 | `pex8696_all_slot_off` | `0x000375b8` | 288 | [pex8696_all_slot_off.c](pex8696_all_slot_off.c) |
| 16 | `pex8696_all_slot_power_off` | `0x0003836c` | 192 | [pex8696_all_slot_power_off.c](pex8696_all_slot_power_off.c) |
| 17 | `pex8696_cfg` | `0x000372ac` | 356 | [pex8696_cfg.c](pex8696_cfg.c) |
| 18 | `pex8696_cfg_multi_host_2` | `0x00036bec` | 220 | [pex8696_cfg_multi_host_2.c](pex8696_cfg_multi_host_2.c) |
| 19 | `pex8696_cfg_multi_host_4` | `0x00036cd4` | 220 | [pex8696_cfg_multi_host_4.c](pex8696_cfg_multi_host_4.c) |
| 20 | `pex8696_dump` | `0x000371b8` | 240 | [pex8696_dump.c](pex8696_dump.c) |
| 21 | `pex8696_hp_ctrl` | `0x00031454` | 228 | [pex8696_hp_ctrl.c](pex8696_hp_ctrl.c) |
| 22 | `pex8696_hp_off` | `0x000312ec` | 232 | [pex8696_hp_off.c](pex8696_hp_off.c) |
| 23 | `pex8696_hp_on` | `0x00031184` | 232 | [pex8696_hp_on.c](pex8696_hp_on.c) |
| 24 | `pex8696_multi_host_mode_cfg` | `0x00037768` | 448 | [pex8696_multi_host_mode_cfg.c](pex8696_multi_host_mode_cfg.c) |
| 25 | `pex8696_multi_host_mode_reg_set` | `0x00037420` | 388 | [pex8696_multi_host_mode_reg_set.c](pex8696_multi_host_mode_reg_set.c) |
| 26 | `pex8696_slot_power_ctrl` | `0x000332ac` | 676 | [pex8696_slot_power_ctrl.c](pex8696_slot_power_ctrl.c) |
| 27 | `pex8696_slot_power_on` | `0x0002fa90` | 440 | [pex8696_slot_power_on.c](pex8696_slot_power_on.c) |
| 28 | `pex8696_slot_power_on_reg` | `0x0002f7c4` | 700 | [pex8696_slot_power_on_reg.c](pex8696_slot_power_on_reg.c) |
| 29 | `pex8696_un_protect` | `0x0002fdf8` | 248 | [pex8696_un_protect.c](pex8696_un_protect.c) |
| 30 | `pex8696_un_protect_reg` | `0x0002fc74` | 372 | [pex8696_un_protect_reg.c](pex8696_un_protect_reg.c) |
| 31 | `PI2CMuxWriteRead` | `0x000256c4` | 264 | [PI2CMuxWriteRead.c](PI2CMuxWriteRead.c) |
| 32 | `PI2CWriteRead` | `0x000253c4` | 760 | [PI2CWriteRead.c](PI2CWriteRead.c) |
| 33 | `read_pex8647_register` | `0x00036998` | 296 | [read_pex8647_register.c](read_pex8647_register.c) |
| 34 | `read_pex8696_register` | `0x0002ebf0` | 296 | [read_pex8696_register_0002ebf0.c](read_pex8696_register_0002ebf0.c) |
| 35 | `read_pex8696_register` | `0x000326ec` | 296 | [read_pex8696_register_000326ec.c](read_pex8696_register_000326ec.c) |
| 36 | `read_pex8696_register` | `0x0003675c` | 276 | [read_pex8696_register_0003675c.c](read_pex8696_register_0003675c.c) |
| 37 | `read_pex_register` | `0x000dd0f8` | 296 | [read_pex_register.c](read_pex_register.c) |
| 38 | `read_plx_eeprom` | `0x000dd6cc` | 268 | [read_plx_eeprom.c](read_plx_eeprom.c) |
| 39 | `Start_GPU_Power_Sequence` | `0x00033ae8` | 184 | [Start_GPU_Power_Sequence.c](Start_GPU_Power_Sequence.c) |
| 40 | `write_pex8647_register` | `0x00036ad0` | 276 | [write_pex8647_register.c](write_pex8647_register.c) |
| 41 | `write_pex8696_register` | `0x0002ead4` | 276 | [write_pex8696_register_0002ead4.c](write_pex8696_register_0002ead4.c) |
| 42 | `write_pex8696_register` | `0x000325d0` | 276 | [write_pex8696_register_000325d0.c](write_pex8696_register_000325d0.c) |
| 43 | `write_pex8696_register` | `0x0003687c` | 276 | [write_pex8696_register_0003687c.c](write_pex8696_register_0003687c.c) |
| 44 | `write_pex_register` | `0x000dd230` | 276 | [write_pex_register.c](write_pex_register.c) |
| 45 | `write_plx_eeprom` | `0x000dd7f0` | 364 | [write_plx_eeprom.c](write_plx_eeprom.c) |
