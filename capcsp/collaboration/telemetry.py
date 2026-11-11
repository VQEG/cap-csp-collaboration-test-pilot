# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Write sampled network telemetry into the shared state table.

CSP telemetry does not travel in the NetworkStep. A backend that can observe
its network exposes a ``csp_telemetry`` source (for ``transport_fikore``, a
FikoRE ``NetworkTelemetrySampler``); the runtime polls it once per step.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from capcsp.collaboration.adapters.fikore_mapper import map_step_event_to_csp
from capcsp.network.api import NetworkTelemetryReceived, event_to_dict
from capcsp.shared_state.table import SharedStateTable


class CspTelemetrySource(Protocol):
    def poll(self, *, force: bool = False) -> list[NetworkTelemetryReceived]: ...


class NoCspTelemetry:
    """Source for backends that observe no network, such as the mock."""

    def poll(self, *, force: bool = False) -> list[NetworkTelemetryReceived]:
        return []


class CspTelemetryWriter:
    """Poll a :class:`CspTelemetrySource` and write each sample as CspFields."""

    def __init__(
        self,
        table: SharedStateTable,
        source: CspTelemetrySource,
        *,
        plan_downlink_mbps_by_ue: dict[int, float] | None = None,
    ) -> None:
        self._table = table
        self._source = source
        self._plans = plan_downlink_mbps_by_ue or {}

    def poll_and_write(self, *, force: bool = False) -> list[dict[str, Any]]:
        """Write the samples due now; return them as ``telemetry.jsonl`` rows."""
        rows = []
        for sample in self._source.poll(force=force):
            event = event_to_dict(sample)
            csp_fields, extensions = map_step_event_to_csp(
                event,
                plan_downlink_mbps=self._plans.get(sample.ue_id),
            )
            self._table.write_csp_fields(sample.ue_id, csp_fields, extensions=extensions)
            rows.append(flat_telemetry_row(event))
        return rows


def flat_telemetry_row(event: dict[str, Any]) -> dict[str, Any]:
    """One ``telemetry.jsonl`` row: UE, time and the telemetry fields."""
    fields = event.get("fields")
    if isinstance(fields, dict):
        return {"ue_id": event["ue_id"], "time_s": event["time_s"], **fields}
    return {"ue_id": event["ue_id"], "time_s": event["time_s"]}


def csp_fields_to_json(fields: Any) -> dict[str, Any] | None:
    if fields is None:
        return None
    return asdict(fields)
