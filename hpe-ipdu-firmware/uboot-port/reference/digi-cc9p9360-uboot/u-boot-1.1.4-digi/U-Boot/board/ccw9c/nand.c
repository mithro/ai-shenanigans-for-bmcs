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

/* this function is called after Programm and Erase Operations to
 * check for success or failure */
static int cc9c_wait(struct mtd_info *mtd, struct nand_chip *this, int state)
{
	unsigned char byte = 0x00;
	int i = 0;
	int retry = 200;
	
	do {
		if (state == FL_WRITING) {
			if (i == 0) {
				WRITE_NAND_COMMAND( NAND_CMD_STATUS, this->IO_ADDR_W );
				retry = 35;
			}
			
			NAND_WAIT_READY();
			i++;
		} else if (state == FL_ERASING) {
			if (i == 0) {
				WRITE_NAND_COMMAND( NAND_CMD_STATUS, this->IO_ADDR_W );
				retry = 200;
			}
			
			NAND_WAIT_READY();
			i++;
		} else {
			NAND_WAIT_READY();
			break;
		}
	
		byte = READ_NAND( this->IO_ADDR_R );
		if ((byte & 0x40) == 0x40)
			break;
	} while (i <= retry);
	
	if (i > retry)
		return byte;

	return 0;
}

static u_char cc9c_read_byte(struct mtd_info *mtd)
{
	struct nand_chip *this = mtd->priv;
	unsigned char byte;

	byte = READ_NAND( this->IO_ADDR_R );
	return byte;
}

static void cc9c_read_buf(struct mtd_info *mtd, u_char* buf, int len)
{
	struct nand_chip *this = mtd->priv;

	int i;

	if ((this->options & NAND_BUSWIDTH_16) == NAND_BUSWIDTH_16) {
		u16 *p = (u16 *) buf;
		len >>= 1;

		for (i=0; i<len; i++)
			p[i] = READ_NAND( this->IO_ADDR_R );

	} else {
		for (i=0; i<len; i++)
			buf[i] = READ_NAND( this->IO_ADDR_R );
	}
}

static void cc9c_write_byte(struct mtd_info *mtd, u_char byte)
{
	struct nand_chip *this = mtd->priv;

	WRITE_NAND( byte, this->IO_ADDR_W );
	return;
}

static void cc9c_write_buf(struct mtd_info *mtd, const u_char *buf, int len)
{
	struct nand_chip *this = mtd->priv;

	int i;

	for (i=0; i<len; i++) {
		WRITE_NAND( buf[i], this->IO_ADDR_W );
	}
}


