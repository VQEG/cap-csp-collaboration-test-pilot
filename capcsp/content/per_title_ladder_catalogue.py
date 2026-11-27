"""Content catalogues in the SFV `content.json` format, built from real per-title encoding ladders.

The source is a CSV with one row per selected ladder encode: for each clip, encoder, segment duration and
VMAF target, the encode on the clip's convex hull that reaches the target (see
`configs/content/aomctc-a2-2k-long/README.md`). One catalogue is written per encoder and segment duration, so
an experiment grid can vary the encoding condition like any other axis.

The encodes give the total size of each representation, but not the size of each segment. Segment sizes
therefore spread the measured total over the segments with a seeded scene factor per segment. The scene
factors depend on the clip and the segment duration only, so all encoders see the same scene pattern, and the
segment sizes of a representation always add up to the measured encode size.
"""

from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Rough size of a DASH manifest: fixed part plus one part per representation
MANIFEST_BASE_BYTES = 900
MANIFEST_BYTES_PER_REPRESENTATION = 450
# Size of an fMP4 init segment, as in the SFV fixture
VIDEO_INIT_SEGMENT_BYTES = 830
AUDIO_INIT_SEGMENT_BYTES = 760


@dataclass(frozen=True)
class CatalogueClip:
    video_id: str
    source_clip: str


@dataclass(frozen=True)
class PerTitleLadderCatalogueSpecification:
    # CSV of selected ladder encodes, relative to the specification file
    source_csv: Path
    # Which VMAF model chose the ladder rungs, for example "vmaf_5h"
    quality_metric: str
    # VMAF targets that become ladder rungs; rows of other targets in the source CSV are ignored
    vmaf_targets: list[int]
    seed: int
    # Spread of segment sizes within a representation; the same scene factor applies to all representations
    segment_size_coefficient_of_variation: float
    # A last segment shorter than this (a frame or two past the last full segment) is cut off with its share of
    # the bytes, so the video ends with a full segment
    drop_last_segment_shorter_than_s: float
    # RFC 6381 codec string per encoder name in the source CSV
    codec_string_by_encoder: dict[str, str]
    segment_durations_s: list[float]
    audio_codec: str
    audio_bitrate_kbps: float
    # File name per catalogue, with the fields {encoder} and {segment_duration_s}
    output_file_pattern: str
    # Feed order
    clips: list[CatalogueClip]

    @classmethod
    def from_file(cls, path: Path) -> PerTitleLadderCatalogueSpecification:
        values = json.loads(path.read_text(encoding="utf-8"))
        specification = cls(
            source_csv=(path.parent / values["source_csv"]).resolve(),
            quality_metric=str(values["quality_metric"]),
            vmaf_targets=[int(target) for target in values["vmaf_targets"]],
            seed=int(values["seed"]),
            segment_size_coefficient_of_variation=float(values["segment_size_coefficient_of_variation"]),
            drop_last_segment_shorter_than_s=float(values["drop_last_segment_shorter_than_s"]),
            codec_string_by_encoder={str(name): str(codec) for name, codec in values["codec_string_by_encoder"].items()},
            segment_durations_s=[float(duration) for duration in values["segment_durations_s"]],
            audio_codec=str(values["audio_codec"]),
            audio_bitrate_kbps=float(values["audio_bitrate_kbps"]),
            output_file_pattern=str(values["output_file_pattern"]),
            clips=[CatalogueClip(**clip) for clip in values["clips"]],
        )
        specification.validate()
        return specification

    def validate(self) -> None:
        if self.segment_size_coefficient_of_variation < 0:
            raise ValueError("The coefficient of variation must not be negative")
        if not self.vmaf_targets:
            raise ValueError("The specification needs at least one VMAF target")
        if any(self.drop_last_segment_shorter_than_s >= duration for duration in self.segment_durations_s):
            raise ValueError("Only last segments shorter than every segment duration can be dropped")
        if not self.codec_string_by_encoder or not self.segment_durations_s or not self.clips:
            raise ValueError("The specification needs at least one encoder, segment duration and clip")
        if any(duration <= 0 for duration in self.segment_durations_s):
            raise ValueError("Segment durations must be positive")
        video_ids = [clip.video_id for clip in self.clips]
        if len(set(video_ids)) != len(video_ids):
            raise ValueError("Video IDs must be unique")

    def output_file_name(self, encoder: str, segment_duration_s: float) -> str:
        return self.output_file_pattern.format(encoder=encoder, segment_duration_s=f"{segment_duration_s:g}")


@dataclass(frozen=True)
class LadderEncode:
    """One selected encode of the source CSV: a rung of the per-title ladder of one clip."""

    target_vmaf: int
    width: int
    height: int
    crf: int
    frame_rate_fps: float
    duration_s: float
    video_bytes: int
    bitrate_kbps: float
    vmaf: float


