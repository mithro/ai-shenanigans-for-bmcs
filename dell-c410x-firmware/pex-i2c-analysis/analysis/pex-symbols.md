# PEX/I2C Symbol Analysis - Dell C410X fullfw

Analysis of symbols from the Dell C410X BMC firmware (`fullfw`) ELF binary
related to PEX8696/PEX8647 PCIe switch control and I2C communication.

- **Total symbols in binary:** 3983
- **PEX/I2C-related symbols:** 209
- **Binary:** `fullfw` (ARM 32-bit ELF, not stripped)
- **Tool:** `arm-linux-gnueabi-nm -n`

## Symbol Type Key

| Type | Meaning |
|------|---------|
| `A` | Absolute |
| `B` | Global BSS (uninitialized data) |
| `D` | Global initialized data |
| `R` | Global read-only data |
| `T` | Global text (function) |
| `U` | Undefined (external) |
| `b` | Local BSS (uninitialized data) |
| `d` | Local initialized data |
| `r` | Local read-only data |
| `t` | Local text (function) |

## PEX8696 Functions

16 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x0002E66C` | 0xA8 | `t` | `get_PEX8696_addr_port` |
| `0x0002EAD4` | 0x11C | `t` | `write_pex8696_register` |
| `0x0002EBF0` | 0x138 | `t` | `read_pex8696_register` |
| `0x0002FC74` | 0x184 | `t` | `pex8696_un_protect_reg` |
| `0x0002FDF8` | 0x110 | `t` | `pex8696_un_protect` |
| `0x000317E4` | 0x14C | `t` | `get_PEX8696_addr_port` |
| `0x000325D0` | 0x11C | `t` | `write_pex8696_register` |
| `0x000326EC` | 0x138 | `t` | `read_pex8696_register` |
| `0x0003675C` | 0x120 | `t` | `read_pex8696_register` |
| `0x0003687C` | 0x11C | `t` | `write_pex8696_register` |
| `0x000371B8` | 0xF4 | `t` | `pex8696_dump` |
| `0x000372AC` | 0x174 | `t` | `pex8696_cfg` |
| `0x000375B8` | 0x130 | `t` | `pex8696_all_slot_off` |
| `0x00037A98` | 0xD4 | `t` | `dump_PEX8696_reg` |
| `0x00037B6C` | 0xD4 | `t` | `set_PEX8696_reg` |
| `0x00037F7C` | 0x174 | `t` | `get_PEX8696_addr_port` |

## PEX8647 Functions

2 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x00036998` | 0x138 | `t` | `read_pex8647_register` |
| `0x00036AD0` | 0x11C | `t` | `write_pex8647_register` |

## PEX Generic / EEPROM Functions

