# I2C Address Pattern Scan Results

Automated scan of the Dell C410X BMC `fullfw` ARM binary for known
I2C addresses and PLX register offsets.

- **Binary:** `fullfw` (ARM 32-bit ELF)
- **Tool:** `arm-linux-gnueabi-objdump -d`
- **Total matches:** 742
- **High-confidence matches (in PEX/I2C/GPU functions):** 114
- **Lower-confidence matches (all functions):** 628
- **Distinct constants matched:** 14

> **Note:** Small values like `0x18`, `0x30`, `0x34` are common
> ARM struct offsets. The *high-confidence* matches are those found
> inside functions whose names contain PEX/I2C/GPU/slot keywords.
> Stack/frame-pointer operations, PC-relative loads (offset, not value),
> and frame-pointer arithmetic are filtered out to reduce false positives.

## Summary of Constants Found

| Constant | Value | Category | High-Conf | All | High-Conf Functions |
|----------|-------|----------|-----------|-----|---------------------|
| `PEX8696_GBT_0x30` | `0x30` | I2C Address (GBT) | 28 | 155 | G_sOEMADT7462_I2CFAN_IOAPI, I2CDrvInit, I2CDrvSetBusRecEnable, I2CDrvTransWatch, all_slot_power_off (+15 more) |
| `PEX8696_I2C_0x18` | `0x18` | I2C Address | 18 | 154 | GPU_Plug_Unplug, GPU_Plug_Unplug_Init, GPU_Power_Sequence_Init, I2CDrvBusRecovery, I2CDrvParseBusInfo (+6 more) |
| `I2C_BUS_0xF3` | `0xF3` | I2C Bus | 17 | 19 | all_slot_power_off, dump_PEX8696_reg, get_plx_serial_number, gpu_attention_sequence, gpu_force_power_off (+12 more) |
| `PEX8696_GBT_0x34` | `0x34` | I2C Address (GBT) | 14 | 65 | asMuxReqTable, multi_host_mode_set, pex8696_multi_host_mode_cfg |
| `PEX8696_GBT_0x32` | `0x32` | I2C Address (GBT) | 14 | 32 | asMuxReqTable, multi_host_mode_set, pex8696_multi_host_mode_cfg |
| `PEX8696_I2C_0x19` | `0x19` | I2C Address | 9 | 134 | I2CDrvParseBusInfo, OnSerCmdSetSerMux, hwchUARTGetMux, hwchUARTSOLSetMux, hwchUARTSetMux (+3 more) |
| `PLX_HP_GPIO_0x3E` | `0x3E` | PLX Register | 6 | 17 | OEM_Multi_Host_Mode_HEADER, asMuxReqTable |
| `PEX8696_GBT_0x36` | `0x36` | I2C Address (GBT) | 4 | 13 | SetSOLMuxImp, asMuxReqTable, multi_host_mode_set, pex8696_multi_host_mode_cfg |
| `PEX8696_I2C_0x1B` | `0x1B` | I2C Address | 2 | 96 | I2CDrvTransWatch, get_PEX8696_addr_port |
| `PEX8696_I2C_0x1A` | `0x1A` | I2C Address | 2 | 32 | I2CDrvTransWatch |
| `PLX_EEPROM_DATA_0x264` | `0x264` | PLX Register | 0 | 3 |  |
| `PLX_PORT_CTRL_0x208` | `0x208` | PLX Register | 0 | 15 |  |
| `PLX_PORT_STRIDE_0x1000` | `0x1000` | PLX Register | 0 | 6 |  |
| `PLX_EEPROM_CTRL_0x260` | `0x260` | PLX Register | 0 | 1 |  |

## High-Confidence Matches

These matches are inside functions whose names indicate PEX/I2C/GPU
relevance, making them very likely to be genuine I2C address or PLX
register references.

### I2C Bus

17 high-confidence matches.

