"""Unit tests of the `constant_rate` network backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from capcsp.collaboration.factory import build_collaboration_stack
from capcsp.collaboration.types import CspControlIntent
from capcsp.network.api import (
    DownloadCancelled,
    DownloadCompleted,
    DownloadProgress,
    NetworkStep,
    UeControl,
)
from capcsp.network.constant_rate import ConstantRateBackend
from capcsp.shared_state.table import InMemorySharedStateTable


def make_backend(**overrides: object) -> ConstantRateBackend:
    settings: dict[str, object] = {"ue_ids": [0, 1], "duration_s": 10.0, "downlink_rate_mbps": 8}
    settings.update(overrides)
    backend = ConstantRateBackend(**settings)  # type: ignore[arg-type]
    assert backend.advance() == NetworkStep(0.0, [], False)
    return backend


def run_until_terminal(backend: ConstantRateBackend) -> dict[tuple[int, str], object]:
    """Advance until the final step and return the terminal event of every request."""
    terminal: dict[tuple[int, str], object] = {}
    while True:
        step = backend.advance()
        for event in step.events:
            if isinstance(event, (DownloadCompleted, DownloadCancelled)):
                terminal[(event.ue_id, event.request_id)] = event
        if step.is_final:
            return terminal


def last_progress(steps: list[NetworkStep]) -> dict[tuple[int, str], int]:
    delivered: dict[tuple[int, str], int] = {}
    for step in steps:
        for event in step.events:
            if isinstance(event, DownloadProgress):
                delivered[(event.ue_id, event.request_id)] = event.bytes_delivered
    return delivered


def test_one_megabyte_at_8_mbps_takes_exactly_one_second() -> None:
    backend = make_backend()
    backend.submit_request(0, "r", 1_000_000)
    steps = [backend.advance() for _ in range(100)]
    assert steps[-1].time_s == 1.0
    assert [type(event) for event in steps[-1].events] == [DownloadProgress, DownloadCompleted]
    assert steps[-1].events[1] == DownloadCompleted(0, "r", 1.0)
    # Linear delivery: 10 kB per 10 ms step, no completion before
    assert steps[0].events == [DownloadProgress(0, "r", 10_000, 0.01)]
    assert all(not isinstance(event, DownloadCompleted) for step in steps[:-1] for event in step.events)


@pytest.mark.parametrize("synthetic_delay_ms", [20, 25])
def test_synthetic_delay_holds_back_the_first_byte(synthetic_delay_ms: int) -> None:
    backend = make_backend(synthetic_delay_ms=synthetic_delay_ms)
    backend.submit_request(0, "r", 1_000_000)
    steps = [backend.advance() for _ in range(110)]
    first_byte_s = min(step.time_s for step in steps if step.events)
    completed_s = [
        event.time_s for step in steps for event in step.events if isinstance(event, DownloadCompleted)
    ]
    assert first_byte_s == 0.03
    # 20 ms is on the step grid; 25 ms ends 5 ms into the step that ends at 1.03 s
    assert completed_s == [1.02 if synthetic_delay_ms == 20 else 1.03]
    # The step of the first byte only transfers from the end of the delay on
    assert last_progress(steps[:3])[(0, "r")] == (30 - synthetic_delay_ms) * 1000


def test_requests_submitted_later_wait_for_their_own_delay() -> None:
    backend = make_backend(synthetic_delay_ms=100)
    for _ in range(50):
        backend.advance()
    backend.submit_request(0, "r", 10_000)
    steps = [backend.advance() for _ in range(11)]
    assert all(not step.events for step in steps[:10])
    assert steps[10].time_s == 0.61
    assert steps[10].events == [DownloadProgress(0, "r", 10_000, 0.61), DownloadCompleted(0, "r", 0.61)]


def test_requests_of_one_ue_share_its_rate_equally() -> None:
    backend = make_backend()
    for request_id in ("a", "b"):
        backend.submit_request(0, request_id, 1_000_000)
    steps = [backend.advance() for _ in range(200)]
    assert steps[0].events == [DownloadProgress(0, "a", 5_000, 0.01), DownloadProgress(0, "b", 5_000, 0.01)]
    completions = [event for event in steps[-1].events if isinstance(event, DownloadCompleted)]
    assert completions == [DownloadCompleted(0, "a", 2.0), DownloadCompleted(0, "b", 2.0)]


def test_share_of_a_finished_request_goes_to_the_others_in_the_same_step() -> None:
    backend = make_backend()
    # 1 MB/s: the small request needs 4 ms at 500 kB/s, the large one gets the other 6 ms alone
    backend.submit_request(0, "large", 1_000_000)
    backend.submit_request(0, "small", 2_000)
    step = backend.advance()
    assert step.events == [
        DownloadProgress(0, "large", 2_000 + 6_000, 0.01),
        DownloadProgress(0, "small", 2_000, 0.01),
        DownloadCompleted(0, "small", 0.01),
    ]


def test_fractional_bytes_carry_over_without_drift() -> None:
    # 3 requests at 1 Mbps: 125000/3 B/s each, 416.67 B per step
    backend = make_backend(ue_ids=[0], downlink_rate_mbps=1, duration_s=100.0)
    for request_id in ("a", "b", "c"):
        backend.submit_request(0, request_id, 10_000_000)
    first_step = backend.advance()
    # Whole bytes are reported, rounded down
    assert [event.bytes_delivered for event in first_step.events] == [416, 416, 416]  # type: ignore[union-attr]
    steps = [first_step] + [backend.advance() for _ in range(2999)]
    # 30 s at 125 kB/s split three ways is exactly 1,250,000 bytes each
    assert last_progress(steps) == {(0, request_id): 1_250_000 for request_id in "abc"}
    # Steps alternate between 416 and 417 bytes instead of losing the fractions
    assert last_progress(steps[:3]) == {(0, request_id): 1_250 for request_id in "abc"}


def test_ues_do_not_share_capacity() -> None:
    backend = make_backend(downlink_rate_mbps_by_ue={"1": 16})
    backend.submit_request(0, "r", 1_000_000)
    backend.submit_request(1, "r", 1_000_000)
    backend.submit_request(1, "s", 1_000_000)
    terminal = run_until_terminal(backend)
    assert terminal[(0, "r")] == DownloadCompleted(0, "r", 1.0)
    assert terminal[(1, "r")] == DownloadCompleted(1, "r", 1.0)
    assert terminal[(1, "s")] == DownloadCompleted(1, "s", 1.0)


def test_rate_cap_lowers_and_zero_removes_it() -> None:
    backend = make_backend()
    backend.set_ue_control(0, UeControl(priority=3.0, rmax_mbps=4.0))
    assert backend.effective_downlink_rate_mbps(0) == 4.0
    assert backend.priority_by_ue == {0: 3.0}
    # A cap above the configured rate has no effect
    backend.set_ue_control(1, UeControl(rmax_mbps=100.0))
    assert backend.effective_downlink_rate_mbps(1) == 8.0
    backend.submit_request(0, "r", 1_000_000)
    for _ in range(100):
        step = backend.advance()
    assert last_progress([step]) == {(0, "r"): 500_000}
    # None leaves the cap and the priority unchanged
    backend.set_ue_control(0, UeControl())
    assert backend.effective_downlink_rate_mbps(0) == 4.0
    assert backend.priority_by_ue == {0: 3.0}
    backend.set_ue_control(0, UeControl(rmax_mbps=0))
    assert backend.effective_downlink_rate_mbps(0) == 8.0
    steps = [backend.advance() for _ in range(50)]
    assert steps[-1].events[-1] == DownloadCompleted(0, "r", 1.5)
    with pytest.raises(ValueError):
        backend.set_ue_control(0, UeControl(rmax_mbps=-1))


def test_cancellation_without_tail_ends_at_the_delivered_bytes() -> None:
    backend = make_backend()
    backend.submit_request(0, "r", 1_000_000)
    backend.advance()
    backend.cancel_request(0, "r")
    step = backend.advance()
    assert step.events == [DownloadCancelled(0, "r", 10_000, 0.02)]
    assert not backend.active_requests
    # Unknown and finished requests are ignored
    backend.cancel_request(0, "r")
    backend.cancel_request(1, "unknown")


def test_cancellation_tail_is_delivered_at_the_ue_rate() -> None:
    backend = make_backend(cancellation_tail_bytes=7_500)
    backend.submit_request(0, "r", 1_000_000)
    backend.submit_request(0, "other", 1_000_000)
    backend.advance()
    # 5 kB each so far; the tail ends at 12.5 kB, which takes 15 ms at 500 kB/s
    backend.cancel_request(0, "r")
    first = backend.advance()
    second = backend.advance()
    assert first.events == [DownloadProgress(0, "other", 10_000, 0.02), DownloadProgress(0, "r", 10_000, 0.02)]
    # The tail ends 5 ms into the step, then the other request gets the full rate
    assert second.events == [
        DownloadProgress(0, "other", 10_000 + 2_500 + 5_000, 0.03),
        DownloadProgress(0, "r", 12_500, 0.03),
        DownloadCancelled(0, "r", 12_500, 0.03),
    ]


def test_cancellation_during_the_synthetic_delay_delivers_nothing() -> None:
    backend = make_backend(synthetic_delay_ms=50, cancellation_tail_bytes=10_000)
    backend.submit_request(0, "r", 1_000_000)
    backend.advance()
    backend.cancel_request(0, "r")
    assert backend.advance().events == [DownloadCancelled(0, "r", 0, 0.02)]


def test_final_step_and_short_last_step() -> None:
    backend = make_backend(ue_ids=[0], duration_s=0.025)
    times = []
    while True:
        step = backend.advance()
        times.append((step.time_s, step.is_final))
        if step.is_final:
            break
    assert times == [(0.01, False), (0.02, False), (0.025, True)]
    with pytest.raises(RuntimeError):
        backend.advance()
    with pytest.raises(ValueError):
        backend.submit_request(0, "late", 1)


def test_request_validation() -> None:
    backend = make_backend()
    backend.submit_request(0, "r", 1)
    for ue_id, request_id, bytes_total in [
        (0, "r", 1),  # duplicate request ID
        (0, "", 1),
        (0, "x", 0),
        (0, "x", True),
        (0, "x", 1.5),
    ]:
        with pytest.raises(ValueError):
            backend.submit_request(ue_id, request_id, bytes_total)  # type: ignore[arg-type]
    for call in (
        lambda: backend.submit_request(7, "x", 1),
        lambda: backend.cancel_request(7, "x"),
        lambda: backend.set_ue_control(7, UeControl()),
    ):
        with pytest.raises(ValueError, match="Unknown UE 7"):
            call()
    # The same request ID is fine on another UE
    backend.submit_request(1, "r", 1)


@pytest.mark.parametrize(
    "settings",
    [
        {"downlink_rate_mbps": None},
        {"downlink_rate_mbps": 0},
        {"downlink_rate_mbps": -1},
        {"downlink_rate_mbps": True},
        {"downlink_rate_mbps": float("inf")},
        {"downlink_rate_mbps": None, "downlink_rate_mbps_by_ue": {"0": 8}},
        {"downlink_rate_mbps_by_ue": {"5": 8}},
        {"downlink_rate_mbps_by_ue": {"zero": 8}},
        {"downlink_rate_mbps_by_ue": {"0": 8, 0: 4}},
        {"downlink_rate_mbps_by_ue": [8, 8]},
        {"step_s": 0},
        {"duration_s": 0},
        {"synthetic_delay_ms": -1},
        {"cancellation_tail_bytes": -1},
        {"cancellation_tail_bytes": 1.5},
        {"ue_ids": []},
        {"ue_ids": [0, 0]},
        {"ue_ids": [-1]},
    ],
)
def test_invalid_configuration(settings: dict[str, object]) -> None:
    arguments: dict[str, object] = {"ue_ids": [0, 1], "duration_s": 1.0, "downlink_rate_mbps": 8}
    arguments.update(settings)
    with pytest.raises(ValueError):
        ConstantRateBackend(**arguments)  # type: ignore[arg-type]


def test_per_ue_rates_alone_are_enough() -> None:
    backend = ConstantRateBackend(ue_ids=[0, 1], duration_s=1.0, downlink_rate_mbps_by_ue={0: 2, "1": 4})
    assert [backend.effective_downlink_rate_mbps(ue_id) for ue_id in (0, 1)] == [2.0, 4.0]


def test_close_is_idempotent() -> None:
    backend = make_backend()
    backend.submit_request(0, "r", 1_000)
    backend.close()
    backend.close()
    assert not backend.active_requests
    with pytest.raises(RuntimeError):
        backend.advance()
    with pytest.raises(ValueError):
        backend.submit_request(0, "s", 1)


def test_collaboration_control_reaches_the_rate_cap(tmp_path: Path) -> None:
    backend = make_backend()
    table = InMemorySharedStateTable(signaling_level="L3", log_path=tmp_path / "shared-state.jsonl")
    collaboration = build_collaboration_stack(
        {"network_backend": "constant_rate", "signaling_level": "L3"},
        table=table,
        backend=backend,
        bridge=MagicMock(),
        plan_downlink_mbps_by_ue=None,
        csp_control_log_path=None,
    )
    collaboration.control.apply(1, CspControlIntent(priority=2.0, max_downlink_mbps=2.0))
    table.close()
    assert backend.effective_downlink_rate_mbps(1) == 2.0
    assert backend.priority_by_ue == {1: 2.0}
