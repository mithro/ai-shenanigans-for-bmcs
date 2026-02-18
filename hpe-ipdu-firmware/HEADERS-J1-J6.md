# HPE Intelligent Modular PDU -- J6 and J1 Extension Bar Bus Headers

## Summary

J6 and J1 are white multi-pin connectors on the HP iPDU Core Unit controller board.
They serve as the **extension bar bus connectors**, providing the internal interface
between the NS9360 controller board and the power distribution / outlet section of
the Core Unit chassis. Through these connectors, the controller board communicates
with and controls the Extension Bars that plug into the Core Unit's IEC C19 outlets.

## Physical Description

| Property | Value |
|----------|-------|
| Ref Des | J1, J6 |
| Connector Colour | White |
| Connector Type | Multi-pin PCB header (exact part number unknown) |
| Location | HP iPDU Core Unit controller board |
| Visible In | Google Photos album "HP PDU AF520A Core Parts" |

The exact pin count, pitch, and connector manufacturer/part number have not yet
been determined from board photos alone. Physical measurement of the board is
required.

## Function

J1 and J6 are the internal bus connectors that link the main controller board (with
the NS9360 CPU, MAXQ3180 power measurement AFE, and associated circuitry) to the
power distribution section of the Core Unit. The power distribution section contains:

- 6x IEC C19 outlets (load segments 1-6)
- 6x circuit breakers (one per load segment)
- Current transformers and voltage sensing circuitry
- PLC (Power Line Communication) coupling circuitry

### Extension Bar Architecture

The HP iPDU uses a **core and stick architecture**:

```
                     Core Unit Controller Board
                      (NS9360, MAXQ3180, etc.)
                            |      |
                           J6      J1
                            |      |
                    Power Distribution Section
                     /    /    |    \    \    \
                   CB1  CB2  CB3  CB4  CB5  CB6    (Circuit Breakers)
                    |    |    |    |    |    |
                   C19  C19  C19  C19  C19  C19    (IEC C19 Outlets)
                    |    |    |    |    |    |
                   Ext  Ext  Ext  Ext  Ext  Ext    (Extension Bars,
                   Bar  Bar  Bar  Bar  Bar  Bar     up to 6 total)
                    |    |    |    |    |    |
                  5xC13 each = up to 30 outlets
```

Each Extension Bar plugs into one of the Core Unit's IEC C19 outlets via an IEC C20
input connector. Up to **6 Extension Bars** can be connected to a single Core Unit,
providing up to **30 IEC C13 outlets** total.

### PLC (Power Line Communication)

Communication between the Core Unit and Extension Bars uses **Power Line
Communication (PLC)** -- data signals are modulated onto the AC power lines. This
means no separate data cable is needed between the Core Unit and Extension Bars;
the IEC C19/C20 power connection carries both AC power and the PLC data signal.

The PLC system enables:

- **Per-outlet switching** -- individual C13 outlets on Extension Bars can be
  remotely switched on/off
- **Per-outlet monitoring** -- voltage, current, power (W/VA), power factor, and
  energy (kWh) per outlet
- **Extension Bar identification** -- the Core Unit discovers which Extension Bars
  are connected and their positions
- **Status indication** -- UID LED activation and power status indication on
  Extension Bars
- **Intelligent Power Discovery (IPD)** -- when used with PLC power cables (blue
  connectors) and HP Common Slot Platinum Power Supplies, the system can
  automatically map server-to-outlet power topology

Evidence for PLC use on this board:
- The **J10 "PLC DIAG"** header on the controller board is explicitly labelled for
  Power Line Communication diagnostics
- Extension Bars have **bright blue PLC IEC C20 input connectors** distinguishing
  them from standard power connectors
- The HP Intelligent Extension Bar (part 627749-001) is described as having a
  "power line communication connector (PLC)"
- PLC power cables with blue connectors are required for Intelligent Power
  Discovery

### Relationship to Other Board Connectors

| Ref Des | Label | Relationship to J1/J6 |
|---------|-------|-----------------------|
| J10 | "PLC DIAG" | PLC diagnostic header -- likely provides test access to the PLC bus signals that pass through J1/J6 |
| J11 | "Mox SPI" | SPI header -- possibly connects to MAXQ3180 power measurement AFE, which processes current/voltage measurements from sensing circuitry connected via J1/J6 |
| J25 | "Digi UART" | Debug UART -- independent of extension bar bus |
| J28 | Pin header | Unknown function |
| J5 | Connector | Unknown function |

## Signal Architecture (Inferred)

The exact pinout of J1 and J6 has not been determined. Based on the board
architecture and iPDU functionality, the connectors likely carry some combination
of the following signal types:

