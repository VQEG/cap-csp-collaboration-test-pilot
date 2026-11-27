"""Per-title ladder catalogues: generation from the AOM CTC encodes and use as a grid axis."""

import csv
import json
from pathlib import Path

import pytest

from capcsp.content.per_title_ladder_catalogue import (
    LadderEncode,
    PerTitleLadderCatalogueSpecification,
    generate_per_title_ladder_catalogues,
    kept_video_bytes,
    ladder_rungs,
    segment_durations_s,
    split_bytes,
)
from capcsp.runner.grid_specification import GridSpecification

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
CATALOGUE_DIRECTORY = CONFIGS / "content" / "aomctc-a2-2k-long"
SPECIFICATION_PATH = CATALOGUE_DIRECTORY / "catalogue-specification.json"


@pytest.fixture(scope="module")
def generated_catalogues() -> dict[Path, dict]:
    return generate_per_title_ladder_catalogues(SPECIFICATION_PATH)


def test_committed_catalogues_match_their_specification(generated_catalogues: dict[Path, dict]) -> None:
    assert len(generated_catalogues) == 5 * 4
    for path, catalogue in generated_catalogues.items():
        assert json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(catalogue)), path.name


def test_segment_sizes_add_up_to_the_measured_encode_sizes(generated_catalogues: dict[Path, dict]) -> None:
    """The measured size of each encode, minus the share of a dropped very short last segment."""
    specification = PerTitleLadderCatalogueSpecification.from_file(SPECIFICATION_PATH)
    with open(specification.source_csv, newline="", encoding="utf-8") as file:
        encodes = {
            (row["codec"], row["clip"], float(row["segment_duration_s"]), int(row["crf"]), int(row["height"])): (
                int(row["video_bytes"]),
                round(float(row["duration_s"]), 6),
            )
            for row in csv.DictReader(file)
            if row["status"] == "ok"
        }
    for catalogue in generated_catalogues.values():
        condition = catalogue["encodingCondition"]
        for video in catalogue["videos"]:
            for representation in video["representations"]["video"]:
                key = (
                    condition["encoder"],
                    video["sourceClip"],
                    condition["segmentDurationS"],
                    representation["crf"],
                    representation["height"],
                )
                video_bytes, source_duration_s = encodes[key]
                expected_bytes = kept_video_bytes(video_bytes, source_duration_s, video["durationS"])
                assert sum(segment["bytes"] for segment in representation["segments"]) == expected_bytes
                assert video["durationS"] > source_duration_s - specification.drop_last_segment_shorter_than_s


def test_ladders_strictly_increase_and_segments_cover_each_video(generated_catalogues: dict[Path, dict]) -> None:
    specification = PerTitleLadderCatalogueSpecification.from_file(SPECIFICATION_PATH)
    for catalogue in generated_catalogues.values():
        segment_duration_s = catalogue["encodingCondition"]["segmentDurationS"]
        assert len(catalogue["videos"]) == 17
        for video in catalogue["videos"]:
            representations = video["representations"]["video"]
            bitrates = [representation["bitrateKbps"] for representation in representations]
            assert bitrates == sorted(bitrates) and len(set(bitrates)) == len(bitrates)
            assert 3 <= len(representations) <= len(specification.vmaf_targets)
            assert {representation["targetVmaf"] for representation in representations} <= set(specification.vmaf_targets)
            for representation in [*representations, *video["representations"]["audio"]]:
                durations = [segment["durationS"] for segment in representation["segments"]]
                assert durations[:-1] == [segment_duration_s] * (len(durations) - 1)
                assert durations[-1] >= specification.drop_last_segment_shorter_than_s
                assert sum(durations) == pytest.approx(video["durationS"])


