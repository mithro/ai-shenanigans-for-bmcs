#!/bin/sh
# KGPE-D16 (AST2050) host power control over sysfs GPIO — the asus_power.sh
# request-line PULSE sequences (HW-WIRING-power-sensors.md §1.2) PLUS the
# BMC-control-lockout (GPIOA4) reclaim the board REQUIRES for power-ON.
#
# *** Hardware-verified 2026-07-13 (real AST2050). ***  The board grants the BMC
# force-OFF (CTL_REQ_POWERDOWN_N / GPIOF0) unconditionally, but only honors the
# BMC power-ON request (CTL_REQ_POWERUP_N / GPIOB1) when the control-lockout line
# ASUS_BMC_CTL_LOCKOUT_N (GPIOA4) is a real GPIO output driven HIGH (=1, "BMC in
# control").  GPIOA4's pad defaults to the PHYLINK alternate function
# (SCU74[25]=1), so a stock image leaves it un-controllable and power-ON silently
# fails at the PSU while force-OFF works.  `setup` reclaims A4 (clears SCU74[25])
# and drives it high before every power op.  eth0 is unaffected — the ftgmac100
# polls the RTL8201CP over MDIO (irq=POLL), not the PHYLINK pin.  On the faithful
# QEMU machine the same writes reach the modeled sequencer (the SCU74[25] clear is
# a harmless no-op there); the modeled latch keys on the B1/F0 assertion.
#
# Usage: kgpe-power.sh {init|on|off|reset|status}
# Active-low request lines: B1 power-up, F0 power-down, B6 reset; H2 = 1 -> on.
set -eu

SCU_KEY=0x1e6e2000     # SCU protection key register (write 0x1688A8A8 to unlock)
SCU74=0x1e6e2074       # multi-function pin control #5 (bit25 = GPIOA4 / PHYLINK)

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

# Line = base + bank*8 + pin. A=0, B=1, F=5, H=7.
A4=$((BASE + 0 * 8 + 4))   # GPIOA4 ASUS_BMC_CTL_LOCKOUT_N (out, 1 = BMC in control)
B1=$((BASE + 1 * 8 + 1))   # GPIOB1 CTL_REQ_POWERUP_N
F0=$((BASE + 5 * 8 + 0))   # GPIOF0 CTL_REQ_POWERDOWN_N
B6=$((BASE + 1 * 8 + 6))   # GPIOB6 CTL_REQ_RESET_N
H2=$((BASE + 7 * 8 + 2))   # GPIOH2 STA_LINE_POWER (input, 1=on)

_exp() { [ -d "/sys/class/gpio/gpio$1" ] || echo "$1" > /sys/class/gpio/export; }
_dir() { echo "$2" > "/sys/class/gpio/gpio$1/direction"; }
_val() { echo "$2" > "/sys/class/gpio/gpio$1/value"; }
_get() { cat "/sys/class/gpio/gpio$1/value"; }

# Reclaim GPIOA4 from its PHYLINK alt-function so it is a drivable GPIO. Needs the
# SCU unlocked first. Best-effort: on platforms without devmem this is skipped and
# the modeled/other-board default (A4 already GPIO) applies.
reclaim_a4() {
	command -v devmem >/dev/null || return 0
	devmem "$SCU_KEY" 32 0x1688A8A8
	s=$(devmem "$SCU74")
	devmem "$SCU74" 32 $(( s & ~0x02000000 ))   # clear bit25 (PHYLINK) -> GPIO
}

setup() {
	reclaim_a4
	_exp "$A4"; _exp "$B1"; _exp "$F0"; _exp "$B6"; _exp "$H2"
	_dir "$A4" out; _val "$A4" 1                 # BMC in control (lockout de-asserted)
	_dir "$B1" out; _dir "$F0" out; _dir "$B6" out; _dir "$H2" in
	_val "$B1" 1; _val "$F0" 1; _val "$B6" 1      # all request lines de-asserted
}

case "${1:-status}" in
	init)  setup ;;
	on)    setup
	       _val "$F0" 1; _val "$B6" 0; _val "$B1" 0
	       sleep 1;      _val "$B6" 1; _val "$B1" 1 ;;   # engage power (reset+power-up pulse)
	off)   setup
	       _val "$B6" 1; _val "$B1" 1; _val "$F0" 0
	       sleep 1;      _val "$F0" 1 ;;                 # force off (power-down pulse)
	reset) setup
	       _val "$F0" 1; _val "$B6" 0; _val "$B1" 1
	       sleep 1;      _val "$B6" 1 ;;                 # warm reset (reset pulse, stays on)
	status) _exp "$H2"; _dir "$H2" in ;;
	*) echo "usage: $0 {init|on|off|reset|status}" >&2; exit 2 ;;
esac

echo "POWER_STATE(GPIOH2)=$(_get "$H2")"
