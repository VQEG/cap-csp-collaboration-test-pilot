# Example Run: Stall During a Dropout

Raw output of a FikoRE run in which both UEs stall, for developing code that reads stall events. It shows the file format only. It is not a VQEG condition or a performance result.

The scenario is C6 with its timeline replaced by one forced downlink dropout: the signal drops by 50 dB from 2 s to 7 s. The run lasts 20 s. Its configuration is in `configs/experiments/stall-example/`.

Regenerate the run from the repository root:

```bash
uv run capcsp run configs/experiments/stall-example/stall-example-b1-b2.json output/stall-example
```

## Result

| UE | Player | Stall start (s) | Stall end (s) | Stall duration (s) |
|---|---|---|---|---|
| 0 | `simple` | 4.43 | 7.48 | 3.05 |
| 1 | `preload` | 4.36 | 7.60 | 3.24 |

Both UEs play `v2` at representation 0 until the buffer runs out. The next segment, at representation 2, is requested during the dropout and only arrives after it. Both UEs then play `v2` to the end.

## Files

The folder has the same layout as the [C1 example](../vqeg-c1-b1-b2-run/README.md), which also explains which fields to read. `network-steps.jsonl`, `telemetry.jsonl`, `fikore.log` and the empty `player.log` are left out to keep the example small. Regenerate the run to get them. The manifest's `config_path` and `content_path` are relative to the repository root.

Stall events are in `videos[].stall_events` and `playback_metrics.stall_events` of `sessionRecord`. Each event has `video_id`, `started_at_s`, `ended_at_s`, `observed_until_s`, `duration_s` and `status`.

## Limits of This Example

- The two representation intervals of `v2` add up to about 5.95 s of the 6 s watched. The missing 0.05 s, just after the stall, is reported as `unattributed_played_duration_s`.
- Only 6 s of media play, far less than the 1 to 5 minutes for which P.1203 is specified, so the scores show the format only.
- It has the same content limits as the C1 example: three 6 s videos and no audio data.
