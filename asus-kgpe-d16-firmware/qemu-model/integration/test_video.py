"""Integration test: Video engine (KVM) faithfulness on the QEMU model.

The AST2050 video engine (0x1E700000) is now modelled by aspeed.video-ast2050 — VR000
is a protection-key lock latch (unlock 0x1A038AA8 -> reads 1), the rest RW while
unlocked, so the OpenBMC aspeed-video driver can bind. Frame capture is deferred. See
peripherals/video/DOC.md. No hardware here.
"""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402
skip_reason = runner.preconditions()
pytestmark = pytest.mark.skipif(skip_reason is not None, reason=skip_reason or "")


@pytest.fixture(scope="module")
def video():
    return runner.run_fwtest("video")


def test_reaches_halt(video):
    assert video.halted, f"video fwtest did not reach the halt sentinel:\n{video.raw}"


def test_protection_key_unlock(video):
    c = next((c for c in video.checks if c[0] == "vr000.unlock"), None)
    assert c is not None and c[1], f"video VR000 protection key not modelled:\n{video.raw}"
