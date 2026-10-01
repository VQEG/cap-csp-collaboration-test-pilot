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
ROUNDING = {"_s": 3, "_ms": 2, "_mbps": 3, "_ratio": 4}


def _round(key: str, value: Any) -> Any:
    if not isinstance(value, float):
        return value
    for suffix, digits in ROUNDING.items():
        if key.endswith(suffix):
            return round(value, digits)
    return value


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


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

    Throughput and RTT are means over the telemetry samples taken while the UE
    had at least one request open. Goodput is the number of bytes delivered to
    the player divided by the time with at least one request open.
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


def write_kpis(rows: list[dict[str, Any]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
