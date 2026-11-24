# Parametric Single-Cell 5G Conditions (`M01`–`M11`)

## Overview

`configs/experiments/layered/` and `configs/grids/{layered-core6,layered-m01-m11,parametric-load-sweep}.json` evaluate player behaviors over an 11-preset parametric single-cell 5G model (`M01`–`M11`) synthesized at runtime by `capcsp/network/parametric_cell.py`.

Every condition shares one physical 5G cell baseline and varies four orthogonal scenario axes:

1. **Normalized competing channel load (`load_rho`)**: `0.00`, `0.50`, `0.75`, `1.00` (sweepable up to `2.00` in custom configurations).
2. **Temporal session variability (`arrival_mode`)**: `poisson` (`M/M/inf` arrivals with `8 s` mean session hold) vs `mmpp` (2-state burst-modulated Poisson waves with `12 s` mean hold, `burst_amplitude = 0.65`, `burst_regime_s = 14 s`).
3. **Spatial geometry (`study_position`, `bg_spatial`)**: homogeneous good-SINR ring (`homogeneous_ring`) vs uniform-area cell disc (`cell_disk`), placing the study UE at `good` (`151.3 m`, MCS 25, ~`0.15 RBG/Mbps`), `mid` (`350.0 m`, MCS 9, ~`0.31 RBG/Mbps`), or `edge` (`650.0 m`, MCS 2, ~`1.0–1.2 RBG/Mbps`).
4. **Study-UE mobility (`study_mobility`)**: `static`, `pedestrian` (`3.6 km/h` walk at cell edge while competing background sessions stay at their sampled coordinates), and `vehicular_traverse` (`73.26 km/h` deterministic `151.3–660.0 m` center–edge–center traversal, `25 s` outbound and `25 s` return).

## Physical, scheduling, and reproducibility invariants

- **Cell baseline**: 3.5 GHz Urban Macro (`UMa` n78, `macroscopic_fading_map_URBAN_MACROCELL_3.5.json`), `20 MHz` channel bandwidth (`50 PRBs`, `12 RBGs` of `4 PRBs` per TTI), TDD `7/3/54`, `10 ms` one-way backhaul delay (`1 ms` jitter), 3GPP-style HARQ with in-order PDCP delivery (`harq_model: legacy_bler`, `order_pkts: true`) and per-class FIFO backhaul delivery.
- **Unconstrained scheduler**: Proportional Fair (`metric_type: 6`, `pf_alpha: 1.0`, `throughput_time_window_ms: 100.0`). **No `dl.rmax_mbps` or `ul.rmax_mbps` token-bucket cap is applied to any UE.**
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
| `M11` | Mobility | `650.0 m` (`edge`) | `cell_disk` | `0.50` | `poisson` | `pedestrian` | 5.66 / 3.19 | 1.001 |

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
