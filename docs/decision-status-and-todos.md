# Decision Status and Action Items

This file lists what we still need to decide or build. Agreed system and interface details live in the [architecture](architecture.md), [player API](player-api.md), [network backend API](network-backend-api.md), [FikoRE co-simulation specification](fikore-cosim.md), and [signaling specification](signaling.md). Implementation and evaluation details live in the [implementation plan](implementation-plan.md), [experiment specification](experiments.md), and [results and scoring specification](results-and-scoring.md).

When we settle an open point, update the relevant specification and tick it off here.

## Current Blockers

- Final network conditions: the FikoRE condition pack C1–C8b in `configs/fikore/` is calibrated and runs end to end, but its values are provisional. We are waiting on SFV-specific bandwidth, RTT and loss values before we treat any condition as final.
- Player and video definitions: Michi's group defines the content catalogue, the quality ladder and the exact B1/B2 rules. Until then, runs use the three-video SFV test fixture, which is too short for the longer C6–C8 timelines.

## Player and Video Definitions

Owner: Michi's group. This covers the player behaviour (B1/B2 rules, prefetch parameters, swipe profiles) and the video definitions (catalogue, codec, ladder, segment durations and sizes).

- [x] Validate the Node.js player engine behind the Network Backend API through the SFV-VQEG v0.7.2 temporary bridge: it receives `NetworkStep` events and calls submit and cancel, never FikoRE wire messages ([Offline Transport Validation](offline-transport-validation.md)).
- [x] Move the validated temporary Python–Node bridge into the common harness. Done by Werner in `capcsp/player/`, adapted from the SFV-VQEG v0.7.2 bridge.
- [ ] Write down the exact B1 and B2 rules, including MPS (max preloaded segments) and PSPV (preload segments per video) values, when preloading starts, how often it is re-evaluated, the bandwidth estimator and its safety margin, and how quality is chosen per video ([Player API](player-api.md#baseline-policies), [Prefetching Terminology](player-api.md#prefetching-terminology)).
- [ ] Define the content catalogue in the SFV `content.json` format: number of videos, video durations, codec, number of quality levels, bitrates per level and segment duration. This replaces `content.yaml` in the specification and the three 6 s fixture videos ([Experiments](experiments.md#content-registry)). Open review comments ask for VP9 or AV1, 4–5 tracks and segments of 3 s or less instead of H.264 with 3 × 5 s segments.
- [ ] Define the swipe profiles SP1–SP3 (mean watch time per profile) and whether SP1 (slow) is needed. The harness currently takes fixed `swipeTimesS` per session; Werner will generate them from the chosen profile and seed.
- [ ] Set the loading-delay rule for the next video after a swipe ([Player API](player-api.md#swipes-and-buffer-invalidation), [Results and Scoring](results-and-scoring.md#per-video-metrics)).
- [ ] Check what other policy inputs we might need, for example the swipe history ([Player API](player-api.md#policy-contract)).
- [ ] Decide whether partial byte progress should run the policy again ([Player API](player-api.md#decision-triggers)).
- [ ] Decide whether requests need priorities in the first version ([Player API](player-api.md#policy-contract)).

Multi-video dash.js player for the real-HTTP validation (later milestone):

- [ ] Work out how the `MediaPlayer` instances share active and queued videos ([Player API](player-api.md#multi-video-dashjs-integration), [Architecture](architecture.md#offline-simulation-and-validation-paths)).
- [ ] Sketch the controller for feed order, swipes, download history, prefetching, and cancellation ([Player API](player-api.md#multi-video-dashjs-integration)).
- [ ] Pick the HTTP version, TLS setup, and connection limits for the mobile-app tests ([Network Backend API](network-backend-api.md#real-http-validation-architecture), [Implementation Plan](implementation-plan.md#real-traffic-validation)).
- [ ] Make the dash.js validator write the same request events and session records as the Python harness ([Network Backend API](network-backend-api.md#real-http-validation-architecture), [Results and Scoring](results-and-scoring.md#session-record-format)).

## FikoRE Co-Simulation Adapter

Owner: Pablo

- [x] Implement the end-to-end `fikore-control-1` adapter: barrier stepping, tagged injection, replayable events and timelines, process management, and `transport_fikore` wiring in the common harness ([FikoRE Co-simulation](fikore-cosim.md), [Message Reference](fikore-cosim-messages.md)).
- [x] Implement and validate the transport and observability path: TCP recovery and persistent connections, Reno/CUBIC/Prague, cancellation, reproducible seeds, per-tag accounting, compact radio/queue telemetry, and long-running mock/FikoRE/SFV campaigns ([Network Backend API](network-backend-api.md#transport-models), [Offline Transport Validation](offline-transport-validation.md)).
- [x] Update the FikoRE physical and MAC models, default profiles and calibrated condition support, and advance the submodule to the corresponding `dev` snapshot.
- [x] Add the calibrated condition pack C1–C7, C8a and C8b with control timelines, replay the timelines through `FikoreLink`, and run the B1/B2 matrix on all nine conditions (`configs/fikore/`, `configs/experiments/vqeg/`, PR #6).
- [x] Add the offline FikoRE reports and plots for each condition (`configs/fikore/results/`, PR #7).
- [ ] Find out why the two study UEs make almost no progress in C4 against 64 saturated background UEs with the 30 ms packet budget ([validation evidence](../configs/experiments/vqeg/validation.md)). C4 is not usable as a policy benchmark until this is resolved.
- [ ] Model core-network delay on the Link, including the ACK return path, instead of holding requests before submission ([Network Backend API](network-backend-api.md#latency-decomposition)). Keep this open until `backhaul_d` is complemented or replaced by a real core-network rate/queue model that can also represent a satellite link. This also replaces the temporary 15 Mbps grant cap in C7.
- [ ] Calibrate transport profiles and compare the offline model with real HTTP traffic.

## Network Conditions

Owners: Karan (SFV-specific target values) and Pablo (FikoRE realization).

- [x] Provide a first FikoRE realization of C1–C8 as calibration bands (C8 split into load-driven C8a and coverage-driven C8b), see the [condition pack README](../configs/fikore/README.md).
- [ ] Karan: Supply SFV-specific C1–C5 profiles with bandwidth, RTT, and loss values ([meeting notes](https://docs.google.com/document/d/1JH8LQ5bbNjfzoaymn4FptL_odv6txNAn-5TOC6kdAFE/edit?tab=t.a7zfcry4xais#heading=h.b2prnlqzgt0a), [research plan](https://docs.google.com/document/d/1JH8LQ5bbNjfzoaymn4FptL_odv6txNAn-5TOC6kdAFE/edit?tab=t.vv9m6x6z2j60#heading=h.l92euqunbl3l)).
- [ ] Pablo: Recalibrate the condition pack once the final values are agreed.
- [ ] All: Decide whether to add a condition for the video throttling of US operators (about 2–2.5 Mbps), as suggested in a review comment.
- [ ] TBD: Choose synthetic or FikoRE-recorded traces for the `trace` backend and create them ([Experiments](experiments.md#trace-backend)).
- [ ] TBD: Match `synthetic_delay_ms` to the non-radio delay measured with live FikoRE ([Network Backend API](network-backend-api.md#latency-decomposition)).

## Common Harness

Owner: Werner

- [x] Build the first runner, KPI table and report (`capcsp run`, `capcsp report`) for the `mock` and `transport_fikore` backends ([Architecture](architecture.md#main-loop)).
- [x] Render the effective FikoRE INI per run, validate overrides and map UE numbers by scenario block order.
- [ ] Add the `constant_rate` and `trace` backends ([Network Backend API](network-backend-api.md#backend-implementations)). `constant_rate` is needed to check B2 against the analytical results of Wehner et al. before using FikoRE.
- [ ] Expand experiment grids (conditions × signaling levels × player behaviour × swipe profiles × seeds) into single runs, instead of one hand-written JSON file per run ([Experiments](experiments.md#experiment-grid)).
- [ ] Generate swipe times from the swipe profile and seed.
- [ ] Call `set_ue_control()` and the player's CAP reports from the runner, so that L1 to L3 can run ([Signaling](signaling.md)).
- [ ] Pass `NetworkTelemetryReceived` into the SFV engine for L2 policies. The runner logs telemetry, but the engine has no input for it yet.

## L3 Bidirectional Collaboration Controller

Owners: Pablo and Werner

- [ ] Turn each `CapReport` into scheduler weights and `rmax_mbps` caps ([Signaling](signaling.md#l3-network-controller-interface)).
- [ ] Choose how often the controller runs, how quickly it may change values, and how long changes remain active ([Signaling](signaling.md#l3-network-controller-interface)).
- [ ] Connect the L3 policy in the common harness to the implemented `TransportBackend.set_ue_control()` hook ([Network Backend API](network-backend-api.md#interface-definition), [Message Reference](fikore-cosim-messages.md#set)). Priority and rate cap are already mapped to FikoRE; conditions must use proportional-fair scheduling or priority is ignored.

## L4 Lookahead Capacity Oracle

Owners: Werner and Pablo. Emir offered to define the oracle precisely.

- [ ] Run the full-buffer FikoRE cases and save the single-UE lookahead traces ([Signaling](signaling.md#l4-capacity-oracle), [Experiments](experiments.md#trace-backend)).
- [ ] Agree whether the multi-UE oracle is a fixed upper bound or changes with player demand ([Signaling](signaling.md#l4-capacity-oracle), [Player API](player-api.md#policy-contract)).

## Evaluation Metrics and QoE Models

Owners: Werner, Markus, Federica

- [ ] Feed P.1204.1 Mode 0 segment scores into the P.1203 session score ([Results and Scoring](results-and-scoring.md#qoe-estimation-models)).
- [ ] Add the Hoßfeld QoE-fairness and Jain throughput-fairness metrics ([Results and Scoring](results-and-scoring.md#aggregate-evaluation-formulas)).
- [ ] Add the KPIs from the results specification that `capcsp` does not compute yet to `kpis.csv` and the report: P.1203 scores (O46, O35, O23) per video and session, per-video metrics such as time to first byte, watch duration and swipe-away, and the fairness metrics above ([Results and Scoring](results-and-scoring.md#session-record-format)).
