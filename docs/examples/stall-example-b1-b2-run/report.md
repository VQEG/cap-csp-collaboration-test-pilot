# Experiment Report

## Runs

- `stall-example-b1-b2`: backend `transport_fikore`, 20 s simulated in 2.963 s, 2 UEs, status completed, bytes conserved

## KPIs per UE

| Run | UE | Player | Initial delay (s) | Swipe delay (s) | Stalls | Stall time (s) | Switches | Delivered (kB) | Wasted | O46 | O35 | O23 | Bitrate (kbit/s) | Prefetch eff. | SFV NT MOS | Goodput (Mbit/s) | Throughput (Mbit/s) | RTT (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stall-example-b1-b2 | 0 | simple | – | 0.290 | 1 | 5.100 | 1 | 278 | 5.6% | 2.29 | 3.79 | 2.23 | 334 | 94.6% | 4.26 | 0.30 | 0.25 | 86.0 |
| stall-example-b1-b2 | 1 | preload | – | 0.270 | 1 | 5.280 | 1 | 401 | 8.1% | 2.27 | 3.79 | 2.19 | 334 | 92.1% | 4.26 | 0.41 | 0.36 | 82.6 |

Swipe delay is the mean time from a swipe to playback of the next video. Wasted is the share of delivered bytes that were never played. Goodput is the bytes delivered to the player divided by the time with at least one download open. Throughput (network-layer, including retransmissions) and RTT are network-side diagnostics: means over the CSP telemetry samples (1 s each by default) that overlap a time with a download open, so idle time inside a sample lowers the throughput. O46, O35 and O23 are the means of the P.1203 scores per video, weighted by played duration. Bitrate is the mean bitrate of the played media, weighted by played duration. Prefetch eff. is one minus the bytes wasted by swipes divided by the delivered bytes. SFV NT MOS is the swipe-delay QoE score of Nguyen and Tran, which only counts delays after a swipe in the middle of a video.

## Cell Fairness

| Run | UEs | Hoßfeld F (O46) | Hoßfeld F (SFV NT) | Jain J (Goodput) | Jain J (Throughput) |
|---|---|---|---|---|---|
| stall-example-b1-b2 | 2 | 0.996 | 1.000 | 0.973 | 0.968 |

Hoßfeld F is one minus twice the population standard deviation of the UE scores, divided by the score range of 4, where 1 means that all UEs have the same score. Jain J is the Jain index of the goodput or throughput of the UEs, where 1 means equal rates and 1 / UEs means that one UE gets everything.

## P.1203 Scores per Video

| Run | UE | Video | Watched (s) | O46 | O35 | O23 |
|---|---|---|---|---|---|---|
| stall-example-b1-b2 | 0 | v2 | 6.0 | 2.29 | 3.79 | 2.23 |
| stall-example-b1-b2 | 1 | v2 | 6.0 | 2.27 | 3.79 | 2.20 |

Videos with less than half a second of played media have no score. P.1203 is only valid for media of 1 minute or longer; shorter videos are scored anyway.

## Quality Models

- `stall-example-b1-b2`: ITU-T P.1203.3 (`itu-p1203` 1.11.0, commit ffed467), ITU-T P.1204.1 Mode 0 (AVQBits|M0) (`mode0-retraining` 0.1.0, commit e4ebd2e), swipe-delay QoE model Nguyen & Tran (arXiv:2603.18575) (alpha 4.52, beta -0.1, gamma -0.23, lambda 0.55), device mobile, display 1080x1920, frame rate from the content file, fallback 30 fps, assumed constant audio score O21 5
