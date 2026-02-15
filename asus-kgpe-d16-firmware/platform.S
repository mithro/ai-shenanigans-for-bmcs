/*
 *  (c) 2017 Raptor Engineering, LLC
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 *  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */
/*
 * Board specific setup info
 *
 ******************************************************************************
 * ASPEED Technology Inc.
 * AST2050 DDR2 SDRAM controller initialization and calibration sequence
 *
 * Audrey Pearson <apearson@raptorengineeringinc.com>
 * modified from DDR3/DDR2 ctrlr init and calib from
 * Gary Hsu, <gary_hsu@aspeedtech.com>
 *
 * Release date: 2014.12.29 formal release for SDK0.60
 *
 * Optional define variable
 * 1. UART5 message output   //
 *    CONFIG_DRAM_UART_38400 // set the UART baud rate to 38400, default is 115200
 ******************************************************************************
 */

#include <config.h>
#include <version.h>
#include "hwreg.h"
/******************************************************************************
 Calibration Macro Start
 Usable registers:
  r0, r1, r2, r3, r5, r6, r7, r8, r9, r10, r11
 ******************************************************************************/
/* PATTERN_TABLE,
   init_delay_timer,
   check_delay_timer,
   clear_delay_timer,
   are for DRAM calibration */

PATTERN_TABLE:
    .word   0xff00ff00
    .word   0xcc33cc33
    .word   0xaa55aa55
    .word   0x88778877
    .word   0x92cc4d6e       @ 5
    .word   0x543d3cde
    .word   0xf1e843c7
    .word   0x7c61d253
    .word   0x00000000       @ 8

    .macro init_delay_timer
    ldr r0, =0x1e782024                          @ Set Timer3 Reload
    str r2, [r0]

    ldr r0, =0x1e6c0038                          @ Clear Timer3 ISR
    ldr r1, =0x00040000
    str r1, [r0]

    ldr r0, =TIMER_CONTROL_REG                          @ Enable Timer3
    ldr r1, [r0]
    mov r2, #7
    orr r1, r1, r2, lsl #8
    str r1, [r0]

    ldr r0, =0x1e6c0008                          @ Check ISR for Timer3 timeout
    .endm

    .macro check_delay_timer
    ldr r1, [r0]
    bic r1, r1, #0xFFFBFFFF
    mov r2, r1, lsr #18
    cmp r2, #0x01
    .endm

    .macro clear_delay_timer
    ldr r0, =TIMER_CONTROL_REG                          @ Disable Timer3
    ldr r1, [r0]
    bic r1, r1, #0x00000F00
    str r1, [r0]

    ldr r0, =0x1e6c0038                          @ Clear Timer3 ISR
    ldr r1, =0x00040000
    str r1, [r0]
    .endm

/******************************************************************************
 Calibration Macro End
 ******************************************************************************/
LPC_Patch:                                       @ load to SRAM base 0x1e720400
    str   r1, [r0]
    str   r3, [r2]
    bic   r1, r1, #0xFF
LPC_Patch_S1:
    subs  r5, r5, #0x01
    moveq pc, r8
    ldr   r3, [r2]
    tst   r3, #0x01
    movne pc, r8
    mov   pc, r7
LPC_Patch_S2:                                    @ load to SRAM base 0x1e720480
    str   r1, [r0]
    mov   pc, r9
LPC_Patch_E:

.globl lowlevel_init
lowlevel_init:

init_dram:
    /* save lr (link register, holds return addr for fcn call) */
    mov r4, lr
/* Test - DRAM initial timer */
    ldr r0, =0x1e782044
    ldr r1, =0xFFFFFFFF
    str r1, [r0]

    ldr r0, =TIMER_CONTROL_REG
    ldr r1, [r0]
    bic r1, r1, #0x0000F000
    str r1, [r0]
    mov r2, #3
    orr r1, r1, r2, lsl #12
    str r1, [r0]
/* Test - DRAM initial timer */

    /*Set Scratch register Bit 7 before initialize*/
    ldr r0, =AST_SCU_BASE        /* 1E6E:2000 */
    ldr r1, =0x1688a8a8
    str r1, [r0]

    ldr r0, =SCU_SOC_SCRATCH1_REG   /* 1E6E:2040 */
    ldr r1, [r0]
    orr r1, r1, #0x80
    str r1, [r0]

    /* Check Scratch Register Bit 6 */
    ldr r0, =SCU_SOC_SCRATCH1_REG   /* 1E6E:2040 */
    ldr r1, [r0]
    bic r1, r1, #0xFFFFFFBF
    mov r2, r1, lsr #6
    cmp r2, #0x01
    beq reg_lock				@ exit

    ldr r2, =0x033103F1                          @ load PLL parameter for 24Mhz CLKIN (396:324)
    ldr r0, =SCU_REV_ID_REG                          @ Check Revision ID
    ldr r1, [r0]
    mov r1, r1, lsr #8
    cmp r1, #0x02
    beq set_MPLL                                 @ match AST2050/AST1100

