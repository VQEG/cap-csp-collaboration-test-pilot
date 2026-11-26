# Parametric Single-Cell 5G Conditions (`M01`–`M11`)

## Overview

`configs/experiments/layered/` and `configs/grids/{layered-core6,layered-m01-m11,parametric-load-sweep}.json` evaluate player behaviors over an 11-preset parametric single-cell 5G model (`M01`–`M11`) synthesized at runtime by `capcsp/network/parametric_cell.py`.

Every condition shares one physical 5G cell baseline and varies four orthogonal scenario axes:

1. **Normalized competing channel load (`load_rho`)**: `0.00`, `0.50`, `0.75`, `1.00` (sweepable up to `2.00` in custom configurations).
2. **Temporal session variability (`arrival_mode`)**: `poisson` (`M/M/inf` arrivals with `8 s` mean session hold) vs `mmpp` (2-state burst-modulated Poisson waves with `12 s` mean hold, `burst_amplitude = 0.65`, `burst_regime_s = 14 s`).
3. **Spatial geometry (`study_position`, `bg_spatial`)**: homogeneous good-SINR ring (`homogeneous_ring`) vs uniform-area cell disc (`cell_disk`), placing the study UE at `good` (`151.3 m`, MCS 25, ~`0.15 RBG/Mbps`), `mid` (`350.0 m`, MCS 9, ~`0.31 RBG/Mbps`), or `edge` (`650.0 m`, MCS 2, ~`1.0–1.2 RBG/Mbps`).
4. **Study-UE mobility (`study_mobility`)**: `static`, `urban_bus` (`25 km/h` deterministic stop-and-go along a `220–650 m` corridor: `15 s` driving, then `10 s` standing at a stop, repeated every `25 s`, while competing background sessions stay at their sampled coordinates), and `vehicular_traverse` (`73.26 km/h` deterministic `151.3–660.0 m` center–edge–center traversal, `25 s` outbound and `25 s` return).

## Physical, scheduling, and reproducibility invariants

