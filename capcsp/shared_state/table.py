# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""In-process shared state table with optional JSONL audit log."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, TextIO, runtime_checkable

from capcsp.shared_state.signaling import parse_signaling_level
from capcsp.shared_state.types import CapReport, CspFields


@runtime_checkable
class SharedStateTable(Protocol):
    """Logical CAP–CSP shared table (docs/signaling.md)."""

    def read_csp_fields(self, ue_id: int) -> CspFields | None: ...

    def write_csp_fields(self, ue_id: int, fields: CspFields, *, extensions: dict[str, Any] | None = None) -> None: ...

    def read_cap_report(self, ue_id: int) -> CapReport | None: ...

    def write_cap_report(self, ue_id: int, report: CapReport) -> None: ...

    def close(self) -> None: ...


class InMemorySharedStateTable:
    """Thread-safe store with append-only JSONL audit on value changes."""

    def __init__(
        self,
        *,
        signaling_level: str,
        log_path: Path | None = None,
        log_reads: bool = False,
    ) -> None:
        self._level_n = parse_signaling_level(signaling_level)
        self._signaling_level = signaling_level.strip().upper()
        self._log_path = log_path
        self._log_reads = log_reads
        self._log_file: TextIO | None = None
        self._lock = threading.Lock()
        self._csp: dict[int, CspFields] = {}
        self._cap: dict[int, CapReport] = {}
        self._last_logged_csp: dict[int, tuple[Any, ...]] = {}
        self._last_logged_cap: dict[int, CapReport] = {}

    def close(self) -> None:
        with self._lock:
            if self._log_file is not None:
                self._log_file.close()
                self._log_file = None

    def _ensure_log_file(self) -> TextIO | None:
        if self._log_path is None:
            return None
        if self._log_file is None:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = self._log_path.open("a", encoding="utf-8")
        return self._log_file

    def _append_log(self, row: dict[str, Any]) -> None:
        file = self._ensure_log_file()
        if file is None:
            return
        row = {**row, "signaling_level": self._signaling_level}
        line = json.dumps(row, allow_nan=False) + "\n"
        file.write(line)
        file.flush()

    @staticmethod
    def _csp_log_key(fields: CspFields, extensions: dict[str, Any] | None) -> tuple[Any, ...]:
        ext_key = json.dumps(extensions, sort_keys=True, allow_nan=False) if extensions else None
        return (asdict(fields), ext_key)

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
        log_key = self._csp_log_key(fields, extensions)
        with self._lock:
            if self._last_logged_csp.get(ue_id) == log_key:
                self._csp[ue_id] = fields
                return
            self._csp[ue_id] = fields
            self._last_logged_csp[ue_id] = log_key
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
            if self._last_logged_cap.get(ue_id) == report:
                self._cap[ue_id] = report
                return
            self._cap[ue_id] = report
            self._last_logged_cap[ue_id] = report
        self._append_log(
            {
                "record_type": "write",
                "direction": "cap_to_csp",
                "ue_id": ue_id,
                "time_s": report.time_s,
                "payload": {"cap_report": asdict(report)},
            }
        )
