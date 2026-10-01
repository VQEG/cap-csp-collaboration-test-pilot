"""Backend `transport_fikore`: TransportBackend from the FikoRE submodule.

The transport models, FikoreLink and the process wrapper live in
5g-network-emulator/transport/. This module only maps the experiment
configuration onto them. Setup follows transport/benchmarks/validate_sfv.py
in the FikoRE repository.
"""

from __future__ import annotations

import json
import math
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fikore_transport.backend import BackendConfig, TransportBackend
from fikore_transport.cc import Cubic, Reno
from fikore_transport.emulator import Emulator, EmulatorConfig
from fikore_transport.fikore_link import FikoreLink
from fikore_transport.link import LoopbackConfig, LoopbackLink
from fikore_transport.scenario import ScenarioDocument

REPO_ROOT = Path(__file__).resolve().parents[2]
FIKORE_ROOT = REPO_ROOT / "5g-network-emulator"

CONGESTION_CONTROLLERS = {"cubic": Cubic, "reno": Reno}


@dataclass(frozen=True)
class ScheduledSet:
    at_tti: int
    target: str
    params: dict[str, object]


def _resolve_repo_path(value: str) -> str:
    path = Path(value)
    return str(path if path.is_absolute() else (REPO_ROOT / path).resolve())


def _timeline_tti(message: dict[str, Any], line_no: int) -> int:
    value = message.get("at_tti")
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"timeline line {line_no} has invalid at_tti")
        return value
    seconds = message.get("at_t")
    if seconds is None:
        return 0
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
        or seconds < 0
    ):
        raise ValueError(f"timeline line {line_no} has invalid at_t")
    return math.floor(float(seconds) * 1000.0 + 0.5)


def load_control_timeline(
    path: Path,
    *,
    study_group: str,
    study_targets: list[str],
) -> list[ScheduledSet]:
    """Load set-only FikoRE timeline commands for socket replay."""
    scheduled: list[ScheduledSet] = []
    with path.open(encoding="utf-8") as stream:
        for line_no, raw in enumerate(stream, 1):
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"invalid timeline JSON at {path}:{line_no}: {error.msg}"
                ) from error
            if not isinstance(message, dict):
                raise ValueError(
                    f"timeline line {line_no} must contain an object"
                )
            at_tti = _timeline_tti(message, line_no)
            commands = message.get("cmds", [message])
            if not isinstance(commands, list) or not commands:
                raise ValueError(
                    f"timeline line {line_no} has no commands"
                )
            for command in commands:
                if not isinstance(command, dict):
                    raise ValueError(
                        f"timeline line {line_no} contains a non-object command"
                    )
                if command.get("op", "set") != "set":
                    raise ValueError(
                        f"timeline line {line_no} contains unsupported "
                        f"operation {command.get('op')!r}"
                    )
                target = command.get("target")
                params = command.get("set")
                if not isinstance(target, str) or not target:
                    raise ValueError(
                        f"timeline line {line_no} has an invalid target"
                    )
                if not isinstance(params, dict) or not params:
                    raise ValueError(
                        f"timeline line {line_no} has no set parameters"
                    )
                if any(
                    not isinstance(key, str)
                    or not key
                    or value is None
                    or isinstance(value, (dict, list))
                    or (
                        isinstance(value, float)
                        and not math.isfinite(value)
                    )
                    for key, value in params.items()
                ):
                    raise ValueError(
                        f"timeline line {line_no} has invalid set parameters"
                    )
                targets = (
                    [f"ue/{name}" for name in study_targets]
                    if target == f"ue/{study_group}"
                    else [target]
                )
                for expanded in targets:
                    scheduled.append(
                        ScheduledSet(at_tti, expanded, dict(params))
                    )
    return scheduled


