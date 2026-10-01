# VQEG FikoRE condition runs

These nine experiment files run the existing two-UE B1/B2 SFV fixture over every contributed FikoRE condition: C1–C7, C8a and C8b.

Each run:

- uses FikoRE seed `20260927`;
- preserves the condition's packet-delay budget and stochastic setting;
- sends TCP acknowledgements over the FikoRE uplink;
- uses a 1 MiB receive window so TCP flow control does not mask C1 or C7;
- runs for the condition's full configured duration;
- stores the rendered scenario as `fikore-effective.ini`;
- fails if a scheduled control command is malformed, late or rejected.

Run one condition from the repository root:

```bash
uv run capcsp run \
  configs/experiments/vqeg/c1-b1-b2.json \
  output/vqeg/c1
```

Run the complete matrix:

```bash
for config in configs/experiments/vqeg/*-b1-b2.json; do
  name="$(basename "$config" -b1-b2.json)"
  uv run capcsp run "$config" "output/vqeg/$name"
done
```

Then compare the outputs:

```bash
uv run capcsp report output/vqeg/* -o output/vqeg/report.md
```

The current SFV fixture contains three short videos. It is sufficient to validate end-to-end player integration, byte conservation, effective scenario rendering and timeline replay. Some late C6/C8 events occur after the finite content has been downloaded, so this matrix is not by itself a performance validation of every dynamic condition. A future long or repeating content catalog should be used for application-level sensitivity measurements across the complete C6–C8 timelines.

C2 uses a real per-UE 25 Mbps nominal downlink grant cap. C7 uses a 15 Mbps nominal grant cap only as a temporary proxy for satellite-backhaul capacity, combined with 150 ms one-way backhaul delay. Replace C7's proxy with a backhaul/PDCP-ingress shaper when one becomes available.
