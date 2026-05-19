"""Parsers for human-readable byte sizes."""

from __future__ import annotations

import re

# Decimal (SI) and binary (IEC) suffixes, both forms accepted.
_UNIT_MULTIPLIERS: dict[str, int] = {
    "": 1,
    "B": 1,
    "K": 1_000, "KB": 1_000, "KIB": 1024,
    "M": 1_000_000, "MB": 1_000_000, "MIB": 1024**2,
    "G": 1_000_000_000, "GB": 1_000_000_000, "GIB": 1024**3,
    "T": 1_000_000_000_000, "TB": 1_000_000_000_000, "TIB": 1024**4,
}

_SIZE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]*)\s*$")


def parse_bytes(value: str | int | float | None) -> int | None:
    """Parse a size string into bytes.

    Accepts ``"512MB"``, ``"1.5GiB"``, ``"1024"`` (raw bytes), ints, floats.
    Returns ``None`` for missing/unparseable/zero input.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        n = int(value)
        return n if n > 0 else None
    match = _SIZE_RE.match(value)
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2).upper()
    mult = _UNIT_MULTIPLIERS.get(suffix)
    if mult is None:
        return None
    out = int(number * mult)
    return out if out > 0 else None


def bytes_to_mb(value: int | None) -> int | None:
    """Convert bytes to megabytes (decimal, rounded to nearest)."""
    if value is None:
        return None
    return max(1, round(value / 1_000_000))


def parse_to_mb(value: str | int | float | None) -> int | None:
    """Shortcut: parse a size string and return MB."""
    return bytes_to_mb(parse_bytes(value))
