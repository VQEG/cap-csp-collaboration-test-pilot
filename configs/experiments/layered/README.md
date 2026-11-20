# Layered FikoRE SFV Experiments

These experiment configurations evaluate SFV player policies (`simple` B1 and `preload` B2) across the 11 layered FikoRE conditions (`M01`–`M11`) using the 18-video portrait HD catalog (`configs/content/sfv-portrait-hd-90s.json`).

Each run executes for `65 s` with:
- seed `20260927` and a unique `Global.run_id`;
- identical `tcp_connection_mode: "persistent"` across both `B1` (`simple`) and `B2` (`preload`) so player policies are compared over the exact same network stack;
- `256 KiB` TCP receive window matched to the `20 MHz` cell bandwidth-delay product;
- TCP acknowledgements carried over the FikoRE uplink (`ack_over_link: true`);
- application-paced `4.0 Mbps` TCP Cubic competing sessions (`background_iperf_ues`) on conditions `M02`–`M11`.

Run a single experiment from the repository root:

```bash
uv run capcsp run configs/experiments/layered/m04-b1.json output/layered/m04-b1
```

Summarize a batch of runs:

```bash
uv run capcsp report output/layered/* -o output/layered/report.md
```

## Multi-seed parametric grids

Multi-seed grids use `network.parametric_cell` to synthesize seed-dependent session arrival timelines and spatial UE placements from `Global.seed` on every replication (`1` study UE per cell, paired `B1` vs `B2` across seeds):

```bash
uv run capcsp grid -j 8 configs/grids/layered-core6.json
uv run capcsp grid -j 8 configs/grids/layered-m01-m11.json
uv run capcsp grid -j 8 configs/grids/parametric-load-sweep.json
```

