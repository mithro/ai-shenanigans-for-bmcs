# UART — AST2050 driver + faithfulness doc

**UART1 0x1E783000 · UART2 (console) 0x1E784000.** Standard 16550-compatible
UARTs (plus VUART 0x1E787000). The AST2050 has UART1/UART2 only — **not** the
AST2400's UART3–5 at 0x1E78D/E/F000 (see `../../AST2050-MEMORY-MAP.md`).

## 1. Registers (16550, 32-bit stride)

| Off | DLAB=0 | DLAB=1 |
|---|---|---|
| 0x00 | RBR (r) / THR (w) | divisor low (DLL) |
| 0x04 | IER | divisor high (DLH) |
| 0x08 | IIR (r) / FCR (w) | — |
| 0x0C | LCR (bit7 = DLAB) | |
| 0x10 | MCR (bit4 = loopback) | |
| 0x14 | LSR (bit0 DR, bit5 THRE) | |
| 0x1C | scratch (RW) | |

## 2. Driver / baud notes

- Program 8N1: `LCR=0x03`; set the divisor via DLAB. **Baud = UARTCLK / (16 × DLL)**
  where **UARTCLK = 24 MHz, optionally ÷13 (SCU2C[12])** — decoupled from the H-PLL
  (see `../scu/DATASHEET-SCU.md §9`). E.g. DLL=13, ÷13 off → 115200; DLL=1, ÷13 on →
  115200. The console (UART2) is the BMC serial / SOL path.
- UARTCLK gate is SCU0C[15] (running at reset).

## 3. QEMU faithfulness

`peripherals/uart/fwtest.c` (4 checks) vs the current model — **all PASS**: the
scratch register (0x1C) is read/write on the console UART, LSR reports transmit-ready,
and an internal `MCR[4]` loopback echoes `THR`→`RBR` on UART1 (verified `0x42`). The
16550 model is register- and datapath-faithful for the G3. **No model change needed**
(legacy boots untouched). Baud *rate* precision (the 24 MHz/÷13 clock) is a rate matter
tied to the SCU clock-tree — validated by timing on silicon, not a register test.

## 4. Deliverable status

| # | Deliverable | State |
|---|---|---|
| 1 | firmware test (`fwtest.c`) | ☑ 4 checks (scratch, THRE, loopback) |
| 2 | doc (this) | ☑ |
| 3 | QEMU model | ☑ 16550 register + datapath faithful (baud rate → SCU clock-tree) |
| 4 | integration test (`../../integration/test_uart.py`) | ☑ |
