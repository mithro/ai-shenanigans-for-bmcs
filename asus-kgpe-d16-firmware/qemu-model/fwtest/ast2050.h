/* AST2050 (G3) MMIO base addresses + register helpers for bare-metal tests.
 *
 * Addresses are the AST2050 map from Raptor hwreg.h and the AST2050 A3
 * datasheet (see ../AST2050-MEMORY-MAP.md). They coincide with the AST2400
 * bases for most blocks; the DIFFERENCES this test suite hunts are in the
 * register-level *semantics* within blocks (VIC bank layout, SCU clocking,
 * DDR2 vs DDR3), not the base addresses.
 *
 * Apache-2.0.
 */
#ifndef AST2050_H
#define AST2050_H

typedef unsigned int u32;

#define AHBC_BASE         0x1E600000u  /* AHB controller + remap (0x8C)        */
#define MAC1_BASE         0x1E660000u  /* ftgmac100 MAC1 (RMII)                */
#define MAC2_BASE         0x1E680000u  /* ftgmac100 MAC2                       */
#define USB_UDC_BASE      0x1E6A0000u  /* USB2.0 device/vhub (aspeed.udc-ast2050)*/
#define VIC_BASE          0x1E6C0000u  /* interrupt controller (compact G3)    */
#define SDMC_BASE         0x1E6E0000u  /* SDRAM controller (DDR2)              */
#define SCU_BASE          0x1E6E2000u  /* system control unit                  */
#define HACE_BASE         0x1E6E3000u  /* hash/crypto (if present on G3)       */
#define ADC_BASE          0x1E6E9000u  /* ADC (sensors)                        */
#define VIDEO_BASE        0x1E700000u  /* video engine (KVM capture)           */
#define GPIO_BASE         0x1E780000u  /* GPIO                                 */
#define RTC_BASE          0x1E781000u  /* RTC                                  */
#define TIMER_BASE        0x1E782000u  /* FTTMR010 timers 1..3                 */
#define UART1_BASE        0x1E783000u  /* UART1                                */
#define UART5_BASE        0x1E784000u  /* console UART (D16 "UART2")           */
#define WDT_BASE          0x1E785000u  /* watchdog                             */
#define PWM_BASE          0x1E786000u  /* PWM / tach (fans)                    */
#define LPC_BASE          0x1E789000u  /* LPC host interface (KCS/BT/SuperIO)  */
#define I2C_BASE          0x1E78A000u  /* I2C controller                       */
#define SMC_BASE          0x16000000u  /* legacy SMC / SPI flash controller    */

/* Console UART used by the harness (see console.c). */
#define UART_CONSOLE_BASE UART5_BASE

/* SCU register offsets (subset; see peripherals/scu/DOC.md). */
#define SCU_PROTECT       0x00u  /* unlock key 0x1688A8A8                      */
#define SCU_RESET         0x04u
#define SCU_CLK_SEL       0x08u
#define SCU_CLK_STOP      0x0Cu
#define SCU_MPLL          0x20u
#define SCU_HPLL          0x24u
#define SCU_STRAP         0x70u  /* hardware strapping                        */
#define SCU_REVID         0x7Cu  /* silicon revision id                       */

static inline u32 readl(u32 addr)            { return *(volatile u32 *)addr; }
static inline void writel(u32 addr, u32 val) { *(volatile u32 *)addr = val; }

#endif /* AST2050_H */
