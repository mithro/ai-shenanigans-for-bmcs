/***********************************************************************
 *
 *  Copyright 2005 by Sistemas Embebidos S.A.
 *  All rights reserved.
 *
 *  $Id$
 *  @Author: Pedro Perez de Heredia
 *  @Descr:  Low level initialization for the UNC90 module.
 *  @References: Derived from initboot.c from ATMEL.
 *
 ***********************************************************************
 *  @History:
 *     2005/01/14 : Initial version.
 ***********************************************************************/

#include "AT91RM9200.h"
#include "unc90_boot.h"


/***********************************************************************
 * @Function: AT91F_WaitForMainClockFrequency
 * @Return:   TRUE on success, FALSE otherwise.
 * @Descr:    Waits until the main clock has been stabilized.
 ***********************************************************************/
unsigned char AT91F_WaitForMainClockFrequency()
{
	volatile char	tmp	= 0;

	/* Determine the main clock frequency */
	while(!(AT91C_BASE_CKGR->CKGR_MCFR & AT91C_CKGR_MAINRDY) && (tmp++ < DELAY_MAIN_FREQ));

	if (tmp >= DELAY_MAIN_FREQ)
		return FALSE;

	return TRUE;
}

/***********************************************************************
 * @Function: AT91F_CheckPLL_FrequencyRange
 * @Return:   TRUE on success, FALSE otherwise.
 * @Descr:    Checks that the selected frequency is between the allowed
 *            ranges.
 ***********************************************************************/
unsigned char AT91F_CheckPLL_FrequencyRange(unsigned int MainClock,
                   unsigned int pllDivider , unsigned int pllMultiplier)
{
	if(pllDivider == 0)
		return FALSE;

	/* Check Input Frequency */
	if( ((MainClock/pllDivider) < INPUT_FREQ_MIN)
	 || ((MainClock/pllDivider) > INPUT_FREQ_MAX) )
		return FALSE;

	/* Check Output Frequency */
	if( ((MainClock/pllDivider*pllMultiplier) < OUTPUT_FREQ_MIN)
	 || ((MainClock/pllDivider*pllMultiplier) > OUTPUT_FREQ_MAX) )
		return FALSE;

	return TRUE;
}

/***********************************************************************
 * @Function: AT91F_InitClocks
 * @Return:   TRUE on success, FALSE otherwise.
 * @Descr:    Clock initialization.
 ***********************************************************************/
unsigned char AT91F_InitClocks(int PLLAR_Register,int PLLBR_Register ,int MCKR_Register)
{
	volatile char 	tmp = 0;
	unsigned int	MainClock;
	unsigned int 	pllDivider,pllMultiplier;

	/* Check if Input & Output Frequencies are in the correct range */

	/* Get Main Clock */
	MainClock 	= (((AT91C_BASE_CKGR->CKGR_MCFR) & AT91C_CKGR_MAINF) * 32768) >> 4;

	pllDivider    	= (PLLAR_Register  & AT91C_CKGR_DIVA);
	pllMultiplier 	= ((PLLAR_Register  & AT91C_CKGR_MULA) >> 16) + 1;
	if(AT91F_CheckPLL_FrequencyRange(MainClock, pllDivider , pllMultiplier) == FALSE)
		return FALSE;

	pllDivider    	= (PLLBR_Register  & AT91C_CKGR_DIVB);
	pllMultiplier 	= ((PLLBR_Register  & AT91C_CKGR_MULB) >> 16) + 1;
	if(AT91F_CheckPLL_FrequencyRange(MainClock, pllDivider , pllMultiplier) == FALSE)
		return FALSE;

	/*
	 * Step 3
	 * Setting PLLA and Divider A
	 */

	AT91C_BASE_CKGR->CKGR_PLLAR = PLLAR_Register;
	/* Wait for PLLA stabilization LOCKA bit in PMC_SR */
	tmp = 0;
	while( !(AT91C_BASE_PMC->PMC_SR & AT91C_PMC_LOCKA) && (tmp++ < DELAY_PLL) ) ;

	/*
	 * Step 4
	 * Setting PLLB and Divider B
	 */

	AT91C_BASE_CKGR->CKGR_PLLBR = PLLBR_Register;
	/* Wait for PLLB stabilization LOCKB bit in PMC_SR */
	tmp = 0;
	while( !(AT91C_BASE_PMC->PMC_SR & AT91C_PMC_LOCKB) && (tmp++ < DELAY_PLL) ) ;

	/*
	 * Step 5
	 * Selection of Master Clock MCK (and Processor Clock PCK)
	 */
	
	/* Constraints of the Master Clock selection sequence */
	/* Write in the MCKR dirty value concerning the clock selection CSS then overwrite it in a second sequence */
	AT91C_BASE_PMC->PMC_MCKR = AT91C_PMC_CSS_SLOW_CLK;
	/* Wait until the master clock is established */
	tmp = 0;
	while( !(AT91C_BASE_PMC->PMC_SR & AT91C_PMC_MCKRDY) && (tmp++ < DELAY_MAIN_FREQ) );

	/* Second sequence */
	AT91C_BASE_PMC->PMC_MCKR = MCKR_Register;
	/* Wait until the master clock is established */
	tmp = 0;
	while( !(AT91C_BASE_PMC->PMC_SR & AT91C_PMC_MCKRDY) && (tmp++ < DELAY_MAIN_FREQ) );

	return TRUE;
}

