/*
 * (C) Copyright 2006 Detlev Zundel, dzu@denx.de
 * (C) Copyright 2006 DENX Software Engineering
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
 */

#include <common.h>


#if (CONFIG_COMMANDS & CFG_CMD_NAND)

#include <nand.h>
#include <a9m2410_nand.h>

/* NanD_Address: Set the current address for the flash chip */

static void NanD_Address(struct nand_chip *nand, int numbytes, unsigned long ofs)
{
	int i;

	/* Send the address */
	/* Devices with 256-byte page are addressed as:
	 * Column (bits 0-7), Page (bits 8-15, 16-23, 24-31)
	 * there is no device on the market with page256
	 * and more than 24 bits.
	 * Devices with 512-byte page are addressed as:
	 * Column (bits 0-7), Page (bits 9-16, 17-24, 25-31)
	 * 25-31 is sent only if the chip support it.
	 * bit 8 changes the read command to be sent
	 * (NAND_CMD_READ0 or NAND_CMD_READ1).
	 */

	if (numbytes == ADDR_COLUMN || numbytes == ADDR_COLUMN_PAGE)
		NF_Addr(ofs);

	ofs = ofs >> nand->page_shift;

	if (numbytes == ADDR_PAGE || numbytes == ADDR_COLUMN_PAGE) {
		for (i = 0; i < nand->chip_shift; i++, ofs = ofs >> 8) {
			NF_Addr(ofs);
		}
	}

	/* Wait for the chip to respond */
	NF_WaitRB();
	return;
}

/* this function is called after Programm and Erase Operations to
 * check for success or failure */
static int a9m24x0_wait(struct mtd_info *mtd, struct nand_chip *this, int state)
{
	NF_WaitRB();
	return 0;
}


static u_char a9m24x0_read_byte(struct mtd_info *mtd)
{
	unsigned char byte;

	byte = NF_Read();
	return byte;
}

static void a9m24x0_read_buf(struct mtd_info *mtd, u_char* buf, int len)
{
	struct nand_chip *this = mtd->priv;

	int i;

	if ((this->options & NAND_BUSWIDTH_16) == NAND_BUSWIDTH_16) {
		u16 val;

		u16 *p = (u16 *) buf;
		len >>= 1;

		for (i=0; i<len; i++)
			p[i] = NF_Read();

	} else {
		for (i=0; i<len; i++)
			buf[i] = NF_Read();
	}
}

static void a9m24x0_write_byte(struct mtd_info *mtd, u_char byte)
{
	NF_Write(byte);
	return;
}

static void a9m24x0_write_buf(struct mtd_info *mtd, const u_char *buf, int len)
{
	int i;

	for (i=0; i<len; i++) {
		NF_Write(buf[i]);
	}
}


