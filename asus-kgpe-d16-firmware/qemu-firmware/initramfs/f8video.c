/*
 * F8 video-datapath demo tool for the ASUS KGPE-D16 BMC (AST2050).
 *
 * Two steps, run in-guest from the initramfs (see init, 'f8video' cmdline gate):
 *
 *  1. "Host renders something": draw an 8-bar colour test pattern into the
 *     VGA/graphics aperture at the top of BMC DRAM (0x43800000, the 8 MB
 *     SCU70[3:2]-strapped carve-out — see the DTS vga_memory node) through
 *     /dev/mem. On real hardware the host's GPU path writes this same DRAM;
 *     the BMC-side write stands in for the host because the region IS BMC
 *     memory (the AST2050 is the host's VGA adapter).
 *
 *  2. "See the virtual VGA screen": capture one frame from /dev/video0 (the
 *     aspeed-video V4L2 device driving the modelled AST2050 video engine:
 *     VR004 trigger -> engine reads the VGA scanout -> JPEG -> stream buffer
 *     -> VIC INT#7 -> vb2 buffer done) and emit it as base64 between
 *     F8-FRAME-BEGIN/END markers so the boot harness can decode and verify
 *     the pattern in the dequeued JPEG.
 *
 * Static-linked; no dependencies beyond the kernel UAPI. Apache-2.0.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <linux/videodev2.h>

#define WIDTH  640
#define HEIGHT 480
#define NBUFS  3

static const char *b64 =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/* The 8 vertical bars, left to right (XRGB: R,G,B). */
static const uint8_t bars[8][3] = {
    { 0xff, 0xff, 0xff },   /* white   */
    { 0xff, 0xff, 0x00 },   /* yellow  */
    { 0x00, 0xff, 0xff },   /* cyan    */
    { 0x00, 0xff, 0x00 },   /* green   */
    { 0xff, 0x00, 0xff },   /* magenta */
    { 0xff, 0x00, 0x00 },   /* red     */
    { 0x00, 0x00, 0xff },   /* blue    */
    { 0x10, 0x10, 0x10 },   /* near-black */
};

static int draw_pattern(unsigned long phys)
{
    size_t len = (size_t)WIDTH * HEIGHT * 4;
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) {
        perror("open /dev/mem");
        return 1;
    }
    uint32_t *fb = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
                        (off_t)phys);
    if (fb == MAP_FAILED) {
        perror("mmap vga aperture");
        close(fd);
        return 1;
    }
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            const uint8_t *c = bars[x / (WIDTH / 8)];
            fb[y * WIDTH + x] = ((uint32_t)c[0] << 16) |
                                ((uint32_t)c[1] << 8) | c[2];
        }
    }
    munmap(fb, len);
    close(fd);
    printf("F8-PATTERN: wrote 8-bar test pattern (%ux%u XRGB8888) to VGA "
           "aperture @0x%08lx\n", WIDTH, HEIGHT, phys);
    printf("F8-PATTERN-BARS: white yellow cyan green magenta red blue "
           "near-black\n");
    return 0;
}

static void emit_base64(const uint8_t *p, size_t n)
{
    char line[77];
    int col = 0;
    for (size_t i = 0; i < n; i += 3) {
        uint32_t v = (uint32_t)p[i] << 16;
        int rem = (int)(n - i);
        if (rem > 1) {
            v |= (uint32_t)p[i + 1] << 8;
        }
        if (rem > 2) {
            v |= p[i + 2];
        }
        line[col++] = b64[(v >> 18) & 63];
        line[col++] = b64[(v >> 12) & 63];
        line[col++] = rem > 1 ? b64[(v >> 6) & 63] : '=';
        line[col++] = rem > 2 ? b64[v & 63] : '=';
        if (col >= 76) {
            line[col] = 0;
            puts(line);
            col = 0;
        }
    }
    if (col) {
        line[col] = 0;
        puts(line);
    }
}

