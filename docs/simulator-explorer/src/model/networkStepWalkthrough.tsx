import type { ReactNode } from "react";
import { GlossaryTerm as T, InlineCode as C } from "@/components/GlossaryTerm";
import type { ComponentTopology, DiagramEdgeId, DiagramNodeId } from "@/model/componentTopology";
import {
  CONSTANT_RATE_SYNTHETIC_DELAY_MS,
  constantRateDownlinkMbps,
  signalingLevelNumber,
  usesConstantRateBackend,
  usesFikoreBackend,
  type ExplorerSettings,
} from "@/model/explorerSettings";

// Ordered steps of one 10 ms NetworkStep, in the order of docs/collaboration.md.
// `highlightedEdges` and `highlightedNodes` are emphasised in the diagram while
// the step is selected; `active: false` greys out a step that does not happen.

export interface WalkthroughStep {
  actor: string;
  description: ReactNode;
  highlightedEdges: DiagramEdgeId[];
  highlightedNodes: DiagramNodeId[];
  active: boolean;
}

export function buildNetworkStepWalkthrough(settings: ExplorerSettings, topology: ComponentTopology): WalkthroughStep[] {
  const fikore = usesFikoreBackend(settings);
  const level = signalingLevelNumber(settings.signalingLevel);
  const state = settings.implementationState;
  const { activeEdges } = topology;
  const constantRate = usesConstantRateBackend(settings);
  const backendNode: DiagramNodeId = fikore ? "transportBackend" : constantRate ? "constantRateBackend" : "mockBackend";
  const backendWithoutTelemetryName = constantRate ? "The constant_rate backend" : "The mock backend";
  const ruleTerm = settings.playerBehavior === "simple" ? <T id="SFVCurrentVideoRule">B1 current-video rule</T> : <T id="SFVMultiVideoPrefetchRule">B2 prefetch rule</T>;

  return [
    {
      actor: "Runner → Backend",
      description: (
        <>
          Calls <T id="advance" asCode>advance()</T> for the next 10 ms.
        </>
      ),
      highlightedEdges: ["advance"],
      highlightedNodes: ["runner", backendNode],
      active: true,
    },
    fikore
      ? {
          actor: "TransportBackend ↔ FikoreLink ↔ FikoRE",
          description: (
            <>
              Runs 10 <T id="TTI">TTIs</T> of 1 ms: TCP segments are injected, FikoRE schedules the radio, ACKs drive congestion control
              {settings.acksOverFikoreUplink ? " (ACKs cross the FikoRE uplink)." : " (ACKs return after a fixed 1 ms)."}
            </>
          ),
          highlightedEdges: ["transportToLink", "linkToFikore"],
          highlightedNodes: ["transportBackend", "fikoreLink", "fikore"],
          active: true,
        }
      : constantRate
      ? {
          actor: "ConstantRateBackend",
          description: (
            <>
              Gives each UE {constantRateDownlinkMbps(settings)} Mbps for the 10 ms, shared equally by that UE's ready requests. A request gets no bytes until{" "}
              <T id="synthetic_delay_ms" asCode>synthetic_delay_ms</T> ({CONSTANT_RATE_SYNTHETIC_DELAY_MS} ms) after it was submitted. No contention between UEs, no
              telemetry.
            </>
          ),
          highlightedEdges: [],
          highlightedNodes: ["constantRateBackend"],
          active: true,
        }
      : {
          actor: "MockNetworkBackend",
          description: <>Shares 80,000 bytes per step (64 Mbps) across all active requests. No delay, no telemetry.</>,
          highlightedEdges: [],
          highlightedNodes: ["mockBackend"],
          active: true,
        },
    {
      actor: "Backend → Runner",
      description: (
        <>
          Returns a <T id="NetworkStep" asCode /> with <T id="DownloadEvents">download events</T> only.
        </>
      ),
      highlightedEdges: ["networkStepToRunner"],
      highlightedNodes: ["runner"],
      active: true,
    },
    {
      actor: "Runner",
      description: (
        <>
          Runs the <T id="byteConservation">byte conservation check</T> on the download events.
        </>
      ),
      highlightedEdges: [],
      highlightedNodes: ["runner"],
      active: true,
    },
    {
      actor: "Backend telemetry → Shared state table",
      description: activeEdges.writeCspFields ? (
        fikore ? (
          <>
            Polls the backend's <T id="NetworkTelemetrySampler">telemetry sampler</T>. Every <T id="csp_telemetry_interval_s" asCode>csp_telemetry_interval_s</T> (1 s), and
            once more on the final step, it returns one sample per UE. The runner maps each sample to <T id="CspFields" asCode />, calls{" "}
            <T id="write_csp_fields" asCode>write_csp_fields</T>
            {level === 0 ? " (audit only at L0)" : ""} and logs it to <T id="telemetry.jsonl" asCode />. Changes go to{" "}
            <T id="shared-state.jsonl" asCode />.
          </>
        ) : (
          <>
            {backendWithoutTelemetryName} has no telemetry source. Only the <T id="plan_downlink_mbps">plan rate</T> was written, once, at run start.
          </>
        )
      ) : (
        <>Nothing to write: no telemetry on {settings.networkBackend} and no plan rate at this level.</>
      ),
      highlightedEdges: ["writeCspFields"],
      highlightedNodes: [backendNode, "runner", "sharedStateTable"],
      active: activeEdges.writeCspFields,
    },
    {
      actor: "Shared state table → Runner",
      description: activeEdges.readCspFields ? (
        <>
          <T id="read_csp_fields" asCode>read_csp_fields</T> per UE through the <T id="signalingLevelFilter">level filter</T>
          {level === 1 ? ": plan rate only." : ": all CSP fields."}
        </>
      ) : (
        <>At L0 the filter returns nothing.</>
      ),
      highlightedEdges: ["readCspFields"],
      highlightedNodes: ["sharedStateTable", "runner"],
      active: activeEdges.readCspFields,
    },
    {
      actor: "Runner → Player",
      description: (
        <>
          Sends <T id="network_step" asCode /> with the download events and the <T id="collaboration" asCode /> snapshot
          {level === 0 ? " (empty at L0)." : "."}
        </>
      ),
      highlightedEdges: ["networkStepToPlayer"],
      highlightedNodes: ["networkStepHarness"],
      active: true,
    },
    {
      actor: "Capacity oracle → Player",
      description: <>Delivers the capacity trace from now onward.</>,
      highlightedEdges: ["capacityTrace"],
      highlightedNodes: ["capacityOracle", "playerRule"],
      active: activeEdges.capacityTrace,
    },
    {
      actor: "Player (Node.js)",
      description: (
        <>
          Advances every UE to <C>time_s</C>
          {level >= 1 && (
            <>
              , passes changed CSP fields to <T id="applyCspUpdate" asCode>applyCspUpdate</T>
            </>
          )}
          , applies download events and swipes. The {ruleTerm} picks the next requests.
        </>
      ),
      highlightedEdges: [],
      highlightedNodes: ["networkStepHarness", "sfvSimulationController", "playerRule"],
      active: true,
    },
    {
      actor: "Player → Runner",
      description: (
        <>
          Answers with <T id="player_actions" asCode />: submit and cancel requests with opaque <T id="request_id">IDs</T> and byte sizes.
        </>
      ),
      highlightedEdges: ["playerActions"],
      highlightedNodes: ["networkStepHarness", "runner"],
      active: true,
    },
    {
      actor: "Player → Runner → Shared state table",
      description: (
        <>
          The runner sends <T id="cap_reports" asCode />. SFV <T id="drainCapReports" asCode>drainCapReports</T> returns a report for a UE only when one is due, so the
          reply is often empty. Each report goes to <T id="write_cap_report" asCode>write_cap_report</T>
          {level < 3 ? " (audit only below L3)." : "."}
        </>
      ),
      highlightedEdges: ["capReportsIpc", "writeCapReport"],
      highlightedNodes: ["networkStepHarness", "runner", "sharedStateTable"],
      active: activeEdges.capReportsIpc,
    },
    {
      actor: "CSP controller",
      description:
        state === "design" ? (
          constantRate ? (
            <>
              Reads CAP reports and calls <T id="set_ue_control" asCode>set_ue_control</T> with <T id="UeControl" asCode />. The constant_rate backend applies{" "}
              <C>rmax_mbps</C> as a cap on the UE rate from the next step; <C>priority</C> has no effect.
            </>
          ) : (
            <>
              Reads CAP reports and calls <T id="set_ue_control" asCode>set_ue_control</T> with <T id="UeControl" asCode />, applied at a stated TTI and acknowledged.
            </>
          )
        ) : (
          <>
            <T id="DummyCSPController" asCode /> reads CAP reports with <T id="read_cap_report" asCode>read_cap_report</T> and logs changed proposals to{" "}
            <T id="csp-control.jsonl" asCode />. Nothing is applied.
          </>
        ),
      highlightedEdges: ["controllerReadsCapReport", "controllerSetsUeControl", "controllerLogsProposal"],
      highlightedNodes: ["cspController"],
      active: activeEdges.controllerReadsCapReport,
    },
    {
      actor: "Runner → Backend",
      description: (
        <>
          Forwards each action as <T id="submit_request" asCode>submit_request</T> or <C>cancel_request</C>, before the next <C>advance()</C>. The step goes to{" "}
          <T id="network-steps.jsonl" asCode />.
        </>
      ),
      highlightedEdges: ["submitOrCancel", "runOutputs"],
      highlightedNodes: ["runner", backendNode, "runOutputs"],
      active: true,
    },
  ];
}