static void a9m24x0_cmdfunc(struct mtd_info *mtd, unsigned command,
			int column, int page_addr)
{
	struct nand_chip *this = mtd->priv;

	if (command == NAND_CMD_READID) {
		NF_Cmd(NAND_CMD_RESET);
		NF_WaitRB();
		NF_Cmd(NAND_CMD_READID);
		/* Read the NAND chip ID: 2. Send address byte zero */
		NanD_Address(this, ADDR_COLUMN, 0);
		NF_WaitRB();
		return;
	}

	if (mtd->oobblock > 512)
		goto a9m24x0_cmdfunc_lp;

	/*
	 * Write out the command to the device.
	 */
	if (command == NAND_CMD_SEQIN) {
		int readcmd;

		if (column >= mtd->oobblock) {
			/* OOB area */
			column -= mtd->oobblock;
			readcmd = NAND_CMD_READOOB;
		} else if (column < 256) {
			/* First 256 bytes --> READ0 */
			readcmd = NAND_CMD_READ0;
		} else {
			column -= 256;
			readcmd = NAND_CMD_READ1;
		}
		NF_Cmd(readcmd);
	}
	NF_Cmd(command);

	if (column != -1 || page_addr != -1) {

		/* Serially input address */
		if (column != -1) {
			/* Adjust columns for 16 bit buswidth */
			if (this->options & NAND_BUSWIDTH_16)
				column >>= 1;
			NF_Addr(column);
		}
		if (page_addr != -1) {
			NF_Addr((unsigned char) (page_addr & 0xff));
			NF_Addr((unsigned char) ((page_addr >> 8) & 0xff));
			/* One more address cycle for devices > 32MiB */
			if (this->chipsize > (32 << 20))
				NF_Addr((unsigned char) ((page_addr >> 16) & 0x0f));
		}
	}

	/*
	 * program and erase have their own busy handlers
	 * status and sequential in needs no delay
	*/
	switch (command) {

	case NAND_CMD_PAGEPROG:
	case NAND_CMD_ERASE1:
	case NAND_CMD_ERASE2:
	case NAND_CMD_SEQIN:
		return;
	case NAND_CMD_STATUS:
		NF_Cmd(NAND_CMD_RESET);		/* this is necessary for STM NAND Flashes */
		NF_WaitRB();
		NF_Cmd(NAND_CMD_STATUS);
		break;

	case NAND_CMD_RESET:
		NF_Cmd(NAND_CMD_RESET);
		NF_WaitRB();
		return;

	/* This applies to read commands */
	default:
		NF_WaitRB();
		return;
	}

	goto a9m24x0_cmdfunc_ready;

a9m24x0_cmdfunc_lp:
	/* Emulate NAND_CMD_READOOB */
	if (command == NAND_CMD_READOOB) {
		column += mtd->oobblock;
		command = NAND_CMD_READ0;
	}


	/* Write out the command to the device. */
	NF_Cmd(command);

	if (column != -1 || page_addr != -1) {

		/* Serially input address */
		if (column != -1) {
			/* Adjust columns for 16 bit buswidth */
			if (this->options & NAND_BUSWIDTH_16)
				column >>= 1;
			NF_Addr(column & 0xff);
			NF_Addr(column >> 8);
		}
		if (page_addr != -1) {
			NF_Addr((unsigned char) (page_addr & 0xff));
			NF_Addr((unsigned char) ((page_addr >> 8) & 0xff));
			/* One more address cycle for devices > 128MiB */
			if (this->chipsize > (128 << 20))
				NF_Addr((unsigned char) ((page_addr >> 16) & 0xff));
		}
	}

	/*
	 * program and erase have their own busy handlers
	 * status and sequential in needs no delay
	*/
	switch (command) {

	case NAND_CMD_CACHEDPROG:
	case NAND_CMD_PAGEPROG:
	case NAND_CMD_ERASE1:
	case NAND_CMD_ERASE2:
	case NAND_CMD_SEQIN:
	case NAND_CMD_STATUS:
		return;

	case NAND_CMD_RESET:
		NF_Cmd(NAND_CMD_RESET);
		NF_WaitRB();
		return;

	case NAND_CMD_READ0:
		/* Write out the start read command */
		NF_Cmd(NAND_CMD_READSTART);
		/* Fall through into ready check */

	/* This applies to read commands */
	default:
		NF_WaitRB();
		return;
	}

a9m24x0_cmdfunc_ready:
	/* Apply this short delay always to ensure that we do wait tWB in
	 * any case on any machine. */
	ndelay (100);
	/* wait until command is processed */
	NF_WaitRB();
	return;
}

static inline void NF_Reset(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

#ifndef CPU_2440
	int i;

	NF_SetCE(NFCE_LOW);
	NF_Cmd(0xFF);		/* reset command */
	for(i = 0; i < 300; i++);	/* tWB > 100ns. */
	NF_WaitRB();		/* wait 200~500us; */
	NF_SetCE(NFCE_HIGH);
#else
	nand->NFCONT&=~(1<<1);
	nand->NFSTAT |= (1<<2);
	NF_Cmd(0xFF);	//reset command
	while(!(nand->NFSTAT&(1<<2)));

	nand->NFCONT|=(1<<1);
#endif
}

