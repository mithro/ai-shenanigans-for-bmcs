#!/usr/bin/env python3
"""
I2C Address Pattern Scanner for Dell C410X BMC fullfw binary.

Scans the ARM32 ELF binary for known I2C addresses and PLX register offsets
by disassembling with arm-linux-gnueabi-objdump and matching against known
constants. Cross-references matches against the symbol table to identify
which functions contain each pattern.

Produces two tiers of results:
  - HIGH CONFIDENCE: Matches inside known PEX/I2C/GPU functions (from the
    symbol table), where the constant is most likely to be a genuine I2C
    address or PLX register reference.
  - ALL MATCHES: Every instruction that uses a target constant as an
    immediate value. Includes many false positives because small values
    like 0x18, 0x30, 0x34 are common struct/stack offsets in ARM code.

Usage:
    uv run tools/scan_i2c_patterns.py

Output:
    analysis/i2c-pattern-scan.md
"""

import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration: paths relative to the pex-i2c-analysis directory
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
ANALYSIS_DIR = BASE_DIR / "analysis"
FULLFW_PATH = ANALYSIS_DIR / "fullfw"
SYMBOL_TABLE_PATH = ANALYSIS_DIR / "symbol-table.txt"
OUTPUT_PATH = ANALYSIS_DIR / "i2c-pattern-scan.md"

OBJDUMP = "arm-linux-gnueabi-objdump"


# ---------------------------------------------------------------------------
# Known constants to scan for
# ---------------------------------------------------------------------------

@dataclass
class KnownConstant:
    """A known constant we are scanning for in the disassembly."""
    value: int
    name: str
    category: str
    description: str
    # If True, the value is common in ARM code (struct offsets, etc.)
    # and should only be treated as high-confidence inside PEX/I2C functions.
    ambiguous: bool = False


# I2C slave addresses (7-bit, used as byte values)
# These small values are very common in ARM code as struct offsets, so they
# are marked ambiguous.
I2C_ADDRESSES = [
    KnownConstant(0x18, "PEX8696_I2C_0x18", "I2C Address",
                  "PEX8696 switch #1 I2C slave address", ambiguous=True),
    KnownConstant(0x19, "PEX8696_I2C_0x19", "I2C Address",
                  "PEX8696 switch #3 I2C slave address", ambiguous=True),
    KnownConstant(0x1A, "PEX8696_I2C_0x1A", "I2C Address",
                  "PEX8696 switch #2 I2C slave address", ambiguous=True),
    KnownConstant(0x1B, "PEX8696_I2C_0x1B", "I2C Address",
                  "PEX8696 switch #4 I2C slave address", ambiguous=True),
    KnownConstant(0x30, "PEX8696_GBT_0x30", "I2C Address (GBT)",
                  "PEX8696 GBT (Global Byte Transfer) address", ambiguous=True),
    KnownConstant(0x32, "PEX8696_GBT_0x32", "I2C Address (GBT)",
                  "PEX8696 GBT address", ambiguous=True),
    KnownConstant(0x34, "PEX8696_GBT_0x34", "I2C Address (GBT)",
                  "PEX8696 GBT address", ambiguous=True),
    KnownConstant(0x36, "PEX8696_GBT_0x36", "I2C Address (GBT)",
                  "PEX8696 GBT address", ambiguous=True),
]

BUS_IDENTIFIERS = [
    KnownConstant(0xF3, "I2C_BUS_0xF3", "I2C Bus",
                  "I2C bus identifier for PEX switch bus (AST2050 engine 3)",
                  ambiguous=False),
]

PLX_REGISTERS = [
    KnownConstant(0x208, "PLX_PORT_CTRL_0x208", "PLX Register",
                  "Port Control register (per-port, stride 0x1000)",
                  ambiguous=False),
    KnownConstant(0x260, "PLX_EEPROM_CTRL_0x260", "PLX Register",
                  "EEPROM Control register", ambiguous=False),
    KnownConstant(0x264, "PLX_EEPROM_DATA_0x264", "PLX Register",
                  "EEPROM Data register", ambiguous=False),
    KnownConstant(0x1000, "PLX_PORT_STRIDE_0x1000", "PLX Register",
                  "Port stride (port_number * 0x1000 = register offset)",
                  ambiguous=True),
    KnownConstant(0x3E, "PLX_HP_GPIO_0x3E", "PLX Register",
                  "Hot-plug related register / GPIO mapping",
                  ambiguous=True),
]

