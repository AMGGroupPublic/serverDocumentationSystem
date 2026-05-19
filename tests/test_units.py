"""Unit-size parser tests."""

from __future__ import annotations

import pytest

from serverdocs.units import bytes_to_mb, parse_bytes, parse_to_mb


@pytest.mark.parametrize(
    "value,expected",
    [
        ("512MB", 512_000_000),
        ("1GB", 1_000_000_000),
        ("1GiB", 1024**3),
        ("1.5GiB", int(1.5 * 1024**3)),
        ("1024", 1024),
        (512, 512),
        (0, None),
        (None, None),
        ("", None),
        ("garbage", None),
    ],
)
def test_parse_bytes(value: object, expected: int | None) -> None:
    assert parse_bytes(value) == expected  # type: ignore[arg-type]


def test_parse_to_mb_roundtrip() -> None:
    assert parse_to_mb("512MB") == 512
    assert parse_to_mb("1GiB") == 1074  # 1.073... → 1074


def test_bytes_to_mb_none() -> None:
    assert bytes_to_mb(None) is None
    assert bytes_to_mb(1_000_000) == 1
