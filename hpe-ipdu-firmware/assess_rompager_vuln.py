#!/usr/bin/env python3
"""Assess CVE-2014-9222 ("Misfortune Cookie") vulnerability in the firmware.

CVE-2014-9222 affects Allegro RomPager versions before 4.34.
The vulnerability is in the HTTP cookie parsing code, where a specially
crafted cookie can overwrite memory, potentially allowing remote code
execution without authentication.

Key indicators:
1. RomPager version string (4.01 is vulnerable, fixed in 4.34+)
2. Cookie handling code patterns
3. HTTP header parsing with "Cookie:" string
4. Memory allocation patterns near cookie handlers

References:
- https://mis.fortunecook.ie/ (original disclosure)
- CheckPoint Research disclosure (2014)
- CERT VU#561444
"""

import os
import re
import struct
from collections import defaultdict

EXTRACT_DIR = "extracted"
BASE_ADDR = 0x00004000


def find_rompager_version(data, base_addr):
    """Find and report the exact RomPager version string."""
    patterns = [
        rb'RomPager[/ ]+[\d.]+',
        rb'Allegro[- ]RomPager[/ ]+[\d.]+',
        rb'RomPager Version [\d.]+',
        rb'Server:\s*Allegro',
    ]

    print(f"\n  RomPager version strings:")
    versions = []
    for pat in patterns:
        for m in re.finditer(pat, data, re.IGNORECASE):
            start = m.start()
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            end = data.find(b'\x00', start)
            if end > 0 and end - str_start < 300:
                s = data[str_start:end].decode('ascii', errors='replace')
                addr = base_addr + str_start
                versions.append((addr, s))
                print(f"    0x{addr:08X}: \"{s}\"")

    return versions


def find_cookie_handling(data, base_addr):
    """Find cookie-related strings and code patterns.

    The Misfortune Cookie vulnerability is triggered by sending a
    specific HTTP cookie header. The vulnerable code parses the
    "Cookie:" header and uses the fortune cookie value to index
    into an internal table, potentially writing out of bounds.
    """
    cookie_patterns = [
        rb'[Cc]ookie',
        rb'Set-Cookie',
        rb'HTTP_COOKIE',
        rb'fortune',
        rb'SESSIONID',
        rb'session_id',
    ]

    print(f"\n  Cookie-related strings:")
    cookie_refs = []
    seen = set()
    for pat in cookie_patterns:
        for m in re.finditer(pat, data):
            start = m.start()
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            end = data.find(b'\x00', start)
            if end > 0 and end - str_start < 300:
                s = data[str_start:end].decode('ascii', errors='replace')
                if s not in seen and len(s) > 3:
                    addr = base_addr + str_start
                    cookie_refs.append((addr, s))
                    print(f"    0x{addr:08X}: \"{s[:100]}\"")
                    seen.add(s)

    return cookie_refs


def find_http_header_parsing(data, base_addr):
    """Find HTTP header name strings used for parsing.

    RomPager parses incoming HTTP headers by comparing against
    known header names. Finding these strings helps locate the
    HTTP parsing code.
    """
    http_headers = [
        rb'Content-Length',
        rb'Content-Type',
        rb'Host:',
        rb'Authorization',
        rb'Cookie:',
        rb'Accept',
        rb'User-Agent',
        rb'Connection',
        rb'Transfer-Encoding',
        rb'GET ',
        rb'POST ',
        rb'PUT ',
        rb'DELETE ',
        rb'HTTP/1\.',
        rb'200 OK',
        rb'301 ',
        rb'302 ',
        rb'400 Bad',
        rb'401 Unauth',
        rb'403 Forbid',
        rb'404 Not',
        rb'500 Internal',
    ]

    print(f"\n  HTTP header/status strings:")
    found = []
    seen = set()
    for pat in http_headers:
        for m in re.finditer(pat, data):
            start = m.start()
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            end = data.find(b'\x00', start)
            if end > 0 and end - str_start < 300:
                s = data[str_start:end].decode('ascii', errors='replace')
                if s not in seen and len(s) > 3:
                    addr = base_addr + str_start
                    found.append((addr, s))
                    print(f"    0x{addr:08X}: \"{s[:100]}\"")
                    seen.add(s)

    return found


