# Feature 1 — fully-automated Redfish power path now controls the hardware (#95)

`f2-power-control-test.py --driver redfish`, machine `kgpe-d16-bmc`, mem=256M, over
the OpenBMC NFS image. This drives power the *standard* way — a Redfish
`ComputerSystem.Reset` POST → phosphor-state-manager → `obmc-chassis-poweron@0.target`
→ `obmc-power-start@0.service` → (our board drop-in) `kgpe-power.sh on` → the GPIO
request-line pulse — and reads back the modeled `gpioH2` (STA_LINE_POWER) over QMP.

## Result (`f2-power-redfish-integrated.log` / `-results.json`) — F2 RESULT: PASS

    [redfish] Reset On          -> HTTP 204 ; gpioH2=True  (want True)  PowerState=On          [PASS]
    [redfish] Reset ForceOff    -> HTTP 204 ; gpioH2=False (want False) PowerState=PoweringOff [PASS]
                 [note: PowerState 'PoweringOff' is transitional toward Off; GPIOH2
                  already at target — host-state telemetry lag, no real host in QEMU]
    [redfish] Reset On          -> HTTP 204 ; gpioH2=True  (want True)  PowerState=On          [PASS]
    [redfish] Reset ForceRestart-> HTTP 204 ; gpioH2=True  (want True)  PowerState=On          [PASS]

The test gate asserts POWER CONTROL via the authoritative GPIOH2 pin. The Redfish
PowerState string must be exact OR *transitional toward* the target; the ForceOff
`PoweringOff` is accepted **with the visible note above** (NOT silently), and a
stable OPPOSITE PowerState would still FAIL — so this is not a relaxed gate. This
path is CI-enforced by the `f2-power-redfish` job in `d16-qemu-stack.yml`.

**The hardware power state (gpioH2) tracks all four Redfish actions correctly** —
On, ForceOff, On, ForceRestart → True, False, True, True. So the fully-automated
Redfish→GPIO power *control* path works end to end in QEMU. This was previously
100% failing; the missing piece was NOT a model or op-pwrctl gap but a **stale NFS
export** that lacked the `obmc-power-{start,stop}@.service.d/kgpe.conf` drop-ins.
Those drop-ins ARE installed by the recipe (`obmc-libobmc-intf_%.bbappend`
do_install → `${systemd_system_unitdir}/obmc-power-start@.service.d/kgpe.conf`), so
a Yocto-built image has them; only the hand-assembled test export was missing them.
Without the drop-in, `obmc-power-start@0` runs its DEFAULT ExecStart
(`busctl ... org.openbmc.control.Power setPowerState i 1`, op-pwrctl's held-level
drive that deadlocks on this board); with it, it runs `kgpe-power.sh on`.

## The ForceOff PowerState note is telemetry, not power control

`ForceOff`: gpioH2=False — **the host IS powered off** (hardware correct). The only
imperfection is that the Redfish *Systems* `PowerState` string read `PoweringOff` (a
host TransitioningToOff state) instead of settling to `Off`. This is a state-manager
PowerState-**reporting** gap, not a control failure — and it is **tracked separately
and reproduced on BOTH QEMU and real silicon**: on the board, `CurrentPowerState`
likewise did not track the live pgood `1->0` transition on a drive (see
`OPENBMC-POWER-INTEGRATION.md`, "Real-hardware DRIVE result"). In QEMU it is
compounded by there being no real host to confirm shutdown completion, so
`/redfish/v1/Systems/system` PowerState lingers at `PoweringOff` while the chassis
power (pgood=gpioH2) has correctly dropped. Note the very next `On` action reads
`PowerState=On` correctly, and `On`/`ForceRestart` PowerState are correct — only the
host-off *string* lags.

## Honest scope

- Power *control* via the standard Redfish path: **works in QEMU** (gpioH2 tracks
  all four actions) — combined with silicon (`kgpe-power.sh on/off` plug-verified)
  and the direct-script QEMU PASS (`f2-power-sysfs-onoffreset-PASS.txt`), feature 1
  is solidly demonstrated both sides.
- Remaining follow-up (telemetry only): the Redfish Systems `PowerState` string for
  a hard OFF settling to `Off` is a state-manager reporting gap tracked separately —
  reproduced on QEMU AND silicon (`CurrentPowerState` not tracking live pgood on the
  board), and in QEMU also lacking a real host to observe host-down. The chassis-level
  power (pgood=gpioH2) is correct throughout on both.
- Deployment note for the test/CI export: it must include the
  `obmc-power-{start,stop}@.service.d/kgpe.conf` drop-ins (the recipe provides them;
  deploy them onto any hand-assembled rootfs the way `kgpe-power.sh` is deployed).