set_MPLL:
    ldr r0, =SCU_M_PLL_PARAM_REG            @ 1E6E:2020 M-PLL (DDR SDRAM) Frequency
    ldr r1, =0x00004c81			@ 200 MHz
    str r1, [r0]

/* Debug - UART console message */
    ldr r0, =UART2_LINE_CTRL_REG		@ 0x1e78400c
    mov r1, #0x83
    str r1, [r0]

    ldr r0, =SCU_FREQ_CNTR_CTRL_RANGE_REG	@ 0x1e6e202c
    ldr r2, [r0]
    mov r2, r2, lsr #12
    tst r2, #0x01
    ldr r0, =UART2_REC_BUFF_REG			@ 0x1e784000
    moveq r1, #0x0D                              @ Baudrate 115200
    movne r1, #0x01                              @ Baudrate 115200, div13
#if defined(CONFIG_DRAM_UART_38400)
    moveq r1, #0x27                              @ Baudrate 38400
    movne r1, #0x03                              @ Baudrate 38400 , div13
#endif
    str r1, [r0]

    ldr r0, =UART2_INT_EN_REG			@ 0x1e784004
    mov r1, #0x00
    str r1, [r0]

    ldr r0, =UART2_LINE_CTRL_REG		@ 0x1e78400c
    mov r1, #0x03
    str r1, [r0]

    ldr r0, =UART2_INT_IDENT_REG		@ 0x1e784008
    mov r1, #0x07
    str r1, [r0]

    ldr r0, =UART2_REC_BUFF_REG			@ 0x1e784000
    mov r1, #0x0D                                @ '\r'
    str r1, [r0]
    mov r1, #0x0A                                @ '\n'
    str r1, [r0]
    mov r1, #0x44                                @ 'D'
    str r1, [r0]
    mov r1, #0x52                                @ 'R'
    str r1, [r0]
    mov r1, #0x41                                @ 'A'
    str r1, [r0]
    mov r1, #0x4D                                @ 'M'
    str r1, [r0]
    mov r1, #0x20                                @ ' '
    str r1, [r0]
    mov r1, #0x49                                @ 'I'
    str r1, [r0]
    mov r1, #0x6E                                @ 'n'
    str r1, [r0]
    mov r1, #0x69                                @ 'i'
    str r1, [r0]
    mov r1, #0x74                                @ 't'
    str r1, [r0]
    mov r1, #0x2D                                @ '-'
    str r1, [r0]
    mov r1, #0x44                                @ 'D'
    str r1, [r0]
    mov r1, #0x44                                @ 'D'
    str r1, [r0]
    mov r1, #0x52                                @ 'R'
    str r1, [r0]
    mov r1, #0x0D                                @ '\r'
    str r1, [r0]
    mov r1, #0x0A                                @ '\n'
    str r1, [r0]
/* Debug - UART console message */

    /* Delay about 100us */
    ldr r2, =0x00000100
delay0:
    nop
    nop
    subs r2, r2, #1          /* until source end addreee [r2]    */
    bne delay0


/******************************************************************************
 Init DRAM
 ******************************************************************************/
    ldr r0, =SCU_KEY_CONTROL_REG
    ldr r1, =0x1688A8A8				@ Unlock SCU registers
    str r1, [r0]

    ldr r0, =SCU_KEY_CONTROL_REG
    ldr r1, [r0]
    cmp r1, #0x01
    bne SCU_regs_locked				@ Still locked. Display error and terminate
    b SCU_regs_unlocked				@ otherwise continue

    /* ERROR MESSAGES */
