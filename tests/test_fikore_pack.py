"""Integrity and co-simulation rendering of the contributed FikoRE pack."""

import hashlib
import json
from pathlib import Path

from fikore_transport.emulator import EmulatorConfig
from fikore_transport.scenario import ScenarioDocument

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "configs" / "fikore"
FIKORE_ROOT = ROOT / "5g-network-emulator"
CONDITIONS = {
    "c1_healthy_5g.ini",
    "c2_plan_capped.ini",
    "c3_borderline_cell.ini",
    "c4_congested_cell.ini",
    "c5_cell_edge_low_sinr.ini",
    "c6_mobility_dropout.ini",
    "c7_satellite_like.ini",
    "c8a_bursty_congestion.ini",
    "c8b_coverage_transition.ini",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_pack_manifest_and_references_are_complete() -> None:
    assert {path.name for path in PACK.glob("*.ini")} == CONDITIONS
    manifest = json.loads((PACK / "manifest.json").read_text())
    for relative, expected in manifest["assets"].items():
        path = PACK / relative
        assert path.is_file(), relative
        assert sha256(path) == expected, relative

    for ini in sorted(PACK.glob("*.ini")):
        document = ScenarioDocument.read(str(ini))
        map_path = Path(document.get("Scenario", "map_file"))
        if not map_path.is_absolute():
            map_path = (FIKORE_ROOT / map_path).resolve()
        assert map_path.is_file(), f"{ini.name}: {map_path}"
        timeline = document.get("Control", "timeline_file")
        if timeline not in (None, "", "none"):
            timeline_path = Path(timeline)
            if not timeline_path.is_absolute():
                timeline_path = (FIKORE_ROOT / timeline_path).resolve()
            assert timeline_path.is_file(), f"{ini.name}: {timeline_path}"
        assert "config/vqeg/" not in ini.read_text()


def test_c2_and_c7_use_explicit_grant_cap_adaptations() -> None:
    c2 = (PACK / "timelines" / "c2_plan_cap.ndjson").read_text()
    c7 = (PACK / "timelines" / "c7_rate_cap.ndjson").read_text()
    assert '"dl.rmax_mbps":25.0' in c2
    assert '"dl.rmax_mbps":15.0' in c7
    assert "traffic.dl_target_mbps" not in c2 + c7


def render_condition(tmp_path: Path, name: str) -> ScenarioDocument:
    source = PACK / name
    output = tmp_path / name
    EmulatorConfig(
        binary="/bin/false",
        base_ini=str(source),
        socket_path=str(tmp_path / "control.sock"),
        duration_s=2.0,
        n_ues=2,
        delay_budget_s=None,
        random_v=None,
        study_ues=["studyVqeg"],
    ).render(str(output))
    return ScenarioDocument.read(str(output))


def test_c4_render_preserves_saturated_background_group(
    tmp_path: Path,
) -> None:
    effective = render_condition(tmp_path, "c4_congested_cell.ini")
    assert effective.get_ue("studyVqeg", "n_ues") == "2"
    assert effective.get_ue("studyVqeg", "dl_target") == "0.0"
    assert effective.get_ue("studyVqeg", "pkt_delay_budget") == "0.030000"
    assert effective.get_ue("backgroundVqeg", "n_ues") == "64"
    assert effective.get_ue("backgroundVqeg", "dl_target") == "100.000000"
    assert effective.get("Control", "transport") == "unix"
    assert effective.get("Control", "sync_mode") == "barrier"


def test_c8a_render_preserves_bursty_background_group(
    tmp_path: Path,
) -> None:
    effective = render_condition(tmp_path, "c8a_bursty_congestion.ini")
    assert effective.get_ue("studyVqeg", "n_ues") == "2"
    assert effective.get_ue("backgroundVqeg", "n_ues") == "20"
    assert effective.get_ue("backgroundVqeg", "dl_target") == "0.500000"
    assert effective.get_ue("backgroundVqeg", "random_v") == "true"
