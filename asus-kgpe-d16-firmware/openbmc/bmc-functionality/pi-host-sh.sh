#!/bin/bash
# Runs ON the Pi: execute "$@" on the KGPE-D16 x86 host (SystemRescue,
# root/systemrescue, 192.168.77.138) over password ssh. Mirror of pi-bmc-sh.sh.
exec timeout -s KILL 60 sshpass -p systemrescue ssh -T \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 \
  -o PreferredAuthentications=password -o PubkeyAuthentication=no \
  root@192.168.77.138 "$@"
