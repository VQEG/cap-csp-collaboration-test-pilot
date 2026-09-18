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
> Nothing has been built yet. The repository currently contains the FikoRE submodule and the design specifications.

Building FikoRE requires the tools listed in its [README](5g-network-emulator/README.md). The proposed test harness uses Python 3.14 and `uv`.

## Usage

Start with these documents:

- [Specification Overview](docs/README.md): system summary and index of all design documents
- [Architecture](docs/architecture.md): components, ownership, time, and execution modes
- [Decision Status](docs/decision-status-and-todos.md): unresolved decisions and implementation action items

The build sequence is in the [implementation plan](docs/implementation-plan.md).

## Results

No pilot results exist yet.

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
