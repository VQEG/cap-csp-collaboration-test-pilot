# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT

"""Tests for capcsp.shared_state."""

from __future__ import annotations

import json
from pathlib import Path

from fikore_transport.backend import NetworkTelemetry

from capcsp.shared_state.mapping import network_telemetry_from_step_event, network_telemetry_to_csp_fields
from capcsp.shared_state.table import InMemorySharedStateTable
from capcsp.shared_state.types import CapReport, CspFields


def test_network_telemetry_from_step_event_nested_fields() -> None:
    event = {
        "event_type": "NetworkTelemetryReceived",
        "ue_id": 1,
        "time_s": 0.01,
        "fields": {
            "throughput_mbps": 2.0,
            "rtt_ms": 45.0,
            "drop_rate": 0.01,
            "ce_rate": 0.0,
        },
    }
    nt = network_telemetry_from_step_event(event)
    assert nt.throughput_mbps == 2.0
    assert nt.rtt_ms == 45.0


def test_network_telemetry_to_csp_fields_mapping() -> None:
    nt = NetworkTelemetry(
        throughput_mbps=10.0,
        rtt_ms=20.0,
        drop_rate=0.05,
        ce_rate=0.1,
        sinr_db=12.3,
    )
    csp, ext = network_telemetry_to_csp_fields(time_s=1.5, telemetry=nt, plan_downlink_mbps=100.0)
    assert csp.updated_at_s == 1.5
    assert csp.plan_downlink_mbps == 100.0
    assert csp.achieved_throughput_mbps == 10.0
    assert csp.rtt_ms == 20.0
    assert csp.loss_rate == 0.05
    assert csp.congestion_rate == 0.1
    assert ext["sinr_db"] == 12.3


def test_in_memory_table_l0_filters_csp_read(tmp_path: Path) -> None:
    log = tmp_path / "shared-state.jsonl"
    table = InMemorySharedStateTable(signaling_level="L0", log_path=log)
    table.write_csp_fields(
        0,
        CspFields(
            updated_at_s=0.1,
            plan_downlink_mbps=None,
            achieved_throughput_mbps=5.0,
            rtt_ms=30.0,
            loss_rate=0.0,
            congestion_rate=None,
        ),
    )
    assert table.read_csp_fields(0) is None
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["direction"] == "csp_to_cap"


def test_in_memory_table_l2_exposes_csp(tmp_path: Path) -> None:
    log = tmp_path / "shared-state.jsonl"
    table = InMemorySharedStateTable(signaling_level="L2", log_path=log)
    fields = CspFields(
        updated_at_s=2.0,
        plan_downlink_mbps=None,
        achieved_throughput_mbps=3.0,
        rtt_ms=25.0,
        loss_rate=0.02,
        congestion_rate=None,
    )
    table.write_csp_fields(1, fields, extensions={"queue_bytes": 1000})
    read = table.read_csp_fields(1)
    assert read == fields


def test_cap_write_logged_at_l2_but_read_blocked_until_l3(tmp_path: Path) -> None:
    log = tmp_path / "shared-state.jsonl"
    table = InMemorySharedStateTable(signaling_level="L2", log_path=log)
    report = CapReport(
        time_s=1.0,
        is_stalled=False,
        playable_buffer_s=2.0,
        current_video_id="v1",
        swipe_rate_per_s=0.5,
    )
    table.write_cap_report(0, report)
    assert table.read_cap_report(0) is None
    assert "cap_to_csp" in log.read_text()

    table_l3 = InMemorySharedStateTable(signaling_level="L3", log_path=None)
    table_l3.write_cap_report(0, report)
    assert table_l3.read_cap_report(0) == report
