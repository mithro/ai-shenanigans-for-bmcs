"""Unit tests for backend construction (pure argv/command builders + registry)."""

import pytest

from firmware_testbench import TargetConfig, available_backends, make_target
from firmware_testbench.backends.hil import build_openocd_flash_cmd
from firmware_testbench.backends.qemu import build_qemu_argv


def test_registry_has_both_backends():
    assert available_backends() == ["hil", "qemu"]


def test_make_target_unknown_backend():
    with pytest.raises(ValueError):
        make_target("bogus", TargetConfig(board="c410x"))


def test_qemu_argv_c410x_kernel_boot():
    cfg = TargetConfig(
        board="c410x", kernel="uImage", dtb="c410x.dtb", initrd="uInitrd",
        ssh_port=2223, ram_mb=128,
    )
    argv = build_qemu_argv(cfg, qemu_bin="qemu-system-arm")
    assert argv[:5] == ["qemu-system-arm", "-M", "c410x-bmc", "-nographic", "-m"]
    assert "128" in argv
    for flag, val in [("-kernel", "uImage"), ("-dtb", "c410x.dtb"),
                      ("-initrd", "uInitrd")]:
        assert argv[argv.index(flag) + 1] == val
    # SSH hostfwd uses the configured port.
    assert any("hostfwd=tcp::2223-:22" in a for a in argv)
    # ftgmac100 NIC is wired.
    assert any("model=ftgmac100" in a for a in argv)


def test_qemu_argv_flash_drive():
    cfg = TargetConfig(board="kgpe-d16", flash="flash.img")
    argv = build_qemu_argv(cfg)
    assert any(a.startswith("file=flash.img") and "if=mtd" in a for a in argv)
    assert argv[1:3] == ["-M", "kgpe-d16-bmc"]


def test_qemu_argv_unknown_board():
    with pytest.raises(ValueError):
        build_qemu_argv(TargetConfig(board="nope"))


def test_openocd_flash_cmd_c410x():
    cfg = TargetConfig(board="c410x")
    argv = build_openocd_flash_cmd(cfg, "image.bin", offset=0x14000000)
    assert argv[0] == "openocd"
    assert "-f" in argv and "ast2050.cfg" in argv
    assert argv[-2] == "-c"
    assert argv[-1] == "init; program image.bin 0x14000000 verify reset exit"