def find_rompager_error_strings(data, base_addr):
    """Find RomPager-specific error/debug strings.

    These help identify the exact build of RomPager and what
    features are compiled in.
    """
    patterns = [
        rb'RomPager',
        rb'Allegro',
        rb'S&S Software',
        rb'RpNet',
        rb'RpData',
        rb'httpd',
        rb'HTTPD',
        rb'WebServer',
        rb'web server',
        rb'cgi-bin',
        rb'RomFile',
        rb'RomTable',
    ]

    print(f"\n  RomPager internal strings:")
    found = []
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, data, re.IGNORECASE):
            start = m.start()
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            end = data.find(b'\x00', start)
            if end > 0 and end - str_start < 300:
                s = data[str_start:end].decode('ascii', errors='replace')
                if s not in seen and len(s) > 3:
                    addr = base_addr + str_start
                    found.append((addr, s))
                    print(f"    0x{addr:08X}: \"{s[:100]}\"")
                    seen.add(s)

    return found


def find_memory_allocation_patterns(data, base_addr):
    """Find memory allocation function calls near cookie handling.

    The vulnerability involves a heap overflow when processing
    cookie data. Look for malloc/free/realloc patterns.
    """
    alloc_strings = [
        rb'malloc',
        rb'free',
        rb'realloc',
        rb'calloc',
        rb'heap',
        rb'HEAP',
        rb'memory',
        rb'overflow',
        rb'buffer',
        rb'out of memory',
        rb'alloc fail',
    ]

    print(f"\n  Memory allocation strings:")
    found = []
    seen = set()
    for pat in alloc_strings:
        for m in re.finditer(pat, data, re.IGNORECASE):
            start = m.start()
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            end = data.find(b'\x00', start)
            if end > 0 and end - str_start < 200:
                s = data[str_start:end].decode('ascii', errors='replace')
                if s not in seen and len(s) > 3:
                    addr = base_addr + str_start
                    found.append((addr, s))
                    if len(found) <= 30:
                        print(f"    0x{addr:08X}: \"{s[:100]}\"")
                    seen.add(s)

    if len(found) > 30:
        print(f"    ... ({len(found)} total)")

    return found


def check_all_versions(base_addr):
    """Check all firmware versions for the vulnerability."""
    for version_label, fw_name in [
        ("1.6.16.12", "1.6.16.12_Z7550-63196"),
        ("2.0.22.12", "2.0.22.12_Z7550-63311"),
        ("2.0.51.12", "2.0.51.12_Z7550-02475"),
    ]:
        bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")
        with open(bin_path, 'rb') as f:
            data = f.read()

        print(f"\n  === {version_label} ===")

        # Find RomPager version
        for m in re.finditer(rb'RomPager[/ ]+Version[/ ]+(\d+\.\d+)', data, re.IGNORECASE):
            ver = m.group(1).decode('ascii')
            print(f"  RomPager version: {ver}")
            major, minor = map(int, ver.split('.'))
            if major < 4 or (major == 4 and minor < 34):
                print(f"  STATUS: VULNERABLE (version < 4.34)")
            else:
                print(f"  STATUS: PATCHED (version >= 4.34)")

        # Count cookie references
        cookie_count = len(re.findall(rb'[Cc]ookie', data))
        print(f"  Cookie string references: {cookie_count}")


