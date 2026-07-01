"""QEMU backend: boot firmware under a custom qemu-system-arm machine.

The argv construction is a pure function (`build_qemu_argv`) so it is unit-tested
without launching anything; `QEMUTarget` wires it to a real subprocess + serial
socket at run time (exercised by integration CI once the QEMU fork is built).
"""

from __future__ import annotations

import os
import select
import shutil
import subprocess

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
    # Use '-display none' (not '-nographic'): '-nographic' also muxes the serial
    # + monitor onto stdio, which fatally conflicts with our explicit
    # '-serial stdio' below ("cannot use stdio by multiple character devices").
    argv: list[str] = [qemu_bin, "-M", BOARD_MACHINE[config.board], "-display", "none"]

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
        self._console: Console | None = None

    def start(self) -> None:
        if shutil.which(self._qemu_bin) is None:
            raise FileNotFoundError(
                f"{self._qemu_bin} not found; build the mithro/qemu fork first"
            )
        argv = build_qemu_argv(self.config, qemu_bin=self._qemu_bin)
        proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0,
        )
        self._proc = proc
        stdout, stdin = proc.stdout, proc.stdin
        assert stdout is not None and stdin is not None

        def _read() -> bytes:
            # Non-blocking read of whatever is buffered.
            r, _, _ = select.select([stdout], [], [], 0)
            if not r:
                return b""
            data = os.read(stdout.fileno(), 65536)
            if data:
                return data
            # EOF: the console pipe closed. No more output will ever arrive, so
            # fail loud immediately rather than letting expect() burn its whole
            # timeout masking a crashed/exited QEMU as a plain timeout.
            raise RuntimeError(
                f"{self._qemu_bin} closed its console (exit code {proc.poll()}) "
                f"before the expected output"
            )

        self._console = Console(_read, stdin.write)

    def console(self) -> Console:
        if self._console is None:
            raise RuntimeError("QEMUTarget not started")
        return self._console

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        self._console = None
        if proc is None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()  # reap the killed child so it is not left a zombie
        finally:
            for pipe in (proc.stdin, proc.stdout):
                if pipe is not None:
                    pipe.close()


register_backend("qemu", QEMUTarget)
