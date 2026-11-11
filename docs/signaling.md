# Signaling and Shared State

The signaling level governs what network information the CAP may receive on the collaboration IPC path and whether CAP reports are visible to a network-side `CSPController`. Signaling levels do not swap the underlying player engine or network backend.

In the current harness, filtered CSP fields are **written** to the shared table from backend telemetry, **read** back in Python, and sent to the player as `network_step.collaboration`. The SFV B1/B2 rules do not yet consume that payload for adaptation; see [Collaboration runtime](collaboration.md) and the [implementation plan](implementation-plan.md) for wiring versus policy work.

## Signaling Levels

Signaling levels define **what may be read** from the shared table (`read_csp_fields`, `read_cap_report`) and therefore what appears in `network_step.collaboration` or reaches a `CSPController`. The harness **always writes** CSP and CAP updates to the table and **`shared-state.jsonl`**; filtering applies on read.

- **L0**: no CSP fields exposed to the CAP (`collaboration.csp_by_ue` is empty). The player policy is expected to rely on download history only once L2/L1 policies are implemented in the SFV engine.
- **L1**: the CAP receives the provisioned subscriber downlink rate (`plan_downlink_mbps`) via `collaboration`.
- **L2**: the CAP receives live `CspFields` from the network backend via `collaboration`.
- **L3**: the CAP still receives CSP via `collaboration`; CAP reports are written to the table and may be read by a `CSPController`, which may act on the CSP through `BackendControlAdapter` (dummy controller today logs proposals only).
- **L4**: the CAP receives a capacity oracle trace via `collaboration` (not implemented in the harness yet).

Player policy consumption and effective FikoRE control are tracked in the [implementation plan](implementation-plan.md).

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
- `achieved_throughput_mbps`: delivered downlink throughput over the preceding telemetry window. It represents measured delivery, not estimated spare capacity or maximum channel rate.

Field mappings from backend telemetry to `CspFields` are logged explicitly. For example, radio packet drop rate maps to `loss_rate` only when configured for that experiment.

Under FikoRE co-simulation, `rtt_ms` comes from the modelled transport's acknowledgement path. FikoRE's one-way PDCP latency remains a separate backend measurement and is not doubled to manufacture RTT.

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

The player engine generates CAP reports on state transitions: stall state changes, video switches, or buffer occupancy changes exceeding a configured threshold. Reports are rate-limited to at most one per second per UE by default.

In the pilot, the SFV engine uses a default buffer threshold of 1.0 s: a report is due when `playable_buffer_s` differs by at least 1.0 s from the last emitted report. The rate limit runs on the session clock. A transition that falls inside the rate-limit window is reported, with the state current at that time, once the window has passed. The report at the end of the run is exempt from the rate limit.

CAP reports represent application telemetry and are managed separately from policy `Action` returns.

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

The baseline implementation is an in-process Python data structure. It maintains current per-UE state and records all reads and updates to an append-only JSONL log (timestamp, UE ID, direction, field, and value).

**Writes** store the full measurement set; optional `extensions` (for example radio hints from FikoRE) appear in `shared-state.jsonl` but not in the narrow `CspFields` schema.

**Reads** apply signaling-level filters: only permitted fields are returned to callers. The harness uses `read_csp_fields` to build `collaboration.csp_by_ue` for the player process; at L3+, `read_cap_report` is used by `CSPController`. The CAP process does not read the table directly.

## Reference implementation

The pilot implements this interface in `capcsp/shared_state/`. `InMemorySharedStateTable` holds the latest `CspFields` and `CapReport` per UE and appends an audit row to **`shared-state.jsonl`** in the run output directory on each write. Each line is a JSON object with at least:

- `record_type`: `"write"` (reads are optional via `log_reads`)
- `direction`: `"csp_to_cap"` or `"cap_to_csp"`
- `ue_id`, `time_s`, `signaling_level`
- `payload`: `csp_fields` with optional `extensions` (extra telemetry keys for audit), or `cap_report` for CAP→CSP rows

The harness feeds the table from `NetworkTelemetryReceived` events (mapped to `CspFields`) and from the CAP reports returned by the **`cap_reports`** IPC message after each `NetworkStep` (an empty map when no report is due). The step-synchronized collaboration runtime lives in `capcsp/collaboration/`; see **[Collaboration runtime](collaboration.md)** for the full tick order, IPC `collaboration` field, and artifacts. Optional experiment key **`plan_downlink_mbps_by_ue`** (`dict`, UE id → Mbps) sets `plan_downlink_mbps` on `CspFields` for L1 experiments.

## CSPController (harness)

At signaling L3+, the harness may run a **`CSPController`** (experiment level L3, code name agnostic of backend). The pilot ships **`DummyCSPController`** with `csp_controller: "dummy"`: it reads `CapReport` from the shared table, logs a `CspControlIntent` proposal to **`csp-control.jsonl`**, and does not call `BackendControlAdapter.apply` (so FikoRE knobs stay unchanged). Real mapping from CAP telemetry to scheduler weights remains future work.

## Data Sources Across Modes

- **Offline co-simulation**: `TransportBackend` emits `NetworkTelemetryReceived` from transport measurements and FikoreLink's compact `events` state; the common harness maps those fields into `CspFields`.
- **Emulated live mode**: a telemetry collector translates live FikoRE metrics into `CspFields`. The HTTP client supplies application-layer observations (e.g., request latency and application throughput).

All telemetry records use backend simulation or elapsed run time.

## L3 Network Controller Interface

The architecture reserves a `UeControl` structure for dynamic scheduling adjustments (scheduler priority and rate caps). The harness applies control through **`FikoreControlAdapter`** (`CspControlIntent` → `UeControl` → `TransportBackend.set_ue_control`); see [Collaboration runtime](collaboration.md).

The network-side mechanism is specified: both parameters are written per UE at runtime through the [control protocol](fikore-cosim-messages.md#set), applied at a stated TTI and acknowledged with the exact instant of application. SINR offset, mobility, background traffic rate and the delay budget are in the same knob catalogue, so the controller's action space is not limited by the interface.

The **collaboration algorithm** for L3 still requires:

- Input CAP telemetry fields evaluated by the controller
- Mapping function from CAP inputs to scheduler weights and rate limits
- Control loop evaluation interval and damping
- Persistence duration of control policies
- Compatibility guarantees between offline and emulated execution

The pilot wires CAP reports, the shared table, and dummy `CSPController` output; the policy itself is not yet specified.

## L4 Capacity Oracle

Under L4, the player receives a piecewise-constant trace of future available capacity from the current timestamp forward.

For single-UE runs, this trace derives from an offline full-buffer FikoRE run matching channel, mobility, and background load seeds.

For multi-UE runs, future capacity depends on mutual scheduling competition among adaptive players. Multi-UE experiments must document whether L4 is evaluated as an exogenous upper bound or a demand-coupled oracle trace.