| Address | Instruction | Constant | Function |
|---------|-------------|----------|----------|
| `0x0002F34C` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `all_slot_power_off` |
| `0x0002FB28` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `pex8696_slot_power_on` |
| `0x0002FE90` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `pex8696_un_protect` |
| `0x00032CE8` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `gpu_force_power_off` |
| `0x000337D0` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `gpu_power_attention_pulse` |
| `0x00033A70` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `gpu_attention_sequence` |
| `0x000374FC` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `pex8696_multi_host_mode_reg_set` |
| `0x00037854` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `pex8696_multi_host_mode_cfg` |
| `0x000379F4` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `pex8647_multi_host_mode_cfg` |
| `0x00037AF8` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `dump_PEX8696_reg` |
| `0x00037BCC` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `set_PEX8696_reg` |
| `0x00037F04` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `gpu_slot_power_off` |
| `0x000383CC` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `pex8696_all_slot_power_off` |
| `0x000DD768` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `read_plx_eeprom` |
| `0x000DD8EC` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `write_plx_eeprom` |
| `0x000DE814` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `get_plx_serial_number` |
| `0x000DEA58` | `mvn	r3, #12` | `I2C_BUS_0xF3` | `set_plx_serial_number` |

### I2C Address

31 high-confidence matches.

| Address | Instruction | Constant | Function |
|---------|-------------|----------|----------|
| `0x00026280` | `add	r3, r3, #24` | `PEX8696_I2C_0x18` | `I2CDrvBusRecovery` |
| `0x0002629C` | `add	r3, r3, #24` | `PEX8696_I2C_0x18` | `I2CDrvBusRecovery` |
| `0x00026494` | `add	r3, r3, #26` | `PEX8696_I2C_0x1A` | `I2CDrvTransWatch` |
| `0x00026530` | `strb	r3, [r2, #26]` | `PEX8696_I2C_0x1A` | `I2CDrvTransWatch` |
| `0x00026538` | `strb	r3, [r2, #27]` | `PEX8696_I2C_0x1B` | `I2CDrvTransWatch` |
| `0x0002665C` | `strb	r3, [r2, #24]` | `PEX8696_I2C_0x18` | `I2CDrvParseBusInfo` |
| `0x00026664` | `strb	r3, [r2, #25]` | `PEX8696_I2C_0x19` | `I2CDrvParseBusInfo` |
| `0x0002E6CC` | `mvn	r2, #27` | `PEX8696_I2C_0x1B` | `get_PEX8696_addr_port` |
| `0x00031D44` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `io_expander_gpu_attention` |
| `0x00031DB8` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `io_expander_gpu_attention` |
| `0x00031E90` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `io_expander_gpu_attention` |
| `0x00031F24` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `io_expander_gpu_attention` |
| `0x00033510` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `pex8696_slot_power_ctrl` |
| `0x00033B24` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `Start_GPU_Power_Sequence` |
| `0x00034260` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `GPU_Power_Sequence_Init` |
| `0x00034390` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `OEM_GPU_POWER_HEADER` |
| `0x00035EC8` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `io_expander_gpu_present` |
| `0x00036004` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `GPU_Plug_Unplug` |
| `0x00036238` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `GPU_Plug_Unplug_Init` |
| `0x0007E3C0` | `mov	r1, #25` | `PEX8696_I2C_0x19` | `hwchUARTSetMuxInternal` |
| `0x0007E4C8` | `mov	r1, #25` | `PEX8696_I2C_0x19` | `hwchUARTSetMux` |
| `0x0007E5EC` | `mov	r1, #25` | `PEX8696_I2C_0x19` | `hwchUARTGetMux` |
| `0x0007F750` | `mov	r1, #25` | `PEX8696_I2C_0x19` | `hwchUARTSetRoutingMux` |
| `0x0007F824` | `mov	r1, #25` | `PEX8696_I2C_0x19` | `hwchUARTSetParam51Mux` |
| `0x0008294C` | `mov	r1, #25` | `PEX8696_I2C_0x19` | `hwchUARTSOLSetMux` |
| `0x000A6E58` | `mvn	r3, r3, lsl #25` | `PEX8696_I2C_0x19` | `OnSerCmdSetSerMux` |
| `0x000A6E5C` | `mvn	r3, r3, lsr #25` | `PEX8696_I2C_0x19` | `OnSerCmdSetSerMux` |
| `0x000DEE6C` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `OEM_GPU_Init_Set_Hook` |
| `0x000DEEB0` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `OEM_GPU_Init_Set_Hook` |
| `0x000DEEF4` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `OEM_GPU_Init_Set_Hook` |
| `0x000DEF38` | `mov	r1, #24` | `PEX8696_I2C_0x18` | `OEM_GPU_Init_Set_Hook` |

