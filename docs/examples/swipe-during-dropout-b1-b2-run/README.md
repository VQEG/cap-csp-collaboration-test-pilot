# Example Run: Swipes During a Dropout

Raw output of a FikoRE run with long and short swipe delays, for developing code that reads swipe delays. It shows the file format only. It is not a VQEG condition or a performance result.

The scenario is the [stall example](../stall-example-b1-b2-run/README.md) with other swipe times: the signal drops by 50 dB from 2 s to 7 s, and both UEs swipe at 3 s and 9 s. The run lasts 20 s. Its configuration is in `configs/experiments/swipe-example/`.

Regenerate the run from the repository root:

```bash
uv run capcsp run configs/experiments/swipe-example/swipe-during-dropout-b1-b2.json output/swipe-during-dropout
```

## Result

| UE | Player | Swipe at (s) | Next video | Swipe delay (s) |
|---|---|---|---|---|
| 0 | `simple` | 3 | `v2` | 4.58 |
| 0 | `simple` | 9 | `v3` | 0.89 |
| 1 | `preload` | 3 | `v2` | 0.02 |
| 1 | `preload` | 9 | `v3` | 0.02 |

UE 0 does not preload, so its first swipe waits for the end of the dropout. UE 1 has already preloaded the next video and starts it almost at once, but it stalls for 1.04 s later in `v2`.

The watch durations are 2.73 s, 1.42 s and 6 s for UE 0, and 2.78 s, 4.94 s and 6 s for UE 1.

## Files

The folder has the same layout as the [C1 example](../vqeg-c1-b1-b2-run/README.md), which also explains which fields to read. `network-steps.jsonl`, `telemetry.jsonl`, `fikore.log` and the empty `player.log` are left out to keep the example small. Regenerate the run to get them. The manifest's `config_path` and `content_path` are relative to the repository root.

## Limits of This Example

- A swipe model has to define which delays count. The preloaded swipes of UE 1 are reported as delays of 0.02 s, and the delays tested by [Nguyen and Tran](https://arxiv.org/abs/2603.18575) start at 0.25 s.
- The session is shorter than the 1 to 5 minutes for which P.1203 is specified, so the scores show the format only.
- It has the same content limits as the C1 example: three 6 s videos, and no audio data.