SCU_regs_locked:
    /* Debug - UART console message */
    ldr r0, =UART2_REC_BUFF_REG			@ 0x1e784000
    mov r1, #0x53				@ 'S'
    str r1, [r0]
    mov r1, #0x43				@ 'C'
    str r1, [r0]
    mov r1, #0x55				@ 'U'
    str r1, [r0]
    mov r1, #0x20				@ ' '
    str r1, [r0]
    mov r1, #0x4c				@ 'L'
    str r1, [r0]
    mov r1, #0x4f				@ 'O'
    str r1, [r0]
    mov r1, #0x43				@ 'C'
    str r1, [r0]
    mov r1, #0x4b				@ 'K'
    str r1, [r0]
    mov r1, #0x45				@ 'E'
    str r1, [r0]
    mov r1, #0x44				@ 'D'
    str r1, [r0]
    mov r1, #0x0D				@ '\r'
    str r1, [r0]
    mov r1, #0x0A				@ '\n'
    str r1, [r0]
    /* Debug - UART console message */
    b reg_lock					@terminate
.LTORG

SCU_regs_unlocked:				@ continue
    ldr r0, =SCU_SOC_SCRATCH1_REG		@ SCU40
    ldr r1, =0x5a000080				@ Set Linux boot key and indicate firmware will initialize DRAM
    str r1, [r0]

    ldr r0, =SDRAM_PROTECTION_KEY_REG
    ldr r1, =0xfc600309				@ Unlock SDRAM registers
    str r1, [r0]

    ldr r0, =SDRAM_PROTECTION_KEY_REG
    ldr r1, [r0]
    cmp r1, #0x01
    bne SDRAM_regs_locked				@ Still locked. Display error and terminate
    b SDRAM_regs_unlocked				@ otherwise continue


SDRAM_regs_locked:
    /* Debug - UART console message */
    ldr r0, =UART2_REC_BUFF_REG			@ 0x1e784000
    mov r1, #0x53				@ 'S'
    str r1, [r0]
    mov r1, #0x44				@ 'D'
    str r1, [r0]
    mov r1, #0x52				@ 'R'
    str r1, [r0]
    mov r1, #0x41				@ 'A'
    str r1, [r0]
    mov r1, #0x4d				@ 'M'
    str r1, [r0]
    mov r1, #0x20				@ ' '
    str r1, [r0]
    mov r1, #0x4c				@ 'L'
    str r1, [r0]
    mov r1, #0x4f				@ 'O'
    str r1, [r0]
    mov r1, #0x43				@ 'C'
    str r1, [r0]
    mov r1, #0x4b				@ 'K'
    str r1, [r0]
    mov r1, #0x45				@ 'E'
    str r1, [r0]
    mov r1, #0x44				@ 'D'
    str r1, [r0]
    mov r1, #0x0D				@ '\r'
    str r1, [r0]
    mov r1, #0x0A				@ '\n'
    str r1, [r0]
    /* Debug - UART console message */
    b reg_lock					@terminate
.LTORG

SDRAM_regs_unlocked:				@continue
    ldr r0, =SCU_KEY_CONTROL_REG
    ldr r1, =0x1688a8a8			@ unlock scu registers (again, apparently?)
    str r1, [r0]

    ldr r0, =SCU_M_PLL_PARAM_REG	@ 0x1e6e:2020 (SCU20)
    ldr r1, =0x000041f0			@ MPLL params: output denumerator=0b0000; output divider=1; numerator=0b001111; post divider=div by 2 
    str r1, [r0]

    /* Delay about 400us */
    ldr r2, =0x00000400
delay1:
    nop
    nop
    subs r2, r2, #1          /* until source end addreee [r2]    */
    bne delay1

    ldr r0, =SDRAM_PROTECTION_KEY_REG
    ldr r1, =0xfc600309		@ unlock sdram registers
    str r1, [r0]

    ldr r0, =SDRAM_DLL_CTRL_REG3		@ DLL ctrl reg #3
    ldr r1, =0x00909090
    str r1, [r0]

    ldr r0, =SDRAM_DLL_CTRL_REG1		@ DLL ctrl reg #1
    ldr r1, =0x00050000
    str r1, [r0]


    ldr r0, =SCU_HW_STRAPPING_REG     		@ SCU70 bits 3:2 - VGA memory size selection
    ldr r1, [r0]
    ldr r2, =0x0000000c
    and	r1, r1, r2
    mov	r2, r1, lsl #2

    ldr r0, =SDRAM_CONFIG_REG               @ MCR04 - Config register
#ifdef CONFIG_1G_DDRII
    ldr r1, =0x00000d89
#endif
#ifdef CONFIG_512M_DDRII
    ldr r1, =0x00000585
