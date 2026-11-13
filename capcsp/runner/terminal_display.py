"""Progress bars and result tables in the terminal, for `capcsp run` and `capcsp grid`."""

from __future__ import annotations

import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from capcsp.runner.grid_execution import GridCellOutcome
from capcsp.runner.run import load_config, run_experiment

STATUS_STYLES = {"completed": "green", "failed": "bold red", "skipped": "dim"}


def simulated_time_progress(console: Console) -> Progress:
    return Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.completed:>6.1f} / {task.total:.0f} s simulated"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def run_experiment_with_progress(config_path: Path, output_dir: Path, console: Console) -> dict[str, Any]:
    """Run one experiment with a progress bar of the simulated time."""
    config = load_config(config_path)
    duration_s = float(config["duration_s"])
    with simulated_time_progress(console) as progress:
        task = progress.add_task(config["run_id"], total=duration_s)

        def show_step(sim_time_s: float) -> None:
            progress.update(task, completed=min(sim_time_s, duration_s))
            if sim_time_s >= duration_s:
                progress.update(task, description=f"{config['run_id']} (scoring)")

        manifest = run_experiment(config_path, output_dir, on_step=show_step)
        progress.update(task, completed=duration_s, description=config["run_id"])
    return manifest


def kpi_table(rows: list[dict[str, Any]], title: str) -> Table:
    """The main KPIs per UE of one run."""
    table = Table(title=title, title_justify="left")
    for name in ("UE", "Behaviour", "Swipes", "Initial delay (s)", "Swipe delay (s)", "Stalls", "Wastage", "P.1203 O46"):
        table.add_column(name, justify="left" if name == "Behaviour" else "right")
    for row in rows:
        table.add_row(
            str(row["ue_id"]),
            "B1 (simple)" if row["player_behavior"] == "simple" else "B2 (preload)",
            str(row["swipes"]),
            _number(row.get("initial_playback_delay_s")),
            _number(row.get("swipe_to_playback_delay_mean_s")),
            str(row.get("stall_count_total", "")),
            _percent(row.get("data_wastage_ratio")),
            _number(row.get("p1203_o46"), digits=2),
        )
    return table


def grid_summary_table(kpi_rows: list[dict[str, Any]]) -> Table:
    """Mean P.1203 O46 and data wastage per condition and behaviour, over all completed cells."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in kpi_rows:
        groups[(str(row["condition"]), str(row["player_behavior"]))].append(row)
    table = Table(title="Mean over UEs and replications", title_justify="left")
    for name in ("Condition", "Behaviour", "UEs", "P.1203 O46", "Stalls per UE", "Wastage"):
        table.add_column(name, justify="left" if name in ("Condition", "Behaviour") else "right")
    for (condition, behavior), rows in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1] != "simple")):
        table.add_row(
            condition,
            "B1 (simple)" if behavior == "simple" else "B2 (preload)",
            str(len(rows)),
            _number(_mean(rows, "p1203_o46"), digits=2),
            _number(_mean(rows, "stall_count_total"), digits=2),
            _percent(_mean(rows, "data_wastage_ratio")),
        )
    return table


class RichGridProgressDisplay:
    """One bar for the whole grid and one bar per running cell."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self.grid_progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("cells"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        )
        self.cell_progress = simulated_time_progress(console)
        self.live = Live(_stack(self.grid_progress, self.cell_progress), console=console, refresh_per_second=8)
        self.grid_task: TaskID | None = None
        self.cell_tasks: dict[str, TaskID] = {}
        self.failed_count = 0

    def __enter__(self) -> RichGridProgressDisplay:
        self.live.__enter__()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.live.__exit__(*exc_info)

    def grid_started(self, cell_count: int, skipped_count: int) -> None:
        self.grid_task = self.grid_progress.add_task("Grid", total=cell_count, completed=skipped_count)
        if skipped_count:
            self.console.log(f"{skipped_count} of {cell_count} cells already finished, skipping them")

    def cell_started(self, run_id: str, duration_s: float) -> None:
        self.cell_tasks[run_id] = self.cell_progress.add_task(run_id, total=duration_s)

    def cell_progressed(self, run_id: str, sim_time_s: float) -> None:
        task = self.cell_tasks.get(run_id)
        if task is not None:
            self.cell_progress.update(task, completed=sim_time_s)

    def cell_finished(self, outcome: GridCellOutcome) -> None:
        task = self.cell_tasks.pop(outcome.run_id, None)
        if task is not None:
            self.cell_progress.remove_task(task)
        if self.grid_task is not None:
            self.grid_progress.advance(self.grid_task)
        style = STATUS_STYLES.get(outcome.status, "")
        message = f"[{style}]{outcome.status}[/] {outcome.run_id}"
        if outcome.wall_s is not None:
            message += f" in {outcome.wall_s:.1f} s"
        if outcome.error:
            self.failed_count += 1
            message += f": {outcome.error}"
        self.console.log(message)


def _stack(*renderables: Any) -> Table:
    grid = Table.grid()
    for renderable in renderables:
        grid.add_row(renderable)
    return grid


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) not in (None, "")]
    return statistics.fmean(values) if values else None


def _number(value: Any, digits: int = 3) -> str:
    if value in (None, ""):
        return "–"
    return f"{float(value):.{digits}f}"


def _percent(value: Any) -> str:
    if value in (None, ""):
        return "–"
    return f"{100 * float(value):.1f} %"
