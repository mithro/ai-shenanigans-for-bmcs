/*
 * (C) Copyright 2006
 * Joachim Jaeger, FS Forth-Systeme GmbH, a DIGI International Company
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

/*
 * Digi CC specific functions
 */


#include <common.h>
#include <command.h>
#if (CONFIG_COMMANDS & CFG_CMD_NAND)
#include <nand.h>
#endif

#if (CONFIG_COMMANDS & CFG_CMD_BSP)
#ifdef CONFIG_DIGI_CMD

#if defined(CONFIG_CCW9C)
extern int fpga_checkbitstream(unsigned int show, uchar* fpgadata, size_t size);
volatile ulong checksum_calc, checksum_read, fpgadatasize;
#endif
DECLARE_GLOBAL_DATA_PTR;

int do_digi_boot (cmd_tbl_t * cmdtp, int flag, int argc, char *argv[])
{
	int type = 0;
	int rcode = 0;
	char *s;
	char cmd[60];
	char img[60];
	char load_address[16];
	char partition_start[16];
	char partition_size[16];

	switch (argc) {

	case 0:
	case 1:
		printf ("Usage:\n%s\n", cmdtp->usage);
		return 1;
		break;
	case 2:
		if (strcmp (argv[1], "eboot") == 0) {
			type = 3;
			if (getenv("eimg") != NULL) {
				sprintf(img, getenv("eimg"));
				sprintf(partition_start, getenv("ebootfladdr"));
				if (getenv("esize") != NULL)
					sprintf(partition_size, "%s", getenv("esize"));
				else
					sprintf(partition_size, "0xC0000");
				
				sprintf(load_address, getenv("ebootaddr"));
#ifdef CONFIG_A9M2410
				sprintf(load_address, "0x30200000");
#endif
			} else {
				printf ("variable eimg does not exist\n");
				return 1;
			}
		} else {
			printf ("Usage:\n%s\n", cmdtp->usage);
			return 1;
		}
		break;
	case 3:
		if ((s = getenv("loadaddr")) != NULL)
			sprintf(load_address, "%s",s);
		if (strcmp (argv[2], "tftp") == 0)
			type = 1;
		else if (strcmp (argv[2], "usb") == 0)
			type = 2;
		else if (strcmp (argv[2], "flash") == 0)
			type = 3;
		else {
			printf ("Usage:\n%s\n", cmdtp->usage);
			return 1;
		}
		if (strcmp (argv[1], "linux") == 0) {
			if (getenv("kimg") != NULL) {
				sprintf(img, getenv("kimg"));
#if (CONFIG_COMMANDS & CFG_CMD_NAND)
# if defined(CONFIG_CC9C_NAND)
#  if defined(CONFIG_CCW9C)
				sprintf(partition_start, "0x00280000");
				sprintf(partition_size, "0x300000");
#  else
				sprintf(partition_start, "0x00100000");
				sprintf(partition_size, "0x300000");
#  endif
# else
				sprintf(partition_start, "0x00100000");
				sprintf(partition_size, "0x300000");
# endif
#else
# ifdef CONFIG_MACH_UNC90
				sprintf(partition_start, "0x10040000");
				sprintf(partition_size, "0x2C0000");
# elif defined(CONFIG_CC9C)
				sprintf(partition_start, "0x50050000");
				sprintf(partition_size, "0x1B0000");
# elif defined(CONFIG_CCW9C)
				sprintf(partition_start, "0x501C0000");
				sprintf(partition_size, "0x300000");
# else
				sprintf(partition_start, "0x80000");
				sprintf(partition_size, "0x280000");
# endif
#endif
			} else {
				printf ("variable kimg does not exist\n");
				return 1;
			}
		} else if (strcmp (argv[1], "wce") == 0) {
			if (getenv("wimg") != NULL) {
				sprintf(img, getenv("wimg"));
				sprintf(partition_start, getenv("wcefladdr"));
				if (getenv("wcesize") != NULL)
					sprintf(partition_size, "%s", getenv("wcesize"));
				else
					sprintf(partition_size, "0x1F00000");
#ifdef CONFIG_A9M2410
				sprintf(load_address, "0x30600000");
#endif
				sprintf(load_address, getenv("wceloadaddr"));
			} else {
				printf ("variable wimg does not exist\n");
				return 1;
			}
		} else {
			printf ("Usage:\n%s\n", cmdtp->usage);
			return 1;
		}
		break;
	default:
		printf ("Usage:\n%s\n", cmdtp->usage);
		return 1;
		break;
	}
	
	if (strcmp (argv[1], "eboot") != 0)
		printf ("%s will be booted now from %s\n",img, argv[2]);
	else
		printf ("%s will be booted now\n",img);

	
	switch (type) {
	case 1:
		sprintf(cmd, "tftp %s %s",load_address, img);
		if (run_command(cmd, 0) < 0) {
			rcode = 1;
			break;
		}
		sprintf(cmd, "run snfs");
		if (run_command(cmd, 0) < 0)
			rcode = 1;
		break;
	case 2:
		sprintf(cmd, "usb reset");
		if (run_command(cmd, 0) < 0) {
			rcode = 1;
			break;
		}
		sprintf(cmd, "fatload usb 0 %s %s",load_address, img);
		if (run_command(cmd, 0) < 0) {
			rcode = 1;
			break;
		}
		sprintf(cmd, "run smtd");
		if (run_command(cmd, 0) < 0)
			rcode = 1;
		break;
	case 3:
#if (CONFIG_COMMANDS & CFG_CMD_NAND)
		sprintf(cmd, "nand read.jffs2s %s %s %s",load_address, partition_start, partition_size);
#else
		sprintf(cmd, "cp.w %s %s %s", partition_start, load_address, partition_size);
#endif
		if (run_command(cmd, 0) < 0) {
			rcode = 1;
			break;
		}
		if ((strcmp (argv[1], "eboot") != 0) && (strcmp (argv[1], "wce") != 0)) {
			sprintf(cmd, "run smtd");
			if (run_command(cmd, 0) < 0)
				rcode = 1;
		}
		break;
	default:
		break;
	}

	if (rcode == 1) {
		printf("command %s failed\n",cmd);
		return rcode;
	}

	if ((strcmp (img, getenv("wimg")) == 0) || (strcmp (img, getenv("eimg")) == 0)) {
		sprintf(cmd, "go %s",load_address);
		run_command(cmd, 0);
	} else {
		sprintf(cmd, "bootm");
		run_command(cmd, 0);
	}
	
	return 0;

}

