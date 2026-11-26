"""Tests for the parametric 5G cell synthesizer and its grid integration."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from fikore_transport.scenario import ScenarioDocument

from capcsp.network.parametric_cell import (
    BUS_CYCLE_S,
    BUS_DRIVE_PHASE_S,
    BUS_STOP_DWELL_S,
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
        if cfg.study_mobility in ("vehicular_traverse", "urban_bus"):
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
                "fikore_base_ini": "5g-network-emulator/config/control_demo.ini",
                "parametric_cell": {"preset": "M01"},
            }
        )


def _study_waypoints(timeline_path: Path) -> list[tuple[int, dict]]:
    """Return `(at_tti, set)` of every `mobility.pos_x_m` command of the study UE."""
    waypoints: list[tuple[int, dict]] = []
    for line in timeline_path.read_text().splitlines():
        message = json.loads(line)
        for cmd in message["cmds"]:
            if cmd["target"] == "ue/studyVqeg" and "mobility.pos_x_m" in cmd["set"]:
                waypoints.append((message["at_tti"], cmd["set"]))
    return waypoints


def _reflect(distance_m: float, d_min: float, d_max: float) -> float:
    span_m = d_max - d_min
    phase = (distance_m % (2.0 * span_m)) / span_m
    return d_min + (phase if phase <= 1.0 else 2.0 - phase) * span_m


def test_m11_is_an_urban_bus_preset() -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M11"})
    assert cfg.study_mobility == "urban_bus"
    assert cfg.study_speed_kmh == 25.0
    assert cfg.study_distance_m == 220.0
    assert (cfg.traverse_min_distance_m, cfg.traverse_max_distance_m) == (220.0, 650.0)
    assert cfg.load_rho == 0.50
    assert cfg.bg_spatial == "cell_disk"
    assert cfg.study_dl_rmax_mbps is None
    assert (BUS_DRIVE_PHASE_S, BUS_STOP_DWELL_S, BUS_CYCLE_S) == (15.0, 10.0, 25.0)


@pytest.mark.parametrize(
    ("mobility", "speed"),
    [("static", 0.0), ("urban_bus", 25.0), ("vehicular_traverse", 73.26)],
)
def test_mobility_default_speed_when_only_mobility_is_set(mobility: str, speed: float) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M01", "study_mobility": mobility})
    assert cfg.study_speed_kmh == speed


def test_urban_bus_moves_study_ue_only_through_the_timeline(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M11"})
    out = synthesize_parametric_cell(cfg, duration_s=15.0, seed=20260927, work_dir=tmp_path / "m11")
    doc = ScenarioDocument.read(str(out.ini_path))
    # Position and instantaneous speed come from the 250 ms timeline, so the INI headers are static.
    assert doc.get_ue("studyVqeg", "mobility_type") == "0"
    assert float(doc.get_ue("studyVqeg", "speed")) == pytest.approx(0.0)
    assert float(doc.get_ue("studyVqeg", "pos_x")) == pytest.approx(220.0)
    assert doc.get_ue("backgroundSfV", "mobility_type") == "0"
    assert float(doc.get_ue("backgroundSfV", "speed")) == pytest.approx(0.0)


def test_urban_bus_trajectory_has_stationary_dwell_windows(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M11"})
    out = synthesize_parametric_cell(cfg, duration_s=65.0, seed=20260927, work_dir=tmp_path / "m11")
    assert out.timeline_path is not None
    waypoints = _study_waypoints(out.timeline_path)
    assert [tti for tti, _ in waypoints] == list(range(0, 70_000, 250))
    assert all(params["mobility.pos_y_m"] == 0.0 for _, params in waypoints)

    speed_ms = 25.0 / 3.6
    for tti, params in waypoints:
        t_s = tti / 1000.0
        within_s = t_s % BUS_CYCLE_S
        cycles = int(t_s // BUS_CYCLE_S)
        driving_s = cycles * BUS_DRIVE_PHASE_S + min(within_s, BUS_DRIVE_PHASE_S)
        assert params["mobility.pos_x_m"] == pytest.approx(
            _reflect(driving_s * speed_ms, 220.0, 650.0), abs=1e-3
        )
        expected_speed = 25.0 if within_s < BUS_DRIVE_PHASE_S else 0.0
        assert params["mobility.speed_kmh"] == expected_speed

    by_time = {tti / 1000.0: params for tti, params in waypoints}
    first_stop_x = 220.0 + 15.0 * speed_ms
    second_stop_x = 220.0 + 30.0 * speed_ms
    assert by_time[0.0]["mobility.pos_x_m"] == pytest.approx(220.0)
    assert first_stop_x == pytest.approx(324.167, abs=1e-3)
    # The bus stands still for the whole 10 s dwell window at each stop
    for t_s in [15.0 + 0.25 * k for k in range(40)]:
        assert by_time[t_s]["mobility.pos_x_m"] == pytest.approx(first_stop_x, abs=1e-3)
        assert by_time[t_s]["mobility.speed_kmh"] == 0.0
    for t_s in [40.0 + 0.25 * k for k in range(40)]:
        assert by_time[t_s]["mobility.pos_x_m"] == pytest.approx(second_stop_x, abs=1e-3)
        assert by_time[t_s]["mobility.speed_kmh"] == 0.0
    # Driving resumes right after the dwell and covers 15 s at 25 km/h
    assert by_time[25.0]["mobility.speed_kmh"] == 25.0
    assert by_time[39.75]["mobility.pos_x_m"] > first_stop_x + 100.0
    assert by_time[39.75]["mobility.pos_x_m"] < second_stop_x


def test_urban_bus_reflects_at_corridor_end_on_long_runs(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M11"})
    out = synthesize_parametric_cell(cfg, duration_s=180.0, seed=1, work_dir=tmp_path / "long")
    assert out.timeline_path is not None
    xs = [params["mobility.pos_x_m"] for _, params in _study_waypoints(out.timeline_path)]
    assert max(xs) <= 650.0 + 1e-9
    assert min(xs) >= 220.0 - 1e-9
    assert max(xs) > 640.0
    peak = xs.index(max(xs))
    assert xs[peak + 120] < max(xs) - 50.0  # moving back towards the cell centre after the turn


def test_vehicular_traverse_keeps_continuous_triangle_wave(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M10"})
    out = synthesize_parametric_cell(cfg, duration_s=65.0, seed=20260927, work_dir=tmp_path / "m10")
    assert out.timeline_path is not None
    speed_ms = 73.26 / 3.6
    d_min, d_max = cfg.traverse_min_distance_m, cfg.traverse_max_distance_m
    for tti, params in _study_waypoints(out.timeline_path):
        assert params["mobility.pos_x_m"] == pytest.approx(_reflect(tti / 1000.0 * speed_ms, d_min, d_max), abs=2e-3)
        assert params["mobility.speed_kmh"] == 73.26


def test_study_dl_rmax_defaults_to_uncapped_and_emits_no_cap() -> None:
    for preset in PARAMETRIC_CELL_PRESETS:
        assert PARAMETRIC_CELL_PRESETS[preset]["study_dl_rmax_mbps"] is None
        assert ParametricCellConfig.from_dict({"preset": preset}).study_dl_rmax_mbps is None
    assert ParametricCellConfig.from_dict({"study_dl_rmax_mbps": None}).study_dl_rmax_mbps is None


def test_study_dl_rmax_on_static_unloaded_cell_writes_timeline_and_enables_control(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M01", "study_dl_rmax_mbps": 2.5})
    assert cfg.study_mobility == "static" and cfg.load_rho == 0.0
    out = synthesize_parametric_cell(cfg, duration_s=20.0, seed=20260927, work_dir=tmp_path / "cap")
    assert out.pool_ue_count == 0
    assert out.timeline_path is not None and out.timeline_path.is_file()

    messages = [json.loads(line) for line in out.timeline_path.read_text().splitlines()]
    assert messages == [
        {"id": 1, "at_tti": 0, "cmds": [{"target": "ue/studyVqeg", "set": {"dl.rmax_mbps": 2.5}}]}
    ]

    doc = ScenarioDocument.read(str(out.ini_path))
    assert doc.get("Control", "enabled") == "true"
    assert Path(doc.get("Control", "timeline_file")) == out.timeline_path.resolve()

    # One study UE addresses `ue/studyVqeg`; several expand to `studyVqeg_<index>`
    single = load_control_timeline(out.timeline_path, study_group="studyVqeg", study_targets=["studyVqeg"])
    assert [(item.at_tti, item.target, item.params) for item in single] == [
        (0, "ue/studyVqeg", {"dl.rmax_mbps": 2.5})
    ]
    multi = load_control_timeline(
        out.timeline_path, study_group="studyVqeg", study_targets=["studyVqeg_0", "studyVqeg_1", "studyVqeg_2"]
    )
    assert [(item.at_tti, item.target, item.params) for item in multi] == [
        (0, f"ue/studyVqeg_{index}", {"dl.rmax_mbps": 2.5}) for index in range(3)
    ]


def test_uncapped_static_unloaded_cell_has_no_timeline_and_control_disabled(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M01"})
    out = synthesize_parametric_cell(cfg, duration_s=20.0, seed=20260927, work_dir=tmp_path / "plain")
    assert out.timeline_path is None
    assert ScenarioDocument.read(str(out.ini_path)).get("Control", "enabled") == "false"


def test_study_dl_rmax_is_emitted_once_at_tti_zero_next_to_mobility_and_background(tmp_path: Path) -> None:
    cfg = ParametricCellConfig.from_dict({"preset": "M11", "study_dl_rmax_mbps": 12.34567})
    out = synthesize_parametric_cell(cfg, duration_s=30.0, seed=7, work_dir=tmp_path / "bus-cap")
    assert out.timeline_path is not None
    cap_commands = []
    for line in out.timeline_path.read_text().splitlines():
        message = json.loads(line)
        for cmd in message["cmds"]:
            if "dl.rmax_mbps" in cmd["set"]:
                cap_commands.append((message["at_tti"], cmd["target"], cmd["set"]))
    assert cap_commands == [(0, "ue/studyVqeg", {"dl.rmax_mbps": 12.3457})]
    # The cap does not disturb the bus trajectory or the background sessions
    uncapped = synthesize_parametric_cell(
        ParametricCellConfig.from_dict({"preset": "M11"}), duration_s=30.0, seed=7, work_dir=tmp_path / "bus"
    )
    assert uncapped.timeline_path is not None
    assert _study_waypoints(out.timeline_path) == _study_waypoints(uncapped.timeline_path)
    assert out.session_count == uncapped.session_count
    assert out.background_iperf_ues == uncapped.background_iperf_ues


@pytest.mark.parametrize(
    "bad_cell",
    [
        {"preset": "M99"},
        {"bandwidth_mhz": 35},
        {"load_rho": -0.1},
        {"bg_bitrate_mbps": 0.0},
        {"study_mobility": "teleport"},
        {"study_mobility": "pedestrian"},
        {"study_mobility": "urban_bus", "study_speed_kmh": 0.0},
        {"study_mobility": "vehicular_traverse", "study_speed_kmh": 0.0},
        {"study_mobility": "urban_bus", "traverse_min_distance_m": 300.0, "traverse_max_distance_m": 300.5},
        {"study_mobility": "vehicular_traverse", "traverse_min_distance_m": 300.0, "traverse_max_distance_m": 300.5},
        {"study_dl_rmax_mbps": 0.0},
        {"study_dl_rmax_mbps": 0.05},
        {"study_dl_rmax_mbps": 1000.5},
        {"study_dl_rmax_mbps": -3.0},
        {"study_dl_rmax_mbps": math.nan},
        {"study_dl_rmax_mbps": math.inf},
        {"study_dl_rmax_mbps": True},
        {"study_dl_rmax_mbps": "2.5"},
        {"unknown_knob": 1},
    ],
)
def test_invalid_parametric_cell_settings_are_rejected(bad_cell: dict) -> None:
    with pytest.raises(ValueError):
        ParametricCellConfig.from_dict(bad_cell)


@pytest.mark.parametrize("cap", [0.1, 2.5, 100, 1000.0])
def test_study_dl_rmax_accepts_values_in_range(cap: float) -> None:
    assert ParametricCellConfig.from_dict({"study_dl_rmax_mbps": cap}).study_dl_rmax_mbps == float(cap)


def test_study_dl_rmax_error_message_names_the_bounds() -> None:
    with pytest.raises(ValueError, match=r"study_dl_rmax_mbps must be between 0\.1 and 1000\.0 Mbps when set"):
        ParametricCellConfig.from_dict({"study_dl_rmax_mbps": 5000.0})


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


def test_mixed_parametric_and_raw_ini_grid_overlays_resolve_cleanly(tmp_path: Path) -> None:
    """Verify grid overlay merging when mixing M04, CUSTOM parametric_cell, and raw fikore_base_ini."""
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
            "RAW_INI": {
                "condition": "RAW_INI",
                "duration_s": 30,
                "network": {
                    "receive_window_bytes": 1048576,
                    "fikore_base_ini": "5g-network-emulator/config/control_demo.ini",
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
        if cell.condition == "RAW_INI":
            assert tf_cfg.fikore_base_ini is not None
            assert tf_cfg.parametric_cell is None
        else:
            assert tf_cfg.fikore_base_ini is None
            assert tf_cfg.parametric_cell is not None