def read_ladder_encodes(
    specification: PerTitleLadderCatalogueSpecification,
) -> dict[tuple[str, str, float], list[LadderEncode]]:
    """Selected encodes per (encoder, clip, segment duration) for the quality metric of the specification.

    Targets that no encode of the clip reaches, and targets not in the specification, are left out.
    """
    encodes: dict[tuple[str, str, float], list[LadderEncode]] = {}
    with open(specification.source_csv, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["metric"] != specification.quality_metric or row["status"] != "ok":
                continue
            if int(row["target_vmaf"]) not in specification.vmaf_targets:
                continue
            key = (row["codec"], row["clip"], float(row["segment_duration_s"]))
            encodes.setdefault(key, []).append(
                LadderEncode(
                    target_vmaf=int(row["target_vmaf"]),
                    width=int(row["width"]),
                    height=int(row["height"]),
                    crf=int(row["crf"]),
                    frame_rate_fps=float(row["frame_rate_fps"]),
                    duration_s=float(row["duration_s"]),
                    video_bytes=int(row["video_bytes"]),
                    bitrate_kbps=float(row["bitrate_kbps"]),
                    vmaf=float(row["vmaf"]),
                )
            )
    return encodes


def ladder_rungs(encodes: list[LadderEncode]) -> list[LadderEncode]:
    """Rungs in increasing bitrate.

    Two VMAF targets can select the same encode; it then becomes one rung, kept for the lowest target. A rung
    that is not more expensive than the rung below it is dropped, so bitrates strictly increase.
    """
    rungs: list[LadderEncode] = []
    for encode in sorted(encodes, key=lambda encode: (encode.target_vmaf, encode.bitrate_kbps)):
        if rungs and encode.bitrate_kbps <= rungs[-1].bitrate_kbps:
            continue
        rungs.append(encode)
    return rungs


def _lognormal_factor_with_mean_one(random_generator: random.Random, coefficient_of_variation: float) -> float:
    if coefficient_of_variation == 0:
        return 1.0
    sigma = math.sqrt(math.log(1 + coefficient_of_variation**2))
    return random_generator.lognormvariate(-sigma**2 / 2, sigma)


def segment_durations_s(
    video_duration_s: float, segment_duration_s: float, drop_last_segment_shorter_than_s: float = 0.0
) -> list[float]:
    """Full segments, then a shorter last segment if the video duration is not a multiple.

    A last segment shorter than `drop_last_segment_shorter_than_s` is left out, which cuts the video short.
    """
    full_segment_count = int(video_duration_s // segment_duration_s)
    durations = [segment_duration_s] * full_segment_count
    remainder_s = round(video_duration_s - full_segment_count * segment_duration_s, 6)
    if remainder_s > 0 and remainder_s >= drop_last_segment_shorter_than_s:
        durations.append(remainder_s)
    return durations


def kept_video_bytes(video_bytes: int, source_duration_s: float, kept_duration_s: float) -> int:
    """Bytes of an encode that fall into the kept part of the video, at the encode's mean bitrate."""
    if kept_duration_s >= source_duration_s:
        return video_bytes
    return round(video_bytes * kept_duration_s / source_duration_s)


def scene_weights(
    specification: PerTitleLadderCatalogueSpecification, source_clip: str, durations_s: list[float]
) -> list[float]:
    """Share of the representation bytes per segment, the same for every encoder of a clip and segment duration."""
    random_generator = random.Random(f"{specification.seed}:{source_clip}:{durations_s[0]:g}")
    weights = [
        duration_s * _lognormal_factor_with_mean_one(random_generator, specification.segment_size_coefficient_of_variation)
        for duration_s in durations_s
    ]
    total = sum(weights)
    return [weight / total for weight in weights]


def split_bytes(total_bytes: int, weights: list[float]) -> list[int]:
    """Integer segment sizes of at least one byte that add up to `total_bytes` exactly.

    Every segment gets one byte, and the rest is split in proportion to the weights by the largest remainder
    method, so rounding never changes the total.
    """
    if total_bytes < len(weights):
        raise ValueError(f"{total_bytes} bytes cannot give each of {len(weights)} segments at least one byte")
    weight_sum = sum(weights)
    remaining_bytes = total_bytes - len(weights)
    quotas = [remaining_bytes * weight / weight_sum for weight in weights]
    sizes = [1 + math.floor(quota) for quota in quotas]
    by_largest_remainder = sorted(range(len(weights)), key=lambda index: (math.floor(quotas[index]) - quotas[index], index))
    for index in by_largest_remainder[: total_bytes - sum(sizes)]:
        sizes[index] += 1
    return sizes


def _segments(video_id: str, representation_id: str, durations_s: list[float], sizes: list[int]) -> list[dict[str, Any]]:
    segments = []
    start_s = 0.0
    for index, (duration_s, size_bytes) in enumerate(zip(durations_s, sizes, strict=True)):
        segments.append(
            {
                "index": index,
                "startS": round(start_s, 6),
                "durationS": duration_s,
                "url": f"/media/{video_id}/chunk-{representation_id}-{index + 1:05d}.m4s",
                "bytes": size_bytes,
            }
        )
        start_s += duration_s
    return segments


def generate_per_title_ladder_catalogue(
    specification: PerTitleLadderCatalogueSpecification,
    encodes: dict[tuple[str, str, float], list[LadderEncode]],
    encoder: str,
    segment_duration_s: float,
) -> dict[str, Any]:
    """Return the catalogue of one encoder and segment duration as an SFV `content.json` document."""
    codec = specification.codec_string_by_encoder[encoder]
    videos = []
    for clip in specification.clips:
        rungs = ladder_rungs(encodes.get((encoder, clip.source_clip, segment_duration_s), []))
        if not rungs:
            raise ValueError(f"No ladder encodes for {encoder}, {clip.source_clip}, {segment_duration_s:g} s segments")
        # The encodes of one clip share the source duration; dropping a very short last segment cuts it short
        source_duration_s = round(rungs[0].duration_s, 6)
        durations_s = segment_durations_s(
            source_duration_s, segment_duration_s, specification.drop_last_segment_shorter_than_s
        )
        video_duration_s = round(sum(durations_s), 6)
        weights = scene_weights(specification, clip.source_clip, durations_s)
        video_representations = []
        for number, rung in enumerate(rungs):
            representation_id = str(number)
            video_representations.append(
                {
                    "id": representation_id,
                    "bitrateKbps": round(rung.bitrate_kbps, 1),
                    "width": rung.width,
                    "height": rung.height,
                    "codec": codec,
                    "frameRateFps": rung.frame_rate_fps,
                    "targetVmaf": rung.target_vmaf,
                    "vmaf": rung.vmaf,
                    "crf": rung.crf,
                    "initUrl": f"/media/{clip.video_id}/init-{representation_id}.m4s",
                    "initBytes": VIDEO_INIT_SEGMENT_BYTES,
                    "segments": _segments(
                        clip.video_id,
                        representation_id,
                        durations_s,
                        split_bytes(kept_video_bytes(rung.video_bytes, source_duration_s, video_duration_s), weights),
                    ),
                }
            )
        audio_sizes = [round(specification.audio_bitrate_kbps * 1000 / 8 * duration_s) for duration_s in durations_s]
        audio_representation = {
            "id": "audio-0",
            "bitrateKbps": specification.audio_bitrate_kbps,
            "codec": specification.audio_codec,
            "initUrl": f"/media/{clip.video_id}/init-audio.m4s",
            "initBytes": AUDIO_INIT_SEGMENT_BYTES,
            "segments": _segments(clip.video_id, "audio", durations_s, audio_sizes),
        }
        videos.append(
            {
                "videoId": clip.video_id,
                "sourceClip": clip.source_clip,
                "manifestUrl": f"/media/{clip.video_id}/manifest.mpd",
                "manifestBytes": MANIFEST_BASE_BYTES
                + MANIFEST_BYTES_PER_REPRESENTATION * (len(video_representations) + 1),
                "durationS": video_duration_s,
                "segmentDurationS": segment_duration_s,
                "representations": {"video": video_representations, "audio": [audio_representation]},
            }
        )
    return {
        "schemaVersion": 1,
        "encodingCondition": {
            "encoder": encoder,
            "codec": codec,
            "segmentDurationS": segment_duration_s,
            "qualityMetric": specification.quality_metric,
        },
        "videos": videos,
    }


def generate_per_title_ladder_catalogues(specification_path: Path) -> dict[Path, dict[str, Any]]:
    """All catalogues of a specification, by output path (next to the specification)."""
    specification = PerTitleLadderCatalogueSpecification.from_file(specification_path)
    encodes = read_ladder_encodes(specification)
    return {
        specification_path.parent / specification.output_file_name(encoder, segment_duration_s): (
            generate_per_title_ladder_catalogue(specification, encodes, encoder, segment_duration_s)
        )
        for encoder in specification.codec_string_by_encoder
        for segment_duration_s in specification.segment_durations_s
    }


def write_per_title_ladder_catalogues(specification_path: Path) -> list[Path]:
    paths = []
    for path, catalogue in generate_per_title_ladder_catalogues(specification_path).items():
        path.write_text(json.dumps(catalogue, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
