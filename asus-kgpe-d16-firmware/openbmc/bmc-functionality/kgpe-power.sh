#!/bin/sh
# KGPE-D16 (AST2050) host power control over sysfs GPIO — the asus_power.sh
# request-line sequences (HW-WIRING-power-sensors.md §1.2), driving the AST2050
# GPIO through the real Linux gpio-aspeed driver. On the faithful QEMU machine
# these writes reach the modeled board power-sequencer (aspeed_gpio_kgpe_d16_
# pwrseq), which latches the host-power state and feeds it back on GPIOH2.
#
# Usage: kgpe-power.sh {init|on|off|reset|status}
# Active-low request lines: B1 power-up, F0 power-down, B6 reset; H2 = 1 -> on.
set -eu

# Resolve the aspeed GPIO controller's sysfs base (label "1e780000.gpio").
BASE=""
for c in /sys/class/gpio/gpiochip*; do
	if [ -r "$c/label" ] && grep -q "1e780000.gpio" "$c/label"; then
		BASE=$(cat "$c/base")
		break
	fi
done
if [ -z "$BASE" ]; then
	echo "kgpe-power: no aspeed (1e780000.gpio) gpiochip found" >&2
	exit 1
fi

# Line = base + bank*8 + pin. B=1, F=5, H=7.
B1=$((BASE + 1 * 8 + 1))   # GPIOB1 CTL_REQ_POWERUP_N
F0=$((BASE + 5 * 8 + 0))   # GPIOF0 CTL_REQ_POWERDOWN_N
B6=$((BASE + 1 * 8 + 6))   # GPIOB6 CTL_REQ_RESET_N
H2=$((BASE + 7 * 8 + 2))   # GPIOH2 STA_LINE_POWER (input, 1=on)

_exp() { [ -d "/sys/class/gpio/gpio$1" ] || echo "$1" > /sys/class/gpio/export; }
_dir() { echo "$2" > "/sys/class/gpio/gpio$1/direction"; }
_val() { echo "$2" > "/sys/class/gpio/gpio$1/value"; }
_get() { cat "/sys/class/gpio/gpio$1/value"; }

_exp "$B1"; _exp "$F0"; _exp "$B6"; _exp "$H2"
_dir "$B1" out; _dir "$F0" out; _dir "$B6" out; _dir "$H2" in

case "${1:-status}" in
	init)  _val "$B1" 1; _val "$F0" 1; _val "$B6" 1 ;;               # all de-asserted
	on)    _val "$F0" 1; _val "$B6" 0; _val "$B1" 0
	       sleep 1;      _val "$B6" 1; _val "$B1" 1 ;;               # engage power
	off)   _val "$B6" 1; _val "$B1" 1; _val "$F0" 0
	       sleep 1;      _val "$F0" 1 ;;                             # force off
	reset) _val "$F0" 1; _val "$B6" 0; _val "$B1" 1
	       sleep 1;      _val "$B6" 1 ;;                             # warm reset (stays on)
	status) : ;;
	*) echo "usage: $0 {init|on|off|reset|status}" >&2; exit 2 ;;
esac

echo "POWER_STATE(GPIOH2)=$(_get "$H2")"
