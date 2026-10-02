# VQEG pilot network-condition pack

## Purpose and scope

This directory is a self-contained description of a project-specific application-facing network-condition ladder for FikoRE. It is inspired by VQEG-style testing, but it is not a normative VQEG matrix. The nine conditions cover C1–C7 and two complementary C8 realizations: load-driven bursts (C8a) and coverage-driven transitions (C8b). Each INI studies the first simulated UE, `studyVqeg`, primarily in the downlink direction.

The pack contains nine complete INIs with no inheritance, deterministic NDJSON control timelines, one explicitly test-only propagation map, this README, and a SHA-256 manifest. The physical calibration used FikoRE `2bcee531918d24a3aabad56fd8e975802a73529c`; the pilot runs the backward-compatible `dev` snapshot pinned by this repository's `5g-network-emulator` submodule.

## Intended behavior

Throughput is in Mbps, RTT and jitter are in milliseconds, and loss is a percentage. The target values are calibration bands rather than exact universal network specifications.

| ID | Behavior | Sustained DL | RTT | Loss | Jitter class | Dynamics | Intended dominant cause | Duration/warm-up (s) |
|---|---|---:|---:|---:|---|---|---|---:|
| C1 | Healthy 5G | 48–80 | 15–40 | 0–0.1 | low | steady | none | 120/20 |
| C2 | Plan-capped | 20–30 | 20–45 | 0–0.1 | low | steady | rate_cap | 120/20 |
| C3 | Borderline cell | 8–16 | 25–60 | 0–0.5 | low | moderate | radio_capacity | 120/20 |
| C4 | Congested cell | 4–9 | 35–90 | 0.2–2 | medium | high | scheduler_and_queue | 120/20 |
| C5 | Cell edge / low SINR | 1.5–5 | 50–110 | 2–5 | medium | deep_fades | radio_and_harq | 120/20 |
| C6 | Mobility / dropout proxy | 3–40 | 40–120 | 0–3 | high | dropouts | mobility | 180/20 |
| C7 | Satellite-like | 12–18 | 240–360 | 0–1 | low | steady | backhaul_delay | 120/20 |
| C8a | Bursty congestion | 12–28 | 20–100 | 0–1.5 | high | scheduled_bursts | periodic_congestion | 300/30 |
| C8b | High-to-low coverage transition | 3–60 | 20–120 | 0–3 | high | spatial_transition | coverage_transition | 180/20 |

## How the pack was created

The baseline data came from FikoRE commit `2bcee531918d24a3aabad56fd8e975802a73529c`. The construction used the propagation maps shipped with that revision, its MCS tables and thresholds, the integrated thermal-noise calculation, the configured transmitter and receiver gains, and the same resource-grid and proportional-fair scheduling rules used by the executable.

The main physical baseline is the 3.5 GHz UMa n78 profile with 100 MHz bandwidth, 46 dBm gNB transmit power, 8.7 dB gNB gain, 0 dB UE gain, −174 dBm/Hz thermal-noise density, 2 dB gNB noise figure, and 9 dB UE noise figure. C6 uses the 3.5 GHz rural n78 realization. C8b uses the 2.38 GHz UMi n40 realization with 20 MHz bandwidth and 43 dBm gNB transmit power. The per-condition INIs are authoritative for every value, including synthetic interference settings.

An offline static pass sampled candidate distances over each stock map, mapped the resulting SINR to MCS, derived the available grid capacity, and selected operating regions away from isolated one-sample MCS crossings. The healthy point is near 150 m; C3 selects the low-capacity MCS-0 region; C5 selects the strongest point in the farthest contiguous eligible region. C4 evaluated 10, 20, 40, and 64 background UEs and selected 64 because its predicted equal-share throughput was closest to the congested target. Packet-level runs then calibrated only the INIs, timelines, and test map.

