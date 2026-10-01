# VQEG condition-matrix smoke evidence

The complete nine-run B1/B2 matrix was executed in the project Docker image with FikoRE `ad17dbd`, SFV fixture `07fab25` and FikoRE seed `20260927`. Every run completed, wrote `fikore-effective.ini`, conserved all submitted bytes and reported no rejected control command.

The table reports means over periods with active object downloads. These values validate end-to-end wiring; they are not replacements for the condition pack's saturated offline calibration.

| Condition | Wall time (s) | UE 0 throughput (Mbps) | UE 1 throughput (Mbps) | UE 0 RTT (ms) | UE 1 RTT (ms) |
|---|---:|---:|---:|---:|---:|
| C1 | 24.118 | 8.641 | 14.625 | 26.28 | 26.16 |
| C2 | 23.740 | 9.701 | 13.970 | 31.41 | 36.70 |
| C3 | 24.474 | 4.914 | 4.566 | 51.00 | 54.56 |
| C4 | 128.292 | 0.000 | 0.001 | n/a | n/a |
| C5 | 22.178 | 2.295 | 2.865 | 70.02 | 78.04 |
| C6 | 32.483 | 3.093 | 2.148 | 64.09 | 75.56 |
| C7 | 21.664 | 0.880 | 1.465 | 309.12 | 311.38 |
| C8a | 120.799 | 5.801 | 4.302 | 39.55 | 36.43 |
| C8b | 33.248 | 3.621 | 3.773 | 34.24 | 41.54 |

The dynamic controls were visible in telemetry:

- C6 downlink SINR ranged from −34.97 to 33.00 dB during attenuation events.
- C8a retained stable radio coverage (19.52 to 31.62 dB) while its background timeline executed.
- C8b ranged from −13.59 to 72.21 dB while the position timeline crossed the custom map.

C4 is operationally important: the run and accounting completed, but the two externally driven study UEs made essentially no application progress against 64 saturated background UEs with the calibrated 30 ms packet budget. This is a valid outcome of combining the condition with bursty TCP object traffic, not proof that the original saturated-source calibration is wrong. It should be investigated before C4 is used as a routine player-policy benchmark.
