"""P.1203 scoring with P.1204.1 Mode 0 video scores."""

import json
from pathlib import Path

import pytest
from mode0_retraining.retrain_mode0 import DEFAULT_CODING_COEFFS, video_model_function_mode0

from capcsp.scoring.p1203 import merge_stalling_events, p1203_integration_scores
from capcsp.scoring.p1204_1_pv import model_codec_name, segment_video_quality_mos
from capcsp.scoring.records import per_second_scores, played_segments_of_video, stalling_events_of_video
from capcsp.scoring.session_scoring import ScoringSettings, combine_video_scores, score_run

CONTENT = Path(__file__).resolve().parents[1] / "sfv-reference-implementation" / "fixtures" / "content" / "content.json"


def interval(representation_id: str, start_at_s: float, start_position_s: float, end_position_s: float) -> dict:
    played_duration_s = end_position_s - start_position_s
    return {
        "representation_id": representation_id,
        "start_at_s": start_at_s,
        "end_at_s": start_at_s + played_duration_s,
        "start_position_s": start_position_s,
        "end_position_s": end_position_s,
        "played_duration_s": played_duration_s,
    }


@pytest.mark.parametrize(
    ("codec", "bitrate_kbps", "width", "height", "frame_rate_fps"),
    [("h264", 750, 640, 360, 59.94), ("hevc", 2000, 1280, 720, 30), ("vp9", 4000, 1920, 1080, 24), ("av1", 8000, 3840, 2160, 60)],
)
@pytest.mark.parametrize("device", ["pc", "mobile"])
def test_mode0_score_equals_reference_function_on_4k_display(
    codec: str, bitrate_kbps: float, width: int, height: int, frame_rate_fps: float, device: str
) -> None:
    coefficients = {
        f"{name}_{key}": value for name, values in DEFAULT_CODING_COEFFS[device].items() for key, value in values.items()
    }
    reference = video_model_function_mode0(
        coefficients,
        {
            "video_codec": codec,
            "video_bitrate": bitrate_kbps,
            "video_width": width,
            "video_height": height,
            "video_frame_rate": frame_rate_fps,
        },
        device,
    )
    assert segment_video_quality_mos(
        content_codec=codec,
        bitrate_kbps=bitrate_kbps,
        width=width,
        height=height,
        frame_rate_fps=frame_rate_fps,
        device=device,
        display_width=3840,
        display_height=2160,
    ) == pytest.approx(reference)


def test_codec_names() -> None:
    assert model_codec_name("avc1") == "h264"
    assert model_codec_name("avc1.64001f") == "h264"
    assert model_codec_name("hvc1.1.6.L93.B0") == "hevc"
    assert model_codec_name("av01.0.04M.08") == "av1"
    with pytest.raises(ValueError, match="does not support"):
        model_codec_name("mp4a.40.2")


def test_intervals_split_into_segments_with_their_own_bitrate() -> None:
    content = json.loads(CONTENT.read_text())["videos"][0]
    video = {"representation_intervals": [interval("2", 7.0, 3.0, 6.0), interval("0", 1.0, 0.5, 3.0)]}
    segments = played_segments_of_video(video, content)
    assert [(s.representation_id, s.segment_index) for s in segments] == [("0", 0), ("0", 1), ("2", 1), ("2", 2)]
    assert [s.played_duration_s for s in segments] == [1.5, 1.0, 1.0, 2.0]
    assert segments[0].bitrate_kbps == pytest.approx(52129 * 8 / 2 / 1000)
    assert (segments[0].width, segments[0].height, segments[0].content_codec) == (180, 320, "avc1")
    assert segments[0].frame_rate_fps == 30


def test_segments_without_frame_rate_in_content_have_none() -> None:
    content = json.loads(CONTENT.read_text())["videos"][0]
    for representation in content["representations"]["video"]:
        del representation["frameRateFps"]
    segments = played_segments_of_video({"representation_intervals": [interval("0", 1.0, 0.0, 1.0)]}, content)
    assert segments[0].frame_rate_fps is None


def test_non_positive_frame_rate_in_content_is_rejected() -> None:
    content = json.loads(CONTENT.read_text())["videos"][0]
    content["representations"]["video"][0]["frameRateFps"] = 0
    with pytest.raises(ValueError, match="frameRateFps"):
        played_segments_of_video({"representation_intervals": [interval("0", 1.0, 0.0, 1.0)]}, content)


def test_per_second_scores_round_the_played_duration() -> None:
    assert per_second_scores([]) == []
    assert per_second_scores([(0.4, 2.0)]) == []
    assert per_second_scores([(0.6, 2.0)]) == [2.0]
    assert per_second_scores([(1.2, 2.0), (1.0, 3.0), (3.75, 4.0)]) == [2.0, 3.0, 4.0, 4.0, 4.0, 4.0]


def test_stalls_use_the_played_media_position() -> None:
    video = {
        "initial_loading_delay_s": 0.3,
        "representation_intervals": [interval("0", 1.0, 0.0, 4.0), interval("2", 8.0, 4.0, 6.0)],
        "stall_events": [
            {"started_at_s": 5.0, "duration_s": 3.0},
            {"started_at_s": 9.0, "duration_s": 0.5},
            {"started_at_s": 9.5, "duration_s": None},
        ],
    }
    assert stalling_events_of_video(video) == [(0.0, 0.3), (4.0, 3.0), (5.0, 0.5)]


def test_stalling_events_merge_and_start_at_zero() -> None:
    assert merge_stalling_events([], 6) == [[0.0, 0.0]]
    assert merge_stalling_events([(9.0, 1.0), (2.0, 0.5)], 6) == [[0.0, 0.0], [2.0, 0.5], [6.0, 1.0]]
    assert merge_stalling_events([(0.0, 0.3), (0.0, 0.2)], 6) == [[0.0, 0.5]]