static int capture_frame(void)
{
    struct v4l2_capability cap;
    struct v4l2_format fmt;
    struct v4l2_input inp;
    struct v4l2_requestbuffers req;
    struct v4l2_buffer buf;
    struct v4l2_control ctrl;
    void *maps[NBUFS];
    size_t maplen[NBUFS];
    int fd, type = V4L2_BUF_TYPE_VIDEO_CAPTURE;

    fd = open("/dev/video0", O_RDWR);
    if (fd < 0) {
        perror("open /dev/video0");
        return 1;
    }
    memset(&cap, 0, sizeof(cap));
    if (ioctl(fd, VIDIOC_QUERYCAP, &cap) == 0) {
        printf("F8-V4L2: driver=%s card=%s\n", cap.driver, cap.card);
    }
    memset(&inp, 0, sizeof(inp));
    if (ioctl(fd, VIDIOC_ENUMINPUT, &inp) == 0) {
        printf("F8-V4L2: input '%s' status=0x%x%s\n", inp.name, inp.status,
               inp.status & V4L2_IN_ST_NO_SIGNAL ? " (NO SIGNAL)" : " (signal)");
    }
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = type;
    if (ioctl(fd, VIDIOC_G_FMT, &fmt) != 0) {
        perror("VIDIOC_G_FMT");
        close(fd);
        return 1;
    }
    printf("F8-V4L2-FMT: %c%c%c%c %ux%u sizeimage=%u\n",
           fmt.fmt.pix.pixelformat & 0xff, (fmt.fmt.pix.pixelformat >> 8) & 0xff,
           (fmt.fmt.pix.pixelformat >> 16) & 0xff,
           (fmt.fmt.pix.pixelformat >> 24) & 0xff,
           fmt.fmt.pix.width, fmt.fmt.pix.height, fmt.fmt.pix.sizeimage);

    /* Mid-scale JPEG quality for a cleaner pattern round-trip. */
    memset(&ctrl, 0, sizeof(ctrl));
    ctrl.id = V4L2_CID_JPEG_COMPRESSION_QUALITY;
    ctrl.value = 8;
    if (ioctl(fd, VIDIOC_S_CTRL, &ctrl) != 0) {
        perror("VIDIOC_S_CTRL jpeg quality");   /* non-fatal */
    }

    memset(&req, 0, sizeof(req));
    req.count = NBUFS;
    req.type = type;
    req.memory = V4L2_MEMORY_MMAP;
    if (ioctl(fd, VIDIOC_REQBUFS, &req) != 0) {
        perror("VIDIOC_REQBUFS");
        close(fd);
        return 1;
    }
    for (unsigned i = 0; i < req.count; i++) {
        memset(&buf, 0, sizeof(buf));
        buf.type = type;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = i;
        if (ioctl(fd, VIDIOC_QUERYBUF, &buf) != 0) {
            perror("VIDIOC_QUERYBUF");
            close(fd);
            return 1;
        }
        maps[i] = mmap(NULL, buf.length, PROT_READ, MAP_SHARED, fd,
                       buf.m.offset);
        maplen[i] = buf.length;
        if (maps[i] == MAP_FAILED) {
            perror("mmap v4l2 buffer");
            close(fd);
            return 1;
        }
        if (ioctl(fd, VIDIOC_QBUF, &buf) != 0) {
            perror("VIDIOC_QBUF");
            close(fd);
            return 1;
        }
    }
    if (ioctl(fd, VIDIOC_STREAMON, &type) != 0) {
        perror("VIDIOC_STREAMON");
        close(fd);
        return 1;
    }
    memset(&buf, 0, sizeof(buf));
    buf.type = type;
    buf.memory = V4L2_MEMORY_MMAP;
    if (ioctl(fd, VIDIOC_DQBUF, &buf) != 0) {
        perror("VIDIOC_DQBUF");
        close(fd);
        return 1;
    }
    printf("F8-FRAME: dequeued buffer %u sequence=%u bytesused=%u\n",
           buf.index, buf.sequence, buf.bytesused);
    printf("F8-FRAME-BEGIN size=%u fmt=%ux%u\n", buf.bytesused,
           fmt.fmt.pix.width, fmt.fmt.pix.height);
    emit_base64(maps[buf.index], buf.bytesused);
    printf("F8-FRAME-END\n");

    ioctl(fd, VIDIOC_STREAMOFF, &type);
    for (unsigned i = 0; i < req.count; i++) {
        munmap(maps[i], maplen[i]);
    }
    close(fd);
    return 0;
}

int main(int argc, char **argv)
{
    unsigned long phys = 0x43800000UL;   /* DTS vga_memory node */
    if (argc > 1) {
        phys = strtoul(argv[1], NULL, 0);
    }
    if (draw_pattern(phys)) {
        return 1;
    }
    return capture_frame();
}
