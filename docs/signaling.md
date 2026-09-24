# Signaling and Shared State

The signaling level governs what network information the player observes and whether the application sends playback state to a network controller. Signaling levels do not swap the underlying player engine or network backend.

## Signaling Levels

- **L0**: baseline without collaboration. The player estimates throughput solely from past segment downloads.
- **L1**: static subscription context. The player receives the provisioned subscriber downlink rate.
- **L2**: live network telemetry. The player receives real-time network measurements supplied by the network backend.
- **L3**: bidirectional collaboration. The player sends CAP telemetry reports to a network-side controller, which dynamically adjusts UE scheduling weights or rate limits via a controllable backend.
- **L4**: theoretical capacity oracle. The player receives a lookahead trace of future available capacity as an upper-bound reference.

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

Under FikoRE co-simulation, `rtt_ms` has no source: the emulator measures one-way latency. Either the field stays `None` or the experiment states the assumption used to derive a round trip from it, and records that assumption with the run.

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

CAP reports represent application telemetry and are managed separately from policy `Action` returns.

## Shared State Interface

```python
from typing import Protocol


class SharedStateTable(Protocol):
    def read_csp_fields(self, ue_id: int) -> CspFields | None: ...

    def write_csp_fields(self, ue_id: int, fields: CspFields) -> None: ...

    def read_cap_report(self, ue_id: int) -> CapReport | None: ...

    def write_cap_report(self, ue_id: int, report: CapReport) -> None: ...
```

The baseline implementation is an in-process Python data structure. It maintains current per-UE state and records all reads and updates to an append-only JSONL log (timestamp, UE ID, direction, field, and value).

The shared table enforces signaling-level filtering, exposing only permitted fields to the active player policy.

## Data Sources Across Modes

- **Offline co-simulation**: the FikoRE adapter maps simulation-time telemetry from socket reports into `CspFields`.
- **Emulated live mode**: a telemetry collector translates live FikoRE metrics into `CspFields`. The HTTP client supplies application-layer observations (e.g., request latency and application throughput).

All telemetry records use backend simulation or elapsed run time.

## L3 Network Controller Interface

The architecture reserves a `UeControl` structure for dynamic scheduling adjustments (scheduler priority and rate caps).

The network-side mechanism is specified: both parameters are written per UE at runtime through the [control protocol](fikore-cosim-messages.md#set), applied at a stated TTI and acknowledged with the exact instant of application. SINR offset, mobility, background traffic rate and the delay budget are in the same knob catalogue, so the controller's action space is not limited by the interface. What this section still owes is the controller itself.

Specification of L3 requires defining:

- Input CAP telemetry fields evaluated by the controller
- Mapping function from CAP inputs to scheduler weights and rate limits
- Control loop evaluation interval and damping
- Persistence duration of control policies
- Compatibility guarantees between offline and emulated execution

L3 is excluded from milestone 1 pending controller design.

## L4 Capacity Oracle

Under L4, the player receives a piecewise-constant trace of future available capacity from the current timestamp forward.

For single-UE runs, this trace derives from an offline full-buffer FikoRE run matching channel, mobility, and background load seeds.

For multi-UE runs, future capacity depends on mutual scheduling competition among adaptive players. Multi-UE experiments must document whether L4 is evaluated as an exogenous upper bound or a demand-coupled oracle trace.
