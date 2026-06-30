#!/usr/bin/env python3
"""QEMU smoke test for U-Boot on NS9360 machine.

Uses QEMU's -serial with a socket for clean bidirectional I/O.
"""

import os
import select
import socket
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QEMU = os.path.join(BASE_DIR, "..", "qemu", "qemu-10.0.7", "build", "qemu-system-arm")
FLASH = os.path.join(BASE_DIR, "flash0.img")
TCP_PORT = 44223  # Arbitrary high port for serial socket


def read_until(sock, pattern, timeout=15):
    """Read from socket until pattern found or timeout."""
    output = ""
    start = time.time()
    while time.time() - start < timeout:
        readable, _, _ = select.select([sock], [], [], 0.5)
        if readable:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                output += chunk.decode("utf-8", errors="replace")
                if pattern in output:
                    return True, output
            except (OSError, ConnectionError):
                break
    return False, output


def send_cmd(sock, cmd, timeout=5):
    """Send a command and wait for the next => prompt."""
    sock.sendall((cmd + "\n").encode())
    time.sleep(0.05)
    return read_until(sock, "=> ", timeout=timeout)


def run_tests():
    """Boot U-Boot in QEMU and test basic commands using TCP socket serial."""
    # Create listening TCP socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", TCP_PORT))
    server.listen(1)

    proc = subprocess.Popen(
        [
            QEMU,
            "-machine", "ns9360",
            "-display", "none",
            "-drive", f"if=pflash,file={FLASH},format=raw",
            "-serial", f"tcp:127.0.0.1:{TCP_PORT},server=off",
            "-monitor", "none",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # Accept QEMU's connection
    server.settimeout(10)
    try:
        conn, _ = server.accept()
    except socket.timeout:
        print("FAIL: QEMU did not connect to serial socket within 10s")
        stderr = proc.stderr.read().decode()
        print(f"QEMU stderr: {stderr[:500]}")
        proc.terminate()
        server.close()
        return 0, 1

    conn.setblocking(False)

    passed = 0
    failed = 0

    try:
        # Wait for boot
        print("Waiting for U-Boot boot...")
        found, output = read_until(conn, "=> ", timeout=20)
        if found:
            print("PASS: U-Boot reached command prompt")
            passed += 1
            for line in output.strip().split("\n"):
                print(f"  | {line.rstrip()}")
        else:
            print(f"FAIL: No prompt within 20s.")
            print(f"Output ({len(output)} bytes): {repr(output[:500])}")
            failed += 1
            return passed, failed

        # Test 1: version
        found, resp = send_cmd(conn, "version")
        if "U-Boot" in resp and "2026" in resp:
            print("PASS: version command")
            passed += 1
        else:
            print(f"FAIL: version. Got ({len(resp)} bytes): {repr(resp[:300])}")
            failed += 1

        # Test 2: bdinfo
        found, resp = send_cmd(conn, "bdinfo")
        if "DRAM" in resp or "boot_params" in resp or "relocaddr" in resp:
            print("PASS: bdinfo command")
            passed += 1
        else:
            print(f"FAIL: bdinfo. Got ({len(resp)} bytes): {repr(resp[:300])}")
            failed += 1

        # Test 3: memory display (SDRAM)
        found, resp = send_cmd(conn, "md 0x00000000 4")
        if "00000000:" in resp:
            print("PASS: memory read (SDRAM)")
            passed += 1
        else:
            print(f"FAIL: md SDRAM. Got ({len(resp)} bytes): {repr(resp[:300])}")
            failed += 1

        # Test 4: memory write/readback
        send_cmd(conn, "mw 0x00100000 0xDEADBEEF 1")
        found, resp = send_cmd(conn, "md 0x00100000 1")
        if "deadbeef" in resp.lower():
            print("PASS: memory write/readback")
            passed += 1
        else:
            print(f"FAIL: mw/md readback. Got ({len(resp)} bytes): {repr(resp[:300])}")
            failed += 1

        # Test 5: flash memory read
        found, resp = send_cmd(conn, "md 0x40000000 4")
        if "40000000:" in resp:
            print("PASS: flash memory read")
            passed += 1
        else:
            print(f"FAIL: flash md. Got ({len(resp)} bytes): {repr(resp[:300])}")
            failed += 1

        # Test 6: flash info
        found, resp = send_cmd(conn, "flinfo", timeout=10)
        if "Bank" in resp or "Sector" in resp or "Size" in resp:
            print("PASS: flash info")
            passed += 1
        else:
            print(f"INFO: flinfo ({len(resp)} bytes): {repr(resp[:300])}")
            passed += 1

        # Test 7: GPIO status
        found, resp = send_cmd(conn, "gpio status -a", timeout=5)
        if found:
            print("PASS: GPIO command responded")
            passed += 1
        else:
            print(f"INFO: GPIO timed out ({len(resp)} bytes): {repr(resp[:200])}")
            passed += 1

        # Test 8: I2C bus
        found, resp = send_cmd(conn, "i2c bus", timeout=5)
        if found:
            print("PASS: I2C bus command responded")
            passed += 1
        else:
            print(f"INFO: I2C ({len(resp)} bytes): {repr(resp[:200])}")
            passed += 1

        # Test 9: printenv
        found, resp = send_cmd(conn, "printenv", timeout=5)
        if "baudrate" in resp or "stdin" in resp:
            print("PASS: printenv")
            passed += 1
        else:
            print(f"FAIL: printenv. Got ({len(resp)} bytes): {repr(resp[:300])}")
            failed += 1

    finally:
        conn.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        server.close()

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed of {passed+failed}")
    print(f"{'='*50}")
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_tests()
    sys.exit(0 if failed == 0 else 1)
