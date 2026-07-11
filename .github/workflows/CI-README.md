# CI — the OpenBMC fuller-rootfs test jobs and how to feed them

The `d16-qemu-stack.yml` workflow proves the AST2050 firmware stack in QEMU. Most
jobs build everything they need from source in-CI. Three jobs are different: they
boot the **fuller OpenBMC image** (`obmc-phosphor-image-ast2050-full`) over NFS
and drive a real client against it —

| Job | Proves |
|-----|--------|
| `f5-ipmi-lan` | **IPMI over LAN (RMCP+)** — the one capability proven on real silicon; `ipmitool -I lanplus` runs the full command suite. |
| `f4-sol` | **Serial-over-LAN** on the AST2050 VUART. |
| `fw-update` | **Firmware-update surface** (Redfish `UpdateService` + IPMI `mc info`), no real flash write. |

## Why the rootfs is not built in-CI

The fuller image is a multi-hour Yocto/bitbake build (`quanta-q71l`, ARMv5TE)
producing a ~20-22 MB `squashfs-xz` (~82 MB unpacked). That build does **not** fit
a stock GitHub-hosted runner (disk/RAM/time). See
`asus-kgpe-d16-firmware/openbmc/bmc-functionality/BUILD-NOTES.md` for the recipe
and `IMG2-STAGING.md` for the staging details.

So the expensive build is **decoupled** from the per-push test runs: the rootfs is
published once (out-of-band) as a durable **GitHub Release asset**, and the three
test jobs fetch it on every push/PR.

- Release tag: **`openbmc-rootfs`**
- Asset name: **`openbmc-full-rootfs.tar`** — a tar of the *staged* rootfs tree
  (unsquashed + MTD/UBI overlay units neutralised by
  `qemu-firmware/scripts/stage-openbmc-nfsroot.sh`), whose members are `./usr`,
  `./etc`, … so the jobs untar it straight into `/export/openbmc-full`.

Both the tag and the asset name are set once in `d16-qemu-stack.yml`
(`OBMC_ROOTFS_RELEASE` / `OBMC_ROOTFS_ASSET`).

## Run vs. skip — the jobs are honest, never a silent green

Each of the three jobs starts with a `Fetch the published OpenBMC fuller rootfs`
step (`id: rootfs`) that runs `gh release download openbmc-rootfs …`:

- **Asset present →** `available=true`; a `::notice::` says the test is RUNNING,
  and every following step (`if: steps.rootfs.outputs.available == 'true'`) runs:
  build QEMU, export the rootfs over NFS, boot, drive the client, upload evidence.
- **Asset absent →** `available=false`; the job emits a **`::warning::`
  annotation** *and* a `$GITHUB_STEP_SUMMARY` block naming the missing asset and
  pointing here, then all test steps are skipped. The job goes green **but with a
  visible SKIPPED warning in the run summary** — it never fakes a pass and never
  silently passes.

This means: the moment the rootfs asset is published, the IPMI-over-LAN / SOL /
fw-update tests start running automatically on every push — no workflow edit
needed.

## Publishing / refreshing the rootfs (the one manual step)

### Option A — the publish workflow (self-hosted builder)

`build-openbmc-rootfs.yml` (`workflow_dispatch`) runs on a **self-hosted runner**
labeled `openbmc-builder`, registered on the faithful build machine where the
OpenBMC tree lives (e.g. `/home/tim/openbmc`). It bitbakes the image (or takes a
pre-built `squashfs_path` input), stages + tars it, and uploads
`openbmc-full-rootfs.tar` to the `openbmc-rootfs` release (creating the release on
first run, `--clobber`ing thereafter).

```
Actions → "Publish OpenBMC fuller rootfs" → Run workflow
  squashfs_path: (blank to bitbake, or a path to a pre-built .squashfs-xz)
  openbmc_tree:  /home/tim/openbmc
  release_tag:   openbmc-rootfs
```

### Option B — manual publish (no self-hosted runner needed)

Build/stage the rootfs locally per `BUILD-NOTES.md`, then publish with the `gh`
CLI from the build machine:

```sh
# 1. build (memory-capped) — see BUILD-NOTES.md
cd /home/tim/openbmc
. setup quanta-q71l build/quanta-q71l
systemd-run --user --scope -p MemoryMax=20G -p MemoryHigh=18G \
    nice -n 15 ionice -c3 bitbake obmc-phosphor-image-ast2050-full

# 2. stage (unsquash + neutralise MTD units) and tar the tree
SQUASHFS=build/quanta-q71l/tmp/deploy/images/quanta-q71l/obmc-phosphor-image-ast2050-full-quanta-q71l.squashfs-xz
asus-kgpe-d16-firmware/qemu-firmware/scripts/stage-openbmc-nfsroot.sh "$SQUASHFS" /tmp/openbmc-full
sudo tar -C /tmp/openbmc-full -cf openbmc-full-rootfs.tar .

# 3. publish (first time creates the release; later refreshes clobber the asset)
REPO=mithro/ai-shenanigans-for-bmcs
gh release view openbmc-rootfs --repo "$REPO" \
  && gh release upload openbmc-rootfs openbmc-full-rootfs.tar --repo "$REPO" --clobber \
  || gh release create openbmc-rootfs openbmc-full-rootfs.tar --repo "$REPO" \
       --title "OpenBMC fuller rootfs (ast2050-full)" \
       --notes "Consumed by f5-ipmi-lan / f4-sol / fw-update in d16-qemu-stack.yml."
```

Refresh the asset whenever the OpenBMC image recipe changes
(`asus-kgpe-d16-firmware/openbmc/recipes/…`) so the CI tests exercise the current
image. There is no schedule wired (a self-hosted build machine may not always be
registered); refresh on recipe changes, or add a `schedule:` to
`build-openbmc-rootfs.yml` if you keep a persistent builder.
