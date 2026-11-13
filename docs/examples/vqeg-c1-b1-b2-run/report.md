# Experiment Report

## Runs

- `vqeg-c1-b1-b2`: backend `transport_fikore`, 120 s simulated in 6.293 s, 2 UEs, status completed, bytes conserved

## KPIs per UE

| Run | UE | Player | Initial delay (s) | Swipe delay (s) | Stalls | Stall time (s) | Switches | Delivered (kB) | Wasted | O46 | O35 | O23 | Goodput (Mbit/s) | Throughput (Mbit/s) | RTT (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vqeg-c1-b1-b2 | 0 | simple | 0.150 | 0.105 | 0 | 0.000 | 1 | 1307 | 8.4% | 3.90 | 4.22 | 4.53 | 16.60 | 1.78 | 27.1 |
| vqeg-c1-b1-b2 | 1 | preload | 0.120 | 0.020 | 0 | 0.000 | 5 | 789 | 0.0% | 3.59 | 3.80 | 4.57 | 15.77 | 1.28 | 26.6 |

Swipe delay is the mean time from a swipe to playback of the next video. Wasted is the share of delivered bytes that were never played. Goodput is the bytes delivered to the player divided by the time with at least one download open. Throughput (network-layer, including retransmissions) and RTT are network-side diagnostics: means over the CSP telemetry samples (1 s each by default) that overlap a time with a download open, so idle time inside a sample lowers the throughput. O46, O35 and O23 are the means of the P.1203 scores per video, weighted by played duration.

## P.1203 Scores per Video

| Run | UE | Video | Watched (s) | O46 | O35 | O23 |
|---|---|---|---|---|---|---|
| vqeg-c1-b1-b2 | 0 | v1 | 6.0 | 3.56 | 3.80 | 4.51 |
| vqeg-c1-b1-b2 | 0 | v2 | 4.6 | 4.08 | 4.46 | 4.52 |
| vqeg-c1-b1-b2 | 0 | v3 | 6.0 | 4.09 | 4.45 | 4.54 |
| vqeg-c1-b1-b2 | 1 | v1 | 6.0 | 3.57 | 3.80 | 4.53 |
| vqeg-c1-b1-b2 | 1 | v2 | 6.0 | 3.59 | 3.79 | 4.58 |
| vqeg-c1-b1-b2 | 1 | v3 | 6.0 | 3.60 | 3.80 | 4.58 |

Videos with less than half a second of played media have no score. P.1203 is only valid for media of 1 minute or longer; shorter videos are scored anyway.

## Quality Models

- `vqeg-c1-b1-b2`: ITU-T P.1203.3 (`itu-p1203` 1.11.0, commit ffed467), ITU-T P.1204.1 Mode 0 (AVQBits|M0) (`mode0-retraining` 0.1.0, commit e4ebd2e), device mobile, display 1080x1920, frame rate from the content file, fallback 30 fps, assumed constant audio score O21 5
