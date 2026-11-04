# Experiment Report

## Runs

- `vqeg-c1-b1-b2`: backend `transport_fikore`, 120 s simulated in 5.544 s, 2 UEs, status completed, bytes conserved

## KPIs per UE

| Run | UE | Player | Initial delay (s) | Swipe delay (s) | Stalls | Stall time (s) | Switches | Delivered (kB) | Wasted | Goodput (Mbit/s) | Throughput (Mbit/s) | RTT (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vqeg-c1-b1-b2 | 0 | simple | – | 0.130 | 0 | 0.000 | 1 | 354 | 26.3% | 10.48 | 10.48 | 26.1 |
| vqeg-c1-b1-b2 | 1 | preload | 0.100 | 0.030 | 0 | 0.000 | 1 | 470 | 22.0% | 20.89 | 20.89 | 26.0 |

Swipe delay is the mean time from a swipe to playback of the next video. Wasted is the share of delivered bytes that were never played. Goodput is the bytes delivered to the player divided by the time with at least one download open. Throughput (network-layer, including retransmissions) and RTT are means over the backend's telemetry samples taken while a download was open.
