# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Signaling level parsing (docs/signaling.md)."""

from __future__ import annotations


def parse_signaling_level(level: str) -> int:
    """Return 0–4 for ``L0``…``L4``."""
    raw = level.strip().upper()
    if not raw.startswith("L") or len(raw) != 2:
        raise ValueError(f"signaling_level must be L0–L4, got {level!r}")
    try:
        n = int(raw[1])
    except ValueError as exc:
        raise ValueError(f"signaling_level must be L0–L4, got {level!r}") from exc
    if n not in range(5):
        raise ValueError(f"signaling_level must be L0–L4, got {level!r}")
    return n
