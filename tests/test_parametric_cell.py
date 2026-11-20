"""Tests for the parametric 5G cell synthesizer and its grid integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from fikore_transport.scenario import ScenarioDocument

from capcsp.network.parametric_cell import (
    CORE6_PRESET_IDS,
    PARAMETRIC_CELL_PRESETS,
    ParametricCellConfig,
    synthesize_parametric_cell,
)
from capcsp.network.transport_fikore import TransportFikoreConfig, load_control_timeline
from capcsp.runner.grid_specification import GridSpecification

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("preset_id", sorted(PARAMETRIC_CELL_PRESETS))
def test_all_presets_synthesize_valid_ini_and_timeline(preset_id: str, tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": preset_id})
    out = synthesize_parametric_cell(cfg, duration_s=30.0, seed=20260927, work_dir=tmp_path / preset_id)
    assert out.ini_path.is_file()
    doc = ScenarioDocument.read(str(out.ini_path))
    assert "studyVqeg" in doc.ue_ids()

    if cfg.load_rho == 0.0:
        assert out.pool_ue_count == 0
        assert out.background_iperf_ues == {}
    else:
        assert out.pool_ue_count >= 4
        assert out.mean_active_bg_ues > 0.0
        assert out.session_count > 0
        assert out.background_iperf_ues == {"backgroundSfV": cfg.bg_bitrate_mbps}
        assert "backgroundSfV" in doc.ue_ids()

    if out.timeline_path is not None:
        scheduled = load_control_timeline(
            out.timeline_path,
            study_group="studyVqeg",
            study_targets=["studyVqeg_0", "studyVqeg_1"],
        )
        assert len(scheduled) > 0
        if cfg.study_mobility == "vehicular_traverse":
            study_cmds = [item for item in scheduled if item.target in ("ue/studyVqeg_0", "ue/studyVqeg_1")]
            assert len(study_cmds) > 20


def test_seed_is_deterministic_and_distinct_across_replications(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M05"})
    a1 = synthesize_parametric_cell(cfg, duration_s=40.0, seed=20260928, work_dir=tmp_path / "a1")
    a2 = synthesize_parametric_cell(cfg, duration_s=40.0, seed=20260928, work_dir=tmp_path / "a2")
    b1 = synthesize_parametric_cell(cfg, duration_s=40.0, seed=20260929, work_dir=tmp_path / "b1")

    assert a1.timeline_path is not None and a2.timeline_path is not None and b1.timeline_path is not None
    assert a1.timeline_path.read_text() == a2.timeline_path.read_text()
    assert a1.timeline_path.read_text() != b1.timeline_path.read_text()


def test_custom_overrides_scale_active_ues_with_load_and_bg_bitrate(tmp_path: Path) -> None:
    low_load = ParametricCellConfig.from_dict(
        {"preset": "M01", "load_rho": 0.5, "bg_bitrate_mbps": 4.0}
    )
    high_load = ParametricCellConfig.from_dict(
        {"preset": "M01", "load_rho": 1.0, "bg_bitrate_mbps": 4.0}
    )
    lower_per_ue_rate = ParametricCellConfig.from_dict(
        {"preset": "M01", "load_rho": 0.5, "bg_bitrate_mbps": 2.0}
    )

    # Raising load_rho from 0.0 on M01 automatically enables cell_disk spatial sampling
    assert low_load.bg_spatial == "cell_disk"
    s_low = synthesize_parametric_cell(low_load, duration_s=20.0, seed=1, work_dir=tmp_path / "low")
    s_high = synthesize_parametric_cell(high_load, duration_s=20.0, seed=1, work_dir=tmp_path / "high")
    s_2m = synthesize_parametric_cell(lower_per_ue_rate, duration_s=20.0, seed=1, work_dir=tmp_path / "2m")

    assert pytest.approx(s_high.mean_active_bg_ues, rel=1e-3) == 2.0 * s_low.mean_active_bg_ues
    assert s_2m.mean_active_bg_ues > 1.8 * s_low.mean_active_bg_ues
    assert s_2m.background_iperf_ues == {"backgroundSfV": 2.0}


def test_transport_fikore_config_validates_parametric_cell() -> None:
    cfg = TransportFikoreConfig.from_dict(
        {
            "link": "loopback",
            "parametric_cell": {
                "preset": "M10",
                "study_speed_kmh": 50.0,
                "bg_bitrate_mbps": 6.0,
            },
        }
    )
    assert cfg.fikore_base_ini is None
    assert cfg.parametric_cell is not None
    assert cfg.parametric_cell.study_speed_kmh == 50.0
    assert cfg.parametric_cell.bg_bitrate_mbps == 6.0

    with pytest.raises(ValueError, match="not both"):
        TransportFikoreConfig.from_dict(
            {
                "fikore_base_ini": "configs/fikore/c1_healthy_5g.ini",
                "parametric_cell": {"preset": "M01"},
            }
        )


@pytest.mark.parametrize(
    "bad_cell",
    [
        {"preset": "M99"},
        {"bandwidth_mhz": 35},
        {"load_rho": -0.1},
        {"bg_bitrate_mbps": 0.0},
        {"study_mobility": "teleport"},
        {"unknown_knob": 1},
    ],
)
def test_invalid_parametric_cell_settings_are_rejected(bad_cell: dict) -> None:
    with pytest.raises(ValueError):
        ParametricCellConfig.from_dict(bad_cell)


def test_core6_and_load_sweep_grids_expand_cleanly() -> None:
    core6_spec = GridSpecification.from_file(REPO_ROOT / "configs" / "grids" / "layered-core6.json")
    core6_cells = core6_spec.cells()
    assert len(core6_cells) == len(CORE6_PRESET_IDS) * 2 * 5
    assert {cell.condition for cell in core6_cells} == set(CORE6_PRESET_IDS)
    for cell in core6_cells[:12:2]:
        tf_cfg = TransportFikoreConfig.from_dict(cell.experiment_config["network"])
        assert tf_cfg.parametric_cell is not None
        assert tf_cfg.parametric_cell.preset == cell.condition

    full_spec = GridSpecification.from_file(REPO_ROOT / "configs" / "grids" / "layered-m01-m11.json")
    full_cells = full_spec.cells()
    assert len(full_cells) == 11 * 2 * 20
    # Paired B1 and B2 runs in each replication share both Global.seed and user swipe seed
    b1_cell, b2_cell = full_cells[0], full_cells[1]
    assert (b1_cell.behavior_mix, b2_cell.behavior_mix) == ("b1", "b2")
    assert (
        b1_cell.experiment_config["network"]["fikore_section_overrides"]["Global"]["seed"]
        == b2_cell.experiment_config["network"]["fikore_section_overrides"]["Global"]["seed"]
    )
    assert (
        b1_cell.experiment_config["sessions"][0]["config"]["seed"]
        == b2_cell.experiment_config["sessions"][0]["config"]["seed"]
    )

    sweep_spec = GridSpecification.from_file(REPO_ROOT / "configs" / "grids" / "parametric-load-sweep.json")
    sweep_cells = sweep_spec.cells()
    assert len(sweep_cells) == 5 * 2 * 3
    rhos = [
        TransportFikoreConfig.from_dict(c.experiment_config["network"]).parametric_cell.load_rho  # type: ignore[union-attr]
        for c in sweep_cells[:10:2]
    ]
    assert rhos == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_mixed_parametric_and_legacy_grid_overlays_resolve_cleanly(tmp_path: Path) -> None:
    """Verify the exact grid overlay shape emitted by simulator-explorer when mixing M04, CUSTOM, and legacy C2."""
    import json
    from capcsp.runner.run import load_config

    grid = {
        "grid_id": "explorer",
        "base": {
            "run_id": "explorer-base",
            "network_backend": "transport_fikore",
            "network": {
                "congestion_control": "cubic",
                "receive_window_bytes": 262144,
                "tcp_connection_mode": "persistent",
                "max_idle_tcp_connections_per_ue": 6,
                "step_ms": 10,
                "study_ues": ["studyVqeg"],
                "ack_over_link": True,
                "delay_budget_s": None,
                "random_v": None,
            },
            "condition": "M04",
            "signaling_level": "L0",
            "clock_mode": "simulation",
            "content": "../content/sfv-portrait-hd-90s.json",
            "duration_s": 65,
            "sessions": [
                {
                    "ue_id": 0,
                    "player_behavior": "simple",
                    "config": {
                        "sessionId": "generic-ue0",
                        "seed": 1000,
                        "scheduling": {"maxConcurrentRequests": 2},
                        "userModel": {"type": "seeded", "watchDurationRangeS": [2, 16]},
                    },
                    "rule_config": {"activeBufferTargetSegments": 2},
                },
                {
                    "ue_id": 1,
                    "player_behavior": "preload",
                    "config": {
                        "sessionId": "generic-ue1",
                        "seed": 1001,
                        "scheduling": {"maxConcurrentRequests": 3},
                        "userModel": {"type": "seeded", "watchDurationRangeS": [2, 16]},
                    },
                    "rule_config": {
                        "activeBufferTargetSegments": 2,
                        "max_preload_segments": 4,
                        "preload_segments_per_video": 2,
                    },
                },
            ],
        },
        "conditions": {
            "M04": {
                "condition": "M04",
                "duration_s": 65,
                "network": {"receive_window_bytes": 262144, "parametric_cell": {"preset": "M04"}},
            },
            "CUSTOM": {
                "condition": "CUSTOM",
                "duration_s": 65,
                "network": {
                    "receive_window_bytes": 262144,
                    "parametric_cell": {
                        "preset": "custom",
                        "bandwidth_mhz": 40,
                        "study_position": "custom",
                        "study_distance_m": 420.0,
                        "study_mobility": "vehicular_traverse",
                        "study_speed_kmh": 55.0,
                        "traverse_min_distance_m": 150.0,
                        "traverse_max_distance_m": 650.0,
                        "load_rho": 0.8,
                        "bg_spatial": "cell_disk",
                        "bg_bitrate_mbps": 5.5,
                        "arrival_mode": "mmpp",
                        "mean_hold_s": 10.0,
                        "burst_amplitude": 0.6,
                        "burst_regime_s": 12.0,
                    },
                },
            },
            "C2": {
                "condition": "C2",
                "duration_s": 120,
                "network": {
                    "receive_window_bytes": 1048576,
                    "fikore_base_ini": "configs/fikore/c2_plan_capped.ini",
                },
            },
        },
        "signaling_levels": ["L0"],
        "ue_counts": [2],
        "behavior_mixes": {"b1-b2": ["simple", "preload"]},
        "replications": 2,
        "network_seed_base": 20260927,
    }

    grid_file = tmp_path / "configs" / "grids" / "my-grid.json"
    grid_file.parent.mkdir(parents=True)
    # Mirror relative content resolution from repo configs/grids/
    real_grid_file = REPO_ROOT / "configs" / "grids" / "_tmp_explorer_check.json"
    try:
        real_grid_file.write_text(json.dumps(grid))
        spec = GridSpecification.from_file(real_grid_file)
    finally:
        real_grid_file.unlink(missing_ok=True)

    cells = spec.cells()
    assert len(cells) == 6
    for idx, cell in enumerate(cells):
        cell_path = tmp_path / f"cell-{idx}.json"
        cell_path.write_text(json.dumps(cell.experiment_config))
        loaded = load_config(cell_path)
        tf_cfg = TransportFikoreConfig.from_dict(loaded["network"])
        if cell.condition == "C2":
            assert tf_cfg.fikore_base_ini is not None
            assert tf_cfg.parametric_cell is None
        else:
            assert tf_cfg.fikore_base_ini is None
            assert tf_cfg.parametric_cell is not None

