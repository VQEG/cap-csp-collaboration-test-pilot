# Experiments and Configuration

An experiment configuration defines the player policy, signaling level, network condition, swipe model, media content, and random seed. The runner expands configuration grids into cell runs and records the realized parameters alongside output metrics.

## Reproducibility

Offline runs are deterministic functions of configuration, input files, code version, and seed. They do not query the system wall clock.

The runner derives independent pseudo-random streams from the primary seed for:

- Radio and channel fading
- Mobility and background traffic
- Video feed and content order
- User swipe timing

Paired comparisons across signaling levels share identical random seeds to isolate information exchange from network or user variance.

## Cell Runs

A cell run models all video UEs competing within a shared network instance. Milestone 1 assumes four homogeneous video UEs per cell with matching player policies, signaling levels, and swipe profiles. Mixed-policy cells are deferred to later milestones.

The runner initializes one session per UE and one shared network backend. Cell-level aggregations are computed once all session records complete.

## Network Conditions

Conditions use descriptive identifiers mapped to backend-specific parameters.

The values below illustrate the configuration shape. The final SFV-specific C1-C5 profiles are pending and tracked in [Decision Status and Action Items](decision-status-and-todos.md#media-content-and-network-conditions).

```yaml
conditions:
  C1:
    name: healthy-5g
    as_seen_by_application:
      downlink_mbps: 60
      rtt_ms: 25
      loss_percent: 0
    synthetic_delay_ms: 25
    fikore:
      base_ini: offline_uma_n78_pedestrian.ini
      video_ues:
        count: 4
        mobility: static
        priority: 4
      background_ues:
        count: 0
      sender_max_bytes_in_flight: 131072
    trace:
      file_pattern: traces/C1_fullbuffer_seed{seed}.txt

  C4:
    name: congested-cell
    as_seen_by_application:
      downlink_mbps: 6
      rtt_ms: 60
      loss_percent: 1
    synthetic_delay_ms: 60
    fikore:
      base_ini: offline_uma_n78_pedestrian.ini
      video_ues:
        count: 4
        mobility: static
        priority: 4
      background_ues:
        count: 20
        downlink_target_mbps: 20
        priority: 1
      sender_max_bytes_in_flight: 131072
```

The runner automatically generates FikoRE `.ini` files from the base template and condition overrides without manual file editing.

`synthetic_delay_ms` configures round-trip delay in constant-rate, trace, and offline FikoRE adapter backends. The adapter holds outgoing requests until this delay elapses before releasing them to FikoRE. The real-HTTP backend observes live network latency and ignores this field.

## Content Registry

The content registry specifies exact byte sizes for every segment and quality representation, providing `bytes_total` for all network requests.

```yaml
videos:
  - video_id: v8
    codec: h264
    frame_rate: 30
    display_aspect_ratio: "9:16"
    segments:
      - segment_index: 0
        duration_s: 5.0
        qualities:
          q0: {width: 480, height: 854, bytes: 310000}
          q1: {width: 720, height: 1280, bytes: 610000}
          q2: {width: 1080, height: 1920, bytes: 940000}
```

Milestone 1 generates synthetic segment sizes based on target bitrates, segment durations, and seeded random variations, persisting the table before execution. Real video encodes can replace synthetic data without modifying player or backend APIs.

## Experiment Grid

```yaml
network_backend: fikore_cosim
sync_ms: 10
session:
  max_videos: 20
  max_duration_s: 300
grid:
  network_condition: [C1, C2, C3, C4, C5]
  signaling_level: [L0, L1, L2, L4]
  player_behavior: [simple, preload]
  swipe_profile: [slow, medium, fast]
  seed: {from: 1, to: 30}
content: content.yaml
```

Signaling level L3 is excluded until the network controller algorithm is specified.

## Trace Backend

The trace backend replays stepwise available bitrates over elapsed session time. Time advances continuously while the player is idle. Multi-UE runs require one independent rate trace per UE.

Traces follow the whitespace-delimited format `time_s bandwidth_mbps` (Mahimahi format). Trace replay is open loop and does not adjust capacity when players are idle. FikoRE offline simulation is used when dynamic demand-scheduler interactions are required.

## Configuration Validation

The runner validates configurations before spawning child processes:

- Durations, byte counts, bitrates, and sender windows must be positive.
- `sync_ms` must be a positive multiple of the FikoRE radio tick.
- Telemetry intervals must align with `sync_ms` boundaries.
- UE IDs must be unique across the cell.
- Every referenced video segment and quality level must exist in the content registry.
- Selected conditions must supply all required fields for the active backend.
- L3 configurations must specify a valid network controller.

Validation errors output the offending YAML path and halt execution immediately.

## Backend Comparisons

Condition labels unify parameter sets across backends without implying numerical trace identity:

- **Constant rate and traces**: fast unit tests, policy prototyping, and open-loop baselines.
- **FikoRE offline**: multi-UE closed-loop scheduling and L3 feedback evaluation.
- **Real HTTP via FikoRE**: end-to-end validation under kernel transport dynamics.

Every generated report records the backend, transport profile, synchronization interval, latency model, sender window, and random seed.
