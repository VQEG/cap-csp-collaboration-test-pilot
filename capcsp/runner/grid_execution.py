"""Run the cells of an experiment grid in parallel, skip finished cells, and merge their KPIs.

Output directory layout:

- <run_id>/: the normal output of one run, plus experiment.json (its configuration) and error.log on failure
- index.csv: one row per cell with its axis values, configuration hash, status and wall time
- kpis.csv: the KPI rows of all completed cells, led by the axes that the KPI table lacks (UE count, mix, replication)
"""

from __future__ import annotations

import csv
import json
import multiprocessing
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import Any, Protocol

from capcsp.runner.grid_specification import GridCell, GridSpecification
from capcsp.runner.kpis import collect_kpis, write_kpis
from capcsp.runner.report import write_report
from capcsp.runner.run import run_experiment

CELL_CONFIG_NAME = "experiment.json"
# Minimum wall-clock time between two progress messages of one cell
PROGRESS_INTERVAL_S = 0.25


@dataclass(frozen=True)
class GridCellOutcome:
    run_id: str
    status: str
    """completed, failed or skipped (finished in an earlier invocation with the same configuration)"""
    wall_s: float | None = None
    error: str | None = None


class GridProgressDisplay(Protocol):
    def grid_started(self, cell_count: int, skipped_count: int) -> None: ...
    def cell_started(self, run_id: str, duration_s: float) -> None: ...
    def cell_progressed(self, run_id: str, sim_time_s: float) -> None: ...
    def cell_finished(self, outcome: GridCellOutcome) -> None: ...


class SilentGridProgressDisplay:
    def grid_started(self, cell_count: int, skipped_count: int) -> None:
        pass

    def cell_started(self, run_id: str, duration_s: float) -> None:
        pass

    def cell_progressed(self, run_id: str, sim_time_s: float) -> None:
        pass

    def cell_finished(self, outcome: GridCellOutcome) -> None:
        pass


def cell_is_finished(cell: GridCell, cell_dir: Path) -> bool:
    """A cell is finished when it completed with the same configuration."""
    manifest_path = cell_dir / "run-manifest.json"
    config_path = cell_dir / CELL_CONFIG_NAME
    if not manifest_path.exists() or not config_path.exists():
        return False
    if json.loads(manifest_path.read_text(encoding="utf-8")).get("status") != "completed":
        return False
    if not (cell_dir / "kpis.csv").exists():
        return False
    return json.loads(config_path.read_text(encoding="utf-8")) == cell.experiment_config


