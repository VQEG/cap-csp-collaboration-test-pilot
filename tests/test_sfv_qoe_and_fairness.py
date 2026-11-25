"""Swipe-delay QoE model of Nguyen and Tran, per-UE SFV KPIs and cell fairness."""

import json
import math
from pathlib import Path
from typing import Any

import pytest

from capcsp.runner.kpis import collect_cell_fairness, collect_kpis, hossfeld_fairness, jain_fairness
from capcsp.scoring.sfv_nguyen_tran import (
    ALPHA,
    BETA,
    GAMMA,
    LAMBDA,
    is_mid_video_swipe,
    sfv_nguyen_tran_scores,
)


def sara_qoe_model(d: list[float], tau: list[float]) -> float:
    """Copy of `qoe_model` of the prototype script of Sara Baldoni, with `math` instead of numpy."""
    d = d[1:]
    d.append(0)
    n_d = sum(1 for delay in d if delay != 0)
    total = sum(tau)
    b = 0.0
    for i in range(len(tau)):
        b += d[i] * math.e ** (0.55 * sum(tau[: i + 1]) / total)
    return 4.52 - 0.10 * b - 0.23 * n_d


def video(
    watch_s: float,
    delay_s: float | None = None,
    *,
    duration_s: float | None = 6.0,
    swiped: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "watch_duration_s": watch_s,
        "video_duration_s": duration_s,
        "swiped_away": swiped,
        "swipe_to_playback_delay_s": delay_s,
        **extra,
    }


def test_coefficients_match_table_iv() -> None:
    assert (ALPHA, BETA, GAMMA, LAMBDA) == (4.52, -0.10, -0.23, 0.55)


def test_empty_session_has_no_score() -> None:
    assert sfv_nguyen_tran_scores([]) is None


@pytest.mark.parametrize(
    ("delays", "watch_s"),
    [
        ([None, 5.01, 1.13], [6.0, 6.0, 6.0]),
        ([None, 0.4, 0.0, 2.5], [6.0, 3.0, 1.0, 4.0]),
        ([None, None, None], [6.0, 2.0, 1.0]),
        ([None, 0.2], [1.0, 9.0]),
    ],
)
def test_raw_score_matches_the_prototype_script(delays: list[float | None], watch_s: list[float]) -> None:
    videos = [video(w, d, duration_s=w) for w, d in zip(watch_s, delays)]
    scores = sfv_nguyen_tran_scores(videos)
    expected = sara_qoe_model([d or 0 for d in delays], watch_s)
    assert scores is not None
    assert scores["raw_unclamped_mos"] == pytest.approx(expected, abs=1e-6)
    assert scores["raw_mos"] == pytest.approx(min(5.0, max(1.0, expected)), abs=1e-6)


def test_raw_score_of_the_example_delay_vector() -> None:
    videos = [video(6.0, None, duration_s=6.0), video(6.0, 5.01, duration_s=6.0), video(6.0, 1.13, duration_s=6.0)]
    scores = sfv_nguyen_tran_scores(videos)
    assert scores is not None
    assert scores["raw_unclamped_mos"] == pytest.approx(3.295142, abs=1e-6)


def test_swipes_after_a_full_playback_are_not_mid_video_swipes() -> None:
    assert not is_mid_video_swipe(video(6.0))
    assert not is_mid_video_swipe(video(6.0 - 5e-4))
    assert is_mid_video_swipe(video(5.0))
    assert is_mid_video_swipe(video(5.0, duration_s=None))
    assert not is_mid_video_swipe(video(2.0, swiped=False))


def test_filtered_score_ignores_delays_after_full_playbacks() -> None:
    videos = [video(6.0, None), video(6.0, 5.01), video(6.0, 1.13)]
    scores = sfv_nguyen_tran_scores(videos)
    assert scores is not None
    assert scores["mid_video_swipes"] == 0
    assert scores["delayed_mid_video_swipes"] == 0
    assert scores["weighted_swipe_delay_s"] == 0.0
    assert scores["mos"] == ALPHA
    # The unfiltered reference still penalizes both delays
    assert scores["raw_mos"] < scores["mos"]


def test_filtered_score_penalizes_mid_video_swipes() -> None:
    videos = [video(3.0, None), video(6.0, 2.0), video(2.0, 1.0)]
    scores = sfv_nguyen_tran_scores(videos)
    assert scores is not None
    # Only the swipe after video 0 (3 s of 6 s) leads to the delay of video 1; the swipe after video 1 is complete
    total_s = 11.0
    weighted = 2.0 * math.exp(LAMBDA * 3.0 / total_s)
    assert scores["mid_video_swipes"] == 2
    assert scores["delayed_mid_video_swipes"] == 1
    assert scores["weighted_swipe_delay_s"] == pytest.approx(weighted, abs=1e-6)
    assert scores["mos"] == pytest.approx(ALPHA + BETA * weighted + GAMMA, abs=1e-6)


