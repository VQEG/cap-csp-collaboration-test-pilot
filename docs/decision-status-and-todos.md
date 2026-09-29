# Decision Status and Action Items

This file lists what we still need to decide or build. Agreed system and interface details live in the [architecture](architecture.md), [player API](player-api.md), [network backend API](network-backend-api.md), [FikoRE co-simulation specification](fikore-cosim.md), and [signaling specification](signaling.md). Implementation and evaluation details live in the [implementation plan](implementation-plan.md), [experiment specification](experiments.md), and [results and scoring specification](results-and-scoring.md).

When we settle an open point, update the relevant specification and tick it off here.

## Multi-Video dash.js Integration

Owner: Michi

- [x] Validate the Node.js player engine behind the Network Backend API through the SFV-VQEG v0.7.2 temporary bridge: it receives `NetworkStep` events and calls submit and cancel, never FikoRE wire messages ([Offline Transport Validation](offline-transport-validation.md)).
- [ ] Move the validated temporary Python–Node bridge into the permanent common harness.
- [ ] Work out how the `MediaPlayer` instances share active and queued videos ([Player API](player-api.md#multi-video-dashjs-integration), [Architecture](architecture.md#offline-simulation-and-validation-paths)).
- [ ] Sketch the controller for feed order, swipes, download history, prefetching, and cancellation ([Player API](player-api.md#multi-video-dashjs-integration)).
- [ ] Pick the HTTP version, TLS setup, and connection limits for the mobile-app tests ([Network Backend API](network-backend-api.md#real-http-validation-architecture), [Implementation Plan](implementation-plan.md#real-traffic-validation)).
- [ ] Make the dash.js validator write the same request events and session records as the Python harness ([Network Backend API](network-backend-api.md#real-http-validation-architecture), [Results and Scoring](results-and-scoring.md#session-record-format)).

## FikoRE Co-Simulation Adapter

Owner: Pablo

- [x] Settle the co-simulation wire format ([FikoRE Co-simulation](fikore-cosim.md), [Message Reference](fikore-cosim-messages.md)). It is `fikore-control-1` with barrier credit, tagged injection and replayable `events`.
- [x] Implement the generic client and process wrapper in the FikoRE repository. `FikoreLink` performs handshake, grants, event-cursor recovery and tag lifetime management.
- [x] Implement transport recovery and object lifecycle. `TransportBackend` uses TCP ACK/SACK/RTO recovery (or the explicit ideal diagnostic mode), and cancellation drains the already-admitted data and ACK tails.
- [x] Implement and externally check Reno, CUBIC and Prague; keep transport and Link selection independent ([Network Backend API](network-backend-api.md#transport-models)).
- [x] Add the run seed, mixed per stream for fading, mobility and background load ([FikoRE Co-simulation](fikore-cosim.md#seeds), [Experiments](experiments.md#reproducibility)). Bigger than it looked: a boolean `random_v` cannot express the grid, and its reproducible setting also zeroes several variances. `[Global] seed` now sets it, and each stream is derived from it so that a seed sweep moves every generator independently.
- [x] Expose compact byte, queue, latency, SINR, mobility and retransmission telemetry. Transport RTT is measured separately from one-way PDCP latency.
- [x] Add per-tag incremental accounting with cursor replay, resynchronisation, bounded retention and `forget` ([Message Reference](fikore-cosim-messages.md#events)).
- [x] Validate slot-by-slot Python stepping with 300 s object, loss and Prague campaigns; checked evidence lives in the FikoRE submodule.
- [x] Validate the SFV v0.7.2 mock/FikoRE seam with two UEs, B1/B2, swipes and cancellation accounting ([Offline Transport Validation](offline-transport-validation.md)).
- [x] Advance this repository's emulator submodule to FikoRE `dev` after the transport/control merge.
- [ ] Integrate the thin pilot-specific backend wiring and permanent Python–Node bridge in the common harness.
- [ ] Calibrate transport profiles and compare the offline model with real HTTP traffic.

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
- [ ] Connect the L3 policy in the common harness to the implemented `TransportBackend.set_ue_control()` hook ([Network Backend API](network-backend-api.md#interface-definition), [Message Reference](fikore-cosim-messages.md#set)). Priority and rate cap are already mapped to FikoRE; conditions must use proportional-fair scheduling or priority is ignored.

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
