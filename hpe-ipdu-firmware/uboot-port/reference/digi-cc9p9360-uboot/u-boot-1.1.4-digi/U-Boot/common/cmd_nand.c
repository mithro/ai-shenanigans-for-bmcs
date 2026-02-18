/*
 * Driver for NAND support, Rick Bronson
 * borrowed heavily from:
 * (c) 1999 Machine Vision Holdings, Inc.
 * (c) 1999, 2000 David Woodhouse <dwmw2@infradead.org>
 *
 * Added 16-bit nand support
 * (C) 2004 Texas Instruments
 */

#include <common.h>

#ifdef CONFIG_A9M2410
# include <a9m2410_nand.h>
#endif

#ifdef CPU_2440
# include <s3c2440.h>
#endif	/* CPU_2440 */


#ifndef CFG_NAND_LEGACY
/*
 *
 * New NAND support
 *
 */
#include <common.h>

#if (CONFIG_COMMANDS & CFG_CMD_NAND)

#include <command.h>
#include <watchdog.h>
#include <malloc.h>
#include <asm/byteorder.h>

#ifdef CONFIG_SHOW_BOOT_PROGRESS
# include <status_led.h>
# define SHOW_BOOT_PROGRESS(arg)	show_boot_progress(arg)
#else
# define SHOW_BOOT_PROGRESS(arg)
#endif

#include <jffs2/jffs2.h>
#include <nand.h>

extern nand_info_t nand_info[];       /* info for NAND chips */

static int nand_dump_oob(nand_info_t *nand, ulong off)
{
	return 0;
}

static int nand_dump(nand_info_t *nand, ulong off)
{
	int i;
	u_char *buf, *p;

	buf = malloc(nand->oobblock + nand->oobsize);
	if (!buf) {
		puts("No memory for page buffer\n");
		return 1;
	}
	off &= ~(nand->oobblock - 1);
	i = nand_read_raw(nand, buf, off, nand->oobblock, nand->oobsize);
	if (i < 0) {
		printf("Error (%d) reading page %08x\n", i, off);
		free(buf);
		return 1;
	}
	printf("Page %08x dump:\n", off);
	i = nand->oobblock >> 4; p = buf;
	while (i--) {
		printf( "\t%02x %02x %02x %02x %02x %02x %02x %02x"
			"  %02x %02x %02x %02x %02x %02x %02x %02x\n",
			p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7],
			p[8], p[9], p[10], p[11], p[12], p[13], p[14], p[15]);
		p += 16;
	}
	puts("OOB:\n");
	i = nand->oobsize >> 3;
	while (i--) {
		printf( "\t%02x %02x %02x %02x %02x %02x %02x %02x\n",
			p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]);
		p += 8;
	}
	free(buf);

	return 0;
}

/* ------------------------------------------------------------------------- */

static void
arg_off_size(int argc, char *argv[], ulong *off, ulong *size, ulong totsize)
{
	*off = 0;
	*size = 0;

#if defined(CONFIG_JFFS2_NAND) && defined(CFG_JFFS_CUSTOM_PART)
	if (argc >= 1 && strcmp(argv[0], "partition") == 0) {
		int part_num;
		struct part_info *part;
		const char *partstr;

		if (argc >= 2)
			partstr = argv[1];
		else
			partstr = getenv("partition");

		if (partstr)
			part_num = (int)simple_strtoul(partstr, NULL, 10);
		else
			part_num = 0;

		part = jffs2_part_info(part_num);
		if (part == NULL) {
			printf("\nInvalid partition %d\n", part_num);
			return;
		}
		*size = part->size;
		*off = (ulong)part->offset;
	} else
#endif
	{
		if (argc >= 1)
			*off = (ulong)simple_strtoul(argv[0], NULL, 16);
		else
			*off = 0;

		if (argc >= 2)
			*size = (ulong)simple_strtoul(argv[1], NULL, 16);
		else
			*size = totsize - *off;

	}

}

