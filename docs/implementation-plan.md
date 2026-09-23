# Implementation Plan

The implementation starts with a minimal closed-loop player-network runner. FikoRE co-simulation and real HTTP validation plug into the established interfaces after player logic is verified on deterministic backends.

## Proposed Package Layout

```text
cap-csp-collaboration-test-pilot/
  5g-network-emulator/          # FikoRE submodule
  capcsp/
    data_models.py
    player/
      engine.py
      video_feed.py
      swipe_models.py
      policies/
        simple.py
        preload.py
    network/
      api.py
      constant_rate.py
      trace.py
      fikore_cosim.py
      fikore_mock.py
      http.py
      cosim_messages.py
    exchange/
      shared_state.py
      emulated_telemetry.py
    origin/
      server.py
    scoring/
      records.py
      p1203.py
      p1204_1_pv.py
      aggregate.py
    runner/
      config.py
      cell.py
      grid.py
      fikore_process.py
      l3_controller.py
  configs/
    content.yaml
    network_conditions.yaml
    experiments/
    fikore/
  results/
  analysis/
  docs/
```

The system is structured as a single installable Python package (`capcsp`). Subpackages isolate domain responsibilities without requiring multiple distributions or standalone microservices.

## Build Sequence

1. Core package skeleton, data models, configuration parser, player engine, swipe model, B1/B2 baseline policies, and constant-rate network backend.
2. Per-segment session records, request logs, baseline scoring functions, and deterministic test fixtures.
3. Trace replay backend, shared-state gating, and L0, L1, L2, and L4 policy inputs.
4. Co-simulation message models, FikoRE mock adapter, FikoRE backend, process wrapper, and multi-UE tests against the mock.
5. Integration against the real emulator and co-simulation acceptance testing, once the FikoRE-side capabilities listed in the [adapter requirements](fikore-cosim.md#adapter-requirements) are available in the emulator submodule.
6. Real HTTP origin server and live traffic path through FikoRE in emulated mode.
7. L3 controller design and network-side adaptation hooks.
8. Multi-video dash.js extension (with Michi), policy porting to JavaScript, and offline-versus-real validation runs.

Each milestone delivers a runnable test harness. Steps 1 through 4 proceed independently of FikoRE C++ development.

## FikoRE Mock Adapter

The mock implements the [`fikore-control-1` wire protocol](fikore-cosim-messages.md) over a local Unix domain socket, playing FikoRE's side of it: greeting, acknowledgements, the credit barrier, and a `state` block. It models deterministic byte allocation across multiple UEs, concurrent objects, cancellation tails, and telemetry fixtures.

Purposes:

- Enable Python harness development prior to FikoRE C++ adapter readiness
- Provide reference protocol transcripts for C++ adapter testing
- Fast execution of protocol edge cases in continuous integration

The mock is a development tool and is never used to generate research results.

## Testing Strategy

- **Unit tests**: buffer states, stall transitions, swipe handling with active downloads, prefetch budgeting, cancellation waste attribution, signaling-level gating, configuration validation, and scoring computations.
- **Contract tests**: enforce semantic consistency across constant-rate, trace, mock, and FikoRE backends.
- **Integration tests**: multi-UE concurrency, startup before time advances, session termination, seeded reproducibility, adapter error recovery, 10 ms versus 1 ms synchronization checks, and legacy FikoRE non-cosim regression checks.

## Real-Traffic Validation

Validation runs use an HTTP origin server behind FikoRE in real-time emulation. The origin delivers byte payloads matching sizes defined in `content.yaml`.

The multi-video dash.js player issues HTTP requests through the emulator. Transport configuration (HTTP version, TCP congestion control, connection pools) remains fixed per test grid and is logged with session records. This setup measures transport dynamics absent in offline co-simulation: TCP slow start, TLS/HTTP handshakes, loss recovery, and head-of-line blocking.

JavaScript policy ports occur only after Python baseline algorithms are verified. The dash.js player manages multiple HTML5 video elements alongside a centralized short-form controller governing playback queues, swipes, prefetching, and cancellation.

## Team Roles

- **Werner**: Python architecture, mock adapter, player engine, experiment runner, scoring, and documentation.
- **Pablo**: FikoRE core changes (run seed, per-tag packet attribution, radio telemetry, fail-stop) and the co-simulation adapter in `capcsp/network/`.
- **Michi**: Short-form state machine design, policy observation schemas, adaptation heuristics, and multi-video dash.js integration.

## Documentation Maintenance

- Protocol schema changes → [fikore-cosim-messages.md](fikore-cosim-messages.md)
- Player state or policy updates → [player-api.md](player-api.md)
- Experiment parameters → [experiments.md](experiments.md)
- System-level architectural changes → [architecture.md](architecture.md)
- Unresolved decisions and implementation work → [decision-status-and-todos.md](decision-status-and-todos.md)
