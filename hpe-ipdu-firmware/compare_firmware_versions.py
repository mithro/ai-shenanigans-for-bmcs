#!/usr/bin/env python3
"""Compare all 3 decompressed firmware versions.

Compares v1.6.16.12, v2.0.22.12, and v2.0.51.12 to understand:
- Size changes
- String additions/removals
- Common structure
- Feature evolution
- Security changes
"""

import os
import re
import struct
import sys
from collections import defaultdict

EXTRACT_DIR = "extracted"
BASE_ADDR = 0x00004000

VERSIONS = [
    ("1.6.16.12", "1.6.16.12_Z7550-63196"),
    ("2.0.22.12", "2.0.22.12_Z7550-63311"),
    ("2.0.51.12", "2.0.51.12_Z7550-02475"),
]


def extract_strings(data, min_length=6):
    """Extract printable ASCII strings from binary data."""
    strings = []
    current = []
    start_pos = 0

    for i, byte in enumerate(data):
        if 32 <= byte < 127:
            if not current:
                start_pos = i
            current.append(chr(byte))
        else:
            if len(current) >= min_length:
                strings.append((start_pos, ''.join(current)))
            current = []

    if len(current) >= min_length:
        strings.append((start_pos, ''.join(current)))

    return strings


def find_version_strings(data):
    """Find firmware version strings."""
    patterns = [
        rb'\d+\.\d+\.\d+\.\d+',  # x.x.x.x version format
        rb'[Vv]ersion\s+[\d.]+',
        rb'Copyright.*\d{4}',
        rb'Build.*\d+',
    ]
    found = []
    for pat in patterns:
        for m in re.finditer(pat, data):
            start = m.start()
            # Get full null-terminated string
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            end = data.find(b'\x00', start)
            if end > 0 and end - str_start < 300:
                s = data[str_start:end].decode('ascii', errors='replace')
                found.append((str_start, s))
    return found


def find_security_strings(data):
    """Find security-related strings (SSL, auth, crypto)."""
    patterns = [
        rb'SSL', rb'TLS', rb'HTTPS', rb'certificate',
        rb'RSA', rb'SHA', rb'MD5', rb'AES', rb'DES',
        rb'LDAP', rb'RADIUS', rb'SNMP',
        rb'password', rb'login', rb'auth',
        rb'cookie', rb'session', rb'token',
        rb'key\s*=', rb'cipher',
    ]
    found = set()
    for pat in patterns:
        for m in re.finditer(pat, data, re.IGNORECASE):
            start = m.start()
            str_start = start
            while str_start > 0 and data[str_start - 1] >= 0x20 and data[str_start - 1] < 0x7F:
                str_start -= 1
            end = data.find(b'\x00', start)
            if end > 0 and end - str_start < 300:
                s = data[str_start:end].decode('ascii', errors='replace')
                if len(s) > 4:
                    found.add(s)
    return found


def find_url_paths(data):
    """Find URL paths in the binary."""
    paths = set()
    pat = re.compile(
        rb'/(?:[\w\-./]+\.(?:html?|css|js|gif|png|jpg|ico|xml|txt|json|cgi|htm|kl1))',
        re.IGNORECASE
    )
    for m in pat.finditer(data):
        start = m.start()
        end = data.find(b'\x00', start)
        if end > 0 and end - start < 256:
            path = data[start:end].decode('ascii', errors='replace')
            paths.add(path)
    return paths


def find_rompager_directives(data):
    """Find RomPager server-side directives."""
    directives = set()
    pattern = re.compile(rb'<!--\s*Rp\w+')
    for m in pattern.finditer(data):
        directive = m.group().decode('ascii', errors='replace')
        # Extract just the directive type
        dm = re.match(r'<!--\s*(Rp\w+)', directive)
        if dm:
            directives.add(dm.group(1))
    return directives


def binary_diff_regions(data1, data2, block_size=4096):
    """Compare two binaries at block level to find changed regions."""
    min_len = min(len(data1), len(data2))
    changed_blocks = []
    identical_bytes = 0
    different_bytes = 0

    for offset in range(0, min_len, block_size):
        end = min(offset + block_size, min_len)
        block1 = data1[offset:end]
        block2 = data2[offset:end]
        if block1 == block2:
            identical_bytes += len(block1)
        else:
            # Count actual different bytes
            diff_count = sum(1 for a, b in zip(block1, block2) if a != b)
            different_bytes += diff_count
            identical_bytes += len(block1) - diff_count
            changed_blocks.append((offset, diff_count, len(block1)))

    return changed_blocks, identical_bytes, different_bytes


