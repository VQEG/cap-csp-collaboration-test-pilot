# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Map network backend telemetry into :class:`CspFields`.

The pilot :class:`~fikore_transport.backend.NetworkTelemetry` combines
measurements from the modelled TCP stack (e.g. round-trip time from SACK timing)
with counters and radio-path hints returned by FikoRE via
:class:`~fikore_transport.fikore_link.FikoreLink` (throughput, drops, ECN rate,
SINR, queue depth, one-way PDCP delay). The narrow :class:`CspFields` schema in
``docs/signaling.md`` holds collaboration-facing numbers; extra keys are kept in
``extensions`` for audit JSONL only until a future split of transport vs access.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from fikore_transport.backend import NetworkTelemetry

from capcsp.shared_state.types import CspFields

_NETWORK_TELEMETRY_KEYS = {f.name for f in fields(NetworkTelemetry)}


def network_telemetry_from_step_event(event: dict[str, Any]) -> NetworkTelemetry:
    """Build :class:`NetworkTelemetry` from a serialized ``NetworkTelemetryReceived`` row."""
    nested = event.get("fields")
    source = nested if isinstance(nested, dict) else event
    merged = {key: source[key] for key in _NETWORK_TELEMETRY_KEYS if key in source}
    return NetworkTelemetry(**merged)


def network_telemetry_to_csp_fields(
    *,
    time_s: float,
    telemetry: NetworkTelemetry,
    plan_downlink_mbps: float | None = None,
) -> tuple[CspFields, dict[str, Any]]:
    """Return collaboration fields plus extensions for JSONL audit rows.

    ``loss_rate`` is populated from ``telemetry.drop_rate`` (byte loss share in
    the transport window). ``congestion_rate`` uses ECN marking rate when
    present.
    """
    extensions: dict[str, Any] = {}
    if telemetry.ip_latency_ms is not None:
        extensions["ip_latency_ms"] = telemetry.ip_latency_ms
    if telemetry.pdcp_latency_ms is not None:
        extensions["pdcp_latency_ms"] = telemetry.pdcp_latency_ms
    if telemetry.retransmitted_bytes is not None:
        extensions["retransmitted_bytes"] = telemetry.retransmitted_bytes
    if telemetry.sinr_db is not None:
        extensions["sinr_db"] = telemetry.sinr_db
    if telemetry.queue_bytes is not None:
        extensions["queue_bytes"] = telemetry.queue_bytes

    csp_fields = CspFields(
        updated_at_s=time_s,
        plan_downlink_mbps=plan_downlink_mbps,
        achieved_throughput_mbps=telemetry.throughput_mbps,
        rtt_ms=telemetry.rtt_ms,
        loss_rate=telemetry.drop_rate,
        congestion_rate=telemetry.ce_rate,
    )
    return csp_fields, extensions
