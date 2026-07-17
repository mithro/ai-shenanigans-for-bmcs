#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Decrypt + decompress an ASUS OpenBoardView .FZ file and dump its netlist.

Reimplements the RC6 decryption and zlib split used by OpenBoardView's
FZFile.cpp so the board's parts / pins / nets can be analysed in Python
without the GUI.

The 44-word FZ key is NOT stored in this repository. Supply it via the
``OBV_FZKEY`` environment variable or a ``.env`` file (see ``.env.example``
and the "Regenerating the data" section of the README for where to obtain it).

Usage:
    uv run extract_fz.py <file.FZ> [--json out.json]
"""
import argparse
import json
import os
import re
import struct
import sys
import zlib

MASK = 0xFFFFFFFF

KEY_ENV_VAR = "OBV_FZKEY"


def _read_env_file():
    """Return dict of KEY=VALUE pairs from the nearest .env file, if any.

    Looks in the current directory and in the repo directory that contains this
    script (its parent), so the tool works whether run from tools/ or the board
    root. This is a tiny loader - no python-dotenv dependency."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(here, "..", ".env"),   # asus-kcma-d8/.env
        os.path.join(here, ".env"),
    ]
    env = {}
    for path in candidates:
        if not os.path.isfile(path):
            continue
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def load_fz_key():
    """Load and validate the 44-word FZ key from the environment / .env file."""
    raw = os.environ.get(KEY_ENV_VAR) or _read_env_file().get(KEY_ENV_VAR)
    if not raw:
        sys.exit(
            f"FZ key not found. Set {KEY_ENV_VAR} in the environment or in a\n"
            f"  .env file (comma/space-separated 0x hex words). See .env.example\n"
            f"  and the README for where to obtain the OpenBoardView FZ key."
        )
    words = [int(w, 16) for w in re.findall(r"0x[0-9a-fA-F]+", raw)]
    if len(words) != 44:
        sys.exit(f"FZ key must be 44 hex words, got {len(words)}. Check your .env.")
    return words


def rotl32(a, b):
    b &= 31
    if b == 0:
        return a & MASK
    return ((a << b) | (a >> (32 - b))) & MASK


def rc6_decode(buf, key):
    """RC6 decrypt in-place, 1:1 with FZFile::decode()."""
    r = 20
    logw = 5
    A = B = C = D = 0
    ibuf = bytearray(16)
    out = bytearray(buf)
    for pos in range(len(out)):
        B = (B + key[0]) & MASK
        D = (D + key[1]) & MASK
        for i in range(1, r + 1):
            t = rotl32((B * (2 * B + 1)) & MASK, logw)
            u = rotl32((D * (2 * D + 1)) & MASK, logw)
            A = (rotl32(A ^ t, u) + key[2 * i]) & MASK
            C = (rotl32(C ^ u, t) + key[2 * i + 1]) & MASK
            A, B, C, D = B, C, D, A
        A = (A + key[2 * r + 2]) & MASK
        C = (C + key[2 * r + 3]) & MASK
        cur = out[pos]
        out[pos] = cur ^ (A & 0xFF)
        del ibuf[0]
        ibuf.append(cur)
        A = ibuf[0] | ibuf[1] << 8 | ibuf[2] << 16 | ibuf[3] << 24
        B = ibuf[4] | ibuf[5] << 8 | ibuf[6] << 16 | ibuf[7] << 24
        C = ibuf[8] | ibuf[9] << 8 | ibuf[10] << 16 | ibuf[11] << 24
        D = ibuf[12] | ibuf[13] << 8 | ibuf[14] << 16 | ibuf[15] << 24
    return out


def load_fz(path):
    raw = open(path, "rb").read()
    # If it already carries the zlib signature at offset 4, it is not encrypted.
    if not (raw[4] == 0x78 and raw[5] in (0x9C, 0xDA)):
        raw = rc6_decode(raw, load_fz_key())
    if not (raw[4] == 0x78 and raw[5] in (0x9C, 0xDA)):
        sys.exit("Decryption failed: no zlib signature after decode.")
    # split(): last 4 bytes little-endian = descr length
    descr_size = struct.unpack_from("<I", raw, len(raw) - 4)[0]
    content_start = 4
    descr_start = len(raw) - descr_size + 4
    content = zlib.decompressobj().decompress(raw[content_start:])
    descr = zlib.decompressobj().decompress(raw[descr_start:])
    return content.decode("latin-1"), descr.decode("latin-1")


def parse_content(text):
    """Return (parts, pins). Mirrors FZFile::parse block handling."""
    parts = []          # list of dict(name, side)
    pins = []           # list of dict(net, part, pnum, pname, x, y)
    block = 0
    text = text.replace(",", ".")  # some boards use comma decimals
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0] == "A":
            body = line[2:]
            if body.startswith("REFDES"):
                block = 1
            elif body.startswith("NET_NAME"):
                block = 2
            elif body.startswith("TESTVIA"):
                block = 3
            else:
                block = -1
            continue
        if line[0] != "S":
            continue
        fields = line[2:].split("!")
        if block == 1:  # part
            name = fields[0]
            smirror = fields[3] if len(fields) > 3 else ""
            parts.append({"name": name,
                          "side": "bottom" if smirror == "YES" else "top"})
        elif block == 2:  # pin
            # NET!REFDES!PIN_NUMBER!PIN_NAME!X!Y!TESTPOINT!RADIUS
            net = fields[0]
            refdes = fields[1]
            pnum = fields[2] if len(fields) > 2 else ""
            pname = fields[3] if len(fields) > 3 else ""
            x = fields[4] if len(fields) > 4 else ""
            y = fields[5] if len(fields) > 5 else ""
            pins.append({"net": net, "part": refdes, "pnum": pnum,
                         "pname": pname, "x": x, "y": y})
    return parts, pins


def parse_descr(text):
    """Return dict partno->description and refdes->description via locations."""
    lines = text.splitlines()
    refdes_desc = {}
    rows = []
    for line in lines[2:]:
        line = line.strip()
        if not line or line[0] == "s":
            continue
        f = line.split("\t")
        if len(f) < 4:
            continue
        partno, desc, qty, locs = f[0], f[1], f[2], f[3]
        rows.append((partno, desc, locs))
        for loc in locs.split():
            refdes_desc[loc.strip()] = desc
    return refdes_desc, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fz")
    ap.add_argument("--json")
    args = ap.parse_args()

    content, descr = load_fz(args.fz)
    parts, pins = parse_content(content)
    refdes_desc, desc_rows = parse_descr(descr)

    print(f"parts={len(parts)} pins={len(pins)} descr_rows={len(desc_rows)}")

    # pins per part
    from collections import Counter, defaultdict
    per_part = Counter(p["part"] for p in pins)
    nets = defaultdict(list)
    for p in pins:
        nets[p["net"]].append(p)

    if args.json:
        out = {
            "parts": parts,
            "pins": pins,
            "refdes_desc": refdes_desc,
            "per_part_pincount": dict(per_part),
        }
        json.dump(out, open(args.json, "w"), indent=1)
        print(f"wrote {args.json}")

    # Show the biggest parts (BGA candidates) with descriptions
    print("\nLargest parts by pin count:")
    for name, cnt in per_part.most_common(25):
        print(f"  {name:8s} {cnt:5d}  {refdes_desc.get(name, '')}")


if __name__ == "__main__":
    main()
