# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT

"""Tests for capcsp.collaboration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from capcsp.collaboration.adapters.noop_control import NoOpControlAdapter
from capcsp.collaboration.cap_reporter import SfVCapReporter
from capcsp.collaboration.csp_controller import DummyCSPController
from capcsp.collaboration.runtime import apply_player_network_events, player_facing_network_step
from capcsp.collaboration.snapshot import build_collaboration_payload
from capcsp.collaboration.telemetry import CspTelemetryWriter, NoCspTelemetry
from capcsp.network.api import NetworkTelemetry, NetworkTelemetryReceived
from capcsp.collaboration.adapters.fikore_control import FikoreControlAdapter
from capcsp.runner.run import derive_plan_downlink_mbps, write_plan_downlink_fields
from capcsp.shared_state.table import InMemorySharedStateTable
from capcsp.collaboration.types import CspControlIntent
from capcsp.shared_state.types import CapReport, CspFields


def test_player_facing_network_step_attaches_collaboration() -> None:
    collab = {"signaling_level": "L0", "csp_by_ue": {}}
    progress = {
        "event_type": "DownloadProgress",
        "ue_id": 0,
        "time_s": 0.01,
        "request_id": "r1",
        "bytes_delivered": 1,
    }
    step = {"time_s": 0.01, "is_final": False, "events": [progress]}
    out = player_facing_network_step(step, collaboration=collab)
    assert out["events"] == [progress]
    assert out["collaboration"] is collab


def test_in_step_telemetry_is_rejected() -> None:
    step = {
        "time_s": 0.01,
        "is_final": False,
        "events": [
            {
                "event_type": "NetworkTelemetryReceived",
                "ue_id": 0,
                "time_s": 0.01,
                "fields": {"throughput_mbps": 1.0},
            }
        ],
    }
    with pytest.raises(ValueError, match="csp_telemetry"):
        apply_player_network_events(step, ue_ids={0}, sizes={}, delivered={}, terminal=set())


def test_build_collaboration_payload_l0_empty(tmp_path: Path) -> None:
    table = InMemorySharedStateTable(signaling_level="L0", log_path=tmp_path / "s.jsonl")
    table.write_csp_fields(
        0,
        CspFields(0.1, 10.0, 5.0, 20.0, 0.0, None),
    )
    payload = build_collaboration_payload(ue_ids={0}, table=table, signaling_level="L0")
    assert payload["signaling_level"] == "L0"
    assert payload["csp_by_ue"] == {}


def test_build_collaboration_payload_l2_exposes_fields(tmp_path: Path) -> None:
    table = InMemorySharedStateTable(signaling_level="L2", log_path=tmp_path / "s.jsonl")
    fields = CspFields(0.2, None, 3.0, 25.0, 0.01, 0.0)
    table.write_csp_fields(0, fields)
    payload = build_collaboration_payload(ue_ids={0}, table=table, signaling_level="L2")
    assert payload["csp_by_ue"]["0"]["achieved_throughput_mbps"] == 3.0


class _FixedSource:
    def __init__(self, samples: list[NetworkTelemetryReceived]) -> None:
        self.samples = samples
        self.forced: list[bool] = []

    def poll(self, *, force: bool = False) -> list[NetworkTelemetryReceived]:
        self.forced.append(force)
        samples, self.samples = self.samples, []
        return samples


def test_csp_telemetry_writer_writes_table_and_rows(tmp_path: Path) -> None:
    table = InMemorySharedStateTable(signaling_level="L2", log_path=tmp_path / "s.jsonl")
    source = _FixedSource(
        [
            NetworkTelemetryReceived(
                0,
                1.0,
                NetworkTelemetry(throughput_mbps=1.5, rtt_ms=40.0, drop_rate=0.0, ce_rate=0.0, queue_bytes=3000),
            )
        ]
    )
    writer = CspTelemetryWriter(table, source, plan_downlink_mbps_by_ue={0: 100.0})
    rows = writer.poll_and_write(force=True)
    assert source.forced == [True]
    assert rows == [
        {
            "ue_id": 0,
            "time_s": 1.0,
            "throughput_mbps": 1.5,
            "rtt_ms": 40.0,
            "ip_latency_ms": None,
            "pdcp_latency_ms": None,
            "ce_rate": 0.0,
            "drop_rate": 0.0,
            "retransmitted_bytes": None,
            "sinr_db": None,
            "queue_bytes": 3000,
        }
    ]
    read = table.read_csp_fields(0)
    assert read is not None
    assert read.updated_at_s == 1.0
    assert read.plan_downlink_mbps == 100.0
    assert read.achieved_throughput_mbps == 1.5
    assert read.rtt_ms == 40.0
    assert writer.poll_and_write() == []


def test_no_csp_telemetry_writes_nothing(tmp_path: Path) -> None:
    table = InMemorySharedStateTable(signaling_level="L2", log_path=tmp_path / "s.jsonl")
    assert CspTelemetryWriter(table, NoCspTelemetry()).poll_and_write(force=True) == []
    assert table.read_csp_fields(0) is None


def test_dummy_csp_controller_logs_proposal(tmp_path: Path) -> None:
    log = tmp_path / "csp-control.jsonl"
    table = InMemorySharedStateTable(signaling_level="L3", log_path=None)
    table.write_cap_report(
        0,
        CapReport(1.0, True, 0.5, "v1", 0.0),
    )
    control = NoOpControlAdapter()
    ctrl = DummyCSPController(signaling_level="L3", log_path=log)
    decisions = ctrl.on_collaboration_tick(
        time_s=1.0,
        ue_ids={0},
        table=table,
        control=control,
    )
    assert len(decisions) == 1
    assert decisions[0].proposed.priority == 2.0
    assert decisions[0].applied is False
    row = json.loads(log.read_text().strip())
    assert row["record_type"] == "control_proposal"
    assert row["reason"] == "dummy_stall_boost"
    ctrl.close()


def test_dummy_csp_controller_skips_duplicate_audit_rows(tmp_path: Path) -> None:
    log = tmp_path / "csp-control.jsonl"
    table = InMemorySharedStateTable(signaling_level="L3", log_path=None)
    table.write_cap_report(
        0,
        CapReport(1.0, False, 1.0, "v1", 0.0),
    )
    ctrl = DummyCSPController(signaling_level="L3", log_path=log)
    for _ in range(2):
        ctrl.on_collaboration_tick(
            time_s=1.0,
            ue_ids={0},
            table=table,
            control=NoOpControlAdapter(),
        )
    ctrl.close()
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_dummy_csp_controller_does_not_call_apply() -> None:
    control = MagicMock()
    control.read_baseline.return_value = CspControlIntent(priority=1.0)
    table = InMemorySharedStateTable(signaling_level="L3", log_path=None)
    table.write_cap_report(
        0,
        CapReport(1.0, False, 1.0, "v1", 0.0),
    )
    DummyCSPController(signaling_level="L3", log_path=None).on_collaboration_tick(
        time_s=1.0,
        ue_ids={0},
        table=table,
        control=control,
    )
    control.apply.assert_not_called()


def test_sfv_cap_reporter_empty_drain_writes_nothing(tmp_path: Path) -> None:
    log = tmp_path / "s.jsonl"
    table = InMemorySharedStateTable(signaling_level="L3", log_path=log)
    bridge = MagicMock()
    bridge.exchange.return_value = {"type": "cap_reports", "reports": {}}
    SfVCapReporter(bridge).fetch_and_write(table, {0, 1})
    table.close()
    assert table.read_cap_report(0) is None
    assert not log.exists() or "cap_to_csp" not in log.read_text(encoding="utf-8")


def test_fikore_control_adapter_calls_set_ue_control() -> None:
    backend = MagicMock()
    backend.set_ue_control = MagicMock()
    adapter = FikoreControlAdapter(backend)
    adapter.apply(0, CspControlIntent(priority=9.0))
    backend.set_ue_control.assert_called_once()


def _capped_fikore_config(**overrides: object) -> dict:
    config: dict = {
        "network_backend": "transport_fikore",
        "network": {"parametric_cell": {"preset": "M01", "study_dl_rmax_mbps": 2.5}},
        "signaling_level": "L0",
    }
    config.update(overrides)
    return config


def test_plan_is_derived_from_the_study_cap_on_transport_fikore() -> None:
    assert derive_plan_downlink_mbps(_capped_fikore_config(), {1, 0}) == {0: 2.5, 1: 2.5}


def test_explicit_plan_wins_over_the_study_cap() -> None:
    config = _capped_fikore_config(plan_downlink_mbps_by_ue={"0": 50, "1": 20.5})
    assert derive_plan_downlink_mbps(config, {0, 1}) == {0: 50.0, 1: 20.5}


@pytest.mark.parametrize(
    "config",
    [
        {"network_backend": "transport_fikore", "network": {"parametric_cell": {"preset": "M01"}}},
        {"network_backend": "transport_fikore", "network": {"fikore_base_ini": "x.ini"}},
        {"network_backend": "transport_fikore", "network": {}},
        {"network_backend": "constant_rate", "network": {"parametric_cell": {"study_dl_rmax_mbps": 2.5}}},
        {"network_backend": "mock", "network": {}},
    ],
)
def test_no_plan_is_derived_without_a_study_cap_on_transport_fikore(config: dict) -> None:
    assert derive_plan_downlink_mbps(config, {0}) is None


def test_non_dict_explicit_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="plan_downlink_mbps_by_ue"):
        derive_plan_downlink_mbps(_capped_fikore_config(plan_downlink_mbps_by_ue=[2.5]), {0})


@pytest.mark.parametrize(("level", "visible"), [("L0", False), ("L1", True), ("L2", True)])
def test_derived_cap_plan_is_hidden_at_l0_and_visible_from_l1(tmp_path: Path, level: str, visible: bool) -> None:
    config = _capped_fikore_config(signaling_level=level)
    plan = derive_plan_downlink_mbps(config, {0})
    table = InMemorySharedStateTable(signaling_level=level, log_path=tmp_path / f"{level}.jsonl")
    write_plan_downlink_fields(table, plan, {0}, level)
    fields = table.read_csp_fields(0)
    payload = build_collaboration_payload(ue_ids={0}, table=table, signaling_level=level)
    if visible:
        assert fields is not None and fields.plan_downlink_mbps == 2.5
        assert payload["csp_by_ue"]["0"]["plan_downlink_mbps"] == 2.5
    else:
        assert fields is None
        assert payload["csp_by_ue"] == {}
    table.close()


def test_plan_fields_skip_unknown_ues(tmp_path: Path) -> None:
    table = InMemorySharedStateTable(signaling_level="L1", log_path=None)
    write_plan_downlink_fields(table, {0: 2.5, 7: 2.5}, {0}, "L1")
    assert table.read_csp_fields(0) is not None
    assert table.read_csp_fields(7) is None