### I2C Address (GBT)

60 high-confidence matches.

| Address | Instruction | Constant | Function |
|---------|-------------|----------|----------|
| `0x000260C0` | `strb	r3, [r2, #48]` | `PEX8696_GBT_0x30` | `I2CDrvSetBusRecEnable` |
| `0x000263D0` | `ldrb	r3, [r3, #48]` | `PEX8696_GBT_0x30` | `I2CDrvTransWatch` |
| `0x000267FC` | `strb	r3, [r2, #48]` | `PEX8696_GBT_0x30` | `I2CDrvInit` |
| `0x0002F1C4` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `all_slot_power_off_reg` |
| `0x0002F354` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `all_slot_power_off` |
| `0x0002F800` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_slot_power_on_reg` |
| `0x0002FB30` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_slot_power_on` |
| `0x0002FCB0` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_un_protect_reg` |
| `0x0002FE98` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_un_protect` |
| `0x00032CF0` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `gpu_force_power_off` |
| `0x00036588` | `and	r3, r3, #48` | `PEX8696_GBT_0x30` | `get_mode_cfg_eeprom_reg` |
| `0x000372D8` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_cfg` |
| `0x000375E4` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_all_slot_off` |
| `0x0003789C` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_multi_host_mode_cfg` |
| `0x000378A8` | `mov	r3, #52` | `PEX8696_GBT_0x34` | `pex8696_multi_host_mode_cfg` |
| `0x000378B4` | `mov	r3, #50` | `PEX8696_GBT_0x32` | `pex8696_multi_host_mode_cfg` |
| `0x000378C0` | `mov	r3, #54` | `PEX8696_GBT_0x36` | `pex8696_multi_host_mode_cfg` |
| `0x00037B00` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `dump_PEX8696_reg` |
| `0x00037BD4` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `set_PEX8696_reg` |
| `0x000382D8` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `multi_host_mode_set` |
| `0x000382E4` | `mov	r3, #50` | `PEX8696_GBT_0x32` | `multi_host_mode_set` |
| `0x000382F0` | `mov	r3, #52` | `PEX8696_GBT_0x34` | `multi_host_mode_set` |
| `0x000382FC` | `mov	r3, #54` | `PEX8696_GBT_0x36` | `multi_host_mode_set` |
| `0x000383D4` | `mov	r3, #48` | `PEX8696_GBT_0x30` | `pex8696_all_slot_power_off` |
| `0x0006C7FC` | `mvn	r2, #54` | `PEX8696_GBT_0x36` | `SetSOLMuxImp` |
| `0x000FCBF4` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `G_sOEMADT7462_I2CFAN_IOAPI` |
| `0x00100229` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x0010023E` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100259` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x0010026E` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x001002A2` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x001002BD` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x001002D2` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x0010052D` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100555` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100578` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x001008A2` | `data byte: 0x36` | `PEX8696_GBT_0x36` | `asMuxReqTable` |
| `0x001008B6` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100A66` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100A8E` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100AAD` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100ACE` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100AEC` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100AEE` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100B06` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100B24` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100B26` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100B35` | `data byte: 0x34` | `PEX8696_GBT_0x34` | `asMuxReqTable` |
| `0x00100C57` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x00100C58` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100C5C` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x00100C5D` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100C61` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x00100C62` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100C66` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x00100C67` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100C6B` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x00100C6C` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |
| `0x00100C70` | `data byte: 0x30` | `PEX8696_GBT_0x30` | `asMuxReqTable` |
| `0x00100C71` | `data byte: 0x32` | `PEX8696_GBT_0x32` | `asMuxReqTable` |

### PLX Register

6 high-confidence matches.

| Address | Instruction | Constant | Function |
|---------|-------------|----------|----------|
| `0x00038F04` | `cmp	r3, #62` | `PLX_HP_GPIO_0x3E` | `OEM_Multi_Host_Mode_HEADER` |
| `0x0010022B` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` | `asMuxReqTable` |
| `0x0010025B` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` | `asMuxReqTable` |
| `0x0010028F` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` | `asMuxReqTable` |
| `0x001002BF` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` | `asMuxReqTable` |
| `0x00100C54` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` | `asMuxReqTable` |

## Hot Functions (High-Confidence)

PEX/I2C/GPU functions ranked by number of distinct constants referenced.

| Function | Distinct Constants | Total Matches | Constants Referenced |
|----------|-------------------|---------------|---------------------|
| `asMuxReqTable` | 5 | 39 | PEX8696_GBT_0x30, PEX8696_GBT_0x32, PEX8696_GBT_0x34, PEX8696_GBT_0x36, PLX_HP_GPIO_0x3E |
| `pex8696_multi_host_mode_cfg` | 5 | 5 | I2C_BUS_0xF3, PEX8696_GBT_0x30, PEX8696_GBT_0x32, PEX8696_GBT_0x34, PEX8696_GBT_0x36 |
| `multi_host_mode_set` | 4 | 4 | PEX8696_GBT_0x30, PEX8696_GBT_0x32, PEX8696_GBT_0x34, PEX8696_GBT_0x36 |
| `I2CDrvTransWatch` | 3 | 4 | PEX8696_GBT_0x30, PEX8696_I2C_0x1A, PEX8696_I2C_0x1B |
| `I2CDrvParseBusInfo` | 2 | 2 | PEX8696_I2C_0x18, PEX8696_I2C_0x19 |
| `all_slot_power_off` | 2 | 2 | I2C_BUS_0xF3, PEX8696_GBT_0x30 |
| `pex8696_slot_power_on` | 2 | 2 | I2C_BUS_0xF3, PEX8696_GBT_0x30 |
| `pex8696_un_protect` | 2 | 2 | I2C_BUS_0xF3, PEX8696_GBT_0x30 |
| `gpu_force_power_off` | 2 | 2 | I2C_BUS_0xF3, PEX8696_GBT_0x30 |
| `dump_PEX8696_reg` | 2 | 2 | I2C_BUS_0xF3, PEX8696_GBT_0x30 |
| `set_PEX8696_reg` | 2 | 2 | I2C_BUS_0xF3, PEX8696_GBT_0x30 |
| `pex8696_all_slot_power_off` | 2 | 2 | I2C_BUS_0xF3, PEX8696_GBT_0x30 |
| `io_expander_gpu_attention` | 1 | 4 | PEX8696_I2C_0x18 |
| `OEM_GPU_Init_Set_Hook` | 1 | 4 | PEX8696_I2C_0x18 |
| `I2CDrvBusRecovery` | 1 | 2 | PEX8696_I2C_0x18 |
| `OnSerCmdSetSerMux` | 1 | 2 | PEX8696_I2C_0x19 |
| `I2CDrvSetBusRecEnable` | 1 | 1 | PEX8696_GBT_0x30 |
| `I2CDrvInit` | 1 | 1 | PEX8696_GBT_0x30 |
| `get_PEX8696_addr_port` | 1 | 1 | PEX8696_I2C_0x1B |
| `all_slot_power_off_reg` | 1 | 1 | PEX8696_GBT_0x30 |
| `pex8696_slot_power_on_reg` | 1 | 1 | PEX8696_GBT_0x30 |
| `pex8696_un_protect_reg` | 1 | 1 | PEX8696_GBT_0x30 |
| `pex8696_slot_power_ctrl` | 1 | 1 | PEX8696_I2C_0x18 |
| `gpu_power_attention_pulse` | 1 | 1 | I2C_BUS_0xF3 |
| `gpu_attention_sequence` | 1 | 1 | I2C_BUS_0xF3 |
| `Start_GPU_Power_Sequence` | 1 | 1 | PEX8696_I2C_0x18 |
| `GPU_Power_Sequence_Init` | 1 | 1 | PEX8696_I2C_0x18 |
| `OEM_GPU_POWER_HEADER` | 1 | 1 | PEX8696_I2C_0x18 |
| `io_expander_gpu_present` | 1 | 1 | PEX8696_I2C_0x18 |
| `GPU_Plug_Unplug` | 1 | 1 | PEX8696_I2C_0x18 |

### Hot Function Details

#### `asMuxReqTable`

- **Distinct constants:** 5
- **Total matches:** 39

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x00100229` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x0010022B` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` |
| `0x0010023E` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100259` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x0010025B` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` |
| `0x0010026E` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x0010028F` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` |
| `0x001002A2` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x001002BD` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x001002BF` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` |
| `0x001002D2` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x0010052D` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100555` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100578` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x001008A2` | `data byte: 0x36` | `PEX8696_GBT_0x36` |
| `0x001008B6` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100A66` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100A8E` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100AAD` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100ACE` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100AEC` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100AEE` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100B06` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100B24` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100B26` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100B35` | `data byte: 0x34` | `PEX8696_GBT_0x34` |
| `0x00100C54` | `data byte: 0x3E` | `PLX_HP_GPIO_0x3E` |
| `0x00100C57` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x00100C58` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100C5C` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x00100C5D` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100C61` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x00100C62` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100C66` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x00100C67` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100C6B` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x00100C6C` | `data byte: 0x32` | `PEX8696_GBT_0x32` |
| `0x00100C70` | `data byte: 0x30` | `PEX8696_GBT_0x30` |
| `0x00100C71` | `data byte: 0x32` | `PEX8696_GBT_0x32` |

#### `pex8696_multi_host_mode_cfg`

- **Distinct constants:** 5
- **Total matches:** 5

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x00037854` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x0003789C` | `mov	r3, #48` | `PEX8696_GBT_0x30` |
| `0x000378A8` | `mov	r3, #52` | `PEX8696_GBT_0x34` |
| `0x000378B4` | `mov	r3, #50` | `PEX8696_GBT_0x32` |
| `0x000378C0` | `mov	r3, #54` | `PEX8696_GBT_0x36` |

