# Decision Status and Action Items

This file lists what we still need to decide or build. Agreed system and interface details live in the [architecture](architecture.md), [player API](player-api.md), [network backend API](network-backend-api.md), [FikoRE co-simulation specification](fikore-cosim.md), and [signaling specification](signaling.md). Evaluation details live in the [experiment specification](experiments.md) and the [results and scoring specification](results-and-scoring.md).

When we settle an open point, update the relevant specification and tick it off here.

## Current Blockers

- Final network conditions: the FikoRE condition pack C1–C8b in `configs/fikore/` is calibrated and runs end to end, but its values are provisional. We are waiting on SFV-specific bandwidth, RTT and loss values before we treat any condition as final.
- Player and video definitions: Michi's group defines the content catalogue, the quality ladder and the exact B1/B2 rules. Until then, runs use the three-video SFV test fixture, which is too short for the longer C6–C8 timelines.

## Player and Video Definitions

Owner: Michi's group. This covers the player behaviour (B1/B2 rules, prefetch parameters, swipe profiles) and the video definitions (catalogue, codec, ladder, segment durations and sizes).

- [x] Run the SFV player engine behind the Network Backend API, through the bridge in `capcsp/player/`.
- [ ] Write down the exact B1 and B2 rules, including MPS (max preloaded segments) and PSPV (preload segments per video) values, when preloading starts, how often it is re-evaluated, the bandwidth estimator and its safety margin, and how quality is chosen per video ([Player API](player-api.md#baseline-policies), [Prefetching Terminology](player-api.md#prefetching-terminology)).
- [ ] Define the content catalogue in the SFV `content.json` format: number of videos, video durations, codec, number of quality levels, bitrates per level and segment duration. This replaces the three 6 s fixture videos ([Experiments](experiments.md#content-registry)). Open review comments ask for VP9 or AV1, 4–5 tracks and segments of 3 s or less instead of H.264 with 3 × 5 s segments. The swipe delay model that Sara proposes also needs longer sessions: its [source study](https://arxiv.org/abs/2603.18575) used six videos of 23–60 s, with viewing times of 2–16 s per video.
- [x] Add width, height, codec and frame rate to the session record ([SFV PR #1](https://github.com/micseu/SFV-Reference-Implementation/pull/1)).
- [ ] Define the swipe profiles SP1–SP3 (mean watch time per profile) and whether SP1 (slow) is needed. Sara proposes a viewing pattern based on [Jung et al. (2025)](https://doi.org/10.1145/3715668.3736346): 36.51% of videos watched to 0–25%, 9.06% to 25–50%, 7.58% to 50–75% and 46.85% to 75–100%.
- [ ] Agree on a more realistic user model with Sara and Michi's group (Michi, Samuel), after the simple one (see [Common Harness](#common-harness)). Open points:
  - Does the watch time depend on the video duration, for example as the share of the video watched (the viewing pattern of [Jung et al. (2025)](https://doi.org/10.1145/3715668.3736346))?
  - Do long loading delays or stalls make users swipe earlier or leave?
  - How is the model seeded, so that comparisons across signaling levels and player behaviours see the same users?
  - If the swipe time depends on playback, it cannot be computed before a run. The model then belongs in SFV as a new `userModel` type, and the harness only passes its parameters.
- [ ] Set the loading-delay rule for the next video after a swipe ([Player API](player-api.md#swipes-and-buffer-invalidation), [Results and Scoring](results-and-scoring.md#per-video-metrics)).
- [ ] Check what other policy inputs we might need, for example the swipe history ([Player API](player-api.md#policy-contract)).
- [ ] Decide whether partial byte progress should run the policy again ([Player API](player-api.md#decision-triggers)).
- [ ] Decide whether requests need priorities in the first version ([Player API](player-api.md#policy-contract)).

Multi-video dash.js player for the real-HTTP validation (later milestone):

- [ ] Work out how the `MediaPlayer` instances share active and queued videos ([Player API](player-api.md#multi-video-dashjs-integration), [Architecture](architecture.md#offline-simulation-and-validation-paths)).
- [ ] Sketch the controller for feed order, swipes, download history, prefetching, and cancellation ([Player API](player-api.md#multi-video-dashjs-integration)).
- [ ] Pick the HTTP version, TLS setup, and connection limits for the mobile-app tests ([Network Backend API](network-backend-api.md#real-http-validation-architecture)).
- [ ] Make the dash.js validator write the same request events and session records as the Python harness ([Network Backend API](network-backend-api.md#real-http-validation-architecture), [Results and Scoring](results-and-scoring.md#session-record-format)).

## FikoRE Co-Simulation Adapter

Owner: Pablo

- [x] Build the `fikore-control-1` adapter and the `transport_fikore` backend ([FikoRE Co-simulation](fikore-cosim.md)).
- [x] Build and validate the transport models: TCP with Reno, CUBIC and Prague, cancellation, seeds, per-tag accounting and telemetry ([Network Backend API](network-backend-api.md#transport-models)).
- [x] Update the FikoRE PHY and MAC models.
- [x] Add the condition pack C1–C8b with timelines, and run B1/B2 on all nine conditions (PR #6).
- [x] Add FikoRE reports and plots per condition (PR #7).
- [ ] Find out why the two study UEs make almost no progress in C4 against 64 saturated background UEs with the 30 ms packet budget ([validation evidence](../configs/experiments/vqeg/validation.md)). C4 is not usable as a policy benchmark until this is resolved.
- [ ] Model core-network delay on the Link, including the ACK return path, instead of holding requests before submission ([Network Backend API](network-backend-api.md#latency-decomposition)). Keep this open until `backhaul_d` is complemented or replaced by a real core-network rate/queue model that can also represent a satellite link. This also replaces the temporary 15 Mbps grant cap in C7.
- [ ] Calibrate transport profiles and compare the offline model with real HTTP traffic.

## Network Conditions

Owners: Karan (SFV-specific target values) and Pablo (FikoRE realization).

- [x] Realize C1–C8 in FikoRE as calibration bands, with C8 split into C8a and C8b ([condition pack](../configs/fikore/README.md)).
- [ ] Karan: Supply SFV-specific C1–C5 profiles with bandwidth, RTT, and loss values ([meeting notes](https://docs.google.com/document/d/1JH8LQ5bbNjfzoaymn4FptL_odv6txNAn-5TOC6kdAFE/edit?tab=t.a7zfcry4xais#heading=h.b2prnlqzgt0a), [research plan](https://docs.google.com/document/d/1JH8LQ5bbNjfzoaymn4FptL_odv6txNAn-5TOC6kdAFE/edit?tab=t.vv9m6x6z2j60#heading=h.l92euqunbl3l)).
- [ ] Pablo: Recalibrate the condition pack once the final values are agreed.
- [ ] All: Decide whether to add a condition for the video throttling of US operators (about 2–2.5 Mbps), as suggested in a review comment.
- [ ] TBD: Choose synthetic or FikoRE-recorded traces for the `trace` backend and create them ([Experiments](experiments.md#trace-backend)).
- [ ] TBD: Match `synthetic_delay_ms` to the non-radio delay measured with live FikoRE ([Network Backend API](network-backend-api.md#latency-decomposition)).

## Common Harness

Owner: Werner

- [x] Build `capcsp run` and `capcsp report` with a KPI table ([Architecture](architecture.md#main-loop)).
- [x] Write the effective FikoRE INI for each run.
- [x] Add the `constant_rate` backend ([Network Backend API](network-backend-api.md#constant-rate-backend)).
- [ ] Check B2 on `constant_rate` against the analytical results of Wehner et al. before using FikoRE.
- [ ] Add the `trace` backend ([Network Backend API](network-backend-api.md#backend-implementations)).
- [ ] Expand experiment grids (conditions × signaling levels × player behaviour × swipe profiles × seeds) into single runs, instead of one hand-written JSON file per run ([Experiments](experiments.md#experiment-grid)).
- [x] Use the seeded `userModel` of SFV as a simple user model, with 2–16 s between swipes ([Experiments](experiments.md#experiment-grid)).
- [x] Wire CAP reports and the shared state table into the runner ([Signaling](signaling.md)).
- [ ] Call effective `set_ue_control()` and feed CSP fields into SFV policies so that L1–L3 change player behaviour ([Signaling](signaling.md)).
- [ ] Build the real-HTTP path: an origin server, with traffic through FikoRE in emulated mode ([Network Backend API](network-backend-api.md#real-http-validation-architecture)).
- [ ] Decide whether to unify the naming in `sessions/ue-<id>.json`: the SFV result object uses camelCase (`sessionRecord`, `terminationReason`), while the record inside it uses snake_case (`session_id`, `representation_intervals`).

## L3 Bidirectional Collaboration Controller

Owners: Pablo and Werner

- [x] Run a dummy controller in each step and log its decisions to `csp-control.jsonl` ([Collaboration](collaboration.md)).
- [ ] Turn each `CapReport` into scheduler weights and `rmax_mbps` caps ([Signaling](signaling.md#l3-network-controller-interface)).
- [ ] Choose how often the controller runs, how quickly it may change values, and how long changes remain active ([Signaling](signaling.md#l3-network-controller-interface)).
- [ ] Enable effective `TransportBackend.set_ue_control()` from a real `CSPController` ([Network Backend API](network-backend-api.md#interface-definition), [Message Reference](fikore-cosim-messages.md#set)). Priority and rate cap are already mapped to FikoRE; conditions must use proportional-fair scheduling or priority is ignored.

## L4 Lookahead Capacity Oracle

Owners: Werner and Pablo. Emir offered to define the oracle precisely.

- [ ] Run the full-buffer FikoRE cases and save the single-UE lookahead traces ([Signaling](signaling.md#l4-capacity-oracle), [Experiments](experiments.md#trace-backend)).
- [ ] Agree whether the multi-UE oracle is a fixed upper bound or changes with player demand ([Signaling](signaling.md#l4-capacity-oracle), [Player API](player-api.md#policy-contract)).

## Evaluation Metrics and QoE Models

Owners: Werner, Markus, Federica

- [x] Feed P.1204.1 Mode 0 segment scores into P.1203 ([Results and Scoring](results-and-scoring.md#qoe-estimation-models)).
- [x] Score for a mobile full HD display (1080x1920, portrait).
- [x] Count the wait after a swipe as initial loading delay.
- [x] Score each video with P.1203, and weight the session mean by played duration.
- [x] Score videos shorter than 1 minute, although P.1203 is specified from 1 minute.
- [ ] Replace the assumed constant good audio quality (O21 5.0) with real audio scores for future encodings; this needs audio in the content, the player and the session record ([Results and Scoring](results-and-scoring.md#qoe-estimation-models)).
- [x] Use the frame rate of each representation from the content file.
- [ ] Add the Hoßfeld QoE-fairness and Jain throughput-fairness metrics ([Results and Scoring](results-and-scoring.md#aggregate-evaluation-formulas)).
- [ ] Add the KPIs from the results specification that `capcsp` does not compute yet to `kpis.csv` and the report: per-video metrics such as time to first byte, watch duration and swipe-away, and the fairness metrics above ([Results and Scoring](results-and-scoring.md#session-record-format)).