int do_digi_update (cmd_tbl_t * cmdtp, int flag, int argc, char *argv[])
{
	int type = 0;
	int rcode = 0;
	int fpga_update = 0;
	int abort = 0;
	int ctrlc_was_pressed = 0;
	ulong fpga_crc_data_size = 0;
	ulong crc_dat;
	ulong checksum32;
	char *s;
	char cmd[60];
	char img[60];
	char load_address[16];
	char erase_start[16];
	char erase_size[16];

	switch (argc) {

	case 0:
	case 1:
	case 2:
		printf ("Usage:\n%s\n", cmdtp->usage);
		return 1;
		break;

	case 3:
		if ((s = getenv("loadaddr")) != NULL) {
			sprintf(load_address, "%s",s);
			crc_dat = simple_strtoul (s, NULL, 16);
		} else {
			sprintf(load_address, "%x",CFG_LOAD_ADDR);
			crc_dat = CFG_LOAD_ADDR;
		}
		if (strcmp (argv[2], "tftp") == 0)
			type = 1;
		else if (strcmp (argv[2], "usb") == 0)
			type = 2;
		else {
			printf ("Usage:\n%s\n", cmdtp->usage);
			return 1;
		}
		if (strcmp (argv[1], "uboot") == 0) {
			if (getenv("uimg") != NULL) {
				sprintf(img, getenv("uimg"));

#if (CONFIG_COMMANDS & CFG_CMD_NAND)
				sprintf(erase_start, "0x00000000");
				sprintf(erase_size, "0x100000");
#else
# ifdef CONFIG_MACH_UNC90
				sprintf(erase_start, "0x10000000");
				sprintf(erase_size, "0x40000");
# elif defined(CONFIG_CC9C)
				sprintf(erase_start, "0x50000000");
				sprintf(erase_size, "0x40000");
# elif defined(CONFIG_CCW9C)
				sprintf(erase_start, "0x50000000");
				sprintf(erase_size, "0x80000");
# else
				sprintf(erase_start, "0x0");
				sprintf(erase_size, "0x40000");
# endif
#endif
			} else {
				printf ("variable uimg does not exist\n");
				return 1;
			}
		} else if (strcmp (argv[1], "kernel") == 0) {
			if (getenv("kimg") != NULL) {
				sprintf(img, getenv("kimg"));
#if (CONFIG_COMMANDS & CFG_CMD_NAND)
# if defined(CONFIG_CC9C_NAND)
#  if defined(CONFIG_CCW9C)
				sprintf(erase_start, "0x00280000");
				sprintf(erase_size, "0x300000");
#  else
				sprintf(erase_start, "0x00180000");
				sprintf(erase_size, "0x300000");
#  endif
# else
				sprintf(erase_start, "0x00100000");
				sprintf(erase_size, "0x300000");
# endif
#else
# ifdef CONFIG_MACH_UNC90
				sprintf(erase_start, "0x10040000");
				sprintf(erase_size, "0x300000");
# elif defined(CONFIG_CC9C)
				sprintf(erase_start, "0x50050000");
				sprintf(erase_size, "0x1B0000");
# elif defined(CONFIG_CCW9C)
				sprintf(erase_start, "0x501C0000");
				sprintf(erase_size, "0x300000");
# else
				sprintf(erase_start, "0x80000");
				sprintf(erase_size, "0x280000");
# endif
#endif
			} else {
				printf ("variable kimg does not exist\n");
				return 1;
			}
		} else if (strcmp (argv[1], "rootfs") == 0) {
			if (getenv("rimg") != NULL) {
				sprintf(img, getenv("rimg"));
#if (CONFIG_COMMANDS & CFG_CMD_NAND)
# if defined(CONFIG_CC9C_NAND)
#  if defined(CONFIG_CCW9C)
				sprintf(erase_start, "0x00580000");
				sprintf(erase_size, getenv("flashpartsize"));
#  else
				sprintf(erase_start, "0x00480000");
				sprintf(erase_size, getenv("flashpartsize"));
#  endif
# else
				sprintf(erase_start, "0x00400000");
				sprintf(erase_size, getenv("flashpartsize"));
# endif
#else
# ifdef CONFIG_MACH_UNC90
				sprintf(erase_start, "0x10340000");
				sprintf(erase_size, "0x300000");
# elif defined(CONFIG_CC9C)
				sprintf(erase_start, "0x50200000");
				sprintf(erase_size, "0x200000");
# elif defined(CONFIG_CCW9C)
				sprintf(erase_start, "0x504C0000");
				sprintf(erase_size, "0x340000");
# else
				sprintf(erase_start, "0x300000");
				sprintf(erase_size, "0x2000000");
# endif
#endif
			} else {
				printf ("variable rimg does not exist\n");
				return 1;
			}
		} else if (strcmp (argv[1], "eboot") == 0) {
			if (getenv("eimg") != NULL) {
				sprintf(img, getenv("eimg"));
				sprintf(erase_start, getenv("ebootfladdr"));
				sprintf(erase_size, "0xC0000");
			} else {
				printf ("variable eimg does not exist\n");
				return 1;
			}
		} else if (strcmp (argv[1], "wce") == 0) {
			if (getenv("wimg") != NULL) {
				sprintf(img, getenv("wimg"));
				sprintf(erase_start, getenv("wcefladdr"));
				sprintf(erase_size, "0x1F00000");	/* 31MB */
#ifdef CONFIG_A9M2410
				sprintf(load_address, "0x30600000");
				crc_dat = simple_strtoul (load_address, NULL, 16);
#endif
			} else {
				printf ("variable wimg does not exist\n");
				return 1;
			}
#if defined(CONFIG_CCW9C)
		} else if (strcmp (argv[1], "fpga") == 0) {
			if (getenv("fimg") != NULL) {
				sprintf(img, getenv("fimg"));
				sprintf(erase_start, "%s", FPGAFLADDR);
				sprintf(erase_size, "0x100000");
			} else {
				printf ("variable fimg does not exist\n");
				return 1;
			}
#endif
		} else {
			printf ("Usage:\n%s\n", cmdtp->usage);
			return 1;
		}
		break;
	default:
		printf ("Usage:\n%s\n", cmdtp->usage);
		return 1;
		break;
	}
	
	printf ("%s will be updated now via %s\n",img, argv[2]);
	
	switch (type) {
	case 1:
		sprintf(cmd, "tftp %s %s",load_address, img);
		if (run_command(cmd, 0) < 0)
			rcode = 1;
		break;
	case 2:
		sprintf(cmd, "usb reset");
		if (run_command(cmd, 0) < 0) {
			rcode = 1;
			break;
		}
		sprintf(cmd, "fatload usb 0 %s %s",load_address, img);
		if (run_command(cmd, 0) < 0)
			rcode = 1;
		break;
	default:
		break;
	}

	if (rcode == 1) {
		printf("command %s failed\n",cmd);
		return rcode;
	}

	if (strcmp (img, getenv("wimg")) == 0) {
		sprintf(cmd, "setenv wcesize %s",getenv("filesize"));
		if (run_command(cmd, 0) < 0)
			rcode = 1;
		else
			saveenv();
	} else if (strcmp (img, getenv("eimg")) == 0) {
		sprintf(cmd, "setenv esize %s",getenv("filesize"));
		if (run_command(cmd, 0) < 0)
			rcode = 1;
		else
			saveenv();
	} else if (strcmp (img, getenv("uimg")) == 0) {
		s = getenv ("filesize");
		checksum32 = crc32 (0, (uchar *)crc_dat, simple_strtoul(s, NULL, 16));
		printf("calculated checksum = 0x%x\n", checksum32);
		printf("Do you really want to override U-Boot? (y/n)\n");

		while (!abort) {
			if (tstc()) {	/* we got a key press	*/
				switch (getc ()) {
					case 0x03:		/* ^C - Control C */
						ctrlc_was_pressed = 1;
						break;
					case 0x79:		/* yes */
						break;
					default:
						ctrlc_was_pressed = 1;
						break;
				}
				abort = 1;
			}
		}
		if (ctrlc_was_pressed == 1) {
			printf("Updating U-Boot aborted\n");
			return 1;
		}
		abort = 0;
#if defined(CONFIG_CCW9C)
	} else if (strcmp (img, getenv("fimg")) == 0) {
		sprintf(cmd, "setenv fpgasize %s",getenv("filesize"));
		if (run_command(cmd, 0) < 0)
			rcode = 1;
		else {
			volatile u_char *bbfw_bin_data;
			ulong ldaddr;
			ulong bbfw_bin_data_len;
	
			printf("Updating FPGA firmware ... \n");

			s = getenv ("filesize");
			bbfw_bin_data_len = simple_strtoul (s, NULL, 16);
			ldaddr = simple_strtoul (load_address, NULL, 16);
	
			bbfw_bin_data = (u_char*)ldaddr;
			if (fpga_checkbitstream(1, bbfw_bin_data, bbfw_bin_data_len) == LOAD_FPGA_FAIL) {
				printf("Updating FPGA firmware aborted\n");
				return 1;
			}
			
			printf("Do you really want to override the FPGA firmware? (y/n)\n");

			/* copy the calculated checksum at end of firmware */
			bbfw_bin_data = (u_char *)(ldaddr + bbfw_bin_data_len);
			*bbfw_bin_data = checksum_calc;
			*(bbfw_bin_data + 1) = checksum_calc >> 8;
			*(bbfw_bin_data + 2) = checksum_calc >> 16;
			*(bbfw_bin_data + 3) = checksum_calc >> 24;
			bbfw_bin_data_len += 4;
			
			fpga_crc_data_size = bbfw_bin_data_len;
			
			while (!abort) {
				if (tstc()) {	/* we got a key press	*/
					switch (getc ()) {
						case 0x03:		/* ^C - Control C */
							ctrlc_was_pressed = 1;
							break;
						case 0x79:		/* yes */
							break;
						default:
							ctrlc_was_pressed = 1;
							break;
					}
					abort = 1;
				}
			}
			if (ctrlc_was_pressed == 1) {
				printf("Updating FPGA firmware aborted\n");
				return 1;
			}
			fpga_update = 1;
			saveenv();	/* save fpgasize */
		}
#endif
	}

	if (rcode == 1) {
		printf("command %s failed\n",cmd);
		return rcode;
	}

#if (CONFIG_COMMANDS & CFG_CMD_NAND)
	printf( "Erasing Flash\n" );
	sprintf(cmd, "nand erase %s %s",erase_start, erase_size);
	if (run_command(cmd, 0) < 0) {
		rcode = 1;
	} else {
		if (fpga_update == 0)
			sprintf(cmd, "nand write.jffs2 %s %s %s",load_address, erase_start, getenv("filesize"));
		else
			sprintf(cmd, "nand write.jffs2 %s %s %x",load_address, erase_start, fpga_crc_data_size);
		if (run_command(cmd, 0) < 0)
			rcode = 1;
	}
	if (rcode == 1) {
		printf("command %s failed\n",cmd);
		return rcode;
	}
#else
	printf( "Erasing Flash (may take a while)\n" );
	if ((strcmp (argv[1], "uboot") == 0) || (strcmp (argv[1], "fpga") == 0)) {
		sprintf(cmd, "protect off %s +%s",erase_start, erase_size);
		if (run_command(cmd, 0) < 0)
			rcode = 1;
	}
	if (rcode == 1) {
		printf("command %s failed\n",cmd);
		return rcode;
	}

	sprintf(cmd, "erase %s +%s",erase_start, erase_size);
	if (run_command(cmd, 0) < 0) {
		printf("command %s failed\n",cmd);
		return 1;
	}
	if (fpga_update == 0)
		sprintf(cmd, "cp.b %s %s %s",load_address, erase_start, getenv("filesize"));
	else
		sprintf(cmd, "cp.b %s %s %x",load_address, erase_start, fpga_crc_data_size);
	if (run_command(cmd, 0) < 0) {
		printf("command %s failed\n",cmd);
		return 1;
	}
	if ((strcmp (argv[1], "uboot") == 0) || (strcmp (argv[1], "fpga") == 0)) {
		sprintf(cmd, "protect on %s +%s",erase_start, erase_size);
		if (run_command(cmd, 0) < 0) {
			printf("command %s failed\n",cmd);
			return 1;
		}
	}
#endif
	if (strcmp (img, getenv("fimg")) != 0) {
		s = getenv ("filesize");
		checksum32 = crc32 (0, (uchar *)crc_dat, simple_strtoul(s, NULL, 16));
		printf("  calculated checksum = 0x%x\n", checksum32);
	}
	return 0;
}