static inline void NF_Init(void) {
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

#ifndef CPU_2440
	NF_Conf((1<<15)|(0<<14)|(0<<13)|(1<<12)|(1<<11)|(TACLS<<8)|(TWRPH0<<4)|(TWRPH1<<0));
	/*nand->NFCONF = (1<<15)|(1<<14)|(1<<13)|(1<<12)|(1<<11)|(TACLS<<8)|(TWRPH0<<4)|(TWRPH1<<0); */
	/* 1  1    1     1,   1      xxx,  r xxx,   r xxx */
	/* En 512B 4step ECCR nFCE=H tACLS   tWRPH0   tWRPH1 */
#else
	NF_Conf ((TACLS<<12)|(TWRPH0<<8)|(TWRPH1<<4)|(0<<0));
	/* TACLS                [14:12] CLE&ALE duration = HCLK*TACLS.
	// TWRPH0               [10:8]  TWRPH0 duration = HCLK*(TWRPH0+1)
	// TWRPH1               [6:4]   TWRPH1 duration = HCLK*(TWRPH1+1)
	// AdvFlash(R)  [3]             Advanced NAND, 0:256/512, 1:1024/2048
	// PageSize(R)  [2]             NAND memory page size
	//                                              when [3]==0, 0:256, 1:512 bytes/page.
	//                                              when [3]==1, 0:1024, 1:2048 bytes/page.
	// AddrCycle(R) [1]             NAND flash addr size
	//                                              when [3]==0, 0:3-addr, 1:4-addr.
	//                                              when [3]==1, 0:4-addr, 1:5-addr.
	// BusWidth(R/W) [0]    NAND bus width. 0:8-bit, 1:16-bit.
	*/

	NF_Cont ((0<<13)|(0<<12)|(0<<10)|(0<<9)|(0<<8)|(0<<6)|(0<<5)|(1<<4)|(1<<1)|(1<<0));
	/* Lock-tight   [13]    0:Disable lock, 1:Enable lock.
	// Soft Lock    [12]    0:Disable lock, 1:Enable lock.
	// EnablillegalAcINT[10]        Illegal access interupt control. 0:Disable, 1:Enable
	// EnbRnBINT    [9]             RnB interrupt. 0:Disable, 1:Enable
	// RnB_TrandMode[8]             RnB transition detection config. 0:Low to High, 1:High to Low
	// SpareECCLock [6]             0:Unlock, 1:Lock
	// MainECCLock  [5]             0:Unlock, 1:Lock
	// InitECC(W)   [4]             1:Init ECC decoder/encoder.
	// Reg_nCE              [1]             0:nFCE=0, 1:nFCE=1.
	// NANDC Enable [0]             operating mode. 0:Disable, 1:Enable.
	*/

	nand->NFSTAT = 0;
#endif
	NF_Reset();
}

/*
 *	hardware specific access to control-lines
 */
static void a9m24x0_hwcontrol(struct mtd_info *mtd, int cmd)
{
	switch(cmd) {
		case NAND_CTL_SETCLE:
		case NAND_CTL_CLRCLE:
		case NAND_CTL_SETALE:
		case NAND_CTL_CLRALE:
			break;
		case NAND_CTL_SETNCE:
			NF_SetCE(NFCE_LOW);
			break;
		case NAND_CTL_CLRNCE:
			NF_SetCE(NFCE_HIGH);
			break;
	}
}

/*
 * Board-specific NAND initialization. The following members of the
 * argument are board-specific (per include/linux/mtd/nand.h):
 * - IO_ADDR_R?: address to read the 8 I/O lines of the flash device
 * - IO_ADDR_W?: address to write the 8 I/O lines of the flash device
 * - hwcontrol: hardwarespecific function for accesing control-lines
 * - dev_ready: hardwarespecific function for  accesing device ready/busy line
 * - enable_hwecc?: function to enable (reset)  hardware ecc generator. Must
 *   only be provided if a hardware ECC is available
 * - eccmode: mode of ecc, see defines
 * - chip_delay: chip dependent delay for transfering data from array to
 *   read regs (tR)
 * - options: various chip options. They can partly be set to inform
 *   nand_scan about special functionality. See the defines for further
 *   explanation
 * Members with a "?" were not set in the merged testing-NAND branch,
 * so they are not set here either.
 */
void board_nand_init(struct nand_chip *nand)
{
	/* NAND flash initialization. */
	NF_Init();

	nand->hwcontrol = a9m24x0_hwcontrol;
	nand->eccmode = NAND_ECC_SOFT;
	nand->waitfunc = a9m24x0_wait;
	nand->read_byte = a9m24x0_read_byte;
	nand->write_byte = a9m24x0_write_byte;
	nand->read_buf = a9m24x0_read_buf;
	nand->write_buf = a9m24x0_write_buf;

	nand->cmdfunc = a9m24x0_cmdfunc;
	nand->chip_delay = 12;
	nand->options |= NAND_SKIP_BBTSCAN;
/*	nand->options = NAND_SAMSUNG_LP_OPTIONS;*/
}
#endif /* (CONFIG_COMMANDS & CFG_CMD_NAND) */
