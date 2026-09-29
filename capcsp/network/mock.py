"""Deterministic in-memory backend for contract tests (backend name `mock`).

Adapted from scripts/mock_network_backend.py in SFV-VQEG-CAP-CSP-Collaboration-Experiments
v0.7.2 by Michael Seufert:
https://github.com/micseu/SFV-VQEG-CAP-CSP-Collaboration-Experiments/blob/9d7d6f9/scripts/mock_network_backend.py

Not a TCP, HTTP or radio model. One cell byte budget per step is split equally
across active UEs, then across each UE's active requests. A cancelled request
receives at most `cancellation_tail_bytes` more before it ends.
"""

from __future__ import annotations

from dataclasses import dataclass

from capcsp.network.api import (
    DownloadCancelled,
    DownloadCompleted,
    DownloadProgress,
    NetworkEvent,
    NetworkStep,
    UeControl,
)


@dataclass
class _Request:
    ue_id: int
    request_id: str
    bytes_total: int
    bytes_delivered: int = 0
    cancelling: bool = False


class MockNetworkBackend:
    name = "mock"

    def __init__(
        self,
        *,
        ue_ids: list[int],
        duration_s: float,
        step_s: float = 0.01,
        cell_bytes_per_step: int = 80000,
        cancellation_tail_bytes: int = 512,
    ) -> None:
        if (
            not ue_ids
            or len(set(ue_ids)) != len(ue_ids)
            or any(not isinstance(ue_id, int) or ue_id < 0 for ue_id in ue_ids)
            or duration_s <= 0
            or step_s <= 0
            or cell_bytes_per_step <= 0
            or cancellation_tail_bytes < 0
        ):
            raise ValueError("Invalid mock network configuration")
        self.ue_ids = frozenset(ue_ids)
        self.duration_s = duration_s
        self.step_s = step_s
        self.budget = cell_bytes_per_step
        self.tail = cancellation_tail_bytes
        self.time_s = 0.0
        self.step_count = 0
        self.initial = True
        self.closed = False
        self.active: dict[tuple[int, str], _Request] = {}
        self.seen: set[tuple[int, str]] = set()
        # Recorded only; the mock does not emulate priority or rate caps
        self.controls: dict[int, UeControl] = {}

    def submit_request(self, ue_id: int, request_id: str, bytes_total: int) -> None:
        self._validate_ue(ue_id)
        key = (ue_id, request_id)
        if (
            self.closed
            or not isinstance(request_id, str)
            or not request_id
            or not isinstance(bytes_total, int)
            or isinstance(bytes_total, bool)
            or bytes_total <= 0
            or key in self.seen
            or self.time_s >= self.duration_s
        ):
            raise ValueError(f"Invalid mock request {key}")
        self.seen.add(key)
        self.active[key] = _Request(ue_id, request_id, bytes_total)

    def cancel_request(self, ue_id: int, request_id: str) -> None:
        self._validate_ue(ue_id)
        request = self.active.get((ue_id, request_id))
        if request is not None:
            request.cancelling = True

    def set_ue_control(self, ue_id: int, control: UeControl) -> None:
        self._validate_ue(ue_id)
        self.controls[ue_id] = control

    def advance(self) -> NetworkStep:
        if self.closed:
            raise RuntimeError("Backend already closed")
        if self.initial:
            self.initial = False
            return NetworkStep(0.0, [], False)
        if self.time_s >= self.duration_s:
            raise RuntimeError("Backend already emitted its final step")
        self.step_count += 1
        self.time_s = min(round(self.step_count * self.step_s, 9), self.duration_s)
        events: list[NetworkEvent] = []
        active_ues = sorted({request.ue_id for request in self.active.values()})
        for ue_id in active_ues:
            pending = sorted(
                (request for request in self.active.values() if request.ue_id == ue_id),
                key=lambda request: request.request_id,
            )
            share = self.budget // len(active_ues) // len(pending)
            for request in pending:
                amount = min(
                    request.bytes_total - request.bytes_delivered,
                    min(share, self.tail) if request.cancelling else share,
                )
                request.bytes_delivered += amount
                if amount:
                    events.append(
                        DownloadProgress(ue_id, request.request_id, request.bytes_delivered, self.time_s)
                    )
                if request.cancelling:
                    events.append(
                        DownloadCancelled(ue_id, request.request_id, request.bytes_delivered, self.time_s)
                    )
                    del self.active[(ue_id, request.request_id)]
                elif request.bytes_delivered == request.bytes_total:
                    events.append(DownloadCompleted(ue_id, request.request_id, self.time_s))
                    del self.active[(ue_id, request.request_id)]
        return NetworkStep(self.time_s, events, self.time_s >= self.duration_s)

    def close(self) -> None:
        self.closed = True
        self.active.clear()

    def _validate_ue(self, ue_id: int) -> None:
        if ue_id not in self.ue_ids:
            raise ValueError(f"Unknown UE {ue_id}")