int do_nand(cmd_tbl_t * cmdtp, int flag, int argc, char *argv[])
{
	int i, dev, ret;
	ulong addr, off, size;
	char *cmd, *s;
	nand_info_t *nand;

	/* at least two arguments please */
	if (argc < 2)
		goto usage;

	cmd = argv[1];

	if (strcmp(cmd, "info") == 0) {

		putc('\n');
		for (i = 0; i < CFG_MAX_NAND_DEVICE; i++) {
			if (nand_info[i].name)
				printf("Device %d: %s, block size %lu KiB\n",
					i, nand_info[i].name,
					nand_info[i].erasesize >> 10);
		}
		return 0;
	}

	if (strcmp(cmd, "device") == 0) {

		if (argc < 3) {
			if ((nand_curr_device < 0) ||
			    (nand_curr_device >= CFG_MAX_NAND_DEVICE))
				puts("\nno devices available\n");
			else
				printf("\nDevice %d: %s\n", nand_curr_device,
					nand_info[nand_curr_device].name);
			return 0;
		}
		dev = (int)simple_strtoul(argv[2], NULL, 10);
		if (dev < 0 || dev >= CFG_MAX_NAND_DEVICE || !nand_info[dev].name) {
			puts("No such device\n");
			return 1;
		}
		printf("Device %d: %s", dev, nand_info[dev].name);
		puts("... is now current device\n");
		nand_curr_device = dev;
		return 0;
	}

	if (strcmp(cmd, "bad") != 0 && strcmp(cmd, "erase") != 0 &&
	    strncmp(cmd, "dump", 4) != 0 &&
	    strncmp(cmd, "read", 4) != 0 && strncmp(cmd, "write", 5) != 0)
		goto usage;

	/* the following commands operate on the current device */
	if (nand_curr_device < 0 || nand_curr_device >= CFG_MAX_NAND_DEVICE ||
	    !nand_info[nand_curr_device].name) {
		puts("\nno devices available\n");
		return 1;
	}
	nand = &nand_info[nand_curr_device];

	if (strcmp(cmd, "bad") == 0) {
		printf("\nDevice %d bad blocks:\n", nand_curr_device);
		for (off = 0; off < nand->size; off += nand->erasesize)
#ifdef CONFIG_GCC41
			if (nand->block_isbad(nand, off))
#else
			if (nand_block_isbad(nand, off))
#endif
				printf("  %08x\n", off);
		return 0;
	}

	if (strcmp(cmd, "erase") == 0) {
		arg_off_size(argc - 2, argv + 2, &off, &size, nand->size);
		if (off == 0 && size == 0)
			return 1;

		printf("\nNAND erase: device %d offset 0x%x, size 0x%x ",
		       nand_curr_device, off, size);
#ifdef CONFIG_GCC41
		struct erase_info instr;

		instr.mtd = nand;
		instr.addr = off;
		instr.len = size;
		instr.callback = 0;

		ret = nand->erase(nand, &instr);
#else
		ret = nand_erase(nand, off, size);
#endif
		printf("%s\n", ret ? "ERROR" : "OK");

		return ret == 0 ? 0 : 1;
	}

	if (strncmp(cmd, "dump", 4) == 0) {
		if (argc < 3)
			goto usage;

		s = strchr(cmd, '.');
		off = (int)simple_strtoul(argv[2], NULL, 16);

		if (s != NULL && strcmp(s, ".oob") == 0)
			ret = nand_dump_oob(nand, off);
		else
			ret = nand_dump(nand, off);

		return ret == 0 ? 1 : 0;

	}

	/* read write */
	if (strncmp(cmd, "read", 4) == 0 || strncmp(cmd, "write", 5) == 0) {
		if (argc < 4)
			goto usage;
/*
		s = strchr(cmd, '.');
		clean = CLEAN_NONE;
		if (s != NULL) {
			if (strcmp(s, ".jffs2") == 0 || strcmp(s, ".e") == 0
			    || strcmp(s, ".i"))
				clean = CLEAN_JFFS2;
		}
*/
		addr = (ulong)simple_strtoul(argv[2], NULL, 16);

		arg_off_size(argc - 3, argv + 3, &off, &size, nand->size);
		if (off == 0 && size == 0)
			return 1;

		i = strncmp(cmd, "read", 4) == 0;	/* 1 = read, 0 = write */
		printf("\nNAND %s: device %d offset %u, size %u ... ",
		       i ? "read" : "write", nand_curr_device, off, size);

#if 0
		char* cmdtail = strchr(argv[1], '.');

		if (cmdtail && !strncmp(cmdtail, ".oob", 2)) {
			ret = nand_write_oob(nand, off, &size, (u_char*)addr);
			printf(" in OOB %d bytes %s: %s\n", size,
			i ? "read" : "written", ret ? "ERROR" : "OK");
		} else {
#endif
		if (i)
#ifdef CONFIG_GCC41
			ret = nand->read(nand, off, (size_t) size, (size_t *)&size, (u_char *)addr);
#else
			ret = nand_read(nand, off, &size, (u_char *)addr);
#endif
		else
#ifdef CONFIG_GCC41
			ret = nand->write(nand, off, (size_t) size, (size_t *)&size, (u_char *)addr);
#else
			ret = nand_write(nand, off, &size, (u_char *)addr);
#endif

		printf(" %d bytes %s: %s\n", size,
		       i ? "read" : "written", ret ? "ERROR" : "OK");
#if 0
		}
#endif

		return ret == 0 ? 0 : 1;
	}
usage:
	printf("Usage:\n%s\n", cmdtp->usage);
	return 1;
}

U_BOOT_CMD(nand, 5, 1, do_nand,
	"nand    - NAND sub-system\n",
	"info                  - show available NAND devices\n"
	"nand device [dev]     - show or set current device\n"
	"nand read[.jffs2]     - addr off size\n"
	"nand write[.jffs2]    - addr off size - read/write `size' bytes starting\n"
	"    at offset `off' to/from memory address `addr'\n"
	"nand erase [off size] - erase `size' bytes from\n"
	"    offset `off' (entire device if not specified)\n"
	"nand bad - show bad blocks\n"
	"nand dump[.oob] off - dump page\n"
	"nand scrub - really clean NAND erasing bad blocks (UNSAFE)\n"
	"nand markbad off - mark bad block at offset (UNSAFE)\n"
	"nand biterr off - make a bit error at offset (UNSAFE)\n");

