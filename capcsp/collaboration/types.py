# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Collaboration control types (network-side actions, audit rows)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CspControlIntent:
    """Backend-agnostic control intent; adapters map this to concrete knobs."""

    priority: float | None = None
    max_downlink_mbps: float | None = None


@dataclass(frozen=True)
class ControlDecision:
    """One CSPController tick outcome for JSONL audit."""

    time_s: float
    ue_id: int
    signaling_level: str
    baseline: CspControlIntent
    proposed: CspControlIntent
    applied: bool
    reason: str

    def to_log_row(self) -> dict[str, Any]:
        return {
            "record_type": "control_proposal",
            "time_s": self.time_s,
            "ue_id": self.ue_id,
            "signaling_level": self.signaling_level,
            "baseline": asdict(self.baseline),
            "proposed": asdict(self.proposed),
            "applied": self.applied,
            "reason": self.reason,
        }
