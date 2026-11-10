# Copyright 2026 VQEG Contributors
# SPDX-License-Identifier: MIT
"""Map :class:`CspControlIntent` onto FikoRE :class:`UeControl`."""

from __future__ import annotations

from typing import Any

from fikore_transport.backend import UeControl

from capcsp.collaboration.types import CspControlIntent
from capcsp.network.api import NetworkBackend


class FikoreControlAdapter:
    """Calls :meth:`NetworkBackend.set_ue_control` when a real controller invokes :meth:`apply`."""

    def __init__(
        self,
        backend: NetworkBackend,
        *,
        baseline_by_ue: dict[int, CspControlIntent] | None = None,
    ) -> None:
        self._backend = backend
        self._baseline = dict(baseline_by_ue or {})

    def read_baseline(self, ue_id: int) -> CspControlIntent:
        return self._baseline.get(ue_id, CspControlIntent(priority=1.0))

    def apply(self, ue_id: int, intent: CspControlIntent) -> None:
        setter = getattr(self._backend, "set_ue_control", None)
        if setter is None:
            return
        control = UeControl(
            priority=intent.priority,
            rmax_mbps=intent.max_downlink_mbps,
        )
        setter(ue_id, control)


def baseline_from_config(raw: Any) -> dict[int, CspControlIntent]:
    """Parse ``csp_baseline_control_by_ue`` from an experiment config."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("csp_baseline_control_by_ue must be a dict when set")
    out: dict[int, CspControlIntent] = {}
    for key, value in raw.items():
        ue_id = int(key)
        if not isinstance(value, dict):
            raise ValueError(f"csp_baseline_control_by_ue[{key}] must be an object")
        priority = value.get("priority")
        max_dl = value.get("max_downlink_mbps", value.get("rmax_mbps"))
        out[ue_id] = CspControlIntent(
            priority=float(priority) if priority is not None else None,
            max_downlink_mbps=float(max_dl) if max_dl is not None else None,
        )
    return out
