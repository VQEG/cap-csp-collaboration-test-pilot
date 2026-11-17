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
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fikore_transport.backend import BackendConfig, NetworkEvent, NetworkStep, TransportBackend
from fikore_transport.cc import CongestionControl, Cubic, Reno
from fikore_transport.emulator import Emulator, EmulatorConfig
from fikore_transport.fikore_link import FikoreLink
from fikore_transport.link import LoopbackConfig, LoopbackLink
from fikore_transport.runner import Flow, Runner
from fikore_transport.scenario import ScenarioDocument
from fikore_transport.tcp import TcpReceiver, TcpSender

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


def physical_ue_map(
    scenario: ScenarioDocument,
    *,
    study_group: str,
    ue_ids: list[int],
    ue_overrides: dict[str, dict[str, object]],
) -> dict[int, int]:
    """Map experiment UE IDs to FikoRE UE numbers.

    FikoRE numbers UEs from 0 in the order of the `[UE]` blocks, expanding each
    block to its `n_ues`. Sorted experiment UE IDs map onto the study group.
    UEs of other groups map from negative IDs, so that their state cannot
    overwrite the state of a study UE.
    """
    if any(ue_id < 0 for ue_id in ue_ids):
        raise ValueError("experiment UE IDs must not be negative")
    if study_group not in scenario.ue_ids():
        raise ValueError(f"study UE group {study_group!r} is not in the scenario")
    mapping: dict[int, int] = {}
    physical = 0
    for group in scenario.ue_ids():
        if group == study_group:
            for ue_id in sorted(ue_ids):
                mapping[ue_id] = physical
                physical += 1
            continue
        count = ue_overrides.get(group, {}).get("n_ues")
        count = int(count) if count is not None else scenario.ue_count(group)
        for _ in range(count):
            mapping[-1 - physical] = physical
            physical += 1
    return mapping


