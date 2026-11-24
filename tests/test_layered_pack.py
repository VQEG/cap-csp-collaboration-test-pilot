"""Integrity, scheduler freedom, and configuration checks for the M01-M11 layered experiments."""

import json
from pathlib import Path

import pytest

from capcsp.network.parametric_cell import PARAMETRIC_CELL_PRESETS, synthesize_parametric_cell
from capcsp.network.transport_fikore import TransportFikoreConfig
from capcsp.scoring.p1204_1_pv import segment_video_quality_mos
from fikore_transport.emulator import EmulatorConfig
from fikore_transport.scenario import ScenarioDocument

ROOT = Path(__file__).resolve().parents[1]
FIKORE_ROOT = ROOT / "5g-network-emulator"
EXTENDED_CONTENT = ROOT / "configs" / "content" / "sfv-portrait-hd-90s.json"
LAYERED_EXPERIMENTS = ROOT / "configs" / "experiments" / "layered"


def test_layered_experiments_synthesize_free_scheduler_scenarios(tmp_path: Path) -> None:
    exp_files = sorted(LAYERED_EXPERIMENTS.glob("m*-b*.json"))
    assert len(exp_files) == 22

    seen_conditions: set[str] = set()
    for exp_file in exp_files:
        exp_cfg = json.loads(exp_file.read_text())
        cond = exp_cfg["condition"]
        seen_conditions.add(cond)
        tf_cfg = TransportFikoreConfig.from_dict(exp_cfg["network"])
        assert tf_cfg.fikore_base_ini is None
        assert tf_cfg.parametric_cell is not None
        assert tf_cfg.parametric_cell.preset == cond
        assert tf_cfg.tcp_connection_mode == "persistent", (
            f"{exp_file.name} must keep tcp_connection_mode='persistent' across B1 and B2"
        )

    assert seen_conditions == set(PARAMETRIC_CELL_PRESETS) - {"custom"}

    for cond in sorted(seen_conditions):
        cell_cfg = TransportFikoreConfig.from_dict(
            {"parametric_cell": {"preset": cond}}
        ).parametric_cell
        assert cell_cfg is not None
        synthesized = synthesize_parametric_cell(
            cell_cfg,
            duration_s=20.0,
            seed=20260927,
            work_dir=tmp_path / cond,
        )
        raw = synthesized.ini_path.read_text()
        assert "rmax_mbps" not in raw, f"{cond} must not configure scheduler caps"
        doc = ScenarioDocument.read(str(synthesized.ini_path))
        assert doc.get("MACLayer", "metric_type") == "6"
        assert doc.get("MACLayer", "harq_model") == "legacy_bler"
        assert doc.get("PDCP_RLC", "order_pkts") == "true"
        assert float(doc.get("PDCP_RLC", "backhaul_d_var")) == pytest.approx(0.001)
        map_path = (FIKORE_ROOT / doc.get("Scenario", "map_file")).resolve()
        assert map_path.is_file(), f"{cond}: {map_path}"
        if synthesized.timeline_path is not None:
            assert synthesized.timeline_path.is_file()
            assert "rmax_mbps" not in synthesized.timeline_path.read_text()


def test_background_iperf_ues_validation_and_cosim_overlay(tmp_path: Path) -> None:
    cell_cfg = TransportFikoreConfig.from_dict(
        {"parametric_cell": {"preset": "M04"}}
    ).parametric_cell
    assert cell_cfg is not None
    synthesized = synthesize_parametric_cell(
        cell_cfg, duration_s=10.0, seed=20260927, work_dir=tmp_path / "m04"
    )
    assert synthesized.background_iperf_ues == {"backgroundSfV": 4.0}

    with pytest.raises(ValueError):
        TransportFikoreConfig.from_dict(
            {"background_iperf_ues": {"backgroundSfV": 0.0}}
        )

    out_ini = tmp_path / "effective.ini"
    EmulatorConfig(
        binary="/bin/false",
        base_ini=str(synthesized.ini_path),
        socket_path=str(tmp_path / "control.sock"),
        duration_s=5.0,
        n_ues=None,
        delay_budget_s=None,
        random_v=None,
        study_ues=["studyVqeg", "backgroundSfV"],
        ue_overrides={"studyVqeg": {"n_ues": "1"}},
    ).render(str(out_ini))
    effective = ScenarioDocument.read(str(out_ini))
    assert effective.get_ue("studyVqeg", "n_ues") == "1"
    assert effective.get_ue("studyVqeg", "dl_target") == "0.0"
    assert int(effective.get_ue("backgroundSfV", "n_ues")) > 10
    assert effective.get_ue("backgroundSfV", "dl_target") == "0.0"


def test_extended_portrait_catalog_has_monotonic_p1204_ladder() -> None:
    dataset = json.loads(EXTENDED_CONTENT.read_text())
    assert len(dataset["videos"]) == 18
    reps = dataset["videos"][0]["representations"]["video"]
    scores = [
        segment_video_quality_mos(
            content_codec=rep["codec"],
            bitrate_kbps=rep["bitrateKbps"],
            width=rep["width"],
            height=rep["height"],
            frame_rate_fps=rep["frameRateFps"],
            device="mobile",
            display_width=1080,
            display_height=1920,
        )
        for rep in reps
    ]
    assert all(b > a for a, b in zip(scores, scores[1:]))
