#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyserial>=3.5",
#   "requests>=2.28",
# ]
# ///
"""TFTP boot a Dell C410X BMC via U-Boot over serial.

Automates the full boot sequence:
  1. Power cycle via Tasmota smart plug
  2. Interrupt U-Boot autoboot
  3. Configure DHCP + TFTP boot
  4. Optionally deploy dnsmasq override to TFTP server
  5. Drop into interactive serial console

The Dell C410X BMC runs an Aspeed AST2050 with U-Boot 1.2.0 (Avocent).
It uses legacy uImage format and has bootdelay=1 with autoload=n.

Usage:
    uv run tftp_boot.py --tasmota-host au-plug-1.iot.welland.mithis.com \\
        --kernel uImage-ast2050

    uv run tftp_boot.py --no-power-cycle --kernel uImage-ast2050 \\
        --initrd initrd-ast2050 --setup-dnsmasq
"""

from __future__ import annotations

import argparse
import os
import re
import select
import subprocess
import sys
import termios
import time
import tty
from typing import Optional

import requests
import serial

# ---------------------------------------------------------------------------
# Known C410X BMC units (MAC → hostname, IP)
# These are registered in dnsmasq on ten64.welland via gdoc2netcfg.
# ---------------------------------------------------------------------------
KNOWN_C410X_UNITS = {
    "1c:6f:65:ec:f0:b1": {"name": "dell-c410x-1", "ip": "10.1.5.80"},
    "50:e5:49:2f:96:0c": {"name": "dell-c410x-2", "ip": "10.1.5.81"},
    "1c:6f:65:ea:fb:da": {"name": "dell-c410x-3", "ip": "10.1.5.82"},
}

# U-Boot prompt patterns (AST2050 EVB convention)
UBOOT_PROMPTS = [b"ast2050evb>", b"=> ", b"> "]

# Error patterns in U-Boot output
UBOOT_ERRORS = [b"ERROR", b"error", b"Retry count exceeded", b"T T T", b"not found"]

# Default addresses from U-Boot environment
DEFAULT_KERNEL_ADDR = "0x41400000"
DEFAULT_INITRD_ADDR = "0x42600000"
DEFAULT_TFTP_SERVER = "10.1.5.1"
DNSMASQ_HOST = "ten64.welland.mithis.com"
DNSMASQ_OVERRIDE_PATH = "/etc/dnsmasq.d/internal/override-dell-c410x-tftp.conf"


# ---------------------------------------------------------------------------
# Tasmota power control
# ---------------------------------------------------------------------------

def tasmota_command(host: str, command: str) -> dict:
    """Send a command to a Tasmota device via its HTTP API.

    Args:
        host: Tasmota device hostname or IP.
        command: Tasmota command string (e.g. "Power Off").

    Returns:
        JSON response from the device.
    """
    url = f"http://{host}/cm?cmnd={command}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def power_cycle(host: str, off_time: float = 5.0) -> None:
    """Power cycle a device via its Tasmota smart plug.

    Args:
        host: Tasmota plug hostname.
        off_time: Seconds to keep power off before turning back on.
    """
    print(f"[tasmota] Powering OFF via {host}")
    result = tasmota_command(host, "Power Off")
    print(f"[tasmota]   Response: {result}")

    print(f"[tasmota] Waiting {off_time:.0f}s with power off...")
    time.sleep(off_time)

    print(f"[tasmota] Powering ON via {host}")
    result = tasmota_command(host, "Power On")
    print(f"[tasmota]   Response: {result}")


# ---------------------------------------------------------------------------
# Serial port helpers
# ---------------------------------------------------------------------------

def open_serial(port: str, baudrate: int = 115200) -> serial.Serial:
    """Open a serial port with standard BMC settings (8N1)."""
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,  # Non-blocking reads with short timeout
    )
    return ser


