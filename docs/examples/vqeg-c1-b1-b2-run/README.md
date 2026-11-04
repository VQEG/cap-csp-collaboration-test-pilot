# Example Run: C1 With B1 and B2

Raw output of one run on FikoRE, for developing code that reads run results, such as the mapping to the QoE model. It shows the file format only. It is not a performance result.

Regenerate the run from the repository root:

```bash
uv run capcsp run configs/experiments/vqeg/c1-b1-b2.json output/vqeg/c1
```

## Files

- `sessions/ue-0.json`: full player result for UE 0 (B1, `simple`), including `sessionRecord`
- `sessions/ue-1.json`: full player result for UE 1 (B2, `preload`), including `sessionRecord`
- `run-manifest.json`: configuration, source revisions, timing and byte accounting
- `kpis.csv`: one row of KPIs per UE, with the columns described in [Results and Scoring](../../results-and-scoring.md#kpi-table)
- `report.md`: readable summary of the KPIs
- `fikore-effective.ini`: FikoRE scenario used in the run
- `network-steps-first-second.jsonl`: network steps with the player's response, first second only
- `telemetry-first-second.jsonl`: network telemetry per UE, every 10 ms, first second only

## Input for the QoE Model

Start from `sessionRecord` in `sessions/ue-<id>.json`:

- `videos[].swipe_to_playback_delay_s`: time from the swipe to the start of playback of this video, or `null` for a video not reached by a swipe
- `videos[].watch_duration_s`: played media time of the video, without stalls
- `playback_latency.swipe_to_playback`: one entry per swipe with `swipe_at_s`, `playback_started_at_s`, `delay_s` and `status`
- `videos[].representation_intervals`: which representation played, when, and at which position in the video
- `videos[].stall_events`: stalls per video
- `videos[].initial_loading_delay_s`: time from activating the video to the start of playback
- `videos[].rendered_quality_timeline`: representation selected for each segment

The first three fields are the inputs of a swipe delay model such as that of [Nguyen and Tran](https://arxiv.org/abs/2603.18575). The other fields are inputs of models that use video quality and stalls, such as P.1203.

Intervals give only `representation_id` and `bitrate_kbps`. Get the resolution and codec from `sfv-reference-implementation/fixtures/content/content.json`, using `video_id` and `representation_id`:

| Representation | Bitrate (kbit/s) | Width | Height | Codec |
|---|---|---|---|---|
| 0 | 180 | 180 | 320 | `avc1` |
| 1 | 350 | 270 | 480 | `avc1` |
| 2 | 650 | 360 | 640 | `avc1` |

The table lists the representations of `v2`, the video that plays to the end in this run.

## Differences From a Normal Output Folder

- The two `.jsonl` files stop after 1 s of the 120 s run. They show the format only. The QoE input does not need them, and the full files are about 15 MB.
- `run-manifest.json` and `kpis.csv` still describe the full run. The manifest's `config_path` and `content_path` are relative to the repository root.
- `fikore.log` and the empty `player.log` are left out.

## Limits of This Example

- Each session has only one swipe, after about 0.1 s, so the swipe delays are short (0.13 s and 0.03 s) and the viewing time before the swipe is close to 0.
- `stall_events` is empty for both UEs. None of the nine VQEG conditions currently produces a stall. See the [stall example](../stall-example-b1-b2-run/README.md) for filled stall events.
- The fixture has three videos of 6 s with 2 s segments, and sessions swipe once, after about 0.1 s. Only `v2` plays for longer than a moment. It plays 4 s at representation 0 and then 2 s at representation 2, in all nine conditions.
- The content has no frame rate. It lists one audio representation per video, but the player does not request audio, so the record has no audio data. A QoE model that needs these inputs has to assume them for now.
- The record includes the fields `p1204_1_segment_scores` and `p1203_output`. Only 6 s of media play, far less than the 1 to 5 minutes for which P.1203 is specified, so the scores show the format only. See [Results and Scoring](../../results-and-scoring.md#session-record-format).
