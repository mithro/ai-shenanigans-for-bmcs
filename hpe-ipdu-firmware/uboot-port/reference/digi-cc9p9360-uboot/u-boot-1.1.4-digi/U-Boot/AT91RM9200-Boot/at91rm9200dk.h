#ifndef __ASSEMBLER__
typedef unsigned long u_32;
typedef unsigned short u_16;
typedef unsigned char u_8;
/* ARM asynchronous clock */
#define ARM_CLK		((u_32)(60000000))
#else
#define ARM_CLK 60000000
#endif

/* #define IO_BASE		0
#define PERIPH_BASE 0xfffff000
*/

/* periph bases */

/*
#define MEMC_BASE (PERIPH_BASE + 0xf00)
#define AIC_BASE  (PERIPH_BASE + 0x0)
#define APMC_BASE (PERIPH_BASE + 0xc00)
#define PIOA_BASE (PERIPH_BASE + 0x400)
#define PIOB_BASE (PERIPH_BASE + 0x600)
#define PIOC_BASE (PERIPH_BASE + 0x800)
#define PIOD_BASE (PERIPH_BASE + 0xc00)
*/

/*
	ARM Core Mode and Status Bits
*/

#define ARM_MODE_USER           0x10
#define ARM_MODE_FIQ            0x11
#define ARM_MODE_IRQ            0x12
#define ARM_MODE_SVC            0x13
#define ARM_MODE_ABORT          0x17
#define ARM_MODE_UNDEF          0x1B
#define ARM_MODE_SYS            0x1F
#define ARM_MODE_MASK           0x1F

#define I_BIT                   0x80
#define F_BIT                   0x40
#define T_BIT                   0x20

#define IRQ_STACK_SIZE		0x10
#define FIQ_STACK_SIZE		0x10
#define ABT_STACK_SIZE		0x10
#define UND_STACK_SIZE		0x10
#define SVC_STACK_SIZE		0x100
#define USER_STACK_SIZE		0x400

/*
	Peripherals
*/	
/*
	PIO registers
*/

/*	
#define PIO_PER	0
#define PIO_PDR	0x4
#define PIO_PSR	0x8
#define PIO_OER	0x10
#define PIO_ODR	0x14
#define PIO_OSR	0x18
#define PIO_IFER 0x20
#define PIO_IFDR 0x24
#define PIO_IFSR 0x28
#define PIO_SODR 0x30
#define PIO_CODR 0x34
#define PIO_ODSR 0x38
#define PIO_PDSR 0x3C
#define PIO_IER	0x40
#define PIO_IDR	0x44
#define PIO_IMR	0x48
#define PIO_ISR	0x4C

#define PIO_PPUER 0x64
#define PIO_PPUDR 0x60
*/

/*
	APMC registers
*/

/* #define APMC_SCER 0x0
#define APMC_SCDR 0x4
#define APMC_SCSR 0x8  
#define APMC_PCER 0x10  
#define APMC_PCDR 0x14
#define APMC_PCSR 0x18 
#define APMC_MOR  0x20
#define APMC_MCFR 0x24 
#define APMC_PLLAR 0x28 
#define APMC_PLLBR 0x2c 
#define APMC_MCKR 0x30 
#define APMC_PCK0 0x40  
#define APMC_PCK1 0x44  
#define APMC_PCK2 0x48  
#define APMC_PCK3 0x4c  
#define APMC_PCK4 0x50  
#define APMC_PCK5 0x54  
#define APMC_PCK6 0x58  
#define APMC_PCK7 0x5c  
#define APMC_IER  0x60
#define APMC_IDR  0x64
#define APMC_SR   0x68
#define APMC_IMR  0x6c */



#define AT91C_BASE_CKGR      0xFFFFFC20 /* (CKGR) Base Address */
#define CKGR_MOR  	     0x0