| ID | Physical base | Initial distance (m) | Static SINR (dB) | Static MCS | Static DL capacity (Mbps) | Offered DL (Mbps) | Background UEs |
|---|---|---:|---:|---:|---:|---:|---:|
| C1 | offline_uma_n78_pedestrian | 151.3 | 27.61 | 27 | 378.00 | 64.00 | 0 |
| C2 | offline_uma_n78_pedestrian | 151.3 | 27.61 | 27 | 378.00 | 25.00 | 0 |
| C3 | offline_uma_n78_pedestrian | 775.5 | -3.50 | 0 | 11.96 | 12.00 | 0 |
| C4 | offline_uma_n78_pedestrian | 151.3 | 27.61 | 27 | 378.00 | 5.92 | 64 |
| C5 | offline_uma_n78_pedestrian | 2543.5 | -2.61 | 1 | 19.24 | 3.75 | 0 |
| C6 | offline_rural_n78_vehicular | 400.0 | 4.51 | 2 | 30.82 | 40.00 | 0 |
| C7 | offline_uma_n78_pedestrian | 151.3 | 27.61 | 27 | 378.00 | 15.00 | 0 |
| C8a | offline_uma_n78_pedestrian | 151.3 | 27.61 | 27 | 378.00 | 20.00 | 20 |
| C8b | offline_umi_n40_npn | 25.0 | 57.34 | 27 | 66.71 | 47.25 | 0 |

The physical-base names identify the canonical offline presets used as source data. They are provenance labels, not runtime dependencies or INI inheritance.

The common packet-level settings are PF (`metric_type: 6`, `pf_alpha: 1.0`), a 100 ms throughput EWMA, allocation-unit re-ranking, active `legacy_bler` HARQ with four retries, 12,000-bit packets, one MIMO layer, and L4S disabled. C3 and C5 add 20 dB only to the low-rate uplink RTT probe so that the return sample exists without changing the reported downlink SINR. C6 combines rural circular mobility with three explicit attenuation events. C8a detaches its background UEs between 1000–1500 ms bursts at 5–8 s intervals, preventing tiny queues from wasting whole allocation units.

The pilot co-simulation adapts two source-rate events because study traffic is injected externally and the internal FikoRE generator remains disabled. C2 applies `dl.rmax_mbps: 25` as the intended per-UE plan cap. C7 applies `dl.rmax_mbps: 15` as a temporary proxy for a 15 Mbps satellite-backhaul bottleneck; this limits nominal radio grant bits rather than actual backhaul payload and must be replaced and recalibrated when a backhaul/PDCP-ingress shaper becomes available.

The C8b map is derived deterministically from the stock 2.38 GHz UMi map. The negative-x side retains the parent realization, a narrow smooth transition is applied around the center, and the positive-x side receives up to 70 dB additional loss. Its JSON metadata records the parent-map hash, transformation parameters, and `test_only: true`. The position timeline makes brief repeated high-to-low sweeps and resets the UE after each exposure. This map is a test fixture, not a calibrated channel model, and must remain outside the production map catalog.

## Paths, working directory, and portability

FikoRE resolves `map_file` and `timeline_file` relative to the process working directory, not relative to the INI file. The harness runs from the `5g-network-emulator` submodule root, so a direct run uses:

```bash
cd 5g-network-emulator
./bin/fikore ../configs/fikore/c1_healthy_5g.ini
```

| ID | INI | `map_file` | `timeline_file` |
|---|---|---|---|
| C1 | `c1_healthy_5g.ini` | `include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json` | none |
| C2 | `c2_plan_capped.ini` | `include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json` | `../configs/fikore/timelines/c2_plan_cap.ndjson` |
| C3 | `c3_borderline_cell.ini` | `include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json` | `../configs/fikore/timelines/c3_rtt_probe_return_path.ndjson` |
| C4 | `c4_congested_cell.ini` | `include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json` | none |
| C5 | `c5_cell_edge_low_sinr.ini` | `include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json` | `../configs/fikore/timelines/c5_rtt_probe_return_path.ndjson` |
| C6 | `c6_mobility_dropout.ini` | `include/maps_scenarios/macroscopic_fading_map_RURAL_MACROCELL_3.5.json` | `../configs/fikore/timelines/c6_mobility_dropouts.ndjson` |
| C7 | `c7_satellite_like.ini` | `include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json` | `../configs/fikore/timelines/c7_rate_cap.ndjson` |
| C8a | `c8a_bursty_congestion.ini` | `include/maps_scenarios/macroscopic_fading_map_URBAN_MACROCELL_3.5.json` | `../configs/fikore/timelines/c8a_background_bursts.ndjson` |
| C8b | `c8b_coverage_transition.ini` | `../configs/fikore/maps/c8b_high_to_low_coverage_test_only.json` | `../configs/fikore/timelines/c8b_coverage_path.ndjson` |

The stock maps remain under `5g-network-emulator/include/maps_scenarios/`; they are not duplicated in this pack. The custom C8b map and all timelines are versioned here. If FikoRE is launched from a different working directory, both the stock paths and the `../configs/fikore/...` paths must be made absolute or adjusted for that working directory.

