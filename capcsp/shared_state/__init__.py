# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""VQEG shared state table (CAP–CSP collaboration bus).

See docs/signaling.md for the logical specification.
"""

from capcsp.shared_state.mapping import network_telemetry_from_step_event, network_telemetry_to_csp_fields
from capcsp.shared_state.table import InMemorySharedStateTable, SharedStateTable
from capcsp.shared_state.types import CapReport, CspFields

__all__ = [
    "CapReport",
    "CspFields",
    "InMemorySharedStateTable",
    "SharedStateTable",
    "network_telemetry_from_step_event",
    "network_telemetry_to_csp_fields",
]
