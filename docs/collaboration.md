# Collaboration Runtime

This page describes how the harness moves CAP–CSP collaboration data on the simulation clock. Field definitions, signaling levels and read filters are in [Signaling and Shared State](signaling.md).

The harness keeps byte delivery and collaboration state apart. A `NetworkStep` carries download events only. CSP telemetry and CAP reports go through the shared state table, which only the Python harness reads and writes. The SFV player process does not touch the table. It receives a filtered CSP snapshot with each `network_step` and returns its pending CAP reports when asked.

In this page, the CAP is the SFV player process and the CSP is the network backend (`mock`, `constant_rate` or `transport_fikore`).

## One Step

The harness runs this tick after each `NetworkBackend.advance()`. The [architecture](architecture.md#one-step) shows the same sequence as a diagram.

1. Validate the step's download events.
2. Poll the backend's CSP telemetry source. A sample is due every `csp_telemetry_interval_s` (1 s by default), and once more on the final step to close the last interval. Each sample is mapped to `CspFields`, written to the table and appended to `telemetry.jsonl`.
3. Build the `collaboration` snapshot from `read_csp_fields`, which applies the signaling filter.
4. Send the step with the snapshot to the player. The player passes the CSP fields of each UE to its SFV controller when they change. B1 and B2 do not use them in decisions yet.
5. Send `cap_reports` and write each returned report to the table. The player returns a report for a UE only when one is due, so the reply is often empty.
6. At L3 and above with `csp_controller: "dummy"`, log control proposals to `csp-control.jsonl`. The dummy controller never applies them.
7. If the step is not final, apply the player's submit and cancel actions to the backend.

Steps 2 to 6 run in `run_collaboration_tick` (`capcsp/collaboration/runtime.py`). Step 7 runs in `bridge.run_sessions`, before the next `advance()`.

## The `collaboration` Snapshot

The harness adds this object to the step it sends to the player. It is not part of the [Network Backend API](network-backend-api.md).

```json
{
  "time_s": 1.0,
  "events": [],
  "is_final": false,
  "collaboration": {
    "signaling_level": "L2",
    "csp_by_ue": {
      "0": {
        "updated_at_s": 1.0,
        "plan_downlink_mbps": null,
        "achieved_throughput_mbps": 1.2,
        "rtt_ms": 30.0,
        "loss_rate": 0.0,
        "congestion_rate": null
      }
    }
  }
}
```

At L0, `csp_by_ue` is empty. The messages between the harness and the player are described in the SFV [co-simulation docs](../sfv-reference-implementation/docs/CO_SIMULATION.md).

## Components

| Component | Location | Role |
|-----------|----------|------|
| `InMemorySharedStateTable` | `capcsp/shared_state/` | Latest `CspFields` and `CapReport` per UE, read filters, `shared-state.jsonl` |
| `run_collaboration_tick` | `capcsp/collaboration/runtime.py` | Steps 2 to 6 of the tick |
| `CspTelemetryWriter` | `capcsp/collaboration/telemetry.py` | Polls the backend's `csp_telemetry` source and writes the samples. Backends without a source use `NoCspTelemetry` |
| `build_collaboration_payload` | `capcsp/collaboration/snapshot.py` | Filtered CSP snapshot for the player |
| `SfVCapReporter` | `capcsp/collaboration/cap_reporter.py` | Writes the player's CAP reports to the table |
| `DummyCSPController` | `capcsp/collaboration/csp_controller.py` | Reads CAP reports at L3 and above and logs proposals |
| `FikoreControlAdapter` | `capcsp/collaboration/adapters/fikore_control.py` | Maps a `CspControlIntent` to `set_ue_control` on `transport_fikore` and `constant_rate`. No controller calls it yet |
| `NoOpControlAdapter` | `capcsp/collaboration/adapters/noop_control.py` | Control adapter for `mock` |
| `SFVNetworkStepHarness` | `sfv-reference-implementation/src/cosim/` | Runs the SFV sessions, applies CSP snapshots and drains CAP reports |

`TransportFikoreBackend` exposes FikoRE's `NetworkTelemetrySampler` as its `csp_telemetry` source. `capcsp/collaboration/adapters/fikore_mapper.py` maps its samples to `CspFields`.

## Output Files

- `shared-state.jsonl`: every run. One row each time a UE's CSP fields or CAP report change. The row format is in [Signaling and Shared State](signaling.md#reference-implementation).
- `telemetry.jsonl`: one row per UE and CSP telemetry sample. It is empty on `mock` and `constant_rate`.
- `network-steps.jsonl`: the steps sent to the player, with download events and the `collaboration` snapshot.
- `csp-control.jsonl`: only at L3 and above with `csp_controller: "dummy"`.

Each `csp-control.jsonl` row has:

- `record_type`: `"control_proposal"`
- `time_s`, `ue_id`, `signaling_level`
- `baseline` and `proposed`, each with `priority` and `max_downlink_mbps`
- `applied`: always `false` for the dummy controller
- `reason`, for example `dummy_stall_boost` or `dummy_no_change`

The run manifest names the two log files (`shared_state_log`, `csp_control_log`, or `null`) and records `clock_mode` and `cap_application` (`"sfv"`).

## Configuration

| Key | Default | Meaning |
|-----|---------|---------|
| `signaling_level` | `L0` | Signaling level, see [Signaling and Shared State](signaling.md) |
| `plan_downlink_mbps_by_ue` | omitted | Plan rate per UE ID. From L1, it is in the table from t = 0 |
| `csp_controller` | omitted | `"dummy"` runs `DummyCSPController` at L3 and above |
| `csp_baseline_control_by_ue` | omitted | Baseline `priority` and `max_downlink_mbps` for the proposal log |
| `clock_mode` | `"simulation"` | The only implemented mode |

The `transport_fikore` network settings set `csp_telemetry_interval_s`. An example L3 configuration is [`configs/experiments/collaboration/l3-dummy-mock.json`](../configs/experiments/collaboration/l3-dummy-mock.json).

## Extending the Design

- Another CSP, such as netem: a new `NetworkBackend` with a `csp_telemetry` source and a `BackendControlAdapter`. The table API stays the same.
- Another CAP, such as WebRTC: a new CAP reporter that writes `CapReport` rows to the same table.
- SFV policies that use CSP fields: a change in the SFV rules only. The fields already reach the controller through `applyCspUpdate`.
- Effective FikoRE control: a `CSPController` that calls `FikoreControlAdapter.apply`.
- A wall-clock runtime: a new driver that keeps `time_s` and the row formats.
