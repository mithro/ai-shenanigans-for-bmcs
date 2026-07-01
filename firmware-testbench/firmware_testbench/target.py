"""The Target abstraction: one bench, two backends.

A ``Target`` is whatever runs the firmware -- QEMU today, real hardware on the
HIL rig later. Board benches are written against this interface only, so the
exact same assertions run in CI (``backend="qemu"``) and against silicon
(``backend="hil"``).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from .console import Console


@dataclass
class TargetConfig:
    """Backend-agnostic description of what to boot and how to reach it."""

    board: str                          # "kgpe-d16" | "c410x" | "ipdu"
    kernel: str | None = None
    dtb: str | None = None
    initrd: str | None = None
    flash: str | None = None
    ssh_port: int = 2222
    ssh_key: str | None = None
    ram_mb: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Target(abc.ABC):
    """A running firmware instance with a console and (optionally) SSH."""

    def __init__(self, config: TargetConfig) -> None:
        self.config = config

    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    @abc.abstractmethod
    def console(self) -> Console:
        """Return the serial console expecter (must be available after start)."""

    def ssh(self, command: str, timeout: float = 60.0) -> tuple[int, str]:
        """Run ``command`` over SSH; return (exit_status, combined_output).

        Optional -- backends without SSH raise ``NotImplementedError``.
        """
        raise NotImplementedError(f"{type(self).__name__} has no SSH backend")

    def __enter__(self) -> "Target":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


# Registry populated by backend modules via ``register_backend``.
_BACKENDS: dict[str, type[Target]] = {}


def register_backend(name: str, cls: type[Target]) -> None:
    _BACKENDS[name] = cls


def _ensure_backends() -> None:
    """Populate the registry by importing the backend modules (idempotent).

    Backends self-register as an import side effect; import them lazily here so
    importing this module never drags in heavy backend deps, while any public
    entry point still sees a fully-populated registry.
    """
    from . import backends  # noqa: F401  (populates the registry)


def available_backends() -> list[str]:
    _ensure_backends()
    return sorted(_BACKENDS)


def make_target(backend: str, config: TargetConfig) -> Target:
    """Factory: construct a Target for ``backend`` ("qemu" | "hil")."""
    _ensure_backends()
    if backend not in _BACKENDS:
        raise ValueError(
            f"unknown backend {backend!r}; available: {available_backends()}"
        )
    return _BACKENDS[backend](config)