int do_nandboot(cmd_tbl_t * cmdtp, int flag, int argc, char *argv[])
{
	char *boot_device = NULL;
	char *ep;
	int dev;
	int r;
	ulong addr, cnt, offset = 0;
	image_header_t *hdr;
	nand_info_t *nand;

	switch (argc) {
	case 1:
		addr = CFG_LOAD_ADDR;
		boot_device = getenv("bootdevice");
		break;
	case 2:
		addr = simple_strtoul(argv[1], NULL, 16);
		boot_device = getenv("bootdevice");
		break;
	case 3:
		addr = simple_strtoul(argv[1], NULL, 16);
		boot_device = argv[2];
		break;
	case 4:
		addr = simple_strtoul(argv[1], NULL, 16);
		boot_device = argv[2];
		offset = simple_strtoul(argv[3], NULL, 16);
		break;
	default:
		printf("Usage:\n%s\n", cmdtp->usage);
		SHOW_BOOT_PROGRESS(-1);
		return 1;
	}

	if (!boot_device) {
		puts("\n** No boot device **\n");
		SHOW_BOOT_PROGRESS(-1);
		return 1;
	}

	dev = simple_strtoul(boot_device, &ep, 16);

	if (dev < 0 || dev >= CFG_MAX_NAND_DEVICE || !nand_info[dev].name) {
		printf("\n** Device %d not available\n", dev);
		SHOW_BOOT_PROGRESS(-1);
		return 1;
	}

	nand = &nand_info[dev];
	printf("\nLoading from device %d: %s (offset 0x%lx)\n",
	       dev, nand->name, offset);

	cnt = nand->oobblock;
#ifdef CONFIG_GCC41
	r = nand->read(nand, offset, (size_t) cnt, (size_t *)&cnt, (u_char *)addr);
#else
	r = nand_read(nand, offset, &cnt, (u_char *) addr);
#endif
	if (r) {
		printf("** Read error on %d\n", dev);
		SHOW_BOOT_PROGRESS(-1);
		return 1;
	}

	hdr = (image_header_t *) addr;

	if (ntohl(hdr->ih_magic) != IH_MAGIC) {
		printf("\n** Bad Magic Number 0x%x **\n", hdr->ih_magic);
		SHOW_BOOT_PROGRESS(-1);
		return 1;
	}

	print_image_hdr(hdr);

	cnt = (ntohl(hdr->ih_size) + sizeof (image_header_t));

#ifdef CONFIG_GCC41
	r = nand->read(nand, offset, (size_t) cnt, (size_t *)&cnt, (u_char *)addr);
#else
	r = nand_read(nand, offset, &cnt, (u_char *) addr);
#endif
	if (r) {
		printf("** Read error on %d\n", dev);
		SHOW_BOOT_PROGRESS(-1);
		return 1;
	}

	/* Loading ok, update default load address */

	load_addr = addr;

	/* Check if we should attempt an auto-start */
	if (((ep = getenv("autostart")) != NULL) && (strcmp(ep, "yes") == 0)) {
		char *local_args[2];
		extern int do_bootm(cmd_tbl_t *, int, int, char *[]);

		local_args[0] = argv[0];
		local_args[1] = NULL;

		printf("Automatic boot of image at addr 0x%08lx ...\n", addr);

		do_bootm(cmdtp, 0, 1, local_args);
		return 1;
	}
	return 0;
}

U_BOOT_CMD(nboot, 4, 1, do_nandboot,
	"nboot   - boot from NAND device\n", "loadAddr dev\n");


#endif				/* (CONFIG_COMMANDS & CFG_CMD_NAND) */

#else /* CFG_NAND_LEGACY */
/*
 *
 * Legacy NAND support - to be phased out
 *
 */
#include <command.h>
#include <malloc.h>
#include <asm/io.h>
#include <watchdog.h>

#ifdef CONFIG_SHOW_BOOT_PROGRESS
# include <status_led.h>
# define SHOW_BOOT_PROGRESS(arg)	show_boot_progress(arg)
#else
# define SHOW_BOOT_PROGRESS(arg)
#endif

#if (CONFIG_COMMANDS & CFG_CMD_NAND)

#ifdef CONFIG_AT91RM9200DK
# include <asm/arch/hardware.h>
#endif

#include <linux/mtd/nand_legacy.h>
#if 0
#include <linux/mtd/nand_ids.h>
#include <jffs2/jffs2.h>
#endif

#ifdef CONFIG_OMAP1510
void archflashwp(void *archdata, int wp);
#endif

#define ROUND_DOWN(value,boundary)      ((value) & (~((boundary)-1)))

#undef	NAND_DEBUG
#undef	PSYCHO_DEBUG

/* ****************** WARNING *********************
 * When ALLOW_ERASE_BAD_DEBUG is non-zero the erase command will
 * erase (or at least attempt to erase) blocks that are marked
 * bad. This can be very handy if you are _sure_ that the block
 * is OK, say because you marked a good block bad to test bad
 * block handling and you are done testing, or if you have
 * accidentally marked blocks bad.
 *
 * Erasing factory marked bad blocks is a _bad_ idea. If the
 * erase succeeds there is no reliable way to find them again,
 * and attempting to program or erase bad blocks can affect
 * the data in _other_ (good) blocks.
 */
#define	 ALLOW_ERASE_BAD_DEBUG 0

#define CONFIG_MTD_NAND_ECC  /* enable ECC */
#define CONFIG_MTD_NAND_ECC_JFFS2

/* bits for nand_legacy_rw() `cmd'; or together as needed */
#define NANDRW_READ	0x01
#define NANDRW_WRITE	0x00
#define NANDRW_JFFS2	0x02
#define NANDRW_JFFS2_SKIP	0x04

/*
 * Imports from nand_legacy.c
 */
