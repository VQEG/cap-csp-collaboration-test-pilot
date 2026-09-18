# Player API

The player architecture decouples execution mechanics from adaptation heuristics. The player engine manages playback timers, buffer queues, user swipes, request lifecycles, and event timing. The adaptation policy decides which segments to download or cancel.

## Policy Contract

The adaptation policy is a pure, deterministic function mapping an `Observation` to an `Action`. It does not access system timers, open network sockets, or communicate directly with backends.

```python
from dataclasses import dataclass
from typing import Literal, Protocol

SignalingLevel = Literal["L0", "L1", "L2", "L3", "L4"]


@dataclass(frozen=True)
class SegmentDescriptor:
    video_id: str
    segment_index: int
    duration_s: float
    bytes_by_quality: dict[str, int]


@dataclass(frozen=True)
class VideoState:
    video_id: str
    playhead_s: float
    playable_buffer_s: float
    is_stalled: bool
    segments: list[SegmentDescriptor]


@dataclass(frozen=True)
class RequestState:
    request_id: str
    video_id: str
    segment_index: int
    quality_id: str
    bytes_total: int
    bytes_delivered: int
    requested_at_s: float
    first_byte_at_s: float | None


@dataclass(frozen=True)
class DownloadHistory:
    request_id: str
    video_id: str
    segment_index: int
    quality_id: str
    bytes_total: int
    requested_at_s: float
    first_byte_at_s: float
    completed_at_s: float


@dataclass(frozen=True)
class CspFields:
    updated_at_s: float
    plan_downlink_mbps: float | None
    achieved_throughput_mbps: float | None
    rtt_ms: float | None
    loss_rate: float | None
    congestion_rate: float | None


@dataclass(frozen=True)
class CapacityPoint:
    start_s: float
    capacity_mbps: float


@dataclass(frozen=True)
class CapacityTrace:
    points: list[CapacityPoint]


@dataclass(frozen=True)
class Observation:
    session_time_s: float
    current_video: VideoState
    upcoming_videos: list[VideoState]
    active_requests: list[RequestState]
    download_history: list[DownloadHistory]
    swipe_history_s: list[float]
    csp_fields: CspFields | None
    oracle_capacity_trace: CapacityTrace | None


@dataclass(frozen=True)
class SegmentRequest:
    video_id: str
    segment_index: int
    quality_id: str


@dataclass(frozen=True)
class Action:
    segment_requests: list[SegmentRequest]
    cancel_request_ids: list[str]


class Policy(Protocol):
    def decide(self, observation: Observation) -> Action: ...
```

The harness exports versioned JSON schemas for `Observation` and `Action`, allowing external implementations (e.g., JavaScript, Kotlin, or C++) to interface with the harness.

Michi had some initial ideas on what other information to add here, e.g. regarding previous swipes (user behavior).

## Decision Triggers

The player engine evaluates policy decisions when the following events occur:

- Session start or transition to a new video
- User swipe or playback completion of current video
- Segment download completion or cancellation
- Playback stall start or recovery
- Arrival of updated CSP telemetry

The policy is not evaluated on raw clock ticks. If multiple events occur within a single simulation step, the engine applies all state updates and invokes the policy once.

## Action Validation

The engine validates policy actions before forwarding them to the network backend:

- Requested videos, segments, and quality levels must exist in the observation.
- The engine assigns unique request IDs and retrieves `bytes_total` from the content registry.
- Completed segments cannot be requested again.
- At most one active request is allowed per segment.
- Quality upgrades or downgrades cancel existing requests before initiating replacements.
- Cancellations execute before new requests in the same action batch.
- Active and completed preloaded segments count against the prefetch budget.

Malformed actions halt the simulation with a validation error rather than silently modifying inputs.

## Concurrency and Multi-Video Requests

A single action can emit multiple segment requests across different upcoming videos. Requests transfer concurrently over the network backend. Object completion order is not guaranteed to match request order.

## Swipes and Buffer Invalidation

When a user swipes, the engine switches active video context immediately:

1. Active requests for the abandoned video are cancelled in the current simulation step.
2. Active requests for subsequent upcoming videos remain active.
3. Delivered bytes for the abandoned video that were never played are logged as application waste.
4. The engine invokes the policy to schedule downloads for the newly active video.

## Prefetching Terminology

- `segments_per_video` (SPV): total number of segments composing a single video (e.g., a 15 s video with 5 s segments has SPV = 3).
- `max_preload_segments` (MPS): aggregate segment budget allowed for preloading ahead of the playhead across all upcoming videos.
- `preload_segments_per_video` (PSPV): segment download limit per future video before advancing to the next queued video.

For example, `MPS = 6` with `PSPV = 3` preloads three segments each for the next two videos. `MPS = 6` with `PSPV = 1` preloads the initial segment for each of the next six videos.

## Baseline Policies

- **B1 (Current video only)**: downloads segments only for the active video and issues no prefetch requests.
- **B2 (Multi-video prefetch)**: distributes download requests across active and upcoming videos up to configured MPS and PSPV limits.

Signaling levels provide additional telemetry fields to policies. A policy that ignores CSP telemetry operates as an L0 baseline under all configurations.

## Multi-Video dash.js Integration

The live HTTP validator should then port validated Python heuristics to dash.js. The implementation coordinates multiple `MediaPlayer` instances under a centralized short-form controller responsible for feed queues, user swipes, cross-video prefetching, and cancellation. Real requests route through FikoRE in emulation mode to an HTTP origin server.

Michi has initial ideas on this, which involve a wrapper around dash.js that would control its manifest and segment (pre)fetching behavior.
