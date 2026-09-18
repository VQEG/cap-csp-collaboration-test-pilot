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

- [ ] Build the Unix socket adapter and its newline-delimited JSON parser ([FikoRE Co-simulation](fikore-cosim.md#transport-protocol), [Message Reference](fikore-cosim-messages.md)).
- [ ] Choose where the adapter hooks into FikoRE and where each request ID is stored ([FikoRE Co-simulation](fikore-cosim.md#adapter-requirements)).
- [ ] Check that the per-UE queue is the right cancellation boundary, then add it ([Network Backend API](network-backend-api.md#cancellation-and-waste-accounting), [FikoRE Co-simulation](fikore-cosim.md#request-cancellation)).
- [ ] Check that round-robin packet generation and a configurable 128 KiB sender window fit the current code ([FikoRE Co-simulation](fikore-cosim.md#concurrent-object-scheduling)).
- [ ] Split the run seed into separate seeds for fading, mobility, and background load ([FikoRE Co-simulation](fikore-cosim.md#configuration), [Experiments](experiments.md#reproducibility)).
- [ ] List the latency and rate metrics FikoRE can measure, and expose only those ([FikoRE Co-simulation](fikore-cosim.md#telemetry), [Signaling](signaling.md#csp-telemetry-fields)).
- [ ] Compare 10 ms reports with 1 ms runs and agree on an acceptable difference ([FikoRE Co-simulation](fikore-cosim.md#acceptance-criteria)).

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
- [ ] Add the network-control hook to the FikoRE adapter ([Network Backend API](network-backend-api.md#interface-definition), [Message Reference](fikore-cosim-messages.md#control-command)).

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
