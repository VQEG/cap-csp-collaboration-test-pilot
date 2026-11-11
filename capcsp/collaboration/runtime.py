# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Step-synchronized collaboration tick (see docs/collaboration.md)."""

from __future__ import annotations

from typing import Any

from capcsp.collaboration.factory import CollaborationContext
from capcsp.collaboration.snapshot import build_collaboration_payload
from capcsp.network.api import NetworkBackend

def player_facing_network_step(step_dict: dict[str, Any], *, collaboration: dict[str, Any]) -> dict[str, Any]:
    """Byte-path events of the step plus the filtered collaboration snapshot."""
    return {
        "time_s": step_dict["time_s"],
        "is_final": step_dict["is_final"],
        "events": step_dict["events"],
        "collaboration": collaboration,
    }


def apply_player_network_events(
    step_dict: dict[str, Any],
    *,
    ue_ids: set[int],
    sizes: dict[tuple[int, str], int],
    delivered: dict[tuple[int, str], int],
    terminal: set[tuple[int, str]],
) -> None:
    """Validate the download events of a step against the submitted requests."""
    for event in step_dict["events"]:
        if event["ue_id"] not in ue_ids:
            raise ValueError(f"Event for unknown UE {event['ue_id']}")
        if event["event_type"] == "NetworkTelemetryReceived":
            raise ValueError(
                "NetworkTelemetryReceived inside a NetworkStep is not supported; "
                "expose a csp_telemetry source on the backend instead"
            )
        key = (event["ue_id"], event["request_id"])
        if key not in sizes or key in terminal:
            raise ValueError(f"Event for unknown or finished request {key}")
        if "bytes_delivered" in event:
            if not delivered[key] <= event["bytes_delivered"] <= sizes[key]:
                raise ValueError(f"Invalid cumulative byte count for {key}")
            delivered[key] = event["bytes_delivered"]
        if event["event_type"] == "DownloadCompleted":
            delivered[key] = sizes[key]
            terminal.add(key)
        elif event["event_type"] == "DownloadCancelled":
            terminal.add(key)


def run_collaboration_tick(
    step_dict: dict[str, Any],
    *,
    bridge: Any,
    collaboration: CollaborationContext,
    ue_ids: set[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attach collaboration view, player step, CAP reports, and optional CSPController."""
    collaboration_payload = build_collaboration_payload(
        ue_ids=ue_ids,
        table=collaboration.table,
        signaling_level=collaboration.signaling_level,
    )
    player_step = player_facing_network_step(step_dict, collaboration=collaboration_payload)
    response = bridge.on_step(player_step)
    logged_step = player_step
    collaboration.cap_reporter.fetch_and_write(collaboration.table, ue_ids)
    if collaboration.csp_controller is not None:
        collaboration.csp_controller.on_collaboration_tick(
            time_s=float(step_dict["time_s"]),
            ue_ids=ue_ids,
            table=collaboration.table,
            control=collaboration.control,
        )
    return response, logged_step


def apply_player_actions(
    backend: NetworkBackend,
    response: dict[str, Any],
    *,
    ue_ids: set[int],
    sizes: dict[tuple[int, str], int],
    delivered: dict[tuple[int, str], int],
) -> None:
    if response.get("type") != "player_actions":
        return
    for action in response["actions"]:
        key = (action.get("ue_id"), action.get("request_id"))
        if key[0] not in ue_ids or not isinstance(key[1], str) or not key[1]:
            raise ValueError(f"Invalid request identity {key}")
        if action.get("op") == "submit_request":
            size = action.get("bytes_total")
            if key in sizes:
                raise ValueError(f"Duplicate request ID {key}")
            if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                raise ValueError(f"Invalid byte count for {key}")
            backend.submit_request(key[0], key[1], size)
            sizes[key] = size
            delivered[key] = 0
        elif action.get("op") == "cancel_request":
            backend.cancel_request(key[0], key[1])
        else:
            raise ValueError(f"Unknown player action {action.get('op')!r}")