#endif
    orr r1, r1, r2
    str r1, [r0]

    ldr r0, =SDRAM_GRAP_MEM_PROTECTION_REG  	@ 1E6E:0008  MCR8: Graphics memory protection reg
    ldr r1, =0x0011030f
    str r1, [r0]

    ldr r0, =SDRAM_NSPEED_REG1              @ 1E6E:0010  @ MCR10: Normal Speed AC Timing Register #1
    ldr r1, =0x22201725
    str r1, [r0]

    ldr r0, =SDRAM_NSPEED_REG2              @ 1E6E:0018	@ MCR18: Normal Speed AC Timing Register #2
    ldr r1, =0x1e29011a
    str r1, [r0]

    ldr r0, =SDRAM_NSPEED_DELAY_CTRL_REG    @ 1E6E:0020	@ MCR20: Normal Speed Delay Control Register
    ldr r1, =0x00c82222
    str r1, [r0]

    ldr r0, =SDRAM_LSPEED_REG1              @ 1E6E:0014 @ MCR14: Low Speed AC Timing Register #1
    ldr r1, =0x22201725
    str r1, [r0]

    ldr r0, =SDRAM_LSPEED_REG2              @ 1E6E:001c @ MCR1c: Low Speed AC Timing Register #2
    ldr r1, =0x1e29011a
    str r1, [r0]

    ldr r0, =SDRAM_LSPEED_DELAY_CTRL_REG    @ 1E6E:0024 @ MCR24: Low Speed Delay Control Register
    ldr r1, =0x00c82222
    str r1, [r0]

    ldr r0, =SDRAM_PAGE_MISS_LATENCY_MASK_REG	@ 1E6E:0038 @ MCR38: Page Miss Latency Mask Register
    ldr r1, =0xffffff82
    str r1, [r0]

    ldr r0, =SDRAM_PRIORITY_GROUP_SET_REG	@ 1E6E:003C @ MCR3C: Priority Group Setting Register
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_MAX_GRANT_LENGTH_REG1    @ 1E6E:0040 @ MCR40: Maximum Grant Length Register #1
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_MAX_GRANT_LENGTH_REG2    @ 1E6E:0044	@ MCR44: Maximum Grant Length Register #2
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_MAX_GRANT_LENGTH_REG3    @ 1E6E:0048 @ MCR48: Maximum Grant Length Register #3
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =0x1e6e004c	@ 1E6E:004c @ MCR4C 
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_ECC_CTRL_STATUS_REG	@ 1E6E:0050 @ MCR50: 
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_ECC_SEGMENT_EN_REG	@ 1E6E:0054 @ MCR54: 
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_ECC_SCRUB_REQ_MASK_CTRL_REG	@ 1E6E:0058 @ MCR58: 
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_ECC_ADDR_FIRST_ERR_REG	@ 1E6E:005C @ MCR5C: 
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_IO_BUFF_MODE_REG         @ 1E6E:0060 @ MCR60: IO Buffer Mode Register
    ldr r1, =0x032aa02a
    str r1, [r0]

    ldr r0, =SDRAM_DLL_CTRL_REG1            @ 1E6E:0064 @ MCR64: DLL Control Register #1
    ldr r1, =0x002d3000
    str r1, [r0]

    ldr r0, =SDRAM_DLL_CTRL_REG2            @ 1E6E:0068 @ MCR68: DLL Control Register #2
    ldr r1, =0x02020202
    str r1, [r0]

    ldr r0, =SDRAM_TEST_CTRL_STATUS_REG     @ 1E6E:0070 @ MCR70: Testing Control/Status Register
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_TEST_START_ADDR_LENGTH_REG   @ 1E6E:0074 @ MCR74: Testing Start Address and Length Register
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_TEST_FAIL_DQ_BIT_REG     @ 1E6E:0078 @ MCR78: Testing Fail DQ Bit Register
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_TEST_INIT_VALUE_REG      @ 1E6E:007C @ MCR7C: Test Initial Value Register
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_PWR_CTRL_REG             @ 1E6E:0034 @ MCR34: Power Control Register
    ldr r1, =0x00000001
    str r1, [r0]

    ldr r2, =0x00000400
