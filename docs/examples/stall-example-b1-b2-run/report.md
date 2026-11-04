# Experiment Report

## Runs

- `stall-example-b1-b2`: backend `transport_fikore`, 20 s simulated in 1.219 s, 2 UEs, status completed, bytes conserved

## KPIs per UE

| Run | UE | Player | Initial delay (s) | Swipe delay (s) | Stalls | Stall time (s) | Switches | Delivered (kB) | Wasted | O46 | O35 | O23 | Goodput (Mbit/s) | Throughput (Mbit/s) | RTT (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stall-example-b1-b2 | 0 | simple | – | 0.330 | 1 | 3.050 | 1 | 296 | 11.5% | 2.53 | 3.79 | 2.73 | 0.43 | 0.62 | 90.6 |
| stall-example-b1-b2 | 1 | preload | – | 0.250 | 1 | 3.240 | 1 | 404 | 8.8% | 2.52 | 3.79 | 2.69 | 0.56 | 0.72 | 82.9 |

Swipe delay is the mean time from a swipe to playback of the next video. Wasted is the share of delivered bytes that were never played. Goodput is the bytes delivered to the player divided by the time with at least one download open. Throughput (network-layer, including retransmissions) and RTT are means over the backend's telemetry samples taken while a download was open. O46, O35 and O23 are the means of the P.1203 scores per video, weighted by played duration.

## P.1203 Scores per Video

| Run | UE | Video | Watched (s) | O46 | O35 | O23 |
|---|---|---|---|---|---|---|
| stall-example-b1-b2 | 0 | v2 | 6.0 | 2.53 | 3.79 | 2.73 |
| stall-example-b1-b2 | 1 | v2 | 6.0 | 2.51 | 3.79 | 2.69 |

Videos with less than half a second of played media have no score. P.1203 is only valid for media of 1 minute or longer; shorter videos are scored anyway.

## Quality Models

- `stall-example-b1-b2`: ITU-T P.1203.3 (`itu-p1203` 1.11.0, commit ffed467), ITU-T P.1204.1 Mode 0 (AVQBits|M0) (`mode0-retraining` 0.1.0, commit e4ebd2e), device mobile, display 1080x1920, assumed frame rate 30 fps, assumed constant audio score O21 5