16 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x000DD0F8` | 0x138 | `t` | `read_pex_register` |
| `0x000DD230` | 0x11C | `t` | `write_pex_register` |
| `0x000DD41C` | 0xDC | `t` | `read_plx_eeprom_process` |
| `0x000DD4F8` | 0x110 | `t` | `write_plx_eeprom_process` |
| `0x000DD6CC` | 0x124 | `t` | `read_plx_eeprom` |
| `0x000DD7F0` | 0x188 | `t` | `write_plx_eeprom` |
| `0x000DD978` | 0x74 | `T` | `Get_Data_From_PLX_EEPROM` |
| `0x000DDA18` | 0x78 | `T` | `Set_Data_To_PLX_EEPROM` |
| `0x000DE430` | 0x194 | `t` | `get_plx_serial_number_process` |
| `0x000DE5C4` | 0x1E0 | `t` | `set_plx_serial_number_process` |
| `0x000DE7A4` | 0xF4 | `t` | `get_plx_serial_number` |
| `0x000DE898` | 0x248 | `t` | `set_plx_serial_number` |
| `0x000DEC18` | 0x3C | `T` | `Get_Serial_Number_From_PLX_EEPROM` |
| `0x000DED28` | 0x48 | `T` | `Set_Serial_Number_To_PLX_EEPROM` |
| `0x000DFEE4` | 0xC0 | `T` | `CmdOEMPLXEEPROM` |
| `0x000DFFA4` | 0xC0 | `T` | `CmdOEMPLXEEPROMSerialNumber` |

## I2C Core / Transport

31 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x000250D4` | 0xE4 | `T` | `I2CDrvResetISR` |
| `0x000251B8` | 0x20C | `T` | `PI2CInitialize` |
| `0x000253C4` | 0x300 | `T` | `PI2CWriteRead` |
| `0x000256C4` | 0x10C | `T` | `PI2CMuxWriteRead` |
| `0x000257D0` | 0x27C | `T` | `I2CInit` |
| `0x00025A4C` | 0x5C | `T` | `I2CGetInfo` |
| `0x00025AA8` | 0x154 | `T` | `I2CGetStatus` |
| `0x00025BFC` | 0x21C | `T` | `I2CStart` |
| `0x00025E18` | 0x104 | `T` | `I2CReadMsg` |
| `0x00025F1C` | 0xB0 | `T` | `I2CDrvSuspendBus` |
| `0x00025FCC` | 0x8C | `T` | `I2CDrvResumeBus` |
| `0x00026058` | 0xA0 | `T` | `I2CDrvSetBusRecEnable` |
| `0x000260F8` | 0xC4 | `t` | `I2CDrvResetI2C` |
| `0x000261BC` | 0x168 | `t` | `I2CDrvBusRecovery` |
| `0x00026324` | 0x2C | `t` | `I2CDrvTransTimerFunc` |
| `0x00026350` | 0x23C | `t` | `I2CDrvTransWatch` |
| `0x0002658C` | 0x24 | `T` | `I2CDrvCalcMemSize` |
| `0x000265B0` | 0x10C | `t` | `I2CDrvParseBusInfo` |
| `0x000266BC` | 0x27C | `T` | `I2CDrvInit` |
| `0x000CE8F0` | 0x180 | `t` | `CreatePrivateI2CCh0Queue` |
| `0x000E015C` | 0x88 | `T` | `IsPI2CQueueEmpty` |
| `0x000E01E4` | 0x138 | `T` | `PI2CTask` |
| `0x0010A374` |  | `d` | `S_cI2CDrvBusName` |
| `0x0010B528` |  | `b` | `S_u8I2CDrvOpenState` |
| `0x0010B52C` |  | `b` | `S_u32I2CDrvFD` |
| `0x00111C7C` |  | `b` | `S_txPrivateI2CTask.0` |
| `0x00112634` |  | `B` | `G_asI2CDrvBus` |
| `0x001143D4` |  | `B` | `G_PI2CCh1Semaphore` |
| `0x001143E0` |  | `B` | `G_PI2CCh0MsgQ` |
| `0x001143E4` |  | `B` | `G_I2CCh0Semaphore` |
| `0x001143E8` |  | `B` | `G_PI2CCh0DataB` |

## I2C Mux (PCA9544/PCA9548)

