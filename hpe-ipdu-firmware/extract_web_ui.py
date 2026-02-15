#!/usr/bin/env python3
"""Extract embedded web UI resources from the decompressed firmware.

The HPE iPDU firmware uses Allegro RomPager 4.01 as its web server.
RomPager embeds web resources (HTML, CSS, JS, images) directly in the
firmware binary. This script extracts them.

RomPager uses a resource table that maps URL paths to binary offsets.
The table entries contain:
- URL path string (e.g., "/images/hp-logo.gif")
- Content type string (e.g., "text/html")
- Pointer to embedded data
- Data length

We search for these patterns to find and extract resources.
"""

import os
import re
import struct
import sys
from collections import defaultdict

EXTRACT_DIR = "extracted"
WEB_DIR = os.path.join(EXTRACT_DIR, "web_ui")
BASE_ADDR = 0x00004000


def find_url_paths(data, base_addr):
    """Find embedded URL paths in the binary.

    RomPager resources are typically referenced by paths like:
    /index.html, /images/logo.gif, /css/style.css, /js/app.js
    """
    # Search for strings starting with / followed by alphanumeric+extensions
    paths = []
    url_pattern = re.compile(
        rb'/(?:[\w\-./]+\.(?:html?|css|js|gif|png|jpg|ico|xml|txt|json|cgi|htm))',
        re.IGNORECASE
    )

    for m in url_pattern.finditer(data):
        start = m.start()
        # Find the full null-terminated string
        end = data.find(b'\x00', start)
        if end == -1 or end - start > 256:
            continue
        path = data[start:end].decode('ascii', errors='replace')
        paths.append((base_addr + start, path))

    return paths


def find_html_blocks(data, base_addr):
    """Find HTML content blocks in the binary.

    HTML blocks start with <!-- or <!DOCTYPE or <html or similar tags.
    They're typically null-terminated.
    """
    blocks = []

    # Search for HTML markers
    markers = [
        b'<!DOCTYPE',
        b'<html',
        b'<HTML',
        b'<!-- Rp',  # RomPager directives
        b'<head',
        b'<HEAD',
    ]

    for marker in markers:
        pos = 0
        while True:
            pos = data.find(marker, pos)
            if pos == -1:
                break

            # Find the end of this HTML block (look for closing tags or null)
            # HTML blocks in RomPager are typically null-terminated
            end = pos
            # Scan forward looking for null bytes, but HTML can be large
            block_end = data.find(b'\x00', pos)
            if block_end == -1:
                pos += 1
                continue

            block = data[pos:block_end]
            if len(block) > 50:  # Skip tiny fragments
                blocks.append((base_addr + pos, block))

            pos = block_end + 1

    return blocks


def find_javascript_blocks(data, base_addr):
    """Find JavaScript content blocks."""
    blocks = []

    # Common JS patterns
    markers = [
        b'function ',
        b'var ',
        b'jQuery',
        b'$(document)',
        b'window.',
    ]

    # More targeted: look for blocks that start with common JS file beginnings
    js_starts = [
        b'/*!\n',  # jQuery, Raphael, etc.
        b'/**\n',
        b'// ',
        b"'use strict'",
    ]

    seen_offsets = set()

    for marker in js_starts:
        pos = 0
        while True:
            pos = data.find(marker, pos)
            if pos == -1:
                break

            # Check if this is at a null boundary (start of a resource)
            if pos > 0 and data[pos - 1] != 0:
                pos += 1
                continue

            # Find end (null terminator)
            end = data.find(b'\x00', pos)
            if end == -1 or end - pos > 500000:
                pos += 1
                continue

            if end - pos > 100 and pos not in seen_offsets:
                blocks.append((base_addr + pos, data[pos:end]))
                seen_offsets.add(pos)

            pos = end + 1

    return blocks


def find_rompager_directives(data, base_addr):
    """Find RomPager server-side directives.

    RomPager uses HTML comments with Rp prefix for server-side processing:
    <!-- RpPageHeader ... -->
    <!-- RpFormInput ... -->
    <!-- RpDynamic ... -->
    """
    directives = []
    pattern = re.compile(rb'<!--\s*Rp\w+[^>]*-->', re.DOTALL)

    for m in pattern.finditer(data):
        directive = m.group().decode('ascii', errors='replace')
        addr = base_addr + m.start()
        directives.append((addr, directive))

    return directives


