"""Per-segment video quality from ITU-T P.1204.1 Mode 0 (AVQBits|M0)."""

from __future__ import annotations

from typing import Literal

from mode0_retraining.retrain_mode0 import (
    DEFAULT_CODING_COEFFS,
    degradation_due_to_coding,
    degradation_due_to_framerate,
    degradation_due_to_upscaling,
    norm_qp,
    pred_qp,
)
from mode0_retraining.utils import map_to_5, mos_from_r

# Model codec name per RFC 6381 sample entry or plain codec name
MODEL_CODEC_BY_CONTENT_CODEC = {
    "avc1": "h264",
    "avc3": "h264",
    "h264": "h264",
    "hev1": "hevc",
    "hvc1": "hevc",
    "h265": "hevc",
    "hevc": "hevc",
    "vp09": "vp9",
    "vp9": "vp9",
    "av01": "av1",
    "av1": "av1",
}


def model_codec_name(content_codec: str) -> str:
    """Return the model codec for a content codec string such as `avc1.64001f`."""
    sample_entry = content_codec.split(".")[0].lower()
    if sample_entry not in MODEL_CODEC_BY_CONTENT_CODEC:
        raise ValueError(f"P.1204.1 Mode 0 does not support codec {content_codec!r}")
    return MODEL_CODEC_BY_CONTENT_CODEC[sample_entry]


def segment_video_quality_mos(
    *,
    content_codec: str,
    bitrate_kbps: float,
    width: int,
    height: int,
    frame_rate_fps: float,
    device: Literal["pc", "mobile"],
    display_width: int,
    display_height: int,
) -> float:
    """Return the video quality MOS (1–5) of one segment.

    Same integration as `video_model_function_mode0` of `mode0_retraining`, with
    the display resolution as an input. That function fixes the display to 3840x2160.
    """
    codec = model_codec_name(content_codec)
    coding_pixels = width * height
    quantization = norm_qp(codec, pred_qp(device, codec, bitrate_kbps, coding_pixels, frame_rate_fps))
    total_degradation = (
        degradation_due_to_coding(DEFAULT_CODING_COEFFS[device][codec], quantization)
        + degradation_due_to_upscaling(device, coding_pixels, display_width * display_height)
        + degradation_due_to_framerate(device, frame_rate_fps)
    )
    return float(map_to_5(mos_from_r(100 - total_degradation)))
