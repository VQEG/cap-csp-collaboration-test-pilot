# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Network-side controller reading CAP reports from the shared state table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from capcsp.collaboration.types import ControlDecision, CspControlIntent
from capcsp.shared_state.table import SharedStateTable, _parse_signaling_level


class BackendControlAdapter(Protocol):
    def read_baseline(self, ue_id: int) -> CspControlIntent: ...

    def apply(self, ue_id: int, intent: CspControlIntent) -> None: ...


class CSPController(Protocol):
    def on_collaboration_tick(
        self,
        *,
        time_s: float,
        ue_ids: set[int],
        table: SharedStateTable,
        control: BackendControlAdapter,
    ) -> list[ControlDecision]: ...


class DummyCSPController:
    """Records stall-based priority proposals; does not call the control adapter."""

    def __init__(
        self,
        *,
        signaling_level: str,
        log_path: Path | None = None,
        stall_priority_multiplier: float = 2.0,
    ) -> None:
        self._signaling_level = signaling_level.strip().upper()
        self._log_path = log_path
        self._stall_priority_multiplier = stall_priority_multiplier

    def on_collaboration_tick(
        self,
        *,
        time_s: float,
        ue_ids: set[int],
        table: SharedStateTable,
        control: BackendControlAdapter,
    ) -> list[ControlDecision]:
        if _parse_signaling_level(self._signaling_level) < 3:
            return []
        decisions: list[ControlDecision] = []
        for ue_id in sorted(ue_ids):
            report = table.read_cap_report(ue_id)
            if report is None:
                continue
            baseline = control.read_baseline(ue_id)
            proposed = baseline
            reason = "dummy_no_change"
            if report.is_stalled and baseline.priority is not None:
                proposed = CspControlIntent(
                    priority=baseline.priority * self._stall_priority_multiplier,
                    max_downlink_mbps=baseline.max_downlink_mbps,
                )
                reason = "dummy_stall_boost"
            decision = ControlDecision(
                time_s=time_s,
                ue_id=ue_id,
                signaling_level=self._signaling_level,
                baseline=baseline,
                proposed=proposed,
                applied=False,
                reason=reason,
            )
            decisions.append(decision)
            self._append_log(decision)
        return decisions

    def _append_log(self, decision: ControlDecision) -> None:
        if self._log_path is None:
            return
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(decision.to_log_row(), allow_nan=False) + "\n"
        with self._log_path.open("a", encoding="utf-8") as file:
            file.write(line)
