"""Hardware-in-the-loop backend: drive a real board via the RPi OpenOCD/UART rig.

The command construction (OpenOCD flash, UART console) is pure and testable now;
the live wiring lands when the remotely-accessible RPi-connected boards
(rpi4-pmod / rpi5-pmod / rpi4-gwifi pattern) come online.
"""

from __future__ import annotations

from ..console import Console
from ..target import Target, TargetConfig, register_backend

# Per-board OpenOCD adapter + target config files (in the program's openocd/ dir).
BOARD_OPENOCD = {
    "kgpe-d16": ("rpi4-jtag.cfg", "ast2050.cfg", "kgpe-d16-bmc.cfg"),
    "c410x": ("rpi4-jtag.cfg", "ast2050.cfg", "c410x-bmc.cfg"),
    "ipdu": ("rpi4-jtag.cfg", "ns9360.cfg", "hpe-ipdu.cfg"),
}


def build_openocd_flash_cmd(config: TargetConfig, image: str, *, offset: int = 0) -> list[str]:
    """OpenOCD invocation to program ``image`` into the board's SPI NOR."""
    if config.board not in BOARD_OPENOCD:
        raise ValueError(f"no OpenOCD config for board {config.board!r}")
    cfgs = BOARD_OPENOCD[config.board]
    argv = ["openocd"]
    for c in cfgs:
        argv += ["-f", c]
    argv += ["-c", f"init; program {image} {offset:#x} verify reset exit"]
    return argv


class HILTarget(Target):
    def __init__(self, config: TargetConfig) -> None:
        super().__init__(config)
        self._console: Console | None = None

    def start(self) -> None:  # pragma: no cover - needs real hardware
        raise NotImplementedError(
            "HIL backend requires the RPi OpenOCD/UART rig; wiring lands with the "
            "rpi4-pmod / rpi5-pmod boards. build_openocd_flash_cmd() is usable now."
        )

    def console(self) -> Console:  # pragma: no cover - needs real hardware
        raise NotImplementedError("HIL console requires the physical UART rig")

    def stop(self) -> None:  # pragma: no cover
        pass


register_backend("hil", HILTarget)