def read_until_prompt(
    ser: serial.Serial,
    prompts: list[bytes],
    timeout: float = 60.0,
    error_patterns: Optional[list[bytes]] = None,
) -> tuple[bytes, bool]:
    """Read serial data until a prompt pattern is detected or timeout.

    All received data is printed to stdout in real-time.

    Args:
        ser: Open serial port.
        prompts: List of byte patterns indicating the prompt was reached.
        timeout: Maximum seconds to wait.
        error_patterns: Optional patterns that indicate an error occurred.

    Returns:
        Tuple of (all_data_received, prompt_found).
    """
    buf = b""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            # Print to stdout in real-time
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

            # Check for prompt
            for prompt in prompts:
                if prompt in buf[-(len(prompt) + 80):]:
                    return buf, True

            # Check for errors (warn but don't stop)
            if error_patterns:
                for pattern in error_patterns:
                    if pattern in chunk:
                        print(f"\n[warning] Detected error pattern: {pattern!r}",
                              file=sys.stderr)
    return buf, False


def send_command(
    ser: serial.Serial,
    command: str,
    timeout: float = 30.0,
    expect_prompt: bool = True,
) -> tuple[bytes, bool]:
    """Send a command to U-Boot and wait for the prompt.

    Args:
        ser: Open serial port.
        command: Command string to send (newline appended automatically).
        timeout: Maximum seconds to wait for prompt after sending.
        expect_prompt: If True, wait for U-Boot prompt after command.

    Returns:
        Tuple of (output_data, prompt_found).
    """
    print(f"\n[uboot] >>> {command}")
    ser.write(f"{command}\n".encode())
    ser.flush()

    if expect_prompt:
        return read_until_prompt(
            ser, UBOOT_PROMPTS, timeout=timeout, error_patterns=UBOOT_ERRORS
        )
    return b"", True


def interrupt_autoboot(ser: serial.Serial, timeout: float = 30.0) -> Optional[bytes]:
    """Interrupt U-Boot autoboot by sending space characters.

    The C410X has bootdelay=1, so we need aggressive timing.
    Sends space every 100ms while watching for the U-Boot prompt.

    Args:
        ser: Open serial port.
        timeout: Maximum seconds to wait for U-Boot prompt.

    Returns:
        All captured boot output if U-Boot prompt was detected, None on timeout.
    """
    print("[uboot] Sending interrupt characters to catch autoboot...")
    buf = b""
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        # Send space to interrupt autoboot
        ser.write(b" ")
        ser.flush()

        # Read any available data
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()

            # Check for U-Boot prompt
            for prompt in UBOOT_PROMPTS:
                if prompt in buf[-(len(prompt) + 80):]:
                    print("\n[uboot] Got U-Boot prompt!")
                    return buf

        # Brief pause between interrupt attempts
        time.sleep(0.1)

    print("\n[uboot] Timeout waiting for U-Boot prompt!", file=sys.stderr)
    return None


def extract_mac_from_output(data: bytes) -> Optional[str]:
    """Extract a MAC address from U-Boot serial output.

    Looks for patterns like:
      MAC: xx:xx:xx:xx:xx:xx
      ethaddr=xx:xx:xx:xx:xx:xx
      MAC Address xx:xx:xx:xx:xx:xx

    Args:
        data: Raw serial output bytes.

    Returns:
        Lowercase MAC address string, or None if not found.
    """
    text = data.decode("ascii", errors="replace")
    # Match MAC address patterns (xx:xx:xx:xx:xx:xx)
    mac_re = re.compile(
        r"(?:MAC[: ]+|ethaddr=)"
        r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})"
    )
    match = mac_re.search(text)
    if match:
        return match.group(1).lower()

    # Fallback: find any standalone MAC in the output
    any_mac = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")
    # Skip the well-known default MAC
    for m in any_mac.finditer(text):
        mac = m.group(1).lower()
        if mac not in ("00:c0:a8:12:34:56", "00:c0:a8:12:34:57"):
            return mac

    return None


# ---------------------------------------------------------------------------
# dnsmasq override deployment
# ---------------------------------------------------------------------------

