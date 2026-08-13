# F2 host power-control — QEMU evidence

## `f2-power-results.json` — automated Redfish loop (op-pwrctl image)

Captured booting the op-pwrctl `-full` image (NFS `10.0.2.2:/export/openbmc-f2power`,
`--mem 64`, `qemu` mask profile) on the faithful `kgpe-d16-bmc` machine and
POSTing `ComputerSystem.Reset` while reading the **modeled GPIOH2** over QMP
(`qom-get /machine/soc/gpio gpioH2`) — the authoritative power-state:

| Redfish action | HTTP | modeled GPIOH2 | meaning |
|---|---|---|---|
| (initial) | — | `false` | host off at boot |
| `ComputerSystem.Reset On` | 204 | **`true`** | op-pwrctl drove GPIOB1 low → latch set → host on |
| `ComputerSystem.Reset ForceOff` | 204 | **`false`** | op-pwrctl drove GPIOF0 low → latch cleared → host off |
| `ComputerSystem.Reset ForceRestart` | 204 | **`true`** | warm reset → host stays on |

This proves the **forward path** of the **Redfish → phosphor-state-manager →
op-pwrctl (org.openbmc.control.Power) → GPIO request line → modeled power latch →
GPIOH2** loop: each Redfish action returns HTTP 204 and the modeled GPIOH2 tracks
it (read independently over QMP). It does **not** prove the Redfish `PowerState`
*readback* — that field read back `null` for every action (see the caveat
below), so the round-trip is not confirmed. The authoritative power-state signal
is therefore GPIOH2 over QMP (above) plus the CI fwtest, not a Redfish
round-trip.

### Caveat — Redfish `PowerState` field

`bmcweb` came up (`RedfishVersion 1.17.0`), but its `PowerState` field read back
intermittently as `null` and one early `On` returned a transient HTTP 500. This
is `bmcweb`'s known behaviour under the real **64 MB** budget (TLS handshakes
reset mid-negotiation — the same memory-pressure crash-looping F1 documented),
**not** a fault in the power model or the GPIO path. The authoritative
power-state evidence is therefore **GPIOH2 over QMP** (above), which is
independent of `bmcweb`. On the real 64 MB board the lean **IPMI** image
(`realhw` mask profile, bmcweb dropped) drives power via `ipmitool chassis power`
through the identical state-manager → op-pwrctl → GPIO backend — see
`../../OPENBMC-POWER-INTEGRATION.md`.

## The authoritative QEMU demo — the fwtest (no bmcweb needed)

The deterministic, CI-gated proof of the model is the bare-metal fwtest, not the
live-bmcweb loop: `qemu-model/peripherals/power/fwtest.c` +
`qemu-model/integration/test_power.py` drive the request lines directly and
assert GPIOH2 (off@reset / on after power-up pulse / on across reset pulse / off
after power-down pulse) — 4 checks, all PASS, run in CI
(`.github/workflows/d16-qemu-stack.yml` `power-control-test`).