/***********************************************************************
 * @Function: AT91F_Enable_Ethernet_Phy
 * @Return:   Nothing.
 * @Descr:    This function enables the ethernet PHY. Sets PA4 line to 
 *            low which corresponds with the PWRDWN line of the PHY.
 ***********************************************************************/
void AT91F_Enable_Ethernet_Phy( void )
{
	AT91PS_PIO p_pio = AT91C_BASE_PIOA;

	/* Setup the PWRDWN pin on UNC90, PA4 configured as output active low */
	p_pio->PIO_PER = AT91C_PIO_PA4;
	p_pio->PIO_OER = AT91C_PIO_PA4;
	p_pio->PIO_CODR = AT91C_PIO_PA4;
}	

/***********************************************************************
 * @Function: AT91F_InitSDRAM
 * @Return:   Nothing.
 * @Descr:    SDRAM initialization code for UNC90.
 ***********************************************************************/
void AT91F_InitSDRAM( void )
{
	volatile int *pRegister;
	AT91PS_PIO pPio = AT91C_BASE_PIOC;
	
	/* Configure PC16..31 as D16..31) */
	pPio->PIO_ASR = 0xFFFF0000;
	pPio->PIO_BSR = 0x0;
	pPio->PIO_PDR = 0xFFFF0000;

	/* Setup SMC to support all connected memories (CS0 = FLASH; CS1=SDRAM) */
	pRegister = (int *)0xFFFFFF60;
	*pRegister = 0x02; 
	
 	/* Write sdram configuration register, for cas latency 2,
	 * ras to cas 2, 32-bit, 4 bank, 9 column, 12 row addresses  */
	pRegister = (int *)0xFFFFFF98;
	*pRegister = 0x2188C155; 
	// PPH
	//*pRegister = 0x7fffffd5; 
	
	//*pRegister = 0x7fffffd4; 
	//*pRegister = 0x2188C154; 
	//*pRegister = 0x00007f54; 

	/* Setup sdram - all sdram timing is off mclk sdramc_mr: issue nop */
	pRegister = (int *)0xFFFFFF90;
	*pRegister = 0x1; 
	pRegister = (int *)0x20000000;
	*pRegister = 0; 
	*pRegister = 0; 

	/* sdramc_mr: issue precharge all */
	pRegister = (int *)0xFFFFFF90;
	*pRegister = 0x2; 
	pRegister = (int *)0x20000000;
	*pRegister = 0; 

	/* Force 8 refresh cycles  sdramc_mr: issue refresh  */
	pRegister = (int *)0xFFFFFF90;
	*pRegister = 0x4; 
	pRegister = (int *)0x20000000;
	*pRegister = 0; 
	*pRegister = 0; 
	*pRegister = 0; 
	*pRegister = 0; 
	*pRegister = 0; 
	*pRegister = 0; 
	*pRegister = 0; 
	*pRegister = 0; 

	/* Set mrs mode */
	pRegister = (int *)0xFFFFFF90;
	*pRegister = 0x3; 
	pRegister = (int *)0x20000080;
	*pRegister = 0; 

	/* Now set refresh to the final number of ~15usec */
	pRegister = (int *)0xFFFFFF94;
	*pRegister = 0x2e0; 
	pRegister = (int *)0x20000000;
	*pRegister = 0; 

	/* Set normal mode */
	pRegister = (int *)0xFFFFFF90;
	*pRegister = 0x00; 
	pRegister = (int *)0x20000000;
	*pRegister = 0; 
}