def generate_dnsmasq_override(boot_filename: str, tftp_server: str) -> str:
    """Generate dnsmasq override config for C410X TFTP boot.

    Args:
        boot_filename: Kernel filename to advertise via DHCP.
        tftp_server: TFTP server IP address.

    Returns:
        Config file contents as a string.
    """
    lines = [
        "# Dell C410X BMC TFTP boot override",
        "# Auto-generated by tftp_boot.py",
        "#",
        "# Tags C410X BMC MACs for TFTP boot parameters.",
        "# IP assignments are handled by the generated configs from gdoc2netcfg.",
        "",
    ]

    # Tag each known C410X BMC MAC
    for mac, info in sorted(KNOWN_C410X_UNITS.items()):
        lines.append(f"# {info['name']} ({info['ip']})")
        lines.append(f"dhcp-host={mac},set:c410x-bmc")

    lines.extend([
        "",
        "# TFTP boot parameters for tagged hosts",
        f"dhcp-boot=tag:c410x-bmc,{boot_filename},{tftp_server},{tftp_server}",
        f'dhcp-option=tag:c410x-bmc,option:tftp-server-name,"{tftp_server}"',
        "",
    ])

    return "\n".join(lines) + "\n"


def deploy_dnsmasq_override(
    boot_filename: str,
    tftp_server: str,
    dnsmasq_host: str = DNSMASQ_HOST,
) -> None:
    """Deploy dnsmasq override config to the TFTP server via SSH.

    Writes the override config and reloads dnsmasq.

    Args:
        boot_filename: Kernel filename to advertise.
        tftp_server: TFTP server IP address.
        dnsmasq_host: Hostname of the dnsmasq server.
    """
    config = generate_dnsmasq_override(boot_filename, tftp_server)
    print(f"[dnsmasq] Deploying override to {dnsmasq_host}:{DNSMASQ_OVERRIDE_PATH}")
    print(f"[dnsmasq] Config contents:")
    for line in config.splitlines():
        print(f"[dnsmasq]   {line}")

    # Write config via SSH (using sudo tee for write permissions)
    proc = subprocess.run(
        [
            "ssh", dnsmasq_host,
            f"sudo tee {DNSMASQ_OVERRIDE_PATH}",
        ],
        input=config.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        print(f"[dnsmasq] ERROR writing config: {proc.stderr.decode()}", file=sys.stderr)
        sys.exit(1)
    print("[dnsmasq] Config written successfully")

    # Reload dnsmasq to pick up the new config
    print("[dnsmasq] Reloading dnsmasq service...")
    proc = subprocess.run(
        ["ssh", dnsmasq_host, "sudo systemctl reload dnsmasq@internal"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # Try alternative service name
        print(f"[dnsmasq] dnsmasq@internal reload failed, trying dnsmasq...")
        proc = subprocess.run(
            ["ssh", dnsmasq_host, "sudo systemctl reload dnsmasq"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"[dnsmasq] ERROR reloading: {proc.stderr}", file=sys.stderr)
            sys.exit(1)
    print("[dnsmasq] Service reloaded")


# ---------------------------------------------------------------------------
# U-Boot TFTP boot sequence
# ---------------------------------------------------------------------------

def uboot_tftp_boot(
    ser: serial.Serial,
    kernel: str,
    kernel_addr: str,
    tftp_server: str,
    initrd: Optional[str] = None,
    initrd_addr: str = DEFAULT_INITRD_ADDR,
    bootargs: Optional[str] = None,
) -> bool:
    """Execute the TFTP boot sequence in U-Boot.

    Steps:
      1. Run DHCP to get an IP (autoload=n prevents auto-loading)
      2. Set TFTP server IP explicitly
      3. Load kernel via TFTP
      4. Load initrd via TFTP (if provided)
      5. Set bootargs (if provided)
      6. Boot with bootm

    Args:
        ser: Serial port with U-Boot prompt active.
        kernel: Kernel filename on TFTP server.
        kernel_addr: Memory address to load kernel at.
        tftp_server: TFTP server IP.
        initrd: Optional initrd filename on TFTP server.
        initrd_addr: Memory address to load initrd at.
        bootargs: Optional kernel boot arguments.

    Returns:
        True if boot command was sent successfully.
    """
    # Step 1: DHCP to get an IP address
    print("\n[boot] === Step 1: DHCP ===")
    output, ok = send_command(ser, "dhcp", timeout=30)
    if not ok:
        print("[boot] WARNING: DHCP may have timed out", file=sys.stderr)

    # Step 2: Set TFTP server IP explicitly (in case DHCP didn't set it)
    print("\n[boot] === Step 2: Set TFTP server ===")
    send_command(ser, f"setenv serverip {tftp_server}", timeout=5)

    # Step 3: Load kernel via TFTP
    print(f"\n[boot] === Step 3: TFTP load kernel ({kernel}) ===")
    output, ok = send_command(ser, f"tftpboot {kernel_addr} {kernel}", timeout=120)
    if not ok:
        print("[boot] ERROR: Kernel TFTP load timed out!", file=sys.stderr)
        return False

    # Check for TFTP errors in output
    if any(err in output for err in [b"T T T", b"Retry count exceeded", b"not found"]):
        print("[boot] ERROR: Kernel TFTP load failed!", file=sys.stderr)
        return False

    # Step 4: Load initrd via TFTP (if provided)
    if initrd:
        print(f"\n[boot] === Step 4: TFTP load initrd ({initrd}) ===")
        output, ok = send_command(
            ser, f"tftpboot {initrd_addr} {initrd}", timeout=120
        )
        if not ok:
            print("[boot] ERROR: Initrd TFTP load timed out!", file=sys.stderr)
            return False

    # Step 5: Set bootargs (if provided)
    if bootargs:
        print(f"\n[boot] === Step 5: Set bootargs ===")
        send_command(ser, f"setenv bootargs {bootargs}", timeout=5)

    # Step 6: Boot!
    print("\n[boot] === Booting! ===")
    if initrd:
        bootm_cmd = f"bootm {kernel_addr} {initrd_addr}"
    else:
        bootm_cmd = f"bootm {kernel_addr}"

    # Don't wait for prompt after bootm — the kernel takes over
    send_command(ser, bootm_cmd, expect_prompt=False)
    return True


# ---------------------------------------------------------------------------
# Interactive console
# ---------------------------------------------------------------------------

def interactive_console(ser: serial.Serial) -> None:
    """Drop into an interactive serial console.

    Provides bidirectional communication:
      - Keyboard input is sent to the serial port
      - Serial output is displayed on the terminal
      - Ctrl+] exits (like telnet)

    Terminal is put into raw mode and restored on exit.

    Args:
        ser: Open serial port.
    """
    print("\n[console] Entering interactive console (Ctrl+] to exit)")
    print("[console] " + "=" * 60)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        ser.timeout = 0  # Non-blocking reads

        while True:
            # Check for data from serial port
            # Check for data from keyboard
            rlist, _, _ = select.select([ser, sys.stdin], [], [], 0.01)

            for source in rlist:
                if source is ser:
                    data = ser.read(ser.in_waiting or 1)
                    if data:
                        os.write(sys.stdout.fileno(), data)
                elif source is sys.stdin:
                    char = os.read(sys.stdin.fileno(), 1)
                    if char == b"\x1d":  # Ctrl+]
                        return
                    ser.write(char)
                    ser.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print("\n[console] " + "=" * 60)
        print("[console] Exited interactive console")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TFTP boot a Dell C410X BMC via U-Boot over serial.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Full power cycle + TFTP boot with kernel
  uv run tftp_boot.py \\
      --tasmota-host au-plug-1.iot.welland.mithis.com \\
      --kernel uImage-ast2050

  # No power cycle, just interrupt U-Boot and boot
  uv run tftp_boot.py --no-power-cycle --kernel uImage-ast2050

  # Boot with initrd and custom bootargs
  uv run tftp_boot.py \\
      --tasmota-host au-plug-1.iot.welland.mithis.com \\
      --kernel uImage-ast2050 --initrd initrd-ast2050 \\
      --bootargs "root=/dev/ram0 mem=96M console=ttyS0"

  # Deploy dnsmasq TFTP config first, then boot
  uv run tftp_boot.py \\
      --tasmota-host au-plug-1.iot.welland.mithis.com \\
      --kernel uImage-ast2050 --setup-dnsmasq
""",
    )

    parser.add_argument(
        "--tasmota-host",
        help="Tasmota smart plug hostname (e.g. au-plug-1.iot.welland.mithis.com). "
        "Required unless --no-power-cycle is used.",
    )
    parser.add_argument(
        "--serial-port",
        default="/dev/ttyUSB0",
        help="Serial port device (default: %(default)s)",
    )
    parser.add_argument(
        "--kernel",
        required=True,
        help="Kernel filename on TFTP server (uImage format)",
    )
    parser.add_argument(
        "--initrd",
        default=None,
        help="Initrd filename on TFTP server (uImage format, optional)",
    )
    parser.add_argument(
        "--bootargs",
        default=None,
        help="Override kernel boot arguments",
    )
    parser.add_argument(
        "--kernel-addr",
        default=DEFAULT_KERNEL_ADDR,
        help="Kernel load address (default: %(default)s)",
    )
    parser.add_argument(
        "--initrd-addr",
        default=DEFAULT_INITRD_ADDR,
        help="Initrd load address (default: %(default)s)",
    )
    parser.add_argument(
        "--tftp-server",
        default=DEFAULT_TFTP_SERVER,
        help="TFTP server IP (default: %(default)s)",
    )
    parser.add_argument(
        "--no-power-cycle",
        action="store_true",
        help="Skip power cycle, just interrupt U-Boot",
    )
    parser.add_argument(
        "--off-time",
        type=float,
        default=5.0,
        help="Power-off duration in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--setup-dnsmasq",
        action="store_true",
        help="Deploy dnsmasq TFTP boot override to ten64.welland via SSH",
    )

    args = parser.parse_args()

    if not args.no_power_cycle and not args.tasmota_host:
        parser.error("--tasmota-host is required unless --no-power-cycle is used")

    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Step 0: Deploy dnsmasq override if requested
    if args.setup_dnsmasq:
        deploy_dnsmasq_override(
            boot_filename=args.kernel,
            tftp_server=args.tftp_server,
        )

    # Step 1: Open serial port
    print(f"[serial] Opening {args.serial_port} at 115200 8N1")
    ser = open_serial(args.serial_port)

    try:
        # Step 2: Power cycle (unless skipped)
        if not args.no_power_cycle:
            power_cycle(args.tasmota_host, off_time=args.off_time)

        # Step 3: Interrupt U-Boot autoboot
        boot_output = interrupt_autoboot(ser, timeout=30)
        if not boot_output:
            print("ERROR: Failed to get U-Boot prompt", file=sys.stderr)
            sys.exit(1)

        # Step 4: Extract MAC from boot output (for informational purposes)
        # Re-read any buffered data for MAC extraction
        time.sleep(0.5)
        remaining = ser.read(ser.in_waiting or 0)
        if remaining:
            sys.stdout.buffer.write(remaining)
            sys.stdout.buffer.flush()

        mac = extract_mac_from_output(boot_output + remaining)
        if mac:
            info = KNOWN_C410X_UNITS.get(mac)
            if info:
                print(f"\n[info] Detected known C410X: {info['name']} "
                      f"(MAC {mac}, IP {info['ip']})")
            else:
                print(f"\n[info] Detected MAC: {mac} (not in known units list)")

        # Step 5: TFTP boot sequence
        ok = uboot_tftp_boot(
            ser=ser,
            kernel=args.kernel,
            kernel_addr=args.kernel_addr,
            tftp_server=args.tftp_server,
            initrd=args.initrd,
            initrd_addr=args.initrd_addr,
            bootargs=args.bootargs,
        )

        if not ok:
            print("\n[boot] Boot sequence failed!", file=sys.stderr)
            print("[boot] Dropping to interactive console for debugging...")

        # Step 6: Interactive console
        interactive_console(ser)

    finally:
        ser.close()
        print("[serial] Port closed")


if __name__ == "__main__":
    main()
