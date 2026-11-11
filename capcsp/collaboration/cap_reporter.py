# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Collect CAP telemetry reports into the shared state table."""

from __future__ import annotations

from typing import Any, Protocol

from capcsp.shared_state.table import SharedStateTable
from capcsp.shared_state.types import CapReport


class CapReporter(Protocol):
    def fetch_and_write(self, table: SharedStateTable, ue_ids: set[int]) -> None: ...


class SfVCapReporter:
    """SFV harness: ``cap_reports`` IPC on the Node player bridge.

    The reply holds only reports SFV drained since the previous step (stall edges, video
    switches, buffer threshold crossings, at most one per second per UE); it is often ``{}``.
    """

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    def fetch_and_write(self, table: SharedStateTable, ue_ids: set[int]) -> None:
        cap_reply = self._bridge.exchange({"type": "cap_reports"})
        if cap_reply.get("type") != "cap_reports" or not isinstance(cap_reply.get("reports"), dict):
            raise RuntimeError(f"Unexpected cap_reports reply: {cap_reply!r}")
        for raw_id, payload in cap_reply["reports"].items():
            ue_id = int(raw_id)
            if ue_id not in ue_ids or not isinstance(payload, dict):
                continue
            report = CapReport(
                time_s=float(payload["time_s"]),
                is_stalled=bool(payload["is_stalled"]),
                playable_buffer_s=float(payload["playable_buffer_s"]),
                current_video_id=str(payload["current_video_id"]),
                swipe_rate_per_s=float(payload["swipe_rate_per_s"]),
            )
            table.write_cap_report(ue_id, report)
