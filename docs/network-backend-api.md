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

The player process never calls `set_ue_control`. At L3 and above, a `CSPController` in the harness may call it through `FikoreControlAdapter`; see [Collaboration Runtime](collaboration.md).

`NetworkEvent` is an internal Python union. Each backend creates these events from its native feedback: `TransportBackend` builds them from `FikoreLink` arrivals, HTTP workers wrap measured socket reads, and synthetic backends compute numerical progress.

`NetworkTelemetryReceived` is the sample type of a backend's CSP telemetry. It never appears in a `NetworkStep`; the harness rejects a step that contains one. A backend exposes its telemetry beside the byte path, as an optional `csp_telemetry` attribute:

```python
class CspTelemetrySource(Protocol):
    def poll(self, *, force: bool = False) -> list[NetworkTelemetryReceived]: ...
```

The harness calls `poll()` after every `advance()` and `poll(force=True)` after the final one. The source returns the samples due at the current backend time and nothing otherwise. `TransportFikoreBackend` uses FikoRE's `NetworkTelemetrySampler`, which reads cumulative per-UE counters from the link (`FikoreLink` state snapshots or the loopback queue) every `csp_telemetry_interval_s` (1 s by default) and takes RTT and retransmitted bytes from the transport. A backend without a source, such as `mock` or `constant_rate`, writes no CSP telemetry.

`ControllableNetworkBackend` reserves the L3 control interface. Baseline levels L0, L1, L2, and L4 do not require it. For `TransportBackend` over FikoRE it maps straight onto the control protocol: `priority` becomes an absolute scheduler priority that replaces the configured value, and `rmax_mbps` a token-bucket cap where `0` removes the cap and `None` leaves it unchanged. `ConstantRateBackend` uses the same `rmax_mbps` semantics as a cap on the UE's configured rate, and records `priority` without effect, because its UEs do not share capacity.

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
- `constant_rate`: `ConstantRateBackend`, a deterministic dedicated rate per UE, described below.
- `trace`: `TraceBackend`, still to be implemented.
- `transport_fikore`: `TransportBackend` from the FikoRE submodule over `FikoreLink`. The same class over the deterministic `LoopbackLink` is used only in tests.
- `http`: `HttpBackend`, which issues HTTP requests through FikoRE in real-time emulation and records the bytes actually delivered to the application.

`HttpBackend` defines an interface contract. The reference validator implements the client inside the extended multi-video dash.js player, bridging request events and telemetry back to the harness.

### Constant-Rate Backend

`ConstantRateBackend` (`capcsp/network/constant_rate.py`) gives every UE its own constant downlink rate, so UEs never compete for capacity. It is the network model of the analytical results of Wehner et al., which assume a constant bandwidth per user, and a fast, predictable network for prototyping player and L1 to L3 policies. It follows the per-UE behaviour of `SFVConstantRateTransport` in the SFV reference implementation, but in `NetworkStep` lockstep. It is not a TCP, HTTP or radio model: there is no slow start, no loss and no queue.

- **Clock**: a deterministic logical clock. After the initial step at `t = 0.0`, every step advances by `step_s`; the last step ends exactly at the run duration.
- **Sharing**: the requests of a UE that are ready share its rate equally. Within a step, the backend splits time at every instant where a request becomes ready or reaches its byte limit, so a request that finishes early hands its share to the others (processor sharing).
- **Delay**: a request receives no bytes before `requested_at_s + synthetic_delay_ms / 1000`, where `requested_at_s` is the backend time at which it was submitted.
- **Exact byte accounting**: delivered bytes are kept as exact fractions, so a UE that always has a ready request receives exactly rate × time over any run length. Events report whole bytes, rounded down; the fraction carries over to the next step. 1,000,000 bytes at 8 Mbps take exactly 1 s after the delay.
- **Event times**: all events carry the time of the step in which they happen, as on the other backends, even when a request completes inside the step. The player issues follow-up requests at event times, and the backend can only receive them at the step time.
- **Cancellation**: a cancelled request still receives up to `cancellation_tail_bytes` beyond the bytes reported so far, at its share of the rate, then ends with a single `DownloadCancelled`. A request cancelled while still within its synthetic delay ends with 0 bytes in the next step.
- **Control**: `set_ue_control` caps the UE rate at `rmax_mbps` from the next step on (`0` removes the cap, `None` leaves it unchanged). `priority` is recorded but has no effect.

Unknown UEs, duplicate request IDs per UE, non-positive sizes, submissions after the final step or after `close()`, and steps after the final step or after `close()` raise errors, as on `mock`. The configuration keys are listed in [Experiments and Configuration](experiments.md#constant-rate-backend).

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

The constant-rate backend injects the configured non-radio delay directly: it holds back the first byte of every request by `synthetic_delay_ms`. The trace backend will do the same. The planned common harness may hold an object until `ready_at_s = requested_at_s + synthetic_delay_ms / 1000` before submitting it to `TransportBackend`. The current SFV/FikoRE validator does not add this synthetic hold; FikoRE applies the template's configured backhaul and radio latency. The real-HTTP backend measures live end-to-end latency directly.

## Real-HTTP Validation Architecture

The live validation path executes end-to-end:

```text
dash.js in UE network namespace
  -> HTTP requests through client-side FikoRE virtual interface
  -> FikoRE real-time emulated radio channel
  -> Server-side FikoRE virtual interface
  -> HTTP origin server
```

The origin serves segment payloads matching byte sizes from the content file (using synthetic payloads or real encoded media). FikoRE schedules, shapes, delays, and drops packets in real time.

The multi-video dash.js player runs this pipeline, providing empirical validation of TCP slow start, connection reuse, and transport multiplexing against offline simulation models.
