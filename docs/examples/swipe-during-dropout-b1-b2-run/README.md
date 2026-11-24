# Example Run: Swipes During a Dropout

Raw output of a FikoRE run with long and short swipe delays, for developing code that reads swipe delays. It shows the file format only. It is not a VQEG condition or a performance result.

The scenario is the [stall example](../stall-example-b1-b2-run/README.md) with other swipe times: the signal drops by 50 dB from 2 s to 7 s, and both UEs swipe at 3 s and 9 s. The run lasts 20 s. Its configuration is in `configs/experiments/swipe-example/`.

Regenerate the run from the repository root:

```bash
uv run capcsp run configs/experiments/swipe-example/swipe-during-dropout-b1-b2.json output/swipe-during-dropout
```

## Result

| UE | Player | Swipe at (s) | Next video | Swipe delay (s) | Status |
|---|---|---|---|---|---|
| 0 | `simple` | 3 | `v2` | `null` | `interrupted_by_next_swipe` |
| 0 | `simple` | 9 | `v3` | 0.51 | `started` |
| 1 | `preload` | 3 | `v2` | 0.02 | `started` |
| 1 | `preload` | 9 | `v3` | 0.02 | `started` |

UE 0 does not preload, so its first swipe at 3 s hits the radio dropout and TCP RTO backoff, never starting `v2` before the user swipes again at 9 s; `v3` then starts 0.51 s later. UE 1 has already preloaded the next video and starts both `v2` and `v3` almost at once (`0.02 s`), stalling for `1.98 s` (`7.02–9.00 s`) after the preloaded portion of `v2` runs out.

The watch durations are `2.735 s`, `0 s` and `6 s` for UE 0, and `2.695 s`, `4 s` and `6 s` for UE 1.

## Files

The folder follows the standard output layout documented in [Results and Scoring](../../results-and-scoring.md#run-output). `network-steps.jsonl`, `telemetry.jsonl`, `fikore.log` and the empty `player.log` are left out to keep the example small. Regenerate the run to get them. The manifest's `config_path` and `content_path` are relative to the repository root.

## Limits of This Example

- A swipe model has to define which delays count. The preloaded swipes of UE 1 are reported as delays of 0.02 s, and the delays tested by [Nguyen and Tran](https://arxiv.org/abs/2603.18575) start at 0.25 s.
- The session is shorter than the 1 to 5 minutes for which P.1203 is specified, so the scores show the format only.
- It uses the 3-video smoke-test fixture (`three 6 s videos`, and no audio data).
