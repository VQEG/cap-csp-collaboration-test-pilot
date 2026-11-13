"""Deterministic constant-rate backend (backend name `constant_rate`).

Not a TCP, HTTP or radio model. Every UE has its own dedicated downlink rate,
so UEs never compete with each other. Within a UE, the requests that are
ready share the UE rate equally (processor sharing): when one request
finishes inside a step, its share goes to the others for the rest of that
step. A request receives no bytes until `synthetic_delay_ms` after it was
submitted, which stands in for the application, origin and core-network delay.

The fluid byte state is kept as exact fractions, so delivered bytes equal
rate x time without rounding drift. Events report whole bytes (rounded down)
and carry the time of the step in which they happen, like the other backends.

Mirrors the per-UE behaviour of SFVConstantRateTransport in the SFV reference
implementation, which assumes the constant per-user bandwidth of the analytical
model of Wehner et al.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from capcsp.network.api import (
    DownloadCancelled,
    DownloadCompleted,
    DownloadProgress,
    NetworkEvent,
    NetworkStep,
    UeControl,
)

BITS_PER_BYTE = 8
BITS_PER_MEGABIT = 1_000_000
MILLISECONDS_PER_SECOND = 1000


def _exact_positive_number(value: Any, description: str, *, allow_zero: bool = False) -> Fraction:
    """Return `value` as an exact fraction of its decimal notation (0.01 becomes 1/100)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{description} must be a finite number, got {value!r}")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{description} must be {'non-negative' if allow_zero else 'positive'}, got {value!r}")
    return Fraction(str(value))


def _megabits_per_second_to_bytes_per_second(rate_mbps: Fraction) -> Fraction:
    return rate_mbps * BITS_PER_MEGABIT / BITS_PER_BYTE


@dataclass
class _ConstantRateRequest:
    ue_id: int
    request_id: str
    bytes_total: int
    first_byte_allowed_at_s: Fraction
    fluid_bytes_delivered: Fraction = Fraction(0)
    reported_bytes_delivered: int = 0
    # Equal to bytes_total until cancellation lowers it to the delivered bytes plus the tail
    bytes_delivered_limit: int = 0
    cancelling: bool = False

    def __post_init__(self) -> None:
        self.bytes_delivered_limit = self.bytes_total

    def remaining_bytes(self) -> Fraction:
        return self.bytes_delivered_limit - self.fluid_bytes_delivered


