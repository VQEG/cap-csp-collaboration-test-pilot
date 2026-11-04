"""Scoring inputs from session records and the content file."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Smallest overlap of a played interval and a segment in seconds
MINIMUM_SEGMENT_OVERLAP_S = 1e-7


@dataclass(frozen=True)
class PlayedSegment:
    """Played part of one media segment."""

    video_id: str
    representation_id: str
    segment_index: int
    content_codec: str
    bitrate_kbps: float
    width: int
    height: int
    played_duration_s: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _intervals_in_playback_order(video_record: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(video_record.get("representation_intervals") or [], key=lambda interval: interval["start_at_s"])


def played_segments_of_video(video_record: dict[str, Any], video_content: dict[str, Any]) -> list[PlayedSegment]:
    """Split the played intervals of a video into segments, in playback order.

    The bitrate of a segment is its size in the content file divided by its duration.
    """
    representations = {str(rep["id"]): rep for rep in video_content["representations"]["video"]}
    played_segments = []
    for interval in _intervals_in_playback_order(video_record):
        representation = representations[str(interval["representation_id"])]
        for segment in representation["segments"]:
            segment_end_s = segment["startS"] + segment["durationS"]
            overlap_s = min(interval["end_position_s"], segment_end_s) - max(
                interval["start_position_s"], segment["startS"]
            )
            if overlap_s > MINIMUM_SEGMENT_OVERLAP_S:
                played_segments.append(
                    PlayedSegment(
                        video_id=video_content["videoId"],
                        representation_id=str(representation["id"]),
                        segment_index=segment["index"],
                        content_codec=representation["codec"],
                        bitrate_kbps=segment["bytes"] * 8 / segment["durationS"] / 1000,
                        width=representation["width"],
                        height=representation["height"],
                        played_duration_s=overlap_s,
                    )
                )
    return played_segments


def per_second_scores(segment_scores: list[tuple[float, float]]) -> list[float]:
    """Sample `(played duration, score)` pairs at the middle of each played second.

    The number of samples is the played duration rounded to full seconds.
    """
    played_duration_s = sum(duration_s for duration_s, _ in segment_scores)
    samples = []
    for second in range(round(played_duration_s)):
        segment_end_s = 0.0
        for duration_s, score in segment_scores:
            segment_end_s += duration_s
            if second + 0.5 <= segment_end_s:
                break
        samples.append(score)
    return samples


def _played_duration_until(intervals: list[dict[str, Any]], time_s: float) -> float:
    played_s = 0.0
    for interval in intervals:
        if interval["end_at_s"] <= time_s:
            played_s += interval["played_duration_s"]
        elif interval["start_at_s"] < time_s:
            elapsed_share = (time_s - interval["start_at_s"]) / (interval["end_at_s"] - interval["start_at_s"])
            played_s += interval["played_duration_s"] * elapsed_share
    return played_s


def stalling_events_of_video(video_record: dict[str, Any]) -> list[tuple[float, float]]:
    """Return `(played media position, duration)` of the loading delay and all stalls of a video."""
    events = []
    initial_loading_delay_s = video_record.get("initial_loading_delay_s")
    if initial_loading_delay_s:
        events.append((0.0, initial_loading_delay_s))
    intervals = _intervals_in_playback_order(video_record)
    for stall in video_record.get("stall_events") or []:
        if stall.get("duration_s"):
            events.append((_played_duration_until(intervals, stall["started_at_s"]), stall["duration_s"]))
    return events
