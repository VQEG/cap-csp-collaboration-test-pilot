# Experiments and Configuration

An experiment configuration defines the player policy, signaling level, network condition, swipe model, media content, and random seed. The runner expands configuration grids into cell runs and records the realized parameters alongside output metrics.

## Reproducibility

Offline runs are deterministic functions of configuration, input files, code version, and seed. They do not query the system wall clock.

Repeating a FikoRE run gives identical session records, network steps and telemetry. `tests/test_runs.py` checks this for runs in separate Python processes with different hash seeds.

The runner derives independent pseudo-random streams from the primary seed for:

- Radio and channel fading
- Mobility and background traffic
- Video feed and content order
- User swipe timing

Paired comparisons across signaling levels share identical random seeds to isolate information exchange from network or user variance.

The first two streams live inside FikoRE and depend on the run seed specified in the [co-simulation design](fikore-cosim.md#seeds). Without it the emulator can be made repeatable or random, but not repeatable in thirty different ways, and the repeatable setting also switches off the traffic, backhaul-jitter and retransmission variances.

## Cell Runs

A cell run models all video UEs competing within a shared network instance. The UEs of a cell can use different player behaviours, as real users run different apps. All UEs of a cell share the signaling level. The number of UEs per cell is a grid axis.

The runner initializes one session per UE and one shared network backend. Cell-level aggregations are computed once all session records complete.

## Network Conditions

Conditions use descriptive identifiers mapped to backend-specific parameters.

On FikoRE (`network_backend: "transport_fikore"`), conditions are defined declaratively via `network.parametric_cell` (`capcsp/network/parametric_cell.py`) and documented in [`configs/experiments/layered/README.md`](../configs/experiments/layered/README.md). Each run deterministically synthesizes `fikore-effective.ini`, `fikore-timeline.ndjson` (Poisson `M/M/inf` or 2-state `mmpp` session arrivals/departures, spatial coordinates, and vehicular trajectories), and application-paced TCP Cubic competing UEs (`backgroundSfV`) strictly from `Global.seed` (`SHA-256("capcsp-parametric-cell::<seed>")`), without checking static `.ini` or `.ndjson` timeline files into git. Raw `.ini` scenarios remain supported via `network.fikore_base_ini` when needed for low-level emulator tests.

```json
{
  "network_backend": "transport_fikore",
  "network": {
    "congestion_control": "cubic",
    "receive_window_bytes": 262144,
    "tcp_connection_mode": "persistent",
    "max_idle_tcp_connections_per_ue": 6,
    "step_ms": 10,
    "study_ues": ["studyVqeg"],
    "ack_over_link": true,
    "delay_budget_s": null,
    "random_v": null,
    "parametric_cell": {
      "preset": "M04"
    },
    "fikore_section_overrides": {
      "Global": {"seed": 20260927}
    }
  }
}
```

Eleven presets (`M01`–`M11`, with `Core-6` = `M01`, `M04`, `M05`, `M07`, `M09`, `M10`) and `"preset": "custom"` share a single unconstrained Proportional Fair (`metric_type: 6`, no `rmax_mbps` caps) 3.5 GHz Urban Macro (`UMa` n78, `20 MHz` default, configurable `10`–`100 MHz`) cell with in-order PDCP delivery (`order_pkts: true`) and per-class FIFO backhaul delivery, varying four orthogonal axes:

- **Normalized competing cell load (`load_rho`)**: `0.0`–`2.0`, translated analytically from calibrated RB shares into active competing SFV-like TCP flows (`bg_bitrate_mbps`, `4.0 Mbps` by default).
- **Spatial geometry (`study_position`, `study_distance_m`, `bg_spatial`, `bg_max_distance_m`)**: study UE at `good` (`151.3 m`), `mid` (`350 m`), `edge` (`650 m`), or `custom` (`10`–`850 m`); competing UEs on a `homogeneous_ring` or uniform-area `cell_disk` (`120`–`700 m`).
- **Temporal arrivals (`arrival_mode`, `mean_hold_s`, `burst_amplitude`, `burst_regime_s`)**: stationary `poisson` (`M/M/inf`) or 2-state `mmpp` burst waves.
- **Study-UE mobility (`study_mobility`, `study_speed_kmh`, `traverse_min_distance_m`, `traverse_max_distance_m`)**: `static`, cell-edge `pedestrian` (`3.6 km/h`, study UE only), or `vehicular_traverse` (`73.26 km/h` radial center–edge–center traversal).

FikoRE imposes no transport window on injected traffic. TCP conditions record the congestion controller, receive window, MSS, ECN, ACK path and connection mode (`persistent` bounded HTTP/1.1-style pool per UE, `multiplexed` RFC 9218 single-connection stream multiplexing, or `fresh` per-object baseline with slow start on every request). The ideal diagnostic transport instead records its fixed shared per-UE window and recovery setting.

Since lockstep co-simulation owns FikoRE's Unix control socket, synthesized or custom control timelines are read by the harness and replayed at their exact TTIs through `FikoreLink`. Each run records the FikoRE revision and copies the rendered scenario to `fikore-effective.ini` (and `fikore-timeline.ndjson` when present).

On FikoRE, the `.ini` file also defines the delay: `backhaul_d` and `backhaul_d_var` set the backhaul and core-network delay (`backhaul_delay_ms` and `backhaul_jitter_ms` in `parametric_cell`), which adds to the queuing, propagation and HARQ delay of the RAN. There is no extra delay controlled by the runner. Note the following for the transport model:

- The backhaul delay applies to downlink data.
- With `ack_over_link: false`, ACKs return after a fixed 1 ms instead of crossing FikoRE. With `ack_over_link: true`, ACKs are sent over the FikoRE uplink and also receive the backhaul delay.
- The HTTP request is not modelled; an object enters the TCP sender directly.

With `control_demo.ini` (3 ms backhaul delay) and `ack_over_link: false`, the measured TCP RTT is about 6 to 7 ms without queuing. To reach a target RTT, set `backhaul_d` accordingly or enable `ack_over_link`.

`synthetic_delay_ms` applies only to the constant-rate and trace backends, which have no delay model of their own. FikoRE ignores it, and the real-HTTP backend observes live end-to-end latency instead.

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

The YAML above shows the fields only. The runner reads the SFV `content.json` format of the `sfv-reference-implementation` submodule. Two catalogues are currently checked in:

- `sfv-reference-implementation/fixtures/content/content.json`: three 6 s smoke-test videos (`180`–`650 kbps`).
- `configs/content/sfv-portrait-hd-90s.json`: a **provisional** synthetic 18-video (`8 s` each, `4 × 2 s` segments, 6-rung portrait Full HD `270×480`–`1080×1920` ladder at `300`–`8000 kbps`) catalogue used to sustain `65 s` multi-swipe runs without feed exhaustion while Michi's group finalizes the pilot catalogue; see [Decision Status and Action Items](decision-status-and-todos.md#player-and-video-definitions).

## Experiment Grid

A grid file expands into one experiment configuration per cell. `capcsp grid` runs the cells in parallel. Examples: `configs/grids/layered-core6.json`, `configs/grids/layered-m01-m11.json`, and `configs/grids/parametric-load-sweep.json`.

```json
{
  "grid_id": "layered-core6",
  "base": { "...": "inline base experiment" },
  "conditions": {
    "M01": {"condition": "M01", "network": {"parametric_cell": {"preset": "M01"}}},
    "M04": {"condition": "M04", "network": {"parametric_cell": {"preset": "M04"}}}
  },
  "signaling_levels": ["L0"],
  "ue_counts": [1],
  "behavior_mixes": {"b1": ["simple"], "b2": ["preload"]},
  "replications": 5,
  "network_seed_base": 20260927
}
```

The keys:

- `base`: a normal experiment configuration, as a path relative to the grid file or inline as an object. Every cell starts from it. The [simulator explorer](simulator-explorer/README.md) writes grid files with an inline base.
- `conditions`: named partial configurations. Each is merged over the base: objects merge key by key, other values replace. Without `conditions`, the grid uses the base condition.
- `signaling_levels`: the signaling levels. All UEs of a cell share one level.
- `ue_counts`: the number of video UEs per cell.
- `behavior_mixes`: named behaviour patterns. A pattern repeats over the UEs of a cell, so `["simple", "preload"]` gives B1, B2, B1, B2 for four UEs. Each behaviour takes its session settings from the first base session with that behaviour.
- `replications`: the number of replications. Replication r sets the FikoRE seed to `network_seed_base + r` and the seed of UE k to `1000 r + k`. Cells of the same replication therefore see the same radio and the same users, so they can be compared in pairs.

Each cell is named `<grid_id>-<condition>-<level>-<n>ue-<mix>-r<replication>`. The output directory, by default `output/grids/<grid_id>`, holds one directory per cell, `index.csv` and `kpis.csv`:

- `index.csv` lists every cell with its axis values, a hash of its configuration, its status and its wall-clock time.
- `kpis.csv` merges the KPI tables of all completed cells. It adds the UE count, the behaviour mix and the replication as leading columns.

A cell is finished when it completed with an unchanged configuration. A new invocation skips finished cells and runs failed or changed ones. With `--force`, it runs all cells again. A failed cell writes `error.log` and does not stop the others.

At L3, set `csp_controller: "dummy"` to exercise the collaboration bus without changing FikoRE (the dummy controller logs proposals only). Example: `configs/experiments/collaboration/l3-dummy-mock.json`. See [Collaboration runtime](collaboration.md).

Optional keys of an experiment configuration: `csp_baseline_control_by_ue`, `clock_mode` (`"simulation"` only), `plan_downlink_mbps_by_ue` (L1).

Swipes come from the SFV `userModel` of each session. The grid configurations in `configs/grids/layered-*.json` use the simple `seeded` model, which draws the time between swipes uniformly from `watchDurationRangeS` (2–16 s, the viewing times of the [swipe delay study](https://arxiv.org/abs/2603.18575)) with the session seed. That time runs from the previous swipe, so loading delays and stalls count towards it. Single-run and scripted examples keep fixed `swipeTimesS`. Without a `swipe_profile` key, the session records name the user model type, or `scripted`. Swipe profiles are not yet a grid axis.

## Constant-Rate Backend

The `constant_rate` backend gives every UE a dedicated constant downlink rate; see the [Network Backend API](network-backend-api.md#constant-rate-backend) for its behaviour. Its settings go into the `network` object of the experiment configuration:

```json
"network_backend": "constant_rate",
"network": {
  "step_s": 0.01,
  "downlink_rate_mbps": 1.0,
  "downlink_rate_mbps_by_ue": {"1": 4.0},
  "synthetic_delay_ms": 25,
  "cancellation_tail_bytes": 0
}
```

- `step_s`: length of one `NetworkStep` in seconds, 0.01 by default.
- `downlink_rate_mbps`: rate of every UE without an entry in `downlink_rate_mbps_by_ue`. It may be left out if every UE has one.
- `downlink_rate_mbps_by_ue`: optional rate per UE ID, overriding `downlink_rate_mbps`.
- `synthetic_delay_ms`: time from submitting a request to its first byte, 0 by default.
- `cancellation_tail_bytes`: bytes a request may still receive after its cancellation, 0 by default.

Rates are in Mbps of application payload (10^6 bit/s). `configs/experiments/b1-b2-two-ue-constant-rate.json` runs B1 and B2 at 1 Mbps each with a 25 ms delay:

```bash
uv run capcsp run configs/experiments/b1-b2-two-ue-constant-rate.json
```

## Trace Backend

The trace backend replays stepwise available bitrates over elapsed session time. Time advances continuously while the player is idle. Multi-UE runs require one independent rate trace per UE.

Traces follow the whitespace-delimited format `time_s bandwidth_mbps` (Mahimahi format). Trace replay is open loop and does not adjust capacity when players are idle. FikoRE offline simulation is used when dynamic demand-scheduler interactions are required.

## Configuration Validation

The runner validates configurations before spawning child processes:

- Durations, byte counts, bitrates, receive windows and MSS values must be positive.
- `sync_ms` must be a positive multiple of the FikoRE radio tick.
- Telemetry intervals must align with `sync_ms` boundaries.
- FikoRE conditions must select the proportional fair scheduler, or `priority` and any L3 control silently do nothing.
- Concurrent runs must get distinct socket paths, telemetry ports and working directories.
- UE IDs must be unique across the cell.
- Every referenced video segment and quality level must exist in the content registry.
- Selected conditions must supply all required fields for the active backend.
- At signaling L3+, `csp_controller` must be `"dummy"` (only supported value today) or omitted; other values are rejected.

Validation errors output the offending YAML path and halt execution immediately.

## Backend Comparisons

Condition labels unify parameter sets across backends without implying numerical trace identity:

- **Constant rate and traces**: fast unit tests, policy prototyping, and open-loop baselines.
- **FikoRE offline**: multi-UE closed-loop scheduling and L3 feedback evaluation.
- **Real HTTP via FikoRE**: end-to-end validation under kernel transport dynamics.

Every run writes `run-manifest.json` with:

- the revisions of `capcsp`, FikoRE and the SFV reference implementation, and whether their trees had local changes
- the full experiment configuration, including the backend, its transport settings, the `NetworkStep` interval and the session seeds
- the wall-clock time, the simulated time and the byte accounting, including whether all bytes were conserved

FikoRE runs also write the effective INI as `fikore-effective.ini`.