#ifdef HW_ECC_2440
static void NF_Reset(void);
static void NF_Init(void);
static int NF8_ReadPage(u32 block, u32 page, u8 *buffer);
static int NF8_WritePage(u32 block, u32 page, u8 *buffer);
static int NF8_MarkBadBlock(u32 block);
static int s3c2440_nand_write(ulong srcAddress,ulong targetBlock,ulong targetSize);
static int s3c2440_nand_read(ulong dst_addr,ulong src_addr,ulong size);

extern int is_bad_block(unsigned long addr);

#endif	/* HW_ECC_2440 */

extern struct nand_chip nand_dev_desc[CFG_MAX_NAND_DEVICE];
extern int curr_device;
extern int nand_legacy_erase(struct nand_chip *nand, size_t ofs,
			    size_t len, int clean);
extern int nand_legacy_rw(struct nand_chip *nand, int cmd, size_t start,
			 size_t len, size_t *retlen, u_char *buf);
extern void nand_print(struct nand_chip *nand);
extern void nand_print_bad(struct nand_chip *nand);
extern int nand_read_oob(struct nand_chip *nand, size_t ofs,
			       size_t len, size_t *retlen, u_char *buf);
extern int nand_write_oob(struct nand_chip *nand, size_t ofs,
				size_t len, size_t *retlen, const u_char *buf);


int do_nand (cmd_tbl_t *cmdtp, int flag, int argc, char *argv[])
{
    int rcode = 0;

    switch (argc) {
    case 0:
    case 1:
	printf ("Usage:\n%s\n", cmdtp->usage);
	return 1;
    case 2:
	if (strcmp(argv[1],"info") == 0) {
		int i;

		putc ('\n');

		for (i=0; i<CFG_MAX_NAND_DEVICE; ++i) {
			if(nand_dev_desc[i].ChipID == NAND_ChipID_UNKNOWN)
				continue; /* list only known devices */
			printf ("Device %d: ", i);
			nand_print(&nand_dev_desc[i]);
		}
		return 0;

	} else if (strcmp(argv[1],"device") == 0) {
		if ((curr_device < 0) || (curr_device >= CFG_MAX_NAND_DEVICE)) {
			puts ("\nno devices available\n");
			return 1;
		}
		printf ("\nDevice %d: ", curr_device);
		nand_print(&nand_dev_desc[curr_device]);
		return 0;

	} else if (strcmp(argv[1],"bad") == 0) {
		if ((curr_device < 0) || (curr_device >= CFG_MAX_NAND_DEVICE)) {
			puts ("\nno devices available\n");
			return 1;
		}
		printf ("\nDevice %d bad blocks:\n", curr_device);
		nand_print_bad(&nand_dev_desc[curr_device]);
		return 0;

	}
	printf ("Usage:\n%s\n", cmdtp->usage);
	return 1;
    case 3:
	if (strcmp(argv[1],"device") == 0) {
		int dev = (int)simple_strtoul(argv[2], NULL, 10);

		printf ("\nDevice %d: ", dev);
		if (dev >= CFG_MAX_NAND_DEVICE) {
			puts ("unknown device\n");
			return 1;
		}
		nand_print(&nand_dev_desc[dev]);
		/*nand_print (dev);*/

		if (nand_dev_desc[dev].ChipID == NAND_ChipID_UNKNOWN) {
			return 1;
		}

		curr_device = dev;

		puts ("... is now current device\n");

		return 0;
	} else if (strcmp(argv[1],"erase") == 0 && strcmp(argv[2], "clean") == 0) {
		struct nand_chip* nand = &nand_dev_desc[curr_device];
		ulong off = 0;
		ulong size = nand->totlen;
		int ret;

		printf ("\nNAND erase: device %d offset %ld, size %ld ... ",
			curr_device, off, size);

		ret = nand_legacy_erase (nand, off, size, 1);

		printf("%s\n", ret ? "ERROR" : "OK");

		return ret;
	}

	printf ("Usage:\n%s\n", cmdtp->usage);
	return 1;
    default:
	/* at least 4 args */

	if (strncmp(argv[1], "read", 4) == 0 ||
	    strncmp(argv[1], "write", 5) == 0) {
		ulong addr = simple_strtoul(argv[2], NULL, 16);
		ulong off  = simple_strtoul(argv[3], NULL, 16);
		ulong size = simple_strtoul(argv[4], NULL, 16);
		int cmd    = (strncmp(argv[1], "read", 4) == 0) ?
				NANDRW_READ : NANDRW_WRITE;
		int ret, total;
		char* cmdtail = strchr(argv[1], '.');

		if (cmdtail && !strncmp(cmdtail, ".oob", 2)) {
			/* read out-of-band data */
			if (cmd & NANDRW_READ) {
				ret = nand_read_oob(nand_dev_desc + curr_device,
						    off, size, (size_t *)&total,
						    (u_char*)addr);
			} else {
				ret = nand_write_oob(nand_dev_desc + curr_device,
						     off, size, (size_t *)&total,
						     (u_char*)addr);
			}
			return ret;

		} else if (cmdtail && !strncmp(cmdtail, ".jffs2s", 2)) {
			cmd |= NANDRW_JFFS2;	/* skip bad blocks (on read too) */
			if (cmd & NANDRW_READ)
				cmd |= NANDRW_JFFS2_SKIP;	/* skip bad blocks (on read too) */

		} else if (cmdtail && !strncmp(cmdtail, ".jffs2", 2))
			cmd |= NANDRW_JFFS2;	/* skip bad blocks */
#ifdef SXNI855T
		/* need ".e" same as ".j" for compatibility with older units */
		else if (cmdtail && !strcmp(cmdtail, ".e"))
			cmd |= NANDRW_JFFS2;	/* skip bad blocks */
#endif
#ifdef CFG_NAND_SKIP_BAD_DOT_I
		/* need ".i" same as ".jffs2s" for compatibility with older units (esd) */
		/* ".i" for image -> read skips bad block (no 0xff) */
		else if (cmdtail && !strcmp(cmdtail, ".i")) {
			cmd |= NANDRW_JFFS2;	/* skip bad blocks (on read too) */
			if (cmd & NANDRW_READ)
				cmd |= NANDRW_JFFS2_SKIP;	/* skip bad blocks (on read too) */
		}
#endif /* CFG_NAND_SKIP_BAD_DOT_I */
		else if (cmdtail) {
			printf ("Usage:\n%s\n", cmdtp->usage);
			return 1;
		}

		printf ("\nNAND %s: device %d offset %ld, size %ld ... ",
			(cmd & NANDRW_READ) ? "read" : "write",
			curr_device, off, size);

#ifndef HW_ECC_2440
		ret = nand_legacy_rw(nand_dev_desc + curr_device, cmd, off, size,
			     (size_t *)&total, (u_char*)addr);
#else
		if (cmd & NANDRW_READ) {
			NF_Init();
			NF_Reset();
			ret = s3c2440_nand_read(addr,off,size);
		} else {
			NF_Init();
			NF_Reset();
			ret = s3c2440_nand_write(addr,off,size);
		}
		total = size;
#endif	/* HW_ECC_2440 */

		printf (" %d bytes %s: %s\n", total,
			(cmd & NANDRW_READ) ? "read" : "written",
			ret ? "ERROR" : "OK");

		return ret;
	} else if (strcmp(argv[1],"erase") == 0 &&
		   (argc == 4 || strcmp("clean", argv[2]) == 0)) {
		int clean = argc == 5;
		ulong off = simple_strtoul(argv[2 + clean], NULL, 16);
		ulong size = simple_strtoul(argv[3 + clean], NULL, 16);
		int ret;

		printf ("\nNAND erase: device %d offset %ld, size %ld ... ",
			curr_device, off, size);

		ret = nand_legacy_erase (nand_dev_desc + curr_device,
					off, size, clean);

		printf("%s\n", ret ? "ERROR" : "OK");

		return ret;
	} else {
		printf ("Usage:\n%s\n", cmdtp->usage);
		rcode = 1;
	}

	return rcode;
    }
}

