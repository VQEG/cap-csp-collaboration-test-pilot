# Experiment Report

## Runs

- `vqeg-c1-b1-b2`: backend `transport_fikore`, 120 s simulated in 15.85 s, 2 UEs, status completed, bytes conserved

## KPIs per UE

| Run | UE | Player | Initial delay (s) | Swipe delay (s) | Stalls | Stall time (s) | Switches | Delivered (kB) | Wasted | O46 | O35 | O23 | Goodput (Mbit/s) | Throughput (Mbit/s) | RTT (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vqeg-c1-b1-b2 | 0 | simple | – | 0.330 | 0 | 0.000 | 0 | 614 | 15.0% | 4.00 | 4.45 | 4.42 | 8.62 | 2.46 | 26.4 |
| vqeg-c1-b1-b2 | 1 | preload | – | 0.030 | 0 | 0.000 | 1 | 470 | 22.1% | 3.59 | 3.79 | 4.58 | 14.46 | 1.90 | 26.5 |

Swipe delay is the mean time from a swipe to playback of the next video. Wasted is the share of delivered bytes that were never played. Goodput is the bytes delivered to the player divided by the time with at least one download open. Throughput (network-layer, including retransmissions) and RTT are network-side diagnostics: means over the CSP telemetry samples (1 s each by default) that overlap a time with a download open, so idle time inside a sample lowers the throughput. O46, O35 and O23 are the means of the P.1203 scores per video, weighted by played duration.

## P.1203 Scores per Video

| Run | UE | Video | Watched (s) | O46 | O35 | O23 |
|---|---|---|---|---|---|---|
| vqeg-c1-b1-b2 | 0 | v2 | 6.0 | 4.00 | 4.45 | 4.42 |
| vqeg-c1-b1-b2 | 1 | v2 | 6.0 | 3.59 | 3.79 | 4.58 |

Videos with less than half a second of played media have no score. P.1203 is only valid for media of 1 minute or longer; shorter videos are scored anyway.

## Quality Models

- `vqeg-c1-b1-b2`: ITU-T P.1203.3 (`itu-p1203` 1.11.0, commit ffed467), ITU-T P.1204.1 Mode 0 (AVQBits|M0) (`mode0-retraining` 0.1.0, commit e4ebd2e), device mobile, display 1080x1920, assumed frame rate 30 fps, assumed constant audio score O21 5
