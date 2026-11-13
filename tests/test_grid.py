"""Experiment grids: expansion into cells, parallel runs, resume and merged KPIs."""

import csv
import json
import shutil
from pathlib import Path

import pytest

from capcsp.runner.grid_execution import run_grid
from capcsp.runner.grid_specification import GridSpecification, merge_configurations

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def fikore_grid(**changes) -> dict:
    values = {
        "grid_id": "test",
        "base": json.loads((CONFIGS / "experiments" / "vqeg" / "c1-b1-b2.json").read_text()),
        "conditions": {
            "C1": {"duration_s": 120, "network": {"fikore_base_ini": "configs/fikore/c1_healthy_5g.ini"}},
            "C6": {"duration_s": 180, "network": {"fikore_base_ini": "configs/fikore/c6_mobility_dropout.ini"}},
        },
        "signaling_levels": ["L0", "L2"],
        "ue_counts": [2, 3],
        "behavior_mixes": {"b1-b2": ["simple", "preload"], "b1": ["simple"]},
        "replications": 2,
    }
    return {**values, **changes}


def test_cells_cover_every_combination_with_distinct_run_ids() -> None:
    cells = GridSpecification.from_dict(fikore_grid()).cells()
    assert len(cells) == 2 * 2 * 2 * 2 * 2
    assert len({cell.run_id for cell in cells}) == len(cells)
    assert cells[0].run_id == "test-c1-l0-2ue-b1-b2-r01"
    # Replication 1 comes first, so a partial grid already covers every other axis
    assert {cell.replication for cell in cells[:16]} == {1}


def test_cells_mix_behaviours_and_keep_the_session_templates() -> None:
    cells = GridSpecification.from_dict(fikore_grid()).cells()
    cell = next(cell for cell in cells if cell.ue_count == 3 and cell.behavior_mix == "b1-b2")
    sessions = cell.experiment_config["sessions"]
    assert [session["player_behavior"] for session in sessions] == ["simple", "preload", "simple"]
    assert [session["ue_id"] for session in sessions] == [0, 1, 2]
    assert sessions[1]["rule_config"]["max_preload_segments"] == 4
    assert sessions[2]["config"]["scheduling"]["maxConcurrentRequests"] == 2


def test_a_replication_has_the_same_seeds_in_every_cell() -> None:
    cells = GridSpecification.from_dict(fikore_grid()).cells()
    for replication in (1, 2):
        same_replication = [cell for cell in cells if cell.replication == replication and cell.ue_count == 2]
        network_seeds = {
            cell.experiment_config["network"]["fikore_section_overrides"]["Global"]["seed"] for cell in same_replication
        }
        session_seeds = {
            tuple(session["config"]["seed"] for session in cell.experiment_config["sessions"]) for cell in same_replication
        }
        assert network_seeds == {20260927 + replication}
        assert session_seeds == {(replication * 1000, replication * 1000 + 1)}


def test_conditions_merge_over_the_base() -> None:
    cell = next(cell for cell in GridSpecification.from_dict(fikore_grid()).cells() if cell.condition == "C6")
    network = cell.experiment_config["network"]
    assert network["fikore_base_ini"] == "configs/fikore/c6_mobility_dropout.ini"
    assert network["congestion_control"] == "cubic"
    assert (cell.experiment_config["condition"], cell.experiment_config["duration_s"]) == ("C6", 180)
    assert merge_configurations({"a": {"b": 1, "c": 2}}, {"a": {"c": 3}}) == {"a": {"b": 1, "c": 3}}


def test_a_grid_file_can_hold_the_base_experiment_itself(tmp_path: Path) -> None:
    base = json.loads((CONFIGS / "experiments" / "b1-b2-two-ue-mock.json").read_text())
    grid_path = tmp_path / "grid.json"
    grid_path.write_text(json.dumps({"grid_id": "inline", "base": base, "ue_counts": [3]}))
    cells = GridSpecification.from_file(grid_path).cells()
    assert [cell.run_id for cell in cells] == ["inline-example-only-l0-3ue-b1-b2-r01"]


@pytest.mark.parametrize(
    "changes",
    [
        {"ue_counts": []},
        {"ue_counts": [0]},
        {"replications": 0},
        {"behavior_mixes": {"odd": ["simple", "unknown"]}},
        {"signaling_levels": ["L9"]},
        {"axes": {}},
    ],
)
def test_invalid_grids_are_rejected(changes: dict) -> None:
    with pytest.raises(ValueError):
        GridSpecification.from_dict(fikore_grid(**changes))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_grid_runs_in_parallel_resumes_and_merges_kpis(tmp_path: Path) -> None:
    grid_path = tmp_path / "grid.json"
    grid = {
        "grid_id": "mock",
        "base": str(CONFIGS / "experiments" / "b1-b2-two-ue-mock.json"),
        "conditions": {"ok": {}, "broken": {"network": {"unknown_setting": 1}}},
        "ue_counts": [2, 3],
        "replications": 1,
    }
    grid_path.write_text(json.dumps(grid))
    specification = GridSpecification.from_file(grid_path)
    output = tmp_path / "out"

    outcomes = run_grid(specification, output, jobs=2)
    assert {outcome.run_id: outcome.status for outcome in outcomes} == {
        "mock-ok-l0-2ue-b1-b2-r01": "completed",
        "mock-ok-l0-3ue-b1-b2-r01": "completed",
        "mock-broken-l0-2ue-b1-b2-r01": "failed",
        "mock-broken-l0-3ue-b1-b2-r01": "failed",
    }
    assert (output / "mock-broken-l0-2ue-b1-b2-r01" / "error.log").exists()
    with open(output / "kpis.csv", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 2 + 3
    assert [row["player_behavior"] for row in rows[2:]] == ["simple", "preload", "simple"]
    assert {(row["ue_count"], row["behavior_mix"], row["replication"]) for row in rows} == {
        ("2", "b1-b2", "1"),
        ("3", "b1-b2", "1"),
    }

    # A second invocation runs only the failed cells again
    statuses = [outcome.status for outcome in run_grid(specification, output, jobs=2)]
    assert sorted(statuses) == ["failed", "failed", "skipped", "skipped"]
    with open(output / "index.csv", newline="") as file:
        index = {row["run_id"]: row["status"] for row in csv.DictReader(file)}
    assert index["mock-ok-l0-2ue-b1-b2-r01"] == "completed"

    # With force, finished cells run again
    statuses = [outcome.status for outcome in run_grid(specification, output, jobs=2, force=True)]
    assert sorted(statuses) == ["completed", "completed", "failed", "failed"]
