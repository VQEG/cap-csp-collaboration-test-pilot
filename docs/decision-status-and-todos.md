# Decision Status and Action Items

This file lists what we still need to decide or build. Agreed system and interface details live in the [architecture](architecture.md), [player API](player-api.md), [network backend API](network-backend-api.md), [FikoRE co-simulation specification](fikore-cosim.md), and [signaling specification](signaling.md). Implementation and evaluation details live in the [implementation plan](implementation-plan.md), [experiment specification](experiments.md), and [results and scoring specification](results-and-scoring.md).

When we settle an open point, update the relevant specification and tick it off here.

## Multi-Video dash.js Integration

Owner: Michi

- [ ] Work out how the `MediaPlayer` instances share active and queued videos ([Player API](player-api.md#multi-video-dashjs-integration), [Architecture](architecture.md#offline-simulation-and-validation-paths)).
- [ ] Sketch the controller for feed order, swipes, download history, prefetching, and cancellation ([Player API](player-api.md#multi-video-dashjs-integration)).
- [ ] Pick the HTTP version, TLS setup, and connection limits for the mobile-app tests ([Network Backend API](network-backend-api.md#real-http-validation-architecture), [Implementation Plan](implementation-plan.md#real-traffic-validation)).
- [ ] Make the dash.js validator write the same request events and session records as the Python harness ([Network Backend API](network-backend-api.md#real-http-validation-architecture), [Results and Scoring](results-and-scoring.md#session-record-format)).

## FikoRE Co-Simulation Adapter

Owner: Pablo

- [x] Settle the co-simulation wire format ([FikoRE Co-simulation](fikore-cosim.md#transport-protocol), [Message Reference](fikore-cosim-messages.md)). It is `fikore-control-1`, newline-delimited JSON over a Unix socket with a credit barrier and tagged byte injection; the pilot adopts it instead of specifying a second protocol. Writing the client for it is harness-side work.
- [x] Choose where the adapter hooks into FikoRE and where each request ID is stored ([FikoRE Co-simulation](fikore-cosim.md#adapter-requirements)). The hook is the start of each simulation step, where scheduled commands are applied before the TTI runs. Request IDs stay in the Python adapter; only a four-byte tag travels on the data path.
- [x] Check that the per-UE queue is the right cancellation boundary, then add it ([Network Backend API](network-backend-api.md#cancellation-and-waste-accounting), [FikoRE Co-simulation](fikore-cosim.md#request-cancellation)). Nothing to add: the adapter stops injecting and the queue drains, which makes the sender window the real boundary and the in-flight tail exactly known.
- [x] Check that round-robin packet generation and a configurable 128 KiB sender window fit the design ([FikoRE Co-simulation](fikore-cosim.md#concurrent-object-scheduling)). They fit, and both live in the harness. The window collides with the PDCP delay budget under congestion, which is why driven UEs raise it.
- [x] Add the run seed, mixed per stream for fading, mobility and background load ([FikoRE Co-simulation](fikore-cosim.md#seeds), [Experiments](experiments.md#reproducibility)). Bigger than it looked: a boolean `random_v` cannot express the grid, and its reproducible setting also zeroes several variances. `[Global] seed` now sets it, and each stream is derived from it so that a seed sweep moves every generator independently.
- [x] Expose mean SINR and retransmitted bytes in the `state` block, alongside the byte, queue and latency counters the pilot asked for ([FikoRE Co-simulation](fikore-cosim.md#telemetry), [Signaling](signaling.md#csp-telemetry-fields)). Note there is no RTT anywhere in the emulator, only one-way latency.
- [x] Add per-tag byte accounting ([FikoRE Co-simulation](fikore-cosim.md#who-retransmits), [Message Reference](fikore-cosim-messages.md#inject)). A `get` returns delivered, expired, dropped and CE bytes per tag, with the drop broken down into queue and radio, and `forget` releases the tag.
- [ ] Add adapter-side recovery of lost bytes ([FikoRE Co-simulation](fikore-cosim.md#who-retransmits)). Harness-side work, and the half of the previous entry that the emulator cannot do for us: read the tag's lost bytes and reinject that many, so the object completes in full.
- [ ] Compare 10 ms windows with 1 ms runs and agree on an acceptable difference; measure the per-window round-trip cost before committing to a pushed report ([FikoRE Co-simulation](fikore-cosim.md#acceptance-criteria)).
- [x] Land the FikoRE-side capabilities listed in the [adapter requirements](fikore-cosim.md#adapter-requirements) in this repo's emulator submodule, which step 5 of the [build sequence](implementation-plan.md#build-sequence) depends on. The submodule now tracks `dev` on `nokia/5g-network-emulator`, which is where the pilot's emulator work lives until it reaches `main`.

## Baseline Policies and Player Heuristics

Owners: Michi and Werner

- [ ] Write down the exact B1 and B2 rules, including the MPS and PSPV limits ([Player API](player-api.md#baseline-policies), [Prefetching Terminology](player-api.md#prefetching-terminology)).
- [ ] Check what other policy inputs we might need ([Player API](player-api.md#policy-contract)).
- [ ] Decide whether partial byte progress should run the policy again ([Player API](player-api.md#decision-triggers)).
- [ ] Decide whether requests need priorities in the first version ([Player API](player-api.md#policy-contract)).
- [ ] Set the loading-delay rule for the next video after a swipe ([Player API](player-api.md#swipes-and-buffer-invalidation), [Results and Scoring](results-and-scoring.md#per-video-metrics)).

## L3 Bidirectional Collaboration Controller

Owners: Pablo and Werner

- [ ] Turn each `CapReport` into scheduler weights and `rmax_mbps` caps ([Signaling](signaling.md#l3-network-controller-interface)).
- [ ] Choose how often the controller runs, how quickly it may change values, and how long changes remain active ([Signaling](signaling.md#l3-network-controller-interface)).
- [ ] Add the network-control hook to the FikoRE adapter ([Network Backend API](network-backend-api.md#interface-definition), [Message Reference](fikore-cosim-messages.md#set)). The network-side action space is settled by the control protocol: priority and rate cap per UE at a stated TTI, plus SINR offset, mobility, background rate and delay budget. Conditions must use the proportional fair scheduler or priority is ignored.

## L4 Lookahead Capacity Oracle

Owners: Werner and Pablo.

- [ ] TBD: Run the full-buffer FikoRE cases and save the single-UE lookahead traces ([Signaling](signaling.md#l4-capacity-oracle), [Experiments](experiments.md#trace-backend)).
- [ ] TBD Agree whether the multi-UE oracle is a fixed upper bound or changes with player demand ([Signaling](signaling.md#l4-capacity-oracle), [Player API](player-api.md#policy-contract)).

## Media Content and Network Conditions

Owners: Karan (condition profiles) and Werner (content and configuration). Trace generation is unassigned.

- [ ] Karan: Supply SFV-specific C1-C5 profiles with bandwidth, RTT, and loss values ([meeting notes](https://docs.google.com/document/d/1JH8LQ5bbNjfzoaymn4FptL_odv6txNAn-5TOC6kdAFE/edit?tab=t.a7zfcry4xais#heading=h.b2prnlqzgt0a), [research plan](https://docs.google.com/document/d/1JH8LQ5bbNjfzoaymn4FptL_odv6txNAn-5TOC6kdAFE/edit?tab=t.vv9m6x6z2j60#heading=h.l92euqunbl3l)).
- [ ] Werner: Generate reproducible segment sizes for `content.yaml` ([Experiments](experiments.md#content-registry)).
- [ ] TBD: Add C1-C5 profiles to the network configuration ([Experiments](experiments.md#network-conditions)).
- [ ] TBD: Choose synthetic or FikoRE-recorded traces and create them ([Experiments](experiments.md#trace-backend)).
- [ ] TBD: Match `synthetic_delay_ms` to the non-radio delay measured with live FikoRE ([Network Backend API](network-backend-api.md#latency-decomposition)).

## Evaluation Metrics and QoE Models

Owner: Werner, Markus, Federica

- [ ] Feed P.1204.1 Mode 0 segment scores into the P.1203 session score ([Results and Scoring](results-and-scoring.md#qoe-estimation-models)).
- [ ] Add the Hoßfeld QoE-fairness and Jain throughput-fairness metrics ([Results and Scoring](results-and-scoring.md#aggregate-evaluation-formulas)).
