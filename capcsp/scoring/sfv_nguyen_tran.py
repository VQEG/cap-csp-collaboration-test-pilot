"""Swipe-delay QoE model for short-form video (SFV) sessions.

Implements Eq. 1 and the coefficients of Table IV of Nguyen and Tran (arXiv:2603.18575), following the prototype
script of Sara Baldoni. The model scores a session from the delays between swipes and the start of the next video:

    MOS = alpha + beta * B + gamma * N_d,    B = sum_i d_i * exp(lambda * t_i / T)

- `d_i` is the swipe-to-playback delay of the swipe from video `i` to video `i + 1` (0 after the last video)
- `t_i` is the cumulative watch time up to and including video `i`, and `T` is the total watch time
- `N_d` is the number of swipes with a non-zero delay

The paper counts swipes that interrupt a video. The SFV player also sets `swiped_away` when the user swipes after
a video played in full. `sfv_nguyen_tran_scores` therefore returns two scores:

- `mos` only counts swipes in the middle of a video
- `raw_mos` counts every swipe delay, exactly as the prototype script does
"""

from __future__ import annotations

import math
from typing import Any

ALPHA = 4.52
BETA = -0.10
GAMMA = -0.23
LAMBDA = 0.55

MIN_MOS = 1.0
MAX_MOS = 5.0

# A video counts as played in full if the watch duration is within this many seconds of the video duration
FULL_PLAY_TOLERANCE_S = 1e-3

REFERENCE = "Nguyen & Tran (arXiv:2603.18575)"

COEFFICIENTS = {"alpha": ALPHA, "beta": BETA, "gamma": GAMMA, "lambda": LAMBDA}


def is_mid_video_swipe(video: dict[str, Any]) -> bool:
    """Return True if the user swiped away before the video finished playing.

    A swipe after a full playback has `swiped_away` set as well, but is not a mid-video swipe. If the video
    duration is unknown, a swipe counts as mid-video.
    """
    if not video.get("swiped_away"):
        return False
    duration_s = video.get("video_duration_s")
    watch_duration_s = float(video.get("watch_duration_s") or 0.0)
    return duration_s is None or watch_duration_s < float(duration_s) - FULL_PLAY_TOLERANCE_S


def _weighted_delay_sum_s(delays_s: list[float], watch_durations_s: list[float]) -> float:
    """Return `B`, the sum of the delays weighted by `exp(lambda * t_i / T)`."""
    total_s = sum(watch_durations_s)
    if total_s <= 0:
        return 0.0
    cumulative_s = 0.0
    weighted_sum_s = 0.0
    for delay_s, watch_duration_s in zip(delays_s, watch_durations_s):
        cumulative_s += watch_duration_s
        weighted_sum_s += delay_s * math.exp(LAMBDA * cumulative_s / total_s)
    return weighted_sum_s


def _clamp(mos: float) -> float:
    return min(MAX_MOS, max(MIN_MOS, mos))


def sfv_nguyen_tran_scores(videos: list[dict[str, Any]]) -> dict[str, float | int] | None:
    """Return the Nguyen and Tran scores of a session, or None if it has no videos.

    `videos` is `sessionRecord["videos"]` in playback order. The delay after video `i` is the
    `swipe_to_playback_delay_s` of video `i + 1`; null delays count as 0.

    Result keys:

    - `mos`: score that only counts delays after mid-video swipes, clamped to [1, 5]
    - `raw_mos`, `raw_unclamped_mos`: score that counts all swipe delays, with and without clamping
    - `mid_video_swipes`: videos that the user swiped away before their end
    - `delayed_mid_video_swipes`: mid-video swipes followed by a non-zero delay
    - `weighted_swipe_delay_s`: `B` of the mid-video-filtered score
    """
    video_count = len(videos)
    if video_count == 0:
        return None

    watch_durations_s = [float(video.get("watch_duration_s") or 0.0) for video in videos]
    raw_delays_s = [
        float(videos[index + 1].get("swipe_to_playback_delay_s") or 0.0) if index + 1 < video_count else 0.0
        for index in range(video_count)
    ]
    mid_video = [is_mid_video_swipe(video) for video in videos]
    # The last video has no following swipe delay, so only transitions 0 .. N - 2 can contribute
    mid_video_delays_s = [
        raw_delays_s[index] if index < video_count - 1 and mid_video[index] else 0.0 for index in range(video_count)
    ]

    weighted_delay_sum_s = _weighted_delay_sum_s(mid_video_delays_s, watch_durations_s)
    delayed_mid_video_swipes = sum(1 for delay_s in mid_video_delays_s if delay_s > 0.0)
    mos = _clamp(ALPHA + BETA * weighted_delay_sum_s + GAMMA * delayed_mid_video_swipes)

    raw_weighted_delay_sum_s = _weighted_delay_sum_s(raw_delays_s, watch_durations_s)
    raw_delayed_swipes = sum(1 for delay_s in raw_delays_s if delay_s != 0)
    raw_unclamped_mos = ALPHA + BETA * raw_weighted_delay_sum_s + GAMMA * raw_delayed_swipes

    return {
        "mos": round(mos, 6),
        "raw_mos": round(_clamp(raw_unclamped_mos), 6),
        "raw_unclamped_mos": round(raw_unclamped_mos, 6),
        "mid_video_swipes": sum(mid_video),
        "delayed_mid_video_swipes": delayed_mid_video_swipes,
        "weighted_swipe_delay_s": round(weighted_delay_sum_s, 6),
    }
