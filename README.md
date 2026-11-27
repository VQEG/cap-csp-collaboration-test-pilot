# VQEG CAP–CSP Collaboration Test Pilot

This repository contains the code and design for the VQEG CAP–CSP collaboration test pilot.

## Background

The [_VQEG White Paper on Quality of Experience-Aware Management for Collaboration Between Network and Application Providers_](https://vqeg.org/media/ioypjcll/vqeg-qoe-management-white-paper.pdf) calls for a proof of concept under basic test and simulation conditions.

The first stage focuses on:

- Short-form video
- 5G network transmission
- Simple bandwidth profiles
- Simple CAP–CSP information exchange

Future stages may extend the pilot to other use cases. See the [working Google Doc](https://docs.google.com/document/d/1JH8LQ5bbNjfzoaymn4FptL_odv6txNAn-5TOC6kdAFE/edit?tab=t.0) for the research scope.

## How It Works

The harness simulates several phones (UEs) that watch short-form video in one 5G cell. Each UE runs the generic SFV player (initially written by Michi Seufert, as a submodule).

The SFV player is a wrapper around dash.js that decides which video segments to download, in which quality and when.

The harness passes each request as a block of bytes of known size to a network backend, FikoRE (maintained by Pablo Perez), which simulates the radio cell, its scheduler and the TCP transport in virtual time, and reports when the bytes arrive.

The player then plays, stalls or swipes to the next video, and we collect that information.

Depending on the signaling level (L0 to L4), the player also receives network information, such as the plan rate or live throughput. Each run writes session records, key numbers and a report, so that runs with and without information exchange can be compared.

The harness implements L0–L3 **information wiring** (shared state table, collaboration snapshots, dummy `CSPController`) without changing SFV B1/B2 behaviour at L0. Design: [docs/collaboration.md](docs/collaboration.md).

## Documentation

We keep a living set of design documents in the `docs/` folder. These are mostly AI-written so we can keep track of the many changes in our design.

Start with these documents:

- [Specification Overview](docs/README.md): system summary and index of all design documents
- [Architecture](docs/architecture.md): components, ownership, time, and execution modes
- [Decision Status](docs/decision-status-and-todos.md): unresolved decisions and implementation action items
- [Simulator Explorer](docs/simulator-explorer/README.md): interactive diagram of which components interact at each signaling level, backend and implementation state (**live at <https://vqeg.github.io/cap-csp-collaboration-test-pilot/>**) — kept in sync with the current state of the codebase and design documents

## Requirements

Clone with `git clone --recurse-submodules`, or initialize the submodules from the repository root in an existing checkout:

```bash
git submodule update --init --recursive
```

Building FikoRE requires Linux and the tools listed in its [README](5g-network-emulator/README.md); on macOS, use its Dockerfile. The transport package supports Python 3.10 or newer. The proposed common test harness uses Python 3.14 and `uv`.

## Usage

Run the example with two UEs (B1 and B2) on the deterministic mock backend. This needs `uv` and Node.js 20 or newer:

```bash
uv run capcsp run configs/experiments/b1-b2-two-ue-mock.json
```

The results go to `output/runs/<run_id>`. Pass a directory as the second argument to write them elsewhere. If the directory already holds a run, add `--force` to run it again.

To run B1 and B2 on a dedicated constant rate per UE instead, as assumed by the analytical model of Wehner et al., use `configs/experiments/b1-b2-two-ue-constant-rate.json`; its settings are described in [Experiments and Configuration](docs/experiments.md#constant-rate-backend).

The output directory contains the run manifest, one session record per UE with its P.1203 scores, the `NetworkStep` transcript, `kpis.csv` and `report.md`. See [Results and Scoring](docs/results-and-scoring.md#qoe-estimation-models) for how the scores are computed.

To compare several runs, run:

```bash
uv run capcsp report output/runs/run-a output/runs/run-b -o report.md
```

See [`docs/examples/stall-example-b1-b2-run/`](docs/examples/stall-example-b1-b2-run/README.md) and [`docs/examples/swipe-during-dropout-b1-b2-run/`](docs/examples/swipe-during-dropout-b1-b2-run/README.md) for the output layout of real runs. Actual experiment results should not be committed.

### macOS

Runs on FikoRE need Linux. On macOS, you can build the container via Docker and run inside it:

```bash
docker build -t capcsp .
docker run --rm -v "$PWD/output:/pilot/output" capcsp \
  capcsp run configs/experiments/b1-b2-two-ue-fikore.json
```

## Configs

Single-run parametric 5G experiments (`M01`–`M11`) live under `configs/experiments/layered/`:

```bash
uv run capcsp run configs/experiments/layered/m04-b1.json
uv run capcsp run configs/experiments/layered/m04-b2.json
```

See [`configs/experiments/layered/README.md`](configs/experiments/layered/README.md) for the `M01`–`M11` presets, the `Core-6` subset (`M01`, `M04`, `M05`, `M07`, `M09`, `M10`), and their unconstrained Proportional Fair cell baseline.

To run a whole grid of conditions, signaling levels, UE counts, behaviour mixes and replications, use a grid file:

```bash
uv run capcsp grid configs/grids/layered-core6.json --jobs 14
uv run capcsp grid configs/grids/layered-m01-m11.json --jobs 14
uv run capcsp grid configs/grids/parametric-load-sweep.json --jobs 14
uv run capcsp grid configs/grids/aomctc-encoding-conditions.json --jobs 14
```

The last grid varies the encoding: per-title ladders of five encoders at 1, 2, 4 and 5 s segments, from real encodes of the AOM CTC a2_2k long clips ([catalogue README](configs/content/aomctc-a2-2k-long/README.md)).

The grid runner shows the progress of the grid and of every running cell. It writes to `output/grids/<grid_id>`: one directory per cell, an `index.csv` with the status of every cell and one merged `kpis.csv`. If you start it again, it skips the cells that already finished with the same configuration. Add `--force` to run them again. Add `--list` to only list the cells. The grid format is described in [Experiments and Configuration](docs/experiments.md#experiment-grid).

## Testing

Run the tests with `uv run pytest`, or with `docker run --rm capcsp pytest` to include the FikoRE test.

## Current Validation

The harness runs Michi's SFV player (B1 and B2) with several UEs on the `mock` and `constant_rate` backends and on FikoRE through `TransportBackend`, including swipes, cancellations, byte accounting, and per-UE TCP connection modes (`persistent` HTTP/1.1-style pool, `multiplexed` RFC 9218 single-connection stream multiplexing, and `fresh` per-object connections). Parametric 5G cell presets `M01`–`M11` (`network.parametric_cell`) deterministically synthesize `fikore-effective.ini`, `fikore-timeline.ndjson`, and application-paced TCP background sessions (`backgroundSfV`) at run start from `Global.seed`. `configs/content/sfv-portrait-hd-90s.json` provides a provisional 18-video Full HD portrait ladder until the final pilot SFV content catalogue lands, and L1–L4 policy logic is not yet connected.

## Contributing

Open a pull request or submit an issue to contribute.

By contributing source code, you agree to license your work under the MIT License below. If your contribution contains third-party code, ensure you have the right to license it under MIT. Disclose any intellectual property rights (IPR) in your pull request or issue.

## Authors and Contributors

- Werner Robitza, AVEQ GmbH (maintainer)
- Pablo Perez, Nokia
- Michael Seufert, Uni Augsburg
- *add your name here!*

## License

Copyright (c) 2026, VQEG Contributors (see above)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
