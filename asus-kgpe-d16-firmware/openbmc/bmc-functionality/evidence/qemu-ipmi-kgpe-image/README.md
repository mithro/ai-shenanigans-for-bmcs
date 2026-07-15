# QEMU IPMI-over-LAN with POPULATED IDs on the kgpe-d16 image (2026-07-16)

Closes the completion audit's one soft-spot for #7 (IPMI): on the GENERIC published
asset (openbmc-full / quanta-q71l) `mc info` over LAN answered rc=0 but with all-zero
identity. On the **kgpe-d16 image** (local `openbmc-img2`, built with the dev_id/FRU
recipes) the QEMU IPMI-over-LAN reports the SAME populated identity as real silicon:

  Manufacturer ID   : 2623   (ASUSTek Computer Inc.)
  Product ID        : 3350 (0x0d16)
  FRU Board Mfg     : ASUSTeK Computer Inc.
  FRU Board Product : KGPE-D16

So #7's QEMU side fully matches silicon once the correct (kgpe-d16) image is used;
the generic-asset zeros were an artifact of the CI test-asset being the generic
machine (see evidence/qemu-sensors/ci-full-asset/README.md), which the recipe-sync
wiring into build-openbmc-rootfs.yml addresses for the next asset build.

## Also fixed here: RMCP+ RAKP robustness
This run initially FAILED: netipmid's RMCP+ RAKP handshake is slow under the 256 MB
QEMU load, so ipmitool's default 1 s/4-retry gave up ("no response from RAKP 1
message") intermittently -> `mc info` (the F5 gate) failed. Adding `-N 5 -R 3` (5 s
per-message timeout, 3 retries) to f5-ipmi-test.py + f4-sol-test.py made auth
reliable -> F5 RESULT: PASS. This is the documented RAKP-slowness workaround, now in
the test harness so the LAN IPMI/SOL tests don't flake in CI.