def _ini_value(value: object) -> str:
    """Format an override value as FikoRE reads it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    raise ValueError(f"invalid FikoRE override value {value!r}")


def _validate_overrides(name: str, overrides: object) -> None:
    if not isinstance(overrides, dict) or any(
        not isinstance(key, str) or not isinstance(values, dict)
        for key, values in overrides.items()
    ):
        raise ValueError(f"{name} must map names to objects of settings")
    for values in overrides.values():
        for key, value in values.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{name} contains an invalid setting name")
            _ini_value(value)


def _validate_background_iperf_ues(mapping: object) -> None:
    if not isinstance(mapping, dict):
        raise ValueError("background_iperf_ues must map UE group names to positive Mbps rates")
    for group, rate in mapping.items():
        if not isinstance(group, str) or not group:
            raise ValueError("background_iperf_ues group names must be non-empty strings")
        if (
            isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not math.isfinite(rate)
            or float(rate) <= 0.0
        ):
            raise ValueError(f"background_iperf_ues[{group!r}] must be a positive finite rate in Mbps")


class _BackgroundTcpDriver:
    """Application-paced TCP flows for non-study UE groups over the shared Runner.

    Each configured group slot follows its ``enabled`` transitions in the replayed
    control timeline: an arriving session opens a fresh TCP connection paced at the
    target application bitrate with bounded send-buffer backpressure, and a departing
    session cancels new writes one TTI before detach and retires after drain.
    """

    FIRST_FLOW_ID = 1_000_000

    def __init__(
        self,
        *,
        link: FikoreLink,
        runner: Runner,
        cc_factory: type[CongestionControl],
        mss: int,
        ack_over_link: bool,
        horizon_ttis: int,
        target_rates_mbps: dict[str, float],
        target_external_ues: dict[str, int],
        scheduled: list[ScheduledSet],
        rwnd_bytes: int = 128 * 1024,
        max_send_buffer_bytes: int = 64 * 1024,
    ) -> None:
        self.link = link
        self.runner = runner
        self.cc_factory = cc_factory
        self.mss = mss
        self.ack_over_link = ack_over_link
        self.rwnd_bytes = rwnd_bytes
        self.max_send_buffer_bytes = max_send_buffer_bytes
        self.target_external_ues = dict(target_external_ues)
        self.bytes_per_tti_by_target = {
            target: rate_mbps * 1e6 / 8.0 / 1000.0
            for target, rate_mbps in target_rates_mbps.items()
        }

        state_events: dict[str, list[tuple[int, bool]]] = {
            target: [(0, True)] for target in target_external_ues
        }
        for item in scheduled:
            if (
                item.target in state_events
                and "enabled" in item.params
                and 0 <= item.at_tti < horizon_ttis
            ):
                enabled = bool(item.params["enabled"])
                events = state_events[item.target]
                if events and events[-1][0] == item.at_tti:
                    events[-1] = (item.at_tti, enabled)
                else:
                    events.append((item.at_tti, enabled))

        self.starts_by_tti: dict[int, list[str]] = defaultdict(list)
        self.stops_by_tti: dict[int, list[str]] = defaultdict(list)
        for target, events in state_events.items():
            active = False
            start_tti = 0
            for at_tti, enabled in events:
                if enabled and not active:
                    self.starts_by_tti[at_tti].append(target)
                    active = True
                    start_tti = at_tti
                elif not enabled and active:
                    stop_tti = max(start_tti + 1, at_tti - 1)
                    if stop_tti < horizon_ttis:
                        self.stops_by_tti[stop_tti].append(target)
                    active = False

        self._next_flow_id = self.FIRST_FLOW_ID
        self._active: dict[str, tuple[Flow, list[float]]] = {}
        self._retiring: list[Flow] = []

    def before_tick(self, tti: int) -> None:
        for target in self.stops_by_tti.get(tti, ()):
            entry = self._active.pop(target, None)
            if entry is not None:
                flow, _ = entry
                flow.sender.app_cancel()
                self._retiring.append(flow)

        for target in self.starts_by_tti.get(tti, ()):
            previous = self._active.pop(target, None)
            if previous is not None:
                previous[0].sender.app_cancel()
                self._retiring.append(previous[0])
            flow_id = self._next_flow_id
            self._next_flow_id += 1
            external_ue = self.target_external_ues[target]
            self.link.register_flow(flow_id, external_ue)
            sender = TcpSender(
                flow_id,
                self.cc_factory(mss=self.mss, cwnd=10 * self.mss),
                self.runner.clock,
                self.runner.sched,
                self.mss,
                direction="dl",
                rwnd=self.rwnd_bytes,
            )
            receiver = TcpReceiver(flow_id, self.mss)
            flow = Flow(sender, receiver, ack_over_link=self.ack_over_link)
            sender.app_write(2 * self.mss)
            self.runner.add_flow(flow)
            self._active[target] = (flow, [0.0])

        for target, (flow, credit) in self._active.items():
            sender = flow.sender
            if sender.app_available < self.max_send_buffer_bytes:
                credit[0] += self.bytes_per_tti_by_target[target]
                if credit[0] >= self.mss:
                    chunks = int(credit[0] // self.mss)
                    room = max(0, self.max_send_buffer_bytes - sender.app_available)
                    grant_bytes = min(chunks * self.mss, room)
                    if grant_bytes > 0:
                        sender.app_write(grant_bytes)
                        credit[0] -= grant_bytes
            else:
                credit[0] = min(credit[0], float(self.mss))

        if self._retiring:
            remaining: list[Flow] = []
            for flow in self._retiring:
                if flow.in_network == 0 and flow.acks_in_network == 0:
                    self.runner.remove_flow(flow.sender.flow)
                    self.link.unregister_flow(flow.sender.flow)
                else:
                    remaining.append(flow)
            self._retiring = remaining

    def close(self) -> None:
        for flow, _ in self._active.values():
            flow.sender.app_cancel()
            self.runner.remove_flow(flow.sender.flow)
            self.link.unregister_flow(flow.sender.flow)
        for flow in self._retiring:
            self.runner.remove_flow(flow.sender.flow)
            self.link.unregister_flow(flow.sender.flow)
        self._active.clear()
        self._retiring.clear()


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
    csp_telemetry_interval_s: float = 1.0
    """Interval of CSP telemetry samples written to the shared state table and telemetry.jsonl"""
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
    background_iperf_ues: dict[str, float] = field(default_factory=dict)
    """Optional non-study UE groups driven by application-paced TCP flows (group -> Mbps)."""

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
        interval = config.csp_telemetry_interval_s
        if (
            isinstance(interval, bool)
            or not isinstance(interval, (int, float))
            or not math.isfinite(interval)
            or interval < 0.001
        ):
            raise ValueError("csp_telemetry_interval_s must be at least 0.001")
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
        _validate_overrides(
            "fikore_section_overrides", config.fikore_section_overrides
        )
        _validate_overrides("fikore_ue_overrides", config.fikore_ue_overrides)
        _validate_background_iperf_ues(config.background_iperf_ues)
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
        self._bg_tcp_driver: _BackgroundTcpDriver | None = None
        horizon_ttis = round(duration_s * 1000)
        scheduled_timeline: list[ScheduledSet] = []
        bg_target_rates: dict[str, float] = {}
        bg_target_external_ues: dict[str, int] = {}

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
            all_scenario_groups = set(scenario.ue_ids())
            for bg_group in config.background_iperf_ues:
                if bg_group == study_group:
                    raise ValueError(
                        f"background_iperf_ues cannot include study group {study_group!r}"
                    )
                if bg_group not in all_scenario_groups:
                    raise ValueError(
                        f"background_iperf_ues group {bg_group!r} is not in the scenario"
                    )

            study_targets = (
                [study_group]
                if len(ue_ids) == 1
                else [
                    f"{study_group}_{index}"
                    for index in range(len(ue_ids))
                ]
            )
            section_overrides = {
                (section, key): _ini_value(value)
                for section, values in config.fikore_section_overrides.items()
                for key, value in values.items()
            }
            ue_overrides = {
                ue_id: {
                    key: _ini_value(value)
                    for key, value in values.items()
                }
                for ue_id, values in config.fikore_ue_overrides.items()
            }
            cosim_groups = list(study_groups)
            emulator_n_ues: int | None = len(ue_ids)
            if config.background_iperf_ues:
                cosim_groups.extend(config.background_iperf_ues.keys())
                emulator_n_ues = None
                ue_overrides.setdefault(study_group, {})["n_ues"] = str(len(ue_ids))

            emulator = Emulator(
                EmulatorConfig(
                    binary=config.fikore_binary,
                    base_ini=config.fikore_base_ini,
                    socket_path=str(self.work_dir / "control.sock"),
                    duration_s=duration_s + 1.0,
                    work_dir=str(FIKORE_ROOT),
                    n_ues=emulator_n_ues,
                    delay_budget_s=config.delay_budget_s,
                    random_v=config.random_v,
                    log_path=str(output_dir / "fikore.log"),
                    study_ues=cosim_groups,
                    section_overrides=section_overrides,
                    ue_overrides=ue_overrides,
                )
            )
            ue_id_map = physical_ue_map(
                scenario,
                study_group=study_group,
                ue_ids=ue_ids,
                ue_overrides=config.fikore_ue_overrides,
            )
            ue_target_map = {
                ue_id: study_targets[index]
                for index, ue_id in enumerate(sorted(ue_ids))
            }
            if config.background_iperf_ues:
                physical = 0
                for group in scenario.ue_ids():
                    if group == study_group:
                        physical += len(ue_ids)
                        continue
                    count_override = config.fikore_ue_overrides.get(group, {}).get("n_ues")
                    count = (
                        int(count_override)
                        if count_override is not None
                        else scenario.ue_count(group)
                    )
                    for slot in range(count):
                        external_ue = -1 - physical
                        target_name = group if count == 1 else f"{group}_{slot}"
                        if group in config.background_iperf_ues:
                            ue_target_map[external_ue] = target_name
                            full_target = f"ue/{target_name}"
                            bg_target_external_ues[full_target] = external_ue
                            bg_target_rates[full_target] = float(
                                config.background_iperf_ues[group]
                            )
                        physical += 1

            link = FikoreLink(
                emulator,
                flow_to_ue={},
                ue_id_map=ue_id_map,
                ue_target_map=ue_target_map,
            )
            timeline_value = section_overrides.get(
                ("Control", "timeline_file"),
                scenario.get("Control", "timeline_file"),
            )
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
                scheduled_timeline = load_control_timeline(
                    timeline_path,
                    study_group=study_group,
                    study_targets=study_targets,
                )
                for scheduled in scheduled_timeline:
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
                horizon_ttis=horizon_ttis,
                rwnd=config.receive_window_bytes,
                cc_factory=CONGESTION_CONTROLLERS[config.congestion_control],
                transport=config.transport,
                tcp_connection_mode=config.tcp_connection_mode,
                max_idle_tcp_connections_per_ue=config.max_idle_tcp_connections_per_ue,
                telemetry_every_windows=None,
                ack_over_link=config.ack_over_link,
            ),
        )
        if config.link == "fikore" and bg_target_external_ues:
            assert isinstance(link, FikoreLink)
            self._bg_tcp_driver = _BackgroundTcpDriver(
                link=link,
                runner=self.runner,
                cc_factory=CONGESTION_CONTROLLERS[config.congestion_control],
                mss=self.cfg.mss,
                ack_over_link=config.ack_over_link,
                horizon_ttis=horizon_ttis,
                target_rates_mbps=bg_target_rates,
                target_external_ues=bg_target_external_ues,
                scheduled=scheduled_timeline,
            )
        self.csp_telemetry = self.telemetry_sampler(
            ue_ids, interval_s=config.csp_telemetry_interval_s
        )

    def advance(self) -> NetworkStep:
        if self._bg_tcp_driver is None:
            return super().advance()
        if self._closed:
            raise RuntimeError("the backend is closed")
        if self._final_emitted:
            raise RuntimeError("backend already emitted its final NetworkStep")
        if self._initial:
            self._initial = False
            return NetworkStep(time_s=0.0, events=[], is_final=False)
        horizon = self.cfg.horizon_ttis
        remaining = (
            self.cfg.window_ttis
            if horizon is None
            else max(horizon - self.runner.clock.tti, 0)
        )
        steps = min(self.cfg.window_ttis, remaining)
        for _ in range(steps):
            self._bg_tcp_driver.before_tick(self.runner.clock.tti)
            if horizon is not None and self.runner.clock.tti + 1 >= horizon:
                request_state = getattr(self.link, "request_state_next_step", None)
                if request_state is not None:
                    request_state()
            self.runner.tick()
        self._windows += 1

        now_s = self.runner.clock.s
        events: list[NetworkEvent] = list(self._request_events(now_s))
        self._cleanup_retiring_flows()
        every = self.cfg.telemetry_every_windows
        if every is not None and self._windows % every == 0:
            events.extend(self._telemetry_events(now_s))

        is_final = horizon is not None and self.runner.clock.tti >= horizon
        self._final_emitted = is_final
        return NetworkStep(time_s=now_s, events=events, is_final=is_final)

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
        if self._bg_tcp_driver is not None:
            self._bg_tcp_driver.close()
        super().close()
        effective_ini = self.work_dir / "cosim-run.ini"
        if effective_ini.exists():
            shutil.copy(effective_ini, self.output_dir / "fikore-effective.ini")
        shutil.rmtree(self.work_dir, ignore_errors=True)