static void cc9c_cmdfunc(struct mtd_info *mtd, unsigned command,
			int column, int page_addr)
{
	struct nand_chip *this = mtd->priv;

	if (command == NAND_CMD_READID) {
		WRITE_NAND_COMMAND( NAND_CMD_RESET, this->IO_ADDR_W );
		NAND_WAIT_READY();
		WRITE_NAND_COMMAND( NAND_CMD_READID, this->IO_ADDR_W );
		/* Read the NAND chip ID: 2. Send address byte zero */
		WRITE_NAND_ADDRESS( 0, this->IO_ADDR_W );
		NAND_WAIT_READY();
		return;
	}

	if (mtd->oobblock > 512)
		goto cc9c_cmdfunc_lp;

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
		WRITE_NAND_COMMAND( readcmd, this->IO_ADDR_W );
	}
	WRITE_NAND_COMMAND( command, this->IO_ADDR_W );

	if (column != -1 || page_addr != -1) {

		/* Serially input address */
		if (column != -1) {
			/* Adjust columns for 16 bit buswidth */
			if (this->options & NAND_BUSWIDTH_16)
				column >>= 1;
			WRITE_NAND_ADDRESS( column, this->IO_ADDR_W );
		}
		if (page_addr != -1) {
			WRITE_NAND_ADDRESS( (unsigned char) (page_addr & 0xff), this->IO_ADDR_W );
			WRITE_NAND_ADDRESS( (unsigned char) ((page_addr >> 8) & 0xff), this->IO_ADDR_W );
			/* One more address cycle for devices > 32MiB */
			if (this->chipsize > (32 << 20))
				WRITE_NAND_ADDRESS( (unsigned char) ((page_addr >> 16) & 0x0f), this->IO_ADDR_W );
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
		break;
	case NAND_CMD_STATUS:
		/* this is necessary for STM NAND Flashes */
		WRITE_NAND_COMMAND( NAND_CMD_RESET, this->IO_ADDR_W );
		NAND_WAIT_READY();
		WRITE_NAND_COMMAND( NAND_CMD_STATUS, this->IO_ADDR_W );
		break;

	case NAND_CMD_RESET:
		WRITE_NAND_COMMAND( NAND_CMD_RESET, this->IO_ADDR_W );
		NAND_WAIT_READY();
		return;

	/* This applies to read commands */
	default:
		NAND_WAIT_READY();
		return;
	}

	goto cc9c_cmdfunc_ready;

cc9c_cmdfunc_lp:
	/* Emulate NAND_CMD_READOOB */
	if (command == NAND_CMD_READOOB) {
		column += mtd->oobblock;
		command = NAND_CMD_READ0;
	}


	/* Write out the command to the device. */
	WRITE_NAND_COMMAND( command, this->IO_ADDR_W );

	if (column != -1 || page_addr != -1) {

		/* Serially input address */
		if (column != -1) {
			/* Adjust columns for 16 bit buswidth */
			if (this->options & NAND_BUSWIDTH_16)
				column >>= 1;
			WRITE_NAND_ADDRESS( column & 0xff, this->IO_ADDR_W );
			WRITE_NAND_ADDRESS( column >> 8, this->IO_ADDR_W );
		}
		if (page_addr != -1) {
			WRITE_NAND_ADDRESS( (unsigned char) (page_addr & 0xff), this->IO_ADDR_W );
			WRITE_NAND_ADDRESS( (unsigned char) ((page_addr >> 8) & 0xff), this->IO_ADDR_W );
			/* One more address cycle for devices > 128MiB */
			if (this->chipsize > (128 << 20))
				WRITE_NAND_ADDRESS( (unsigned char) ((page_addr >> 16) & 0xff), this->IO_ADDR_W );
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
		WRITE_NAND_COMMAND( NAND_CMD_RESET, this->IO_ADDR_W );
		NAND_WAIT_READY();
		return;

	case NAND_CMD_READ0:
		/* Write out the start read command */
		WRITE_NAND_COMMAND( NAND_CMD_READSTART, this->IO_ADDR_W );
		/* Fall through into ready check */

	/* This applies to read commands */
	default:
		NAND_WAIT_READY();
		return;
	}

cc9c_cmdfunc_ready:
	/* Apply this short delay always to ensure that we do wait tWB in
	 * any case on any machine. */
	ndelay (100);
	/* wait until command is processed */
	NAND_WAIT_READY();
	return;
}


/*
 *	hardware specific access to control-lines
 */
static void cc9c_hwcontrol(struct mtd_info *mtd, int cmd)
{
	switch(cmd) {
		case NAND_CTL_SETCLE:
		case NAND_CTL_CLRCLE:
		case NAND_CTL_SETALE:
		case NAND_CTL_CLRALE:
		case NAND_CTL_SETNCE:
		case NAND_CTL_CLRNCE:
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
	set_gpio_cfg_reg_val( NAND_BUSY_GPIO,
			      NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_INPUT);

	nand->hwcontrol = cc9c_hwcontrol;
	nand->eccmode = NAND_ECC_SOFT;
	nand->waitfunc = cc9c_wait;
	nand->read_byte = cc9c_read_byte;
	nand->write_byte = cc9c_write_byte;
	nand->read_buf = cc9c_read_buf;
	nand->write_buf = cc9c_write_buf;

	nand->cmdfunc = cc9c_cmdfunc;
	nand->chip_delay = 20;
	nand->options = NAND_NO_AUTOINCR;
/*	nand->options |= NAND_SKIP_BBTSCAN;*/

}
#endif /* (CONFIG_COMMANDS & CFG_CMD_NAND) */
