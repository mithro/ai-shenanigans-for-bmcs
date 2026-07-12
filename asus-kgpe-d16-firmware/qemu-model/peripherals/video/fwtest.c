/* Video engine (KVM capture) — AST2050 @ 0x1E700000 (see DATASHEET-VIDEO.md).
 * VR000 protection key (unlock 0x1A038AA8), VR004 capture trigger/status, VR008
 * source, VR030/034 windows, VR054 stream buffer, VR304/VR308 interrupts.
 * Exercises the full datasheet §20.6-style capture flow: unlock -> mode detect
 * (640x480 internal-VGA readback) -> program buffers -> trigger capture +
 * compression -> poll completion -> verify a JPEG (SOI marker) landed in the
 * compressed-stream buffer and INT#7 is pending in the VIC raw status.
 * Not modelled in mainline QEMU. OpenBMC aspeed-video / KVM path. Apache-2.0. */
#include "harness.h"
#include "ast2050.h"

const char fwtest_name[] = "video";

/* build.py boots the machine with -m 128: DRAM = 128 MB at 0x40000000, and the
 * kgpe-d16-bmc VGA carve-out is the top 8 MB (SCU70[3:2]=00, HW-verified). */
#define DRAM_BASE      0x40000000u
#define DRAM_SIZE      0x08000000u
#define VGA_MEM_SIZE   0x00800000u
#define VGA_BASE       (DRAM_BASE + DRAM_SIZE - VGA_MEM_SIZE)  /* 0x47800000 */
#define COMP_BUF       0x41000000u   /* compressed-stream buffer, clear of us */

#define VR(off)        (VIDEO_BASE + (off))

void fwtest_run(void)
{
    u32 i, v;

    fwt_reg("vr000.protect", VR(0x000));
    fwt_reg("vr008.source",  VR(0x008));
    writel(VR(0x000), 0x1A038AA8u);        /* unlock key */
    fwt_check("vr000.unlock", readl(VR(0x000)), 0x00000001u); /* unlocked reads 1 */

    /* Idle status: VR004[16] capture / [18] compression read 1 = idle. */
    fwt_check("vr004.idle", readl(VR(0x004)) & 0x50000u, 0x50000u);

    /* --- Mode detection (VR004[0] 0->1): internal-VGA 640x480 readback --- */
    writel(VR(0x304), 0x0000003Fu);        /* enable all completion causes */
    writel(VR(0x308), 0xFFFFFFFFu);        /* W1C any stale status */
    writel(VR(0x008), 0x00000000u);        /* VR008[2]=0: integrated VGA source */
    writel(VR(0x004), 0x00000001u);        /* trigger mode detection */
    fwt_check("md.ready", readl(VR(0x308)) & 0x10u, 0x10u);
    v = readl(VR(0x098));
    fwt_check("md.stable", v & 0x6000u, 0x6000u);   /* H/V stable */
    v = readl(VR(0x090));                  /* right edge [27:16], left [11:0] */
    fwt_check("md.width", ((v >> 16) & 0xFFFu) - (v & 0xFFFu) + 1, 640);
    v = readl(VR(0x094));                  /* bottom [28:16], top [12:0] */
    fwt_check("md.height", ((v >> 16) & 0x1FFFu) - (v & 0x1FFFu) + 1, 480);
    writel(VR(0x308), 0x10u);              /* ack mode-detect-ready */

    /* --- Capture + compress a 16x16 frame from the VGA carve-out --- */
    for (i = 0; i < 16 * 16; i++) {
        writel(VGA_BASE + i * 4, 0x00FF0000u);   /* solid red XRGB8888 */
    }
    writel(COMP_BUF, 0);                   /* scrub the SOI landing zone */
    writel(VR(0x030), (16u << 16) | 16u);  /* capture window 16x16 */
    writel(VR(0x034), (16u << 16) | 16u);  /* compression window 16x16 */
    writel(VR(0x048), 16u * 4u);           /* scan-line offset */
    writel(VR(0x054), COMP_BUF);           /* compressed-stream buffer base */
    writel(VR(0x058), 0x00000006u);        /* stream buffer 4 pkt x 64 KB */
    writel(VR(0x004), 0x00000012u);        /* trigger capture [1] + comp [4] */

    /* Busy during the frame (a few MMIO reads deep), idle + complete after. */
    for (i = 0; i < 1000000; i++) {
        if ((readl(VR(0x308)) & 0x0Au) == 0x0Au) {
            break;                         /* capture [1] + comp [3] complete */
        }
    }
    fwt_check("frame.complete", readl(VR(0x308)) & 0x0Au, 0x0Au);
    fwt_check("frame.idle", readl(VR(0x004)) & 0x50000u, 0x50000u);

    /* The dequeued stream is a JPEG: SOI/JFIF at the buffer base, and the
     * frame-end offset VR078 (what aspeed-video reads as the frame size) is a
     * plausible non-zero 8-byte-aligned count. */
    fwt_check("jpeg.soi", readl(COMP_BUF), 0xE0FFD8FFu);  /* FF D8 FF E0 (LE) */
    v = readl(VR(0x078));
    fwt_kv("jpeg.size", v);
    fwt_check("jpeg.size.aligned", v & 0x7u, 0);
    fwt_check("jpeg.size.nonzero", v != 0, 1);
    fwt_kv("frame.counter", readl(VR(0x07C)));

    /* INT#7 pending in the G3 VIC raw status (0x1E6C0008). The G3 VIC resets
     * with SENSE/EVENT = 0 (all edge, datasheet §16), so program INT7 as
     * high-level first — exactly what the kernel's G3 VIC driver does — and
     * the raw bit then follows the video engine's level line (§10 p.99:
     * "sensitive high level"). */
    writel(VIC_BASE + 0x2C, 0x80u);        /* EVENT: INT7 high/rising */
    writel(VIC_BASE + 0x24, 0x80u);        /* SENSE: INT7 level */
    fwt_check("vic.int7.raw", readl(VIC_BASE + 0x08) & 0x80u, 0x80u);
    writel(VR(0x308), 0xFFFFFFFFu);        /* W1C: line must drop */
    fwt_check("vic.int7.clear", readl(VIC_BASE + 0x08) & 0x80u, 0);
}