ALL_CONSTANTS = I2C_ADDRESSES + BUS_IDENTIFIERS + PLX_REGISTERS

# Build a lookup from value to list of constants (some values might collide)
VALUE_TO_CONSTANTS: dict[int, list[KnownConstant]] = defaultdict(list)
for c in ALL_CONSTANTS:
    VALUE_TO_CONSTANTS[c.value].append(c)

# Keywords identifying PEX/I2C/GPU-related functions (case-insensitive).
# A match inside one of these functions is "high confidence".
PEX_FUNCTION_KEYWORDS = [
    "pex", "plx", "i2c", "gpu", "slot_power", "hp_ctrl", "hp_on", "hp_off",
    "multi_host", "eeprom", "hot_plug", "mux", "pi2c",
]


# ---------------------------------------------------------------------------
# Symbol table parsing
# ---------------------------------------------------------------------------

@dataclass
class Symbol:
    """A symbol from the nm output."""
    address: int
    sym_type: str
    name: str
    size: Optional[int] = None  # estimated from next symbol


def parse_symbol_table(path: Path) -> list[Symbol]:
    """Parse arm-linux-gnueabi-nm -n output into a list of symbols.

    Format: "ADDR TYPE NAME" or "         U NAME" for undefined symbols.
    """
    symbols = []
    with open(path, "r") as f:
        for line in f:
            line = line.rstrip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                addr = int(parts[0], 16)
            except ValueError:
                continue
            sym_type = parts[1]
            name = parts[2]
            symbols.append(Symbol(address=addr, sym_type=sym_type, name=name))

    # Sort by address and estimate sizes
    symbols.sort(key=lambda s: s.address)
    for i in range(len(symbols) - 1):
        symbols[i].size = symbols[i + 1].address - symbols[i].address

    return symbols


def build_function_ranges(
    symbols: list[Symbol],
) -> list[tuple[int, int, str]]:
    """Build sorted list of (start, end, name) for binary-search lookup.

    Only includes symbols that are functions (type t/T) and have valid sizes.
    """
    entries = []
    for sym in symbols:
        if sym.sym_type in ("t", "T") and sym.size and sym.size > 0:
            entries.append((sym.address, sym.address + sym.size, sym.name))
    entries.sort(key=lambda e: e[0])
    return entries


def build_data_symbol_ranges(
    symbols: list[Symbol],
) -> list[tuple[int, int, str]]:
    """Build sorted ranges for data symbols."""
    entries = []
    for sym in symbols:
        if sym.sym_type in ("d", "D", "r", "R") and sym.size and sym.size > 0:
            entries.append((sym.address, sym.address + sym.size, sym.name))
    entries.sort(key=lambda e: e[0])
    return entries


def find_containing_entry(
    addr: int, ranges: list[tuple[int, int, str]]
) -> Optional[str]:
    """Binary search for the range containing a given address."""
    lo, hi = 0, len(ranges) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end, name = ranges[mid]
        if addr < start:
            hi = mid - 1
        elif addr >= end:
            lo = mid + 1
        else:
            return name
    return None


def is_pex_related_function(name: str) -> bool:
    """Check if a function name suggests PEX/I2C/GPU relevance."""
    name_lower = name.lower()
    return any(kw in name_lower for kw in PEX_FUNCTION_KEYWORDS)


# ---------------------------------------------------------------------------
# Disassembly scanning
# ---------------------------------------------------------------------------

@dataclass
class PatternMatch:
    """A match of a known constant in the disassembly."""
    address: int
    instruction: str
    raw_line: str
    constant: KnownConstant
    containing_function: Optional[str]
    high_confidence: bool  # True if in a PEX-related function