11 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x0003C828` | 0x1AC | `T` | `ParsingMuxTable` |
| `0x0003C9D4` | 0x374 | `T` | `I2CMuxHandler` |
| `0x0007671C` | 0x40 | `T` | `OEMPCA9544MuxInit` |
| `0x0007675C` | 0x40 | `T` | `OEMPCA9544MuxRead` |
| `0x0007679C` | 0x130 | `T` | `OEMPCA9544MuxWrite` |
| `0x000768CC` | 0x40 | `T` | `OEMPCA9548MuxInit` |
| `0x0007690C` | 0x40 | `T` | `OEMPCA9548MuxRead` |
| `0x0007694C` | 0x134 | `T` | `OEMPCA9548MuxWrite` |
| `0x000C0FD0` | 0x20 | `T` | `MuxPositionInit` |
| `0x000C11A0` | 0x94 | `T` | `SerialMuxSetMuxPositionInternal` |
| `0x000C1234` | 0x648 | `T` | `SerialMuxSetMuxPosition` |

## GPU Power Control

22 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x0002BF2C` | 0x100 | `t` | `led_gpu_power` |
| `0x0002EEC0` | 0x114 | `t` | `gpu_power_attention_pulse` |
| `0x0002F188` | 0x174 | `t` | `all_slot_power_off_reg` |
| `0x0002F2FC` | 0x12C | `t` | `all_slot_power_off` |
| `0x0002F7C4` | 0x2CC | `t` | `pex8696_slot_power_on_reg` |
| `0x0002FA90` | 0x1E4 | `t` | `pex8696_slot_power_on` |
| `0x00030184` | 0x50 | `t` | `all_gpu_power_off` |
| `0x00030300` | 0x90 | `t` | `gpu_power_on_4_8_12_16` |
| `0x00030390` | 0x90 | `t` | `gpu_power_on_3_7_11_15` |
| `0x00030420` | 0x90 | `t` | `gpu_power_on_2_6_10_14` |
| `0x000304B0` | 0x90 | `t` | `gpu_power_on_1_5_9_13` |
| `0x000319F8` | 0x118 | `t` | `is_gpu_power_on` |
| `0x000332AC` | 0x2C8 | `t` | `pex8696_slot_power_ctrl` |
| `0x00033600` | 0x33C | `t` | `gpu_power_attention_pulse` |
| `0x00033AE8` | 0xC0 | `t` | `Start_GPU_Power_Sequence` |
| `0x00033E68` | 0x74 | `T` | `Count_GPU_Power_On` |
| `0x00034134` | 0x104 | `T` | `Slot_Pwr_Btn_Trigger` |
| `0x00034238` | 0x74 | `T` | `GPU_Power_Sequence_Init` |
| `0x000342AC` | 0x130 | `T` | `OEM_GPU_POWER_HEADER` |
| `0x00037C40` | 0x26C | `t` | `slot_power_off` |
| `0x00037EAC` | 0xD0 | `t` | `gpu_slot_power_off` |
| `0x0003836C` | 0xD4 | `t` | `pex8696_all_slot_power_off` |

## Hot-Plug Control

3 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x00031184` | 0x168 | `t` | `pex8696_hp_on` |
| `0x000312EC` | 0x168 | `t` | `pex8696_hp_off` |
| `0x00031454` | 0xE8 | `t` | `pex8696_hp_ctrl` |

## Multi-Host Configuration

11 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x00036BEC` | 0xE8 | `t` | `pex8696_cfg_multi_host_2` |
| `0x00036CD4` | 0xE8 | `t` | `pex8696_cfg_multi_host_4` |
| `0x00036DBC` | 0x134 | `t` | `pex8647_cfg_multi_host_8` |
| `0x00036EF0` | 0x134 | `t` | `pex8647_cfg_multi_host_2_4` |
| `0x00037420` | 0x198 | `t` | `pex8696_multi_host_mode_reg_set` |
| `0x000376E8` | 0x80 | `t` | `is_cfg_multi_host_8` |
| `0x00037768` | 0x1DC | `t` | `pex8696_multi_host_mode_cfg` |
| `0x00037944` | 0x154 | `t` | `pex8647_multi_host_mode_cfg` |
| `0x00038230` | 0x13C | `t` | `multi_host_mode_set` |
| `0x00038A74` | 0x24 | `T` | `Multi_Host_Mode` |
| `0x00038A98` | 0x9BC | `T` | `OEM_Multi_Host_Mode_HEADER` |

## PEX/I2C Data / Variables

