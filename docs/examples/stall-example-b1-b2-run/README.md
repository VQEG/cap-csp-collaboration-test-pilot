# Example Run: Stall During a Dropout

Raw output of a FikoRE run in which both UEs stall, for developing code that reads stall events. It shows the file format only. It is not a VQEG condition or a performance result.

The scenario starts from an unloaded `100 MHz` parametric 5G cell (`M01` at `mid` `350 m`, with `25 ms` backhaul delay and `20 ms` jitter) with its control timeline set to one forced downlink dropout: the signal drops by 50 dB from 2 s to 7 s. The run lasts 20 s. Its configuration is in `configs/experiments/stall-example/`.

Regenerate the run from the repository root:

```bash
uv run capcsp run configs/experiments/stall-example/stall-example-b1-b2.json output/stall-example
```

## Result

| UE | Player | Stall start (s) | Stall end (s) | Stall duration (s) |
|---|---|---|---|---|
| 0 | `simple` | 4.39 | 9.49 | 5.10 |
| 1 | `preload` | 4.38 | 9.66 | 5.28 |

Both UEs play `v2` at representation 0 until the buffer runs out. The next segment, at representation 2, is requested during the dropout and only arrives after it. Both UEs then play `v2` to the end.

## Files

The folder follows the standard output layout documented in [Results and Scoring](../../results-and-scoring.md#run-output) (`sessions/ue-0.json`, `sessions/ue-1.json`, `run-manifest.json`, `kpis.csv`, `report.md`, `fikore-effective.ini`). `network-steps.jsonl`, `telemetry.jsonl`, `fikore.log` and the empty `player.log` are left out to keep the example small. Regenerate the run to get them. The manifest's `config_path` and `content_path` are relative to the repository root.

Stall events are in `videos[].stall_events` and `playback_metrics.stall_events` of `sessionRecord`. Each event has `video_id`, `started_at_s`, `ended_at_s`, `observed_until_s`, `duration_s` and `status`.

## Limits of This Example

- The two representation intervals of `v2` add up to about 5.95 s of the 6 s watched. The missing 0.05 s, just after the stall, is reported as `unattributed_played_duration_s`.
- Only 6 s of media play, far less than the 1 to 5 minutes for which P.1203 is specified, so the scores show the format only.
- It uses the 3-video smoke-test fixture (`three 6 s videos` and no audio data).
