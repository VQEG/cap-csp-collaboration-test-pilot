"""Run one experiment: SFV player sessions on one network backend.

Output directory layout:

- run-manifest.json: configuration, revisions, timing and byte accounting
- sessions/ue-<id>.json: full player result per UE, including the session record
- network-steps.jsonl: every NetworkStep with the player's response
- telemetry.jsonl: NetworkTelemetryReceived events
- player.log: stderr of the player process
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capcsp.network.mock import MockNetworkBackend
from capcsp.network.transport_fikore import TransportFikoreBackend, TransportFikoreConfig
from capcsp.player.bridge import NodePlayerBridge, run_sessions

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTENT = REPO_ROOT / "sfv-reference-implementation" / "fixtures" / "content" / "content.json"
BACKENDS = ("mock", "transport_fikore")

# Keys passed through to the player process
PLAYER_KEYS = ("sessions", "duration_s", "timingDefaults", "run_id", "signaling_level", "condition", "swipe_profile")


def load_config(path: Path) -> dict[str, Any]:
    """Read and check an experiment configuration."""
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("network_backend") not in BACKENDS:
        raise ValueError(f"network_backend must be one of {BACKENDS}")
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
    content = config.get("content")
    config["content_path"] = str((path.parent / content).resolve() if content else DEFAULT_CONTENT)
    config.setdefault("run_id", path.stem)
    return config


def create_backend(config: dict[str, Any], output_dir: Path) -> Any:
    ue_ids = [session["ue_id"] for session in config["sessions"]]
    settings = dict(config.get("network", {}))
    if config["network_backend"] == "mock":
        return MockNetworkBackend(ue_ids=ue_ids, duration_s=config["duration_s"], **settings)
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


def run_experiment(config_path: Path, output_dir: Path) -> dict[str, Any]:
    """Run the experiment in `config_path` and write all outputs to `output_dir`."""
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sessions").mkdir(exist_ok=True)
    player_config = {key: config[key] for key in PLAYER_KEYS if key in config}
    player_config["dataset"] = json.loads(Path(config["content_path"]).read_text(encoding="utf-8"))
    player_config["network_backend"] = config["network_backend"]
    ue_ids = {session["ue_id"] for session in config["sessions"]}

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
    }
    transcript: list[dict[str, Any]] = []
    telemetry: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    backend = create_backend(config, output_dir)
    try:
        with NodePlayerBridge(player_config, log_path=output_dir / "player.log") as bridge:
            result = run_sessions(backend, bridge, ue_ids=ue_ids, transcript=transcript, telemetry=telemetry)
        manifest["status"] = "completed"
    finally:
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
    return manifest
