# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT

"""Tests for capcsp.collaboration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from capcsp.collaboration.adapters.noop_control import NoOpControlAdapter
from capcsp.collaboration.cap_reporter import SfVCapReporter
from capcsp.collaboration.csp_controller import DummyCSPController
from capcsp.collaboration.runtime import player_facing_network_step
from capcsp.collaboration.snapshot import build_collaboration_payload
from capcsp.collaboration.telemetry import StepEventCspTelemetrySource
from capcsp.collaboration.adapters.fikore_control import FikoreControlAdapter
from capcsp.shared_state.table import InMemorySharedStateTable
from capcsp.collaboration.types import CspControlIntent
from capcsp.shared_state.types import CapReport, CspFields


def test_player_facing_network_step_strips_telemetry() -> None:
    collab = {"signaling_level": "L0", "csp_by_ue": {}}
    step = {
        "time_s": 0.01,
        "is_final": False,
        "events": [
            {
                "event_type": "NetworkTelemetryReceived",
                "ue_id": 0,
                "time_s": 0.01,
                "fields": {"throughput_mbps": 1.0},
            },
            {
                "event_type": "DownloadProgress",
                "ue_id": 0,
                "time_s": 0.01,
                "request_id": "r1",
                "bytes_delivered": 1,
            },
        ],
    }
    out = player_facing_network_step(step, collaboration=collab)
    assert len(out["events"]) == 1
    assert out["events"][0]["event_type"] == "DownloadProgress"
    assert out["collaboration"] is collab


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


def test_step_event_csp_telemetry_source_writes_table(tmp_path: Path) -> None:
    table = InMemorySharedStateTable(signaling_level="L2", log_path=tmp_path / "s.jsonl")
    source = StepEventCspTelemetrySource(table, plan_downlink_mbps_by_ue={0: 100.0})
    source.ingest_step_events(
        [
            {
                "event_type": "NetworkTelemetryReceived",
                "ue_id": 0,
                "time_s": 0.05,
                "fields": {"throughput_mbps": 1.5, "rtt_ms": 40.0, "drop_rate": 0.0, "ce_rate": 0.0},
            }
        ]
    )
    read = table.read_csp_fields(0)
    assert read is not None
    assert read.plan_downlink_mbps == 100.0


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
