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


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def collect_kpis(run_dir: Path) -> list[dict[str, Any]]:
    """Return one KPI row per UE of the run in `run_dir`."""
    manifest = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
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
        swipe_delays = summary.get("swipe_to_playback_delays_s") or []
        samples = telemetry.get(ue_id, [])
        row: dict[str, Any] = {
            "run_id": manifest["run_id"],
            "network_backend": record["network_backend"],
            "condition": record.get("condition"),
            "signaling_level": record.get("signaling_level"),
            "ue_id": ue_id,
            "player_behavior": record.get("player_behavior"),
            "termination_reason": result.get("terminationReason"),
            "requests": len(result.get("requests", [])),
            "swipes": len(swipe_delays),
            "swipe_to_playback_delay_mean_s": _mean(swipe_delays),
        }
        row.update({field: summary.get(field) for field in SUMMARY_FIELDS})
        row["throughput_mean_mbps"] = _mean(
            [s["throughput_mbps"] for s in samples if s.get("throughput_mbps") is not None]
        )
        row["rtt_mean_ms"] = _mean([s["rtt_ms"] for s in samples if s.get("rtt_ms") is not None])
        rows.append(row)
    return rows


def write_kpis(rows: list[dict[str, Any]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
