"""QEMU backend: boot firmware under a custom qemu-system-arm machine.

The argv construction is a pure function (`build_qemu_argv`) so it is unit-tested
without launching anything; `QEMUTarget` wires it to a real subprocess + serial
socket at run time (exercised by integration CI once the QEMU fork is built).
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from typing import Sequence

from ..console import Console
from ..target import Target, TargetConfig, register_backend

# Map board -> QEMU machine name provided by the mithro/qemu fork.
BOARD_MACHINE = {
    "kgpe-d16": "kgpe-d16-bmc",
    "c410x": "c410x-bmc",       # board-complete machine (planned)
    "ipdu": "ns9360",
}


def build_qemu_argv(
    config: TargetConfig,
    *,
    qemu_bin: str = "qemu-system-arm",
    serial_socket: str | None = None,
) -> list[str]:
    """Construct the qemu-system-arm command line for ``config``.

    Pure and deterministic -- the unit tests assert the exact flags so that
    changes to how a board is launched are reviewable.
    """
    if config.board not in BOARD_MACHINE:
        raise ValueError(
            f"no QEMU machine for board {config.board!r}; "
            f"known: {sorted(BOARD_MACHINE)}"
        )
    argv: list[str] = [qemu_bin, "-M", BOARD_MACHINE[config.board], "-nographic"]

    if config.ram_mb is not None:
        argv += ["-m", str(config.ram_mb)]
    if config.kernel:
        argv += ["-kernel", config.kernel]
    if config.dtb:
        argv += ["-dtb", config.dtb]
    if config.initrd:
        argv += ["-initrd", config.initrd]
    if config.flash:
        # SPI NOR modelled as an MTD/pflash drive on the machine.
        argv += ["-drive", f"file={config.flash},format=raw,if=mtd"]

    # ftgmac100 on user-net with an SSH host-forward, mirroring the existing
    # run-qemu.py convention (hostfwd tcp::<ssh_port>-:22).
    argv += [
        "-netdev", f"user,id=net0,hostfwd=tcp::{config.ssh_port}-:22",
        "-net", "nic,model=ftgmac100,netdev=net0",
    ]

    if serial_socket:
        argv += ["-serial", f"unix:{serial_socket},server=on,wait=off"]
    else:
        argv += ["-serial", "stdio"]
    return argv


class QEMUTarget(Target):
    def __init__(self, config: TargetConfig, qemu_bin: str = "qemu-system-arm") -> None:
        super().__init__(config)
        self._qemu_bin = qemu_bin
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._console: Console | None = None

    def start(self) -> None:
        if shutil.which(self._qemu_bin) is None:
            raise FileNotFoundError(
                f"{self._qemu_bin} not found; build the mithro/qemu fork first"
            )
        argv = build_qemu_argv(self.config, qemu_bin=self._qemu_bin)
        self._proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0,
        )
        stdout, stdin = self._proc.stdout, self._proc.stdin
        assert stdout is not None and stdin is not None

        def _read() -> bytes:
            # Non-blocking-ish read of whatever is buffered.
            import os
            import select
            r, _, _ = select.select([stdout], [], [], 0)
            if r:
                return os.read(stdout.fileno(), 65536)
            return b""

        self._console = Console(_read, stdin.write)

    def console(self) -> Console:
        if self._console is None:
            raise RuntimeError("QEMUTarget not started")
        return self._console

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None


register_backend("qemu", QEMUTarget)
