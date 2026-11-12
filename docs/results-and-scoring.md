# Results and Scoring

Each run produces one structured session record per video UE. Scoring is computed post-simulation to ensure metric calculations do not alter player execution or network timing.

## Run Output

`capcsp run` writes these files to the output directory, which git ignores. Real runs are available in [`examples/vqeg-c1-b1-b2-run/`](examples/vqeg-c1-b1-b2-run/README.md) and, with stalls, in [`examples/stall-example-b1-b2-run/`](examples/stall-example-b1-b2-run/README.md).

- `sessions/ue-<id>.json`: full player result per UE: `events`, `requests`, `ruleState`, `cache` and `sessionRecord`
- `run-manifest.json`: configuration, source revisions, timing, byte accounting, quality model versions in `scoring`, and collaboration metadata (`shared_state_log`, `csp_control_log` or null, `clock_mode`, `cap_application`)
- `network-steps.jsonl`: every network step with the player's response (download events only, plus `collaboration`)
- `telemetry.jsonl`: CSP telemetry samples per UE, one every `csp_telemetry_interval_s` (1 s by default) plus a final partial one; the same samples are written to the shared table, and they are the KPI input
- `shared-state.jsonl`: append-only audit of shared table writes (CSP and CAP fields per UE)
- `csp-control.jsonl`: present when `signaling_level` is L3+ and `csp_controller` is `"dummy"`; control proposals from `CSPController`
- `kpis.csv` and `report.md`: KPIs per UE, including the combined P.1203 scores; the report also lists scores per video and the model versions
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
      "initial_loading_delay_s": 0.33,
      "swipe_to_playback_delay_s": 0.33,
      "stall_count": 0,
      "stall_duration_s": 0,
      "stall_events": [],
      "quality_switch_count": 0,
      "representation_intervals": [
        {
          "video_id": "v2",
          "representation_id": "2",
          "bitrate_kbps": 650,
          "width": 360,
          "height": 640,
          "codec": "avc1",
          "frame_rate_fps": 30,
          "segment_index": 0,
          "segment_index_end": 2,
          "start_at_s": 0.43,
          "end_at_s": 6.43,
          "start_position_s": 0.005,
          "end_position_s": 6,
          "played_duration_s": 5.995
        }
      ],
      "bytes_delivered": 519838,
      "bytes_media_delivered": 516322,
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
    "swipe_to_playback_delays_s": [0.33],
    "videos_started": 1,
    "videos_completed": 1,
    "stall_count_total": 0,
    "stall_duration_total_s": 0,
    "quality_switch_count_total": 0,
    "bytes_delivered": 614204,
    "bytes_media_delivered": 607174,
    "bytes_data_wastage": 90852,
    "data_wastage_ratio": 0.1496,
    "bytes_unresolved_at_cutoff": 0
  }
}
```

The record also holds the transport settings, session timing, cache lifecycle, playback latency and `playback_metrics`, which combines the quality intervals and stalls of all videos. The manifest holds the configuration and source revisions. Request timestamps and events are in the other fields of the session file.

Scoring adds these fields after the simulation. See [QoE Estimation Models](#qoe-estimation-models).

- `videos[].p1204_1_segment_scores`: played segments with their model inputs and `video_quality_mos`
- `videos[].p1203_output`: `O46`, `O35`, `O23` and the per-second `O22` of the video, or `null` if less than 0.5 s was played
- `session_summary.p1203_output`: means of `O46`, `O35` and `O23` over the scored videos, weighted by played duration, or `null` if no video was scored

Prefetch efficiency is planned and not produced yet.

## KPI Table

`kpis.csv` has one row per UE. Empty cells are `null` values. `capcsp/runner/kpis.py` computes the table.

Run and session:

- `run_id`, `network_backend`, `condition`, `signaling_level`: run identifiers from the configuration
- `ue_id`, `player_behavior`: UE number and player, `simple` (B1) or `preload` (B2)
- `termination_reason`: `session_end` or `simulation_cutoff`
- `requests`: number of requests in the session file

Swipes and delays:

- `swipes`: number of swipes
- `swipe_to_playback_delay_mean_s`: mean time from a swipe to playback of the next video, without swipes where playback did not start
- `swipe_wait_total_s`: sum of all swipe delays
- `initial_playback_delay_s`: time to the start of playback of the first video, empty if the user swiped away before it started

Playback:

- `videos_started`, `videos_completed`: videos with played media, and videos played to their end
- `stall_count_total`, `stall_duration_total_s`: number and total duration of stalls
- `quality_switch_count_total`: quality changes within and between videos

Bytes, as described in [Byte Attribution and Waste Classification](#byte-attribution-and-waste-classification):

- `bytes_delivered`: all delivered bytes
- `bytes_data_wastage`: delivered media bytes that can no longer be used
- `data_wastage_ratio`: `bytes_data_wastage` divided by the delivered media bytes
- `bytes_unresolved_at_cutoff`: unplayed bytes that could still become useful at the simulation cutoff

Quality, from `session_summary.p1203_output`, on a scale of 1 to 5. See [QoE Estimation Models](#qoe-estimation-models).

- `p1203_o46`: final audiovisual score
- `p1203_o35`: audiovisual score without the effect of stalls
- `p1203_o23`: stalling indication, where 5 means no effect of stalls

Network:

- `active_download_time_s`: time with at least one request open
- `goodput_mbps`: bytes delivered to the player, divided by `active_download_time_s`
- `throughput_mbps`: network-side diagnostic. Mean throughput of the CSP telemetry samples in `telemetry.jsonl` whose interval overlaps a time with a request open, including retransmissions
- `rtt_mean_ms`: network-side diagnostic. Mean transport round-trip time of the same samples

`throughput_mbps` and `rtt_mean_ms` describe the network as the CSP sees it, at the cadence of the CSP telemetry (`csp_telemetry_interval_s`, 1 s by default). They are not application measurements. A sample that covers both download and idle time counts in full. For bursty sessions, `throughput_mbps` is therefore well below `goodput_mbps`. Use `goodput_mbps` for the throughput the player obtained.

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
- P.1204.1 Mode 0 segment scores and P.1203 scores

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

The primary audiovisual score uses ITU-T P.1203.3 integration, applied to each video on its own and computed by the [P.1203 reference implementation](https://github.com/itu-p1203/itu-p1203). Video scores come from ITU-T P.1204.1 Mode 0 (AVQBits|M0) instead of the P.1203.1 video module, using [`mode0-retraining`](https://github.com/aveq-research/p1203-mode0-retraining) with its default coefficients. `capcsp/scoring/` holds this code. Both packages are pinned in `pyproject.toml`.

Scoring works as follows:

1. Split each played interval into media segments. The representation gives the resolution and codec. The segment size and duration in the content file give the segment bitrate.
2. Compute one Mode 0 score per segment.
3. Sample the segment scores once per played second as O22. The number of samples is the played duration rounded to full seconds.
4. Pass O21, O22 and the stalling events of the video to `P1203Standalone`. All amendment switches are off.
5. Combine the video scores into the session score as their mean, weighted by played duration. Videos are not joined into one P.1203 session.

The stalling events of a video are its initial loading delay at position 0 and its stall events at their played media position. The initial loading delay is the wait after a swipe or, for the first video, the wait for the first playback.

The optional `scoring` block of an experiment configuration sets the model inputs that session records and content files do not hold:

- `device`: `mobile` (default) or `pc`
- `display_width` and `display_height`: display resolution for the upscaling degradation, by default 1080x1920 (portrait full HD)
- `frame_rate_fps`: assumed frame rate of all representations, by default 30, as stated in the manifests of the SFV fixture
- `audio_o21`: assumed constant audio score, by default 5.0 (constant good quality), as the player does not request audio

P.1203 is only valid for media of 1 minute or longer. Shorter videos are scored fully anyway, knowing this limit. Only videos with less than 0.5 s of played media have no score, as they have no per-second O22 value. They do not count towards the session score.

Two inputs are assumptions and not measured, and must be addressed for future encodings:

- Audio is assumed to be of constant good quality. This raises the audiovisual score: at O21 5.0, an O22 of 3.5 gives an O35 of 4.6. Scores do not reflect real audio quality or audio delivery.
- The frame rate is assumed to be the same for all representations. The content file and the representation intervals carry `frame_rate_fps` per representation (30 fps in the fixture), but the scoring does not read it yet.

Reports must state model versions. Short-Video Streaming Challenge metrics may be reported as supplementary comparative benchmarks.

## Diagnostic Event Logs

Each experiment run writes these diagnostic logs:

- **Network request log**: per-request state transitions and terminal events in `requests` and `events` of the session file, and cumulative delivery steps in `network-steps.jsonl`.
- **Telemetry log**: CSP telemetry samples per UE in `telemetry.jsonl`, used for the network KPIs.
- **Collaboration logs**: `shared-state.jsonl` and, at L3 and above, `csp-control.jsonl`; see [Collaboration Runtime](collaboration.md#output-files).
