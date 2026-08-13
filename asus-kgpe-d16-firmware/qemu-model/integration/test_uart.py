"""Integration test: UART faithfulness on the QEMU model.

Boots `peripherals/uart/fwtest.c` under `-M kgpe-d16-bmc`: the 16550 scratch
register is RW, LSR reports transmit-ready, and an internal MCR[4] loopback echoes
THR->RBR on UART1. The model is 16550-faithful for the G3 (no change needed); baud
rate precision ties to the SCU clock-tree. See peripherals/uart/DOC.md. No hardware.

Run:  uv run --with pytest python -m pytest integration/test_uart.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402

skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def uart():
    return runner.run_fwtest("uart")


def test_reaches_halt(uart):
    assert uart.halted, f"uart fwtest did not reach the halt sentinel:\n{uart.raw}"


def test_all_checks_pass(uart):
    failed = [c for c in uart.checks if not c[1]]
    assert uart.fails == 0, f"UART checks failed: {failed}\n{uart.raw}"


def test_loopback(uart):
    c = next((c for c in uart.checks if c[0] == "uart1.loopback"), None)
    assert c is not None and c[1], f"UART loopback failed:\n{uart.raw}"
