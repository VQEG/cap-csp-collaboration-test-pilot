# Network Backend API

The network backend abstracts network dynamics from player logic. It accepts opaque byte requests and returns timestamped delivery events.

## Interface Definition

```python
from dataclasses import dataclass
from typing import Protocol, TypeAlias


@dataclass(frozen=True)
class DownloadProgress:
    ue_id: int
    request_id: str
    bytes_delivered: int
    time_s: float


@dataclass(frozen=True)
class DownloadCompleted:
    ue_id: int
    request_id: str
    time_s: float


@dataclass(frozen=True)
class DownloadCancelled:
    ue_id: int
    request_id: str
    bytes_delivered: int
    time_s: float


@dataclass(frozen=True)
class NetworkTelemetry:
    throughput_mbps: float | None
    rtt_ms: float | None
    ip_latency_ms: float | None
    pdcp_latency_ms: float | None
    ce_rate: float | None
    drop_rate: float | None
    retransmitted_bytes: int | None
    sinr_db: float | None
    queue_bytes: int | None


@dataclass(frozen=True)
class NetworkTelemetryReceived:
    ue_id: int
    time_s: float
    fields: NetworkTelemetry


NetworkEvent: TypeAlias = (
    DownloadProgress
    | DownloadCompleted
    | DownloadCancelled
    | NetworkTelemetryReceived
)


@dataclass(frozen=True)
class NetworkStep:
    time_s: float
    events: list[NetworkEvent]
    is_final: bool


class NetworkBackend(Protocol):
    def submit_request(
        self, ue_id: int, request_id: str, bytes_total: int
    ) -> None: ...

    def cancel_request(self, ue_id: int, request_id: str) -> None: ...

    def advance(self) -> NetworkStep: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class UeControl:
    priority: float | None = None
    rmax_mbps: float | None = None


class ControllableNetworkBackend(NetworkBackend, Protocol):
    def set_ue_control(self, ue_id: int, control: UeControl) -> None: ...
```

`NetworkEvent` is an internal Python union. Each backend creates these events from its native telemetry: the FikoRE adapter translates wire reports, HTTP workers wrap measured socket reads, and synthetic backends compute numerical progress.

`ControllableNetworkBackend` reserves the L3 control interface. Baseline levels L0, L1, L2, and L4 do not require it. For the FikoRE adapter it maps straight onto the control protocol: `priority` becomes an absolute scheduler priority that replaces the configured value, and `rmax_mbps` a token-bucket cap where `0` removes the cap and `None` leaves it unchanged.

`rtt_ms` stays `None` under FikoRE co-simulation: the emulator measures one-way latency, and doubling it would fabricate a value the backend did not observe.

## Common Semantics

All backends implement these contracts:

- Time starts at `0.0` and advances monotonically.
- Event timestamps are less than or equal to `NetworkStep.time_s`.
- Delivered byte counters are cumulative from request initiation.
- Request IDs are unique per UE and never reused within a run.
- A request completes only after all `bytes_total` bytes arrive.
- Multiple requests per UE can transfer concurrently.
- Submission order does not determine completion order.
- Cancelling an unknown or completed request is a no-op.
- `close()` is idempotent and frees worker threads, sockets, and subprocesses.

The player engine maintains the request registry, mapping opaque request IDs to video, segment, quality, duration, codec, resolution, and attempt index. The backend receives only `ue_id`, `request_id`, and `bytes_total`.

## Cancellation and Waste Accounting

Cancelling an in-flight request stops packet generation for that object. Packets already queued in the network pipeline continue to deliver or drop. The request remains active until this in-flight tail drains, emitting a single `DownloadCancelled` event with the final cumulative delivered bytes.

Bytes delivered to the application but never displayed count as application waste. Retransmitted or dropped packets count as network-layer overhead and are tracked separately.

In real HTTP runs, the client measures bytes delivered to the application layer before terminating the stream. Because post-close radio bytes cannot be attributed without lower-layer packet tracing, HTTP cancellation waste represents a lower bound.

## Backend Implementations

- `ConstantRateBackend`: allocates a fixed bandwidth per UE, distributed across active requests via deterministic round-robin scheduling.
- `TraceBackend`: replays recorded available bitrates over logical time. Time advances continuously even when the player is idle.
- `FikoreCosimBackend`: synchronizes requests and telemetry with the FikoRE adapter over a Unix socket, using FikoRE as the master clock.
- `HttpBackend`: issues HTTP requests through FikoRE in real-time emulation, recording actual application-level byte deliveries.

`HttpBackend` defines an interface contract. The reference validator implements the client inside the extended multi-video dash.js player, bridging request events and telemetry back to the harness.

## Latency Decomposition

The architecture separates three latency components:

- **Application and origin latency**: duration between request decision and initial byte generation at the server.
- **Core-network latency**: transport delay outside the radio access network.
- **Radio latency**: queueing delay, MAC scheduling, radio transmission, and HARQ retransmissions in FikoRE.

Constant-rate and trace backends inject configured non-radio delay directly. The FikoRE co-simulation adapter delays submitting requests to FikoRE until `ready_at_s = requested_at_s + synthetic_delay_ms / 1000`. FikoRE then simulates radio latency only. Effective delay is recorded alongside request logs. The real-HTTP backend measures live end-to-end network latency directly.

## Real-HTTP Validation Architecture

The live validation path executes end-to-end:

```text
dash.js in UE network namespace
  -> HTTP requests through client-side FikoRE virtual interface
  -> FikoRE real-time emulated radio channel
  -> Server-side FikoRE virtual interface
  -> HTTP origin server
```

The origin serves segment payloads matching byte sizes from `content.yaml` (using synthetic payloads or real encoded media). FikoRE schedules, shapes, delays, and drops packets in real time.

Once algorithms are proven in Python, the multi-video dash.js player (to be developed!) runs this pipeline, providing empirical validation of TCP slow start, connection reuse, and transport multiplexing against offline simulation models.