U_BOOT_CMD(
	nand,	5,	1,	do_nand,
	"nand    - NAND sub-system\n",
	"info  - show available NAND devices\n"
	"nand device [dev] - show or set current device\n"
	"nand read[.jffs2[s]]  addr off size\n"
	"nand write[.jffs2] addr off size - read/write `size' bytes starting\n"
	"    at offset `off' to/from memory address `addr'\n"
	"nand erase [clean] [off size] - erase `size' bytes from\n"
	"    offset `off' (entire device if not specified)\n"
	"nand bad - show bad blocks\n"
	"nand read.oob addr off size - read out-of-band data\n"
	"nand write.oob addr off size - write out-of-band data\n"
);

int do_nandboot (cmd_tbl_t *cmdtp, int flag, int argc, char *argv[])
{
	char *boot_device = NULL;
	char *ep;
	int dev;
	ulong cnt;
	ulong addr;
	ulong offset = 0;
	image_header_t *hdr;
	int rcode = 0;
	switch (argc) {
	case 1:
		addr = CFG_LOAD_ADDR;
		boot_device = getenv ("bootdevice");
		break;
	case 2:
		addr = simple_strtoul(argv[1], NULL, 16);
		boot_device = getenv ("bootdevice");
		break;
	case 3:
		addr = simple_strtoul(argv[1], NULL, 16);
		boot_device = argv[2];
		break;
	case 4:
		addr = simple_strtoul(argv[1], NULL, 16);
		boot_device = argv[2];
		offset = simple_strtoul(argv[3], NULL, 16);
		break;
	default:
		printf ("Usage:\n%s\n", cmdtp->usage);
		SHOW_BOOT_PROGRESS (-1);
		return 1;
	}

	if (!boot_device) {
		puts ("\n** No boot device **\n");
		SHOW_BOOT_PROGRESS (-1);
		return 1;
	}

	dev = simple_strtoul(boot_device, &ep, 16);

	if ((dev >= CFG_MAX_NAND_DEVICE) ||
	    (nand_dev_desc[dev].ChipID == NAND_ChipID_UNKNOWN)) {
		printf ("\n** Device %d not available\n", dev);
		SHOW_BOOT_PROGRESS (-1);
		return 1;
	}

	printf ("\nLoading from device %d: %s at 0x%lx (offset 0x%lx)\n",
		dev, nand_dev_desc[dev].name, nand_dev_desc[dev].IO_ADDR,
		offset);

	if (nand_legacy_rw (nand_dev_desc + dev, NANDRW_READ, offset,
			SECTORSIZE, NULL, (u_char *)addr)) {
		printf ("** Read error on %d\n", dev);
		SHOW_BOOT_PROGRESS (-1);
		return 1;
	}

	hdr = (image_header_t *)addr;

	if (ntohl(hdr->ih_magic) == IH_MAGIC) {

		print_image_hdr (hdr);

		cnt = (ntohl(hdr->ih_size) + sizeof(image_header_t));
		cnt -= SECTORSIZE;
	} else {
		printf ("\n** Bad Magic Number 0x%x **\n", ntohl(hdr->ih_magic));
		SHOW_BOOT_PROGRESS (-1);
		return 1;
	}

	if (nand_legacy_rw (nand_dev_desc + dev, NANDRW_READ,
			offset + SECTORSIZE, cnt, NULL,
			(u_char *)(addr+SECTORSIZE))) {
		printf ("** Read error on %d\n", dev);
		SHOW_BOOT_PROGRESS (-1);
		return 1;
	}

	/* Loading ok, update default load address */

	load_addr = addr;

	/* Check if we should attempt an auto-start */
	if (((ep = getenv("autostart")) != NULL) && (strcmp(ep,"yes") == 0)) {
		char *local_args[2];
		extern int do_bootm (cmd_tbl_t *, int, int, char *[]);

		local_args[0] = argv[0];
		local_args[1] = NULL;

		printf ("Automatic boot of image at addr 0x%08lx ...\n", addr);

		do_bootm (cmdtp, 0, 1, local_args);
		rcode = 1;
	}
	return rcode;
}