# Regex to parse objdump disassembly lines like:
#    2e694:	e3a0c010 	mov	ip, #16
# Captures: address, hex_encoding, mnemonic+operands, optional comment
DISASM_LINE_RE = re.compile(
    r"^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(.+?)(?:\s*@\s*(.*))?$"
)

# Instructions that set register values from immediates (relevant for
# loading I2C addresses or register offsets into registers).
VALUE_SETTING_INSTRUCTIONS = {
    "mov", "movs", "movw", "movt",
    "mvn", "mvns",
    "ldr", "ldrb", "ldrh",
}

# Instructions that compare/test against immediates (relevant for
# checking I2C addresses or switch/case on address values).
COMPARE_INSTRUCTIONS = {
    "cmp", "cmn", "tst",
}

# Instructions that do arithmetic with immediates (relevant for
# computing register offsets like base + 0x208).
ARITHMETIC_INSTRUCTIONS = {
    "add", "adds", "sub", "subs",
    "and", "ands", "orr", "orrs", "eor", "eors",
    "bic", "bics",
}

# Store instructions — these can store byte values that happen to be
# I2C addresses, but are also extremely common for struct field writes.
STORE_INSTRUCTIONS = {
    "str", "strb", "strh",
}

ALL_IMM_INSTRUCTIONS = (
    VALUE_SETTING_INSTRUCTIONS
    | COMPARE_INSTRUCTIONS
    | ARITHMETIC_INSTRUCTIONS
    | STORE_INSTRUCTIONS
)


def classify_instruction(mnemonic_operands: str) -> tuple[Optional[str], str]:
    """Extract the base mnemonic and classify the instruction.

    Returns (base_mnemonic, category) where category is one of:
    'value_set', 'compare', 'arithmetic', 'store', or 'other'.
    """
    parts = mnemonic_operands.strip().split(None, 1)
    if not parts:
        return None, "other"

    mnemonic = parts[0].lower().rstrip("{}")

    # Strip condition code suffix (e.g., "moveq" -> "mov")
    base = mnemonic
    for suffix in ("eq", "ne", "cs", "hs", "cc", "lo", "mi", "pl",
                   "vs", "vc", "hi", "ls", "ge", "lt", "gt", "le", "al"):
        if len(base) > len(suffix) and base.endswith(suffix):
            stripped = base[: -len(suffix)]
            if stripped in ALL_IMM_INSTRUCTIONS:
                base = stripped
                break

    if base in VALUE_SETTING_INSTRUCTIONS:
        return base, "value_set"
    if base in COMPARE_INSTRUCTIONS:
        return base, "compare"
    if base in ARITHMETIC_INSTRUCTIONS:
        return base, "arithmetic"
    if base in STORE_INSTRUCTIONS:
        return base, "store"
    return None, "other"


def is_false_positive_pattern(mnemonic_operands: str) -> bool:
    """Check if an instruction matches common false-positive patterns.

    Filters out:
    - Stack frame operations: `str r3, [fp, #-24]`, `ldr r3, [sp, #20]`
    - Frame pointer arithmetic: `sub r3, fp, #24`, `add r2, fp, #0x30`
    - Stack pointer arithmetic: `sub sp, sp, #0x30`
    - PC-relative loads: `ldr r0, [pc, #24]` (the #24 is an offset, not a value)
    - Literal pool label references in comments handled separately
    """
    operands_lower = mnemonic_operands.lower()
    # Stack/frame-pointer-relative loads/stores
    if re.search(r'\[(?:fp|sp|r11|r13)', operands_lower):
        return True
    # Frame pointer arithmetic (sub r3, fp, #24 is accessing local var)
    if re.search(r'(?:sub|add)\w*\s+\w+,\s*(?:fp|r11)', operands_lower):
        return True
    # Stack pointer arithmetic
    if re.match(r'\s*(?:sub|add)\w*\s+(?:sp|r13)', operands_lower):
        return True
    # PC-relative loads — the immediate is an offset into the code, not a value
    # e.g., `ldr r0, [pc, #24]` means "load from address PC+24"
    if re.search(r'\[pc', operands_lower):
        return True
    return False


