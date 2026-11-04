# Experiment Report

## Runs

- `stall-example-b1-b2`: backend `transport_fikore`, 20 s simulated in 1.064 s, 2 UEs, status completed, bytes conserved

## KPIs per UE

| Run | UE | Player | Initial delay (s) | Swipe delay (s) | Stalls | Stall time (s) | Switches | Delivered (kB) | Wasted | Goodput (Mbit/s) | Throughput (Mbit/s) | RTT (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stall-example-b1-b2 | 0 | simple | – | 0.340 | 1 | 3.220 | 1 | 297 | 11.9% | 0.42 | 0.55 | 71.2 |
| stall-example-b1-b2 | 1 | preload | – | 0.230 | 1 | 3.350 | 1 | 386 | 4.4% | 0.53 | 0.65 | 70.8 |

Swipe delay is the mean time from a swipe to playback of the next video. Wasted is the share of delivered bytes that were never played. Goodput is the bytes delivered to the player divided by the time with at least one download open. Throughput (network-layer, including retransmissions) and RTT are means over the backend's telemetry samples taken while a download was open.
