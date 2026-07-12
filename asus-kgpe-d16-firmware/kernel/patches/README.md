# Modern-kernel patches for the AST2050 (KGPE-D16 BMC)

Patch series against **Linux 6.6.70** (stable tag commit
`1acb10106df3062d221af9b3124de4d968ee34d2`) that makes the modern kernel run
on the real AST2050. Generated with `git format-patch` from the working build
tree (`.worktrees/d16-qemu/asus-kgpe-d16-firmware/qemu-firmware/kernel/linux`,
a gitignored shallow clone of linux-stable), so the full commit provenance —
author, date, hardware-verification notes — is preserved in each file.

## The series

| # | Patch | Where it lives |
|---|-------|----------------|
| 0001 | `clk-aspeed`: add AST2050 support | `asus-kgpe-d16-firmware/qemu-firmware/kernel/patches/0001-clk-aspeed-add-ast2050-support.patch` on branch `claude/d16-qemu-firmware-stack` (PR #16) |
| 0002 | `ftgmac100`: leave MACCLK at the U-Boot default on the AST2050 | `0002-ftgmac100-ast2050-macclk.patch` in this directory on branch `claude/culvert-g3-port` (PR #22) |
| 0003 | `irqchip`: add `aspeed,ast2050-vic` driver for the G3 VIC | **this directory** |

Until PRs #16/#22 merge, 0001/0002 are only on those branches; this README is
written from the branch that first put 0003 on `main`. The numbering matches
the apply order on a pristine v6.6.70 tree.

Note on 0002: the working kernel tree reached the same end state via two
commits (`69dd008c2` adding the VIC driver, then `235581692` reverting the
earlier ftgmac100 MAC-reset/udelay workarounds that the dead timer had
motivated). The *net* ftgmac100 diff of that pair is byte-identical to 0002,
so no separate "revert" patch is needed here.

## 0003 — the G3 VIC driver (`irq-aspeed-g3-vic.c`)

The key fix for the whole modern-Linux-on-AST2050 effort. The G3 interrupt
controller is a compact VIC at `0x1e6c0000` (AST2050 datasheet §16), not the
AST2400+ interleaved map at `0x1e6c0080` that mainline `irq-aspeed-vic.c`
drives — so on the G3 the stock driver's register writes hit nothing, no
interrupt is ever enabled, the timer clockevent is dead, and boot hangs at the
first `usleep_range()`. The driver programs sense/event/dual-edge per
datasheet Table 36 (no firmware does it on the P2A reset-boot path) and ACKs
edge sources via `VIC38`.

Bind it from the DT (see `asus-kgpe-d16-firmware/dts/kgpe-d16-g3vic.dts` on
branch `claude/culvert-g3-port`):

```dts
vic: interrupt-controller@1e6c0000 {
    compatible = "aspeed,ast2050-vic";
    reg = <0x1e6c0000 0x1000>;
    interrupt-controller;
    #interrupt-cells = <1>;
};
```

**Hardware-verified 2026-07-09 on the real KGPE-D16 AST2050** (boot via
culvert P2A + TFTP): the FTTMR010 clockevent fires (~1 kHz), `eth0` links up
on real interrupts, IP-config completes, and NFS-root userspace runs. Full
debug narrative: `asus-kgpe-d16-firmware/TIMER-CLOCKEVENT-ROOT-CAUSE.md`
(branch `claude/culvert-g3-port`).

## Applying

```sh
git clone --depth 1 --branch v6.6.70 \
    https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git
cd linux
git am path/to/0001-*.patch path/to/0002-*.patch path/to/0003-*.patch
# (0002 is a plain diff, not a mail: use `git apply` / `patch -p1` for it)
```