delay2:
    nop
    nop
    subs r2, r2, #1          /* until source end addreee [r2]    */
    bne delay2

    ldr r0, =SDRAM_MRS_EMRS2_MODE_SET_REG		@ MCR2c: MRS/EMRS2 Mode Setting Register
    ldr r1, =0x00000732
    str r1, [r0]

    ldr r0, =SDRAM_MRS_EMRS3_MODE_SET_REG		@ MCR30: EMRS/EMRS3 Mode Setting Register
    ldr r1, =0x00000040
    str r1, [r0]

    ldr r0, =SDRAM_MODE_SET_CTRL_REG		@ MCR28: Mode Setting Control Register
    ldr r1, =0x00000005
    str r1, [r0]

    ldr r0, =SDRAM_MODE_SET_CTRL_REG		@ MCR28: Mode Setting Control Register
    ldr r1, =0x00000007
    str r1, [r0]

    ldr r0, =SDRAM_MODE_SET_CTRL_REG		@ MCR28: Mode Setting Control Register
    ldr r1, =0x00000003
    str r1, [r0]

    ldr r0, =SDRAM_MODE_SET_CTRL_REG		@ MCR28: Mode Setting Control Register
    ldr r1, =0x00000001
    str r1, [r0]

    ldr r0, =SDRAM_REFRESH_TIMING_REG		@ MCR0C: Refresh Timing Register
    ldr r1, =0x00005a08
    str r1, [r0]

    ldr r0, =SDRAM_MRS_EMRS2_MODE_SET_REG		@ MCR2C: MRS/EMRS2 Mode Setting Register
    ldr r1, =0x00000632
    str r1, [r0]

    ldr r0, =SDRAM_MODE_SET_CTRL_REG		@ MCR28: Mode Setting Control Register
    ldr r1, =0x00000001
    str r1, [r0]

    ldr r0, =SDRAM_MRS_EMRS3_MODE_SET_REG		@ MCR30: EMRS/EMRS3 Mode Setting Register
    ldr r1, =0x000003c0
    str r1, [r0]

    ldr r0, =SDRAM_MODE_SET_CTRL_REG		@ MCR28: Mode Setting Control Register
    ldr r1, =0x00000003
    str r1, [r0]

    ldr r0, =SDRAM_MRS_EMRS3_MODE_SET_REG		@ MCR30: EMRS/EMRS3 Mode Setting Register
    ldr r1, =0x00000040
    str r1, [r0]

    ldr r0, =SDRAM_MODE_SET_CTRL_REG		@ MCR28: Mode Setting Control Register
    ldr r1, =0x00000003
    str r1, [r0]

    ldr r0, =SDRAM_REFRESH_TIMING_REG		@ MCR0C: Refresh Timing Register
    ldr r1, =0x00005a21
    str r1, [r0]

    ldr r0, =SDRAM_PWR_CTRL_REG			@ MCR34: Power Control Register
    ldr r1, =0x00007c03
    str r1, [r0]

    ldr r0, =AST2100_COMPATIBLE_SCU_MPLL_PARA	@ MCR120: AST2000 Backward compatible SCU MPLL Parameter
    ldr r1, =0x00004c41
    str r1, [r0]

@ end

    b set_scratch					@ set success flag and terminate
.LTORG

/******************************************************************************
 End DRAM Init
 ******************************************************************************/

set_scratch:
    /*Set Scratch register Bit 6 after ddr initial finished */
    ldr r0, =SCU_SOC_SCRATCH1_REG		@ SCU40
    ldr r1, [r0]
    orr r1, r1, #0x40
    str r1, [r0]

    /* Debug - UART console message */
    ldr r0, =UART2_REC_BUFF_REG			 @ 0x1e784000
    mov r1, #0x2e                                @ '.'
    str r1, [r0]
    mov r1, #0x2e                                @ '.'
    str r1, [r0]
    mov r1, #0x2e                                @ '.'
    str r1, [r0]
    mov r1, #0x44                                @ 'D'
    str r1, [r0]
    mov r1, #0x6F                                @ 'o'
    str r1, [r0]
    mov r1, #0x6E                                @ 'n'
    str r1, [r0]
    mov r1, #0x65                                @ 'e'
    str r1, [r0]
    mov r1, #0x0D                                @ '\r'
    str r1, [r0]
    mov r1, #0x0A                                @ '\n'
    str r1, [r0]
    /* Debug - UART console message */

reg_lock:
    /* Lock SCU and SDRAM registers */
    ldr r0, =SCU_KEY_CONTROL_REG
    ldr r1, =0x00000000
    str r1, [r0]

    ldr r0, =SDRAM_PROTECTION_KEY_REG
    ldr r1, =0x00000000
    str r1, [r0]

    /* Return to caller */
    /* restore lr */
    mov lr, r4

    /* back to arch calling code */
    mov pc, lr
