"""Command-line interface: `capcsp run`, `capcsp grid` and `capcsp report`."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

from rich.console import Console

from capcsp.runner.grid_execution import cell_is_finished, run_grid
from capcsp.runner.grid_specification import GridSpecification
from capcsp.runner.kpis import collect_kpis, write_kpis
from capcsp.runner.report import write_report
from capcsp.runner.run import load_config
from capcsp.runner.terminal_display import (
    RichGridProgressDisplay,
    grid_summary_table,
    kpi_table,
    run_experiment_with_progress,
)

# Relative to the working directory, which git ignores
DEFAULT_OUTPUT_ROOT = Path("output")


def main() -> None:
    parser = argparse.ArgumentParser(prog="capcsp", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run an experiment, then write kpis.csv and report.md")
    run.add_argument("config", type=Path, help="Experiment configuration (JSON)")
    run.add_argument("output", type=Path, nargs="?", help="Output directory (default: output/runs/<run_id>)")
    run.add_argument("-f", "--force", action="store_true", help="Run again even if the output directory holds a run")
    grid = commands.add_parser("grid", help="Run every cell of an experiment grid; finished cells are skipped")
    grid.add_argument("grid", type=Path, help="Grid file (JSON)")
    grid.add_argument(
        "output", type=Path, nargs="?", help="Output directory with one subdirectory per cell (default: output/grids/<grid_id>)"
    )
    grid.add_argument(
        "-j", "--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2), help="Cells to run in parallel"
    )
    grid.add_argument("-f", "--force", action="store_true", help="Run every cell again, also the finished ones")
    grid.add_argument("--list", action="store_true", help="Only list the cells and whether they are finished")
    report = commands.add_parser("report", help="Write one report for several runs")
    report.add_argument("runs", type=Path, nargs="+", help="Output directories of runs")
    report.add_argument("-o", "--output", type=Path, default=Path("report.md"), help="Report file")
    args = parser.parse_args()
    console = Console(log_path=False)

    if args.command == "run":
        args.output = args.output or DEFAULT_OUTPUT_ROOT / "runs" / load_config(args.config)["run_id"]
        if (args.output / "run-manifest.json").exists() and not args.force:
            console.print(f"[bold red]{args.output} already holds a run.[/] Add --force to run it again.")
            sys.exit(1)
        manifest = run_experiment_with_progress(args.config, args.output, console)
        rows = collect_kpis(args.output)
        write_kpis(rows, args.output / "kpis.csv")
        write_report([args.output], args.output / "report.md")
        console.print(kpi_table(rows, f"{manifest['run_id']}: {manifest['status']} in {manifest['wall_s']} s"))
        console.print(f"Results in {args.output}")
    elif args.command == "grid":
        sys.exit(run_grid_command(args, console))
    else:
        write_report(args.runs, args.output)
        console.print(f"Report written to {args.output}")


def run_grid_command(args: argparse.Namespace, console: Console) -> int:
    specification = GridSpecification.from_file(args.grid)
    args.output = args.output or DEFAULT_OUTPUT_ROOT / "grids" / specification.grid_id
    if args.list:
        for cell in specification.cells():
            finished = cell_is_finished(cell, args.output / cell.run_id)
            console.print(f"{'[green]finished[/]' if finished else '[yellow]open[/]    '} {cell.run_id}")
        return 0
    with RichGridProgressDisplay(console) as display:
        outcomes = run_grid(specification, args.output, jobs=args.jobs, force=args.force, display=display)
    rows = collect_grid_kpis(args.output)
    if rows:
        console.print(grid_summary_table(rows))
    failed = [outcome for outcome in outcomes if outcome.status == "failed"]
    counts = {status: sum(outcome.status == status for outcome in outcomes) for status in ("completed", "skipped", "failed")}
    console.print(
        f"{counts['completed']} completed, {counts['skipped']} skipped, {counts['failed']} failed. "
        f"Index in {args.output / 'index.csv'}, KPIs in {args.output / 'kpis.csv'}"
    )
    for outcome in failed:
        console.print(f"[bold red]failed[/] {outcome.run_id}: see {args.output / outcome.run_id / 'error.log'}")
    return 1 if failed else 0


def collect_grid_kpis(output_dir: Path) -> list[dict[str, str]]:
    path = output_dir / "kpis.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


if __name__ == "__main__":
    main()
