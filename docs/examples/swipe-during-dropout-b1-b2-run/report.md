# Experiment Report

## Runs

- `swipe-during-dropout-b1-b2`: backend `transport_fikore`, 20 s simulated in 3.272 s, 2 UEs, status completed, bytes conserved

## KPIs per UE

| Run | UE | Player | Initial delay (s) | Swipe delay (s) | Stalls | Stall time (s) | Switches | Delivered (kB) | Wasted | O46 | O35 | O23 | Bitrate (kbit/s) | Prefetch eff. | SFV NT MOS | Goodput (Mbit/s) | Throughput (Mbit/s) | RTT (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| swipe-during-dropout-b1-b2 | 0 | simple | 0.270 | 0.510 | 0 | 0.000 | 1 | 631 | 5.0% | 3.71 | 4.15 | 4.32 | 504 | 95.1% | 4.23 | 0.53 | 0.42 | 84.0 |
| swipe-during-dropout-b1-b2 | 1 | preload | 0.310 | 0.020 | 1 | 1.980 | 1 | 600 | 26.6% | 3.10 | 3.62 | 3.92 | 254 | 73.9% | 4.05 | 0.53 | 0.44 | 89.8 |

Swipe delay is the mean time from a swipe to playback of the next video. Wasted is the share of delivered bytes that were never played. Goodput is the bytes delivered to the player divided by the time with at least one download open. Throughput (network-layer, including retransmissions) and RTT are network-side diagnostics: means over the CSP telemetry samples (1 s each by default) that overlap a time with a download open, so idle time inside a sample lowers the throughput. O46, O35 and O23 are the means of the P.1203 scores per video, weighted by played duration. Bitrate is the mean bitrate of the played media, weighted by played duration. Prefetch eff. is one minus the bytes wasted by swipes divided by the delivered bytes. SFV NT MOS is the swipe-delay QoE score of Nguyen and Tran, which only counts delays after a swipe in the middle of a video.

## Cell Fairness

| Run | UEs | Hoßfeld F (O46) | Hoßfeld F (SFV NT) | Jain J (Goodput) | Jain J (Throughput) |
|---|---|---|---|---|---|
| swipe-during-dropout-b1-b2 | 2 | 0.848 | 0.957 | 1.000 | 1.000 |

Hoßfeld F is one minus twice the population standard deviation of the UE scores, divided by the score range of 4, where 1 means that all UEs have the same score. Jain J is the Jain index of the goodput or throughput of the UEs, where 1 means equal rates and 1 / UEs means that one UE gets everything.

## P.1203 Scores per Video

| Run | UE | Video | Watched (s) | O46 | O35 | O23 |
|---|---|---|---|---|---|---|
| swipe-during-dropout-b1-b2 | 0 | v1 | 2.7 | 3.16 | 3.47 | 4.29 |
| swipe-during-dropout-b1-b2 | 0 | v3 | 6.0 | 3.96 | 4.45 | 4.33 |
| swipe-during-dropout-b1-b2 | 1 | v1 | 2.7 | 3.14 | 3.47 | 4.25 |
| swipe-during-dropout-b1-b2 | 1 | v2 | 4.0 | 2.32 | 3.47 | 2.71 |
| swipe-during-dropout-b1-b2 | 1 | v3 | 6.0 | 3.60 | 3.80 | 4.58 |

Videos with less than half a second of played media have no score. P.1203 is only valid for media of 1 minute or longer; shorter videos are scored anyway.

## Quality Models

- `swipe-during-dropout-b1-b2`: ITU-T P.1203.3 (`itu-p1203` 1.11.0, commit ffed467), ITU-T P.1204.1 Mode 0 (AVQBits|M0) (`mode0-retraining` 0.1.0, commit e4ebd2e), swipe-delay QoE model Nguyen & Tran (arXiv:2603.18575) (alpha 4.52, beta -0.1, gamma -0.23, lambda 0.55), device mobile, display 1080x1920, frame rate from the content file, fallback 30 fps, assumed constant audio score O21 5