/***********************************************************************
 * @Function: AT91F_Read_p15_c1
 * @Return:   The value read.
 * @Descr:    This function reads co-processor 15, register 1 (control 
 *            register).
 ***********************************************************************/
unsigned int AT91F_Read_p15_c1(void)
{
    unsigned int value;

    __asm__ __volatile__(
	"mrc     p15, 0, %0, c1, c0, 0   @ read control reg\n"
	: "=r" (value)
	:
	: "memory");
 
    return value;
}

/***********************************************************************
 * @Function: AT91F_Write_p15_c1
 * @Return:   Nothing.
 * @Descr:    This function writes co-processor 15, register 1 (control 
 *            register).
 ***********************************************************************/
void AT91F_Write_p15_c1(unsigned int value)
{
    __asm__ __volatile__(
        "mcr     p15, 0, %0, c1, c0, 0   @ write it back\n"
	: "=r" (value)
	:
	: "memory");

    AT91F_Read_p15_c1();
}

/***********************************************************************
 * @Function: AT91F_Enable_ICache
 * @Return:   Nothing.
 * @Descr:    Enables the Instruction Cache.
 ***********************************************************************/
void AT91F_Enable_ICache(void)
{
    unsigned int i, reg;
    
    reg = AT91F_Read_p15_c1();
    for (i=0; i<100; i++);
    AT91F_Write_p15_c1(reg | C1_IDC);
}

/***********************************************************************
 * @Function: AT91F_InitFlash
 * @Return:   Nothing.
 * @Descr:    Initialization of the Flash Memory CS line.
 ***********************************************************************/
void AT91F_InitFlash()
{
	/* Setup UNC90 Flash */
	/* Setup Static Memory controller 0
           Bits[6..0]     Wait states: 0x6  [6 wait states] 
           Bits[7]        Wait states enabled: 0x1 [1 = wait states enabled]
           Bits[11..8]    Data float time: 0x2  [2 TDF cycles] 
           Bits[12]       Byte Access type: 0x1 [Chip Select is connected to 16-bit wide device]
           Bits[14..13]   Data Bus Width:   0x1 16-bit
           Bits[15]       Data Read Protocol: 0x0 Standard Read protocol is used.
           Bits[17..16]   Address to Chip Select setup: 0x1 SMC2_ACSS_1_CYCLE 
           Bits[26..24]   Read and Write Signal Setup Time: 0x0
           Bits[31..29]   Read and Write Signal Hold Time: 0x0
         */
	
	AT91C_BASE_SMC2->SMC2_CSR[0] = (AT91C_SMC2_NWS & 0x6) | AT91C_SMC2_WSEN
                          | (AT91C_SMC2_TDF & 0x200) | AT91C_SMC2_BAT | AT91C_SMC2_DBW_16;
}

/***********************************************************************
 * @Function: AT91F_UNC90_Printk
 * @Return:   Nothing.
 * @Descr:    This function is used to send a string through the serial
 *            port selected as console port (DBGU, USART1 or USART2).
 *            Can be used for very low level debugging pourposes.
 ***********************************************************************/
void AT91F_UNC90_Printk(char *buffer) /* \arg pointer to a string ending by \0 */
{
	while(*buffer != '\0') {
#ifdef	CONFIG_DBGU
		while (!(((AT91PS_USART)AT91C_BASE_DBGU)->US_CSR & AT91C_US_TXRDY));
		((AT91PS_USART)AT91C_BASE_DBGU)->US_THR = (*buffer++ & 0x1FF);
#elif defined(CONFIG_USART1)
		while (!(((AT91PS_USART)AT91C_BASE_US1)->US_CSR & AT91C_US_TXRDY));
		((AT91PS_USART)AT91C_BASE_US1)->US_THR = (*buffer++ & 0x1FF);
#elif defined(CONFIG_USART2)
		while (!(((AT91PS_USART)AT91C_BASE_US2)->US_CSR & AT91C_US_TXRDY));
		((AT91PS_USART)AT91C_BASE_US2)->US_THR = (*buffer++ & 0x1FF);
#else
	#error No serial port defined for console
#endif   
		
	}
}

