/*
 * (C) Copyright 2002, 2003
 * David Mueller, ELSOFT AG, d.mueller@elsoft.ch
 *
 * See file CREDITS for list of people who contributed to this
 * project.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 *
 */
 /****************************************************************************
 * Global routines used for VCMA9 and A9M2410
 *****************************************************************************/

#include <s3c2410.h>

/*-----------------------------------------------------------------------
 * NAND flash settings
 */
#if (CONFIG_COMMANDS & CFG_CMD_NAND)

/* #define NAND_DEBUG	1*/

#define CFG_MAX_NAND_DEVICE	1	/* Max number of NAND devices		*/
#define SECTORSIZE 512

#define ADDR_COLUMN 1
#define ADDR_PAGE 2
#define ADDR_COLUMN_PAGE 3

#define NAND_ChipID_UNKNOWN 	0x00
#define NAND_MAX_FLOORS 1
#define NAND_MAX_CHIPS 1

#define NAND_WAIT_READY(nand)	NF_WaitRB()

#define NAND_DISABLE_CE(nand)	NF_SetCE(NFCE_HIGH)
#define NAND_ENABLE_CE(nand)	NF_SetCE(NFCE_LOW)


#define WRITE_NAND_COMMAND(d, adr)	NF_Cmd(d)
#define WRITE_NAND_COMMANDW(d, adr)	NF_CmdW(d)
#define WRITE_NAND_ADDRESS(d, adr)	NF_Addr(d)
#define WRITE_NAND(d, adr)		NF_Write(d)
#define READ_NAND(adr)			NF_Read()

/* the following functions are NOP's because S3C24X0 handles this in hardware */
#define NAND_CTL_CLRALE(nandptr)
#define NAND_CTL_SETALE(nandptr)
#define NAND_CTL_CLRCLE(nandptr)
#define NAND_CTL_SETCLE(nandptr)

/* following commands are only used by S3C2440 with hardware ECC */
#define NAND_SOFT_UNLOCK()	NF_SOFT_UnLock()
#define NAND_MECC_UNLOCK()	NF_MECC_UnLock()
#define NAND_MECC_LOCK()	NF_MECC_Lock()
#define NAND_SECC_UNLOCK()	NF_SECC_UnLock()
#define NAND_SECC_LOCK()	NF_SECC_Lock()
#define NAND_RSTECC()		NF_RSTECC()
#define NAND_CLEAR_RB()		NF_CLEAR_RB()
#define NAND_DETECT_RB()	NF_DETECT_RB()


#define CONFIG_MTD_NAND_VERIFY_WRITE	1

#define TACLS   0
#define TWRPH0  4
#define TWRPH1  2


typedef enum {
	NFCE_LOW,
	NFCE_HIGH
} NFCE_STATE;

static inline void NF_Conf(u16 conf)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	nand->NFCONF = conf;
}

#ifdef CPU_2440
static inline void NF_Cont(u16 cont)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	nand->NFCONT = cont;
}
#endif

static inline void NF_Cmd(u8 cmd)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

#ifndef CPU_2440
	nand->NFCMD = cmd;
#else
	nand->NFCMMD = cmd;
#endif	
}

static inline void NF_CmdW(u8 cmd)
{
	NF_Cmd(cmd);
	udelay(1);
}

static inline void NF_Addr(u8 addr)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	nand->NFADDR = addr;
}

static inline void NF_SetCE(NFCE_STATE s)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	switch (s) {
		case NFCE_LOW:
#ifndef CPU_2440		
			nand->NFCONF &= ~(1<<11);
#else
			nand->NFCONT &= ~(1 << 1);
			nand->NFSTAT |= (1 << 2);
#endif			
			break;

		case NFCE_HIGH:
#ifndef CPU_2440		
			nand->NFCONF |= (1<<11);
#else
			nand->NFCONT |= (1 << 1);
#endif			
			break;
	}
}

static inline void NF_WaitRB(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	while (!(nand->NFSTAT & (1<<0)));
}

static inline void NF_Write(u8 data)
{
#ifndef CPU_2440
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	nand->NFDATA = data;
#else
	(*(volatile unsigned char *)0x4E000010) = data;
#endif
}

static inline u8 NF_Read(void)
{
#ifndef CPU_2440
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	return(nand->NFDATA);
#else	
	return (*(volatile unsigned char *)0x4E000010);
#endif

}

static inline void NF_Init_ECC(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

#ifndef CPU_2440
	nand->NFCONF |= (1<<12);
#else
	nand->NFCONT |= (1<<4);
#endif	
}

static inline u32 NF_Read_ECC(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

#ifndef CPU_2440
	return(nand->NFECC);
#else
	return(nand->NFMECCD0);	/* TODO: ECC has to be implemented at all for 2440 */
#endif	
}

#ifdef CPU_2440
static inline void NF_SOFT_UnLock(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT&=~(1<<12);
}

static inline void NF_MECC_UnLock(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT&=~(1<<5);
}

static inline void NF_MECC_Lock(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT|=(1<<5);
}

static inline void NF_SECC_UnLock(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT&=~(1<<6);
}

static inline void NF_SECC_Lock(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT|=(1<<6);
}

static inline void NF_RSTECC(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT|=(1<<4);
}

static inline void NF_DETECT_RB(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	while(!(nand->NFSTAT&(1<<2)));
}

static inline void NF_CLEAR_RB(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFSTAT |= (1<<2);
}
#endif /* CPU_2440 */
#endif /* (CONFIG_COMMANDS & CFG_CMD_NAND) */

