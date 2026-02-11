# Dell C410X -- Complete GPIO Pin Mapping

## Overview

The Dell C410X BMC uses GPIO pins from two sources:

1. **38 on-chip GPIO pins** on the Aspeed AST2050 SoC itself, accessed through the
   Linux kernel driver `/dev/aess_gpiodrv` via ioctl calls from the `fullfw` binary.

2. **80 off-chip GPIO pins** on five NXP PCA9555 16-bit I2C GPIO expander chips,
   accessed over I2C using the `PCA9555GPIOInit/Set/Clear/Get` driver functions.

Together these 118 GPIO lines control every physical aspect of the chassis: front-panel
LEDs, power sequencing, button inputs, card presence detection, fan status indication,
and PSU monitoring.

---

## Part 1: Aspeed AST2050 On-Chip GPIO Pins

The AST2050 organizes its GPIOs into groups of 8 pins named by letter (GPIOA[7:0],
GPIOB[7:0], etc.). Each group of 4 letters shares a 32-bit register bank. The firmware
accesses these through the AESS kernel driver, passing the ASCII letter of the group
(e.g., 'A' = 0x41) as part of the ioctl command.

### GPIOA -- System Interrupt Inputs

These pins are active-low inputs with interrupt-on-change enabled. They connect to
interrupt output pins (#INT) of I2C devices, allowing the BMC to respond immediately
when a device signals an event rather than constantly polling.

| Pin | Bit Mask | Device ID | Connected To | What It Does |
|-----|----------|-----------|-------------|--------------|
| **GPIOA4** | 0x0010 | 0x0005 | PCA9555 #INT at bus 0xF6, addr 0x20 | **GPU card presence change interrupt.** When any of the 16 PCIe slots has a graphics card inserted or removed, the PCA9555 at address 0x20 on I2C bus 0xF6 (which monitors all 16 PRSNT# signals) pulls this pin low. The BMC's interrupt handler then reads the PCA9555 input registers to determine which specific slot changed, and logs a "GPU plug" or "GPU unplug" event to the System Event Log (SEL). If a card was removed while powered, the firmware also triggers an emergency slot power-off sequence for that slot. |
| **GPIOA5** | 0x0020 | 0x0008 | PCA9555 #INT at bus 0xF1, addr 0x20 | **PSU presence/failure interrupt.** When any of the four hot-swappable power supplies is inserted, removed, or experiences an AC or DC failure, the PCA9555 at address 0x20 on I2C bus 0xF1 asserts this interrupt. The handler reads the PSU status register (lower nibble = 4 PSU present/fail bits), compares with the previous state, and logs insertion/removal events. On PSU failure, the firmware checks whether enough good PSUs remain to power the active GPUs -- if not (e.g., only 1 PSU left but 8+ GPUs running), it initiates an emergency system power-off via `OEM_Chassis_Control(0)` to prevent hardware damage. |

### GPIOB -- Hardware Event Notification Inputs

Eight input pins with interrupt-on-change enabled, monitoring various hardware status
signals. Most connect to I2C device interrupt lines or external logic signals.

| Pin | Bit Mask | Device ID | Connected To | What It Does |
|-----|----------|-----------|-------------|--------------|
| **GPIOB0** | 0x0100 | 0x0009 | ADT7462 #1 THERM/INT output | **Thermal management chip #1 alert.** The first ADT7462 (behind PCA9544A mux channel 0xB0 on bus 0xF1) asserts this pin when any of its monitored temperatures (Board Temp 1, 2, or 3) crosses a programmed threshold, or when a fan tachometer (FAN 1, 2, 5, or 6) reports a speed below the minimum RPM limit. The interrupt handler reads the ADT7462 status registers to identify the specific alert source and logs the event to the SEL. |
| **GPIOB1** | 0x0200 | 0x000A | ADT7462 #2 THERM/INT output | **Thermal management chip #2 alert.** Same as GPIOB0 but for the second ADT7462 (mux channel 0xB8), which monitors Board Temp 4, 5, 6 and fans FAN 3, 4, 7, 8. |
| **GPIOB2** | 0x0400 | 0x000B | PMBus ALERT# from PSU bus | **Power supply PMBus alert.** The four hot-swappable PSUs communicate status over PMBus (an I2C-based protocol). When any PSU detects an internal fault (over-temperature, over-current, fan failure inside the PSU), it asserts the shared PMBus ALERT# line connected to this pin. The handler performs a PMBus Alert Response Address (ARA) transaction to identify which PSU raised the alert, then reads its specific status registers to determine the fault type (AC input loss, DC output fault, internal thermal shutdown). This is separate from the coarser PSU present/fail detection on GPIOA5 -- PMBus alerts provide granular fault diagnostics. |
| **GPIOB3** | 0x0800 | 0x000C | PCA9548 mux #1 or #2 interrupt | **Per-slot temperature sensor alert.** The 16 TMP100 temperature sensors (one per PCIe slot) sit behind two PCA9548 8-channel I2C muxes on bus 0xF4. When a TMP100 detects its temperature has crossed the programmed alert threshold (indicating a GPU is overheating), the alert propagates through the PCA9548 mux to this interrupt pin. The handler sequentially selects each mux channel to poll the TMP100 alert status register and identify which slot triggered the alert. |
| **GPIOB4** | 0x1000 | 0x000D | PCA9555 #INT at bus 0xF6, addr 0x22 | **GPU attention button interrupt.** The C410X has per-slot "attention" buttons (one for each of the 16 PCIe slots) used for PCIe hot-plug operations. When an administrator presses the attention button on a specific slot, the PCA9555 at address 0x22 on bus 0xF6 (which monitors all 16 button inputs) pulls this pin low. The handler reads the 2-byte button state to identify which slot's button was pressed, and if exactly one button is pressed, initiates the slot hot-plug power sequence for that slot (power-on if the slot was off, or a graceful power-down if it was on). The `Slot_Pwr_Btn_Trigger()` function explicitly rejects simultaneous multi-button presses as invalid. |
| **GPIOB5** | 0x2000 | 0x000E | PCA9555 #INT at bus 0xF6, addr 0x23 | **Slot status change interrupt.** The PCA9555 at address 0x23 on bus 0xF6 is a pure-input device monitoring 16 per-slot status signals (such as power-good indicators from each slot's voltage regulator, or MRL -- Manual Retention Latch -- sensor signals indicating whether the physical card retainer is open or closed). When any slot's status signal changes, this interrupt fires and the handler reads the expander to determine which slot and what changed. |
| **GPIOB6** | 0x4000 | 0x000F | PEX8696 PCIe switch interrupt | **Primary PCIe switch event.** The PLX PEX8696 96-lane PCIe switch (which fans out the host PCIe link to the 16 slots) has an interrupt output that signals link-level events: a downstream port completing link training (a new GPU has been enumerated), a link going down (card removed or faulted), or a hot-plug command completion. The handler reads PEX8696 hot-plug status registers over I2C (bus 0xF3) to manage the PCIe link state machine. |
| **GPIOB7** | 0x8000 | 0x0011 | PEX8647 secondary PCIe switch interrupt | **Secondary PCIe switch event.** The PLX PEX8647 48-lane PCIe switch handles the upstream link to the host server via iPass cables. This interrupt signals cable connect/disconnect events and link training status changes on the upstream ports. The handler reads PEX8647 registers to update the `Multi_Host_Cfg` state, which tracks how many host links are active and in what configuration (1x16, 2x8, or 4x4 lane mapping). |

### GPIOE -- Mixed Control and Status Signals

A mix of outputs (active drive) and inputs used for system control functions.

| Pin | Bit Mask | Dir | Device ID | Connected To | What It Does |
|-----|----------|-----|-----------|-------------|--------------|
| **GPIOE0** | 0x0001 | Out | 0x0015 | BMC system ready indicator | **BMC initialization complete signal.** Directly driven by firmware after all IO tables are loaded, all drivers initialized, and the sensor polling loop is running. External logic or a status LED may monitor this pin to indicate the BMC is fully operational. Also serves as the IRQ source for the primary system interrupt (IRQ entry 0 in the IO table), using the AST2050's ability to interrupt on output pin state changes. |
| **GPIOE1** | 0x0002 | Out | 0x0012 | PS_ON# control buffer enable | **Power supply master enable.** Controls the buffer that drives the PS_ON# signal to all four PSU bays. When asserted (low), the buffer is enabled and the PS_ON# state from the PCA9555 on bus 0xF1 (bit 4) reaches the PSUs. When deasserted (high), the buffer is disabled, forcing PS_ON# high (inactive) regardless of the PCA9555 state, which acts as a hardware safety interlock preventing accidental power-on. |
| **GPIOE2** | 0x0004 | In | 0x0013 | System power good (PWRGD) feedback | **Main 12V power good signal.** An input from the power distribution circuitry indicating that all active PSU outputs have stabilized and the main 12V rail is within regulation. The firmware monitors this pin during the power-on sequence (`Start_System_Power_Sequence`): after asserting PS_ON#, it waits for this pin to go high (power good) before proceeding to enable GPU slot power. If power good doesn't arrive within the timeout, the firmware logs a "System ON fail" event and aborts the power sequence. Also connected to IRQ entry 3 for immediate notification of power loss events (unexpected PWRGD deassertion during operation). |
| **GPIOE3** | 0x0008 | Out | 0x0014 | INA219 power monitor bus enable | **I2C bus 0xF0 isolation control.** Enables or disables the I2C bus buffer that connects the AST2050 to the 16 INA219 current/power sensors on bus 0xF0. During initial power-up (before the 12V rails are stable), this pin is held low to isolate the INA219s, preventing I2C bus errors from unpowered sensors pulling SDA/SCL to invalid levels. Once PWRGD is confirmed, the firmware asserts this pin to connect the INA219 bus. Also deasserted during power-down via `all_ina219_off()`. |
| **GPIOE4** | 0x0010 | In (inverted) | 0x0020 | Front panel power button | **Chassis power button input (active-low, auto-inverted).** Connected to the front-panel momentary pushbutton. The polarity inversion means the firmware reads "1" when the button is pressed. The `Power_Switch_Trigger()` function debounces this input (requiring 3+ consecutive reads of the pressed state) before triggering a power state change. A short press (<4 seconds) initiates a graceful power toggle (on->off or off->on). The actual power button IO index is 0x8053, which maps through IX_fl.bin entry 83 to IO expander sub-index 35. |
| **GPIOE5** | 0x0020 | Out | 0x001E | Front panel ID button LED driver | **Chassis identify button backlight / secondary LED driver.** An output used in conjunction with the ID (identify) LED control. When the chassis identify function is active (triggered by an IPMI Chassis Identify command or the front-panel ID button), this pin is driven to enable a secondary LED element or backlight on the ID button itself. The `ID_LED_off()` function deasserts this via IO index 0x8035 (writing value 1 = off). |

### GPIOF -- PCIe Switch Control

| Pin | Bit Mask | Dir | Device ID | Connected To | What It Does |
|-----|----------|-----|-----------|-------------|--------------|
| **GPIOF6** | 0x4000 | Out | 0x003E | PEX8696 PCIe switch reset | **Primary PCIe switch hardware reset.** Directly drives the #RESET pin on the PLX PEX8696 96-lane PCIe switch. Pulsed low during system initialization to reset the switch to a known state before configuring its 16 downstream ports. Also used during error recovery -- if the PCIe switch enters a fault state, the firmware can reset it without power-cycling the entire chassis. Connected to IRQ entry 4 in the IO table. |

### GPIOI and GPIOJ -- Multi-Host Configuration and System Data Bus

These 16 output pins form a parallel data bus used by the firmware to communicate
status to external logic (such as a CPLD or FPGA on the board) and to read back
multi-host cabling configuration.

| Pin | Bit Mask | Dir | Device ID | Function |
|-----|----------|-----|-----------|----------|
| **GPIOI0** | 0x0001 | Out | 0x0021 | Multi-host data bit 0 -- iPass cable configuration readback. The `get_mode_cfg_ipass_gpio()` function reads PEX8647 registers to determine host link topology and outputs the result on these pins. Bit 0 indicates whether iPass cable port 1 has an active link. |
| **GPIOI1** | 0x0002 | Out | 0x0022 | Multi-host data bit 1 -- iPass cable port 2 link status. |
| **GPIOI2** | 0x0004 | Out | 0x0023 | Multi-host data bit 2 -- iPass cable port 3 link status. |
| **GPIOI3** | 0x0008 | Out | 0x0024 | Multi-host data bit 3 -- iPass cable port 4 link status. |
| **GPIOI4** | 0x0010 | Out | 0x0025 | Multi-host data bit 4 -- combined link width indicator (bit 0). Together with bits 5-7, encodes the negotiated PCIe link width: x1, x4, x8, or x16 per upstream port. |
| **GPIOI5** | 0x0020 | Out | 0x0026 | Multi-host data bit 5 -- link width indicator (bit 1). |
| **GPIOI6** | 0x0040 | Out | 0x0027 | Multi-host data bit 6 -- link width indicator (bit 2). |
| **GPIOI7** | 0x0080 | Out | 0x0028 | Multi-host data bit 7 -- link width indicator (bit 3). |
| **GPIOJ0** | 0x0100 | Out | 0x0029 | System status data bit 0 -- GPU power state summary. The firmware outputs a compressed representation of which GPU slots are currently powered on. Used by board-level logic to coordinate power sequencing with external systems. |
| **GPIOJ1** | 0x0200 | Out | 0x002A | System status data bit 1 -- GPU power group 2 state. |
| **GPIOJ2** | 0x0400 | Out | 0x002B | System status data bit 2 -- GPU power group 3 state. |
| **GPIOJ3** | 0x0800 | Out | 0x002C | System status data bit 3 -- GPU power group 4 state. |
| **GPIOJ4** | 0x1000 | Out | 0x002D | System status data bit 4 -- PSU status summary (bit 0). Encodes the 4-PSU presence/health state for external monitoring. |
| **GPIOJ5** | 0x2000 | Out | 0x002E | System status data bit 5 -- PSU status summary (bit 1). |
| **GPIOJ6** | 0x4000 | Out | 0x002F | System status data bit 6 -- thermal alert summary. Asserted when any temperature sensor is in warning or critical state. |
| **GPIOJ7** | 0x8000 | Out | 0x0030 | System status data bit 7 -- general fault indicator. Asserted when any hardware subsystem is in a fault condition (combines fan fail, thermal alert, PSU fail, and GPU power fault into a single summary bit). |

### GPIOM and GPION -- System Power Control Outputs

These pins directly control the system power state and hardware resets.

| Pin | Bit Mask | Dir | Device ID | Connected To | What It Does |
|-----|----------|-----|-----------|-------------|--------------|
| **GPIOM0** | 0x0001 | Out | 0x0031 | PS_ON# signal (active-low) | **Master power supply turn-on signal.** When driven low (via the GPIOE1-controlled buffer), all installed PSUs begin delivering 12V power. When driven high, PSUs go to standby mode (5Vsb only). This is the primary power control pin, toggled by `ps_on_pull_down()` (power on) and `ps_on_pull_up()` (power off). The actual control path goes through a PCA9555 on bus 0xF1 (bit 4 of the output register), but GPIOM0 provides the enable gate. |
| **GPIOM1** | 0x0002 | Out | 0x003C | System reset output | **Board-level hardware reset.** Directly drives the system reset net that resets all non-BMC logic on the board: the PEX8696 and PEX8647 PCIe switches, the I2C mux chips, and other board-level logic. Used during initialization and error recovery. Distinct from the per-PCIe-switch reset on GPIOF6 -- this resets everything except the BMC itself. |
| **GPION4** | 0x1000 | Out | 0x003D | PEX8647 secondary switch reset | **Secondary PCIe switch hardware reset.** Drives the #RESET pin on the PLX PEX8647 48-lane PCIe switch (the upstream bridge to the host server). Pulsed during initialization after GPIOM1 system reset completes, giving the PEX8647 time to load its configuration from EEPROM before releasing reset. |
| **GPION5** | 0x2000 | Out | 0x0010 | Slot power enable master | **GPU slot power sequencing gate.** A master enable that controls whether the PEX8696 PCIe switch's hot-plug controller is allowed to deliver power to downstream slots. The firmware asserts this pin before initiating the staggered 4-phase GPU power-on sequence (groups 1/5/9/13, then 2/6/10/14, then 3/7/11/15, then 4/8/12/16) and deasserts it during emergency power-off to immediately cut all slot power regardless of the PEX8696's hot-plug state machine. |
| **GPION6** | 0x4000 | Out | 0xF640 | Fan tachometer input selector | **Fan monitoring mux select.** The C410X has 8 physical fans but the ADT7462 chips have only 4 tachometer inputs each. This pin controls a hardware multiplexer that selects which set of fan tachometer signals is routed to the ADT7462 TACH inputs. The firmware alternates this pin between reads to poll all 8 fans across two measurement passes. |

---

## Part 2: PCA9555 I2C GPIO Expander Pins

Five PCA9555 chips provide 80 additional GPIO pins. Each PCA9555 has two 8-bit ports
(Port 0 and Port 1) for 16 pins total. These are accessed over I2C using the
`G_sPCA9555_I2CGPIO_IOAPI` driver functions.

### PCA9555 #1 -- GPU Card Presence Detect (Bus 0xF6, 7-bit Address 0x20)

This chip monitors the PCIe PRSNT# (present) signal from all 16 GPU slots. Each PCIe
slot has a physical pin that is pulled low by the card's edge connector when a card is
fully seated. The PCA9555 reads these 16 signals and the firmware reads both ports in
a single I2C transaction via `read_gpu_present()` (function at 0x00035f14).

The PRSNT# signals are **active-low**: a low level means "card present." The firmware
inverts the read value so that a "1" bit means "present" in software.

| Port | Bit | Pin | Connected To |
|------|-----|-----|-------------|
| **Port 0** | 0 | P0.0 | **Slot 1 PRSNT#** -- PCIe x16 slot 1 card presence. Low = GPU/accelerator card physically seated in slot 1. The `Is_GPU_Present(0)` function reads this bit (inverted) to check if slot 1 is occupied. |
| | 1 | P0.1 | **Slot 2 PRSNT#** -- Slot 2 card presence. |
| | 2 | P0.2 | **Slot 3 PRSNT#** -- Slot 3 card presence. |
| | 3 | P0.3 | **Slot 4 PRSNT#** -- Slot 4 card presence. |
| | 4 | P0.4 | **Slot 5 PRSNT#** -- Slot 5 card presence. |
| | 5 | P0.5 | **Slot 6 PRSNT#** -- Slot 6 card presence. |
| | 6 | P0.6 | **Slot 7 PRSNT#** -- Slot 7 card presence. |
| | 7 | P0.7 | **Slot 8 PRSNT#** -- Slot 8 card presence. |
| **Port 1** | 0 | P1.0 | **Slot 9 PRSNT#** -- Slot 9 card presence. |
| | 1 | P1.1 | **Slot 10 PRSNT#** -- Slot 10 card presence. |
| | 2 | P1.2 | **Slot 11 PRSNT#** -- Slot 11 card presence. |
| | 3 | P1.3 | **Slot 12 PRSNT#** -- Slot 12 card presence. |
| | 4 | P1.4 | **Slot 13 PRSNT#** -- Slot 13 card presence. |
| | 5 | P1.5 | **Slot 14 PRSNT#** -- Slot 14 card presence. |
| | 6 | P1.6 | **Slot 15 PRSNT#** -- Slot 15 card presence. |
| | 7 | P1.7 | **Slot 16 PRSNT#** -- Slot 16 card presence. |

**Interrupt output (#INT)** connects to **GPIOA4** on the AST2050, providing immediate
notification of any card insertion or removal event.

When the interrupt fires, the firmware:
1. Reads both PCA9555 ports (2 bytes = 16 presence bits)
2. Compares with `GPU_Present_Previous` (stored at 0x10a3f7)
3. For each changed bit, logs either "GPU plug_log" or "GPU unplug_log" to the SEL
4. If a card was removed from a powered slot, initiates `slot_power_off()` for that slot
5. Updates the IPMI discrete sensor 0xA0-0xAF (PCIe Presence) readings

### PCA9555 #2 -- Slot Status Signals (Bus 0xF6, 7-bit Address 0x21)

This chip provides per-slot power-good feedback and additional status signals. All 16
pins are configured as inputs with polarity inversion enabled (active-low signals read
as "1" in software).

| Port | Bit | Pin | Connected To |
|------|-----|-----|-------------|
| **Port 0** | 0 | P0.0 | **Slot 1 PWRGD** -- 12V power good feedback from slot 1's voltage regulator. High when the slot's power rail is stable and within regulation. The firmware checks this after enabling slot power to confirm the GPU received clean power. |
| | 1 | P0.1 | **Slot 2 PWRGD** |
| | 2 | P0.2 | **Slot 3 PWRGD** |
| | 3 | P0.3 | **Slot 4 PWRGD** |
| | 4 | P0.4 | **Slot 5 PWRGD** |
| | 5 | P0.5 | **Slot 6 PWRGD** |
| | 6 | P0.6 | **Slot 7 PWRGD** |
| | 7 | P0.7 | **Slot 8 PWRGD** |
| **Port 1** | 0 | P1.0 | **Slot 9 PWRGD** |
| | 1 | P1.1 | **Slot 10 PWRGD** |
| | 2 | P1.2 | **Slot 11 PWRGD** |
| | 3 | P1.3 | **Slot 12 PWRGD** |
| | 4 | P1.4 | **Slot 13 PWRGD** |
| | 5 | P1.5 | **Slot 14 PWRGD** |
| | 6 | P1.6 | **Slot 15 PWRGD** |
| | 7 | P1.7 | **Slot 16 PWRGD** |

**Interrupt output (#INT)** connects to **GPIOB5** on the AST2050.

### PCA9555 #3 -- GPU Attention Buttons and Slot Power Control (Bus 0xF6, 7-bit Address 0x22)

This chip serves a dual role: some pins are inputs monitoring per-slot attention buttons,
and other pins are outputs controlling per-slot power enable signals. The firmware reads
button state via `get_gpu_attention()` (function at 0x00031fb4) using the I2C address
0x44 (8-bit) on bus 0xF6.

| Port | Bit | Pin | Dir | Connected To |
|------|-----|-----|-----|-------------|
| **Port 0** | 0 | P0.0 | In | **Slot 1 attention button** -- Physical pushbutton on the chassis near slot 1. Pressing it requests a PCIe hot-plug operation for that slot. Active-low (pressed = 0). The `Slot_Pwr_Btn_Trigger()` function identifies which single button was pressed (rejects multi-button presses) and initiates the slot power sequence. |
| | 1 | P0.1 | In | **Slot 2 attention button** |
| | 2 | P0.2 | In | **Slot 3 attention button** |
| | 3 | P0.3 | In | **Slot 4 attention button** |
| | 4 | P0.4 | In | **Slot 5 attention button** |
| | 5 | P0.5 | In | **Slot 6 attention button** |
| | 6 | P0.6 | In | **Slot 7 attention button** |
| | 7 | P0.7 | In | **Slot 8 attention button** |
| **Port 1** | 0 | P1.0 | In | **Slot 9 attention button** |
| | 1 | P1.1 | In | **Slot 10 attention button** |
| | 2 | P1.2 | In | **Slot 11 attention button** |
| | 3 | P1.3 | In | **Slot 12 attention button** |
| | 4 | P1.4 | In | **Slot 13 attention button** |
| | 5 | P1.5 | In | **Slot 14 attention button** |
| | 6 | P1.6 | In | **Slot 15 attention button** |
| | 7 | P1.7 | In | **Slot 16 attention button** |

**Interrupt output (#INT)** connects to **GPIOB4** on the AST2050.

When an attention button is pressed:
1. GPIOB4 interrupt fires
2. Firmware reads 2 bytes from PCA9555 at 0x22 -> `GPU_Attention_Buffer` at 0x10a3cf
3. `Slot_Pwr_Btn_Trigger()` counts set bits -- must be exactly 1
4. If the slot is off: initiates `gpu_power_attention_pulse()` to power on
5. If the slot is on: initiates graceful slot power-off sequence

### PCA9555 #4 -- Per-Slot Status LEDs (Bus 0xF6, 7-bit Address 0x23)

This chip has all 16 pins configured as inputs in the IO table. These are dedicated
per-slot status monitoring pins.

| Port | Bit | Pin | Connected To |
|------|-----|-----|-------------|
| **Port 0** | 0 | P0.0 | **Slot 1 MRL (Manual Retention Latch) sensor** -- Detects whether the physical card retention bracket is in the locked or unlocked position. Open = card can be removed; Closed = card is locked in place. Used in conjunction with the attention button for safe hot-plug: the firmware only allows card removal when the MRL is open. |
| | 1 | P0.1 | **Slot 2 MRL sensor** |
| | 2 | P0.2 | **Slot 3 MRL sensor** |
| | 3 | P0.3 | **Slot 4 MRL sensor** |
| | 4 | P0.4 | **Slot 5 MRL sensor** |
| | 5 | P0.5 | **Slot 6 MRL sensor** |
| | 6 | P0.6 | **Slot 7 MRL sensor** |
| | 7 | P0.7 | **Slot 8 MRL sensor** |
| **Port 1** | 0 | P1.0 | **Slot 9 MRL sensor** |
| | 1 | P1.1 | **Slot 10 MRL sensor** |
| | 2 | P1.2 | **Slot 11 MRL sensor** |
| | 3 | P1.3 | **Slot 12 MRL sensor** |
| | 4 | P1.4 | **Slot 13 MRL sensor** |
| | 5 | P1.5 | **Slot 14 MRL sensor** |
| | 6 | P1.6 | **Slot 15 MRL sensor** |
| | 7 | P1.7 | **Slot 16 MRL sensor** |

**Interrupt output (#INT)** connects to **GPIOB5** (shared with PCA9555 #2).

### PCA9555 #5 -- System Management GPIO (Bus 0xF1, 7-bit Address 0x20)

This chip sits on I2C bus 0xF1 (the thermal management bus, separate from the slot
management bus 0xF6). It provides miscellaneous system-level control and status signals
including PSU management, fan LED control, and front-panel LED outputs.

| Port | Bit | Pin | Dir | Connected To |
|------|-----|-----|-----|-------------|
| **Port 0** | 0 | P0.0 | In | **PSU 1 present/fail** -- Active-low presence and DC good signal for PSU bay 1. Low = PSU installed and DC output is good. Read by `io_expander_psu_present_fail()` which masks the lower nibble of Port 0 to get 4 PSU status bits. |
| | 1 | P0.1 | In | **PSU 2 present/fail** -- PSU bay 2 status. |
| | 2 | P0.2 | In | **PSU 3 present/fail** -- PSU bay 3 status. |
| | 3 | P0.3 | In | **PSU 4 present/fail** -- PSU bay 4 status. |
| | 4 | P0.4 | Out | **PS_ON# control bit** -- The firmware writes this bit to control the PS_ON# signal that turns all PSUs on (bit=0) or off (bit=1). `ps_on_pull_down()` clears bit 4 (ANDs with ~0x10) to power on; `ps_on_pull_up()` sets bit 4 (ORs with 0x10) to power off. This is the I2C-controlled half of the PS_ON# path; GPIOE1 on the AST2050 provides the hardware enable gate. |
| | 5 | P0.5 | Out | **PSU fan speed control** -- PWM or discrete signal to the PSU internal fans. Some enterprise PSUs accept an external fan speed override signal. |
| | 6 | P0.6 | Out | **System status summary output** -- Active-low output driven by the firmware when any critical error exists. May connect to an external system monitoring connector. |
| | 7 | P0.7 | Out | **BMC heartbeat** -- Toggled periodically by the firmware's watchdog task. An external circuit can monitor this pin to detect BMC firmware hangs (if the pin stops toggling, the BMC is unresponsive). |
| **Port 1** | 0 | P1.0 | Out | **Fan 1 bicolor LED** -- Green/red per-fan status indicator for fan bay 1. Controlled by `FAN_LED_Green(0)` / `FAN_LED_Red(0)` via IO index 0x8036, which maps through IX_fl.bin to this PCA9555 output. Value 0 = green (fan running normally), value 1 = red (fan failed or below minimum RPM). The indicator is physically located on the fan tray or the rear panel near the fan bay. |
| | 1 | P1.1 | Out | **Fan 2 bicolor LED** -- IO index 0x8037. Green = normal, red = failed. |
| | 2 | P1.2 | Out | **Fan 3 bicolor LED** -- IO index 0x8038. |
| | 3 | P1.3 | Out | **Fan 4 bicolor LED** -- IO index 0x8039. |
| | 4 | P1.4 | Out | **Fan 5 bicolor LED** -- IO index 0x803A. |
| | 5 | P1.5 | Out | **Fan 6 bicolor LED** -- IO index 0x803B. |
| | 6 | P1.6 | Out | **Fan 7 bicolor LED** -- IO index 0x803C. |
| | 7 | P1.7 | Out | **Fan 8 bicolor LED** -- IO index 0x803D. |

**Interrupt output (#INT)** connects to **GPIOA5** on the AST2050, triggering the PSU
present/fail interrupt handler when any of the Port 0 input pins change state.

---

## Part 3: Front-Panel LED System

The C410X front panel has several LED indicators controlled through a combination of
the AST2050's LED driver block (which handles blink timing in hardware) and PCA9555
GPIO outputs (which control the physical LED connections). Most front-panel LEDs are
bicolor (two LED elements in one package) where the firmware selects the color by
driving different control lines.

### System Power LED (Green)

| Property | Value |
|----------|-------|
| **Color** | Green (single color) |
| **Location** | Front panel, left side |
| **IO indices** | 0x802C (LED blink controller), 0x803E (PCA9555 physical output) |
| **IX_fl.bin mapping** | Entry 44 -> driver type 0x19, sub-index 29 (LED controller); Entry 62 -> driver type 0x0F, sub-index 11 (I/O expander) |
| **Control functions** | `SYS_PWR_LED_ON()`, `SYS_PWR_LED_OFF()`, `SYS_PWR_LED_Blink()` |
| **State variable** | `LED_System_Power_State` at 0x10b794 |

**Behavior:**
| System State | LED State | What It Means |
|-------------|-----------|---------------|
| All PSUs off or not present | **Off** | No power at all -- chassis has no AC input, or all PSU bays are empty. |
| Standby power (5Vsb active, 12V off) | **Steady green** | At least one PSU is installed and has AC input. The BMC is running on 5V standby power. The system is ready to be powered on. |
| System powering on (12V coming up) | **Blinking green** | The firmware has asserted PS_ON# and is waiting for PWRGD. The GPUs are going through the staggered power-on sequence (groups 1/5/9/13, then 2/6/10/14, etc.). |
| System fully on | **Steady green** | All PSUs report power good, GPU power sequencing is complete. |

### System Status LED (Bicolor Amber/Green)

| Property | Value |
|----------|-------|
| **Colors** | Amber + Green (bicolor, two LED elements) |
| **Location** | Front panel, next to power LED |
| **IO indices** | 0x802A (amber element), 0x802B (green element), 0x803F (PCA9555 enable) |
| **IX_fl.bin mapping** | Entry 42 -> type 0x19, sub 30; Entry 43 -> type 0x19, sub 31; Entry 63 -> type 0x0F, sub 13 |
| **Control functions** | `SYS_Status_LED_Amber_ON/OFF/Blink/Blink_Fast()` |
| **State variable** | `LED_System_Status_State` at 0x10b795 |

**Behavior -- `led_system()` priority logic:**

The `led_system()` function (at 0x2bbdc) checks six error arrays in priority order.
The highest-priority active error determines the LED state:

| Priority | LED State | Error Condition | What It Means |
|----------|-----------|----------------|---------------|
| **1 (highest)** | **Amber fast blink** (state=3) | `PSU_Errors[0..3]` -- any PSU has failed | A power supply has experienced an AC input loss (`ac_fail_assertion_log`) or DC output failure (`dc_fail_assertion_log`). If insufficient PSUs remain for the number of active GPUs, the system will emergency power-off. Immediate attention required. |
| **2** | **Amber slow blink** (state=2) | `GPU_Power[0..15]` -- any GPU slot has a power fault | A per-slot INA219 current sensor reported an over-current or under-voltage condition on a GPU slot's 12V rail, or a slot failed to achieve power-good after being enabled. May indicate a faulty GPU card, a short circuit on the PCIe power connector, or a GPU drawing more power than the slot can deliver. |
| **3** | **Steady amber** (state=1) | Any of: `FAN_Speed[0..7]` (fan below minimum RPM), `Board_Temp[0..5]` (ADT7462 over-temperature), `GPU_Temp[0..15]` (TMP100 per-slot over-temperature), `GPU_Watt[0..15]` (per-slot over-power) | A non-critical warning threshold has been crossed. Examples: a fan is spinning slowly (but not stopped), a board region temperature is elevated (but not critical), or a GPU slot is drawing more power than its warning threshold. The system continues operating but the condition should be investigated. |
| **4 (lowest)** | **Off** (state=0) | No errors in any array | All 72 sensors are within normal operating parameters. The chassis is healthy. |

### Chassis Identify LED (Blue)

| Property | Value |
|----------|-------|
| **Color** | Blue (single color) |
| **Location** | Front panel and/or rear panel |
| **IO indices** | 0x8051 (blink pattern), 0x8052 (steady on/off), 0x8035 (PCA9555 physical output) |
| **IX_fl.bin mapping** | Entry 81 -> type 0x19, sub 1; Entry 82 -> type 0x19, sub 33; Entry 53 -> type 0x0F, sub 1 |
| **Control functions** | `ID_LED_on()`, `ID_LED_off()`, `IP_Ctrl_ID_LED_ON/OFF/Blink_Fast()` |
| **State variable** | `ID_Status` at 0x10b821, `g_CHASSIS_IDENTIFY` at 0x10b820 |

**Behavior:**
| Trigger | LED State | What It Means |
|---------|-----------|---------------|
| IPMI Chassis Identify command (timed) | **Blinking blue** | An administrator sent an IPMI "Chassis Identify" command with a timeout (typically 15 seconds). The LED blinks to help identify this specific chassis in a rack full of identical hardware. After the timeout, the LED turns off automatically. The remaining time is tracked in `g_ID_LED_CNT` (at 0x10b81e). |
| IPMI Chassis Identify command (force on) | **Steady blue** | The IPMI command specified "Force Identify On" (indefinite). The LED stays on until explicitly turned off. `g_ID_LED_ALWAYS` flag (at 0x10b81f) is set. |
| Front-panel ID button press | **Blinking blue** | The `ID_Switch_Trigger()` function (reading GPIOE4/IO index 0x8054) detected a button press. Toggles the identify state. |
| Off | **Off** | No identify operation in progress. |

### Per-Fan Status LEDs (8 LEDs, Bicolor Green/Red)

| Property | Value |
|----------|-------|
| **Colors** | Green + Red (bicolor) |
| **Location** | Near each fan bay on the rear panel or fan tray |
| **IO indices** | 0x8036 (Fan 1) through 0x803D (Fan 8) |
| **IX_fl.bin mapping** | Entries 54-61 -> driver type 0x0F, sub-indices 6, 7, 8, 9, 2, 3, 4, 5 |
| **Control functions** | `FAN_LED_Green(n)`, `FAN_LED_Red(n)` via `get_fan_record_id(n)` |
| **State variable** | `LED_FAN_State[8]` at 0x10b77c |

| Fan | IO Index | PCA9555 Pin | Color Value 0 | Color Value 1 |
|-----|----------|-------------|---------------|---------------|
| **Fan 1** | 0x8036 | Bus 0xF1, addr 0x20, Port 1, bit 0 | Green (normal) | Red (failed) |
| **Fan 2** | 0x8037 | Port 1, bit 1 | Green | Red |
| **Fan 3** | 0x8038 | Port 1, bit 2 | Green | Red |
| **Fan 4** | 0x8039 | Port 1, bit 3 | Green | Red |
| **Fan 5** | 0x803A | Port 1, bit 4 | Green | Red |
| **Fan 6** | 0x803B | Port 1, bit 5 | Green | Red |
| **Fan 7** | 0x803C | Port 1, bit 6 | Green | Red |
| **Fan 8** | 0x803D | Port 1, bit 7 | Green | Red |

**Behavior -- `led_fan()` logic:**
- **Green**: Fan tachometer reading is at or above the minimum RPM threshold. Normal operation.
- **Red**: Fan tachometer reading has dropped below the minimum RPM threshold, OR the fan has stopped entirely (0 RPM reading). The `fan_fail[n]` flag (array at 0x10b7b6) is set by the ADT7462 sensor polling code when it detects the low-speed condition.

### Per-GPU-Slot Power Status LEDs (16 LEDs, Bicolor Green/Amber)

| Property | Value |
|----------|-------|
| **Colors** | Green + Amber (bicolor) |
| **Location** | On the chassis rear panel or slot bracket area, one per PCIe slot |
| **IO indices** | 0x8040 (Slot 1) through 0x804F (Slot 16) |
| **IX_fl.bin mapping** | Entries 64-79 -> driver type 0x0F, sub-indices 14-29 |
| **Control functions** | `GPU_PWR_LED_Green(n)`, `GPU_PWR_LED_Amber(n)` via `get_gpu_record_id(n)` |
| **State variable** | `LED_GPU_Power_State[16]` at 0x10b784 |

| Slot | IO Index | Color Value 0 | Color Value 1 |
|------|----------|---------------|---------------|
| **Slot 1** | 0x8040 | Amber (fault) | Green (normal) |
| **Slot 2** | 0x8041 | Amber | Green |
| **Slot 3** | 0x8042 | Amber | Green |
| **Slot 4** | 0x8043 | Amber | Green |
| **Slot 5** | 0x8044 | Amber | Green |
| **Slot 6** | 0x8045 | Amber | Green |
| **Slot 7** | 0x8046 | Amber | Green |
| **Slot 8** | 0x8047 | Amber | Green |
| **Slot 9** | 0x8048 | Amber | Green |
| **Slot 10** | 0x8049 | Amber | Green |
| **Slot 11** | 0x804A | Amber | Green |
| **Slot 12** | 0x804B | Amber | Green |
| **Slot 13** | 0x804C | Amber | Green |
| **Slot 14** | 0x804D | Amber | Green |
| **Slot 15** | 0x804E | Amber | Green |
| **Slot 16** | 0x804F | Amber | Green |

Note the inverted polarity compared to fan LEDs: for GPU LEDs, value 0 = amber (fault)
and value 1 = green (normal). This matches `GPU_PWR_LED_Amber()` writing 0 and
`GPU_PWR_LED_Green()` writing 1.

**Behavior -- `led_gpu_power()` logic:**
- **Green**: Slot is powered and the INA219 current sensor reports normal power consumption. The GPU is operating within its rated power envelope. This is the "hot-plug indicator" for the slot -- green means the slot is live and the card should not be physically removed.
- **Amber**: The `gpu_pwr_error[n]` flag (uint16 array at 0x10b7ca) is set, meaning the slot has a power fault: the INA219 reported over-current, the slot failed to achieve power-good, or the slot was commanded off due to a PSU failure. When amber, the card should be investigated or replaced.

---

## Part 4: Interrupt Routing Summary

The firmware registers 6 interrupt sources through the IRQ entries in IO_fl.bin (type 23).
Each interrupt connects an AST2050 on-chip GPIO input pin to a specific handler routine.

| IRQ # | GPIO Pin | Source Device | When It Fires | Handler Action |
|-------|----------|--------------|---------------|----------------|
| 0 | GPIOA4 | PCA9555 #1 (0xF6:0x20) #INT | GPU card inserted or removed from any of 16 slots | Reads 16-bit presence state, logs plug/unplug events, triggers slot power-off for hot-removed cards |
| 1 | GPIOA5 | PCA9555 #5 (0xF1:0x20) #INT | PSU inserted, removed, or failed | Reads 4-bit PSU status, logs events, initiates emergency shutdown if insufficient PSUs for active GPUs |
| 2 | GPIOB7 | PEX8647 INT output | Upstream PCIe link change (iPass cable connect/disconnect) | Reads PEX8647 registers, updates multi-host configuration state |
| 3 | GPIOE2 | Power distribution PWRGD | System 12V power good asserted or lost | During power-on: confirms PSU output stable; during operation: triggers emergency power-off sequence on unexpected power loss |
| 4 | GPIOF6 | PEX8696 INT output | Downstream PCIe link event (GPU link training complete or link down) | Reads PEX8696 hot-plug status, manages per-slot link state machine |
| 5 | GPIOB4 | PCA9555 #3 (0xF6:0x22) #INT | Per-slot attention button pressed | Reads 16-bit button state, validates single-button press, initiates hot-plug sequence for that slot |

---

## Part 5: Power Sequencing GPIO Flow

The complete power-on sequence uses GPIOs in this order:

```
1. Power button press detected on GPIOE4 (front panel) or IPMI Chassis Control command
         |
2. GPIOE1 asserted (enable PS_ON# buffer)
         |
3. PCA9555 #5, Port 0, bit 4 cleared (PS_ON# driven low through buffer)
   "ps_on_pull_down" -- all PSUs begin delivering 12V
         |
4. Wait for GPIOE2 to go high (PWRGD = system 12V rail stable)
         |
5. GPIOE3 asserted (enable I2C bus 0xF0 buffer to INA219 sensors)
         |
6. GPION5 asserted (enable PEX8696 hot-plug controller)
         |
7. GPU power-on phase 1: slots 1,5,9,13 enabled via PEX8696 I2C (bus 0xF3)
   "gpu_power_on_1_5_9_13" -- gpu_un_protect(0x11)
         |
8. GPU power-on phase 2: slots 2,6,10,14 enabled
   "gpu_power_on_2_6_10_14" -- gpu_un_protect(0x33)
         |
9. GPU power-on phase 3: slots 3,7,11,15 enabled
   "gpu_power_on_3_7_11_15" -- gpu_un_protect(0x77)
         |
10. GPU power-on phase 4: slots 4,8,12,16 enabled
    "gpu_power_on_4_8_12_16" -- gpu_un_protect(0xFF)
         |
11. For each slot: verify PCA9555 #2 per-slot PWRGD, then start INA219 monitoring
         |
12. SYS_PWR_LED changes from blinking green to steady green
    System Status LED stays off (no errors)
    Per-slot GPU LEDs change to steady green as each slot comes online
```

The staggered 4-phase GPU power sequence avoids inrush current spikes. Each phase
enables 4 slots that are physically distributed across the chassis (1,5,9,13 are every
4th slot), spreading the current draw evenly across the power distribution bus.

---

## Appendix: IO Index Cross-Reference

Quick reference for the IO indices used in GPIO and LED operations. Each IO index
has bit 15 set (0x8000), meaning it goes through the IX_fl.bin lookup table. The
lower 10 bits are the IX_fl.bin entry number.

| IO Index | IX Entry | Driver Type | Sub-Index | Used By | Physical Function |
|----------|----------|-------------|-----------|---------|-------------------|
| 0x8000 | 0 | 0x18 (LED) | 0 | GPU presence IRQ | IRQ device for card presence change |
| 0x8001 | 1 | 0x18 (LED) | 1 | Power button IRQ | IRQ device for power button |
| 0x800B | 11 | 0x18 (LED) | 3 | PSU fail handler | IRQ device for PSU failure |
| 0x800C | 12 | 0x18 (LED) | 4 | GPU attention handler | IRQ device for attention buttons |
| 0x802A | 42 | 0x19 (GPIO+) | 30 | `SYS_Status_LED_*` | System status LED amber element |
| 0x802B | 43 | 0x19 (GPIO+) | 31 | `SYS_Status_LED_*` | System status LED green element |
| 0x802C | 44 | 0x19 (GPIO+) | 29 | `SYS_PWR_LED_*` | System power LED blink controller |
| 0x8035 | 53 | 0x0F (IOexp) | 1 | `ID_LED_off` | Chassis identify LED PCA9555 output |
| 0x8036-0x803D | 54-61 | 0x0F (IOexp) | 2-9 | `FAN_LED_*` | Fan 1-8 bicolor status LEDs |
| 0x803E | 62 | 0x0F (IOexp) | 11 | `SYS_PWR_LED_*` | System power LED PCA9555 output |
| 0x803F | 63 | 0x0F (IOexp) | 13 | `SYS_Status_LED_*` | System status LED PCA9555 output |
| 0x8040-0x804F | 64-79 | 0x0F (IOexp) | 14-29 | `GPU_PWR_LED_*` | Slot 1-16 bicolor power LEDs |
| 0x8051 | 81 | 0x19 (GPIO+) | 1 | `ID_LED_on` | Identify LED blink pattern |
| 0x8052 | 82 | 0x19 (GPIO+) | 33 | `ID_LED_on` | Identify LED steady on/off |
| 0x8053 | 83 | 0x0F (IOexp) | 35 | `Power_Switch_Trigger` | Front-panel power button input |
| 0x8054 | 84 | 0x0F (IOexp) | 37 | `ID_Switch_Trigger` | Front-panel identify button input |
