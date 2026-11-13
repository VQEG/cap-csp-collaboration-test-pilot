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
from capcsp.runner.run import run_experiment, swipe_profile_label

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


def test_constant_rate(tmp_path: Path) -> None:
    output = run(tmp_path, "b1-b2-two-ue-constant-rate", duration_s=8)
    check_sessions(output, "constant_rate")
    network = json.loads((CONFIGS / "b1-b2-two-ue-constant-rate.json").read_text())["network"]
    bytes_per_step = network["downlink_rate_mbps"] * 1e6 / 8 * network["step_s"]
    delivered: dict[tuple[int, str], int] = {}
    for line in (output / "network-steps.jsonl").read_text().splitlines():
        step_bytes: dict[int, int] = {}
        for event in json.loads(line)["network_step"]["events"]:
            if event["event_type"] == "DownloadProgress":
                ue_id, key = event["ue_id"], (event["ue_id"], event["request_id"])
                increase = event["bytes_delivered"] - delivered.get(key, 0)
                step_bytes[ue_id] = step_bytes.get(ue_id, 0) + increase
                delivered[key] = event["bytes_delivered"]
        # Each UE has its own rate; whole-byte reporting moves at most one byte per request between steps
        assert all(amount <= bytes_per_step + 3 for amount in step_bytes.values())
    assert {ue_id for ue_id, _ in delivered} == {0, 1}
    for session in (output / "sessions").glob("ue-*.json"):
        record = json.loads(session.read_text())["sessionRecord"]
        assert record["swipe_profile"] == "seeded"
        assert record["user_model"]["watchDurationRangeS"] == [2, 16]


def test_swipe_profile_label_follows_the_user_model() -> None:
    def config(*models: dict | None, **extra) -> dict:
        sessions = [{"config": {"userModel": model} if model else {"swipeTimesS": [1]}} for model in models]
        return {"sessions": sessions, **extra}

    seeded = {"type": "seeded", "watchDurationRangeS": [2, 16]}
    assert swipe_profile_label(config(seeded, seeded)) == "seeded"
    assert swipe_profile_label(config(None, None)) == "scripted"
    assert swipe_profile_label(config(seeded, None)) == "mixed"
    assert swipe_profile_label(config(seeded, swipe_profile="medium")) == "medium"


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


def test_cap_reports_are_event_driven_not_per_step(tmp_path: Path) -> None:
    duration_s = 2.0
    output = run(tmp_path, "b1-b2-two-ue-mock", duration_s=duration_s)
    steps = len((output / "network-steps.jsonl").read_text().splitlines())
    rows = [
        json.loads(line)
        for line in (output / "shared-state.jsonl").read_text().splitlines()
    ]
    cap_times: dict[int, list[float]] = {}
    for row in rows:
        if row.get("direction") == "cap_to_csp":
            cap_times.setdefault(row["ue_id"], []).append(row["time_s"])
    assert set(cap_times) == {0, 1}
    for times in cap_times.values():
        assert len(times) < steps
        # Initial report, at most one per second, plus the final flush past the rate limit.
        assert len(times) <= duration_s + 2
        for previous, current in zip(times, times[1:-1]):
            assert current - previous >= 1.0 - 1e-8


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
    assert manifest["scoring"]["settings"]["fallback_frame_rate_fps"] == 30.0
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


def test_loopback_csp_telemetry_reaches_the_player_at_l2(tmp_path: Path) -> None:
    output = run(
        tmp_path,
        "b1-b2-two-ue-fikore",
        network={"link": "loopback"},
        duration_s=2.5,
        signaling_level="L2",
    )
    rows = [json.loads(line) for line in (output / "telemetry.jsonl").read_text().splitlines()]
    # One sample per UE and second, and a forced sample closing the last half second
    assert [(row["time_s"], row["ue_id"]) for row in rows] == [
        (1.0, 0), (1.0, 1), (2.0, 0), (2.0, 1), (2.5, 0), (2.5, 1)
    ]
    assert any(row["throughput_mbps"] > 0 and row["rtt_ms"] for row in rows)

    audit = [json.loads(line) for line in (output / "shared-state.jsonl").read_text().splitlines()]
    assert {row["ue_id"] for row in audit if row["direction"] == "csp_to_cap"} == {0, 1}

    steps = [json.loads(line)["network_step"] for line in (output / "network-steps.jsonl").read_text().splitlines()]
    assert all(
        event["event_type"] != "NetworkTelemetryReceived" for step in steps for event in step["events"]
    )
    before = [step for step in steps if step["time_s"] < 1.0]
    after = [step for step in steps if step["time_s"] >= 1.0]
    assert all(not step["collaboration"]["csp_by_ue"] for step in before)
    assert all(
        step["collaboration"]["csp_by_ue"]["0"]["achieved_throughput_mbps"] is not None for step in after
    )


def test_csp_telemetry_interval_is_configurable(tmp_path: Path) -> None:
    output = run(
        tmp_path,
        "b1-b2-two-ue-fikore",
        network={"link": "loopback", "csp_telemetry_interval_s": 0.5},
        duration_s=1.0,
    )
    rows = [json.loads(line) for line in (output / "telemetry.jsonl").read_text().splitlines()]
    assert sorted({row["time_s"] for row in rows}) == [0.5, 1.0]


@pytest.mark.skipif(
    not Path(TransportFikoreConfig().fikore_binary).exists(), reason="FikoRE binary is not built (Linux only)"
)
def test_transport_over_fikore(tmp_path: Path) -> None:
    output = run(tmp_path, "b1-b2-two-ue-fikore", duration_s=1)
    check_sessions(output, "transport_fikore")
    manifest = json.loads((output / "run-manifest.json").read_text())
    assert manifest["byte_accounting"]["bytes_conserved"]


def request_signatures(output: Path) -> dict[str, list[tuple[str, int]]]:
    """Request ID and size of every request, per session."""
    signatures = {}
    for session in sorted((output / "sessions").glob("ue-*.json")):
        requests = json.loads(session.read_text())["requests"]
        signatures[session.stem] = [(request["requestId"], request["bytesTotal"]) for request in requests]
    return signatures


@pytest.mark.skipif(
    not Path(TransportFikoreConfig().fikore_binary).exists(), reason="FikoRE is not built"
)
def test_mock_and_fikore_make_the_same_requests_in_the_short_fixture(tmp_path: Path) -> None:
    # Replacing the mock with FikoRE must not change which requests the player makes in the 0.2 s fixture.
    # Timing differs, so a request that completes on the mock can still be in flight on FikoRE when it is
    # cancelled; final states and delivered bytes are therefore not compared.
    (tmp_path / "mock").mkdir()
    (tmp_path / "fikore").mkdir()
    mock = request_signatures(run(tmp_path / "mock", "b1-b2-two-ue-mock"))
    fikore = request_signatures(run(tmp_path / "fikore", "b1-b2-two-ue-fikore"))
    assert mock == fikore
    assert all(mock.values())


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