#### `multi_host_mode_set`

- **Distinct constants:** 4
- **Total matches:** 4

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x000382D8` | `mov	r3, #48` | `PEX8696_GBT_0x30` |
| `0x000382E4` | `mov	r3, #50` | `PEX8696_GBT_0x32` |
| `0x000382F0` | `mov	r3, #52` | `PEX8696_GBT_0x34` |
| `0x000382FC` | `mov	r3, #54` | `PEX8696_GBT_0x36` |

#### `I2CDrvTransWatch`

- **Distinct constants:** 3
- **Total matches:** 4

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x000263D0` | `ldrb	r3, [r3, #48]` | `PEX8696_GBT_0x30` |
| `0x00026494` | `add	r3, r3, #26` | `PEX8696_I2C_0x1A` |
| `0x00026530` | `strb	r3, [r2, #26]` | `PEX8696_I2C_0x1A` |
| `0x00026538` | `strb	r3, [r2, #27]` | `PEX8696_I2C_0x1B` |

#### `I2CDrvParseBusInfo`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x0002665C` | `strb	r3, [r2, #24]` | `PEX8696_I2C_0x18` |
| `0x00026664` | `strb	r3, [r2, #25]` | `PEX8696_I2C_0x19` |

#### `all_slot_power_off`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x0002F34C` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x0002F354` | `mov	r3, #48` | `PEX8696_GBT_0x30` |

#### `pex8696_slot_power_on`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x0002FB28` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x0002FB30` | `mov	r3, #48` | `PEX8696_GBT_0x30` |

#### `pex8696_un_protect`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x0002FE90` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x0002FE98` | `mov	r3, #48` | `PEX8696_GBT_0x30` |

#### `gpu_force_power_off`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x00032CE8` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x00032CF0` | `mov	r3, #48` | `PEX8696_GBT_0x30` |

#### `dump_PEX8696_reg`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x00037AF8` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x00037B00` | `mov	r3, #48` | `PEX8696_GBT_0x30` |

#### `set_PEX8696_reg`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x00037BCC` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x00037BD4` | `mov	r3, #48` | `PEX8696_GBT_0x30` |

#### `pex8696_all_slot_power_off`

- **Distinct constants:** 2
- **Total matches:** 2

| Address | Instruction | Constant |
|---------|-------------|----------|
| `0x000383CC` | `mvn	r3, #12` | `I2C_BUS_0xF3` |
| `0x000383D4` | `mov	r3, #48` | `PEX8696_GBT_0x30` |

## Potentially Interesting Non-PEX Functions

Functions NOT matching PEX/I2C/GPU keywords that still reference
multiple target constants. These may be undiscovered PEX-related functions
or generic utility functions that happen to use the same values.

| Function | Distinct Constants | Total Matches | Constants Referenced |
|----------|-------------------|---------------|---------------------|
| `PETStructToArray` | 5 | 5 | PEX8696_GBT_0x30, PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1A, PEX8696_I2C_0x1B |
| `RSSPValidateRAKP1Msg` | 4 | 5 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1A, PEX8696_I2C_0x1B |
| `CheckSetSerModemConfigParamSubFnEnable` | 4 | 4 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1A, PEX8696_I2C_0x1B |
| `UserInfoSetUserPWDReq` | 3 | 8 | PEX8696_GBT_0x30, PEX8696_GBT_0x32, PEX8696_I2C_0x19 |
| `RSSPOnSMWaitRAKP1StateRecvRAKP1` | 3 | 8 | PEX8696_GBT_0x34, PEX8696_I2C_0x18, PEX8696_I2C_0x1B |
| `SenMgrGetReading` | 3 | 8 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1A |
| `TermCmdHandlerParse` | 3 | 7 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1B |
| `TermCmdHandlerHeadState` | 3 | 6 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1B |
| `TermCmdHandlerBodyState` | 3 | 6 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1B |
| `TermCmdHandlerBufFullState` | 3 | 5 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1B |
| `FanCtrlAlgInit` | 3 | 5 | PEX8696_GBT_0x30, PEX8696_GBT_0x34, PEX8696_I2C_0x18 |
| `RSSPReplyOpenSessionResp` | 3 | 4 | PEX8696_GBT_0x30, PEX8696_GBT_0x34, PEX8696_I2C_0x18 |
| `OnSingleSessActivateSession` | 3 | 4 | PEX8696_GBT_0x30, PEX8696_I2C_0x1A, PEX8696_I2C_0x1B |
| `TermCmdHandlerTailState` | 3 | 4 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1B |
| `SendRawSensorReadingCmd` | 3 | 3 | PEX8696_GBT_0x30, PEX8696_GBT_0x34, PEX8696_I2C_0x18 |
| `DefaultTableInit` | 3 | 3 | PEX8696_GBT_0x30, PEX8696_GBT_0x34, PEX8696_I2C_0x18 |
| `PEFSendToPETByDefault` | 3 | 3 | PEX8696_I2C_0x18, PEX8696_I2C_0x19, PEX8696_I2C_0x1B |
| `ProchotChecker` | 2 | 11 | PEX8696_GBT_0x30, PEX8696_GBT_0x34 |
| `EventNetChangeCfg` | 2 | 8 | PEX8696_I2C_0x19, PLX_PORT_CTRL_0x208 |
| `FanCtrlAlgHandlerFunc` | 2 | 8 | PEX8696_GBT_0x30, PEX8696_I2C_0x19 |

