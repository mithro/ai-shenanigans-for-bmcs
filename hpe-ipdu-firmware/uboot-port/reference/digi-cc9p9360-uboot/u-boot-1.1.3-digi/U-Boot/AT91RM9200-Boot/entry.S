#include <at91rm9200dk.h>

		.text
		.align

#define STACK             0x22000000

/* ------------------------ List of Exported resources -------------------------*/
		.globl	__entry,_entry
		.globl	__stext,_stext
		.globl _start,start
		
/*------------------------------------------------------------------------------*/
/*  Define the vector table.*/
/*  The reset vector jumps to the handler code.*/
/*  All others just dead loop on themselves!*/
/*------------------------------------------------------------------------------*/
/*------------------------------------------------------------------------------*/
/*    InitReset. This code is executed with the FLASH at address 0.*/
/*------------------------------------------------------------------------------*/
startoftext:
rstvec:
                B           InitReset 
undefvec:
                B           undefvec 
swivec:
                B           swivec   
pabtvec:
                B           pabtvec  
dabtvec:
                B           dabtvec  
rsvdvec:
                B           rsvdvec  
irqvec:
                ldr         pc, [pc,#-0xF20]        
fiqvec:
                ldr         pc, [pc,#-0xF20]       

#-------------------
#- The reset handler
#-------------------
InitReset:

# Get the CKGR Base Address
	ldr     r1, = AT91C_BASE_CKGR	
	
#-Main oscillator Enable register	APMC_MOR : Enable main oscillator , OSCOUNT = 0xFF
#	ldr 	r0, = AT91C_CKGR_MOSCEN:OR:AT91C_CKGR_OSCOUNT
	ldr 	r0, =0x0000FF01
	str     r0, [r1, #CKGR_MOR]

#------------------------------------------------------------------------------
#-Low level Init (PMC, AIC, EBI, ....)
#------------------------------------------------------------------------------

#- Add loop to compensate Main Oscillator startup time
	ldr 	r0, =0x00000010
LoopOsc:
	subs    r0, r0, #1              
	bhi     LoopOsc
	
	ldr 	r1, = 0x00204000	

#- Set up Supervisor Mode and set SVC Stack
	msr     cpsr_c, #(ARM_MODE_SVC | I_BIT | F_BIT)
# Insure word alignement
	bic     r1, r1, #3                  
# Init stack SYS	
	mov     sp, r1                      
	
	bl AT91F_LowLevelInit

#-------------------------------------
# Read/modify/write CP15 control register 
#-------------------------------------
# read cp15 control registre (cp15 r1) in r0
    mrc     p15, 0, r0, c1, c0, 0
# Reset bit :Little Endian end fast bus mode
    ldr     r3, =0xC0000080      
# Set bit :Asynchronous clock mode, Not Fast Bus
#    ldr     r4, =0xC0000000      
# Set bit :Asynchronous clock mode, Not Fast Bus, Enable ICache
# PPH 
    ldr     r4, =0xC0005000      
    
    bic     r0, r0, r3             
    orr     r0, r0, r4             
# write r0 in cp15 control registre (cp15 r1)
    mcr     p15, 0, r0, c1, c0, 0 
    
#---------------------------------
#- Setup the stack for each mode
#---------------------------------
   ldr		r0, =STACK

#- Set up Fast Interrupt Mode and set FIQ Mode Stack
	msr     CPSR_c, #(ARM_MODE_FIQ | I_BIT | F_BIT)
# Init stack FIQ
	mov     r13, r0                     
 	sub     r0, r0, #FIQ_STACK_SIZE

#- Set up Interrupt Mode and set IRQ Mode Stack
	msr     CPSR_c, #(ARM_MODE_IRQ | I_BIT | F_BIT)
# Init stack IRQ
	mov     r13, r0                     
	sub     r0, r0, #IRQ_STACK_SIZE
 
#- Set up Abort Mode and set Abort Mode Stack
	msr     CPSR_c, #(ARM_MODE_ABORT | I_BIT | F_BIT)
# Init stack Abort
	mov     r13, r0
	sub     r0, r0, #ABT_STACK_SIZE

#- Set up Undefined Instruction Mode and set Undef Mode Stack
	msr     CPSR_c, #(ARM_MODE_UNDEF | I_BIT | F_BIT)
# Init stack Undef
	mov     r13, r0 
	sub     r0, r0, #UND_STACK_SIZE

#- Set up Supervisor Mode and set Supervisor Mode Stack
	msr     CPSR_c, #(ARM_MODE_SVC | I_BIT | F_BIT)
# Init stack Sup
	mov     r13, r0


#------------------------------------------------------------------------------
#- Branch on C code Main function (with interworking)
#----------------------------------------------------
#- Branch must be performed by an interworking call as either an ARM or Thumb 
#- main C function must be supported. This makes the code not position-
#- independant. A Branch with link would generate errors 
#------------------------------------------------------------------------------
 		b _main


#------------------------------------------------------------------------------
#- Loop for ever
#---------------
#- End of application. Normally, never occur.
#- Could jump on Software Reset ( B 0x0 ).
#------------------------------------------------------------------------------
End:
	b           End
