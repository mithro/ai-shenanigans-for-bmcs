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
# fails at the PSU while force-OFF works.  `a4` reclaims A4 (clears SCU74[25]) and
# drives it high; on/off/reset re-assert it and pulse the request lines.  eth0 is
# unaffected (the ftgmac100 polls the RTL8201CP over MDIO, irq=POLL, not PHYLINK).
#
# GPIO OWNERSHIP: op-pwrctl (org.openbmc.control.Power) is kept only to READ pgood
# (GPIOH2) and claims B1/F0/B6/H2 via libgpiod. This script therefore:
#   * `a4`/`init`  reclaim + drive A4 ONLY (A4 is not used by op-pwrctl), so
#     op-pwrctl still owns B1/F0/B6/H2 for its pgood read;
#   * `on`/`off`/`reset` are invoked by the obmc-power-{start,stop}@ drop-ins,
#     which STOP op-pwrctl first (releasing B1/F0/B6) and restart it after;
#   * H2 is read via devmem (non-exclusive), never sysfs, so a `status` never
#     collides with op-pwrctl's claim on GPIOH2.
#
# Usage: kgpe-power.sh {a4|init|on|off|reset|status}
# Active-low request lines: B1 power-up, F0 power-down, B6 reset; H2 = 1 -> on.
set -eu

SCU_KEY=0x1e6e2000     # SCU protection key register (write 0x1688A8A8 to unlock)
SCU74=0x1e6e2074       # multi-function pin control #5 (bit25 = GPIOA4 / PHYLINK)
GPIO00=0x1E780000      # GPIO data,      banks A-D (GPIOA4 = bit 4)
GPIO04=0x1E780004      # GPIO direction, banks A-D
GPIO20=0x1E780020      # GPIO data, banks E-H (GPIOH2 = bit 26 = STA_LINE_POWER)

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

_exp()   { [ -d "/sys/class/gpio/gpio$1" ] || echo "$1" > /sys/class/gpio/export; }
_unexp() { [ -d "/sys/class/gpio/gpio$1" ] && echo "$1" > /sys/class/gpio/unexport || true; }
_dir()   { echo "$2" > "/sys/class/gpio/gpio$1/direction"; }
_val()   { echo "$2" > "/sys/class/gpio/gpio$1/value"; }
_h2()    { echo $(( ( $(devmem $GPIO20) >> 26 ) & 1 )); }   # STA_LINE_POWER via devmem

# Release the request lines back to op-pwrctl (which claims B1/F0/B6/H2 for its
# pgood read). A4 stays owned by us — op-pwrctl does not use it.
release_lines() { _unexp "$B1"; _unexp "$F0"; _unexp "$B6"; }

# Reclaim GPIOA4 from its PHYLINK alt-function so it is a drivable GPIO, and drive
# it high (BMC in control). Best-effort: skipped where devmem is absent (e.g. the
# modeled default already has A4 as GPIO).
setup_a4() {
	if command -v devmem >/dev/null; then
		devmem "$SCU_KEY" 32 0x1688A8A8                 # unlock SCU
		s=$(devmem "$SCU74")
		devmem "$SCU74" 32 $(( s & ~0x02000000 ))       # clear bit25 (PHYLINK) -> GPIO
		# Drive A4 out+high via DEVMEM, not sysfs: clearing SCU74[25] with devmem
		# does NOT update the kernel pinctrl view, so a sysfs `gpio export` of A4
		# fails wherever the pad's pinctrl still claims A4 for PHYLINK (observed in
		# the faithful QEMU model -- A4 never reached the modeled GPIO latch, so
		# power-ON silently never engaged; hardware-verified fix). devmem writes the
		# banks-A-D direction+data registers directly, reaching the pin on both
		# silicon and QEMU regardless of pinctrl.
		d=$(devmem "$GPIO04"); devmem "$GPIO04" 32 $(( d | 0x10 ))   # A4 (bit4) -> output
		v=$(devmem "$GPIO00"); devmem "$GPIO00" 32 $(( v | 0x10 ))   # A4 (bit4) -> high
	else
		_exp "$A4"; _dir "$A4" out; _val "$A4" 1        # fallback: sysfs (no devmem)
	fi
}

# Claim + de-assert the three request lines (call only when op-pwrctl is stopped).
setup_lines() {
	_exp "$B1"; _exp "$F0"; _exp "$B6"
	_dir "$B1" out; _dir "$F0" out; _dir "$B6" out
	_val "$B1" 1; _val "$F0" 1; _val "$B6" 1            # all de-asserted
}

case "${1:-status}" in
	a4|init) setup_a4 ;;                                # reclaim + drive A4 only
	on)    setup_a4; setup_lines
	       _val "$F0" 1; _val "$B6" 0; _val "$B1" 0
	       sleep 1;      _val "$B6" 1; _val "$B1" 1      # engage power (reset+power-up pulse)
	       release_lines ;;
	off)   setup_a4; setup_lines
	       _val "$B6" 1; _val "$B1" 1; _val "$F0" 0
	       sleep 1;      _val "$F0" 1                    # force off (power-down pulse)
	       release_lines ;;
	reset) setup_a4; setup_lines
	       _val "$F0" 1; _val "$B6" 0; _val "$B1" 1
	       sleep 1;      _val "$B6" 1                    # warm reset (reset pulse, stays on)
	       release_lines ;;
	status) : ;;
	*) echo "usage: $0 {a4|init|on|off|reset|status}" >&2; exit 2 ;;
esac

echo "POWER_STATE(GPIOH2)=$(_h2)"