U_BOOT_CMD(
	nboot,	4,	1,	do_nandboot,
	"nboot   - boot from NAND device\n",
	"loadAddr dev off\n"
);


#ifdef HW_ECC_2440

#define BAD_CHECK	(0)
#define ECC_CHECK	(0)

#define FAIL	0
#define OK	1

u8 NF8_Spare_Data[16];

static u8 se8Buf[16]={
	0xff,0xff,0xff,0xff,
	0xff,0xff,0xff,0xff,
	0xff,0xff,0xff,0xff,
	0xff,0xff,0xff,0xff
};


/*
 * NF_Reset :
 */
void NF_Reset(void)
{
	int i;

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	NAND_ENABLE_CE(nand);
	NF_CLEAR_RB();

	nand->NFCMMD = NAND_CMD_RESET;

	for(i=0;i<10;i++);
	NF_DETECT_RB();
	NAND_DISABLE_CE(nand);
}

/*
 * NF_Init :
 */
static void NF_Init(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	nand->NFCONF = (TACLS<<12)|(TWRPH0<<8)|(TWRPH1<<4)|(0<<0);
	/*
	TACLS        [14:12]         CLE&ALE duration = HCLK*TACLS.
	TWRPH0       [10:8]          TWRPH0 duration = HCLK*(TWRPH0+1)
	TWRPH1       [6:4]           TWRPH1 duration = HCLK*(TWRPH1+1)
	AdvFlash(R)  [3]             Advanced NAND, 0:256/512, 1:1024/2048
	PageSize(R)  [2]             NAND memory page size
					when [3]==0, 0:256, 1:512 bytes/page.
					when [3]==1, 0:1024, 1:2048 bytes/page.
	AddrCycle(R) [1]             NAND flash addr size
					when [3]==0, 0:3-addr, 1:4-addr.
					when [3]==1, 0:4-addr, 1:5-addr.
	BusWidth(R/W) [0]            NAND bus width. 0:8-bit, 1:16-bit.
        */

	nand->NFCONT = (0<<13)|(0<<12)|(0<<10)|(0<<9)|(0<<8)|(1<<6)|(1<<5)|(1<<4)|(1<<1)|(1<<0);
	/*
	Lock-tight   [13]            0:Disable lock, 1:Enable lock.
	Soft Lock    [12]            0:Disable lock, 1:Enable lock.
	EnablillegalAcINT[10]        Illegal access interupt control. 0:Disable, 1:Enable
	EnbRnBINT    [9]             RnB interrupt. 0:Disable, 1:Enable
	RnB_TrandMode[8]             RnB transition detection config. 0:Low to High, 1:High to Low
	SpareECCLock [6]             0:Unlock, 1:Lock
	MainECCLock  [5]             0:Unlock, 1:Lock
	InitECC(W)   [4]             1:Init ECC decoder/encoder.
	Reg_nCE      [1]             0:nFCE=0, 1:nFCE=1.
	NANDC Enable [0]             operating mode. 0:Disable, 1:Enable.
        */

}

/*
 * NF8_EraseBlock
 */
static int NF8_EraseBlock(u32 block)
{
	u32 blockPage=(block<<5);

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

#if BAD_CHECK
	if(NF8_IsBadBlock(block))
		return FAIL;
#endif

	NAND_ENABLE_CE(nand);

	nand->NFCMMD=NAND_CMD_ERASE1;	/* Erase one block 1st command, Block Addr:A9-A25 */
	/* Address 3-cycle */
	nand->NFADDR=(blockPage&0xff);	/* Page number=0 */
	nand->NFADDR=((blockPage>>8)&0xff);
	nand->NFADDR=((blockPage>>16)&0xff);


	NF_CLEAR_RB();
	nand->NFCMMD=NAND_CMD_ERASE2;	/* Erase one blcok 2nd command */
	NF_DETECT_RB();
	if(nand->NFSTAT&0x8)
		return FAIL;

	nand->NFCMMD=NAND_CMD_STATUS;	/* Read status command */

	if (NFDATA8&0x1) {	/* Erase error */
		NAND_DISABLE_CE(nand);
		printf("[ERASE_ERROR:block#=%d]\n",block);
/*		NF8_MarkBadBlock(block); */
		return FAIL;
	} else {
		NAND_DISABLE_CE(nand);
		return OK;
	}
}

