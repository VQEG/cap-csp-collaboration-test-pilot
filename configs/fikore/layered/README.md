# Layered FikoRE Network-Condition Pack

## Purpose and structure

This directory defines an 11-condition layered radio and contention model (`M01`–`M11`) for systematic CAP-CSP collaboration experiments over FikoRE. Unlike heterogeneous point conditions that mix rate limiters, backhaul shapers, and distinct cell carriers, every condition here shares a single physical cell baseline and varies only four orthogonal parameters:

1. **Normalized competing channel load (`rho`)**: `0%`, `50%`, `75%`, `100%`.
2. **Temporal session variability (`tau`)**: `med` (Poisson `M/M/inf` arrivals with 8 s mean session hold) vs `high` (burst-modulated Poisson waves with 12 s mean hold).
3. **Spatial distribution (`S`)**: homogeneous good-SINR ring (`good_homo`) vs uniform-area cell distribution (`good_het`, `mid_het`, `edge_het`) shifting the study UE from `151.3 m` (MCS 25, ~0.15 RBG/Mbps) to `350.0 m` (MCS 9, ~0.31 RBG/Mbps) and `650.0 m` (MCS 2, ~1.1 RBG/Mbps).
4. **Mobility (`M`)**: `static`, `ped_edge` (`3.6 km/h` pedestrian walk at cell edge), and `veh_traverse` (`73.3 km/h` deterministic center–edge–center traversal, 25 s outbound and 25 s return).

## Physical and scheduling invariants

- **Cell baseline**: 3.5 GHz Urban Macro (`UMa` n78, `macroscopic_fading_map_URBAN_MACROCELL_3.5.json`), `20 MHz` channel bandwidth (`50 PRBs`, `12 RBGs` of `4 PRBs` per TTI, `scheduling_config: 0`), TDD `7/3/54`, `10 ms` one-way backhaul delay (`backhaul_d_var: 0.0`), in-order delivery (`harq_model: disabled`, `order_pkts: true`).
- **Unconstrained scheduler**: Proportional Fair (`metric_type: 6`, `pf_alpha: 1.0`, `throughput_time_window_ms: 100.0`). **No `dl.rmax_mbps` or `ul.rmax_mbps` token-bucket cap is applied to any UE.**
- **Competing SFV-like flows**: Competing UEs (`backgroundSfV`) attach and detach according to pre-rendered Poisson NDJSON timelines (`timelines/*.ndjson`) at freshly sampled spatial coordinates. In co-simulation (`capcsp`), `network.background_iperf_ues: {"backgroundSfV": 4.0}` drives each active competing UE with an application-paced `4.0 Mbps` TCP Cubic sender with bounded send-buffer backpressure (`64 KiB`), providing client-side congestion self-regulation without scheduler caps.

## Condition summary

| ID | INI | Layer | Study position | BG distribution | Target load | Dynamics | Mobility | Offline TCP mean / P10 (Mbps) | Study RB cost (RBG/Mbps) |
|---|---|---|---|---|---:|---|---|---:|---:|
| M01 | `m01_l1_base_good_static.ini` | L1 | `151.3 m` (good) | none | 0% | steady | static | 62.35 / 62.11 | 0.154 |
| M02 | `m02_l2_homo_rho050_med.ini` | L2 | `151.3 m` (good) | `good_homo` | 50% | `med` | static | 15.39 / 5.56 | 0.139 |
| M03 | `m03_l2_homo_rho075_med.ini` | L2 | `151.3 m` (good) | `good_homo` | 75% | `med` | static | 12.81 / 4.77 | 0.137 |
| M04 | `m04_l2_homo_rho100_med.ini` | L2 | `151.3 m` (good) | `good_homo` | 100% | `med` | static | 3.80 / 1.73 | 0.147 |
| M05 | `m05_l2_homo_rho100_high.ini` | L2 | `151.3 m` (good) | `good_homo` | 100% | `high` | static | 3.80 / 1.26 | 0.152 |
| M06 | `m06_l3_good_het_rho100_med.ini` | L3 | `151.3 m` (good) | `het` disc | 100% | `med` | static | 21.55 / 10.60 | 0.139 |
| M07 | `m07_l3_mid_het_rho100_med.ini` | L3 | `350.0 m` (mid) | `het` disc | 100% | `med` | static | 7.62 / 5.07 | 0.311 |
| M08 | `m08_l3_edge_het_rho050_med.ini` | L3 | `650.0 m` (edge) | `het` disc | 50% | `med` | static | 4.12 / 2.11 | 1.173 |
| M09 | `m09_l3_edge_het_rho075_med.ini` | L3 | `650.0 m` (edge) | `het` disc | 75% | `med` | static | 2.48 / 0.93 | 1.026 |
| M10 | `m10_l4_veh_traverse_het_rho050.ini` | L4 | `151–660 m` | `het` disc | 50% | `med` | `veh_traverse` | 24.67 / 11.14 | 0.229 |
| M11 | `m11_l4_ped_edge_het_rho050.ini` | L4 | `~650 m` (edge) | `het` disc | 50% | `med` | `ped_edge` | 5.66 / 3.19 | 1.001 |

## Path resolution

Relative `map_file` and `timeline_file` entries resolve from the `5g-network-emulator` working directory (`../configs/fikore/layered/timelines/*.ndjson`), matching the parent `configs/fikore/` convention.
