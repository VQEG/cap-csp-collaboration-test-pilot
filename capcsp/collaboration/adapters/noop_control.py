# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Control adapter that records intent without touching the network backend."""

from __future__ import annotations

from capcsp.collaboration.types import CspControlIntent


class NoOpControlAdapter:
    """Baseline reads only; ``apply`` is a no-op (mock backend without a control plane)."""

    def __init__(self, *, baseline_by_ue: dict[int, CspControlIntent] | None = None) -> None:
        self._baseline = dict(baseline_by_ue or {})

    def read_baseline(self, ue_id: int) -> CspControlIntent:
        return self._baseline.get(ue_id, CspControlIntent(priority=1.0))

    def apply(self, ue_id: int, intent: CspControlIntent) -> None:
        _ = (ue_id, intent)
