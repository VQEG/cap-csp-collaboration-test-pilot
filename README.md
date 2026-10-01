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

## Requirements

> [!NOTE]
> The FikoRE submodule contains the incremental control path, the transport models and `TransportBackend`. The SFV player is included as a second submodule. The common harness and the full experiment matrix are still under development.

Clone with `git clone --recurse-submodules`, or run `git submodule update --init` in an existing checkout. Building FikoRE requires Linux and the tools listed in its [README](5g-network-emulator/README.md); on macOS, use its Dockerfile. The transport package supports Python 3.10 or newer. The proposed common test harness uses Python 3.14 and `uv`.

## Usage

Run the example with two UEs (B1 and B2) on the deterministic mock backend. This needs `uv` and Node.js 20 or newer:

```bash
uv run capcsp run configs/experiments/b1-b2-two-ue-mock.json output/mock
```

The output directory holds the run manifest, one session record per UE, the `NetworkStep` transcript, `kpis.csv` and `report.md`. `uv run capcsp report output/run-a output/run-b -o report.md` compares several runs.

Runs on FikoRE need Linux. On macOS, build the container and run inside it:

```bash
docker build -t capcsp .
docker run --rm -v "$PWD/output:/pilot/output" capcsp \
  capcsp run configs/experiments/b1-b2-two-ue-fikore.json output/fikore
```

The contributed FikoRE condition matrix is under `configs/experiments/vqeg/`. For example:

```bash
uv run capcsp run configs/experiments/vqeg/c1-b1-b2.json output/vqeg/c1
```

See `configs/experiments/vqeg/README.md` for all nine C1–C8a/C8b runs, their common transport assumptions and the complete matrix command.

Run the tests with `uv run pytest`, or with `docker run --rm capcsp pytest` to include the FikoRE test.

Start with these documents:

- [Specification Overview](docs/README.md): system summary and index of all design documents
- [Architecture](docs/architecture.md): components, ownership, time, and execution modes
- [Decision Status](docs/decision-status-and-todos.md): unresolved decisions and implementation action items
- [Offline Transport Validation](docs/offline-transport-validation.md): run the SFV v0.7.2 example against its mock and FikoRE

The build sequence is in the [implementation plan](docs/implementation-plan.md).

## Current Validation

The harness runs Michi's SFV player (B1 and B2) with several UEs on the `mock` backend and on FikoRE through `TransportBackend`, including swipes, cancellations, byte accounting and persistent per-UE TCP connection reuse. Fresh TCP connections per object remain available as a comparison mode. This is not yet the full pilot experiment matrix: content is still the three-video SFV test fixture, and L1 to L4 are not connected.

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
