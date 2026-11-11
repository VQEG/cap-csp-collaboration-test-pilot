"""Markdown report comparing the KPIs of one or more runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capcsp.runner.kpis import collect_kpis, collect_video_scores

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
    ("p1203_o46", "O46", "{:.2f}"),
    ("p1203_o35", "O35", "{:.2f}"),
    ("p1203_o23", "O23", "{:.2f}"),
    ("goodput_mbps", "Goodput (Mbit/s)", "{:.2f}"),
    ("throughput_mbps", "Throughput (Mbit/s)", "{:.2f}"),
    ("rtt_mean_ms", "RTT (ms)", "{:.1f}"),
)


# Columns of the per-video score table: (key, heading, format)
VIDEO_SCORE_COLUMNS = (
    ("run_id", "Run", "{}"),
    ("ue_id", "UE", "{}"),
    ("video_id", "Video", "{}"),
    ("watch_duration_s", "Watched (s)", "{:.1f}"),
    ("O46", "O46", "{:.2f}"),
    ("O35", "O35", "{:.2f}"),
    ("O23", "O23", "{:.2f}"),
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


def _table(columns: tuple[tuple[str, str, str], ...], rows: list[dict[str, Any]]) -> list[str]:
    lines = ["| " + " | ".join(heading for _, heading, _ in columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(key), fmt, key) for key, _, fmt in columns) + " |")
    return lines


def _model_version(model: dict[str, Any]) -> str:
    revision = f", commit {model['commit'][:7]}" if model.get("commit") else ""
    return f"{model['standard']} (`{model['package']}` {model['version']}{revision})"


def _scoring_summary(run_dir: Path) -> str | None:
    manifest = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
    scoring = manifest.get("scoring")
    if not scoring:
        return None
    settings = scoring["settings"]
    return (
        f"- `{manifest['run_id']}`: {_model_version(scoring['integration_model'])}, "
        f"{_model_version(scoring['video_model'])}, device {settings['device']}, "
        f"display {settings['display_width']}x{settings['display_height']}, "
        f"assumed frame rate {settings['frame_rate_fps']:g} fps, assumed constant audio score O21 {settings['audio_o21']:g}"
    )


def write_report(run_dirs: list[Path], path: Path) -> None:
    rows = [row for run_dir in run_dirs for row in collect_kpis(run_dir)]
    lines = ["# Experiment Report", "", "## Runs", ""]
    lines += [_run_summary(run_dir) for run_dir in run_dirs]
    lines += ["", "## KPIs per UE", ""]
    lines += _table(COLUMNS, rows)
    lines += [
        "",
        "Swipe delay is the mean time from a swipe to playback of the next video. "
        "Wasted is the share of delivered bytes that were never played. "
        "Goodput is the bytes delivered to the player divided by the time with at least one download open. "
        "Throughput (network-layer, including retransmissions) and RTT are network-side diagnostics: "
        "means over the CSP telemetry samples (1 s each by default) that overlap a time with a download "
        "open, so idle time inside a sample lowers the throughput. "
        "O46, O35 and O23 are the means of the P.1203 scores per video, weighted by played duration.",
        "",
    ]
    video_scores = [row for run_dir in run_dirs for row in collect_video_scores(run_dir)]
    if video_scores:
        lines += ["## P.1203 Scores per Video", ""]
        lines += _table(VIDEO_SCORE_COLUMNS, video_scores)
        lines += [
            "",
            "Videos with less than half a second of played media have no score. "
            "P.1203 is only valid for media of 1 minute or longer; shorter videos are scored anyway.",
            "",
        ]
    scoring_summaries = [summary for summary in map(_scoring_summary, run_dirs) if summary]
    if scoring_summaries:
        lines += ["## Quality Models", "", *scoring_summaries, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
