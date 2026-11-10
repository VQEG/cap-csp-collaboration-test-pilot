# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Map FikoRE-shaped step telemetry into collaboration CspFields."""

from __future__ import annotations

from typing import Any

from capcsp.shared_state.mapping import network_telemetry_from_step_event, network_telemetry_to_csp_fields

__all__ = ["map_step_event_to_csp"]


def map_step_event_to_csp(
    event: dict[str, Any],
    *,
    plan_downlink_mbps: float | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Return (:class:`CspFields`, extensions) from a serialized telemetry event."""
    nt = network_telemetry_from_step_event(event)
    return network_telemetry_to_csp_fields(
        time_s=float(event["time_s"]),
        telemetry=nt,
        plan_downlink_mbps=plan_downlink_mbps,
    )
