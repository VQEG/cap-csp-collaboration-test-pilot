"""Network Backend API types (docs/network-backend-api.md).

The dataclasses come from fikore_transport/backend.py in the FikoRE submodule,
which is the Python reference. This module adds the protocols and serialization.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Protocol

from fikore_transport.backend import (
    DownloadCancelled,
    DownloadCompleted,
    DownloadProgress,
    NetworkEvent,
    NetworkStep,
    NetworkTelemetry,
    NetworkTelemetryReceived,
    UeControl,
)

__all__ = [
    "ControllableNetworkBackend",
    "DownloadCancelled",
    "DownloadCompleted",
    "DownloadProgress",
    "NetworkBackend",
    "NetworkEvent",
    "NetworkStep",
    "NetworkTelemetry",
    "NetworkTelemetryReceived",
    "UeControl",
    "event_to_dict",
    "step_to_dict",
]


class NetworkBackend(Protocol):
    def submit_request(self, ue_id: int, request_id: str, bytes_total: int) -> None: ...

    def cancel_request(self, ue_id: int, request_id: str) -> None: ...

    def advance(self) -> NetworkStep: ...

    def close(self) -> None: ...


class ControllableNetworkBackend(NetworkBackend, Protocol):
    def set_ue_control(self, ue_id: int, control: UeControl) -> None: ...


def event_to_dict(event: Any) -> dict[str, Any]:
    """Serialize an event by class name and fields."""
    return {"event_type": type(event).__name__, **asdict(event)}


def step_to_dict(step: NetworkStep) -> dict[str, Any]:
    """Serialize a NetworkStep for the player process and the transcript."""
    if not math.isfinite(step.time_s) or step.time_s < 0:
        raise ValueError(f"Invalid backend time {step.time_s}")
    for event in step.events:
        if event.time_s < 0 or event.time_s > step.time_s + 1e-9:
            raise ValueError(f"Event at {event.time_s} s lies outside its step at {step.time_s} s")
    return {
        "time_s": step.time_s,
        "events": [event_to_dict(event) for event in step.events],
        "is_final": step.is_final,
    }