@dataclass(frozen=True)
class TransportFikoreConfig:
    """Settings of the `network` block for `transport_fikore`."""

    link: str = "fikore"
    """`fikore`, or `loopback` for tests without the emulator"""
    transport: str = "tcp"
    """`tcp`, or `ideal` for the diagnostic fixed-window transport"""
    congestion_control: str = "cubic"
    receive_window_bytes: int = 128 * 1024
    tcp_connection_mode: str = "persistent"
    """`persistent` for an HTTP/1.1-style connection pool per UE, or `fresh` for one connection per object"""
    max_idle_tcp_connections_per_ue: int = 6
    """Maximum number of idle connections kept in the pool of each UE"""
    step_ms: int = 10
    """Duration of one NetworkStep towards the player in milliseconds"""
    telemetry_interval_ms: int = 10
    """Interval of NetworkTelemetryReceived events; a multiple of step_ms"""
    fikore_binary: str = str(FIKORE_ROOT / "bin" / "fikore")
    fikore_base_ini: str = str(FIKORE_ROOT / "config" / "control_demo.ini")
    study_ues: list[str] | None = None
    ack_over_link: bool = False
    replay_timeline: bool = True
    delay_budget_s: float | None = 30.0
    """PDCP delay budget; high so that validation runs do not expire packets"""
    random_v: bool | None = False
    fikore_section_overrides: dict[str, dict[str, object]] = field(
        default_factory=dict
    )
    fikore_ue_overrides: dict[str, dict[str, object]] = field(
        default_factory=dict
    )
    fikore_overrides: dict[str, str] = field(default_factory=dict)
    """Legacy selected-UE overrides; prefer structured overrides."""

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> TransportFikoreConfig:
        values = dict(values)
        unknown = set(values) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown transport_fikore settings: {sorted(unknown)}")
        if "fikore_base_ini" in values:
            values["fikore_base_ini"] = _resolve_repo_path(
                values["fikore_base_ini"]
            )
        config = cls(**values)
        if config.link not in ("fikore", "loopback"):
            raise ValueError(f"Unknown link {config.link!r}")
        if config.congestion_control not in CONGESTION_CONTROLLERS:
            raise ValueError(f"Unknown congestion control {config.congestion_control!r}")
        if config.tcp_connection_mode not in ("persistent", "fresh"):
            raise ValueError(f"Unknown TCP connection mode {config.tcp_connection_mode!r}")
        if config.max_idle_tcp_connections_per_ue < 0:
            raise ValueError("max_idle_tcp_connections_per_ue must not be negative")
        if config.step_ms <= 0 or config.receive_window_bytes <= 0:
            raise ValueError("step_ms and receive_window_bytes must be positive")
        if config.telemetry_interval_ms <= 0 or config.telemetry_interval_ms % config.step_ms:
            raise ValueError("telemetry_interval_ms must be a positive multiple of step_ms")
        if config.study_ues is not None:
            if (
                not isinstance(config.study_ues, list)
                or not config.study_ues
                or any(
                    not isinstance(ue_id, str) or not ue_id
                    for ue_id in config.study_ues
                )
                or len(set(config.study_ues)) != len(config.study_ues)
            ):
                raise ValueError("study_ues must be a non-empty list of unique IDs")
        if (
            config.delay_budget_s is not None
            and (
                isinstance(config.delay_budget_s, bool)
                or not isinstance(config.delay_budget_s, (int, float))
                or not math.isfinite(config.delay_budget_s)
                or config.delay_budget_s <= 0
            )
        ):
            raise ValueError("delay_budget_s must be positive or null")
        if config.random_v is not None and not isinstance(config.random_v, bool):
            raise ValueError("random_v must be boolean or null")
        if not isinstance(config.ack_over_link, bool):
            raise ValueError("ack_over_link must be boolean")
        if not isinstance(config.replay_timeline, bool):
            raise ValueError("replay_timeline must be boolean")
        return config


