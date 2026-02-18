/*
 * (C) Copyright 2001
 * Kyle Harris, Nexus Technologies, Inc. kharris@nexus-tech.net
 *
 * (C) Copyright 2001
 * Wolfgang Denk, DENX Software Engineering, wd@denx.de.
 *
 * (C) Copyright 2003
 * Texas Instruments, <www.ti.com>
 * Kshitij Gupta <Kshitij@ti.com>
 *
 * (C) Copyright 2005
 * FS Forth-Systeme GmbH
 *
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
#include <linux/byteorder/swab.h>

/* Flash Organisation Structure */
typedef struct {
	unsigned int sector_number;
	unsigned int sector_size;
} fl_org_def_t;


/* Flash Organisations */
fl_org_def_t OrgSTM29DW323DB[] = {
	{ 8, 8*1024 }, /* 8* 8kBytes sectors */ 
	{ 63, 64*1024 }	/* 63 *  64 kBytes sectors */
};

flash_info_t	flash_info[CFG_MAX_FLASH_BANKS];
ulong		flash_base_addr[CFG_MAX_FLASH_BANKS] = { CFG_FLASH_BASE };

/* AT49BV1614A Codes */
#define FLASH_CODE1		0xAA
#define FLASH_CODE2		0x55
#define ID_IN_CODE		0x90
#define ID_OUT_CODE		0xF0


#define CMD_READ_ARRAY		0x00F0
#define CMD_UNLOCK1		0x00AA
#define CMD_UNLOCK2		0x0055
#define CMD_ERASE_SETUP		0x0080
#define CMD_ERASE_CONFIRM	0x0030
#define CMD_PROGRAM		0x00A0
#define CMD_UNLOCK_BYPASS	0x0020
#define CMD_SECTOR_UNLOCK	0x0070
#define CMD_WRITE_TO_BUF	0x0025
#define CMD_WRITE_BUF_TO_FLASH	0x0029


#define BIT_ERASE_DONE		0x0080
#define BIT_RDY_MASK		0x0080
#define BIT_PROGRAM_ERROR	0x0020
#define BIT_WR_TO_BUF_ABORT	0x0002
#define BIT_TIMEOUT		0x80000000 /* our flag */

#define READY 1
#define ERR   2
#define TMO   4

#define SWAP(x)               __swab16(x)

extern int write_data (flash_info_t *info, ulong dest, ulong data);

/***********************************************************************
 * @Function: flash_identification
 * @Return: The flash size in bytes.
 * @Descr: Identifies the flash device and fills the info flash struct.
 ***********************************************************************/
static void flash_identification( flash_info_t * info, int dev )
{
	u16 manuf_code, device_code, add_device_code, third_word;
	vu_short *base = (vu_short *)flash_base_addr[dev];
	
	base[0x555] = FLASH_CODE1;
	base[0x2aa] = FLASH_CODE2;
	base[0x555] = ID_IN_CODE;

	manuf_code = base[0x000];
	device_code = base[0x001];
	add_device_code = base[0x00e];
	third_word = base[0x00f];

	base[0x555] = FLASH_CODE1;
	base[0x2aa] = FLASH_CODE2;
	base[0x555] = ID_OUT_CODE;

	if( (u16)STM_MANUFACT == manuf_code )
	{
		/* Vendor type */
		info->flash_id = (STM_MANUFACT & FLASH_VENDMASK) | (AMD_ID_DL324B & FLASH_TYPEMASK);
		info->sector_count = 71;
		info->size = 0x00400000;
	}
}

/***********************************************************************
 * @Function: flash_number_sector
 * @Return: 
 * @Descr: 
 ***********************************************************************/
static ushort flash_number_sector( fl_org_def_t *flash_def, unsigned int nb_blocks)
{
	int i, nb_sectors = 0;

	for( i=0; i < nb_blocks; i++) {
		nb_sectors += flash_def[i].sector_number;
	}

	return nb_sectors;
}

/***********************************************************************
 * @Function: flash_unlock_sector
 * @Return: Nothing.
 * @Descr: Unlocks the selected flash sector.
 ***********************************************************************/
static void flash_unlock_sector( flash_info_t * info, unsigned int sector )
{
	vu_short *addr = (vu_short *)(info->start[sector]);
	vu_short *base = (vu_short *)(info->start[0]);

	base[0x555] = CMD_UNLOCK1;
	*addr = CMD_SECTOR_UNLOCK;
}

/***********************************************************************
 * @Function: flash_init
 * @Return: The flash size in bytes.
 * @Descr: Fills the flash_info struct and return the flash size.
 ***********************************************************************/
