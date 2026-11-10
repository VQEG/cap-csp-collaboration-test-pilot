# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Dataclasses for the shared state table (see docs/signaling.md)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CspFields:
    """Fields exposed from the CSP / network side toward the CAP."""

    updated_at_s: float
    plan_downlink_mbps: float | None
    achieved_throughput_mbps: float | None
    rtt_ms: float | None
    loss_rate: float | None
    congestion_rate: float | None


@dataclass(frozen=True)
class CapReport:
    """Application telemetry from the CAP toward a network controller."""

    time_s: float
    is_stalled: bool
    playable_buffer_s: float
    current_video_id: str
    swipe_rate_per_s: float
