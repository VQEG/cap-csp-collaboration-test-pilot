# Offline Transport Validation

This procedure validates the SFV v0.7.2 generic `NetworkBackend` seam first with its deterministic mock and then with FikoRE's modelled transport. The two runs use the same player, dataset, sessions, seeds, swipes and 10 ms cadence. Only the backend changes.

The mock is a contract baseline, not a radio or TCP model. Matching request decisions in the short fixture does not imply that both networks are equivalent.

This procedure uses Michi's external SFV-VQEG repository and Pablo's `validate_sfv.py`. It records the first integration proof. The same check now runs in this repository with `capcsp run` on `configs/experiments/b1-b2-two-ue-mock.json` and `configs/experiments/b1-b2-two-ue-fikore.json` (see the [README](../README.md#usage)), using the `sfv-reference-implementation` submodule instead of a sibling checkout. Backend names differ between the two procedures: the SFV-VQEG fixture calls the mock `constant_rate_mock`, and its session records store `network_backend: external` for both runs. The harness records `mock` and `transport_fikore` as defined in the [Network Backend API](network-backend-api.md#backend-implementations).

## Revisions

The validated external versions are:

- `SFV-VQEG-CAP-CSP-Collaboration-Experiments` v0.7.2;
- `SFV-Reference-Implementation` v0.7.0;
- the FikoRE `dev` commit pinned by this repository's submodule.

Record exact SHAs with `git rev-parse HEAD` in each checkout and from the FikoRE integration's `run-manifest.json` fields `fikore_revision`, `sfv_vqeg_revision` and `sfv_core_revision`.

## Checkout Layout and Prerequisites

The two SFV repositories must be sibling directories with their exact checkout names because the VQEG package declares `file:../SFV-Reference-Implementation`. The `sfv-reference-implementation` submodule of this repository is pinned to the same v0.7.0 tag, but cannot replace the sibling checkout for this procedure. The pilot/FikoRE checkout can live elsewhere. Set paths explicitly; no personal absolute path is required:

```bash
export PILOT_ROOT=/path/to/cap-csp-collaboration-test-pilot
export FIKORE_ROOT="$PILOT_ROOT/5g-network-emulator"
export SFV_VQEG_ROOT=/path/to/SFV-VQEG-CAP-CSP-Collaboration-Experiments
export SFV_CORE_ROOT=/path/to/SFV-Reference-Implementation
export OUT_ROOT="${TMPDIR:-/tmp}/sfv-fikore-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT_ROOT"
```

Requirements are Linux, Node.js 20+, Python 3.10+, a C++ build toolchain and `jq`. FikoRE links against `libmnl` and `libnetfilter_queue`, which exist only on Linux; on macOS, run the procedure inside a container built from FikoRE's Dockerfile. Poetry is not required for these runtime checks.

Install and verify the JavaScript dependencies:

```bash
cd "$SFV_CORE_ROOT"
npm ci
npm run verify

cd "$SFV_VQEG_ROOT"
npm ci
npm test
python3 -m unittest discover -s test -p 'test_*.py'
```

`npm run test:all` is equivalent when a current Poetry installation is available. The direct command above also works with distributions that package an older Poetry version.

Build FikoRE and its transport tests:

```bash
cd "$FIKORE_ROOT"
make -j"$(nproc)"
make test-transport
make test-transport-integration
```

## Deterministic Mock

```bash
cd "$SFV_VQEG_ROOT"
SFV_CORE_ROOT="$SFV_CORE_ROOT" \
python3 scripts/run-network-experiment.py \
  examples/network-backend-mock.json \
  "$OUT_ROOT/mock"
```

The JSON fixture defines two UEs:

- UE 0: simple/B1 behaviour;
- UE 1: preload/B2 behaviour;
- one swipe per UE;
- 10 ms steps;
- 80000 shared bytes per step;
- a synthetic 512-byte cancellation tail.

Inspect the manifest:

```bash
jq . "$OUT_ROOT/mock/run-manifest.json"
```

Inspect session policy and summary:

```bash
jq '.sessions[] | {
  ue_id,
  behavior: .result.sessionRecord.player_behavior,
  termination: .result.terminationReason,
  requests: (.result.requests | length),
  summary: .result.sessionRecord.session_summary
}' "$OUT_ROOT/mock/run-result.json"
```

Inspect action counts:

```bash
jq '[
  .[] | .player_response.actions[]? | .op
] | group_by(.) | map({operation: .[0], count: length})' \
  "$OUT_ROOT/mock/network-step-transcript.json"
```

The first step must be at zero and the last one final:

```bash
jq '{
  first: {
    time_s: .[0].network_step.time_s,
    final: .[0].network_step.is_final
  },
  last: {
    time_s: .[-1].network_step.time_s,
    final: .[-1].network_step.is_final
  }
}' "$OUT_ROOT/mock/network-step-transcript.json"
```

## FikoRE TransportBackend

Use the same SFV JSON explicitly:

```bash
cd "$FIKORE_ROOT"
PYTHONPATH=transport python3 transport/benchmarks/validate_sfv.py \
  --sfv-vqeg-root "$SFV_VQEG_ROOT" \
  --sfv-core-root "$SFV_CORE_ROOT" \
  --config "$SFV_VQEG_ROOT/examples/network-backend-mock.json" \
  --output "$OUT_ROOT/fikore"
```

`validate_sfv.py` ignores the fixture's `network_backend: constant_rate_mock` selector and instantiates `TransportBackend -> FikoreLink -> FikoRE`. It reuses the player/session part of the fixture.

Inspect the run:

```bash
jq '{
  status,
  duration_s,
  network_steps,
  bytes_conserved,
  submitted_bytes,
  terminal_bytes,
  in_flight_bytes,
  max_events_per_reply,
  fikore_revision,
  sfv_vqeg_revision,
  sfv_core_revision
}' "$OUT_ROOT/fikore/run-manifest.json"
```

Verify conservation independently:

```bash
jq '{
  accounted:
    (.terminal_bytes.delivered
     + .terminal_bytes.dropped
     + .terminal_bytes.expired
     + .in_flight_bytes),
  submitted: .submitted_bytes,
  conserved:
    ((.terminal_bytes.delivered
      + .terminal_bytes.dropped
      + .terminal_bytes.expired
      + .in_flight_bytes)
     == .submitted_bytes)
}' "$OUT_ROOT/fikore/run-manifest.json"
```

Inspect the compact per-UE summaries:

```bash
jq '.sessions[] | {
  ue_id,
  player_behavior,
  termination_reason,
  request_count,
  request_states,
  abort_requests,
  bytes_delivered,
  bytes_data_wastage,
  bytes_unresolved_at_cutoff
}' "$OUT_ROOT/fikore/run-manifest.json"
```

## Short-Run Parity

For the pinned 0.2 s fixture, compare request IDs, sizes and final states:

```bash
diff -u \
  <(jq -S '[
    .sessions[] | {
      ue_id,
      requests: [
        .result.requests[] |
        {requestId, bytesTotal, state}
      ]
    }
  ]' "$OUT_ROOT/mock/run-result.json") \
  <(jq -S '[
    .sessions[] | {
      ue_id,
      requests: [
        .result.requests[] |
        {requestId, bytesTotal, state}
      ]
    }
  ]' "$OUT_ROOT/fikore/run-result.json")
```

An empty diff demonstrates that replacing the mock did not break the generic boundary or change the short fixture's decisions. Network progress, timestamps, RTT, loss and cancellation-tail timing are not expected to be identical. A previous pinned run differed by 261 wastage bytes for B2 at the cutoff while preserving request identity and delivered bytes.

## Longer Policy and Cancellation Checks

B1/B2 policy behaviour over 5 s:

```bash
cd "$FIKORE_ROOT"
PYTHONPATH=transport python3 transport/benchmarks/validate_sfv.py \
  --sfv-vqeg-root "$SFV_VQEG_ROOT" \
  --sfv-core-root "$SFV_CORE_ROOT" \
  --config "$SFV_VQEG_ROOT/examples/network-backend-mock.json" \
  --duration 5 \
  --output "$OUT_ROOT/fikore-5s"
```

Under the checked fixture, B1 requests no future-video media before the swipe; B2 preloads `v2/0`, `v2/1`, `v3/0` and `v3/1`.

Cancellation under a 1 Mbit/s per-UE cap:

```bash
PYTHONPATH=transport python3 transport/benchmarks/validate_sfv.py \
  --sfv-vqeg-root "$SFV_VQEG_ROOT" \
  --sfv-core-root "$SFV_CORE_ROOT" \
  --config "$SFV_VQEG_ROOT/examples/network-backend-mock.json" \
  --duration 1 \
  --rmax-mbps 1 \
  --output "$OUT_ROOT/fikore-cancel"
```

Every cancellation tail, `finalBytesDelivered - bytesDeliveredAtAbort`, must be non-negative. At a finite cutoff, terminal plus in-flight bytes must equal submitted bytes.

```bash
jq -s '[
  .[] | .requests[] |
  select(.abortRequestedAt != null) |
  {
    requestId,
    state,
    tail_bytes:
      ((.finalBytesDelivered // .bytesDelivered)
       - (.bytesDeliveredAtAbort // 0))
  }
] | {
  count: length,
  all_nonnegative: all(.tail_bytes >= 0),
  requests: .
}' "$OUT_ROOT"/fikore-cancel/ue-*-session.json
```

## Default FikoRE Configuration

The validator uses [`config/control_demo.ini`](../5g-network-emulator/config/control_demo.ini) as its base template. It generates a temporary INI with:

- fast barrier mode and a per-run Unix socket;
- one UE per SFV session;
- internal traffic targets disabled;
- 1500-byte packet/MSS alignment;
- 30 s PDCP delay budget;
- abort on timeout;
- 65536 retained object events;
- monitoring output disabled.

The remaining template scenario is 20 MHz at 3.5 GHz with proportional-fair scheduling and static UEs at 300 m. The backend uses CUBIC, 128 KiB rwnd, Not-ECT downlink, 1 ms internal TTIs and 10 ms `NetworkStep` windows.

## Acceptance

The integration passes when:

- all SFV core and bridge tests execute and pass;
- both runs start at `t=0` and reach a final step;
- FikoRE reports `status: completed` and `bytes_conserved: true`;
- the FikoRE integration manifest records the expected three repository revisions;
- the mock manifest records `status: completed`, `network_backend: constant_rate_mock` and the expected UE IDs;
- short-run request signatures match;
- longer B1/B2 and cancellation checks behave as documented;
- both external SFV worktrees remain clean.