def find_function_prologues(data, base_addr):
    """Find ARM function prologues to estimate function count.

    Common ARM function prologue patterns:
    - STMFD SP!, {regs, LR} -> E92D....
    - PUSH {regs, LR} -> same encoding
    """
    count = 0
    for offset in range(0, len(data) - 3, 4):
        word = struct.unpack_from('>I', data, offset)[0]
        # STMFD SP!, {..., LR} = E92Dxxxx where bit 14 (LR) is set
        if (word & 0xFFFF0000) == 0xE92D0000 and (word & 0x4000):
            count += 1
    return count


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))

    # Load all firmware versions
    firmware = {}
    for version, fw_name in VERSIONS:
        bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")
        with open(bin_path, 'rb') as f:
            firmware[version] = f.read()
        print(f"Loaded {version}: {len(firmware[version]):,} bytes")

    # 1. Size comparison
    print(f"\n{'='*70}")
    print(f"  Firmware Size Comparison")
    print(f"{'='*70}")
    for version, data in firmware.items():
        func_count = find_function_prologues(data, BASE_ADDR)
        printable = sum(1 for b in data if 32 <= b < 127)
        pct = printable / len(data) * 100
        print(f"  {version}: {len(data):>10,} bytes  "
              f"({len(data)/1024/1024:.1f} MB)  "
              f"~{func_count:,} functions  "
              f"{pct:.0f}% printable")

    # Size growth
    v16 = len(firmware["1.6.16.12"])
    v2022 = len(firmware["2.0.22.12"])
    v2051 = len(firmware["2.0.51.12"])
    print(f"\n  Growth: v1.6→v2.0.22: +{v2022-v16:,} bytes (+{(v2022-v16)/v16*100:.0f}%)")
    print(f"  Growth: v2.0.22→v2.0.51: +{v2051-v2022:,} bytes (+{(v2051-v2022)/v2022*100:.1f}%)")

    # 2. String comparison
    print(f"\n{'='*70}")
    print(f"  String Comparison")
    print(f"{'='*70}")
    string_sets = {}
    for version, data in firmware.items():
        strings = extract_strings(data, min_length=8)
        string_set = set(s for _, s in strings)
        string_sets[version] = string_set
        print(f"  {version}: {len(string_set):,} unique strings (>= 8 chars)")

    # Strings added in v2.0 that weren't in v1.6
    added_v2 = string_sets["2.0.22.12"] - string_sets["1.6.16.12"]
    removed_v2 = string_sets["1.6.16.12"] - string_sets["2.0.22.12"]
    print(f"\n  Strings added in v2.0.22 (not in v1.6): {len(added_v2):,}")
    print(f"  Strings removed in v2.0.22 (was in v1.6): {len(removed_v2):,}")

    # Show interesting added strings
    interesting_keywords = ['ldap', 'ssl', 'tls', 'https', 'snmp', 'ipv6',
                           'radius', 'rack', 'json', 'xml', 'ajax',
                           'jquery', 'raphael', 'password', 'auth',
                           'syslog', 'ntp', 'dhcp', 'firmware',
                           'upgrade', 'security', 'certificate']
    print(f"\n  Notable strings added in v2.0.22:")
    for s in sorted(added_v2):
        s_lower = s.lower()
        if any(kw in s_lower for kw in interesting_keywords) and len(s) < 120:
            print(f"    \"{s[:100]}\"")

    # Strings changed between v2.0.22 and v2.0.51
    added_v2051 = string_sets["2.0.51.12"] - string_sets["2.0.22.12"]
    removed_v2051 = string_sets["2.0.22.12"] - string_sets["2.0.51.12"]
    print(f"\n  Strings added in v2.0.51 (not in v2.0.22): {len(added_v2051):,}")
    print(f"  Strings removed in v2.0.51 (was in v2.0.22): {len(removed_v2051):,}")
    if added_v2051:
        print(f"\n  Notable strings added in v2.0.51:")
        for s in sorted(added_v2051):
            s_lower = s.lower()
            if any(kw in s_lower for kw in interesting_keywords) and len(s) < 120:
                print(f"    \"{s[:100]}\"")

    # 3. URL path comparison
    print(f"\n{'='*70}")
    print(f"  Web UI URL Path Comparison")
    print(f"{'='*70}")
    url_sets = {}
    for version, data in firmware.items():
        urls = find_url_paths(data)
        url_sets[version] = urls
        print(f"  {version}: {len(urls)} URL paths")

    # URLs added/removed
    urls_added_v2 = url_sets["2.0.22.12"] - url_sets["1.6.16.12"]
    urls_removed_v2 = url_sets["1.6.16.12"] - url_sets["2.0.22.12"]
    print(f"\n  URLs added in v2.0.22 (not in v1.6): {len(urls_added_v2)}")
    for url in sorted(urls_added_v2)[:30]:
        print(f"    + {url}")
    if len(urls_added_v2) > 30:
        print(f"    ... ({len(urls_added_v2)} total)")

    print(f"\n  URLs removed in v2.0.22 (was in v1.6): {len(urls_removed_v2)}")
    for url in sorted(urls_removed_v2)[:20]:
        print(f"    - {url}")

    urls_added_v2051 = url_sets["2.0.51.12"] - url_sets["2.0.22.12"]
    urls_removed_v2051 = url_sets["2.0.22.12"] - url_sets["2.0.51.12"]
    print(f"\n  URLs added in v2.0.51: {len(urls_added_v2051)}")
    for url in sorted(urls_added_v2051):
        print(f"    + {url}")
    print(f"\n  URLs removed in v2.0.51: {len(urls_removed_v2051)}")
    for url in sorted(urls_removed_v2051):
        print(f"    - {url}")

    # 4. Security string comparison
    print(f"\n{'='*70}")
    print(f"  Security Feature Comparison")
    print(f"{'='*70}")
    sec_sets = {}
    for version, data in firmware.items():
        sec = find_security_strings(data)
        sec_sets[version] = sec

    # Security features added in v2.0
    sec_added = sec_sets["2.0.22.12"] - sec_sets["1.6.16.12"]
    sec_removed = sec_sets["1.6.16.12"] - sec_sets["2.0.22.12"]
    print(f"\n  Security strings added in v2.0.22:")
    for s in sorted(sec_added):
        if len(s) < 120:
            print(f"    + \"{s[:100]}\"")
    print(f"\n  Security strings removed in v2.0.22:")
    for s in sorted(sec_removed):
        if len(s) < 120:
            print(f"    - \"{s[:100]}\"")

    # 5. RomPager directive comparison
    print(f"\n{'='*70}")
    print(f"  RomPager Directive Comparison")
    print(f"{'='*70}")
    for version, data in firmware.items():
        directives = find_rompager_directives(data)
        print(f"  {version}: {len(directives)} directive types: {', '.join(sorted(directives))}")

    # 6. Binary diff between v2.0.22 and v2.0.51
    print(f"\n{'='*70}")
    print(f"  Binary Diff: v2.0.22 vs v2.0.51")
    print(f"{'='*70}")
    changed, identical, different = binary_diff_regions(
        firmware["2.0.22.12"], firmware["2.0.51.12"], block_size=4096
    )
    total = identical + different
    print(f"  Identical bytes: {identical:,} ({identical/total*100:.1f}%)")
    print(f"  Different bytes: {different:,} ({different/total*100:.1f}%)")
    print(f"  Changed 4KB blocks: {len(changed)}")

    if changed:
        print(f"\n  Changed regions (top 20 by diff count):")
        for offset, diff_count, block_len in sorted(changed, key=lambda x: x[1], reverse=True)[:20]:
            addr = BASE_ADDR + offset
            pct = diff_count / block_len * 100
            # Try to identify what's in this region
            region_type = "unknown"
            if offset < 0x500000:
                region_type = "code"
            elif offset < 0x680000:
                region_type = "web UI"
            else:
                region_type = "strings/config"
            print(f"    0x{addr:08X}: {diff_count:>4d}/{block_len} bytes different ({pct:.0f}%) [{region_type}]")

    # 7. Version-specific strings (identifiers)
    print(f"\n{'='*70}")
    print(f"  Version Identification Strings")
    print(f"{'='*70}")
    for version, data in firmware.items():
        print(f"\n  {version}:")
        ver_strings = find_version_strings(data)
        seen = set()
        for _, s in sorted(ver_strings):
            if s not in seen and len(s) < 120:
                print(f"    \"{s[:100]}\"")
                seen.add(s)

    # 8. Default config comparison
    print(f"\n{'='*70}")
    print(f"  Default Configuration Comparison")
    print(f"{'='*70}")
    for version, data in firmware.items():
        # Find Brookline string
        pos = data.find(b'Brookline')
        if pos == -1:
            print(f"  {version}: No 'Brookline' string found!")
            continue

        print(f"\n  {version} (Brookline at file offset 0x{pos:X}):")
        # Dump 256 bytes from the string as null-terminated fields
        dump_end = min(len(data), pos + 384)
        field_start = pos
        fields = []
        while field_start < dump_end:
            field_end = data.find(b'\x00', field_start)
            if field_end == -1 or field_end >= dump_end:
                break
            field = data[field_start:field_end]
            if field:
                try:
                    s = field.decode('ascii')
                    if all(32 <= ord(c) < 127 for c in s):
                        fields.append(s)
                except UnicodeDecodeError:
                    pass
            # Skip null padding (groups of nulls)
            field_start = field_end + 1
            while field_start < dump_end and data[field_start] == 0:
                field_start += 1

        for f in fields:
            print(f"    \"{f}\"")


if __name__ == '__main__':
    main()
