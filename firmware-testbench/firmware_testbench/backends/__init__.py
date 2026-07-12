"""Backend registry population. Importing this registers all known backends."""

from . import hil, qemu  # noqa: F401  (side effect: register_backend)

__all__ = ["qemu", "hil"]
