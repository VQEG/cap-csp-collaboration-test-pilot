import type { RepositoryId } from "@/data/repositories";

// Hover texts for every term marked with <GlossaryTerm id="…"> in the page.
// Text in `backticks` is rendered as code. Sources: docs/signaling.md,
// docs/network-backend-api.md, docs/collaboration.md and the code.

export type GlossaryKind =
  | "component"
  | "data type"
  | "field"
  | "method"
  | "IPC message"
  | "event"
  | "output file"
  | "config key"
  | "concept";

export interface GlossaryField {
  name: string;
  type: string;
  description: string;
}

export interface GlossaryEntry {
  name: string;
  kind: GlossaryKind;
  repository?: RepositoryId;
  definedIn?: string;
  /** Set when the term only exists on a branch, for example "PR #12". */
  availability?: string;
  summary: string;
  fields?: GlossaryField[];
}

const CSP_FIELD_LIST: GlossaryField[] = [
  { name: "updated_at_s", type: "float", description: "Simulation time of the write that produced these values." },
  { name: "plan_downlink_mbps", type: "float | None", description: "Provisioned subscriber downlink rate from the experiment config. Visible from L1." },
  { name: "achieved_throughput_mbps", type: "float | None", description: "Delivered downlink throughput over the last telemetry window. Visible from L2." },
  { name: "rtt_ms", type: "float | None", description: "Round-trip time of the modelled TCP ACK path. Visible from L2." },
  { name: "loss_rate", type: "float | None", description: "Share of bytes dropped in the transport window. Visible from L2." },
  { name: "congestion_rate", type: "float | None", description: "ECN CE marking rate; null while L4S is off. Visible from L2." },
];

const CAP_REPORT_FIELD_LIST: GlossaryField[] = [
  { name: "time_s", type: "float", description: "Simulation time of the report." },
  { name: "is_stalled", type: "bool", description: "The player is currently rebuffering." },
  { name: "playable_buffer_s", type: "float", description: "Seconds of the current video that can play without new data." },
  { name: "current_video_id", type: "str", description: "Video the user is watching." },
  { name: "swipe_rate_per_s", type: "float", description: "Recent swipe rate of the user." },
];