28 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x0010A3D1` |  | `d` | `PEX8696_Slot_Power` |
| `0x0010A680` |  | `d` | `PEX_Serial_Number_Default` |
| `0x0010A688` |  | `d` | `PEX_Serial_Number` |
| `0x0010B784` |  | `b` | `LED_GPU_Power_State` |
| `0x0010B7CA` |  | `b` | `Error_GPU_Power` |
| `0x0010B847` |  | `b` | `PEX8696_Un_Protect_Index` |
| `0x0010B849` |  | `b` | `PEX8696_GPU_On_Index` |
| `0x0010B84B` |  | `b` | `PEX8696_Command` |
| `0x0010B853` |  | `b` | `PEX8696_Reg_Value` |
| `0x0010B871` |  | `b` | `GPU_Power_Button_Press` |
| `0x0010B883` |  | `b` | `PEX8696_Command` |
| `0x0010B88B` |  | `b` | `PEX8696_Address` |
| `0x0010B88C` |  | `b` | `PEX8696_Port_Number` |
| `0x0010B88D` |  | `b` | `PEX8696_Reg_Value` |
| `0x0010B8BB` |  | `b` | `OEM_Cmd_Slot_Pwr_Btn` |
| `0x0010B8C6` |  | `b` | `Multi_Host_Ctrl` |
| `0x0010B8C7` |  | `b` | `Multi_Host_Cfg` |
| `0x0010B8CB` |  | `b` | `Multi_Host_8647_Cfg` |
| `0x0010B8CD` |  | `b` | `PEX8696_Command` |
| `0x0010B8D5` |  | `b` | `PEX8647_Command` |
| `0x0010B8DD` |  | `b` | `PEX8647_Reg_Value` |
| `0x0010B8E1` |  | `b` | `GPU_Power_Off_PEX8696_Address` |
| `0x0010B8F1` |  | `b` | `GPU_Power_Off_PEX8696_Port_Number` |
| `0x0010B901` |  | `b` | `GPU_Power_Off_Count` |
| `0x0010B902` |  | `b` | `GPU_Power_Off_PEX8696_Command` |
| `0x00111E7E` |  | `b` | `PEX_Command` |
| `0x00111E86` |  | `b` | `PEX_Reg_Value` |
| `0x00111E8A` |  | `b` | `PEX_EEPROM_Value` |

## Serial/SOL Mux (UART)

36 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x00069640` | 0x68 | `T` | `SOLCmdSetSerMux` |
| `0x0006C4D0` | 0x138 | `T` | `SOLForceSetMux` |
| `0x0006C608` | 0x208 | `t` | `SetSOLMuxImp` |
| `0x0006C810` | 0xA8 | `T` | `OnSOLCmdSetSerMux` |
| `0x0006C8B8` | 0x1E0 | `T` | `SOLMuxCallBackFunc` |
| `0x0006CB50` | 0xA0 | `T` | `SOLInitMux` |
| `0x0007E364` | 0x108 | `T` | `hwchUARTSetMuxInternal` |
| `0x0007E46C` | 0x128 | `T` | `hwchUARTSetMux` |
| `0x0007E594` | 0xC4 | `T` | `hwchUARTGetMux` |
| `0x0007F6F4` | 0xCC | `T` | `hwchUARTSetRoutingMux` |
| `0x0007F7C0` | 0xDC | `T` | `hwchUARTSetParam51Mux` |
| `0x000828F0` | 0xC0 | `T` | `hwchUARTSOLSetMux` |
| `0x0008ABD8` | 0x144 | `T` | `RawSOLSetMux` |
| `0x000A0928` | 0xEC | `t` | `SerPowerOffSetMux` |
| `0x000A0A14` | 0xA0 | `t` | `SerPowerOnSetMux` |
| `0x000A0AB4` | 0x78 | `t` | `SerPowerChangeResetMuxBlock` |
| `0x000A26D0` | 0x12C | `T` | `SerResetMux` |
| `0x000A27FC` | 0xB0 | `T` | `SerInitMux` |
| `0x000A2D2C` | 0x100 | `t` | `CheckSerConfigMuxSwitchCtrl` |
| `0x000A3C90` | 0x200 | `t` | `SerCmdSetMuxSwitchCtrl` |
| `0x000A3E90` | 0x4C | `t` | `SerCmdGetMuxSwitchCtrl` |
| `0x000A68A4` | 0xEC | `T` | `SerialChannelMuxCallbackFunc` |
| `0x000A6990` | 0x15C | `T` | `SerForceSetMux` |
| `0x000A6AEC` | 0x460 | `T` | `OnSerCmdSetSerMux` |
| `0x000A6F4C` | 0xFC | `T` | `OnSerCmdSetSerRoutingMux` |
| `0x000C0B50` | 0x480 | `T` | `SerialMuxInit` |
| `0x000C0FF0` | 0x1B0 | `T` | `SerialMuxServiceRegister` |
| `0x000D1F28` | 0x25C | `T` | `CmdSetSerModemMux` |
| `0x000D22E4` | 0x1B4 | `T` | `CmdSetSerRoutingMux` |
| `0x000DBE50` | 0xAC | `T` | `UARTHWSetMux` |
| `0x000DBEFC` | 0x84 | `T` | `UARTHWGetMux` |
| `0x000DC060` | 0xAC | `T` | `UARTHWSetRoutingMux` |
| `0x000DC15C` | 0x8C | `T` | `UARTHWSetParam51Mux` |
| `0x000EA600` | 0x144 | `T` | `RawSerSetMux` |
| `0x000EA744` | 0x144 | `T` | `RawSerSetMuxInternal` |
| `0x000EA888` | 0x13C | `T` | `RawSerGetMux` |

