# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""In-process shared state table with optional JSONL audit log."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from capcsp.shared_state.types import CapReport, CspFields


def _parse_signaling_level(level: str) -> int:
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


@runtime_checkable
class SharedStateTable(Protocol):
    """Logical CAP–CSP shared table (docs/signaling.md)."""

    def read_csp_fields(self, ue_id: int) -> CspFields | None: ...

    def write_csp_fields(self, ue_id: int, fields: CspFields, *, extensions: dict[str, Any] | None = None) -> None: ...

    def read_cap_report(self, ue_id: int) -> CapReport | None: ...

    def write_cap_report(self, ue_id: int, report: CapReport) -> None: ...


class InMemorySharedStateTable:
    """Thread-safe store with append-only JSONL writes for collaboration audit."""

    def __init__(
        self,
        *,
        signaling_level: str,
        log_path: Path | None = None,
        log_reads: bool = False,
    ) -> None:
        self._level_n = _parse_signaling_level(signaling_level)
        self._signaling_level = signaling_level.strip().upper()
        self._log_path = log_path
        self._log_reads = log_reads
        self._lock = threading.Lock()
        self._csp: dict[int, CspFields] = {}
        self._cap: dict[int, CapReport] = {}

    def _append_log(self, row: dict[str, Any]) -> None:
        if self._log_path is None:
            return
        row = {**row, "signaling_level": self._signaling_level}
        line = json.dumps(row, allow_nan=False) + "\n"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as file:
            file.write(line)

    def read_csp_fields(self, ue_id: int) -> CspFields | None:
        with self._lock:
            stored = self._csp.get(ue_id)
        result: CspFields | None
        if self._level_n == 0:
            result = None
        elif self._level_n == 1:
            if stored is None:
                result = None
            else:
                result = CspFields(
                    updated_at_s=stored.updated_at_s,
                    plan_downlink_mbps=stored.plan_downlink_mbps,
                    achieved_throughput_mbps=None,
                    rtt_ms=None,
                    loss_rate=None,
                    congestion_rate=None,
                )
        else:
            result = stored
        if self._log_reads:
            payload = asdict(result) if result is not None else None
            self._append_log(
                {
                    "record_type": "read",
                    "direction": "csp_to_cap",
                    "ue_id": ue_id,
                    "time_s": stored.updated_at_s if stored is not None else None,
                    "payload": payload,
                }
            )
        return result

    def write_csp_fields(
        self, ue_id: int, fields: CspFields, *, extensions: dict[str, Any] | None = None
    ) -> None:
        with self._lock:
            self._csp[ue_id] = fields
        payload = {"csp_fields": asdict(fields)}
        if extensions:
            payload["extensions"] = extensions
        self._append_log(
            {
                "record_type": "write",
                "direction": "csp_to_cap",
                "ue_id": ue_id,
                "time_s": fields.updated_at_s,
                "payload": payload,
            }
        )

    def read_cap_report(self, ue_id: int) -> CapReport | None:
        with self._lock:
            stored = self._cap.get(ue_id)
        if self._level_n < 3:
            result = None
        else:
            result = stored
        if self._log_reads:
            payload = asdict(result) if result is not None else None
            self._append_log(
                {
                    "record_type": "read",
                    "direction": "cap_to_csp",
                    "ue_id": ue_id,
                    "time_s": stored.time_s if stored is not None else None,
                    "payload": payload,
                }
            )
        return result

    def write_cap_report(self, ue_id: int, report: CapReport) -> None:
        with self._lock:
            self._cap[ue_id] = report
        self._append_log(
            {
                "record_type": "write",
                "direction": "cap_to_csp",
                "ue_id": ue_id,
                "time_s": report.time_s,
                "payload": {"cap_report": asdict(report)},
            }
        )