def test_p1203_scores_fall_with_stalling() -> None:
    def scores(stalling_events: list[tuple[float, float]]) -> dict[str, float]:
        result = p1203_integration_scores(
            per_second_video_o22=[3.5] * 60, audio_o21=5.0, stalling_events=stalling_events, device="mobile"
        )
        assert result is not None
        return result

    no_stalling = scores([])
    assert no_stalling["O23"] == pytest.approx(5.0)
    assert 1 <= no_stalling["O46"] <= 5
    stalling = scores([(0.0, 0.5), (10.0, 5.0), (30.0, 5.0)])
    assert stalling["O46"] < no_stalling["O46"]
    assert stalling["O23"] < no_stalling["O23"]
    assert stalling["O35"] == pytest.approx(no_stalling["O35"])


def test_p1203_accepts_one_second_with_two_events_at_the_start() -> None:
    result = p1203_integration_scores(
        per_second_video_o22=[3.0], audio_o21=5.0, stalling_events=[(0.0, 0.2), (0.0, 0.3)], device="pc"
    )
    assert result is not None


def test_p1203_without_video_scores_returns_none() -> None:
    assert p1203_integration_scores(per_second_video_o22=[], audio_o21=5.0, stalling_events=[], device="pc") is None


@pytest.mark.parametrize(
    "values",
    [{"device": "tv"}, {"unknown": 1}, {"audio_o21": 0}, {"fallback_frame_rate_fps": 0}, {"display_width": -1}],
)
def test_invalid_settings(values: dict) -> None:
    with pytest.raises(ValueError):
        ScoringSettings.from_dict(values)


def test_combine_video_scores_weights_by_played_duration() -> None:
    assert combine_video_scores([]) is None
    combined = combine_video_scores(
        [(1.0, {"O46": 2.0, "O35": 3.0, "O23": 5.0}), (3.0, {"O46": 4.0, "O35": 3.0, "O23": 1.0})]
    )
    assert combined == {"O46": 3.5, "O35": 3.0, "O23": 2.0}


def test_score_run_adds_scores_to_session_record(tmp_path: Path) -> None:
    dataset = json.loads(CONTENT.read_text())
    (tmp_path / "sessions").mkdir()
    session_path = tmp_path / "sessions" / "ue-0.json"
    videos = [
        {"video_id": "v1", "representation_intervals": [], "stall_events": []},
        {
            "video_id": "v2",
            "initial_loading_delay_s": 0.3,
            "representation_intervals": [interval("0", 1.0, 0.0, 4.0)],
            "stall_events": [{"started_at_s": 5.0, "duration_s": 2.0}],
        },
        {"video_id": "v3", "initial_loading_delay_s": 0.2, "representation_intervals": [interval("2", 8.0, 0.0, 6.0)]},
    ]
    session_path.write_text(json.dumps({"sessionRecord": {"videos": videos, "session_summary": {}}}))

    scoring = score_run(tmp_path, dataset, ScoringSettings())

    record = json.loads(session_path.read_text())["sessionRecord"]
    first, second, third = record["videos"]
    assert first["p1203_output"] is None
    assert first["p1204_1_segment_scores"] == []
    assert len(second["p1203_output"]["O22"]) == 4
    assert second["p1203_output"]["O23"] < third["p1203_output"]["O23"]
    assert third["p1204_1_segment_scores"][0]["video_quality_mos"] > second["p1204_1_segment_scores"][0]["video_quality_mos"]
    session = record["session_summary"]["p1203_output"]
    for score in ("O46", "O35", "O23"):
        expected = (4 * second["p1203_output"][score] + 6 * third["p1203_output"][score]) / 10
        assert session[score] == pytest.approx(expected)
    assert "O22" not in session
    assert scoring["integration_model"]["version"] == "1.11.0"
    assert scoring["video_model"]["commit"]
    assert scoring["settings"]["device"] == "mobile"


def test_score_run_uses_the_frame_rate_of_the_content_file(tmp_path: Path) -> None:
    dataset = json.loads(CONTENT.read_text())
    representations = dataset["videos"][1]["representations"]["video"]
    representations[0]["frameRateFps"] = 15
    del representations[2]["frameRateFps"]
    (tmp_path / "sessions").mkdir()
    session_path = tmp_path / "sessions" / "ue-0.json"
    videos = [
        {"video_id": "v2", "representation_intervals": [interval("0", 1.0, 0.0, 2.0), interval("2", 3.0, 2.0, 4.0)]},
    ]
    session_path.write_text(json.dumps({"sessionRecord": {"videos": videos, "session_summary": {}}}))

    score_run(tmp_path, dataset, ScoringSettings(fallback_frame_rate_fps=24.0))

    segment_scores = json.loads(session_path.read_text())["sessionRecord"]["videos"][0]["p1204_1_segment_scores"]
    low, high = segment_scores[0], segment_scores[-1]
    assert (low["frame_rate_fps"], low["frame_rate_from_content"]) == (15, True)
    assert (high["frame_rate_fps"], high["frame_rate_from_content"]) == (24.0, False)
    at_content_frame_rate = segment_video_quality_mos(
        content_codec=low["content_codec"],
        bitrate_kbps=low["bitrate_kbps"],
        width=low["width"],
        height=low["height"],
        frame_rate_fps=15,
        device="mobile",
        display_width=1080,
        display_height=1920,
    )
    assert low["video_quality_mos"] == pytest.approx(at_content_frame_rate)