def test_encoders_of_a_clip_share_the_scene_pattern(generated_catalogues: dict[Path, dict]) -> None:
    def relative_sizes(name: str) -> list[float]:
        representation = generated_catalogues[CATALOGUE_DIRECTORY / name]["videos"][0]["representations"]["video"][0]
        sizes = [segment["bytes"] for segment in representation["segments"]]
        return [size / sum(sizes) for size in sizes]

    assert relative_sizes("x264-segment-2s.json") == pytest.approx(relative_sizes("svtav1-segment-2s.json"), abs=1e-4)


def test_an_encode_selected_for_two_targets_becomes_one_rung() -> None:
    def encode(target: int, crf: int, bitrate: float) -> LadderEncode:
        return LadderEncode(target, 854, 480, crf, 30.0, 5.0, int(bitrate * 625), bitrate, float(target))

    rungs = ladder_rungs([encode(70, 36, 266.0), encode(60, 36, 266.0), encode(50, 39, 131.0), encode(80, 33, 423.0)])
    assert [(rung.target_vmaf, rung.crf) for rung in rungs] == [(50, 39), (60, 36), (80, 33)]


def test_segments_split_the_video_and_its_bytes_exactly() -> None:
    assert segment_durations_s(9.192517, 2) == [2, 2, 2, 2, 1.192517]
    assert segment_durations_s(10.0, 2) == [2, 2, 2, 2, 2]
    # A last segment of a frame or two is dropped, a longer one is kept
    assert segment_durations_s(5.005, 5, 0.05) == [5]
    assert segment_durations_s(9.192517, 1, 0.05) == [1] * 9 + [0.192517]
    assert kept_video_bytes(1_001_000, 5.005, 5.0) == 1_000_000
    assert kept_video_bytes(1_000_000, 5.0, 5.0) == 1_000_000
    sizes = split_bytes(1_000_003, [0.2, 0.3, 0.5])
    assert sum(sizes) == 1_000_003
    # Skewed weights and small totals keep the total and give every segment a byte
    assert split_bytes(10, [0.9, 0.09, 0.01]) == [7, 2, 1]
    assert split_bytes(3, [1.0, 0.0, 0.0]) == [1, 1, 1]
    with pytest.raises(ValueError, match="at least one byte"):
        split_bytes(2, [0.5, 0.3, 0.2])


def test_the_content_axis_sets_the_catalogue_of_each_cell() -> None:
    specification = GridSpecification.from_file(CONFIGS / "grids" / "aomctc-encoding-conditions.json")
    cells = specification.cells()
    assert len(cells) == 3 * 20 * 2 * 3
    cell = next(cell for cell in cells if cell.content_catalogue == "vp9-seg4s")
    assert cell.experiment_config["content"] == str(CATALOGUE_DIRECTORY / "vp9-segment-4s.json")
    assert "-vp9-seg4s-" in cell.run_id
    # Cells that differ only in the catalogue get the same seeds
    same_users = [
        other
        for other in cells
        if (other.condition, other.behavior_mix, other.replication)
        == (cell.condition, cell.behavior_mix, cell.replication)
    ]
    assert len({json.dumps(other.experiment_config["sessions"]) for other in same_users}) == 1


def test_grids_without_the_content_axis_keep_their_run_ids() -> None:
    cells = GridSpecification.from_file(CONFIGS / "grids" / "layered-core6.json").cells()
    assert cells[0].run_id == "layered-core6-m01-l0-1ue-b1-r01"
    assert {cell.content_catalogue for cell in cells} == {"base"}
    assert cells[0].experiment_config["content"].endswith("sfv-portrait-hd-90s.json")


def test_a_missing_content_catalogue_is_rejected(tmp_path: Path) -> None:
    grid = json.loads((CONFIGS / "grids" / "aomctc-encoding-conditions.json").read_text(encoding="utf-8"))
    grid["base"]["content"] = str(CATALOGUE_DIRECTORY / "x264-segment-2s.json")
    grid["content_catalogues"] = {"missing": "does-not-exist.json"}
    grid_path = tmp_path / "grid.json"
    grid_path.write_text(json.dumps(grid), encoding="utf-8")
    with pytest.raises(ValueError, match="not found"):
        GridSpecification.from_file(grid_path)
