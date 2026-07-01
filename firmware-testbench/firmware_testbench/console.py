"""Serial/console expect engine.

Transport-agnostic: it reads and writes bytes through injected callables, so the
same expect logic drives a QEMU serial socket, an SSH channel, or a real UART on
the hardware-in-the-loop rig -- and is unit-testable with fake streams (no real
IO, no wall-clock sleeps).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Pattern, Sequence, Union

PatternLike = Union[str, Pattern[str]]


class ExpectTimeout(TimeoutError):
    """Raised when none of the expected patterns appear before the deadline.

    Carries the console buffer accumulated so far so callers (and test
    failures) can see exactly what the target *did* emit -- failing loud, per
    the project convention.
    """

    def __init__(self, patterns: Sequence[PatternLike], timeout: float, buffer: str):
        self.patterns = [p if isinstance(p, str) else p.pattern for p in patterns]
        self.timeout = timeout
        self.buffer = buffer
        super().__init__(
            f"timed out after {timeout:.1f}s waiting for {self.patterns!r}; "
            f"buffer tail: {buffer[-400:]!r}"
        )


@dataclass
class Match:
    """Result of a successful :meth:`Console.expect`."""

    index: int          # index into the pattern list that matched
    match: re.Match     # the regex match object
    before: str         # console text emitted before the match
    after: str          # the matched text itself


class Console:
    """Line-oriented expect over arbitrary byte transports.

    Parameters
    ----------
    read:
        ``read() -> bytes`` returning any bytes currently available (``b""`` if
        none). Must not block indefinitely; a short-timeout read is expected.
    write:
        ``write(data: bytes) -> None``.
    clock / sleep:
        injectable time sources so timeouts are deterministic under test.
    """

    def __init__(
        self,
        read: Callable[[], bytes],
        write: Callable[[bytes], None],
        *,
        encoding: str = "utf-8",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = 0.02,
    ) -> None:
        self._read = read
        self._write = write
        self._encoding = encoding
        self._clock = clock
        self._sleep = sleep
        self._poll = poll_interval
        self._buf = ""

    @property
    def buffer(self) -> str:
        """Text seen so far and not yet consumed by an ``expect``."""
        return self._buf

    def _compile(self, patterns: Sequence[PatternLike]) -> list[Pattern[str]]:
        return [p if isinstance(p, re.Pattern) else re.compile(p) for p in patterns]

    def expect(
        self,
        patterns: PatternLike | Sequence[PatternLike],
        timeout: float = 30.0,
    ) -> Match:
        """Wait until one of ``patterns`` matches the console stream.

        Returns the first pattern (by list order) that matches at the earliest
        position. Consumes the buffer up to and including the match.
        """
        if isinstance(patterns, (str, re.Pattern)):
            patterns = [patterns]
        compiled = self._compile(patterns)
        deadline = self._clock() + timeout

        while True:
            best: tuple[int, re.Match] | None = None
            for idx, pat in enumerate(compiled):
                m = pat.search(self._buf)
                if m and (best is None or m.start() < best[1].start()):
                    best = (idx, m)
            if best is not None:
                idx, m = best
                before, after = self._buf[: m.start()], m.group(0)
                self._buf = self._buf[m.end():]
                return Match(index=idx, match=m, before=before, after=after)

            if self._clock() >= deadline:
                raise ExpectTimeout(patterns, timeout, self._buf)

            chunk = self._read()
            if chunk:
                self._buf += chunk.decode(self._encoding, errors="replace")
            else:
                self._sleep(self._poll)

    def send(self, data: str) -> None:
        self._write(data.encode(self._encoding))

    def send_line(self, line: str = "", newline: str = "\n") -> None:
        self.send(line + newline)