ulong flash_init( void )
{
	int i, j, k;
	unsigned int flash_nb_blocks, sector;
	unsigned int start_address;
	fl_org_def_t *flash;

	ulong size = 0;

	for( i = 0; i < CFG_MAX_FLASH_BANKS; i++ ) 
	{
		ulong flashbase = 0;
		
		memset( &flash_info[i], 0, sizeof(flash_info_t) );

		flash_identification( &flash_info[i], i );

		if( (flash_info[i].flash_id & FLASH_TYPEMASK) ==
			(AMD_ID_DL324B & FLASH_TYPEMASK) ) {
			flash = OrgSTM29DW323DB;
			flash_nb_blocks = sizeof( OrgSTM29DW323DB ) / sizeof( fl_org_def_t );
		} else {
			flash_nb_blocks = 0;
			flash = OrgSTM29DW323DB;
		}

		flash_info[i].sector_count = flash_number_sector( flash, flash_nb_blocks );
		
		flashbase = flash_base_addr[i];
		
		sector = 0;
		start_address = flashbase;
		flash_info[i].size = 0;

		for( j = 0; j < flash_nb_blocks; j++ ) {
			for( k = 0; k < flash[j].sector_number; k++ ) {
				flash_info[i].start[sector++] = start_address;
				start_address += flash[j].sector_size;
				flash_info[i].size += flash[j].sector_size;
			}
		}

		size += flash_info[i].size;

		if( (flash_info[i].flash_id & FLASH_TYPEMASK) ==
		    (AMD_ID_DL324B & FLASH_TYPEMASK) ) {
		    	/* Unlock all sectors at reset */
			for( j = 0; j < flash_info[i].sector_count; j++ ) {
				flash_unlock_sector( &flash_info[i], j );
			}
		}
	}

	return size;
}

/***********************************************************************
 * @Function: flash_print_info
 * @Return: Nothing.
 * @Descr: Displays information of the flash device.
 ***********************************************************************/
void flash_print_info( flash_info_t * info )
{
	int i;

	printf("flash_id: 0x%X\n", info->flash_id);
	switch( info->flash_id & FLASH_VENDMASK ){
		case (STM_MANUFACT & FLASH_VENDMASK):
			printf( "STM: " );
			break;
		default:
			printf( "info->flash_id 0x%lx\n", (ulong)info->flash_id );
			printf( "Unknown Vendor\n" );
			break;
	}

	switch( info->flash_id & FLASH_TYPEMASK ){
		case ( AMD_ID_DL324B & FLASH_TYPEMASK ):
			printf( "AMD_ID_DL324B (4MB)\n");
			break;
		default:
			printf( "Unknown Chip Type\n" );
			return;
			break;
	}

	printf( "  Size: %ld MB in %d Sectors\n",
		info->size >> 20, info->sector_count );

	printf ("  Sector Start Addresses:");
	
	for( i = 0; i < info->sector_count; i++ ) {
		if( (i % 5) == 0 ){
			printf ("\n   ");
		}
		printf (" 0x%08lX%s", info->start[i],
			info->protect[i] ? " (RO)" : "     ");
	}
	printf ("\n");
}

/***********************************************************************
 * @Function: flash_erase
 * @Return: Error code.
 * @Descr: Erased the selected number of sectors.
 ***********************************************************************/
int flash_erase( flash_info_t * info, int s_first, int s_last )
{
	vu_short *base = (vu_short *)(info->start[0]);
	ulong result;
	int iflag, prot, sect;
	int rc = ERR_OK;
	int chip1;

	/* first look for protection bits */
	if( info->flash_id == FLASH_UNKNOWN ) {
		printf( "%s: Error, unkown flash type: 0x%lx\n", __FUNCTION__, 
		        info->flash_id );
		return ERR_UNKNOWN_FLASH_TYPE;
	}

	if( (s_first < 0) || (s_first > s_last) ) {
		printf( "%s: Error in arguments\n", __FUNCTION__ );
		return ERR_INVAL;
	}

	if( (info->flash_id & FLASH_VENDMASK) !=
	    (STM_MANUFACT & FLASH_VENDMASK) ) {
		printf( "%s: Unknown vendor flash: 0x%lx\n", __FUNCTION__, 
	                info->flash_id );
		return ERR_UNKNOWN_FLASH_VENDOR;
	}

	prot = 0;
	for (sect = s_first; sect <= s_last; ++sect) {
		if (info->protect[sect]) {
			prot++;
		}
	}
	if( prot )
		return ERR_PROTECTED;

	/*
	 * Disable interrupts which might cause a timeout here.
	 */
	iflag = disable_interrupts ();

	/* Start erase on unprotected sectors */
	for( sect = s_first; sect <= s_last && !ctrlc(); sect++ ) {
		if( sect == s_first )
			printf( "Erasing sector %2d  ", sect );
		else
			printf( "%2d  ", sect );

		/* arm simple, non interrupt dependent timer */
		reset_timer_masked ();

		if( info->protect[sect] == 0 ) {	/* not protected */
			vu_short *addr = (vu_short *)(info->start[sect]);

			base[0x555] = CMD_UNLOCK1;
			base[0x2aa] = CMD_UNLOCK2;
			base[0x555] = CMD_ERASE_SETUP;

			base[0x555] = CMD_UNLOCK1;
			base[0x2aa] = CMD_UNLOCK2;
			*addr = CMD_ERASE_CONFIRM;

			/* wait until flash is ready */
			chip1 = 0;

			do{
				result = *addr;

				/* check timeout */
				if( get_timer_masked () > CFG_FLASH_ERASE_TOUT ) {
					base[0x555] = CMD_READ_ARRAY;
					chip1 = TMO;
					break;
				}

				if( !chip1 && (result & 0xFFFF) & BIT_ERASE_DONE )
					chip1 = READY;
			}while( !chip1 );

			base[0x555] = CMD_READ_ARRAY;

			if( chip1 == ERR ) {
				rc = ERR_PROG_ERROR;
				printf("flash_erase\n");
				goto outahere;
			}
			if( chip1 == TMO ) {
				rc = ERR_TIMOUT;
				goto outahere;
			}
			
			debug( "OK\n" );
		}else {			/* it was protected */
			debug( "Sector %d protected\n", sect );
		}
	}
	puts("\n");

	if( ctrlc() )
		printf( "User Interrupt!\n" );

outahere:
	/* allow flash to settle - wait 10 ms */
	udelay_masked( 10000 );

	if( iflag )
		enable_interrupts ();

	return rc;
}