export const GLOSSARY = {
  // Components
  NetworkStepHarness: {
    name: "SFVNetworkStepHarness",
    kind: "component",
    repository: "sfv",
    definedIn: "sfv-reference-implementation/src/cosim/, run by scripts/cosim-network-step-worker.mjs",
    summary:
      "Node.js side of the player bridge, in the SFV repository. Holds one `SFVSimulationController` per UE, applies each `network_step` to them and answers with `player_actions`. It passes changed `collaboration.csp_by_ue` fields to `applyCspUpdate` and answers `cap_reports` with `drainCapReports`.",
  },
  SFVSimulationController: {
    name: "SFVSimulationController",
    kind: "component",
    repository: "sfv",
    definedIn: "sfv-reference-implementation/src/simulation/SFVSimulationController.js",
    summary:
      "Simulated short-form video player for one UE: playback clock, buffer, swipes between videos and the request queue. It calls the configured rule to decide what to download next.",
  },
  SFVCurrentVideoRule: {
    name: "SFVCurrentVideoRule (B1)",
    kind: "component",
    repository: "sfv",
    definedIn: "sfv-reference-implementation/src/rules/SFVCurrentVideoRule.js",
    summary:
      "Player behavior B1. Loads the manifest of the current video and keeps `activeBufferTargetSegments` segments of it buffered. Does not preload other videos and reads no CSP fields.",
  },
  SFVMultiVideoPrefetchRule: {
    name: "SFVMultiVideoPrefetchRule (B2)",
    kind: "component",
    repository: "sfv",
    definedIn: "sfv-reference-implementation/src/rules/SFVMultiVideoPrefetchRule.js",
    summary:
      "Player behavior B2. Does what B1 does, then preloads up to `preload_segments_per_video` segments of the next videos in the playlist, capped by `max_preload_segments`. Reads no CSP fields yet.",
  },
  Runner: {
    name: "Runner",
    kind: "component",
    repository: "harness",
    definedIn: "capcsp/runner/run.py, capcsp/player/bridge.py",
    summary:
      "Python process that owns the simulation clock. It loads the experiment config, starts the backend and the Node player, runs the step loop, checks byte conservation and writes all run outputs. It also owns the shared state table and the collaboration tick.",
  },
  TransportBackend: {
    name: "TransportBackend",
    kind: "component",
    repository: "fikore",
    definedIn: "5g-network-emulator/transport/fikore_transport/backend.py",
    summary:
      "Implements the `NetworkBackend` API on top of a modelled TCP stack (CUBIC or Reno) per UE. Turns byte requests into TCP segments, sends them over `FikoreLink` and reports delivery and cancellations. Its `NetworkTelemetrySampler` is the backend's CSP telemetry source. Wrapped by `capcsp/network/transport_fikore.py` in the harness.",
  },
  FikoreLink: {
    name: "FikoreLink",
    kind: "component",
    repository: "fikore",
    definedIn: "5g-network-emulator/transport/fikore_transport/fikore_link.py",
    summary:
      "Drives the FikoRE process over its control protocol on a Unix socket. Each TTI it injects packets, advances FikoRE and reads back grants, deliveries and drops.",
  },
  FikoRE: {
    name: "FikoRE",
    kind: "component",
    repository: "fikore",
    definedIn: "5g-network-emulator/",
    summary:
      "5G RAN emulator (Nokia). Models radio channel, HARQ, scheduler and background UEs at 1 ms TTI. A condition is a base INI file plus an optional timeline of runtime changes.",
  },
  MockNetworkBackend: {
    name: "MockNetworkBackend",
    kind: "component",
    repository: "harness",
    definedIn: "capcsp/network/mock.py",
    summary:
      "Deterministic test backend. Shares a fixed budget of 80,000 bytes per 10 ms step (64 Mbps) across all active requests. No radio, no TCP, no delay and no telemetry source.",
  },
  ConstantRateBackend: {
    name: "ConstantRateBackend",
    kind: "component",
    repository: "harness",
    definedIn: "capcsp/network/constant_rate.py (backend name constant_rate)",
    summary:
      "Deterministic backend that gives every UE its own constant downlink rate, so UEs never compete. The ready requests of a UE share its rate equally (processor sharing). A request gets no bytes until `synthetic_delay_ms` after submission. Bytes are kept as exact fractions; events report whole bytes at the step time. `set_ue_control` caps the UE rate with `rmax_mbps`; `priority` is recorded only. Not a TCP, HTTP or radio model, and no telemetry source. It is the network model of the analytical results of Wehner et al.",
  },
  SharedStateTable: {
    name: "SharedStateTable",
    kind: "component",
    repository: "harness",
    definedIn: "capcsp/shared_state/table.py",
    summary:
      "Per-UE store of the latest `CspFields` and `CapReport`. Writes always store the full values; reads apply the signaling-level filter. Every change is appended to `shared-state.jsonl`. The Node player never touches it directly.",
  },
  DummyCSPController: {
    name: "DummyCSPController",
    kind: "component",
    repository: "harness",
    definedIn: "capcsp/collaboration/csp_controller.py",
    summary:
      "Placeholder L3 controller, enabled with `csp_controller: \"dummy\"`. Each step it reads the latest `CapReport` of every UE; on a stall it proposes the baseline priority × 2 (baseline from `csp_baseline_control_by_ue`, default 1.0). Changed proposals go to `csp-control.jsonl` with `applied: false`. It never calls `set_ue_control`.",
  },
  CSPController: {
    name: "CSP controller",
    kind: "component",
    repository: "harness",
    summary:
      "Network-side controller for L3. Reads CAP reports and sets per-UE scheduler priority or rate caps through `set_ue_control`. Its algorithm (inputs, mapping, interval, damping, persistence) is not specified yet.",
  },
  FikoreControlAdapter: {
    name: "FikoreControlAdapter",
    kind: "component",
    repository: "harness",
    definedIn: "capcsp/collaboration/adapters/fikore_control.py",
    summary:
      "Maps a `CspControlIntent` (priority, max_downlink_mbps) to `UeControl` (priority, rmax_mbps) and calls `set_ue_control` on the backend. Used on `transport_fikore` and `constant_rate`; `mock` gets `NoOpControlAdapter`. Ready for a real controller; the dummy controller does not call it.",
  },
  CapacityOracle: {
    name: "Capacity oracle",
    kind: "component",
    summary:
      "L4 reference: a piecewise-constant trace of future available capacity, from now onward. For one UE it comes from an offline full-buffer FikoRE run with the same seeds. For several adaptive UEs a run must say whether it is an exogenous bound or a demand-coupled trace. Not implemented.",
  },
  RunOutputs: {
    name: "Run outputs",
    kind: "component",
    repository: "harness",
    summary: "Files the runner writes into the output directory of a run. Hover a file name for its content.",
  },

  // Data types
  CspFields: {
    name: "CspFields",
    kind: "data type",
    repository: "harness",
    definedIn: "capcsp/shared_state/types.py (spec: docs/signaling.md)",
    summary:
      "What the network (CSP) may tell the player (CAP). Mapped from backend telemetry; the signaling level decides which fields the player can read. Missing measurements stay null; backends must not invent values.",
    fields: CSP_FIELD_LIST,
  },
  CapReport: {
    name: "CapReport",
    kind: "data type",
    repository: "harness",
    definedIn: "capcsp/shared_state/types.py (spec: docs/signaling.md)",
    summary:
      "What the player (CAP) tells the network. SFV `drainCapReports` returns one on a stall edge, a video switch or a buffer change of 1 s or more, at most once per second of session time per UE. The terminal state is always reported after the final step.",
    fields: CAP_REPORT_FIELD_LIST,
  },
  UeControl: {
    name: "UeControl",
    kind: "data type",
    repository: "fikore",
    definedIn: "5g-network-emulator/transport/fikore_transport/backend.py",
    summary:
      "Per-UE network knob set by an L3 controller. FikoRE applies it at a stated TTI and acknowledges the exact instant; priority only has an effect with the PF scheduler (metric_type 6). The constant_rate backend applies `rmax_mbps` from the next step and records `priority` without effect.",
    fields: [
      { name: "priority", type: "float | None", description: "Scheduler weight of the UE." },
      { name: "rmax_mbps", type: "float | None", description: "Downlink rate cap of the UE. 0 removes the cap, None leaves it unchanged." },
    ],
  },
  CspControlIntent: {
    name: "CspControlIntent",
    kind: "data type",
    repository: "harness",
    definedIn: "capcsp/collaboration/types.py",
    summary: "Backend-neutral control proposal of a CSP controller. `FikoreControlAdapter` turns it into `UeControl`.",
    fields: [
      { name: "priority", type: "float | None", description: "Proposed scheduler weight." },
      { name: "max_downlink_mbps", type: "float | None", description: "Proposed rate cap; becomes rmax_mbps." },
    ],
  },
  NetworkStep: {
    name: "NetworkStep",
    kind: "data type",
    repository: "fikore",
    definedIn: "fikore_transport/backend.py (API: docs/network-backend-api.md)",
    summary: "Result of one `advance()`: everything that happened in the network during the last 10 ms.",
    fields: [
      { name: "time_s", type: "float", description: "Simulation time at the end of the step." },
      { name: "events", type: "list[NetworkEvent]", description: "DownloadProgress, DownloadCompleted and DownloadCancelled. Telemetry is not part of the step." },
      { name: "is_final", type: "bool", description: "The run ends after this step." },
    ],
  },
  NetworkTelemetrySampler: {
    name: "NetworkTelemetrySampler",
    kind: "component",
    repository: "fikore",
    definedIn: "5g-network-emulator/transport/fikore_transport/telemetry.py",
    summary:
      "CSP telemetry source of `TransportBackend`, exposed as `csp_telemetry`. The runner polls it after every step. Every `csp_telemetry_interval_s` (1 s), and once more on the final step, it returns one `NetworkTelemetry` sample per UE with rates over that interval. Each sample is mapped to `CspFields` and logged to `telemetry.jsonl`. The mock and constant_rate backends have no source.",
    fields: [
      { name: "throughput_mbps", type: "float | None", description: "→ achieved_throughput_mbps" },
      { name: "rtt_ms", type: "float | None", description: "→ rtt_ms (TCP ACK timing)" },
      { name: "drop_rate", type: "float | None", description: "→ loss_rate" },
      { name: "ce_rate", type: "float | None", description: "→ congestion_rate" },
      { name: "ip_latency_ms, pdcp_latency_ms", type: "float | None", description: "Extensions, audit only" },
      { name: "sinr_db, queue_bytes, retransmitted_bytes", type: "…", description: "Extensions, audit only" },
    ],
  },
  DownloadEvents: {
    name: "Download events",
    kind: "event",
    repository: "fikore",
    definedIn: "docs/network-backend-api.md",
    summary:
      "`DownloadProgress` (cumulative bytes delivered), `DownloadCompleted` and `DownloadCancelled`, each with `ue_id`, `request_id` and `time_s`. The runner rejects events for unknown requests or byte counts that go backwards or exceed the request size.",
  },

  // Fields
  plan_downlink_mbps: {
    name: "plan_downlink_mbps",
    kind: "field",
    summary:
      "Provisioned subscriber downlink rate (tariff). Comes from `plan_downlink_mbps_by_ue` in the config, not from the network. It is written to the table at run start from L1, so it also works on backends without telemetry (mock, constant_rate).",
  },
  achieved_throughput_mbps: {
    name: "achieved_throughput_mbps",
    kind: "field",
    summary:
      "Delivered downlink throughput over the last telemetry interval (1 s). It is measured delivery, not spare capacity or the maximum channel rate. From the sample's `throughput_mbps`.",
  },
  rtt_ms: {
    name: "rtt_ms",
    kind: "field",
    summary:
      "Round-trip time measured on the modelled TCP acknowledgement path. With ACKs over the FikoRE uplink it includes uplink scheduling; otherwise ACKs return after a fixed 1 ms. FikoRE's one-way PDCP latency is not doubled to fake an RTT.",
  },
  loss_rate: {
    name: "loss_rate",
    kind: "field",
    summary: "Share of bytes dropped in the last telemetry interval, from the sample's `drop_rate`.",
  },
  congestion_rate: {
    name: "congestion_rate",
    kind: "field",
    summary: "ECN Congestion Experienced marking rate, from the sample's `ce_rate`. Null in the pilot because L4S/ECN marking is off.",
  },
  updated_at_s: {
    name: "updated_at_s",
    kind: "field",
    summary: "Simulation time of the write that produced the current `CspFields`. 0.0 for the plan rate seeded at run start.",
  },

  // Methods
  advance: {
    name: "advance()",
    kind: "method",
    repository: "fikore",
    definedIn: "NetworkBackend protocol (capcsp/network/api.py)",
    summary: "Moves the network forward by one step (10 ms) and returns a `NetworkStep`.",
  },
  submit_request: {
    name: "submit_request / cancel_request",
    kind: "method",
    definedIn: "NetworkBackend protocol (capcsp/network/api.py)",
    summary:
      "`submit_request(ue_id, request_id, bytes_total)` starts an opaque byte download; `cancel_request(ue_id, request_id)` stops one. The backend never sees what the bytes are (manifest, segment, quality).",
  },
  set_ue_control: {
    name: "set_ue_control(ue_id, UeControl)",
    kind: "method",
    repository: "fikore",
    definedIn: "ControllableNetworkBackend (capcsp/network/api.py), TransportBackend, ConstantRateBackend",
    summary:
      "Changes the scheduler priority and rate cap of one UE at runtime. On `transport_fikore` it goes through the FikoRE control protocol. On `constant_rate`, `rmax_mbps` caps the UE's configured rate from the next step and `priority` is recorded without effect. Nothing in the pilot calls it yet.",
  },
  write_csp_fields: {
    name: "write_csp_fields(ue_id, CspFields, extensions)",
    kind: "method",
    repository: "harness",
    definedIn: "capcsp/shared_state/table.py",
    summary:
      "Stores the latest network values for a UE. Called for every telemetry sample at every level (audit), and once at start for the plan rate (L1+). Extra telemetry goes to `extensions` and appears only in `shared-state.jsonl`.",
  },
  read_csp_fields: {
    name: "read_csp_fields(ue_id)",
    kind: "method",
    repository: "harness",
    definedIn: "capcsp/shared_state/table.py",
    summary:
      "Returns `CspFields` filtered by signaling level: nothing at L0, only the plan rate at L1, everything from L2. The runner uses it to build `collaboration.csp_by_ue`.",
  },
  write_cap_report: {
    name: "write_cap_report(ue_id, CapReport)",
    kind: "method",
    repository: "harness",
    definedIn: "capcsp/shared_state/table.py",
    summary: "Stores the latest `CapReport` of a UE. Happens at every level for audit.",
  },
  read_cap_report: {
    name: "read_cap_report(ue_id)",
    kind: "method",
    repository: "harness",
    definedIn: "capcsp/shared_state/table.py",
    summary: "Returns the latest `CapReport` from L3 on, nothing below. Used by the CSP controller.",
  },
  applyCspUpdate: {
    name: "applyCspUpdate(fields, time)",
    kind: "method",
    repository: "sfv",
    definedIn: "SFVSimulationController",
    summary:
      "Stores the CSP fields of one UE in the SFV engine, without triggering a new decision. Rules can read them with `getCspFields()`; B1 and B2 do not yet.",
  },
  drainCapReports: {
    name: "drainCapReports(time, { final })",
    kind: "method",
    repository: "sfv",
    definedIn: "SFVSimulationController",
    summary:
      "Returns a `CapReport` for the `cap_reports` reply only when one is due: on a stall edge, a video switch or a buffer change of 1 s or more, at most once per second. With `final` the rate limit does not apply.",
  },

  // IPC messages between Python and Node
  network_step: {
    name: "network_step",
    kind: "IPC message",
    repository: "harness",
    definedIn: "capcsp/player/bridge.py → cosim-network-step-worker.mjs",
    summary:
      "JSON line from the runner to the Node player, once per step: `time_s`, `events`, `is_final` and the `collaboration` snapshot.",
  },
  collaboration: {
    name: "collaboration",
    kind: "IPC message",
    repository: "harness",
    definedIn: "capcsp/collaboration/snapshot.py",
    summary:
      "Object added to `network_step`: `{ signaling_level, csp_by_ue: { \"0\": CspFields, … } }`, built with `read_csp_fields`. Empty `csp_by_ue` at L0.",
  },
  player_actions: {
    name: "player_actions",
    kind: "IPC message",
    repository: "harness",
    summary:
      "Node's answer to `network_step`: a list of `{ op: submit_request | cancel_request, ue_id, request_id, bytes_total }`. The runner forwards them to the backend before the next `advance()`.",
  },
  cap_reports: {
    name: "cap_reports",
    kind: "IPC message",
    repository: "harness",
    definedIn: "capcsp/collaboration/cap_reporter.py",
    summary:
      "Second exchange after each step: the runner sends `{ type: \"cap_reports\" }`, Node answers `{ reports: { \"0\": CapReport, … } }`. A UE appears only when `drainCapReports` has a report due, so the reply is often empty. Each report goes to `write_cap_report`.",
  },
  request_id: {
    name: "request_id",
    kind: "concept",
    summary:
      "ID the player chooses for a request. The backend treats it as an opaque string and only checks that it is unique per UE.",
  },

  // Concepts
  signalingLevelFilter: {
    name: "Signaling-level filter",
    kind: "concept",
    summary:
      "Applied on read, not on write: L0 hides all CSP fields, L1 shows only the plan rate, L2+ shows all of them. CAP reports are readable by a controller only from L3.",
  },
  TTI: {
    name: "TTI",
    kind: "concept",
    summary: "Transmission time interval: FikoRE's scheduling tick of 1 ms. One `NetworkStep` covers 10 TTIs.",
  },
  PFScheduler: {
    name: "PF scheduler",
    kind: "concept",
    summary:
      "Proportional fair scheduler (FikoRE metric_type 6). Balances throughput and fairness between UEs; it is the only scheduler that honours `UeControl.priority`.",
  },
  byteConservation: {
    name: "Byte conservation check",
    kind: "concept",
    summary:
      "The runner checks every download event against the submitted requests: known request, not finished, cumulative bytes only grow and never exceed the request size. A violation stops the run.",
  },
  acksOverUplink: {
    name: "ack_over_link",
    kind: "config key",
    summary:
      "When true, TCP ACKs travel over the FikoRE uplink, so RTT includes uplink scheduling. When false, ACKs return after a fixed 1 ms and the measured RTT is lower than the condition's target.",
  },
  tcpConnectionMode: {
    name: "tcp_connection_mode",
    kind: "config key",
    summary:
      "`persistent` reuses up to `max_idle_tcp_connections_per_ue` warm connections. `fresh` opens a new connection per object, with slow start each time; it is the comparison baseline.",
  },
  plan_downlink_mbps_by_ue: {
    name: "plan_downlink_mbps_by_ue",
    kind: "config key",
    summary: "Map from UE id to plan rate in Mbps. Source of `plan_downlink_mbps`.",
  },
  csp_controller: {
    name: "csp_controller",
    kind: "config key",
    summary: "`\"dummy\"` enables `DummyCSPController` at L3 and above. `null` runs without controller.",
  },
  downlink_rate_mbps: {
    name: "downlink_rate_mbps",
    kind: "config key",
    summary:
      "Rate of every UE on the constant_rate backend, in Mbps of application payload (10^6 bit/s). `downlink_rate_mbps_by_ue` overrides it per UE ID; it may be left out if every UE has an entry there. The example uses 1.0.",
  },
  synthetic_delay_ms: {
    name: "synthetic_delay_ms",
    kind: "config key",
    summary:
      "constant_rate setting: time from submitting a request to its first byte, standing in for application, origin and core-network delay. 0 by default; the example uses 25.",
  },
  cancellation_tail_bytes: {
    name: "cancellation_tail_bytes",
    kind: "config key",
    summary:
      "Bytes a request may still receive after its cancellation, beyond those reported so far, before it ends with `DownloadCancelled`. 0 by default on constant_rate; the mock example uses 512.",
  },
  fallback_frame_rate_fps: {
    name: "scoring.fallback_frame_rate_fps",
    kind: "config key",
    definedIn: "capcsp/scoring/session_scoring.py",
    summary:
      "Frame rate for representations without `frameRateFps` in the content file, 30 by default. Replaces `frame_rate_fps`. Each scored segment records the `frame_rate_fps` used and `frame_rate_from_content`.",
  },
  csp_telemetry_interval_s: {
    name: "csp_telemetry_interval_s",
    kind: "config key",
    summary: "Interval of the CSP telemetry samples in the `transport_fikore` network settings. Default 1 s.",
  },

  // Output files
  "run-manifest.json": { name: "run-manifest.json", kind: "output file", summary: "Configuration, code revisions, timing and byte accounting of the run." },
  "sessions/": { name: "sessions/ue-<id>.json", kind: "output file", summary: "Full player result per UE: events, requests, rule state, cache and the scored session record." },
  "network-steps.jsonl": { name: "network-steps.jsonl", kind: "output file", summary: "Every step as sent to the player, with the `collaboration` snapshot and the player's response." },
  "telemetry.jsonl": { name: "telemetry.jsonl", kind: "output file", summary: "One row per UE and CSP telemetry sample, every `csp_telemetry_interval_s` (1 s). Empty on the mock and constant_rate backends." },
  "kpis.csv": { name: "kpis.csv", kind: "output file", summary: "One row of KPIs per UE, including P.1203 scores." },
  "report.md": { name: "report.md", kind: "output file", summary: "Readable run report: KPIs per UE, scores per video, model versions and scoring settings, including where the frame rate came from." },
  "player.log": { name: "player.log", kind: "output file", summary: "Log output (stderr) of the Node player process." },
  "fikore-effective.ini": { name: "fikore-effective.ini", kind: "output file", summary: "The FikoRE INI actually used, after config overrides." },
  "fikore.log": { name: "fikore.log", kind: "output file", summary: "Output of the FikoRE process." },
  "shared-state.jsonl": {
    name: "shared-state.jsonl",
    kind: "output file",
    summary: "Audit log of the shared state table: one row per changed write (`direction` csp_to_cap or cap_to_csp, `ue_id`, `time_s`, `payload`). Written at every level.",
  },
  "csp-control.jsonl": {
    name: "csp-control.jsonl",
    kind: "output file",
    summary: "Controller proposals: `baseline`, `proposed`, `applied` (always false for the dummy) and `reason` (dummy_stall_boost or dummy_no_change). Only at L3+ with the dummy controller.",
  },
} satisfies Record<string, GlossaryEntry>;

export type GlossaryTermId = keyof typeof GLOSSARY;