def run_grid_cell(run_id: str, experiment_config: dict[str, Any], cell_dir: Path, progress_queue: Any) -> GridCellOutcome:
    """Run one cell in a worker process and report its progress through `progress_queue`."""
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "error.log").unlink(missing_ok=True)
    config_path = cell_dir / CELL_CONFIG_NAME
    config_path.write_text(json.dumps(experiment_config, indent=2) + "\n", encoding="utf-8")
    progress_queue.put(("started", run_id, experiment_config["duration_s"]))
    last_message_at = 0.0

    def report_step(sim_time_s: float) -> None:
        nonlocal last_message_at
        now = time.monotonic()
        if now - last_message_at >= PROGRESS_INTERVAL_S:
            last_message_at = now
            progress_queue.put(("progressed", run_id, sim_time_s))

    wall_start = time.perf_counter()
    try:
        run_experiment(config_path, cell_dir, on_step=report_step)
        write_kpis(collect_kpis(cell_dir), cell_dir / "kpis.csv")
        write_report([cell_dir], cell_dir / "report.md")
    except Exception as error:  # a failed cell must not stop the grid
        (cell_dir / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        return GridCellOutcome(run_id, "failed", round(time.perf_counter() - wall_start, 3), f"{type(error).__name__}: {error}")
    return GridCellOutcome(run_id, "completed", round(time.perf_counter() - wall_start, 3))


def run_grid(
    specification: GridSpecification,
    output_dir: Path,
    *,
    jobs: int = 1,
    force: bool = False,
    display: GridProgressDisplay | None = None,
) -> list[GridCellOutcome]:
    """Run all unfinished cells with up to `jobs` worker processes, then write index.csv and kpis.csv.

    With `force`, finished cells run again too.
    """
    if jobs < 1:
        raise ValueError("jobs must be positive")
    display = display or SilentGridProgressDisplay()
    output_dir.mkdir(parents=True, exist_ok=True)
    cells = specification.cells()
    if len({cell.run_id for cell in cells}) != len(cells):
        raise ValueError("Grid cells must have distinct run IDs; check the condition and mix names")
    outcomes: dict[str, GridCellOutcome] = {}
    pending = []
    for cell in cells:
        if not force and cell_is_finished(cell, output_dir / cell.run_id):
            manifest = json.loads((output_dir / cell.run_id / "run-manifest.json").read_text(encoding="utf-8"))
            outcomes[cell.run_id] = GridCellOutcome(cell.run_id, "skipped", manifest.get("wall_s"))
        else:
            pending.append(cell)
    display.grid_started(len(cells), len(cells) - len(pending))

    # Spawned workers start clean; FikoRE and Node.js child processes are not inherited from a forked parent
    context = multiprocessing.get_context("spawn")
    with context.Manager() as manager, ProcessPoolExecutor(max_workers=jobs, mp_context=context) as executor:
        progress_queue = manager.Queue()
        futures: dict[Future[GridCellOutcome], GridCell] = {
            executor.submit(run_grid_cell, cell.run_id, cell.experiment_config, output_dir / cell.run_id, progress_queue): cell
            for cell in pending
        }
        running = set(futures)
        while running:
            done, running = wait(running, timeout=0.1, return_when=FIRST_COMPLETED)
            _forward_progress(progress_queue, display)
            for future in done:
                cell = futures[future]
                try:
                    outcome = future.result()
                except Exception as error:  # the worker process itself died
                    outcome = GridCellOutcome(cell.run_id, "failed", error=f"{type(error).__name__}: {error}")
                outcomes[cell.run_id] = outcome
                display.cell_finished(outcome)
                write_grid_index(cells, outcomes, output_dir / "index.csv")
        _forward_progress(progress_queue, display)

    ordered = [outcomes[cell.run_id] for cell in cells]
    write_grid_index(cells, outcomes, output_dir / "index.csv")
    write_grid_kpis(cells, output_dir)
    return ordered


def _forward_progress(progress_queue: Any, display: GridProgressDisplay) -> None:
    while True:
        try:
            message = progress_queue.get_nowait()
        except Empty:
            return
        kind, run_id, value = message
        if kind == "started":
            display.cell_started(run_id, value)
        else:
            display.cell_progressed(run_id, value)


def write_grid_index(cells: list[GridCell], outcomes: dict[str, GridCellOutcome], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["run_id", *cells[0].axis_values, "config_hash", "status", "wall_s", "error"])
        for cell in cells:
            outcome = outcomes.get(cell.run_id)
            writer.writerow(
                [
                    cell.run_id,
                    *cell.axis_values.values(),
                    cell.config_hash,
                    # A skipped cell completed in an earlier invocation
                    ("completed" if outcome.status == "skipped" else outcome.status) if outcome else "pending",
                    "" if outcome is None or outcome.wall_s is None else outcome.wall_s,
                    "" if outcome is None or outcome.error is None else outcome.error,
                ]
            )


def write_grid_kpis(cells: list[GridCell], output_dir: Path) -> list[dict[str, Any]]:
    """Merge the KPI tables of all finished cells into one.

    The KPI rows already hold the condition and signaling level; the other axes become leading columns.
    """
    rows = []
    for cell in cells:
        cell_kpis = output_dir / cell.run_id / "kpis.csv"
        if not cell_is_finished(cell, output_dir / cell.run_id):
            continue
        with open(cell_kpis, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                axis_values = {"ue_count": cell.ue_count, "behavior_mix": cell.behavior_mix, "replication": cell.replication}
                rows.append({**axis_values, **row})
    if rows:
        write_kpis(rows, output_dir / "kpis.csv")
    return rows