class TransportFikoreBackend(TransportBackend):
    """TransportBackend that also owns the emulator's working directory."""

    name = "transport_fikore"

    def __init__(
        self,
        config: TransportFikoreConfig,
        *,
        ue_ids: list[int],
        duration_s: float,
        output_dir: Path,
    ) -> None:
        self.settings = config
        self.work_dir = Path(tempfile.mkdtemp(prefix="capcsp-fikore-"))
        self.output_dir = output_dir
        if config.link == "fikore":
            if not Path(config.fikore_binary).exists():
                raise FileNotFoundError(
                    f"FikoRE binary not found at {config.fikore_binary}; build it with `make` in 5g-network-emulator"
                )
            scenario = ScenarioDocument.read(config.fikore_base_ini)
            study_groups = (
                list(config.study_ues)
                if config.study_ues is not None
                else scenario.ue_ids()
            )
            if len(study_groups) != 1:
                raise ValueError(
                    "transport_fikore requires exactly one study UE group; "
                    f"selected {study_groups}"
                )
            study_group = study_groups[0]
            study_targets = (
                [study_group]
                if len(ue_ids) == 1
                else [
                    f"{study_group}_{index}"
                    for index in range(len(ue_ids))
                ]
            )
            section_overrides = {
                (section, key): str(value)
                for section, values in config.fikore_section_overrides.items()
                for key, value in values.items()
            }
            emulator = Emulator(
                EmulatorConfig(
                    binary=config.fikore_binary,
                    base_ini=config.fikore_base_ini,
                    socket_path=str(self.work_dir / "control.sock"),
                    duration_s=duration_s + 1.0,
                    work_dir=str(FIKORE_ROOT),
                    n_ues=len(ue_ids),
                    delay_budget_s=config.delay_budget_s,
                    random_v=config.random_v,
                    log_path=str(output_dir / "fikore.log"),
                    study_ues=study_groups,
                    section_overrides=section_overrides,
                    ue_overrides={
                        ue_id: {
                            key: str(value)
                            for key, value in values.items()
                        }
                        for ue_id, values in config.fikore_ue_overrides.items()
                    },
                    extra=dict(config.fikore_overrides),
                )
            )
            # FikoRE numbers UEs from 0; map sorted experiment UE IDs onto them
            ue_id_map = {ue_id: index for index, ue_id in enumerate(sorted(ue_ids))}
            ue_target_map = {
                ue_id: study_targets[index]
                for index, ue_id in enumerate(sorted(ue_ids))
            }
            link = FikoreLink(
                emulator,
                flow_to_ue={},
                ue_id_map=ue_id_map,
                ue_target_map=ue_target_map,
            )
            timeline_value = scenario.get("Control", "timeline_file")
            if (
                config.replay_timeline
                and timeline_value not in (None, "", "none")
            ):
                timeline_path = Path(timeline_value)
                if not timeline_path.is_absolute():
                    timeline_path = (FIKORE_ROOT / timeline_path).resolve()
                if not timeline_path.is_file():
                    raise FileNotFoundError(
                        f"FikoRE timeline not found: {timeline_path}"
                    )
                for scheduled in load_control_timeline(
                    timeline_path,
                    study_group=study_group,
                    study_targets=study_targets,
                ):
                    link.schedule_set(
                        scheduled.at_tti,
                        scheduled.target,
                        scheduled.params,
                    )
        else:
            link = LoopbackLink(LoopbackConfig())
        super().__init__(
            link,
            BackendConfig(
                window_ttis=config.step_ms,
                horizon_ttis=round(duration_s * 1000),
                rwnd=config.receive_window_bytes,
                cc_factory=CONGESTION_CONTROLLERS[config.congestion_control],
                transport=config.transport,
                tcp_connection_mode=config.tcp_connection_mode,
                max_idle_tcp_connections_per_ue=config.max_idle_tcp_connections_per_ue,
                telemetry_every_windows=config.telemetry_interval_ms // config.step_ms,
                ack_over_link=config.ack_over_link,
            ),
        )

    def accounting(self) -> dict[str, Any] | None:
        """Byte conservation counters of the link, or None for the loopback link."""
        link = self.link
        if not isinstance(link, FikoreLink):
            return None
        accounted = sum(link.terminal_bytes.values()) + link.in_flight_bytes
        return {
            "submitted_bytes": link.submitted_bytes,
            "terminal_bytes": dict(link.terminal_bytes),
            "in_flight_bytes": link.in_flight_bytes,
            "bytes_conserved": accounted == link.submitted_bytes,
        }

    def close(self) -> None:
        super().close()
        effective_ini = self.work_dir / "cosim-run.ini"
        if effective_ini.exists():
            shutil.copy(effective_ini, self.output_dir / "fikore-effective.ini")
        shutil.rmtree(self.work_dir, ignore_errors=True)
