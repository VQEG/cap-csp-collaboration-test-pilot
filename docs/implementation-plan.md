# Implementation Plan

The implementation starts with a minimal closed-loop player-network runner. FikoRE co-simulation and real HTTP validation plug into the established interfaces after player logic is verified on deterministic backends.

## Proposed Package Layout

```text
cap-csp-collaboration-test-pilot/
  5g-network-emulator/          # FikoRE submodule
    transport/                  # Generic transport, Links and NetworkBackend
  capcsp/
    data_models.py
    player/
      bridge.py                 # Node.js player process behind the Network Backend API
    network/
      api.py
      constant_rate.py
      trace.py
      transport_fikore.py       # Thin wiring to submodule TransportBackend
      http.py
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

The SFV reference and SFV-VQEG repositories are external sibling checkouts for the current validation, not submodules of this repository.

The system is structured as a single installable Python package (`capcsp`). Subpackages isolate domain responsibilities without requiring multiple distributions or standalone microservices.

## Build Sequence

1. Core package skeleton, data models, configuration parser, bridge to the JavaScript player, and constant-rate network backend.
2. Per-segment session records, request logs, baseline scoring functions, and deterministic test fixtures.
3. Trace replay backend, shared-state gating, and L0, L1, L2, and L4 policy inputs.
4. Wire the generic `TransportBackend` and `FikoreLink` from the FikoRE submodule into the common harness; retain only pilot-specific request and configuration mapping in `capcsp/network/`.
5. Integrate the JavaScript SFV engine through the validated `NetworkStep` bridge and run the mock/FikoRE acceptance procedure in [Offline Transport Validation](offline-transport-validation.md).
6. Real HTTP origin server and live traffic path through FikoRE in emulated mode.
7. L3 controller design and network-side adaptation hooks.
8. Real-HTTP runs with the multi-video dash.js player (with Michi) and offline-versus-real validation runs.

The FikoRE-side control plane, generic client and transport models needed by steps 4 and 5 are now available in the pinned submodule. The common harness wiring remains to be implemented.

## FikoRE Mock Adapter

The current SFV integration mock implements the generic `NetworkBackend` contract in memory. It models deterministic shared byte allocation, concurrent objects and cancellation tails; it deliberately does not emulate `fikore-control-1`, TCP or radio behaviour.

Purposes:

- Enable player and bridge development without FikoRE
- Provide deterministic `NetworkStep` transcripts
- Exercise IDs, concurrent objects, swipes and cancellation semantics quickly

The mock is a development tool and is never used to generate research results.

## Testing Strategy

- **Unit tests**: buffer states, stall transitions, swipe handling with active downloads, prefetch budgeting, cancellation waste attribution, signaling-level gating, configuration validation, and scoring computations.
- **Contract tests**: enforce semantic consistency across constant-rate, trace, mock, and FikoRE backends.
- **Integration tests**: use `make test-transport` and `make test-transport-integration` in the submodule for transport and wire behaviour, then the SFV procedure for multi-UE startup, session termination, B1/B2 and cancellation. The backend keeps 1 ms Link causality while exposing 10 ms player windows.

## Real-Traffic Validation

Validation runs use an HTTP origin server behind FikoRE in real-time emulation. The origin delivers byte payloads matching sizes defined in `content.yaml`.

The multi-video dash.js player issues HTTP requests through the emulator. Transport configuration (HTTP version, TCP congestion control, connection pools) remains fixed per test grid and is logged with session records. This setup measures transport dynamics that offline runs model only in part or not at all: TCP slow start, TLS/HTTP handshakes, loss recovery, and head-of-line blocking.

The dash.js player manages multiple HTML5 video elements alongside a centralized short-form controller governing playback queues, swipes, prefetching, and cancellation.

## Team Roles

- **Werner**: Python architecture, mock adapter, JavaScript player bridge, experiment runner, scoring, and documentation.
- **Pablo**: FikoRE core changes (run seed, per-tag packet attribution, radio telemetry, fail-stop) and the generic `fikore-control-1` Python client and transport models in the FikoRE repository. The pilot-specific FikoRE backend built on that client lives in `capcsp/network/`.
- **Michi**: JavaScript player (engine, B1/B2 policies, multi-video dash.js integration) and its connection to the Network Backend API.

## Documentation Maintenance

- Protocol schema changes → [fikore-cosim-messages.md](fikore-cosim-messages.md)
- Player state or policy updates → [player-api.md](player-api.md)
- Experiment parameters → [experiments.md](experiments.md)
- System-level architectural changes → [architecture.md](architecture.md)
- Unresolved decisions and implementation work → [decision-status-and-todos.md](decision-status-and-todos.md)
