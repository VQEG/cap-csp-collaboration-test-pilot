# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Ingest network step events into the shared state table."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from capcsp.collaboration.adapters.fikore_mapper import map_step_event_to_csp
from capcsp.shared_state.table import SharedStateTable


class CspTelemetrySource(Protocol):
    def ingest_step_events(self, events: list[dict[str, Any]]) -> None: ...


class StepEventCspTelemetrySource:
    """Write CspFields from ``NetworkTelemetryReceived`` rows in a NetworkStep."""

    def __init__(
        self,
        table: SharedStateTable,
        *,
        plan_downlink_mbps_by_ue: dict[int, float] | None = None,
    ) -> None:
        self._table = table
        self._plans = plan_downlink_mbps_by_ue or {}

    def ingest_step_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            if event.get("event_type") != "NetworkTelemetryReceived":
                continue
            ue_id = int(event["ue_id"])
            csp_fields, extensions = map_step_event_to_csp(
                event,
                plan_downlink_mbps=self._plans.get(ue_id),
            )
            self._table.write_csp_fields(ue_id, csp_fields, extensions=extensions)


def append_flat_telemetry(telemetry: list[dict[str, Any]], event: dict[str, Any]) -> None:
    """Append one row to ``telemetry.jsonl`` aggregate (legacy shape)."""
    fields = event.get("fields")
    if isinstance(fields, dict):
        telemetry.append({"ue_id": event["ue_id"], "time_s": event["time_s"], **fields})
    else:
        telemetry.append({"ue_id": event["ue_id"], "time_s": event["time_s"]})


def csp_fields_to_json(fields: Any) -> dict[str, Any] | None:
    if fields is None:
        return None
    return asdict(fields)
