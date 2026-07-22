# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown"]
# ///
"""Generate the styled HTML status report from the canonical markdown version.

The markdown file is the source of truth; this wraps its rendered HTML in a
self-contained, theme-aware template with a TOC sidebar and colourised status
glyphs. Fails loud on any missing input.
"""
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/reports/2026-07-22-ast2050-kgpe-d16-status.md"
DST = ROOT / "docs/reports/2026-07-22-ast2050-kgpe-d16-status.html"

md_text = SRC.read_text(encoding="utf-8")

md = markdown.Markdown(extensions=["tables", "toc", "fenced_code"], extension_configs={
    "toc": {"toc_depth": "2-3", "anchorlink": False},
})
body = md.convert(md_text)
toc = md.toc

# Colourise status glyphs everywhere (tables + prose).
GLYPHS = {
    "✅": '<span class="st ok">✅</span>',        # ✅
    "\U0001F536": '<span class="st part">\U0001F536</span>',  # 🔶
    "\U0001F537": '<span class="st blk">\U0001F537</span>',   # 🔷
    "⬜": '<span class="st todo">⬜</span>',      # ⬜
    "Ⓝ": '<span class="st na">Ⓝ</span>',        # Ⓝ
    "◐": '<span class="st part">◐</span>',      # ◐
    "✗": '<span class="st blk">✗</span>',       # ✗
}
for g, rep in GLYPHS.items():
    body = body.replace(g, rep)

CSS = """
:root {
  --bg: #ffffff; --fg: #1c2733; --muted: #5b6b7b; --line: #dde4ea;
  --accent: #0b5fa5; --thead: #eef3f7; --row: #f7fafc; --chip: #eef3f7;
  --ok: #1a7f37; --part: #b26a00; --blk: #0b5fa5; --todo: #8a97a3; --na: #8a97a3;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #10151b; --fg: #dbe4ec; --muted: #93a4b3; --line: #2a3541;
    --accent: #6cb2ee; --thead: #1a222c; --row: #151d25; --chip: #1a222c;
    --ok: #4ac26b; --part: #e3a008; --blk: #6cb2ee; --todo: #7a8894; --na: #7a8894;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.layout { display: flex; max-width: 1500px; margin: 0 auto; }
nav.toc {
  position: sticky; top: 0; align-self: flex-start; flex: 0 0 290px;
  max-height: 100vh; overflow-y: auto; padding: 24px 8px 24px 20px;
  border-right: 1px solid var(--line); font-size: 13px;
}
nav.toc > .toctitle { font-weight: 700; margin-bottom: 8px; color: var(--muted);
  text-transform: uppercase; letter-spacing: .06em; font-size: 11px; }
nav.toc ul { list-style: none; margin: 0; padding-left: 12px; }
nav.toc > ul { padding-left: 0; }
nav.toc li { margin: 3px 0; }
main { flex: 1 1 auto; min-width: 0; padding: 28px 36px 80px; }
h1 { font-size: 26px; line-height: 1.25; margin: 0 0 12px; }
h2 { font-size: 21px; margin: 44px 0 10px; padding-top: 10px; border-top: 2px solid var(--line); }
h3 { font-size: 16.5px; margin: 26px 0 8px; }
p, li { max-width: 1050px; }
blockquote { margin: 12px 0; padding: 8px 14px; border-left: 3px solid var(--part);
  background: var(--row); color: var(--muted); }
code { background: var(--chip); padding: 1px 5px; border-radius: 4px;
  font: 12.5px/1.4 ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; margin: 12px 0 18px; font-size: 13.5px; width: auto; }
th, td { border: 1px solid var(--line); padding: 5px 9px; text-align: left; vertical-align: top; }
thead th { background: var(--thead); position: sticky; top: 0; }
tbody tr:nth-child(even) { background: var(--row); }
td:first-child { white-space: nowrap; }
.st { font-weight: 600; }
.st.ok { color: var(--ok); } .st.part { color: var(--part); }
.st.blk { color: var(--blk); } .st.todo, .st.na { color: var(--todo); }
hr { border: 0; border-top: 1px solid var(--line); margin: 34px 0; }
em { color: var(--muted); }
@media (max-width: 1000px) { nav.toc { display: none; } main { padding: 18px; } }
@media print { nav.toc { display: none; } body { font-size: 12px; } }
"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AST2050 / ASUS KGPE-D16 open-firmware program — status report 2026-07-22</title>
<style>{CSS}</style>
</head>
<body>
<div class="layout">
<nav class="toc"><div class="toctitle">Contents</div>{toc}</nav>
<main>
{body}
</main>
</div>
</body>
</html>
"""

# Wrap tables for horizontal scroll on narrow screens.
html = html.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")

DST.write_text(html, encoding="utf-8")
print(f"wrote {DST} ({DST.stat().st_size:,} bytes)")
