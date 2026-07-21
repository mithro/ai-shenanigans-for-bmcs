# scripts — Ghidra / MCP infrastructure helpers

Repo-wide helper scripts for the Ghidra decompilation setup used by the
firmware reverse engineering (see "Ghidra decompilation via MCP" in the
top-level [`CLAUDE.md`](../CLAUDE.md)). Board-specific tooling lives in the
board directories, not here.

- **`vnc-display.sh`** — starts/stops a headless X display (`:99`, via VNC) that
  Ghidra's GUI — and the `ghidra-mcp`, `pyghidra-mcp`, and `playwright` MCP
  servers configured in [`../.mcp.json`](../.mcp.json) — need to run.
  Usage: `scripts/vnc-display.sh start|stop|status`.
- **`ghidra-vnc.sh`** — launches the Ghidra GUI (`GHIDRA_INSTALL_DIR`) on that
  display, optionally opening a project file:
  `scripts/ghidra-vnc.sh [project-file]`. Enable the **GhidraMCPPlugin** in the
  GUI afterwards so the MCP bridge can connect.
- **`bridge_mcp_ghidra.py`** — the MCP↔Ghidra bridge itself: a FastMCP server
  (PEP 723 script; deps `mcp` + `requests`) that translates MCP tool calls into
  HTTP requests against the GhidraMCPPlugin's REST endpoint (default
  `http://127.0.0.1:8080/`). Launched via `.mcp.json` as the `ghidra-mcp`
  server; run with `uv run scripts/bridge_mcp_ghidra.py`.

Typical bring-up order:

```sh
scripts/vnc-display.sh start          # 1. X display :99
scripts/ghidra-vnc.sh <project>       # 2. Ghidra GUI (enable GhidraMCPPlugin)
# 3. MCP clients connect through bridge_mcp_ghidra.py (started from .mcp.json)
```
