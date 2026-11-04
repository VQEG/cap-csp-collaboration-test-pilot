# Results and Scoring

Each run produces one structured session record per video UE. Scoring is computed post-simulation to ensure metric calculations do not alter player execution or network timing.

## Run Output

`capcsp run` writes these files to the output directory, which git ignores. Real runs are available in [`examples/vqeg-c1-b1-b2-run/`](examples/vqeg-c1-b1-b2-run/README.md) and, with stalls, in [`examples/stall-example-b1-b2-run/`](examples/stall-example-b1-b2-run/README.md).

- `sessions/ue-<id>.json`: full player result per UE: `events`, `requests`, `ruleState`, `cache` and `sessionRecord`
- `run-manifest.json`: configuration, source revisions, timing and byte accounting
- `network-steps.jsonl`: every network step with the player's response
- `telemetry.jsonl`: network telemetry samples per UE
- `kpis.csv` and `report.md`: KPIs per UE
- `player.log`: error output of the player process
- `fikore-effective.ini` and `fikore.log`: scenario and log of the FikoRE backend

## Session Record Format

Session records serve as the primary dataset for evaluation. All metrics include explicit units in their field names. The record is the `sessionRecord` field of `sessions/ue-<id>.json`, with schema version 2.

This excerpt comes from UE 0 of the example run. It shows one of the three videos and omits some fields:

```json
{
  "schema_version": 2,
  "run_id": "vqeg-c1-b1-b2",
  "session_id": "generic-ue0",
  "ue_id": 0,
  "condition": "C1",
  "network_backend": "transport_fikore",
  "signaling_level": "L0",
  "player_behavior": "simple",
  "swipe_profile": "scripted",
  "resolved_swipe_times_s": [0.1],
  "seed": 17,
  "termination_reason": "simulation_cutoff",
  "videos": [
    {
      "video_id": "v2",
      "video_sequence_number": 1,
      "video_duration_s": 6,
      "watch_duration_s": 6,
      "swiped_away": false,
      "time_to_first_byte_s": 0.02,
      "initial_loading_delay_s": 0.13,
      "swipe_to_playback_delay_s": 0.13,
      "stall_count": 0,
      "stall_duration_s": 0,
      "stall_events": [],
      "quality_switch_count": 1,
      "representation_intervals": [
        {
          "video_id": "v2",
          "representation_id": "0",
          "bitrate_kbps": 180,
          "segment_index": 0,
          "segment_index_end": 1,
          "start_at_s": 0.23,
          "end_at_s": 4.225,
          "start_position_s": 0.005,
          "end_position_s": 4,
          "played_duration_s": 3.995
        }
      ],
      "bytes_delivered": 259309,
      "bytes_media_delivered": 254967,
      "bytes_data_wastage": 0,
      "data_wastage_by_reason": {
        "swipe": 0,
        "representation_superseded": 0,
        "cache_admission_rejected": 0,
        "session_end": 0
      },
      "bytes_unresolved_at_cutoff": 0
    }
  ],
  "session_summary": {
    "initial_playback_delay_s": null,
    "swipe_to_playback_delays_s": [0.13],
    "videos_started": 1,
    "videos_completed": 1,
    "stall_count_total": 0,
    "stall_duration_total_s": 0,
    "quality_switch_count_total": 1,
    "bytes_delivered": 353675,
    "bytes_media_delivered": 345819,
    "bytes_data_wastage": 90852,
    "data_wastage_ratio": 0.2627,
    "bytes_unresolved_at_cutoff": 0
  }
}
```

The record also holds the transport settings, session timing, cache lifecycle, playback latency and `playback_metrics`, which combines the quality intervals and stalls of all videos. The manifest holds the configuration and source revisions. Request timestamps and events are in the other fields of the session file.

The following fields are planned and not produced yet: P.1203 scores per video (`O46`, `O35`, `O23`) and per session, and prefetch efficiency.

## Byte Attribution and Waste Classification

Delivered bytes map directly to the corresponding media object in the request registry, regardless of which video is actively displaying when bytes arrive.

Data wastage counts delivered media bytes that can no longer be used. `data_wastage_by_reason` separates these reasons:

- `swipe`: unplayed bytes of a video the user swiped away, including preloaded segments and bytes of cancelled requests
- `representation_superseded`: a completed segment replaced by a higher-quality representation of the same segment
- `cache_admission_rejected`: delivered bytes the cache did not accept
- `session_end`: unplayed bytes when the user session ends

A simulation cutoff is not a session end. Unplayed bytes that could still become useful at the cutoff are reported as `bytes_unresolved_at_cutoff`, not as wastage. For example, preloaded segments of a video that was never reached are unresolved.

`data_wastage_ratio` is `bytes_data_wastage` divided by `bytes_media_delivered`, or `null` if no media bytes were delivered.

Retransmitted or dropped radio packets are tracked separately as network-layer overhead.

## Per-Video Metrics

Each video record includes:

- Watch duration and swipe flag
- Rendered quality representations over time
- Time to first byte
- Initial loading delay and swipe-to-playback delay
- Stall events, stall count and aggregate stall duration
- Delivered, wasted and unresolved byte totals

Quality scores from ITU-T P.1203 / P.1204.1 or P.1204.3 are planned for each video record.

Time to first byte uses the earliest request of the video that received a byte. It is `null` if no request of the video received a byte. Aggregate KPIs exclude `null` values.

## Aggregate Evaluation Formulas

These formulas are planned and not implemented yet.

### Prefetch Efficiency

$$\text{Efficiency} = 1 - \frac{\text{bytes\_wasted\_prefetch}}{\text{bytes\_delivered}}$$

Yields `null` when no bytes were delivered. The session record does not separate prefetch waste yet.

### QoE Fairness (Hoßfeld Index)

Computed across mean session O46 scores for all $K$ video UEs in a cell:

$$F = 1 - \frac{2 \cdot \sigma(O_{46})}{5 - 1}$$

where $\sigma(O_{46})$ is the population standard deviation of session MOS values.

### Throughput Fairness (Jain's Index)

Computed across mean achieved throughput $x_k$ for each UE $k \in \{1, \dots, K\}$:

$$J = \frac{\left(\sum_{k=1}^K x_k\right)^2}{K \cdot \sum_{k=1}^K x_k^2}$$

Yields `null` when aggregate throughput is zero.

## QoE Estimation Models

The primary audiovisual score uses ITU-T P.1203 session integration. Per-segment video quality inputs use ITU-T P.1204.1 Mode 0 (AVQBits). Werner has code for this and will implement it.

The session record gives the bitrate and representation ID of each played interval. The resolution and codec come from the content file, using `video_id` and `representation_id`. The current content file has no frame rate. It lists one audio representation per video, but the player does not request audio, so the session record has no audio data.

Reports must state model versions. Short-Video Streaming Challenge metrics may be reported as supplementary comparative benchmarks.

## Diagnostic Event Logs

Each experiment run writes these diagnostic logs:

- **Network request log**: per-request state transitions and terminal events in `requests` and `events` of the session file, and cumulative delivery steps in `network-steps.jsonl`.
- **Telemetry log**: network samples per UE in `telemetry.jsonl`.

A CAP–CSP exchange log, with all signaling fields, state changes and feedback reports, is planned.