int s3c2440_nand_write(ulong srcAddress,ulong targetBlock,ulong targetSize)
{
	int i;
	int programError=0;
	u8 *srcPt,*saveSrcPt;
	u32 blockIndex;

	srcPt=(u8 *)srcAddress;
	blockIndex=targetBlock/NAND_BLOCK_SIZE;

	while(1) {
		saveSrcPt=srcPt;
#if BAD_CHECK
		if(NF8_IsBadBlock(blockIndex)) {	/* 1:bad 0:good */
			blockIndex++;		/* for next block */
			continue;
		}
#endif
		if(!NF8_EraseBlock(blockIndex)) {
			blockIndex++;		/* for next block */
			printf(" Error->  Erase Block %d  \n",(int)blockIndex);
			continue;
		}

		for(i=0; i< NAND_PAGES_IN_BLOCK ;i++) {
			if(!NF8_WritePage(blockIndex,i,srcPt)) {
				/* block num, page num, buffer */
				programError=1;
				break;
			}
#if ECC_CHECK
			if(!NF8_ReadPage(blockIndex,i,srcPt)) {
				printf("ECC Error(block=%d,page=%d!!!\n",(int)blockIndex,i);
			}
#endif
			srcPt += NAND_PAGE_SIZE;
			if((u32)srcPt>=(srcAddress+targetSize))	/* Check end of buffer */
				break;	/* Exit for loop */
		}
		if(programError==1) {
			blockIndex++;
			srcPt=saveSrcPt;
			programError=0;
			continue;
		}
		if((u32)srcPt>=(srcAddress+targetSize))
			break;	/* Exit while loop */
		blockIndex++;
	}
	return 0;
}


int s3c2440_nand_read(ulong dst_addr,ulong src_addr,ulong size)
{
	char *buf = (char *)dst_addr;
	char page_buf[NAND_PAGE_SIZE];
	int i, j;

	if ((src_addr & NAND_BLOCK_MASK) || (size & NAND_PAGE_MASK))
		return -1;      /* invalid alignment */

	while (size > 0) {
		/* If this block is bad, go next block */
		if (is_bad_block(src_addr)) {
			src_addr += NAND_BLOCK_SIZE;
			continue;
		}
		/* Read block */
		for (i = 0; i < NAND_PAGES_IN_BLOCK; i++) {
			NF8_ReadPage((src_addr/NAND_BLOCK_SIZE),i,(char *)page_buf);
			for (j = 0; j < NAND_PAGE_SIZE; j++)
				*buf++ = page_buf[j];
			src_addr += NAND_PAGE_SIZE;
			size -= NAND_PAGE_SIZE;
			if (size == 0)
				break;
		}
	}
	return 0;
}

int NF8_ReadPage(u32 block,u32 page,u8 *buffer)
{
	int i;
	unsigned int blockPage;
	u32 Mecc, Secc;
	u32 ecc;
	u8 *bufPt=buffer;
	u8 se[16];

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	page=page&0x1f;
	blockPage=(block<<5)+page;
	NF_RSTECC();		/* Initialize ECC */
	NF_MECC_UnLock();

	NAND_ENABLE_CE(nand);

	NF_CLEAR_RB();
	nand->NFCMMD=NAND_CMD_READ0;		/* Read command */
	nand->NFADDR=(0);			/* Column = 0 */
	nand->NFADDR=(blockPage&0xff);
	nand->NFADDR=((blockPage>>8)&0xff);	/* Block & Page num. */
	nand->NFADDR=((blockPage>>16)&0xff);
	NF_DETECT_RB();


	for(i=0;i<512;i++) {
		*bufPt++=NFDATA8;	/* Read one page */
	}

	NF_MECC_Lock();

	NF_SECC_UnLock();
	Mecc=NFDATA32;
	nand->NFMECCD0=((Mecc&0xff00)<<8)|(Mecc&0xff);
	nand->NFMECCD1=((Mecc&0xff000000)>>8)|((Mecc&0xff0000)>>16);

	NF_SECC_Lock();
	se[0]=Mecc&0xff;
	se[1]=(Mecc&0xff00)>>8;
	se[2]=(Mecc&0xff0000)>>16;
	se[3]=(Mecc&0xff000000)>>24;
	ecc = NFDATA32;		/* read 4~7 */
	Secc=NFDATA32;
	nand->NFSECCD=((Secc&0xff00)<<8)|(Secc&0xff);
	se[8]=Secc&0xff;
	se[9]=(Secc&0xff00)>>8;
	se[10]=(Secc&0xff0000)>>16;
	se[11]=(Secc&0xff000000)>>24;
	NAND_DISABLE_CE(nand);

	if ((nand->NFESTAT0&0xf) == 0x0){
#ifdef NAND_DEBUG
		printf("ECC OK!\n");
#endif
		return OK;
	} else {
		printf("ECC FAIL! %x\n",(nand->NFESTAT0&0xf));
		return FAIL;
	}


}

