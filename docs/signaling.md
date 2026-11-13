# Signaling and Shared State

The signaling level sets what network information the CAP may receive and whether a network-side `CSPController` may read CAP reports. It does not change the player engine or the network backend. How the harness moves the data is in [Collaboration Runtime](collaboration.md).

## Signaling Levels

The harness writes all CSP fields and CAP reports to the shared table at every level. The level filters what can be read back:

- **L0**: the CAP receives no CSP fields. The policy relies on its download history.
- **L1**: the CAP receives the provisioned downlink rate (`plan_downlink_mbps`).
- **L2**: the CAP receives all `CspFields`.
- **L3**: as L2. In addition, a `CSPController` may read CAP reports and act on the CSP.
- **L4**: the CAP receives a capacity oracle trace. The harness does not implement L4 yet.

The B1 and B2 policies do not use CSP fields yet, and no controller acts on the CSP yet. Both are tracked in [Decision Status and Action Items](decision-status-and-todos.md).

Unavailable measurements default to `None`. Backends must not fabricate synthetic values for missing metrics.

## CSP Telemetry Fields

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CspFields:
    updated_at_s: float
    plan_downlink_mbps: float | None
    achieved_throughput_mbps: float | None
    rtt_ms: float | None
    loss_rate: float | None
    congestion_rate: float | None
```

- `plan_downlink_mbps`: provisioned tariff rate from experiment configuration.
- `achieved_throughput_mbps`: delivered downlink throughput over the preceding telemetry interval. It represents measured delivery, not estimated spare capacity or maximum channel rate.

Field mappings from backend telemetry to `CspFields` are logged explicitly. For example, radio packet drop rate maps to `loss_rate` only when configured for that experiment.

Under FikoRE co-simulation, `rtt_ms` comes from the modelled transport's acknowledgement path. FikoRE's one-way PDCP latency remains a separate backend measurement and is not doubled to manufacture RTT.

`rtt_ms` is a transport measurement. A network operator does not see the end-to-end TCP round trip; the application's transport does. It is an open point whether `rtt_ms` should become a CAP field, with `CspFields` keeping only a network delay such as RAN or core delay.

The backend samples CSP telemetry every `csp_telemetry_interval_s` of simulation time (1 s by default, the same as the CAP report rate limit). Each sample covers the time since the previous one. The last sample of a run covers the remainder.

FikoRE additionally knows each UE's CQI, MCS, spectral efficiency and rank, which yield an achievable rate for that UE's current channel. That is neither measured throughput nor an oracle, and it is closer to what a real CSP could publish than either. It is a candidate additional L2 field, kept out of `CspFields` until an experiment needs it.

## CAP Telemetry Reports

```python
@dataclass(frozen=True)
class CapReport:
    time_s: float
    is_stalled: bool
    playable_buffer_s: float
    current_video_id: str
    swipe_rate_per_s: float
```

The SFV engine emits a CAP report when a stall starts or ends, when the current video changes, or when `playable_buffer_s` has moved by at least 1.0 s since the last report. Each UE sends at most one report per second of session time. A change inside that second is reported, with the state current at that time, once the second has passed. The report at the end of the run is exempt from the limit.

CAP reports are application telemetry. They are separate from the policy's `Action` returns.

## Shared State Interface

```python
from typing import Protocol


class SharedStateTable(Protocol):
    def read_csp_fields(self, ue_id: int) -> CspFields | None: ...

    def write_csp_fields(
        self, ue_id: int, fields: CspFields, *, extensions: dict | None = None
    ) -> None: ...

    def read_cap_report(self, ue_id: int) -> CapReport | None: ...

    def write_cap_report(self, ue_id: int, report: CapReport) -> None: ...
```

Writes store the full payload. Optional `extensions`, such as radio hints from FikoRE, go to the log but not into `CspFields`. Reads return only the fields the signaling level permits. Only the Python harness uses the table; the CAP process does not read it.

## Reference Implementation

`InMemorySharedStateTable` in `capcsp/shared_state/` holds the latest `CspFields` and `CapReport` per UE. It appends a row to `shared-state.jsonl` each time a UE's stored CSP fields or CAP report change. Each row is a JSON object with at least:

- `record_type`: `"write"`, or `"read"` when `log_reads` is on
- `direction`: `"csp_to_cap"` or `"cap_to_csp"`
- `ue_id`, `time_s`, `signaling_level`
- `payload`: `csp_fields` with optional `extensions`, or `cap_report`

## Data Sources Across Modes

- **Offline co-simulation**: the backend's CSP telemetry source samples the link beside the byte path, as described in the [Network Backend API](network-backend-api.md). The harness maps the samples to `CspFields`.
- **Emulated live mode**: a telemetry collector translates live FikoRE metrics into `CspFields`. The HTTP client supplies application-layer observations (e.g., request latency and application throughput).

All telemetry records use backend simulation or elapsed run time.

## L3 Network Controller Interface

At L3, a `CSPController` reads CAP reports from the table and may adjust scheduling per UE through a `UeControl` (scheduler priority and rate cap). `FikoreControlAdapter` maps a `CspControlIntent` to `TransportBackend.set_ue_control`. The pilot has only `DummyCSPController`, which logs its proposals to `csp-control.jsonl` and never applies them.

The network-side mechanism is specified: both parameters are written per UE at runtime through the [control protocol](fikore-cosim-messages.md#set), applied at a stated TTI and acknowledged with the exact instant of application. SINR offset, mobility, background traffic rate and the delay budget are in the same knob catalogue, so the controller's action space is not limited by the interface.

The **collaboration algorithm** for L3 still requires:

- Input CAP telemetry fields evaluated by the controller
- Mapping function from CAP inputs to scheduler weights and rate limits
- Control loop evaluation interval and damping
- Persistence duration of control policies
- Compatibility guarantees between offline and emulated execution


## L4 Capacity Oracle

Under L4, the player receives a piecewise-constant trace of future available capacity from the current timestamp forward.

For single-UE runs, this trace derives from an offline full-buffer FikoRE run matching channel, mobility, and background load seeds.

For multi-UE runs, future capacity depends on mutual scheduling competition among adaptive players. Multi-UE experiments must document whether L4 is evaluated as an exogenous upper bound or a demand-coupled oracle trace.
