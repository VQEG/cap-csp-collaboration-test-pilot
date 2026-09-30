# Network Backend API

The network backend abstracts network dynamics from player logic. It accepts opaque byte requests and returns timestamped delivery events.

## Interface Definition

The Python reference for these types is [`transport/fikore_transport/backend.py`](../5g-network-emulator/transport/fikore_transport/backend.py) in the FikoRE submodule.

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
    throughput_mbps: float | None = None
    rtt_ms: float | None = None
    ip_latency_ms: float | None = None
    pdcp_latency_ms: float | None = None
    ce_rate: float | None = None
    drop_rate: float | None = None
    retransmitted_bytes: int | None = None
    sinr_db: float | None = None
    queue_bytes: int | None = None


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

`NetworkEvent` is an internal Python union. Each backend creates these events from its native telemetry: `TransportBackend` builds them from `FikoreLink` feedback, HTTP workers wrap measured socket reads, and synthetic backends compute numerical progress.

`ControllableNetworkBackend` reserves the L3 control interface. Baseline levels L0, L1, L2, and L4 do not require it. For `TransportBackend` over FikoRE it maps straight onto the control protocol: `priority` becomes an absolute scheduler priority that replaces the configured value, and `rmax_mbps` a token-bucket cap where `0` removes the cap and `None` leaves it unchanged.

Under FikoRE co-simulation, `rtt_ms` is measured by the modelled transport's acknowledgement path. It is not obtained by doubling FikoRE's one-way `pdcp_latency_ms`; both measurements remain separate.

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

Each backend has a fixed name. Experiment configurations select the backend by this name, and session records store it in `network_backend`:

- `mock`: `MockNetworkBackend`, a deterministic shared byte budget for contract tests, adapted from the SFV-VQEG v0.7.2 repository. It never produces research results.
- `constant_rate`: `ConstantRateBackend`, still to be implemented.
- `trace`: `TraceBackend`, still to be implemented.
- `transport_fikore`: `TransportBackend` from the FikoRE submodule over `FikoreLink`. The same class over the deterministic `LoopbackLink` is used only in tests.
- `http`: `HttpBackend`, which issues HTTP requests through FikoRE in real-time emulation and records the bytes actually delivered to the application.

`HttpBackend` defines an interface contract. The reference validator implements the client inside the extended multi-video dash.js player, bridging request events and telemetry back to the harness.

## Transport Models

Implemented: `TransportBackend` implements `NetworkBackend` on top of a Link that accepts segments at a TTI and returns terminal arrivals by a TTI. The transport model and Link are independent axes:

- TCP controllers: Reno, CUBIC and externally bound Prague.
- Diagnostic transport: ideal fixed window with immediate outcome recovery.
- Links: `FikoreLink` and deterministic `LoopbackLink`.
- Runner-level traffic: open-loop UDP, not currently exposed through `TransportBackend`.

The implementation lives under [`5g-network-emulator/transport/`](../5g-network-emulator/transport/). TCP uses an HTTP/1.1-style persistent pool by default: sequential objects reuse idle per-UE connections and keep their cwnd and RTT state, while concurrent objects open additional connections. `tcp_connection_mode="fresh"` keeps the one-flow-per-object baseline, and `max_idle_tcp_connections_per_ue` bounds the idle pool. Cancellation retires only the affected connection after its accounting tail drains.

Current limitations include no HTTP/2-style multiplexing on one connection and no modelled handshake, FIN, Nagle, window scaling, PRR or RACK/TLP. See the submodule's [`LIMITATIONS.md`](../5g-network-emulator/transport/docs/LIMITATIONS.md).

## Latency Decomposition

The architecture separates three latency components:

- **Application and origin latency**: duration between request decision and initial byte generation at the server.
- **Core-network latency**: transport delay outside the radio access network.
- **Radio latency**: queueing delay, MAC scheduling, radio transmission, and HARQ retransmissions in FikoRE.

Constant-rate and trace backends will inject configured non-radio delay directly. The planned common harness may hold an object until `ready_at_s = requested_at_s + synthetic_delay_ms / 1000` before submitting it to `TransportBackend`. The current SFV/FikoRE validator does not add this synthetic hold; FikoRE applies the template's configured backhaul and radio latency. The real-HTTP backend measures live end-to-end latency directly.

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

The multi-video dash.js player runs this pipeline, providing empirical validation of TCP slow start, connection reuse, and transport multiplexing against offline simulation models.
