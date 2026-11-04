"""ITU-T P.1203.3 integration of existing per-second audio and video scores."""

from __future__ import annotations

from typing import Literal

from itu_p1203 import P1203Standalone


def merge_stalling_events(stalling_events: list[tuple[float, float]], media_duration_s: int) -> list[list[float]]:
    """Return sorted `[media position, duration]` pairs in the P.1203 input format.

    - Limit positions to the scored media duration.
    - Merge events at the same position. The P.1203 random forest features fail on
      several events at position 0.
    - Start with a zero-length event at position 0 if no event is there.
      `P1203Standalone` shifts all positions otherwise.
    """
    duration_by_position: dict[float, float] = {0.0: 0.0}
    for position_s, duration_s in stalling_events:
        position_s = float(min(position_s, media_duration_s))
        duration_by_position[position_s] = duration_by_position.get(position_s, 0.0) + duration_s
    return [[position_s, duration_by_position[position_s]] for position_s in sorted(duration_by_position)]


def p1203_integration_scores(
    *,
    per_second_video_o22: list[float],
    audio_o21: float,
    stalling_events: list[tuple[float, float]],
    device: Literal["pc", "mobile"],
) -> dict[str, float] | None:
    """Return O46, O35 and O23, or `None` without any video score."""
    media_duration_s = len(per_second_video_o22)
    if media_duration_s == 0:
        return None
    input_report = {
        "O21": [audio_o21] * media_duration_s,
        "O22": per_second_video_o22,
        "I23": {"stalling": merge_stalling_events(stalling_events, media_duration_s)},
        "IGen": {"device": device},
    }
    output = P1203Standalone(input_report, quiet=True).calculate_complete()
    return {score: float(output[score]) for score in ("O46", "O35", "O23")}