## I2C Sensor/IO APIs

15 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x000FC344` |  | `R` | `G_sLM75_I2CTEMP_IOSAPI` |
| `0x000FC354` |  | `R` | `G_sPCA9555_I2CGPIO_IOAPI` |
| `0x000FCBA4` |  | `R` | `G_sOEMPCA9544_I2CSWITCH_IOAPI` |
| `0x000FCBB0` |  | `R` | `G_sOEMPCA9548_I2CSWITCH_IOAPI` |
| `0x000FCBBC` |  | `R` | `G_sOEMADT7462_I2CADC_IOSAPI` |
| `0x000FCBCC` |  | `R` | `G_sOEMADT7462_I2CTEMP_IOSAPI` |
| `0x000FCBDC` |  | `R` | `G_sOEMADT7462_I2CFAN_IOSAPI` |
| `0x000FCBEC` |  | `R` | `G_sOEMADT7462_I2CFAN_IOAPI` |
| `0x000FCBFC` |  | `R` | `G_sOEMADT7473_I2CTEMP_IOSAPI` |
| `0x000FCC0C` |  | `R` | `G_sOEMINA219_I2CADC_IOSAPI` |
| `0x000FCC1C` |  | `R` | `G_sOEMTMP100_I2CTEMP_IOSAPI` |
| `0x000FCC2C` |  | `R` | `G_sOEMW83792_I2CTEMP_IOSAPI` |
| `0x001015A0` |  | `R` | `G_sGenericAnalog_I2CTEMP_IOSAPI` |
| `0x001015C0` |  | `R` | `G_sGenericAnalog_I2CFAN_IOSAPI` |
| `0x001015E0` |  | `R` | `G_sGenericAnalog_I2CADC_IOSAPI` |

## Other Mux / Misc

18 symbols found.

| Address | Est. Size | Type | Symbol Name |
|---------|-----------|------|-------------|
| `0x000EB64C` | 0x144 | `T` | `RawSetRoutingMux` |
| `0x000EB790` | 0x150 | `T` | `RawSetParam51Mux` |
| `0x000FD701` |  | `R` | `au8SerConfigMuxSwitchCtrlMask` |
| `0x00100154` |  | `R` | `asMuxReqTable` |
| `0x0010B774` |  | `B` | `FanTachMuxFunc` |
| `0x0010B91E` |  | `B` | `G_u8MuxTblHasInit` |
| `0x00111154` |  | `B` | `G_bMuxSwitching2System` |
| `0x00111158` |  | `B` | `G_u32SerialChannelMuxServiceHandle` |
| `0x0011115C` |  | `B` | `G_sSerialChannelMuxCallbackNode` |
| `0x00111C14` |  | `b` | `S_asMuxInfo` |
| `0x00111C34` |  | `b` | `S_txMuxInfoSemaphore` |
| `0x00111E24` |  | `B` | `UARTSetMuxFunc` |
| `0x00111E28` |  | `B` | `UARTSetRoutingMuxFunc` |
| `0x00111E2C` |  | `B` | `UARTSetParam51MuxFunc` |
| `0x00111E30` |  | `B` | `UARTGetMuxFunc` |
| `0x00111E60` |  | `b` | `bAIMSerialMUXRegister.4` |
| `0x00112838` |  | `B` | `G_u8MuxTblRecIdx` |
| `0x00114478` |  | `B` | `G_u16AIMMUXEventID` |
