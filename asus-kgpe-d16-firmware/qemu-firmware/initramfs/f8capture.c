/*
 * Capture-only variant of f8video.c for REAL-HARDWARE BIOS-VGA capture on the
 * AST2050 BMC. No test-pattern write — grabs whatever the host left in the
 * AST2050 VGA framebuffer (the BIOS POST screen; the OS runs on the NVIDIA GPU,
 * so the AST2050 fb retains the BIOS content). Streams one JPEG frame from
 * /dev/video0 (aspeed-video) and writes it to argv[1] (default /tmp/bios.jpg),
 * reporting the input signal status and format. Static-linked. Apache-2.0.
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <linux/videodev2.h>

#define MAXBUFS 4

int main(int argc, char **argv)
{
    const char *out = argc > 1 ? argv[1] : "/tmp/bios.jpg";
    int quality = argc > 2 ? atoi(argv[2]) : 60;
    /* On the 64 MB AST2050 the vb2 dma-contig pool is tiny; fewer buffers = a
     * better chance REQBUFS succeeds. Default 1, override with F8_NBUFS. */
    const char *nbenv = getenv("F8_NBUFS");
    int NBUFS = nbenv ? atoi(nbenv) : 1;
    if (NBUFS < 1) NBUFS = 1;
    if (NBUFS > MAXBUFS) NBUFS = MAXBUFS;
    struct v4l2_capability cap;
    struct v4l2_format fmt;
    struct v4l2_input inp;
    struct v4l2_requestbuffers req;
    struct v4l2_buffer buf;
    struct v4l2_control ctrl;
    void *maps[MAXBUFS];
    size_t maplen[MAXBUFS];
    int fd, type = V4L2_BUF_TYPE_VIDEO_CAPTURE;

    fd = open("/dev/video0", O_RDWR | O_NONBLOCK);
    if (fd < 0) { perror("open /dev/video0"); return 1; }

    memset(&cap, 0, sizeof(cap));
    if (ioctl(fd, VIDIOC_QUERYCAP, &cap) == 0)
        printf("CAP: driver=%s card=%s\n", cap.driver, cap.card);

    memset(&inp, 0, sizeof(inp));
    if (ioctl(fd, VIDIOC_ENUMINPUT, &inp) == 0)
        printf("INPUT: '%s' status=0x%x%s\n", inp.name, inp.status,
               inp.status & V4L2_IN_ST_NO_SIGNAL ? " (NO SIGNAL)" : " (SIGNAL)");

    memset(&fmt, 0, sizeof(fmt));
    fmt.type = type;
    if (ioctl(fd, VIDIOC_G_FMT, &fmt) != 0) { perror("VIDIOC_G_FMT"); return 1; }
    printf("FMT: %c%c%c%c %ux%u sizeimage=%u\n",
           fmt.fmt.pix.pixelformat & 0xff, (fmt.fmt.pix.pixelformat >> 8) & 0xff,
           (fmt.fmt.pix.pixelformat >> 16) & 0xff, (fmt.fmt.pix.pixelformat >> 24) & 0xff,
           fmt.fmt.pix.width, fmt.fmt.pix.height, fmt.fmt.pix.sizeimage);

    memset(&ctrl, 0, sizeof(ctrl));
    ctrl.id = V4L2_CID_JPEG_COMPRESSION_QUALITY;
    ctrl.value = quality;
    if (ioctl(fd, VIDIOC_S_CTRL, &ctrl) != 0) perror("S_CTRL jpeg quality (non-fatal)");

    memset(&req, 0, sizeof(req));
    req.count = NBUFS; req.type = type; req.memory = V4L2_MEMORY_MMAP;
    if (ioctl(fd, VIDIOC_REQBUFS, &req) != 0) { perror("REQBUFS"); return 1; }
    for (unsigned i = 0; i < req.count; i++) {
        memset(&buf, 0, sizeof(buf));
        buf.type = type; buf.memory = V4L2_MEMORY_MMAP; buf.index = i;
        if (ioctl(fd, VIDIOC_QUERYBUF, &buf) != 0) { perror("QUERYBUF"); return 1; }
        maps[i] = mmap(NULL, buf.length, PROT_READ, MAP_SHARED, fd, buf.m.offset);
        maplen[i] = buf.length;
        if (maps[i] == MAP_FAILED) { perror("mmap buf"); return 1; }
        if (ioctl(fd, VIDIOC_QBUF, &buf) != 0) { perror("QBUF"); return 1; }
    }
    if (ioctl(fd, VIDIOC_STREAMON, &type) != 0) { perror("STREAMON"); return 1; }

    /* Bounded, non-blocking dequeue via poll(). Crucial on the AST2050: if the G3
     * engine never completes a frame we MUST STREAMOFF quickly -- a free-running
     * engine saturates the shared DRAM/M-bus and starves the CPU (the box goes
     * unreachable: SSH banner timeouts while ping still works). A blocking DQBUF
     * with no timeout is what caused exactly that. Total budget bounded below. */
    int got = 0, budget_ms = 12000;
    struct pollfd pfd = { .fd = fd, .events = POLLIN };
    while (budget_ms > 0 && !got) {
        int pr = poll(&pfd, 1, 1000);
        budget_ms -= 1000;
        if (pr < 0) { if (errno == EINTR) continue; perror("poll"); break; }
        if (pr == 0) { printf("poll: no frame yet (%d ms left)\n", budget_ms); continue; }
        if (pfd.revents & (POLLERR | POLLHUP)) { printf("poll: POLLERR/HUP\n"); break; }
        memset(&buf, 0, sizeof(buf));
        buf.type = type; buf.memory = V4L2_MEMORY_MMAP;
        if (ioctl(fd, VIDIOC_DQBUF, &buf) != 0) {
            if (errno == EAGAIN) continue;
            perror("DQBUF"); break;
        }
        printf("FRAME: buffer=%u sequence=%u bytesused=%u\n",
               buf.index, buf.sequence, buf.bytesused);
        if (buf.bytesused > 0) {
            int ofd = open(out, O_WRONLY | O_CREAT | O_TRUNC, 0644);
            if (ofd >= 0) {
                ssize_t w = write(ofd, maps[buf.index], buf.bytesused);
                printf("WROTE %zd bytes -> %s\n", w, out);
                close(ofd);
                got = 1;
            } else perror("open out");
        }
        ioctl(fd, VIDIOC_QBUF, &buf);   /* requeue */
    }

    ioctl(fd, VIDIOC_STREAMOFF, &type);
    for (unsigned i = 0; i < req.count; i++) munmap(maps[i], maplen[i]);
    close(fd);
    return got ? 0 : 2;
}
