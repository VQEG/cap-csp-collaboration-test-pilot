"""Markdown report comparing the KPIs of one or more runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capcsp.runner.kpis import collect_kpis

# Columns of the KPI table: (key, heading, format)
COLUMNS = (
    ("run_id", "Run", "{}"),
    ("ue_id", "UE", "{}"),
    ("player_behavior", "Player", "{}"),
    ("initial_playback_delay_s", "Initial delay (s)", "{:.3f}"),
    ("swipe_to_playback_delay_mean_s", "Swipe delay (s)", "{:.3f}"),
    ("stall_count_total", "Stalls", "{}"),
    ("stall_duration_total_s", "Stall time (s)", "{:.3f}"),
    ("quality_switch_count_total", "Switches", "{}"),
    ("bytes_delivered", "Delivered (kB)", "{:.0f}"),
    ("data_wastage_ratio", "Wasted", "{:.1%}"),
    ("goodput_mbps", "Goodput (Mbit/s)", "{:.2f}"),
    ("throughput_mbps", "Throughput (Mbit/s)", "{:.2f}"),
    ("rtt_mean_ms", "RTT (ms)", "{:.1f}"),
)


def _cell(value: Any, fmt: str, key: str) -> str:
    if value is None:
        return "–"
    if key == "bytes_delivered":
        value = value / 1000
    return fmt.format(value)


def _run_summary(run_dir: Path) -> str:
    manifest = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
    config = manifest["config"]
    parts = [
        f"backend `{manifest['network_backend']}`",
        f"{config['duration_s']} s simulated in {manifest.get('wall_s', '?')} s",
        f"{len(manifest['ue_ids'])} UEs",
        f"status {manifest['status']}",
    ]
    accounting = manifest.get("byte_accounting")
    if accounting:
        parts.append("bytes conserved" if accounting["bytes_conserved"] else "bytes NOT conserved")
    return f"- `{manifest['run_id']}`: " + ", ".join(parts)


def write_report(run_dirs: list[Path], path: Path) -> None:
    rows = [row for run_dir in run_dirs for row in collect_kpis(run_dir)]
    lines = ["# Experiment Report", "", "## Runs", ""]
    lines += [_run_summary(run_dir) for run_dir in run_dirs]
    lines += ["", "## KPIs per UE", ""]
    lines.append("| " + " | ".join(heading for _, heading, _ in COLUMNS) + " |")
    lines.append("|" + "---|" * len(COLUMNS))
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(key), fmt, key) for key, _, fmt in COLUMNS) + " |")
    lines += [
        "",
        "Swipe delay is the mean time from a swipe to playback of the next video. "
        "Wasted is the share of delivered bytes that were never played. "
        "Goodput is the bytes delivered to the player divided by the time with at least one download open. "
        "Throughput (network-layer, including retransmissions) and RTT are means over the backend's "
        "telemetry samples taken while a download was open.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