def find_content_type_strings(data, base_addr):
    """Find HTTP content type strings used by RomPager."""
    types = []
    ct_pattern = re.compile(
        rb'(?:text/html|text/css|text/javascript|application/javascript|'
        rb'image/gif|image/png|image/jpeg|application/json|text/xml|'
        rb'application/octet-stream|text/plain)',
        re.IGNORECASE
    )

    for m in ct_pattern.finditer(data):
        addr = base_addr + m.start()
        ct = m.group().decode('ascii', errors='replace')
        types.append((addr, ct))

    return types


def extract_gif_images(data, base_addr):
    """Find and extract embedded GIF images."""
    images = []
    pos = 0
    while True:
        # GIF magic: GIF87a or GIF89a
        pos = data.find(b'GIF8', pos)
        if pos == -1:
            break
        if pos + 6 > len(data):
            break

        version = data[pos:pos + 6]
        if version not in (b'GIF87a', b'GIF89a'):
            pos += 1
            continue

        # Find GIF end marker (0x00 0x3B = block terminator + trailer)
        # GIF files end with 0x3B
        end = data.find(b'\x3b', pos + 6)
        if end == -1 or end - pos > 1000000:
            pos += 1
            continue

        end += 1  # Include the trailer byte
        gif_data = data[pos:end]
        images.append((base_addr + pos, gif_data))
        pos = end

    return images


