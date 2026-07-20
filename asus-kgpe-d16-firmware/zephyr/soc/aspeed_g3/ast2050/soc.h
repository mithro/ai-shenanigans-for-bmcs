/*
 * ASPEED AST2050 (G3) SoC — ARM926EJ-S.
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef ASPEED_AST2050_SOC_H_
#define ASPEED_AST2050_SOC_H_

/* AST2050 memory map (reverse-engineered; see asus-kgpe-d16-firmware). */
#define AST2050_DRAM_BASE   0x40000000  /* 64 MB SDMC */
#define AST2050_UART2_BASE  0x1e784000  /* NS16550 console (ttyS4) */
#define AST2050_VIC_BASE    0x1e6c0000  /* compact G3 VIC */
#define AST2050_TIMER_BASE  0x1e782000
#define AST2050_SCU_BASE    0x1e6e2000

#endif /* ASPEED_AST2050_SOC_H_ */