### Power Measurement Signals

The MAXQ3180 3-phase power measurement AFE (U15) measures voltage, current, active
power, reactive power, apparent power, power factor, and frequency. It requires
analog inputs from:

- **Current transformers** (e.g., PT1 KSZT770 2mA:2mA CT) on each load segment
- **Voltage sensing** from the AC mains

These analog sensing signals from the power distribution section likely route
through J1/J6 to reach the MAXQ3180 on the controller board.

### PLC Bus Signals

The PLC modulator/demodulator circuitry on the controller board needs to couple
its data signal onto the AC power lines that feed the IEC C19 outlets. The PLC
coupling path runs through J1/J6 to reach the outlet section.

### Possible Control Signals

Depending on the architecture, J1/J6 may also carry:

- Relay/contactor drive signals for outlet switching on the Core Unit itself
- Circuit breaker status signals
- Ground/neutral/earth connections
- DC power for PLC coupling circuits in the outlet section

## Why Two Connectors (J1 and J6)?

The Core Unit has 6 load segments. The use of two separate bus connectors (J1 and
J6) may reflect:

1. **Split bus architecture** -- J1 may serve load segments 1-3 and J6 may serve
   load segments 4-6 (or vice versa), matching the 3-phase power distribution on
   3-phase models
2. **Input vs output** -- one connector may carry signals from the power input side
   (mains, voltage sensing) while the other carries signals to/from the outlet side
   (current sensing, PLC, relay control)
3. **Redundancy or separate functions** -- one may carry power measurement analog
   signals while the other carries PLC digital/modulated signals

The actual split of functionality between J1 and J6 requires board tracing to
determine.

## Extension Bar Types

Two generations of Extension Bars have been used with the HP iPDU:

### Standard Extension Bar

| Property | Value |
|----------|-------|
| Outlets | 5x IEC C13 |
| Monitoring | Per-bar power indicator (green LED) |
| Switching | Not individually switchable |
| PLC | Not required |
| Connection | IEC C20 input to Core Unit C19 outlet |

### Intelligent Extension Bar (G2)

| Property | Value |
|----------|-------|
| Example Part | AF547A (kit), 627749-001 (individual) |
| Outlets | 5x IEC C13 with PLC connectors (blue) |
| Monitoring | Per-outlet V, A, W, VA, PF, kWh |
| Switching | Per-outlet remote on/off |
| Height | 5U |
| PLC | Required -- bright blue PLC IEC C20 input |
| Features | Status indicator and UID LED per outlet |
| Connection | PLC IEC C20 input to Core Unit C19 outlet |

## Open Investigation Items

The following require physical access to the board to determine:

- [ ] Exact connector type, pin count, and pitch for J1 and J6
- [ ] Complete pinout (signal-to-pin mapping) for both connectors
- [ ] Whether J1 and J6 carry the same signals or different ones
- [ ] The PLC modulation scheme (FSK, OFDM, spread spectrum, etc.)
- [ ] The data-link protocol used over PLC (framing, addressing, error detection)
- [ ] The application protocol used to command outlet switching and read measurements
- [ ] Which NS9360 serial port(s) drive the PLC modem
- [ ] Whether there is a dedicated PLC modem IC on the board (not yet identified)
  or if PLC modulation is done in software via a serial port
- [ ] The relationship between J1 and J6 (same bus duplicated, or split functions)
- [ ] Whether any AC power lines pass through these connectors or only low-voltage
  signals
- [ ] Circuit breaker status signal routing (if any)
- [ ] Board trace analysis from J1/J6 to NS9360 GPIO pins and MAXQ3180 inputs

## References

- [ANALYSIS.md](ANALYSIS.md) -- Full board component inventory and NS9360 I/O
  architecture
- [RESOURCES.md](RESOURCES.md) -- Datasheets and documentation links
- [STATUS.md](STATUS.md) -- Project status and open items
- [HP Intelligent PDU User Manual (ManualsLib)](https://www.manualslib.com/manual/1252706/Hp-Intelligent-Pdu.html)
  -- 104-page official user guide
- [HP iPDU QuickSpecs (ManualsLib)](https://www.manualslib.com/manual/693626/Hp-Ipdu-Intelligent.html)
  -- 17-page product QuickSpecs
- [Google Photos: HP PDU AF520A Core Parts](https://photos.google.com/share/AF1QipOlajnfRlw4bCdkUFzp4Ti6VZBmPwLn1eyXQCJaOMjkgSEMFuxiXs21xtg1u3QJMA?key=TjdOQno3d2FLbzJYSFhBM3RoZ2RfU2xxclJaT05n)
  -- Physical board teardown photos showing J1 and J6 connectors
