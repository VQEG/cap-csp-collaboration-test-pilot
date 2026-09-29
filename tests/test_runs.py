"""End-to-end runs of the example experiment on each backend."""

import json
import shutil
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


def test_mock(tmp_path: Path) -> None:
    output = run(tmp_path, "b1-b2-two-ue-mock")
    check_sessions(output, "mock")
    first, *_, last = (output / "network-steps.jsonl").read_text().splitlines()
    assert json.loads(first)["network_step"]["time_s"] == 0.0
    assert json.loads(last)["network_step"]["is_final"]


def test_transport_over_loopback(tmp_path: Path) -> None:
    output = run(tmp_path, "b1-b2-two-ue-fikore", network={"link": "loopback"}, duration_s=2)
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
