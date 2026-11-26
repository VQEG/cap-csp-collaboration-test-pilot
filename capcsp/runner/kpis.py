"""Per-UE KPIs from the outputs of one run."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path
from typing import Any

# Session summary fields copied into the KPI table
SUMMARY_FIELDS = (
    "initial_playback_delay_s",
    "swipe_wait_total_s",
    "videos_started",
    "videos_completed",
    "stall_count_total",
    "stall_duration_total_s",
    "quality_switch_count_total",
    "bytes_delivered",
    "bytes_data_wastage",
    "data_wastage_ratio",
    "bytes_unresolved_at_cutoff",
)

# Decimal places per unit suffix
ROUNDING = {
    "_s": 3,
    "_ms": 2,
    "_mbps": 3,
    "_kbps": 1,
    "_ratio": 4,
    "_o46": 3,
    "_o35": 3,
    "_o23": 3,
    "_mos": 3,
    "_efficiency": 4,
    "_fairness": 4,
}

# Tolerance in seconds for a video that was played in full
FULL_PLAY_TOLERANCE_S = 1e-3

# Lowest and highest value of a MOS scale
MOS_MIN = 1.0
MOS_MAX = 5.0


def _round(key: str, value: Any) -> Any:
    if not isinstance(value, float):
        return value
    for suffix, digits in ROUNDING.items():
        if key.endswith(suffix):
            return round(value, digits)
    return value


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _is_mid_video_swipe(video: dict[str, Any]) -> bool:
    """Return True if the user swiped away before the video finished playing."""
    if not video.get("swiped_away"):
        return False
    duration_s = video.get("video_duration_s")
    return duration_s is None or float(video.get("watch_duration_s") or 0.0) < float(duration_s) - FULL_PLAY_TOLERANCE_S


def _played_bitrate_mean_kbps(videos: list[dict[str, Any]]) -> float | None:
    """Return the mean bitrate of the played media, weighted by the played duration of each interval."""
    intervals = [interval for video in videos for interval in video.get("representation_intervals") or []]
    total_s = sum(interval.get("played_duration_s") or 0.0 for interval in intervals)
    if total_s <= 0:
        return None
    weighted_kbps = sum(
        (interval.get("bitrate_kbps") or 0.0) * (interval.get("played_duration_s") or 0.0) for interval in intervals
    )
    return weighted_kbps / total_s


def _sfv_session_kpis(record: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    """Return the per-video aggregates and the swipe-delay score of one session record."""
    videos = record.get("videos") or []
    bytes_wasted_swipe = sum((video.get("data_wastage_by_reason") or {}).get("swipe", 0) for video in videos)
    bytes_delivered = summary.get("bytes_delivered")
    return {
        "mid_video_swipes": sum(1 for video in videos if _is_mid_video_swipe(video)),
        "time_to_first_byte_mean_s": _mean(
            [video["time_to_first_byte_s"] for video in videos if video.get("time_to_first_byte_s") is not None]
        ),
        "played_bitrate_mean_kbps": _played_bitrate_mean_kbps(videos),
        "bytes_media_delivered": summary.get("bytes_media_delivered"),
        "bytes_wasted_swipe": bytes_wasted_swipe,
        "prefetch_efficiency": (
            1.0 - bytes_wasted_swipe / bytes_delivered if bytes_delivered is not None and bytes_delivered > 0 else None
        ),
        "sfv_nt_mos": (summary.get("sfv_nguyen_tran_output") or {}).get("mos"),
    }


def active_intervals(requests: list[dict[str, Any]], end_s: float) -> list[tuple[float, float]]:
    """Merge the [start, end] intervals of all requests into disjoint intervals."""
    spans = sorted(
        (request["startTime"], request["endTime"] if request.get("endTime") is not None else end_s)
        for request in requests
        if request.get("startTime") is not None
    )
    merged: list[tuple[float, float]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _is_active(intervals: list[tuple[float, float]], window_start: float, window_end: float) -> bool:
    return any(start < window_end and end > window_start for start, end in intervals)


def collect_kpis(run_dir: Path) -> list[dict[str, Any]]:
    """Return one KPI row per UE of the run in `run_dir`.

    Throughput and RTT are network-side diagnostics: means over the CSP
    telemetry samples whose interval overlaps a time with at least one request
    open. Goodput is the number of bytes delivered to the player divided by the
    time with at least one request open.
    """
    manifest = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
    end_s = manifest.get("sim_time_s", manifest["config"]["duration_s"])
    telemetry: dict[int, list[dict[str, Any]]] = {}
    telemetry_path = run_dir / "telemetry.jsonl"
    if telemetry_path.exists():
        for line in telemetry_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            telemetry.setdefault(row["ue_id"], []).append(row)

    rows = []
    for ue_id in manifest["ue_ids"]:
        result = json.loads((run_dir / "sessions" / f"ue-{ue_id}.json").read_text(encoding="utf-8"))
        record = result["sessionRecord"]
        summary = record["session_summary"]
        requests = result.get("requests", [])
        swipe_delays = summary.get("swipe_to_playback_delays_s") or []
        measured_swipe_delays = [
            value
            for value in swipe_delays
            if isinstance(value, (int, float))
        ]
        intervals = active_intervals(requests, end_s)
        active_s = sum(end - start for start, end in intervals)

        # A sample covers the time since the previous sample of the same UE
        active_samples = []
        previous_s = 0.0
        for sample in telemetry.get(ue_id, []):
            if _is_active(intervals, previous_s, sample["time_s"]):
                active_samples.append(sample)
            previous_s = sample["time_s"]

        row: dict[str, Any] = {
            "run_id": manifest["run_id"],
            "network_backend": record["network_backend"],
            "condition": record.get("condition"),
            "signaling_level": record.get("signaling_level"),
            "ue_id": ue_id,
            "player_behavior": record.get("player_behavior"),
            "termination_reason": result.get("terminationReason"),
            "requests": len(requests),
            "swipes": len(swipe_delays),
            "swipe_to_playback_delay_mean_s": _mean(measured_swipe_delays),
        }
        row.update({field: summary.get(field) for field in SUMMARY_FIELDS})
        session_scores = summary.get("p1203_output") or {}
        row["p1203_o46"] = session_scores.get("O46")
        row["p1203_o35"] = session_scores.get("O35")
        row["p1203_o23"] = session_scores.get("O23")
        row.update(_sfv_session_kpis(record, summary))
        row["active_download_time_s"] = active_s
        row["goodput_mbps"] = (
            sum(request.get("bytesDelivered", 0) for request in requests) * 8 / active_s / 1e6
            if active_s > 0
            else None
        )
        row["throughput_mbps"] = _mean(
            [s["throughput_mbps"] for s in active_samples if s.get("throughput_mbps") is not None]
        )
        row["rtt_mean_ms"] = _mean([s["rtt_ms"] for s in active_samples if s.get("rtt_ms") is not None])
        rows.append({key: _round(key, value) for key, value in row.items()})
    return rows


def hossfeld_fairness(mos_values: list[float]) -> float | None:
    """Return the Hoßfeld QoE fairness `1 - 2 * sigma(MOS) / (5 - 1)` with the population standard deviation.

    1 means that all UEs have the same MOS, 0 the largest possible spread. None without values.
    """
    if not mos_values:
        return None
    if len(mos_values) == 1:
        return 1.0
    return 1.0 - 2.0 * statistics.pstdev(mos_values) / (MOS_MAX - MOS_MIN)


def jain_fairness(values: list[float]) -> float | None:
    """Return Jain's fairness index `(sum x)^2 / (K * sum x^2)` of non-negative values.

    1 means equal shares, 1 / K that one UE gets everything. None without values or if all are 0.
    """
    total = sum(values)
    if not values or total <= 0:
        return None
    return total**2 / (len(values) * sum(value**2 for value in values))


def _valid(rows: list[dict[str, Any]], key: str, *, non_negative: bool = False) -> list[float]:
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    return [value for value in values if value >= 0] if non_negative else values


def collect_cell_fairness(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    """Return the fairness across the UEs of a cell from the rows of `collect_kpis`.

    - `hossfeld_p1203_o46`, `hossfeld_sfv_nt_mos`: Hoßfeld QoE fairness of the session MOS values
    - `jain_goodput_mbps`, `jain_throughput_mbps`: Jain's index of the goodput and the throughput

    A metric is None if no UE has a valid value.
    """
    fairness: dict[str, float | int | None] = {
        "hossfeld_p1203_o46": hossfeld_fairness(_valid(rows, "p1203_o46")),
        "hossfeld_sfv_nt_mos": hossfeld_fairness(_valid(rows, "sfv_nt_mos")),
        "jain_goodput_mbps": jain_fairness(_valid(rows, "goodput_mbps", non_negative=True)),
        "jain_throughput_mbps": jain_fairness(_valid(rows, "throughput_mbps", non_negative=True)),
    }
    rounded: dict[str, float | int | None] = {
        key: None if value is None else round(value, 4) for key, value in fairness.items()
    }
    rounded["ue_count"] = len(rows)
    return rounded


def collect_video_scores(run_dir: Path) -> list[dict[str, Any]]:
    """Return one row per scored video of the run in `run_dir`."""
    manifest = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
    rows = []
    for ue_id in manifest["ue_ids"]:
        result = json.loads((run_dir / "sessions" / f"ue-{ue_id}.json").read_text(encoding="utf-8"))
        for video in result["sessionRecord"]["videos"]:
            scores = video.get("p1203_output")
            if scores:
                rows.append(
                    {
                        "run_id": manifest["run_id"],
                        "ue_id": ue_id,
                        "video_id": video["video_id"],
                        "watch_duration_s": video.get("watch_duration_s"),
                        "O46": scores["O46"],
                        "O35": scores["O35"],
                        "O23": scores["O23"],
                    }
                )
    return rows


def write_kpis(rows: list[dict[str, Any]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