def extract_immediate_values(
    mnemonic_operands: str, comment: Optional[str], base_mnemonic: Optional[str]
) -> set[int]:
    """Extract immediate values from an instruction.

    Returns a set of integers found as immediates (deduplicated so that
    e.g. `mov r3, #48 @ 0x30` only yields 0x30 once, not twice).
    """
    values: set[int] = set()

    if base_mnemonic is None:
        return values

    parts = mnemonic_operands.strip().split(None, 1)
    operands = parts[1] if len(parts) > 1 else ""

    # Find all #value patterns in operands
    for m in re.finditer(r"#(0x[0-9a-fA-F]+|\d+)", operands):
        val_str = m.group(1)
        val = int(val_str, 16) if val_str.startswith("0x") else int(val_str)
        values.add(val)

        # For mvn, also record the NOT'd value (masked to byte width)
        if base_mnemonic in ("mvn", "mvns"):
            not_val = (~val) & 0xFF
            values.add(not_val)

    # Check the comment for hex value (objdump: "mov r3, #48  @ 0x30")
    if comment:
        for m in re.finditer(r"0x([0-9a-fA-F]+)", comment):
            val = int(m.group(1), 16)
            values.add(val)

    return values


def scan_disassembly(
    fullfw_path: Path,
    func_ranges: list[tuple[int, int, str]],
) -> list[PatternMatch]:
    """Disassemble the binary and scan for known constant values."""
    print(f"Running {OBJDUMP} -d on {fullfw_path}...")
    result = subprocess.run(
        [OBJDUMP, "-d", str(fullfw_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"Disassembly complete ({len(result.stdout)} bytes of output)")

    target_values = set(VALUE_TO_CONSTANTS.keys())

    matches = []
    lines_scanned = 0
    current_function_label = None

    for line in result.stdout.splitlines():
        # Track function labels
        label_match = re.match(r"^([0-9a-f]+)\s+<(.+?)>:", line)
        if label_match:
            current_function_label = label_match.group(2)
            continue

        m = DISASM_LINE_RE.match(line)
        if not m:
            continue

        lines_scanned += 1
        addr_str, hex_encoding, mnemonic_operands, comment = m.groups()
        addr = int(addr_str, 16)

        base_mnemonic, instr_category = classify_instruction(mnemonic_operands)
        if instr_category == "other":
            continue

        # Skip common false-positive patterns
        if is_false_positive_pattern(mnemonic_operands):
            continue

        imm_values = extract_immediate_values(mnemonic_operands, comment, base_mnemonic)

        for val in imm_values:
            if val not in target_values:
                continue

            # Determine containing function
            func_name = find_containing_entry(addr, func_ranges)
            if func_name is None and current_function_label:
                func_name = current_function_label

            is_pex_func = func_name is not None and is_pex_related_function(func_name)

            for constant in VALUE_TO_CONSTANTS[val]:
                # For ambiguous values, only include if in a PEX-related
                # function OR if the instruction type is suggestive
                # (mov/cmp with the exact value, not add/sub offset)
                high_conf = is_pex_func
                if constant.ambiguous and not is_pex_func:
                    # For non-PEX functions, only keep mov/cmp/strb
                    # as possible legitimate I2C address usage
                    if instr_category not in ("value_set", "compare"):
                        continue

                matches.append(
                    PatternMatch(
                        address=addr,
                        instruction=mnemonic_operands.strip(),
                        raw_line=line.strip(),
                        constant=constant,
                        containing_function=func_name,
                        high_confidence=high_conf,
                    )
                )

    print(f"Scanned {lines_scanned} instructions, found {len(matches)} matches")
    return matches


# ---------------------------------------------------------------------------
# Data section scanning for I2C address tables
# ---------------------------------------------------------------------------

def scan_data_sections(
    fullfw_path: Path,
    data_ranges: list[tuple[int, int, str]],
) -> list[PatternMatch]:
    """Scan .rodata and .data sections for known byte values in tables.

    Only reports matches inside PEX/I2C-related data symbols.
    """
    print("Scanning data sections for address tables...")
    result = subprocess.run(
        [OBJDUMP, "-s", "-j", ".rodata", "-j", ".data", str(fullfw_path)],
        capture_output=True,
        text=True,
        check=True,
    )

    matches = []
    hex_line_re = re.compile(r"^\s+([0-9a-f]+)\s+((?:[0-9a-f]{2,8}\s*)+)")

    target_byte_values = {}
    for c in ALL_CONSTANTS:
        if c.value <= 0xFF:
            target_byte_values[c.value] = c

    for line in result.stdout.splitlines():
        m = hex_line_re.match(line)
        if not m:
            continue
        base_addr = int(m.group(1), 16)
        hex_parts = m.group(2).strip().split()
        hex_str = "".join(hex_parts)
        for i in range(0, len(hex_str), 2):
            byte_val = int(hex_str[i : i + 2], 16)
            if byte_val in target_byte_values:
                byte_addr = base_addr + i // 2
                c = target_byte_values[byte_val]
                sym_name = find_containing_entry(byte_addr, data_ranges)
                if sym_name and is_pex_related_function(sym_name):
                    matches.append(
                        PatternMatch(
                            address=byte_addr,
                            instruction=f"data byte: 0x{byte_val:02X}",
                            raw_line=line.strip(),
                            constant=c,
                            containing_function=sym_name,
                            high_confidence=True,
                        )
                    )

    print(f"Found {len(matches)} matches in data sections")
    return matches


# ---------------------------------------------------------------------------
# Analysis and reporting
# ---------------------------------------------------------------------------

def generate_report(
    all_matches: list[PatternMatch],
    symbols: list[Symbol],
    output_path: Path,
) -> None:
    """Generate the markdown report of scan results."""

    high_conf = [m for m in all_matches if m.high_confidence]
    low_conf = [m for m in all_matches if not m.high_confidence]

    lines: list[str] = []

    # ---- Header ----
    lines.append("# I2C Address Pattern Scan Results")
    lines.append("")
    lines.append("Automated scan of the Dell C410X BMC `fullfw` ARM binary for known")
    lines.append("I2C addresses and PLX register offsets.")
    lines.append("")
    lines.append("- **Binary:** `fullfw` (ARM 32-bit ELF)")
    lines.append(f"- **Tool:** `{OBJDUMP} -d`")
    lines.append(f"- **Total matches:** {len(all_matches)}")
    lines.append(f"- **High-confidence matches (in PEX/I2C/GPU functions):** "
                 f"{len(high_conf)}")
    lines.append(f"- **Lower-confidence matches (all functions):** "
                 f"{len(low_conf)}")
    lines.append(f"- **Distinct constants matched:** "
                 f"{len({m.constant.name for m in all_matches})}")
    lines.append("")
    lines.append("> **Note:** Small values like `0x18`, `0x30`, `0x34` are common")
    lines.append("> ARM struct offsets. The *high-confidence* matches are those found")
    lines.append("> inside functions whose names contain PEX/I2C/GPU/slot keywords.")
    lines.append("> Stack/frame-pointer operations, PC-relative loads (offset, not value),")
    lines.append("> and frame-pointer arithmetic are filtered out to reduce false positives.")
    lines.append("")

    # ---- Summary table ----
    lines.append("## Summary of Constants Found")
    lines.append("")
    lines.append("| Constant | Value | Category | High-Conf | All | High-Conf Functions |")
    lines.append("|----------|-------|----------|-----------|-----|---------------------|")

    constant_stats: dict[str, dict] = {}
    for m in all_matches:
        name = m.constant.name
        if name not in constant_stats:
            constant_stats[name] = {
                "value": m.constant.value,
                "category": m.constant.category,
                "high": 0,
                "total": 0,
                "high_funcs": set(),
            }
        constant_stats[name]["total"] += 1
        if m.high_confidence:
            constant_stats[name]["high"] += 1
            if m.containing_function:
                constant_stats[name]["high_funcs"].add(m.containing_function)

    for name, info in sorted(
        constant_stats.items(), key=lambda x: -x[1]["high"]
    ):
        funcs = ", ".join(sorted(info["high_funcs"])[:5])
        if len(info["high_funcs"]) > 5:
            funcs += f" (+{len(info['high_funcs']) - 5} more)"
        lines.append(
            f"| `{name}` | `0x{info['value']:X}` | {info['category']} "
            f"| {info['high']} | {info['total']} | {funcs} |"
        )
    lines.append("")

    # ---- High-confidence results by category ----
    lines.append("## High-Confidence Matches")
    lines.append("")
    lines.append("These matches are inside functions whose names indicate PEX/I2C/GPU")
    lines.append("relevance, making them very likely to be genuine I2C address or PLX")
    lines.append("register references.")
    lines.append("")

    by_category: dict[str, list[PatternMatch]] = defaultdict(list)
    for m in high_conf:
        by_category[m.constant.category].append(m)

    category_order = [
        "I2C Bus",
        "I2C Address",
        "I2C Address (GBT)",
        "PLX Register",
    ]
    for category in category_order:
        cat_matches = by_category.get(category, [])
        if not cat_matches:
            continue

        lines.append(f"### {category}")
        lines.append("")
        lines.append(f"{len(cat_matches)} high-confidence matches.")
        lines.append("")
        lines.append("| Address | Instruction | Constant | Function |")
        lines.append("|---------|-------------|----------|----------|")

        for m in sorted(cat_matches, key=lambda x: x.address):
            func = m.containing_function or "(unknown)"
            instr = m.instruction
            if len(instr) > 55:
                instr = instr[:52] + "..."
            lines.append(
                f"| `0x{m.address:08X}` | `{instr}` "
                f"| `{m.constant.name}` | `{func}` |"
            )
        lines.append("")

    # ---- Hot functions ----
    lines.append("## Hot Functions (High-Confidence)")
    lines.append("")
    lines.append("PEX/I2C/GPU functions ranked by number of distinct constants referenced.")
    lines.append("")

    func_dc_high: dict[str, set[str]] = defaultdict(set)
    func_count_high: dict[str, int] = defaultdict(int)
    for m in high_conf:
        func = m.containing_function or "(unknown)"
        func_dc_high[func].add(m.constant.name)
        func_count_high[func] += 1

    hot = sorted(
        func_dc_high.items(),
        key=lambda x: (len(x[1]), func_count_high[x[0]]),
        reverse=True,
    )

    lines.append("| Function | Distinct Constants | Total Matches | Constants Referenced |")
    lines.append("|----------|-------------------|---------------|---------------------|")

    for func, constants in hot[:30]:
        total = func_count_high[func]
        const_list = ", ".join(sorted(constants))
        lines.append(
            f"| `{func}` | {len(constants)} | {total} | {const_list} |"
        )
    lines.append("")

    # ---- Detailed breakdown of top hot functions ----
    lines.append("### Hot Function Details")
    lines.append("")

    by_func_high: dict[str, list[PatternMatch]] = defaultdict(list)
    for m in high_conf:
        func = m.containing_function or "(unknown)"
        by_func_high[func].append(m)

    for func, constants in hot[:20]:
        if len(constants) < 2:
            continue
        func_matches = sorted(by_func_high[func], key=lambda m: m.address)
        lines.append(f"#### `{func}`")
        lines.append("")
        lines.append(f"- **Distinct constants:** {len(constants)}")
        lines.append(f"- **Total matches:** {len(func_matches)}")
        lines.append("")
        lines.append("| Address | Instruction | Constant |")
        lines.append("|---------|-------------|----------|")
        for m in func_matches:
            instr = m.instruction
            if len(instr) > 60:
                instr = instr[:57] + "..."
            lines.append(
                f"| `0x{m.address:08X}` | `{instr}` | `{m.constant.name}` |"
            )
        lines.append("")

    # ---- Lower-confidence interesting functions ----
    # Show non-PEX functions that match many constants — these might be
    # functions we haven't identified as PEX-related yet.
    lines.append("## Potentially Interesting Non-PEX Functions")
    lines.append("")
    lines.append("Functions NOT matching PEX/I2C/GPU keywords that still reference")
    lines.append("multiple target constants. These may be undiscovered PEX-related functions")
    lines.append("or generic utility functions that happen to use the same values.")
    lines.append("")

    func_dc_low: dict[str, set[str]] = defaultdict(set)
    func_count_low: dict[str, int] = defaultdict(int)
    for m in low_conf:
        func = m.containing_function or "(unknown)"
        func_dc_low[func].add(m.constant.name)
        func_count_low[func] += 1

    low_hot = sorted(
        func_dc_low.items(),
        key=lambda x: (len(x[1]), func_count_low[x[0]]),
        reverse=True,
    )

    lines.append("| Function | Distinct Constants | Total Matches | Constants Referenced |")
    lines.append("|----------|-------------------|---------------|---------------------|")

    for func, constants in low_hot[:20]:
        if len(constants) < 2:
            break
        total = func_count_low[func]
        const_list = ", ".join(sorted(constants))
        lines.append(
            f"| `{func}` | {len(constants)} | {total} | {const_list} |"
        )
    lines.append("")

    # ---- Write report ----
    report = "\n".join(lines) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)
    print(f"Report written to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Verify files exist
    if not FULLFW_PATH.exists():
        print(f"ERROR: fullfw binary not found at {FULLFW_PATH}")
        print("Run tools/extract_fullfw.py first to extract the binary.")
        return 1
    if not SYMBOL_TABLE_PATH.exists():
        print(f"ERROR: symbol table not found at {SYMBOL_TABLE_PATH}")
        return 1

    # Verify objdump is available
    try:
        subprocess.run([OBJDUMP, "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print(f"ERROR: {OBJDUMP} not found. Install with:")
        print("  sudo apt install binutils-arm-linux-gnueabi")
        return 1

    print("=" * 70)
    print("I2C Address Pattern Scanner for Dell C410X fullfw")
    print("=" * 70)
    print()

    # Parse symbol table
    print("Parsing symbol table...")
    symbols = parse_symbol_table(SYMBOL_TABLE_PATH)
    print(f"  Loaded {len(symbols)} symbols")

    func_ranges = build_function_ranges(symbols)
    print(f"  Built function range map with {len(func_ranges)} entries")

    data_ranges = build_data_symbol_ranges(symbols)
    print(f"  Built data symbol range map with {len(data_ranges)} entries")
    print()

    # Scan disassembly for known constants
    code_matches = scan_disassembly(FULLFW_PATH, func_ranges)
    print()

    # Scan data sections for address tables
    data_matches = scan_data_sections(FULLFW_PATH, data_ranges)
    print()

    all_matches = code_matches + data_matches
    high_conf = [m for m in all_matches if m.high_confidence]
    low_conf = [m for m in all_matches if not m.high_confidence]

    # Generate report
    print("Generating report...")
    generate_report(all_matches, symbols, OUTPUT_PATH)
    print()

    # ---- Summary to stdout ----
    print("=" * 70)
    print("SCAN SUMMARY")
    print("=" * 70)
    print(f"Total matches:            {len(all_matches)}")
    print(f"  High-confidence:        {len(high_conf)}")
    print(f"  Lower-confidence:       {len(low_conf)}")
    print(f"  Code matches:           {len(code_matches)}")
    print(f"  Data section matches:   {len(data_matches)}")
    print()

    distinct = {m.constant.name for m in all_matches}
    print(f"Distinct constants found: {len(distinct)}")
    for name in sorted(distinct):
        total = sum(1 for m in all_matches if m.constant.name == name)
        high = sum(1 for m in high_conf if m.constant.name == name)
        print(f"  {name}: {high} high-conf / {total} total")

    print()
    funcs_high = {m.containing_function for m in high_conf if m.containing_function}
    print(f"PEX/I2C functions with matches: {len(funcs_high)}")

    # Top hot functions (high confidence)
    func_dc: dict[str, set[str]] = defaultdict(set)
    for m in high_conf:
        if m.containing_function:
            func_dc[m.containing_function].add(m.constant.name)
    hot_sorted = sorted(func_dc.items(), key=lambda x: len(x[1]), reverse=True)
    print()
    print("Top 10 hot functions (high-confidence, most distinct constants):")
    for func, consts in hot_sorted[:10]:
        print(f"  {func}: {len(consts)} constants ({', '.join(sorted(consts))})")

    print()
    print(f"Report saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
