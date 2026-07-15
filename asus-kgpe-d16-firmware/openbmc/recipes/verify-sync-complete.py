#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Guard: every file:// SRC_URI source of a recipe that sync-to-openbmc-tree.sh
stages must ITSELF be staged by that script — otherwise a `bitbake` of the image
fails do_fetch on the missing source (or silently ships a stale file).

Static check (no build). For each .bb/.bbappend under recipes/ whose basename the
sync script installs, collect its `file://NAME` sources and confirm each NAME is
also installed by the sync. Recipes the sync does NOT stage (e.g. nbd-swap, which
is deployed over NBD, not baked into the image) are out of scope and skipped.

Run:  uv run asus-kgpe-d16-firmware/openbmc/recipes/verify-sync-complete.py
Exit 0 = complete; exit 1 = a staged recipe references an unstaged source.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SYNC = (ROOT / "sync-to-openbmc-tree.sh").read_text()

# Filenames the sync script stages: anything it names in an `install`/`for f in`.
# NB: list `bbappend` before `bb` so the alternation prefers the longer suffix
# (else "foo.bbappend" is truncated to "foo.bb").
STAGED = set(re.findall(r"[\w.@%+-]+\.(?:bbappend|bb|conf|sh|service|json|yaml|bin)",
                        SYNC))

# license references are not SRC_URI payload; ignore.
IGNORE = {"Apache-2.0", "MIT", "GPL-2.0-or-later"}

missing = []
checked = 0
staged_recipes = 0
for rec in sorted(ROOT.rglob("*.bb")) + sorted(ROOT.rglob("*.bbappend")):
    if rec.name not in STAGED:          # sync does not stage this recipe -> skip
        continue
    staged_recipes += 1
    # Strip bitbake comments (# to end-of-line) FIRST so a file:// that appears
    # only inside an explanatory comment is NOT counted as a real SRC_URI source
    # (which would give accidental, fragile "coverage"). Scope note: a file staged
    # for a BASE recipe's SRC_URI via a .bbappend's FILESEXTRAPATHS — where the
    # .bbappend itself declares no file:// — is outside this static check (the
    # file:// lives in the upstream base recipe, which this repo does not contain).
    text = "\n".join(ln.split("#", 1)[0] for ln in rec.read_text().splitlines())
    for m in re.findall(r"file://([A-Za-z0-9._@%+-]+)", text):
        name = m.split("/")[-1]
        if name in IGNORE:
            continue
        checked += 1
        if name not in STAGED:
            missing.append((rec.name, name))

print(f"checked {checked} file:// sources across {staged_recipes} sync-staged recipes")
if missing:
    print(f"\n*** {len(missing)} staged recipe(s) reference an UNSTAGED source: ***")
    for rec, name in missing:
        print(f"  {rec}: file://{name}  (add it to sync-to-openbmc-tree.sh)")
    sys.exit(1)
print("OK: every staged recipe's file:// sources are also staged by the sync script")
