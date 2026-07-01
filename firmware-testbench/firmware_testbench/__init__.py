"""firmware-testbench: one bench, two backends (QEMU + hardware-in-the-loop).

Public API::

    from firmware_testbench import make_target, TargetConfig
    cfg = TargetConfig(board="c410x", kernel="uImage", dtb="c410x.dtb")
    with make_target("qemu", cfg) as t:
        t.console().expect(r"login:")
"""

from .console import Console, ExpectTimeout, Match
from .target import (
    Target,
    TargetConfig,
    available_backends,
    make_target,
    register_backend,
)

__all__ = [
    "Console",
    "ExpectTimeout",
    "Match",
    "Target",
    "TargetConfig",
    "make_target",
    "available_backends",
    "register_backend",
]