/*-----------------------------------------------------------------------
 * Copy memory to flash, returns:
 * 0 - OK
 * 1 - write timeout
 * 2 - Flash not erased
 */

#define FLASH_WIDTH	2	/* flash bus width in bytes */

int write_buff (flash_info_t *info, uchar *src, ulong addr, ulong cnt)
{
	ulong cp, wp, data;
	int i, l, rc;

	wp = (addr & ~(FLASH_WIDTH-1));	/* get lower FLASH_WIDTH aligned address */

	/*
	 * handle unaligned start bytes
	 */
	if ((l = addr - wp) != 0) {
		data = 0;
		for (i=0, cp=wp; i<l; ++i, ++cp) {
			data = (data << 8) | (*(uchar *)cp);
		}
		for (; i<FLASH_WIDTH && cnt>0; ++i) {
			data = (data << 8) | *src++;
			--cnt;
			++cp;
		}
		for (; cnt==0 && i<FLASH_WIDTH; ++i, ++cp) {
			data = (data << 8) | (*(uchar *)cp);
		}

		if ((rc = write_data(info, wp, SWAP (data))) != 0) {
			return (rc);
		}
		wp += FLASH_WIDTH;
	}

	/*
	 * handle FLASH_WIDTH aligned part
	 */
	while (cnt >= FLASH_WIDTH) {
		data = 0;
		for (i=0; i<FLASH_WIDTH; ++i) {
			data = (data << 8) | *src++;
		}
		if ((rc = write_data(info, wp, SWAP (data))) != 0) {
			return (rc);
		}
		wp  += FLASH_WIDTH;
		cnt -= FLASH_WIDTH;
	}

	if (cnt == 0) {
		return (0);
	}

	/*
	 * handle unaligned tail bytes
	 */
	data = 0;
	for (i=0, cp=wp; i<FLASH_WIDTH && cnt>0; ++i, ++cp) {
		data = (data << 8) | *src++;
		--cnt;
	}
	for (; i<FLASH_WIDTH; ++i, ++cp) {
		data = (data << 8) | (*(uchar *)cp);
	}

	return (write_data(info, wp, SWAP (data)));
}

/*-----------------------------------------------------------------------
 * Write a word to Flash, returns:
 * 0 - OK
 * 1 - write timeout
 * 2 - Flash not erased
 */
extern int write_data (flash_info_t *info, ulong dest, ulong data)
{
	vu_short *addr  = (vu_short*)(info->start[0]);
	vu_short *sdest = (vu_short *)dest;
	ushort sdata = (ushort)data;
	ushort sval;
	ulong start, passed;
	int flag, rc;

	/* Check if Flash is (sufficiently) erased */
	if ((*sdest & sdata) != sdata) {
		return (2);
	}
	/* Disable interrupts which might cause a timeout here */
	flag = disable_interrupts();

	addr[0x0555] = 0x00AA;
	addr[0x02AA] = 0x0055;
	addr[0x0555] = 0x00A0;

	*sdest = sdata;

	/* re-enable interrupts if necessary */
	if (flag)
		enable_interrupts();

	rc = 0;
	/* data polling for D7 */
	start = get_timer (0);

	for (passed=0; passed < CFG_FLASH_WRITE_TOUT; passed=get_timer(start)) {

		sval = *sdest;

		if ((sval & 0x0080) == (sdata & 0x0080))
			break;

		if ((sval & 0x0020) == 0)	/* DQ5: Timeout? */
			continue;

		sval = *sdest;

		if ((sval & 0x0080) != (sdata & 0x0080))
			rc = 1;

		break;
	}

	if (passed >= CFG_FLASH_WRITE_TOUT) 
		rc = 1;

	/* reset to read mode */
	addr = (vu_short *)info->start[0];
	addr[0] = 0x00F0;	/* reset bank */

	return (rc);
}
