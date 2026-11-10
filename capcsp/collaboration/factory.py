# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Wire collaboration components from an experiment configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capcsp.collaboration.adapters.fikore_control import FikoreControlAdapter, baseline_from_config
from capcsp.collaboration.adapters.noop_control import NoOpControlAdapter
from capcsp.collaboration.cap_reporter import SfVCapReporter
from capcsp.collaboration.csp_controller import CSPController, DummyCSPController
from capcsp.collaboration.telemetry import StepEventCspTelemetrySource
from capcsp.network.api import NetworkBackend
from capcsp.shared_state.table import SharedStateTable, _parse_signaling_level


@dataclass
class CollaborationContext:
    """Per-run collaboration stack used by :func:`capcsp.player.bridge.run_sessions`
    and :func:`capcsp.collaboration.runtime.run_collaboration_tick`."""

    table: SharedStateTable
    telemetry: StepEventCspTelemetrySource
    signaling_level: str
    cap_reporter: SfVCapReporter
    control: FikoreControlAdapter | NoOpControlAdapter
    csp_controller: CSPController | None


def build_collaboration_stack(
    config: dict[str, Any],
    *,
    table: SharedStateTable,
    backend: NetworkBackend,
    bridge: Any,
    plan_downlink_mbps_by_ue: dict[int, float] | None,
    csp_control_log_path: Path | None,
) -> CollaborationContext:
    signaling_level = str(config.get("signaling_level", "L0"))
    baseline = baseline_from_config(config.get("csp_baseline_control_by_ue"))
    network_backend = config.get("network_backend", "mock")
    if network_backend == "transport_fikore":
        control: FikoreControlAdapter | NoOpControlAdapter = FikoreControlAdapter(
            backend, baseline_by_ue=baseline
        )
    else:
        control = NoOpControlAdapter(baseline_by_ue=baseline)

    csp_controller: CSPController | None = None
    controller_name = config.get("csp_controller")
    if controller_name == "dummy" and _parse_signaling_level(signaling_level) >= 3:
        csp_controller = DummyCSPController(
            signaling_level=signaling_level,
            log_path=csp_control_log_path,
        )
    elif controller_name not in (None, "dummy"):
        raise ValueError(f"Unsupported csp_controller {controller_name!r}")

    telemetry = StepEventCspTelemetrySource(table, plan_downlink_mbps_by_ue=plan_downlink_mbps_by_ue)
    return CollaborationContext(
        table=table,
        telemetry=telemetry,
        signaling_level=signaling_level,
        cap_reporter=SfVCapReporter(bridge),
        control=control,
        csp_controller=csp_controller,
    )
