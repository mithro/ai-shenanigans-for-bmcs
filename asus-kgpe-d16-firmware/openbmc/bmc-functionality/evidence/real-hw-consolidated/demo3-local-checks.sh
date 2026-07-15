#!/bin/sh
# Feature checks on the clean OpenBMC (power crash-loop masked in the export).
set +e
echo "==== uptime / load / mem ===="; uptime; free | grep -i mem
echo ""; echo "==== F5b: host-local IPMI over KCS (ipmitool -I open mc info) ===="
timeout 45 ipmitool -I open mc info 2>&1
echo ""; echo "==== F1: system-id (FRU device 0) ===="
timeout 45 ipmitool -I open fru print 0 2>&1
echo ""; echo "==== F3: sensors (SDR elist) ===="
timeout 75 ipmitool -I open sdr elist 2>&1
echo ""; echo "==== F2: chassis power status ===="
timeout 30 ipmitool -I open chassis status 2>&1
echo ""; echo "==== BMC state ===="
timeout 20 obmcutil state 2>&1
echo ""; echo "==== running phosphor services ===="
systemctl --no-pager --type=service --state=running | grep -iE 'ipmi|sensor|network|kcs|host|mapper|sol|console|bmc' | head -n 20
echo "==== DEMO-DONE ===="
