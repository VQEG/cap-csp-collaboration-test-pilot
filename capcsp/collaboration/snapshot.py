# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Filtered CSP views for the CAP process."""

from __future__ import annotations

from typing import Any

from capcsp.collaboration.telemetry import csp_fields_to_json
from capcsp.shared_state.table import SharedStateTable


def build_collaboration_payload(
    *,
    ue_ids: set[int],
    table: SharedStateTable,
    signaling_level: str,
) -> dict[str, Any]:
    """Return the ``collaboration`` object attached to each ``network_step`` IPC message."""
    csp_by_ue: dict[str, Any] = {}
    for ue_id in sorted(ue_ids):
        fields = table.read_csp_fields(ue_id)
        payload = csp_fields_to_json(fields)
        if payload is not None:
            csp_by_ue[str(ue_id)] = payload
    return {
        "signaling_level": signaling_level.strip().upper(),
        "csp_by_ue": csp_by_ue,
    }
