"""Integration test: Video engine (KVM) faithfulness on the QEMU model.

The AST2050 video engine (0x1E700000) is not modelled — checks xfail until an
aspeed.video-ast2050 device is added (see peripherals/video/DOC.md §3). This blocks
OpenBMC KVM verification. No hardware here.
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


@pytest.mark.xfail(reason="video engine unmodelled; needs aspeed.video-ast2050 (DOC.md §3)",
                   strict=False)
def test_video_modelled(video):
    c = next((c for c in video.checks if c[0] == "vr000.unlock"), None)
    assert c is not None and c[1]
