"""Integrity, scheduler freedom, and configuration checks for the layered FikoRE pack."""

import hashlib
import json
from pathlib import Path

import pytest

from capcsp.network.transport_fikore import TransportFikoreConfig
from capcsp.scoring.p1204_1_pv import segment_video_quality_mos
from fikore_transport.emulator import EmulatorConfig
from fikore_transport.scenario import ScenarioDocument

ROOT = Path(__file__).resolve().parents[1]
LAYERED_PACK = ROOT / "configs" / "fikore" / "layered"
FIKORE_ROOT = ROOT / "5g-network-emulator"
EXTENDED_CONTENT = ROOT / "configs" / "content" / "sfv-portrait-hd-90s.json"
LAYERED_EXPERIMENTS = ROOT / "configs" / "experiments" / "layered"

EXPECTED_INIS = {
    "m01_l1_base_good_static.ini",
    "m02_l2_homo_rho050_med.ini",
    "m03_l2_homo_rho075_med.ini",
    "m04_l2_homo_rho100_med.ini",
    "m05_l2_homo_rho100_high.ini",
    "m06_l3_good_het_rho100_med.ini",
    "m07_l3_mid_het_rho100_med.ini",
    "m08_l3_edge_het_rho050_med.ini",
    "m09_l3_edge_het_rho075_med.ini",
    "m10_l4_veh_traverse_het_rho050.ini",
    "m11_l4_ped_edge_het_rho050.ini",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_layered_pack_manifest_and_free_scheduler_invariants() -> None:
    assert {p.name for p in LAYERED_PACK.glob("*.ini")} == EXPECTED_INIS
    manifest = json.loads((LAYERED_PACK / "manifest.json").read_text())
    for relative, expected in manifest["assets"].items():
        path = LAYERED_PACK / relative
        assert path.is_file(), relative
        assert _sha256(path) == expected, relative

    for ini in sorted(LAYERED_PACK.glob("*.ini")):
        raw = ini.read_text()
        assert "rmax_mbps" not in raw, f"{ini.name} must not configure scheduler caps"
        doc = ScenarioDocument.read(str(ini))
        assert doc.get("MACLayer", "metric_type") == "6"
        assert doc.get("MACLayer", "harq_model") == "legacy_bler"
        assert doc.get("PDCP_RLC", "order_pkts") == "true"
        assert float(doc.get("PDCP_RLC", "backhaul_d_var")) == pytest.approx(0.001)
        map_path = (FIKORE_ROOT / doc.get("Scenario", "map_file")).resolve()
        assert map_path.is_file(), f"{ini.name}: {map_path}"
        timeline = doc.get("Control", "timeline_file")
        if timeline not in (None, "", "none"):
            tl_path = (FIKORE_ROOT / timeline).resolve()
            assert tl_path.is_file(), f"{ini.name}: {tl_path}"
            assert "rmax_mbps" not in tl_path.read_text()


def test_background_iperf_ues_validation_and_cosim_overlay(tmp_path: Path) -> None:
    cfg = TransportFikoreConfig.from_dict(
        {
            "fikore_base_ini": "configs/fikore/layered/m04_l2_homo_rho100_med.ini",
            "study_ues": ["studyVqeg"],
            "background_iperf_ues": {"backgroundSfV": 4.0},
            "ack_over_link": True,
            "delay_budget_s": None,
            "random_v": None,
        }
    )
    assert cfg.background_iperf_ues == {"backgroundSfV": 4.0}

    with pytest.raises(ValueError):
        TransportFikoreConfig.from_dict(
            {"background_iperf_ues": {"backgroundSfV": 0.0}}
        )

    out_ini = tmp_path / "effective.ini"
    EmulatorConfig(
        binary="/bin/false",
        base_ini=cfg.fikore_base_ini,
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
    exp_files = sorted(LAYERED_EXPERIMENTS.glob("m*-b*.json"))
    assert len(exp_files) == 22
    for exp_file in exp_files:
        exp_cfg = json.loads(exp_file.read_text())
        assert exp_cfg["network"]["tcp_connection_mode"] == "persistent", (
            f"{exp_file.name} must keep tcp_connection_mode='persistent' across B1 and B2"
        )