/***********************************************************************
 * @Function: AT91F_LowLevelInit
 * @Return:   Nothing.
 * @Descr:    This function performs low level HW initialization.
 ***********************************************************************/
void AT91F_LowLevelInit( void )
{
#ifdef	CONFIG_DBGU
	/* Pointer to DBGU memory mapped peripheral control register bank */
	AT91PS_USART 	pUSART = (AT91PS_USART)AT91C_BASE_DBGU;
#elif defined(CONFIG_USART1)
	AT91PS_USART 	pUSART = (AT91PS_USART)AT91C_BASE_US1;   
#elif defined(CONFIG_USART2)
	AT91PS_USART 	pUSART = (AT91PS_USART)AT91C_BASE_US2;   
#else
	#error No serial port defined for console
#endif   
	/* Pointer to Power Management Controller */
	AT91PS_PMC     pPMC  = (AT91PS_PMC)AT91C_BASE_PMC;
	AT91PS_PDC	pPdc;
	unsigned char 	status;
	
	/*
	 * Step 2.
	 * Checking the Main Oscillator Frequency (Optional).
	 */
	status = AT91F_WaitForMainClockFrequency();

	/*
	 * Step 3 to 5.
	 */

	AT91F_InitFlash();
	
	status = AT91F_InitClocks(PLLAR,PLLBR, MCKR);

	/*
	 * SDRAM
	 */

	AT91F_InitSDRAM();
	
	/* Enable Ethernet PHY */ 
	AT91F_Enable_Ethernet_Phy();
	
	
	/* Open PIO for serial console */
#ifdef	CONFIG_DBGU
	AT91C_BASE_PIOA->PIO_ASR = AT91C_PA31_DTXD | AT91C_PA30_DRXD;
#elif defined(CONFIG_USART1)
	pPMC->PMC_PCER = (1<<AT91C_ID_US1);
  	AT91C_BASE_PIOB->PIO_ASR = AT91C_PB20_TXD1 | AT91C_PB21_RXD1;
#elif defined(CONFIG_USART2)
	pPMC->PMC_PCER = (1<<AT91C_ID_US2);
  	AT91C_BASE_PIOA->PIO_ASR = AT91C_PA23_TXD2 | AT91C_PA22_RXD2;
#endif
	
	/* Peripheral B select register */
	AT91C_BASE_PIOA->PIO_BSR = 0x0;

	/* PIO Disabe register */
#ifdef	CONFIG_DBGU
	AT91C_BASE_PIOA->PIO_PDR = AT91C_PA31_DTXD | AT91C_PA30_DRXD;
#elif defined(CONFIG_USART1)
	AT91C_BASE_PIOB->PIO_PDR = AT91C_PB20_TXD1 | AT91C_PB21_RXD1;
#elif defined(CONFIG_USART2)
	AT91C_BASE_PIOA->PIO_PDR = AT91C_PA23_TXD2 | AT91C_PA22_RXD2;
#endif

	/****************************/
	/* Configure serial console */
	/****************************/
	
	/* Disable interrupts */
	pUSART->US_IDR = (unsigned int) -1;
	
	/* Reset receiver and transmitter */
	pUSART->US_CR = AT91C_US_RSTRX | AT91C_US_RSTTX | AT91C_US_RXDIS | AT91C_US_TXDIS;

	/* Define the baudrate divisor register */
	pUSART->US_BRGR = MASTER_CLOCK/(UNC90_CONSOLE_BAUDRATE*16); /* 33 For 60 MHz and 24 for 45 MHz */
	
	/* Write the timeguard register. */
	pUSART->US_TTGR = 0;
	
	/* Peripheral Data Controller (PDC) */
	/* Clear Transmit and Receive counters */
	pPdc = (AT91PS_PDC) &pUSART->US_RPR;
	
	/* Define the USART mode. AT91RM9200 comes out of reset with length as 5data bits */ 
	pUSART->US_MR = AT91C_US_CHMODE_NORMAL | AT91C_US_PAR_NONE | AT91C_US_CHRL_8_BITS;
	
	/* Enable Transmitter */
	pUSART->US_CR = AT91C_US_TXEN;

	/* Enable I-Cache */
	AT91F_Enable_ICache();

#ifdef DEBUG
	AT91F_UNC90_Printk("\n\rLow Level Init performed\n\r");
#endif

}
