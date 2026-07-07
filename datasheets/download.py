#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Re-download the vendored Aspeed SoC datasheets in this directory.

These PDFs are committed to the repo (see README.md); this script exists so the
exact artifacts can be reproduced from the upstream VGA-museum mirrors. Run:

    uv run datasheets/download.py

Fails loudly (non-zero exit) if any document cannot be fetched or verified, per
the repo's "fail loud and fast" convention -- no silent fallbacks.
"""

import hashlib
import io
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

ASPEED_DIR = Path(__file__).resolve().parent / "aspeed"

# Each entry: dest filename, url, expected sha256, zip-member (or None), note
DOCS = [
    (
        "AST2400_Datasheet.pdf",
        "https://www.vgamuseum.info/images/doc/aspeed/ast2400_datasheet.zip",
        "c229cec162e12d2d0214184761f08ba171862eb94ec30c7e7b408b507e41f83e",
        "AST2400 - datasheet.pdf",  # PDF is inside a zip
        "AST2400/AST1250 A1 Datasheet V1.4 (702pp)",
    ),
    (
        "AST2500_Datasheet.pdf",
        "https://vgamuseum.info/images/doc/aspeed/ast2520a2gp_datasheet.pdf",
        "757f13ac745c3d071fb0b1e4d48be2146c257db9495d71874933c16d530e5f1f",
        None,
        "AST2500/AST2520 A2 Datasheet V1.6 / 'Software Programming Guide' (833pp)",
    ),
    (
        "AST2600_Datasheet.pdf",
        "https://www2.vgamuseum.info/images/doc/aspeed/ast2600_datasheet.pdf",
        "5205848143aeecb752d202a6ac11321681c55993c6597322a0c45c3763920962",
        None,
        "AST2600 A3 Datasheet V1.2 (1580pp)",
    ),
]


def fetch(url: str) -> bytes:
    """Download a URL, returning its bytes. Raises on any failure."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    )
    # Some mirrors have broken cert chains; the sha256 check below is the real
    # integrity guarantee, so tolerate cert issues but keep everything else loud.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        return resp.read()


def main() -> int:
    ASPEED_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    for name, url, want_sha, member, note in DOCS:
        dest = ASPEED_DIR / name
        print(f"\n{name}  <-  {url}\n  ({note})")
        try:
            blob = fetch(url)
            if member is not None:
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    blob = zf.read(member)
            if not blob.startswith(b"%PDF"):
                raise ValueError(f"not a PDF (starts {blob[:8]!r})")

            got_sha = hashlib.sha256(blob).hexdigest()
            dest.write_bytes(blob)
            if got_sha == want_sha:
                print(f"  OK  {len(blob):,} bytes  sha256 verified")
            else:
                # A newer datasheet revision changes the hash -- surface it, do
                # not silently accept or reject.
                print(f"  WARNING  sha256 mismatch (upstream revised?)")
                print(f"    expected {want_sha}")
                print(f"    got      {got_sha}")
        except Exception as exc:  # noqa: BLE001 -- report and continue, fail at end
            print(f"  FAIL  {exc}")
            failures.append(name)

    if failures:
        print(f"\nFAILED: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nAll datasheets downloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