int do_envreset (cmd_tbl_t * cmdtp, int flag, int argc, char *argv[]) {

	uchar data[CFG_ENV_SIZE];
#ifdef CFG_ENV_IS_IN_EEPROM
	uint addr = CFG_I2C_EEPROM_ADDR;
#endif
	char cmd[60];
	char bcmd[80];
	char ethadr[20];
	char wlanadr[20];
	char *s;
	int e1 = 0;
	int e2 = 0;
	int e3 = 0;
#ifndef CFG_ENV_IS_IN_EEPROM
	int ret = 0;
#endif

	switch (argc) {

	case 1:
		break;

	default:
		printf ("Usage:\n%s\n", cmdtp->usage);
		return 1;
	}

	printf ("Environment will be set to Default now!\n");
	
	if ((s = getenv("bootcmd")) != NULL) {
		sprintf(bcmd, getenv("bootcmd"));
		e1 = 1;
	}

	if ((s = getenv("ethaddr")) != NULL) {
		sprintf(ethadr, getenv("ethaddr"));
		e2 = 1;
	}

	if ((s = getenv("wlanaddr")) != NULL) {
		sprintf(wlanadr, getenv("wlanaddr"));
		e3 = 1;
	}

	memset (data, 0xFF, CFG_ENV_SIZE);
#ifdef CFG_ENV_IS_IN_NAND
#ifdef CONFIG_GCC41
	nand_info_t *nand;
	struct erase_info instr;
	int i;

	for (i = 0; i < CFG_MAX_NAND_DEVICE; i++) {
		if (nand_info[i].name)
			break;
	}
	nand = &nand_info[i];
	
	instr.mtd = nand;
	instr.addr = CFG_ENV_OFFSET;
	instr.len = CFG_ENV_SIZE;
	instr.callback = 0;

	if (nand->erase(nand, &instr)) {
		printf ("Erasing of Environment failed!\n");
		return 1;
	}
#else
	if (nand_erase(&nand_info[0], CFG_ENV_OFFSET, CFG_ENV_SIZE)) {
		printf ("Erasing of Environment failed!\n");
		return 1;
	}
#endif

	ulong total = CFG_ENV_SIZE;
#ifdef CONFIG_GCC41
	ret = nand->write(nand, CFG_ENV_OFFSET, (size_t) total, (size_t *)&total, (u_char *)data);
#else
	ret = nand_write(&nand_info[0], CFG_ENV_OFFSET, &total, (u_char*)data);
#endif
	if (ret || total != CFG_ENV_SIZE) {
		printf ("Writing 0xFF to Environment failed!\n");
		return 1;
	}

#elif defined CFG_ENV_IS_IN_EEPROM
	if (eeprom_write (addr, CFG_ENV_OFFSET, data, CFG_ENV_SIZE)) {
		printf("EEPROM write failed\n");
		return 1;
	}

#elif defined CFG_ENV_IS_IN_FLASH
	if (flash_sect_protect (0, (ulong)CFG_ENV_ADDR, ((CFG_ENV_ADDR + CFG_ENV_SECT_SIZE)-1))) {
		printf ("Unprotecting Environment sector failed!\n");
		return 1;
	}

	if (flash_sect_erase (CFG_ENV_ADDR, ((CFG_ENV_ADDR + CFG_ENV_SECT_SIZE)-1))) {
		printf ("Erasing of Environment failed!\n");
		return 1;
	}

	ret = flash_write((char *)data, CFG_ENV_ADDR, CFG_ENV_SECT_SIZE);
	if (ret != 0) {
		printf ("Writing 0xFF to Environment failed!\n");
		return 1;
	}
	(void) flash_sect_protect (1, (ulong)CFG_ENV_ADDR, ((CFG_ENV_ADDR + CFG_ENV_SECT_SIZE)-1));
#endif
	gd->env_valid = 0;
	env_relocate ();

	sprintf(cmd, "saveenv");	/* do_saveenv includes 1-wire EEPROM for CCXP */
	if (e1 != 0)
		setenv("bootcmd",bcmd);
	if (e2 != 0)
		setenv("ethaddr",ethadr);
	if (e3 != 0)
		setenv("wlanaddr",wlanadr);

	if ((e1 + e2 + e3) > 0)
		run_command(cmd, 0);
	
	return 0;
}

U_BOOT_CMD(
	dboot,	3,	0,	do_digi_boot,
	"dboot   - Digi CCxx modules boot commands\n",
	"[OS] [type] ([partition])\n"
	"  - boots `OS' of `type' of `partition'\n"
	"    values for `OS': linux, wce, eboot\n"
	"    values for `type': flash, tftp, usb\n"
	"    values for `partition': 0, 1,.. (optional)\n"
);

U_BOOT_CMD(
	update,	3,	0,	do_digi_update,
	"update  - Digi CCxx modules update commands\n",
	"[file] [type] ([partition])\n"
	"  - updates `file' via `type' in `partition'\n"
	"    values for `file': uboot, kernel, rootfs, eboot, wce\n"
	"    values for `type': tftp, usb\n"
	"    values for `partition': 0, 1,.. (optional)\n"
);

U_BOOT_CMD(
	envreset,	1,	0,	do_envreset,
	"envreset- Sets environment variables to default setting\n",
	"\n"
	"  - overwrites all current variables\n"
);

#endif	/* (CONFIG_DIGI_CMD) */
#endif	/* (CONFIG_COMMANDS & CFG_CMD_BSP) */
