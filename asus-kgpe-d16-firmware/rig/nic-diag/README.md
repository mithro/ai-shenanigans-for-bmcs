# NIC diagnostic tools (P2A register + TX-ring dumps)

Rig-specific helpers used to diagnose the modern-kernel ftgmac100 RMII-TX failure on the
real AST2050 (see `../../NIC-MAC-REGISTER-COMPARISON.md`). They read MAC/SCU registers and
the TX descriptor ring over **P2A** (culvert on the diskless host) via the ASUS Pi bridge.

- `mac_block_host.py` / `run_mac_block.py` — dump the ftgmac100 MAC register block + the
  MAC-relevant SCU registers. `run_*` pushes the `*_host.py` to the host (base64) and runs it.
- `tx_ring_host.py` / `run_tx_ring.py` — read `TXR_BADR` and decode the TX descriptor ring
  (txdes0 OWN bit / FTS / LTS / EDOTR / len, txdes3 buffer address).

Hardcoded for this rig: Pi `asus-bmc`, diskless host `192.168.77.138` (user
`root`/`systemrescue`), culvert at `/root/culvert-g3/build/src/culvert`. Run from the
worktree root: `uv run asus-kgpe-d16-firmware/rig/nic-diag/run_mac_block.py`.

**Capture timing matters**: capture *after* Linux fully boots (in the `ip_auto_config`
carrier wait), NOT during U-Boot's tftp — otherwise you read U-Boot's ring
(`TXR_BADR=0x43fe9760`, 1 descriptor) and mistake it for Linux's.