def test_the_last_swipe_has_no_delay_and_the_score_is_clamped() -> None:
    scores = sfv_nguyen_tran_scores([video(1.0, None), video(1.0, 60.0), video(1.0, 60.0)])
    assert scores is not None
    assert scores["mos"] == 1.0
    assert scores["raw_mos"] == 1.0
    assert scores["raw_unclamped_mos"] < 1.0
    # The swipes after videos 0 and 1 lead to the two delays; video 2 has no following swipe
    assert scores["delayed_mid_video_swipes"] == 2


def test_zero_total_watch_time_has_no_weighted_delay() -> None:
    scores = sfv_nguyen_tran_scores([video(0.0, None), video(0.0, 1.0)])
    assert scores is not None
    assert scores["weighted_swipe_delay_s"] == 0.0
    # The delayed swipe still counts in the penalty term
    assert scores["mos"] == pytest.approx(ALPHA + GAMMA)


def test_hossfeld_fairness() -> None:
    assert hossfeld_fairness([]) is None
    assert hossfeld_fairness([3.2]) == 1.0
    assert hossfeld_fairness([4.0, 4.0]) == 1.0
    assert hossfeld_fairness([1.0, 5.0]) == pytest.approx(0.0)
    assert hossfeld_fairness([3.0, 5.0]) == pytest.approx(0.5)


def test_jain_fairness() -> None:
    assert jain_fairness([]) is None
    assert jain_fairness([0.0, 0.0]) is None
    assert jain_fairness([7.0]) == 1.0
    assert jain_fairness([5.0, 5.0, 5.0]) == pytest.approx(1.0)
    assert jain_fairness([10.0, 0.0]) == pytest.approx(0.5)


def test_collect_cell_fairness() -> None:
    rows = [
        {"p1203_o46": 4.0, "sfv_nt_mos": 4.5, "goodput_mbps": 10.0, "throughput_mbps": 8.0},
        {"p1203_o46": 4.0, "sfv_nt_mos": None, "goodput_mbps": 0.0, "throughput_mbps": None},
    ]
    fairness = collect_cell_fairness(rows)
    assert fairness == {
        "hossfeld_p1203_o46": 1.0,
        "hossfeld_sfv_nt_mos": 1.0,
        "jain_goodput_mbps": 0.5,
        "jain_throughput_mbps": 1.0,
        "ue_count": 2,
    }
    empty = collect_cell_fairness([])
    assert empty["ue_count"] == 0
    assert all(value is None for key, value in empty.items() if key != "ue_count")


def write_run(tmp_path: Path, videos: list[dict[str, Any]], summary: dict[str, Any]) -> Path:
    output = tmp_path / "out"
    (output / "sessions").mkdir(parents=True)
    (output / "run-manifest.json").write_text(
        json.dumps(
            {
                "run_id": "sfv-kpis",
                "network_backend": "mock",
                "ue_ids": [0],
                "sim_time_s": 10.0,
                "config": {"duration_s": 10.0},
            }
        )
    )
    (output / "sessions" / "ue-0.json").write_text(
        json.dumps(
            {
                "terminationReason": "completed",
                "requests": [],
                "sessionRecord": {
                    "network_backend": "mock",
                    "player_behavior": "simple",
                    "videos": videos,
                    "session_summary": summary,
                },
            }
        )
    )
    return output


def test_collect_kpis_adds_the_sfv_columns(tmp_path: Path) -> None:
    videos = [
        video(
            6.0,
            None,
            time_to_first_byte_s=0.1,
            representation_intervals=[
                {"bitrate_kbps": 1000.0, "played_duration_s": 2.0},
                {"bitrate_kbps": 4000.0, "played_duration_s": 4.0},
            ],
            data_wastage_by_reason={"swipe": 0},
        ),
        video(
            1.0,
            0.5,
            time_to_first_byte_s=0.3,
            representation_intervals=[{"bitrate_kbps": 500.0, "played_duration_s": 1.0}],
            data_wastage_by_reason={"swipe": 250},
        ),
        video(0.0, 0.2, time_to_first_byte_s=None, data_wastage_by_reason={"swipe": 150}),
    ]
    summary = {
        "bytes_delivered": 2000,
        "bytes_media_delivered": 1900,
        "sfv_nguyen_tran_output": sfv_nguyen_tran_scores(videos),
    }
    row = collect_kpis(write_run(tmp_path, videos, summary))[0]
    assert row["mid_video_swipes"] == 2
    assert row["time_to_first_byte_mean_s"] == pytest.approx(0.2)
    # (1000 * 2 + 4000 * 4 + 500 * 1) / 7 = 2642.857...
    assert row["played_bitrate_mean_kbps"] == 2642.9
    assert row["bytes_media_delivered"] == 1900
    assert row["bytes_wasted_swipe"] == 400
    assert row["prefetch_efficiency"] == pytest.approx(0.8)
    assert row["sfv_nt_mos"] == pytest.approx(summary["sfv_nguyen_tran_output"]["mos"], abs=1e-3)


def test_collect_kpis_without_bytes_or_playback(tmp_path: Path) -> None:
    row = collect_kpis(write_run(tmp_path, [video(0.0)], {"bytes_delivered": 0}))[0]
    assert row["prefetch_efficiency"] is None
    assert row["played_bitrate_mean_kbps"] is None
    assert row["time_to_first_byte_mean_s"] is None
    assert row["sfv_nt_mos"] is None
