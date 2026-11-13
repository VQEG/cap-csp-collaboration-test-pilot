"""P.1203 scores per video and their combination per session for the session files of one run."""

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
    # Display resolution for the upscaling degradation (portrait full HD)
    display_width: int = 1080
    display_height: int = 1920
    # Frame rate of representations without `frameRateFps` in the content file
    fallback_frame_rate_fps: float = 30.0
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
        if settings.display_width <= 0 or settings.display_height <= 0 or settings.fallback_frame_rate_fps <= 0:
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
    scored_videos: list[tuple[float, dict[str, Any]]] = []

    for video in record["videos"]:
        segment_outputs = []
        segment_scores = []
        for segment in played_segments_of_video(video, video_content_by_id[video["video_id"]]):
            frame_rate_fps = segment.frame_rate_fps or settings.fallback_frame_rate_fps
            mos = segment_video_quality_mos(
                content_codec=segment.content_codec,
                bitrate_kbps=segment.bitrate_kbps,
                width=segment.width,
                height=segment.height,
                frame_rate_fps=frame_rate_fps,
                device=settings.device,
                display_width=settings.display_width,
                display_height=settings.display_height,
            )
            segment_outputs.append(
                {
                    **segment.to_dict(),
                    "frame_rate_fps": frame_rate_fps,
                    "frame_rate_from_content": segment.frame_rate_fps is not None,
                    "video_quality_mos": mos,
                }
            )
            segment_scores.append((segment.played_duration_s, mos))

        per_second_video_o22 = per_second_scores(segment_scores)
        scores = p1203_integration_scores(
            per_second_video_o22=per_second_video_o22,
            audio_o21=settings.audio_o21,
            stalling_events=stalling_events_of_video(video),
            device=settings.device,
        )
        video["p1204_1_segment_scores"] = segment_outputs
        video["p1203_output"] = None if scores is None else {**scores, "O22": per_second_video_o22}
        if scores is not None:
            scored_videos.append((sum(duration_s for duration_s, _ in segment_scores), scores))

    record["session_summary"]["p1203_output"] = combine_video_scores(scored_videos)


def combine_video_scores(scored_videos: list[tuple[float, dict[str, Any]]]) -> dict[str, float] | None:
    """Return the means of O46, O35 and O23 over `(played duration, scores)` of the videos, weighted by duration."""
    if not scored_videos:
        return None
    total_played_duration_s = sum(duration_s for duration_s, _ in scored_videos)
    return {
        score: sum(duration_s * scores[score] for duration_s, scores in scored_videos) / total_played_duration_s
        for score in ("O46", "O35", "O23")
    }


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
