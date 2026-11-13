"""Run one experiment: SFV player sessions on one network backend.

Output directory layout:

- run-manifest.json: configuration, revisions, timing and byte accounting
- sessions/ue-<id>.json: full player result per UE, including the scored session record
- network-steps.jsonl: every NetworkStep with the player's response
- telemetry.jsonl: CSP telemetry samples, every csp_telemetry_interval_s (1 s by default)
- shared-state.jsonl: append-only audit log for the VQEG shared state table
- csp-control.jsonl: CSPController proposals at signaling L3+ (when configured)
- player.log: stderr of the player process
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from capcsp.network.constant_rate import ConstantRateBackend
from capcsp.network.mock import MockNetworkBackend
from capcsp.network.transport_fikore import TransportFikoreBackend, TransportFikoreConfig
from capcsp.collaboration.factory import build_collaboration_stack
from capcsp.player.bridge import NodePlayerBridge, run_sessions
from capcsp.scoring.session_scoring import ScoringSettings, score_run
from capcsp.shared_state.signaling import parse_signaling_level
from capcsp.shared_state.table import InMemorySharedStateTable
from capcsp.shared_state.types import CspFields

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTENT = REPO_ROOT / "sfv-reference-implementation" / "fixtures" / "content" / "content.json"
BACKENDS = ("mock", "constant_rate", "transport_fikore")

# Keys passed through to the player process
PLAYER_KEYS = ("sessions", "duration_s", "timingDefaults", "run_id", "signaling_level", "condition", "swipe_profile")


def load_config(path: Path) -> dict[str, Any]:
    """Read and check an experiment configuration."""
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("network_backend") not in BACKENDS:
        raise ValueError(f"network_backend must be one of {BACKENDS}")
    if not isinstance(config.get("network", {}), dict):
        raise ValueError("network must be an object of backend settings")
    duration = config.get("duration_s")
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError("duration_s must be positive")
    sessions = config.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("sessions must be a non-empty list")
    ue_ids = [session.get("ue_id") for session in sessions]
    if any(not isinstance(ue_id, int) or isinstance(ue_id, bool) or ue_id < 0 for ue_id in ue_ids):
        raise ValueError("Every session needs a non-negative integer ue_id")
    if len(set(ue_ids)) != len(ue_ids):
        raise ValueError("Duplicate ue_id")
    for session in sessions:
        if session.get("player_behavior") not in ("simple", "preload"):
            raise ValueError(f"UE {session['ue_id']}: player_behavior must be 'simple' (B1) or 'preload' (B2)")
    ScoringSettings.from_dict(config.get("scoring", {}))
    content = config.get("content")
    config["content_path"] = str((path.parent / content).resolve() if content else DEFAULT_CONTENT)
    config.setdefault("run_id", path.stem)
    config.setdefault("signaling_level", "L0")
    config.setdefault("clock_mode", "simulation")
    parse_signaling_level(config["signaling_level"])
    controller = config.get("csp_controller")
    if controller is not None and controller != "dummy":
        raise ValueError('csp_controller must be null or "dummy"')
    if config.get("clock_mode") != "simulation":
        raise ValueError('Only clock_mode "simulation" is implemented')
    return config


def create_backend(config: dict[str, Any], output_dir: Path) -> Any:
    ue_ids = [session["ue_id"] for session in config["sessions"]]
    settings = dict(config.get("network", {}))
    if config["network_backend"] == "mock":
        return MockNetworkBackend(ue_ids=ue_ids, duration_s=config["duration_s"], **settings)
    if config["network_backend"] == "constant_rate":
        return ConstantRateBackend(ue_ids=ue_ids, duration_s=config["duration_s"], **settings)
    return TransportFikoreBackend(
        TransportFikoreConfig.from_dict(settings),
        ue_ids=ue_ids,
        duration_s=config["duration_s"],
        output_dir=output_dir,
    )


def git_revision(path: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True, check=False
        ).stdout.strip()

    return {"commit": git("rev-parse", "HEAD") or None, "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row) + "\n")


def swipe_profile_label(config: dict[str, Any]) -> str:
    """The `swipe_profile` of the session records.

    Without an explicit `swipe_profile`, SFV labels every session "scripted", even one
    with a `userModel`. Use the user model type of the sessions instead.
    """
    if "swipe_profile" in config:
        return config["swipe_profile"]
    model_types = {
        session.get("config", {}).get("userModel", {}).get("type", "scripted") for session in config["sessions"]
    }
    return model_types.pop() if len(model_types) == 1 else "mixed"


def run_experiment(
    config_path: Path, output_dir: Path, on_step: Callable[[float], None] | None = None
) -> dict[str, Any]:
    """Run the experiment in `config_path` and write all outputs to `output_dir`.

    `on_step` receives the simulated time of every network step, for progress displays.
    """
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sessions").mkdir(exist_ok=True)
    player_config = {key: config[key] for key in PLAYER_KEYS if key in config}
    player_config["dataset"] = json.loads(Path(config["content_path"]).read_text(encoding="utf-8"))
    player_config["network_backend"] = config["network_backend"]
    player_config["swipe_profile"] = swipe_profile_label(config)
    ue_ids = {session["ue_id"] for session in config["sessions"]}

    shared_state_log_name = "shared-state.jsonl"
    shared_state_path = output_dir / shared_state_log_name
    shared_table = InMemorySharedStateTable(
        signaling_level=config["signaling_level"],
        log_path=shared_state_path,
    )
    csp_control_log_name: str | None = None
    csp_control_path: Path | None = None
    if config.get("csp_controller") == "dummy" and parse_signaling_level(config["signaling_level"]) >= 3:
        csp_control_log_name = "csp-control.jsonl"
        csp_control_path = output_dir / csp_control_log_name

    manifest: dict[str, Any] = {
        "run_id": config["run_id"],
        "status": "failed",
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "config_path": str(config_path.resolve()),
        "config": {key: value for key, value in config.items() if key != "content_path"},
        "content_path": config["content_path"],
        "network_backend": config["network_backend"],
        "ue_ids": sorted(ue_ids),
        "revisions": {
            "capcsp": git_revision(REPO_ROOT),
            "fikore": git_revision(REPO_ROOT / "5g-network-emulator"),
            "sfv_reference_implementation": git_revision(REPO_ROOT / "sfv-reference-implementation"),
        },
        "shared_state_log": shared_state_log_name,
        "csp_control_log": csp_control_log_name,
        "clock_mode": config["clock_mode"],
        "cap_application": "sfv",
    }
    transcript: list[dict[str, Any]] = []
    telemetry: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    backend = create_backend(config, output_dir)
    collaboration = None
    try:
        plan_downlink = config.get("plan_downlink_mbps_by_ue")
        if plan_downlink is not None:
            if not isinstance(plan_downlink, dict):
                raise ValueError("plan_downlink_mbps_by_ue must be a dict when set")
            plan_downlink = {int(k): float(v) for k, v in plan_downlink.items()}
        if plan_downlink and parse_signaling_level(config["signaling_level"]) >= 1:
            for ue_id, plan_mbps in plan_downlink.items():
                if ue_id not in ue_ids:
                    continue
                shared_table.write_csp_fields(
                    ue_id,
                    CspFields(
                        updated_at_s=0.0,
                        plan_downlink_mbps=plan_mbps,
                        achieved_throughput_mbps=None,
                        rtt_ms=None,
                        loss_rate=None,
                        congestion_rate=None,
                    ),
                )
        with NodePlayerBridge(player_config, log_path=output_dir / "player.log") as bridge:
            collaboration = build_collaboration_stack(
                config,
                table=shared_table,
                backend=backend,
                bridge=bridge,
                plan_downlink_mbps_by_ue=plan_downlink,
                csp_control_log_path=csp_control_path,
            )
            result = run_sessions(
                backend,
                bridge,
                ue_ids=ue_ids,
                transcript=transcript,
                telemetry=telemetry,
                collaboration=collaboration,
                on_step=on_step,
            )
        manifest["status"] = "completed"
    finally:
        shared_table.close()
        if collaboration is not None and collaboration.csp_controller is not None:
            close = getattr(collaboration.csp_controller, "close", None)
            if callable(close):
                close()
        backend.close()
        manifest["wall_s"] = round(time.perf_counter() - wall_start, 3)
        manifest["network_steps"] = len(transcript)
        accounting = getattr(backend, "accounting", None)
        if accounting is not None:
            manifest["byte_accounting"] = accounting()
        write_jsonl(output_dir / "network-steps.jsonl", transcript)
        write_jsonl(output_dir / "telemetry.jsonl", telemetry)
        write_json(output_dir / "run-manifest.json", manifest)

    manifest["sim_time_s"] = result["sim_time_s"]
    for session in result["sessions"]:
        write_json(output_dir / "sessions" / f"ue-{session['ue_id']}.json", session["result"])
    write_json(output_dir / "run-manifest.json", manifest)
    manifest["scoring"] = score_run(
        output_dir, player_config["dataset"], ScoringSettings.from_dict(config.get("scoring", {}))
    )
    write_json(output_dir / "run-manifest.json", manifest)
    return manifest
