"""End-to-end runs of the example experiment on each backend."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from capcsp.network.transport_fikore import TransportFikoreConfig
from capcsp.runner.kpis import collect_kpis
from capcsp.runner.report import write_report
from capcsp.runner.run import run_experiment

CONFIGS = Path(__file__).resolve().parents[1] / "configs" / "experiments"
TERMINAL_STATES = {"COMPLETED", "CANCELLED"}

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")


def run(tmp_path: Path, name: str, **overrides: object) -> Path:
    config = json.loads((CONFIGS / f"{name}.json").read_text())
    config.update(overrides)
    config_path = tmp_path / f"{name}.json"
    # Keep the default content path, which is resolved relative to the config file
    config_path.write_text(json.dumps(config))
    output = tmp_path / "out"
    manifest = run_experiment(config_path, output)
    assert manifest["status"] == "completed"
    return output


def check_sessions(output: Path, backend: str) -> None:
    rows = collect_kpis(output)
    assert [row["player_behavior"] for row in rows] == ["simple", "preload"]
    for row in rows:
        assert row["network_backend"] == backend
        assert row["requests"] > 0
    for session in (output / "sessions").glob("ue-*.json"):
        requests = json.loads(session.read_text())["requests"]
        for request in requests:
            assert request["state"] in TERMINAL_STATES
            assert 0 <= request["bytesDelivered"] <= request["bytesTotal"]
    write_report([output], output / "report.md")
    assert "## KPIs per UE" in (output / "report.md").read_text()


def test_kpis_ignore_swipes_without_a_playback_measurement(
    tmp_path: Path,
) -> None:
    output = tmp_path / "out"
    sessions = output / "sessions"
    sessions.mkdir(parents=True)
    (output / "run-manifest.json").write_text(
        json.dumps(
            {
                "run_id": "unmeasured-swipe",
                "network_backend": "mock",
                "ue_ids": [0],
                "sim_time_s": 2.0,
                "config": {"duration_s": 2.0},
            }
        )
    )
    (sessions / "ue-0.json").write_text(
        json.dumps(
            {
                "terminationReason": "completed",
                "requests": [],
                "sessionRecord": {
                    "network_backend": "mock",
                    "player_behavior": "simple",
                    "session_summary": {
                        "swipe_to_playback_delays_s": [None, 0.5]
                    },
                },
            }
        )
    )
    row = collect_kpis(output)[0]
    assert row["swipes"] == 2
    assert row["swipe_to_playback_delay_mean_s"] == 0.5


def test_mock(tmp_path: Path) -> None:
    output = run(tmp_path, "b1-b2-two-ue-mock")
    check_sessions(output, "mock")
    lines = (output / "network-steps.jsonl").read_text().splitlines()
    first, *_, last = lines
    assert json.loads(first)["network_step"]["time_s"] == 0.0
    assert json.loads(last)["network_step"]["is_final"]
    step1 = json.loads(lines[1])["network_step"]
    assert "collaboration" in step1
    assert all(
        e.get("event_type") != "NetworkTelemetryReceived" for e in step1.get("events", [])
    )


def test_l3_dummy_writes_csp_control(tmp_path: Path) -> None:
    output = run(
        tmp_path,
        "b1-b2-two-ue-mock",
        signaling_level="L3",
        csp_controller="dummy",
        duration_s=0.2,
    )
    manifest = json.loads((output / "run-manifest.json").read_text())
    assert manifest["csp_control_log"] == "csp-control.jsonl"
    assert (output / "csp-control.jsonl").is_file()


def test_l0_determinism_hash_stable(tmp_path: Path) -> None:
    """Session/KPI determinism for default L0 mock (hash file set excludes L3-only artifacts)."""
    config = CONFIGS / "b1-b2-two-ue-mock.json"
    first = _run_with_hash_seed(config, tmp_path / "a", "1")
    second = _run_with_hash_seed(config, tmp_path / "b", "2")
    assert first == second


def test_run_writes_p1203_scores(tmp_path: Path) -> None:
    output = run(tmp_path, "b1-b2-two-ue-mock", duration_s=8)
    for row in collect_kpis(output):
        assert 1 <= row["p1203_o46"] <= 5
    record = json.loads((output / "sessions" / "ue-0.json").read_text())["sessionRecord"]
    assert any(video["p1204_1_segment_scores"] for video in record["videos"])
    manifest = json.loads((output / "run-manifest.json").read_text())
    assert manifest["shared_state_log"] == "shared-state.jsonl"
    assert (output / "shared-state.jsonl").is_file()
    assert manifest.get("csp_control_log") is None
    assert not (output / "csp-control.jsonl").exists()
    assert manifest["clock_mode"] == "simulation"
    assert manifest["cap_application"] == "sfv"
    assert manifest["scoring"]["settings"]["frame_rate_fps"] == 30.0
    write_report([output], output / "report.md")
    report = (output / "report.md").read_text()
    assert "## P.1203 Scores per Video" in report
    assert "ITU-T P.1204.1 Mode 0" in report


@pytest.mark.parametrize("tcp_connection_mode", ["persistent", "fresh"])
def test_transport_over_loopback(tmp_path: Path, tcp_connection_mode: str) -> None:
    network = {"link": "loopback", "tcp_connection_mode": tcp_connection_mode}
    output = run(tmp_path, "b1-b2-two-ue-fikore", network=network, duration_s=2)
    check_sessions(output, "transport_fikore")
    assert (output / "telemetry.jsonl").read_text()


@pytest.mark.skipif(
    not Path(TransportFikoreConfig().fikore_binary).exists(), reason="FikoRE binary is not built (Linux only)"
)
def test_transport_over_fikore(tmp_path: Path) -> None:
    output = run(tmp_path, "b1-b2-two-ue-fikore", duration_s=1)
    check_sessions(output, "transport_fikore")
    manifest = json.loads((output / "run-manifest.json").read_text())
    assert manifest["byte_accounting"]["bytes_conserved"]


def _run_with_hash_seed(config: Path, output: Path, hash_seed: str) -> dict[str, str]:
    """Run `config` in a new process and return a digest per result file."""
    subprocess.run(
        [sys.executable, "-m", "capcsp.cli", "run", str(config), str(output)],
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
    )
    files = [
        output / "network-steps.jsonl",
        output / "telemetry.jsonl",
        output / "shared-state.jsonl",
        *sorted((output / "sessions").glob("*.json")),
    ]
    return {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in files}


@pytest.mark.skipif(
    not Path(TransportFikoreConfig().fikore_binary).exists(), reason="FikoRE is not built"
)
def test_fikore_run_repeats_with_a_different_python_hash_seed(tmp_path: Path) -> None:
    config = CONFIGS / "stall-example" / "stall-example-b1-b2.json"
    first = _run_with_hash_seed(config, tmp_path / "first", "1")
    second = _run_with_hash_seed(config, tmp_path / "second", "2")
    assert first == second
    # The stalls come from the timeline set by the section override in the config
    record = json.loads((tmp_path / "first" / "sessions" / "ue-0.json").read_text())["sessionRecord"]
    assert record["session_summary"]["stall_count_total"] == 1
