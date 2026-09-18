# Results and Scoring

Each run produces one structured session record per video UE. Scoring is computed post-simulation to ensure metric calculations do not alter player execution or network timing.

## Session Record Format

Session records serve as the primary dataset for evaluation. All metrics include explicit units in their field names.

```json
{
  "schema_version": 1,
  "created_at": "2026-09-18T12:00:00Z",
  "run_id": "c04-L2-preload-seed17",
  "session_id": "c04-L2-preload-seed17-ue3",
  "ue_id": 3,
  "condition": "C4_congested",
  "network_backend": "fikore_cosim",
  "signaling_level": "L2",
  "player_behavior": "preload",
  "swipe_profile": "medium",
  "seed": 17,
  "videos": [
    {
      "video_id": "v8",
      "video_sequence_number": 0,
      "video_duration_s": 15.0,
      "watch_duration_s": 1.8,
      "swiped_away": true,
      "time_to_first_byte_s": 0.12,
      "initial_loading_delay_s": 0.45,
      "stall_count": 0,
      "stall_duration_s": 0.0,
      "bytes_delivered": 1234567,
      "bytes_wasted": 345678,
      "p1203_output": {"O46": 3.91, "O35": 4.2, "O23": 4.6}
    }
  ],
  "session_summary": {
    "videos_started": 12,
    "videos_completed": 7,
    "o46_mean": 3.75,
    "initial_loading_delay_mean_s": 0.52,
    "stall_count_total": 3,
    "stall_duration_total_s": 4.2,
    "bytes_delivered": 8123456,
    "bytes_wasted_prefetch": 2310912,
    "prefetch_efficiency": 0.72
  }
}
```

The record also captures the realized configuration, source code revisions, request timestamps, quality timelines, user swipe events, network telemetry logs, and transport settings.

## Byte Attribution and Waste Classification

Delivered bytes map directly to the corresponding media object in the request registry, regardless of which video is actively displaying when bytes arrive.

Application waste includes:

- Delivered prefetch segments that are never played
- Delivered segments belonging to the unplayed portion of a swiped video
- The in-flight tail of a cancelled request delivered after the cancel decision

Retransmitted or dropped radio packets are tracked separately as network-layer overhead.

## Per-Video Metrics

Each video record includes:

- Watch duration and swipe flag
- Requested and rendered quality representations over time
- Timestamps for request, first byte, and completion
- Initial loading delay
- Stall count and aggregate stall duration
- Delivered, rendered, and wasted byte totals
- ITU-T P.1203 / P.1204.1 or P.1204.3 quality scores

If a request is cancelled before byte arrival, its time-to-first-byte is `null`. Aggregate averages exclude `null` values and log the valid sample count.

## Aggregate Evaluation Formulas

### Prefetch Efficiency

$$\text{Efficiency} = 1 - \frac{\text{bytes\_wasted\_prefetch}}{\text{bytes\_delivered}}$$

Yields `null` when no bytes were delivered.

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

Reports must state model versions. Short-Video Streaming Challenge metrics may be reported as supplementary comparative benchmarks.

## Diagnostic Event Logs

Each experiment run generates two auxiliary diagnostic logs:

- **CAP–CSP exchange log**: time-indexed record of all signaling fields, state changes, and feedback reports.
- **Network request log**: per-request state transitions, cumulative delivery steps, and terminal events.
