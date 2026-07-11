# F-IMG2 QEMU demonstration evidence

The four image-recipe fixes (`asus-kgpe-d16-firmware/openbmc/recipes/`), rebuilt
into `obmc-phosphor-image-ast2050-full` and booted over NFS on the faithful
`kgpe-d16-bmc` QEMU machine (F3's W83795G-capable QEMU + g3vic kernel + a
vuart-enabled DTB, `--mem 256` so bmcweb + IPMI + sensors + entity-manager run
together — the fixes are image-config, orthogonal to the 64 MB per-feature RAM
masking F1-F5 established for real hardware). Captured by `../img2-demo.py`
(main run) and the SOL/FRU re-capture pass.

| Gap | Evidence file | Result |
|-----|---------------|--------|
| (a) SOL | `a-sol-config-object.txt` | settingsd owns `/xyz/openbmc_project/ipmi/sol/eth0` with the full `xyz.openbmc_project.Ipmi.SOL` property set; ObjectMapper resolves it |
| (a) SOL | `a-sol-info.txt` | `ipmitool -I lanplus sol info 1` rc=0 reads the config end-to-end (Enabled/Force*/Privilege ADMINISTRATOR/Retry Count 7/Payload Port 623) — was ResourceNotFound before |
| (a) SOL | `a-sol-activate.txt` | best-effort; `sol activate` intermittently hits netipmid's socket-activation RMCP+ RAKP race (F5's known issue), independent of the config-object fix |
| (b) SDR | `b-sdr-elist.txt`, `b-sdr-{voltage,fan,temperature}.txt` | all 18 KGPE-D16 rails with correct W83795G values: CPU_DIODE 41.9C, CPU0/1_DTS 45/46.5C, VCORE0/1 0.96V, P12V 11.97V, P5V 4.99V, P3V3 3.26V, P1V5 1.47V, P1V1 1.09V, P0V9 0.90V, VBAT 3.01V, FAN1-6 |
| (c) Redfish | `c-redfish-chassis.txt`, `c-redfish-chassis-member.txt` | `/redfish/v1/Chassis` -> 1 member `ASUS_KGPE_D16` (was empty); Manufacturer=ASUSTeK, Model=KGPE-D16, Part/Serial/AssetTag/ChassisType |
| (d) mc info | `d-mc-info.txt` | Manufacturer ID 2623 (ASUSTek Computer Inc.), Product ID 0x0d16, Additional Device Support Sensor/SDR/SEL/FRU/Chassis |
| (d) FRU | `d-fru-diagnostics.txt` | kgpe-d16-fru-populate.service Finished OK; `/system/chassis/motherboard` inventory populated (Manufacturer=ASUSTeK, PrettyName=KGPE-D16, Part/Serial) |
| (d) FRU | `d-fru-print-0.txt` | `ipmitool -I lanplus fru print 0` rc=0 -> Board Mfg "ASUSTeK Computer Inc.", Board Product "KGPE-D16", Board Serial KGPED16-OPENBMC-0001, Board Part 90-MSVDR0-G0UAY0Z (device 0 = the motherboard, via the 0x0 inventory-map mapping + Item.Present=true) |
| (d) FRU | `d-fru-print.txt` | full-enumeration `fru print` sometimes times out on netipmid's RMCP+ race (F5); `fru print 0` is the clean per-device capture above |

## Notes

- `sol activate` fully opening the console additionally needs a live host serial
  peer on the VUART; the config-object fix (the F4-identified gap) is proven by
  `sol info` reading the object end-to-end + the `busctl` object dump.
- All fixes are also present at the file/binary level in the staged rootfs:
  settingsd references `ipmi/sol/eth0` (11x), `libipmi20.so` contains `VCORE0`,
  `dev_id.json` carries the ASUS IDs, the EM `kgpe-d16.json` + hwmon `hwmon@2f.conf`
  + FRU blob/service are installed.
