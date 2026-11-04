"""P.1203 scores per video and session for the session files of one run."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from importlib.metadata import distribution
from pathlib import Path
from typing import Any, Literal

from capcsp.scoring.p1203 import p1203_integration_scores
from capcsp.scoring.p1204_1_pv import segment_video_quality_mos
from capcsp.scoring.records import per_second_scores, played_segments_of_video, stalling_events_of_video


@dataclass(frozen=True)
class ScoringSettings:
    """Model inputs missing from the session record and the content file."""

    # P.1204.1 device class
    device: Literal["pc", "mobile"] = "mobile"
    # Display resolution for the upscaling degradation
    display_width: int = 1080
    display_height: int = 1920
    # Assumed frame rate of all representations; the manifests of the SFV fixture state 30 fps
    frame_rate_fps: float = 30.0
    # Assumed constant audio score, because the player does not request audio; 5.0 is constant good quality
    audio_o21: float = 5.0

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ScoringSettings:
        unknown = set(values) - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown scoring settings: {sorted(unknown)}")
        settings = cls(**values)
        if settings.device not in ("pc", "mobile"):
            raise ValueError("scoring.device must be 'pc' or 'mobile'")
        if settings.display_width <= 0 or settings.display_height <= 0 or settings.frame_rate_fps <= 0:
            raise ValueError("scoring display size and frame rate must be positive")
        if not 1 <= settings.audio_o21 <= 5:
            raise ValueError("scoring.audio_o21 must be between 1 and 5")
        return settings


def _model_package_version(package: str) -> dict[str, Any]:
    package_distribution = distribution(package)
    direct_url = json.loads(package_distribution.read_text("direct_url.json") or "{}")
    return {
        "package": package,
        "version": package_distribution.version,
        "commit": direct_url.get("vcs_info", {}).get("commit_id"),
    }


def _score_session_record(record: dict[str, Any], dataset: dict[str, Any], settings: ScoringSettings) -> None:
    """Add `p1204_1_segment_scores` and `p1203_output` to the videos and summary of a session record."""
    video_content_by_id = {video["videoId"]: video for video in dataset["videos"]}
    session_segment_scores: list[tuple[float, float]] = []
    session_stalling_events: list[tuple[float, float]] = []

    def first_playback_time(video: dict[str, Any]) -> float:
        intervals = video.get("representation_intervals") or []
        return min((interval["start_at_s"] for interval in intervals), default=float("inf"))

    for video in sorted(record["videos"], key=first_playback_time):
        segment_outputs = []
        segment_scores = []
        for segment in played_segments_of_video(video, video_content_by_id[video["video_id"]]):
            mos = segment_video_quality_mos(
                content_codec=segment.content_codec,
                bitrate_kbps=segment.bitrate_kbps,
                width=segment.width,
                height=segment.height,
                frame_rate_fps=settings.frame_rate_fps,
                device=settings.device,
                display_width=settings.display_width,
                display_height=settings.display_height,
            )
            segment_outputs.append({**segment.to_dict(), "video_quality_mos": mos})
            segment_scores.append((segment.played_duration_s, mos))

        stalling_events = stalling_events_of_video(video)
        session_position_s = sum(duration_s for duration_s, _ in session_segment_scores)
        session_stalling_events += [(position_s + session_position_s, length_s) for position_s, length_s in stalling_events]
        session_segment_scores += segment_scores

        video["p1204_1_segment_scores"] = segment_outputs
        video["p1203_output"] = _p1203_output(segment_scores, stalling_events, settings)

    record["session_summary"]["p1203_output"] = _p1203_output(session_segment_scores, session_stalling_events, settings)


def _p1203_output(
    segment_scores: list[tuple[float, float]],
    stalling_events: list[tuple[float, float]],
    settings: ScoringSettings,
) -> dict[str, Any] | None:
    per_second_video_o22 = per_second_scores(segment_scores)
    scores = p1203_integration_scores(
        per_second_video_o22=per_second_video_o22,
        audio_o21=settings.audio_o21,
        stalling_events=stalling_events,
        device=settings.device,
    )
    return None if scores is None else {**scores, "O22": per_second_video_o22}


def score_run(run_dir: Path, dataset: dict[str, Any], settings: ScoringSettings) -> dict[str, Any]:
    """Score all session files of a run in place and return the model description for the manifest."""
    for session_path in sorted((run_dir / "sessions").glob("ue-*.json")):
        result = json.loads(session_path.read_text(encoding="utf-8"))
        _score_session_record(result["sessionRecord"], dataset, settings)
        session_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {
        "integration_model": {"standard": "ITU-T P.1203.3", **_model_package_version("itu-p1203")},
        "video_model": {"standard": "ITU-T P.1204.1 Mode 0 (AVQBits|M0)", **_model_package_version("mode0-retraining")},
        "settings": asdict(settings),
    }
