/* 
 * nand_cp.c: Copy from nand to destination
 * Copyright (C) Samsung Electronics
 *          SW.LEE <hitchcar@samsung.com>
 *     -- Correct mis-used register (Reset,TranRnB....)
 *     -- add 16Bit NAND
 *
 * MIZI Based Code
 *
 * Copyright (C) 2003	
 * Gianluca Costa <gcoata@libero.it>
 * 
 *  Under GPLver2
 */

#include <common.h>
#include <s3c2440.h>
#include <linux/mtd/nand.h>
#include <a9m2410_nand.h>

#ifdef CPU_2440

void nand_select(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT &= ~(1 << 1);
}
void nand_deselect(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFCONT |= (1 << 1);
}
void nand_clear_RnB(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	nand->NFSTAT |= (1 << 2);
}
void nand_wait(void)
{
	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();
	while(!(nand->NFSTAT & 0x4));
}

int nandll_read_page(unsigned char *buf, unsigned long addr)
{
        int i;
	unsigned short *ptr16 = (unsigned short *)buf;

        if (addr & NAND_PAGE_MASK) {
                return -1;      /* invalid alignment */
        }

        /* chip Enable */
        nand_select();
        nand_clear_RnB();

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

        nand->NFCMMD = NAND_CMD_READ0;
        /* Write Address */
	nand->NFADDR = addr & 0xff;
	nand->NFADDR = (addr >> 9) & 0xff;
	nand->NFADDR = (addr >> 17) & 0xff;
#ifdef NAND_3_ADDR_CYCLE
#else
	nand->NFADDR = (addr >> 25) & 0xff;
#endif
        nand_wait();

        for(i=0; i < NAND_PAGE_SIZE/2; i++) {
                *ptr16 = NFDATA16;
                ptr16++;
        }
#if 0	
	for (i = 0; i < 8 ; i++)
		printf(" 0x%4x ", NFDATA16);
	printf("\n");
#endif
        /* chip Disable */
        nand_deselect();
        return 0;
}

/* low level nand read function */
int nandll_read_oob(char *buf, unsigned long addr)
{
	int i;
	unsigned long *ptr32 = (unsigned long *)buf;

	if ((addr & NAND_BLOCK_MASK)) {
		return -1;      /* invalid alignment */
	}

	/* Chip Enable */
	nand_select();
	nand_clear_RnB();

	S3C2410_NAND * const nand = S3C2410_GetBase_NAND();

	nand->NFCMMD = NAND_CMD_READOOB;

	/* Write Address */
	nand->NFADDR = addr & 0xff;
	nand->NFADDR = (addr >> 9) & 0xff;
	nand->NFADDR = (addr >> 17) & 0xff;
#ifdef NAND_3_ADDR_CYCLE
#else
	nand->NFADDR = (addr >> 25) & 0xff;
#endif
	nand_wait();

	for(i=0; i < NAND_OOB_SIZE/4; i++) {
		*ptr32 = NFDATA32;
		ptr32++;
	}
	/* Chip Disable */
	nand_deselect();
	return 0;
}

int is_bad_block(unsigned long addr)
{
        char oob_buf[16];

        nandll_read_oob((char *)oob_buf, addr);

#ifdef S3C24X0_16BIT_NAND
        if ( (oob_buf[0] != 0xFF) ||  (oob_buf[1] != 0xFF) )
                return 1;
#else
        if (oob_buf[5] != 0xFF)
                return 1;
#endif
        else
                return 0;
}

/*
 * Read data from NAND.
 */
int
nandll_read_blocks(unsigned long dst_addr, unsigned long src_addr, int size)
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
                        nandll_read_page((char *)page_buf, src_addr);
                        for (j = 0; j < NAND_PAGE_SIZE; j++)
                                *buf++ = page_buf[j];
                        src_addr += NAND_PAGE_SIZE;
                        size -= NAND_PAGE_SIZE;
                        if (size == 0) break;
                }
        }
        return 0;
}



#endif /* CPU_2440 */