- **Cell baseline**: 3.5 GHz Urban Macro (`UMa` n78, `macroscopic_fading_map_URBAN_MACROCELL_3.5.json`), `20 MHz` channel bandwidth (`50 PRBs`, `12 RBGs` of `4 PRBs` per TTI), TDD `7/3/54`, `10 ms` one-way backhaul delay (`1 ms` jitter), 3GPP-style HARQ with in-order PDCP delivery (`harq_model: legacy_bler`, `order_pkts: true`) and per-class FIFO backhaul delivery.
- **Unconstrained scheduler**: Proportional Fair (`metric_type: 6`, `pf_alpha: 1.0`, `throughput_time_window_ms: 100.0`). **No `dl.rmax_mbps` or `ul.rmax_mbps` token-bucket cap is applied to any UE in `M01`–`M11`.** The optional `parametric_cell.study_dl_rmax_mbps` knob (default `null`) is the only way to install a static study-UE downlink cap; see [Static downlink cap and L1 plan coupling](#static-downlink-cap-and-l1-plan-coupling).
- **Competing SFV-like flows**: Competing UEs (`backgroundSfV`) attach and detach according to synthesized session timelines at freshly sampled spatial coordinates, driven in co-simulation by application-paced `4.0 Mbps` TCP Cubic senders with bounded send-buffer backpressure (`64 KiB`).
- **Deterministic runtime synthesis**: `synthesize_parametric_cell()` derives its RNG strictly from `Global.seed` (`SHA-256("capcsp-parametric-cell::<seed>")`), writes `fikore-effective.ini` and `fikore-timeline.ndjson` into each run's output directory, and produces byte-identical scenarios across paired `B1`/`B2` runs and re-runs without checking static `.ini` or `.ndjson` files into git.

## Condition summary (`M01`–`M11`)

The Core-6 screening subset (`configs/grids/layered-core6.json`) comprises `M01`, `M04`, `M05`, `M07`, `M09`, and `M10`.

| ID | Group | Study position | BG distribution | `load_rho` | Arrivals | Study mobility | Backlogged TCP mean / P10 (Mbps) | Study RB cost (RBG/Mbps) |
|---|---|---|---|---:|---|---|---:|---:|
| `M01` | Baseline | `151.3 m` (`good`) | `none` | `0.00` | `poisson` | `static` | 62.35 / 62.11 | 0.154 |
| `M02` | Center load | `151.3 m` (`good`) | `homogeneous_ring` | `0.50` | `poisson` | `static` | 15.39 / 5.56 | 0.139 |
| `M03` | Center load | `151.3 m` (`good`) | `homogeneous_ring` | `0.75` | `poisson` | `static` | 12.81 / 4.77 | 0.137 |
| `M04` | Center load | `151.3 m` (`good`) | `homogeneous_ring` | `1.00` | `poisson` | `static` | 3.80 / 1.73 | 0.147 |
| `M05` | Center waves | `151.3 m` (`good`) | `homogeneous_ring` | `1.00` | `mmpp` | `static` | 3.80 / 1.26 | 0.152 |
| `M06` | Spatial / Edge | `151.3 m` (`good`) | `cell_disk` | `1.00` | `poisson` | `static` | 21.55 / 10.60 | 0.139 |
| `M07` | Spatial / Edge | `350.0 m` (`mid`) | `cell_disk` | `1.00` | `poisson` | `static` | 7.62 / 5.07 | 0.311 |
| `M08` | Spatial / Edge | `650.0 m` (`edge`) | `cell_disk` | `0.50` | `poisson` | `static` | 4.12 / 2.11 | 1.173 |
| `M09` | Spatial / Edge | `650.0 m` (`edge`) | `cell_disk` | `0.75` | `poisson` | `static` | 2.48 / 0.93 | 1.026 |
| `M10` | Mobility | `151.3–660.0 m` | `cell_disk` | `0.50` | `poisson` | `vehicular_traverse` | 24.67 / 11.14 | 0.229 |
| `M11` | Mobility | `220–650 m` corridor | `cell_disk` | `0.50` | `poisson` | `urban_bus` | 15.63 / 9.15 | 0.345 |

### `M11` urban bus stop-and-go

The study UE starts at `220 m` and drives along the `220–650 m` corridor at `25 km/h` (`6.94 m/s`, inside the `20–30 km/h` urban transit band). Every `25 s` cycle drives for `15 s` and stands for `10 s` at a bus stop (`mobility.speed_kmh = 0`). The position advances `104.17 m` per driving phase, so the first stops are at `324.17 m` (`t = 15–25 s`), `428.33 m` (`t = 40–50 s`), and `532.50 m` (`t = 65 s`). On longer runs the bus reflects at `650 m` and drives back. The synthesizer emits a `250 ms` waypoint timeline for `ue/studyVqeg`; the static `[UE]` header keeps `mobility_type: 0`, and `backgroundSfV` UEs never move.

`M11` measurement: 3 seeds (`20260927`–`20260929`), `65 s` runs, one backlogged TCP Cubic flow (`4 MiB` receive window, `ack_over_link: true`, persistent connection) on the study UE. Mean and P10 pool the `1 s` goodput windows from `5 s` to `65 s` (`180` windows): mean `15.63 Mbps`, P10 `9.15 Mbps` (per-seed means `16.92`, `13.97`, `16.02` Mbps). The RB cost is the mean number of RBGs assigned per DL TTI divided by the mean goodput of the same run on a load-free copy of the cell (`load_rho = 0.0`, same trajectory): `0.345 RBG/Mbps` (per-seed `0.345`, `0.351`, `0.339`; load-free mean goodput `19.92 Mbps`). With this harness the `M01` row reproduces within 1.5 % for throughput (`61.5–61.7` vs `62.35 Mbps`) and 3 % for RB cost (`0.159` vs `0.154`), but the `M10` RB cost is `0.31` instead of the `0.229` listed above, so compare RB-cost values across rows with care until the full 20-seed grid recalibrates all rows with one method. The `M11` RTT and loss bands of the Simulator Explorer are not yet recalibrated for the bus trajectory.

## Static downlink cap and L1 plan coupling

`parametric_cell.study_dl_rmax_mbps` (`null` or `0.1`–`1000.0` Mbps) emits one `dl.rmax_mbps` control command for `ue/studyVqeg` at TTI `0`, so FikoRE caps the study-UE downlink for the whole run, on any preset (also on `M01`, which otherwise has no timeline). A backlogged TCP flow on `M01` capped at `2.5 Mbps` reaches `2.27 Mbps` goodput.

When `plan_downlink_mbps_by_ue` is not set and `network_backend` is `transport_fikore`, `capcsp run` uses the cap as the plan rate of every UE. The player sees `plan_downlink_mbps` only from `"signaling_level": "L1"`, so paired configs that differ only in `signaling_level` isolate the value of telling the player the cap. They live in `configs/experiments/l1-cap/` (kept apart from `configs/experiments/layered/`, which holds exactly the 22 uncapped `M01`–`M11` configs):

| Config | Signaling level | Behavior | Network |
|---|---|---|---|
| `m01-cap2p5-l0-b1.json`, `m01-cap2p5-l0-b2.json` | `L0` | `simple` / `preload` | `M01`, `study_dl_rmax_mbps: 2.5` |
| `m01-cap2p5-l1-b1.json`, `m01-cap2p5-l1-b2.json` | `L1` (plan `2.5 Mbps` visible) | `simple` / `preload` | `M01`, `study_dl_rmax_mbps: 2.5` |

```bash
uv run capcsp run configs/experiments/l1-cap/m01-cap2p5-l0-b1.json
uv run capcsp run configs/experiments/l1-cap/m01-cap2p5-l1-b1.json
```

## Running single scenarios and grids

```bash
# Single paired-swipe scenario (synthesizes INI + timeline from preset M04)
uv run capcsp run configs/experiments/layered/m04-b1.json
uv run capcsp run configs/experiments/layered/m04-b2.json

# Core-6 screening grid (6 conditions x 2 behaviors x 5 seeds = 60 cells)
uv run capcsp grid configs/grids/layered-core6.json --jobs 14

# Full M01-M11 evaluation grid (11 conditions x 2 behaviors x 20 seeds = 440 cells)
uv run capcsp grid configs/grids/layered-m01-m11.json --jobs 14

# Continuous load_rho sweep on a custom 5G cell (5 loads x 2 behaviors x 3 seeds = 30 cells)
uv run capcsp grid configs/grids/parametric-load-sweep.json --jobs 14
```

> **Note on `configs/content/sfv-portrait-hd-90s.json`:** This 18-clip (`8 s` / `4 x 2 s` segments, 6-rung Full HD portrait `270x480`–`1080x1920`) catalogue is a **provisional synthetic test asset** used to keep `65 s` multi-swipe runs well inside the feed until the pilot's final encoded SFV content catalogue lands.
