"""Expand an experiment grid into one experiment configuration per cell.

A grid file names a base experiment (a path relative to the grid file, or the experiment itself) and the axes to vary:

- `conditions`: named partial configurations merged over the base, for example the FikoRE scenario and duration
- `content_catalogues`: named content catalogues (paths relative to the grid file), for example one per encoder and
  segment duration; without this axis, every cell uses the content of the base experiment
- `signaling_levels`: signaling levels, for example ["L0"]
- `ue_counts`: number of video UEs per cell
- `behavior_mixes`: named behaviour patterns, repeated over the UEs of a cell; ["simple", "preload"] alternates B1 and B2
- `replications`: number of replications; replication r gives the same seeds in every cell, so cells can be compared in pairs

The base experiment provides one session template per player behaviour: the first base session with that behaviour.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from capcsp.shared_state.signaling import parse_signaling_level

PLAYER_BEHAVIORS = ("simple", "preload")
# Session seeds are replication * SESSION_SEED_STRIDE + ue_id, so UEs never share a seed
SESSION_SEED_STRIDE = 1000
# Name of the only content catalogue when a grid has no content_catalogues axis
BASE_CONTENT_CATALOGUE = "base"


@dataclass(frozen=True)
class GridCell:
    """One run of the grid, with its axis values and its complete experiment configuration."""

    run_id: str
    condition: str
    content_catalogue: str
    signaling_level: str
    ue_count: int
    behavior_mix: str
    replication: int
    experiment_config: dict[str, Any]

    @property
    def axis_values(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "content_catalogue": self.content_catalogue,
            "signaling_level": self.signaling_level,
            "ue_count": self.ue_count,
            "behavior_mix": self.behavior_mix,
            "replication": self.replication,
        }

    @property
    def config_hash(self) -> str:
        """Hash of the experiment configuration; a finished cell with the same hash is not run again."""
        canonical = json.dumps(self.experiment_config, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class GridSpecification:
    grid_id: str
    base_experiment: dict[str, Any]
    conditions: dict[str, dict[str, Any]]
    # Catalogue name to absolute content path; None keeps the content of the base experiment
    content_catalogues: dict[str, str | None]
    signaling_levels: list[str]
    ue_counts: list[int]
    behavior_mixes: dict[str, list[str]]
    replications: int
    network_seed_base: int

    @classmethod
    def from_file(cls, path: Path) -> GridSpecification:
        values = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(values.get("base"), dict):
            base_experiment, base_dir = copy.deepcopy(values["base"]), path.parent
        else:
            base_path = (path.parent / values["base"]).resolve()
            base_experiment, base_dir = json.loads(base_path.read_text(encoding="utf-8")), base_path.parent
        # Content paths are relative to the file that holds the base; make them independent of where cell configs are written
        if "content" in base_experiment:
            base_experiment["content"] = str((base_dir / base_experiment["content"]).resolve())
        if "content_catalogues" in values:
            values["content_catalogues"] = {
                name: str((path.parent / content).resolve()) for name, content in values["content_catalogues"].items()
            }
        return cls.from_dict({**values, "base": base_experiment}, default_grid_id=path.stem)

    @classmethod
    def from_dict(cls, values: dict[str, Any], default_grid_id: str = "grid") -> GridSpecification:
        known = {
            "grid_id",
            "base",
            "conditions",
            "content_catalogues",
            "signaling_levels",
            "ue_counts",
            "behavior_mixes",
            "replications",
            "network_seed_base",
        }
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"Unknown grid settings: {sorted(unknown)}")
        specification = cls(
            grid_id=values.get("grid_id", default_grid_id),
            base_experiment=values["base"],
            conditions=values.get("conditions") or {str(values["base"].get("condition", "base")): {}},
            content_catalogues=values.get("content_catalogues") or {BASE_CONTENT_CATALOGUE: None},
            signaling_levels=values.get("signaling_levels", ["L0"]),
            ue_counts=values.get("ue_counts", [len(values["base"]["sessions"])]),
            behavior_mixes=values.get("behavior_mixes", {"b1-b2": ["simple", "preload"]}),
            replications=values.get("replications", 1),
            network_seed_base=values.get("network_seed_base", 20260927),
        )
        specification._validate()
        return specification

    def _validate(self) -> None:
        for level in self.signaling_levels:
            parse_signaling_level(level)
        if not self.ue_counts or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 1 for count in self.ue_counts
        ):
            raise ValueError("ue_counts must be a non-empty list of positive integers")
        if not isinstance(self.replications, int) or self.replications < 1:
            raise ValueError("replications must be a positive integer")
        if not self.behavior_mixes:
            raise ValueError("behavior_mixes must name at least one mix")
        for name, content in self.content_catalogues.items():
            if content is not None and not Path(content).is_file():
                raise ValueError(f"Content catalogue {name!r} not found: {content}")
        templates = self.session_templates()
        for name, pattern in self.behavior_mixes.items():
            if not pattern:
                raise ValueError(f"Behaviour mix {name!r} is empty")
            for behavior in pattern:
                if behavior not in templates:
                    raise ValueError(
                        f"Behaviour mix {name!r} uses {behavior!r}, but the base experiment has no such session"
                    )

    def session_templates(self) -> dict[str, dict[str, Any]]:
        """The first base session of each player behaviour."""
        templates: dict[str, dict[str, Any]] = {}
        for session in self.base_experiment["sessions"]:
            templates.setdefault(session["player_behavior"], session)
        return templates

    def cells(self) -> list[GridCell]:
        """All cells, ordered by replication first, so a partial grid already covers every other axis."""
        return [
            self._cell(condition, content_catalogue, level, ue_count, mix, replication)
            for replication, condition, content_catalogue, level, ue_count, mix in itertools.product(
                range(1, self.replications + 1),
                self.conditions,
                self.content_catalogues,
                self.signaling_levels,
                self.ue_counts,
                self.behavior_mixes,
            )
        ]

    def _cell(
        self, condition: str, content_catalogue: str, level: str, ue_count: int, mix: str, replication: int
    ) -> GridCell:
        content = self.content_catalogues[content_catalogue]
        # Grids without the content axis keep their run IDs, so finished cells are still found
        content_part = "" if content is None else f"-{content_catalogue}"
        run_id = f"{self.grid_id}-{condition}{content_part}-{level}-{ue_count}ue-{mix}-r{replication:02d}".lower()
        config = merge_configurations(self.base_experiment, self.conditions[condition])
        if content is not None:
            config["content"] = content
        config["run_id"] = run_id
        config["signaling_level"] = level
        config["condition"] = self.conditions[condition].get("condition", condition)
        config["sessions"] = self._sessions(ue_count, self.behavior_mixes[mix], replication)
        if config.get("network_backend") == "transport_fikore":
            network = config.setdefault("network", {})
            overrides = network.setdefault("fikore_section_overrides", {})
            overrides.setdefault("Global", {})["seed"] = self.network_seed_base + replication
        return GridCell(run_id, condition, content_catalogue, level, ue_count, mix, replication, config)

    def _sessions(self, ue_count: int, pattern: list[str], replication: int) -> list[dict[str, Any]]:
        templates = self.session_templates()
        sessions = []
        for ue_id in range(ue_count):
            session = copy.deepcopy(templates[pattern[ue_id % len(pattern)]])
            session["ue_id"] = ue_id
            session_config = session.setdefault("config", {})
            session_config["sessionId"] = f"ue{ue_id}"
            session_config["seed"] = replication * SESSION_SEED_STRIDE + ue_id
            sessions.append(session)
        return sessions


def merge_configurations(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge `overlay` into a copy of `base`: objects merge key by key, all other values replace."""
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_configurations(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged
