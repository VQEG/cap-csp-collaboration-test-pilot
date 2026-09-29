"""Command-line interface: `capcsp run` and `capcsp report`."""

from __future__ import annotations

import argparse
from pathlib import Path

from capcsp.runner.kpis import collect_kpis, write_kpis
from capcsp.runner.report import write_report
from capcsp.runner.run import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(prog="capcsp", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run an experiment, then write kpis.csv and report.md")
    run.add_argument("config", type=Path, help="Experiment configuration (JSON)")
    run.add_argument("output", type=Path, help="Output directory")
    report = commands.add_parser("report", help="Write one report for several runs")
    report.add_argument("runs", type=Path, nargs="+", help="Output directories of runs")
    report.add_argument("-o", "--output", type=Path, default=Path("report.md"), help="Report file")
    args = parser.parse_args()

    if args.command == "run":
        manifest = run_experiment(args.config, args.output)
        write_kpis(collect_kpis(args.output), args.output / "kpis.csv")
        write_report([args.output], args.output / "report.md")
        print(f"{manifest['run_id']}: {manifest['status']} in {manifest['wall_s']} s, results in {args.output}")
    else:
        write_report(args.runs, args.output)
        print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