static int NF8_WritePage(u32 block,u32 page,u8 *buffer)
{
	int i;
	u32 blockPage, Mecc, Secc;
	u8 *bufPt=buffer;

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	NF_RSTECC();		/* Initialize ECC */
	NF_MECC_UnLock();
	blockPage=(block<<5)+page;

	NAND_ENABLE_CE(nand);
	nand->NFCMMD=NAND_CMD_READ0;		/* First a read access */
	nand->NFCMMD=NAND_CMD_SEQIN;		/* Write 1st command */
	nand->NFADDR=(0);			/* Column 0 */
	nand->NFADDR=(blockPage&0xff);
	nand->NFADDR=((blockPage>>8)&0xff);	/* Block & page num. */
	nand->NFADDR=((blockPage>>16)&0xff);


	for(i=0;i<512;i++) {
		NFDATA8=*bufPt++;	/* Write one page to NFM from buffer */
	}

	NF_MECC_Lock();
        /*
	Get ECC data.
	Spare data for 8bit
	byte  0     1    2    3     4          5               6      7            8         9
	ecc  [0]   [1]  [2]  [3]    x   [Bad marking]        SECC0  SECC1
	*/
	Mecc = nand->NFMECC0;
	se8Buf[0]=(u8)(Mecc&0xff);
	se8Buf[1]=(u8)((Mecc>>8) & 0xff);
	se8Buf[2]=(u8)((Mecc>>16) & 0xff);
	se8Buf[3]=(u8)((Mecc>>24) & 0xff);
	se8Buf[5]=0xff;		/* Marking good block */

	NF_SECC_UnLock();
	/* Write extra data(ECC, bad marking) */
	for(i=0;i<4;i++) {
		NFDATA8=se8Buf[i];	/* Write spare array(Main ECC) */
		NF8_Spare_Data[i]=se8Buf[i];
	}
	NF_SECC_Lock();
	Secc=nand->NFSECC;
	se8Buf[8]=(u8)(Secc&0xff);
	se8Buf[9]=(u8)((Secc>>8) & 0xff);
	for(i=4;i<16;i++) {
		NFDATA8=se8Buf[i];	/* Write spare array(Spare ECC and Mark) */
		NF8_Spare_Data[i]=se8Buf[i];
	}
	NF_CLEAR_RB();
	nand->NFCMMD=NAND_CMD_PAGEPROG;	/* Write 2nd command */
	NF_DETECT_RB();

	if(nand->NFSTAT&0x8)
		return FAIL;

	nand->NFCMMD=NAND_CMD_STATUS;	/* Read status command */

	for(i=0;i<3;i++);	/* twhr=60ns */

	if (NFDATA8&0x1) {	/* Page write error */
		NAND_DISABLE_CE(nand);
		printf("[PROGRAM_ERROR:block#=%d]\n",block);
		NF8_MarkBadBlock(block);
		return FAIL;
	} else {
		NAND_DISABLE_CE(nand);
		return OK;
	}

}

static int NF8_MarkBadBlock(u32 block)
{
	int i;
	u32 blockPage=(block<<5);

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	se8Buf[0]=0xff;
	se8Buf[1]=0xff;
	se8Buf[2]=0xff;
	se8Buf[5]=0x44;		/* Bad block mark=44 */

	NAND_ENABLE_CE(nand);
	nand->NFCMMD=NAND_CMD_READOOB;		/* First a read access */
	nand->NFCMMD=NAND_CMD_SEQIN;		/* Write 1st command */

	nand->NFADDR=(0x0);			/* The mark of bad block is */
	nand->NFADDR=(blockPage&0xff);		/* marked 5th spare array */
	nand->NFADDR=((blockPage>>8)&0xff);	/* in the 1st page. */
	nand->NFADDR=((blockPage>>16)&0xff);

	for(i=0;i<16;i++) {
		NFDATA8=se8Buf[i];	/* Write spare array */
	}

	NF_CLEAR_RB();
	nand->NFCMMD=NAND_CMD_PAGEPROG;	/* Write 2nd command */
	NF_DETECT_RB();

	nand->NFCMMD=NAND_CMD_STATUS;

	for(i=0;i<3;i++);	/* twhr=60ns */

	if (NFDATA8&0x1) {	/* Spare arrray write error */
		NAND_DISABLE_CE(nand);
		printf("[Program error is occurred but ignored]\n");
	} else {
		NAND_DISABLE_CE(nand);
	}

	printf("[block #%d is marked as a bad block]\n",block);
	return OK;
}

#if BAD_CHECK
static int NF8_IsBadBlock(u32 block)
{
	unsigned int blockPage;
	u8 data;

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	blockPage=(block<<5);	/* For 2'nd cycle I/O[7:5] */

	NAND_ENABLE_CE(nand);
	NF_CLEAR_RB();

	nand->NFCMMD=NAND_CMD_READOOB;		/* Spare array read command */
	nand->NFADDR=((512+5)&0xf);		/* Read the mark of bad block in spare array(M addr=5), A4-A7:Don't care */
	nand->NFADDR=(blockPage&0xff);		/* The mark of bad block is in 0 page */
	nand->NFADDR=((blockPage>>8)&0xff);	/* For block number A[24:17] */
	nand->NFADDR=((blockPage>>16)&0xff);	/* For block number A[25] */

	NF_DETECT_RB();		/* Wait tR(max 12us) */

	data=NFDATA8;

	NAND_DISABLE_CE(nand);

	if(data!=0xff) {
		printf("[block %d has been marked as a bad block(%x)]\n",block,data);
		return FAIL;
	} else {
		return OK;
	}
}
#endif	/* BAD_CHECK */

#endif	/* HW_ECC_2440 */

#endif	/* (CONFIG_COMMANDS & CFG_CMD_NAND) */
#endif /* CFG_NAND_LEGACY */