class ConstantRateBackend:
    name = "constant_rate"

    def __init__(
        self,
        *,
        ue_ids: list[int],
        duration_s: float,
        step_s: float = 0.01,
        downlink_rate_mbps: float | None = None,
        downlink_rate_mbps_by_ue: dict[int | str, float] | None = None,
        synthetic_delay_ms: float = 0,
        cancellation_tail_bytes: int = 0,
    ) -> None:
        if (
            not isinstance(ue_ids, list)
            or not ue_ids
            or len(set(ue_ids)) != len(ue_ids)
            or any(not isinstance(ue_id, int) or isinstance(ue_id, bool) or ue_id < 0 for ue_id in ue_ids)
        ):
            raise ValueError("ue_ids must be a non-empty list of unique non-negative integers")
        if (
            isinstance(cancellation_tail_bytes, bool)
            or not isinstance(cancellation_tail_bytes, int)
            or cancellation_tail_bytes < 0
        ):
            raise ValueError("cancellation_tail_bytes must be a non-negative integer")
        self.ue_ids = frozenset(ue_ids)
        self.duration_s = _exact_positive_number(duration_s, "duration_s")
        self.step_s = _exact_positive_number(step_s, "step_s")
        self.synthetic_delay_s = (
            _exact_positive_number(synthetic_delay_ms, "synthetic_delay_ms", allow_zero=True)
            / MILLISECONDS_PER_SECOND
        )
        self.cancellation_tail_bytes = cancellation_tail_bytes
        self.configured_downlink_rate_mbps_by_ue = self._configured_rates(
            downlink_rate_mbps, downlink_rate_mbps_by_ue
        )
        # Set by set_ue_control; a cap only ever lowers the configured rate
        self.downlink_rate_cap_mbps_by_ue: dict[int, Fraction] = {}
        # Recorded only: with a dedicated rate per UE there is nothing to prioritize against
        self.priority_by_ue: dict[int, float] = {}
        self.controls: dict[int, UeControl] = {}
        self.current_time_s = Fraction(0)
        self.step_count = 0
        self.initial_step_pending = True
        self.closed = False
        self.active_requests: dict[tuple[int, str], _ConstantRateRequest] = {}
        self.submitted_request_keys: set[tuple[int, str]] = set()

    def _configured_rates(
        self,
        downlink_rate_mbps: float | None,
        downlink_rate_mbps_by_ue: dict[int | str, float] | None,
    ) -> dict[int, Fraction]:
        overrides: dict[int, Fraction] = {}
        if downlink_rate_mbps_by_ue is not None:
            if not isinstance(downlink_rate_mbps_by_ue, dict):
                raise ValueError("downlink_rate_mbps_by_ue must map UE IDs to rates in Mbps")
            for raw_ue_id, rate_mbps in downlink_rate_mbps_by_ue.items():
                try:
                    ue_id = int(raw_ue_id)
                except (TypeError, ValueError):
                    raise ValueError(f"downlink_rate_mbps_by_ue has an invalid UE ID {raw_ue_id!r}") from None
                if ue_id not in self.ue_ids:
                    raise ValueError(f"downlink_rate_mbps_by_ue names unknown UE {ue_id}")
                if ue_id in overrides:
                    raise ValueError(f"downlink_rate_mbps_by_ue names UE {ue_id} twice")
                overrides[ue_id] = _exact_positive_number(rate_mbps, f"downlink_rate_mbps_by_ue[{ue_id}]")
        default_rate = (
            None
            if downlink_rate_mbps is None
            else _exact_positive_number(downlink_rate_mbps, "downlink_rate_mbps")
        )
        rates: dict[int, Fraction] = {}
        for ue_id in sorted(self.ue_ids):
            rate = overrides.get(ue_id, default_rate)
            if rate is None:
                raise ValueError(f"UE {ue_id} has no rate: set downlink_rate_mbps or downlink_rate_mbps_by_ue")
            rates[ue_id] = rate
        return rates

    @property
    def time_s(self) -> float:
        return float(self.current_time_s)

    def effective_downlink_rate_mbps(self, ue_id: int) -> float:
        """Configured rate of `ue_id`, lowered to its rate cap if one is set."""
        self._validate_ue(ue_id)
        return float(self._effective_downlink_rate_mbps(ue_id))

    def _effective_downlink_rate_mbps(self, ue_id: int) -> Fraction:
        configured = self.configured_downlink_rate_mbps_by_ue[ue_id]
        cap = self.downlink_rate_cap_mbps_by_ue.get(ue_id)
        return configured if cap is None else min(configured, cap)

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
            or key in self.submitted_request_keys
            or self.current_time_s >= self.duration_s
        ):
            raise ValueError(f"Invalid constant-rate request {key}")
        self.submitted_request_keys.add(key)
        self.active_requests[key] = _ConstantRateRequest(
            ue_id=ue_id,
            request_id=request_id,
            bytes_total=bytes_total,
            first_byte_allowed_at_s=self.current_time_s + self.synthetic_delay_s,
        )

    def cancel_request(self, ue_id: int, request_id: str) -> None:
        self._validate_ue(ue_id)
        request = self.active_requests.get((ue_id, request_id))
        if request is None or request.cancelling:
            return
        request.cancelling = True
        if request.first_byte_allowed_at_s > self.current_time_s:
            # Still within the synthetic delay: no bytes are on their way yet
            request.bytes_delivered_limit = request.reported_bytes_delivered
        else:
            request.bytes_delivered_limit = min(
                request.bytes_total, request.reported_bytes_delivered + self.cancellation_tail_bytes
            )

    def set_ue_control(self, ue_id: int, control: UeControl) -> None:
        """Apply a rate cap from the next step on. As in FikoRE, `rmax_mbps=0` removes the cap
        and `None` leaves it (and the recorded priority) unchanged."""
        self._validate_ue(ue_id)
        if control.rmax_mbps is not None:
            cap = _exact_positive_number(control.rmax_mbps, "rmax_mbps", allow_zero=True)
            if cap == 0:
                self.downlink_rate_cap_mbps_by_ue.pop(ue_id, None)
            else:
                self.downlink_rate_cap_mbps_by_ue[ue_id] = cap
        if control.priority is not None:
            self.priority_by_ue[ue_id] = control.priority
        self.controls[ue_id] = control

    def advance(self) -> NetworkStep:
        if self.closed:
            raise RuntimeError("Backend already closed")
        if self.initial_step_pending:
            self.initial_step_pending = False
            return NetworkStep(0.0, [], False)
        if self.current_time_s >= self.duration_s:
            raise RuntimeError("Backend already emitted its final step")
        step_start_s = self.current_time_s
        self.step_count += 1
        step_end_s = min(self.step_count * self.step_s, self.duration_s)
        events: list[NetworkEvent] = []
        for ue_id in sorted(self.ue_ids):
            requests = sorted(
                (request for request in self.active_requests.values() if request.ue_id == ue_id),
                key=lambda request: request.request_id,
            )
            if not requests:
                continue
            self._share_rate_between(requests, ue_id, step_start_s, step_end_s)
            events.extend(self._finish_step(requests, float(step_end_s)))
        self.current_time_s = step_end_s
        return NetworkStep(float(step_end_s), events, step_end_s >= self.duration_s)

    def _share_rate_between(
        self,
        requests: list[_ConstantRateRequest],
        ue_id: int,
        step_start_s: Fraction,
        step_end_s: Fraction,
    ) -> None:
        """Deliver the UE rate over the step to the ready requests, in equal shares.

        The step is split at every instant where a request becomes ready or reaches
        its byte limit, so the share of a finished request goes to the others.
        """
        ue_rate_bytes_per_s = _megabits_per_second_to_bytes_per_second(self._effective_downlink_rate_mbps(ue_id))
        interval_start_s = step_start_s
        while interval_start_s < step_end_s:
            transferring = [
                request
                for request in requests
                if request.first_byte_allowed_at_s <= interval_start_s and request.remaining_bytes() > 0
            ]
            next_ready_s = min(
                (
                    request.first_byte_allowed_at_s
                    for request in requests
                    if request.first_byte_allowed_at_s > interval_start_s
                ),
                default=step_end_s,
            )
            interval_end_s = min(step_end_s, next_ready_s)
            if transferring:
                share_bytes_per_s = ue_rate_bytes_per_s / len(transferring)
                first_finish_s = interval_start_s + (
                    min(request.remaining_bytes() for request in transferring) / share_bytes_per_s
                )
                interval_end_s = min(interval_end_s, first_finish_s)
                share_bytes = share_bytes_per_s * (interval_end_s - interval_start_s)
                for request in transferring:
                    request.fluid_bytes_delivered = min(
                        request.fluid_bytes_delivered + share_bytes, Fraction(request.bytes_delivered_limit)
                    )
            interval_start_s = interval_end_s

    def _finish_step(self, requests: list[_ConstantRateRequest], time_s: float) -> list[NetworkEvent]:
        events: list[NetworkEvent] = []
        for request in requests:
            whole_bytes_delivered = math.floor(request.fluid_bytes_delivered)
            if whole_bytes_delivered > request.reported_bytes_delivered:
                request.reported_bytes_delivered = whole_bytes_delivered
                events.append(DownloadProgress(request.ue_id, request.request_id, whole_bytes_delivered, time_s))
            if request.remaining_bytes() > 0:
                continue
            if request.cancelling:
                events.append(
                    DownloadCancelled(request.ue_id, request.request_id, request.reported_bytes_delivered, time_s)
                )
            else:
                events.append(DownloadCompleted(request.ue_id, request.request_id, time_s))
            del self.active_requests[(request.ue_id, request.request_id)]
        return events

    def close(self) -> None:
        self.closed = True
        self.active_requests.clear()

    def _validate_ue(self, ue_id: int) -> None:
        if ue_id not in self.ue_ids:
            raise ValueError(f"Unknown UE {ue_id}")