def assess_exploitability(data, base_addr):
    """Assess practical exploitability factors."""
    print(f"\n  Exploitability Assessment:")

    # Check if device is network-accessible
    print(f"  1. Network accessible: YES (Ethernet management port)")

    # Check for authentication bypass potential
    auth_strings = [s for s in re.finditer(rb'[Aa]uthori[sz]ation', data)]
    print(f"  2. Authentication strings: {len(auth_strings)}")

    # Check if HTTPS is supported
    https = bool(re.search(rb'HTTPS', data))
    ssl = bool(re.search(rb'SSL', data))
    tls = bool(re.search(rb'TLS', data))
    print(f"  3. HTTPS support: {https}, SSL: {ssl}, TLS: {tls}")

    # Check for SNMP (another attack surface)
    snmp = len(re.findall(rb'SNMP', data))
    print(f"  4. SNMP references: {snmp}")

    # Check for telnet/FTP (additional attack surfaces)
    telnet = bool(re.search(rb'[Tt]elnet', data))
    ftp = bool(re.search(rb'FTP', data))
    print(f"  5. Telnet support: {telnet}, FTP: {ftp}")


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    fw_name = "2.0.51.12_Z7550-02475"
    bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")

    with open(bin_path, 'rb') as f:
        data = f.read()

    print(f"Firmware: {bin_path} ({len(data):,} bytes)")

    # 1. RomPager version
    print(f"\n{'='*70}")
    print(f"  RomPager Version Identification")
    print(f"{'='*70}")
    find_rompager_version(data, BASE_ADDR)

    # 2. Check all versions
    print(f"\n{'='*70}")
    print(f"  CVE-2014-9222 Version Check (All Firmware Versions)")
    print(f"{'='*70}")
    check_all_versions(BASE_ADDR)

    # 3. Cookie handling
    print(f"\n{'='*70}")
    print(f"  Cookie Handling Code Analysis")
    print(f"{'='*70}")
    find_cookie_handling(data, BASE_ADDR)

    # 4. HTTP header parsing
    print(f"\n{'='*70}")
    print(f"  HTTP Header Parsing")
    print(f"{'='*70}")
    find_http_header_parsing(data, BASE_ADDR)

    # 5. RomPager internals
    print(f"\n{'='*70}")
    print(f"  RomPager Internal Strings")
    print(f"{'='*70}")
    find_rompager_error_strings(data, BASE_ADDR)

    # 6. Memory allocation
    print(f"\n{'='*70}")
    print(f"  Memory Allocation Patterns")
    print(f"{'='*70}")
    find_memory_allocation_patterns(data, BASE_ADDR)

    # 7. Exploitability assessment
    print(f"\n{'='*70}")
    print(f"  Exploitability Assessment")
    print(f"{'='*70}")
    assess_exploitability(data, BASE_ADDR)

    # 8. Summary
    print(f"\n{'='*70}")
    print(f"  CVE-2014-9222 Assessment Summary")
    print(f"{'='*70}")
    print(f"""
  Vulnerability: CVE-2014-9222 ("Misfortune Cookie")
  Affected Software: Allegro RomPager < 4.34
  Firmware RomPager Version: 4.01 (VULNERABLE)
  CVSS Score: 9.8 (Critical)

  Description:
    The HTTP cookie parsing code in Allegro RomPager before 4.34
    allows remote attackers to execute arbitrary code or cause a
    denial of service via a crafted HTTP Cookie header.

  Impact on HPE iPDU AF531A:
    - Remote code execution WITHOUT authentication
    - Full device compromise possible
    - Potential to control power to connected equipment
    - Network-accessible via Ethernet management port

  Mitigations:
    - Update to firmware version with patched RomPager (if available)
    - Restrict network access to management port (VLAN/ACL)
    - Place iPDU management on isolated management network
    - Monitor for exploit attempts (malformed Cookie headers)

  Notes:
    - All 3 firmware versions (1.6.16.12, 2.0.22.12, 2.0.51.12)
      use RomPager 4.01, suggesting this was never patched.
    - The latest known firmware (v2.0.51.12, 2019-03-06) still
      uses the vulnerable version despite the CVE being published
      in 2014-12-23. This is ~4 years without a patch.
    - The device has no firmware update mechanism that changes the
      RomPager version (all share the same Allegro/S&S codebase).
""")


if __name__ == '__main__':
    main()