The supplied INIs intentionally omit `seed` and `run_id`. FikoRE can run them directly with its defaults. For reproducible campaigns, copy an INI, add a unique `seed` and `run_id` under `[Global]`, and run the copy from the FikoRE repository root. Do not reuse a run ID because text loggers append to an existing `logs/<run_id>/` directory.

## CAP-CSP harness use

Set `network.fikore_base_ini` to a path under `configs/fikore/`, select `study_ues: [studyVqeg]`, preserve the scenario's calibrated UE settings with `delay_budget_s: null` and `random_v: null`, and use `ack_over_link: true` when the experiment needs RTT to include both directions. A 1 MiB receive window avoids masking high-bandwidth or high-delay conditions with TCP flow control.

The renderer converts only the selected `studyVqeg` block to externally injected traffic. Background groups retain their configured counts and source traffic. Since co-simulation uses the Unix control socket, the harness reads the INI's NDJSON timeline and replays every `set` at its original TTI through `FikoreLink`; commands targeting `studyVqeg` are expanded to every concrete study UE.

## Measurement and acceptance protocol

Sustained throughput is the median of non-overlapping 1 s downlink windows after warm-up. Short-window dynamics use 10 ms windows where relevant so that PF grant intermittency is not hidden by one-second averaging. The offline RTT proxy is UL IP latency plus DL IP latency, using only samples for which both directions report positive latency; an external echo can be used for live application RTT. Jitter is RTT P95 minus P50. Terminal loss includes expiry, queue-drop, and radio-drop bits and excludes bits still pending at the end of the measurement interval.

The fixed validation seeds are `20260927, 20260928, 20260929`. Validation duration and warm-up are listed in the target table. The INI `duration` controls simulator runtime; warm-up is an analysis rule and is therefore documented here rather than represented by an INI runtime knob. A condition is accepted when its complete target behavior, dominant-cause check, RTT sample coverage, and exact bit closure pass in at least 2 of 3 seeds.


## Measured three-seed validation

The values below are medians from the original offline source-rate validation. Every accepted run also had a zero bit-conservation residual. They remain physical baselines for the pack, but C2 and C7 require separate co-simulation measurements after their timelines were adapted to nominal grant caps.

| ID | Passing seeds | DL median (Mbps) | RTT P50 (ms) | Loss (%) | Jitter (ms) | DL SINR (dB) |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 3/3 | 64.00 | 22.48 | 0.000 | 1.08 | 27.11 |
| C2 | 3/3 | 25.00 | 26.44 | 0.000 | 1.15 | 27.11 |
| C3 | 3/3 | 12.00 | 44.00 | 0.009 | 6.33 | -4.16 |
| C4 | 3/3 | 5.81 | 82.00 | 1.830 | 12.50 | 27.11 |
| C5 | 2/3 | 3.65 | 102.14 | 2.509 | 17.35 | -8.43 |
| C6 | 3/3 | 39.99 | 53.34 | 0.005 | 1470.32 | 21.95 |
| C7 | 3/3 | 15.00 | 302.43 | 0.000 | 1.98 | 27.11 |
| C8a | 3/3 | 19.99 | 33.83 | 0.000 | 97.85 | 27.12 |
| C8b | 3/3 | 47.25 | 34.05 | 0.001 | 162.70 | 53.02 |


The packet-level radio state is the acceptance reference. C5 is the least seed-robust condition: its static pass selected −2.61 dB and MCS 1, while packet-level execution measured a median −8.43 dB and MCS 0 with a small outage fraction; it passed the full condition in two of three seeds. C3 was closer to the static estimate: −3.50 dB predicted and −4.16 dB measured, both at MCS 0.

## Interpretation and limitations

C6 is a repeatable mobility/dropout proxy, not a handover model. C7 reproduces a high-delay, medium-bandwidth application envelope but does not model a satellite waveform. The RTT values above are internal IP-layer proxies, not live application echoes. The synthetic interference parameters do not constitute a multicell simulation. The pack does not model carrier aggregation, beamforming, inter-cell scheduling, or handover signaling. Distances are coordinates in one concrete shadowing realization, not universal distance-to-KPI mappings.

`manifest.json` records the upstream FikoRE commit, condition-contract hash, fixed seeds, and SHA-256 digest of every materialized asset. The custom map carries its own parent-map hash and transformation metadata so the pack can be audited after relocation.