def extract_png_images(data, base_addr):
    """Find and extract embedded PNG images."""
    images = []
    png_sig = b'\x89PNG\r\n\x1a\n'
    png_end = b'IEND'

    pos = 0
    while True:
        pos = data.find(png_sig, pos)
        if pos == -1:
            break

        # Find IEND chunk
        end = data.find(png_end, pos + 8)
        if end == -1 or end - pos > 1000000:
            pos += 1
            continue

        end += 12  # IEND chunk is 12 bytes (length + type + CRC)
        png_data = data[pos:end]
        images.append((base_addr + pos, png_data))
        pos = end

    return images


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs(WEB_DIR, exist_ok=True)

    fw_name = "2.0.51.12_Z7550-02475"
    bin_path = os.path.join(EXTRACT_DIR, f"{fw_name}_decompressed.bin")

    with open(bin_path, 'rb') as f:
        data = f.read()

    print(f"Firmware: {bin_path} ({len(data):,} bytes)")

    # 1. Find URL paths
    print(f"\n{'='*70}")
    print(f"  URL Paths")
    print(f"{'='*70}")
    paths = find_url_paths(data, BASE_ADDR)
    print(f"  Found {len(paths)} URL paths:")
    for addr, path in sorted(paths, key=lambda x: x[1]):
        print(f"    0x{addr:08X}: {path}")

    # Save URL list
    with open(os.path.join(WEB_DIR, "url_paths.txt"), 'w') as f:
        for addr, path in sorted(paths, key=lambda x: x[1]):
            f.write(f"0x{addr:08X}: {path}\n")

    # 2. Find RomPager directives
    print(f"\n{'='*70}")
    print(f"  RomPager Server-Side Directives")
    print(f"{'='*70}")
    directives = find_rompager_directives(data, BASE_ADDR)
    # Count unique directive types
    directive_types = defaultdict(int)
    for addr, d in directives:
        # Extract the directive name
        m = re.match(r'<!--\s*(Rp\w+)', d)
        if m:
            directive_types[m.group(1)] += 1

    print(f"  Found {len(directives)} RomPager directives:")
    for dtype, count in sorted(directive_types.items()):
        print(f"    {dtype}: {count} occurrences")
        # Show first example
        for addr, d in directives:
            if dtype in d:
                truncated = d[:100] + "..." if len(d) > 100 else d
                print(f"      Example: {truncated}")
                break

    # 3. Find content types
    print(f"\n{'='*70}")
    print(f"  HTTP Content Types")
    print(f"{'='*70}")
    content_types = find_content_type_strings(data, BASE_ADDR)
    ct_counts = defaultdict(int)
    for _, ct in content_types:
        ct_counts[ct] += 1
    print(f"  Found {len(content_types)} content type strings:")
    for ct, count in sorted(ct_counts.items()):
        print(f"    {ct}: {count}")

    # 4. Extract HTML blocks
    print(f"\n{'='*70}")
    print(f"  HTML Content Blocks")
    print(f"{'='*70}")
    html_blocks = find_html_blocks(data, BASE_ADDR)
    print(f"  Found {len(html_blocks)} HTML blocks:")
    total_html_size = 0
    for i, (addr, block) in enumerate(html_blocks[:20]):
        # Try to identify the page
        title_match = re.search(rb'<title>(.*?)</title>', block, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).decode('ascii', errors='replace') if title_match else "untitled"
        size = len(block)
        total_html_size += size
        print(f"    {i+1:3d}. 0x{addr:08X}: {size:,} bytes - \"{title[:60]}\"")

    if len(html_blocks) > 20:
        for _, block in html_blocks[20:]:
            total_html_size += len(block)
        print(f"    ... ({len(html_blocks)} total)")
    print(f"  Total HTML content: {total_html_size:,} bytes ({total_html_size/1024:.0f} KB)")

    # Save largest HTML blocks
    for i, (addr, block) in enumerate(sorted(html_blocks, key=lambda x: len(x[1]), reverse=True)[:20]):
        filename = f"page_{i+1:02d}_0x{addr:08X}.html"
        filepath = os.path.join(WEB_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(block)

    # 5. Extract images
    print(f"\n{'='*70}")
    print(f"  Embedded Images")
    print(f"{'='*70}")

    gif_images = extract_gif_images(data, BASE_ADDR)
    print(f"  GIF images: {len(gif_images)}")
    for i, (addr, img) in enumerate(gif_images):
        filename = f"image_{i+1:02d}_0x{addr:08X}.gif"
        filepath = os.path.join(WEB_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(img)
        # Get dimensions from GIF header
        if len(img) >= 10:
            width = struct.unpack_from('<H', img, 6)[0]
            height = struct.unpack_from('<H', img, 8)[0]
            print(f"    {filename}: {len(img):,} bytes, {width}x{height}")

    png_images = extract_png_images(data, BASE_ADDR)
    print(f"  PNG images: {len(png_images)}")
    for i, (addr, img) in enumerate(png_images):
        filename = f"image_{len(gif_images)+i+1:02d}_0x{addr:08X}.png"
        filepath = os.path.join(WEB_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(img)
        print(f"    {filename}: {len(img):,} bytes")

    # 6. Extract JavaScript blocks
    print(f"\n{'='*70}")
    print(f"  JavaScript Blocks")
    print(f"{'='*70}")
    js_blocks = find_javascript_blocks(data, BASE_ADDR)
    print(f"  Found {len(js_blocks)} JavaScript blocks:")
    total_js_size = 0
    for i, (addr, block) in enumerate(sorted(js_blocks, key=lambda x: len(x[1]), reverse=True)):
        size = len(block)
        total_js_size += size
        # Try to identify the library
        first_line = block[:100].decode('ascii', errors='replace').split('\n')[0]
        if i < 15:
            print(f"    {i+1:3d}. 0x{addr:08X}: {size:,} bytes - \"{first_line[:70]}\"")

        # Save JS blocks
        filename = f"script_{i+1:02d}_0x{addr:08X}.js"
        filepath = os.path.join(WEB_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(block)

    if len(js_blocks) > 15:
        print(f"    ... ({len(js_blocks)} total)")
    print(f"  Total JavaScript: {total_js_size:,} bytes ({total_js_size/1024:.0f} KB)")

    # 7. Summary
    total_web = total_html_size + total_js_size + sum(len(img) for _, img in gif_images) + sum(len(img) for _, img in png_images)
    print(f"\n{'='*70}")
    print(f"  Summary")
    print(f"{'='*70}")
    print(f"  URL paths:         {len(paths)}")
    print(f"  HTML blocks:       {len(html_blocks)} ({total_html_size/1024:.0f} KB)")
    print(f"  JavaScript blocks: {len(js_blocks)} ({total_js_size/1024:.0f} KB)")
    print(f"  GIF images:        {len(gif_images)}")
    print(f"  PNG images:        {len(png_images)}")
    print(f"  RomPager directives: {len(directives)}")
    print(f"  Total web content: ~{total_web/1024:.0f} KB")
    print(f"  Extracted to:      {WEB_DIR}/")


if __name__ == '__main__':
    main()
