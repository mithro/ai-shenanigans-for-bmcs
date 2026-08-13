"""Integration test: Video engine (KVM) faithfulness on the QEMU model.

The AST2050 video engine (0x1E700000) is modelled by aspeed.video-ast2050 — VR000
is a protection-key lock latch (unlock 0x1A038AA8 -> reads 1), and the capture
datapath is behavioural: VR004[0] mode detection reports the internal-VGA
640x480 scanout, VR004[1]/[4] capture+compression reads the VGA carve-out at
the top of DRAM, writes a JPEG to the VR054 stream buffer, updates the
VR070/VR078/VR07C read-back counters and raises completion on VIC INT#7. See
peripherals/video/DOC.md and DATASHEET-VIDEO.md. No hardware here.
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


def _check(t, label):
    c = next((c for c in t.checks if c[0] == label), None)
    assert c is not None and c[1], f"video fwtest check '{label}' failed:\n{t.raw}"


def test_reaches_halt(video):
    assert video.halted, f"video fwtest did not reach the halt sentinel:\n{video.raw}"


def test_protection_key_unlock(video):
    _check(video, "vr000.unlock")


def test_engine_idle_status(video):
    """VR004[16]/[18] read 1 (idle) when no frame is in flight (p.234)."""
    _check(video, "vr004.idle")
    _check(video, "frame.idle")


def test_mode_detection(video):
    """VR004[0] trigger -> internal-VGA 640x480 read-back + VR308[4] (p.235)."""
    _check(video, "md.ready")
    _check(video, "md.stable")
    _check(video, "md.width")
    _check(video, "md.height")


def test_capture_datapath(video):
    """VR004[1]/[4] trigger -> JPEG in the VR054 stream buffer + completion
    status (p.234-236, 243, 246-247, 250)."""
    _check(video, "frame.complete")
    _check(video, "jpeg.soi")
    _check(video, "jpeg.size.aligned")
    _check(video, "jpeg.size.nonzero")
    assert video.kvs.get("frame.counter") == 1, video.raw


def test_vic_int7(video):
    """Completion is a level-high line into VIC INT#7 (§10 p.99): pending in
    the raw status while VR308&VR304 != 0, dropped by the W1C ack."""
    _check(video, "vic.int7.raw")
    _check(video, "vic.int7.clear")
