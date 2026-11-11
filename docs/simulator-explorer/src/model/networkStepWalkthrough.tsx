import type { ReactNode } from "react";
import { GlossaryTerm as T, InlineCode as C } from "@/components/GlossaryTerm";
import type { ComponentTopology, DiagramEdgeId, DiagramNodeId } from "@/model/componentTopology";
import { signalingLevelNumber, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

// Ordered steps of one 10 ms NetworkStep. `highlightedEdges` and
// `highlightedNodes` are emphasised in the diagram while the step is
// selected; `active: false` greys out a step that does not happen.

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
  const backendNode: DiagramNodeId = fikore ? "transportBackend" : "mockBackend";
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
          Returns a <T id="NetworkStep" asCode /> with <T id="DownloadEvents">download events</T>
          {fikore ? (
            <>
              {" "}
              and one <T id="NetworkTelemetryReceived" asCode /> per UE.
            </>
          ) : (
            "."
          )}
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
          Runs the <T id="byteConservation">byte conservation check</T> and logs {fikore && <><T id="telemetry.jsonl" asCode /> and </>}
          <T id="network-steps.jsonl" asCode />.
        </>
      ),
      highlightedEdges: ["runOutputs"],
      highlightedNodes: ["runner", "runOutputs"],
      active: true,
    },
    {
      actor: "Runner → Shared state table",
      description: activeEdges.writeCspFields ? (
        fikore ? (
          <>
            Maps telemetry to <T id="CspFields" asCode /> and calls <T id="write_csp_fields" asCode>write_csp_fields</T>
            {state === "pr8" && level === 0 ? " (audit only at L0)" : ""}. Changes go to <T id="shared-state.jsonl" asCode />.
          </>
        ) : (
          <>
            No telemetry on mock. Only the <T id="plan_downlink_mbps">plan rate</T> was written once, at run start.
          </>
        )
      ) : state === "master" ? (
        <>No shared state table on master.</>
      ) : (
        <>Nothing to write: no telemetry on mock and no plan rate at this level.</>
      ),
      highlightedEdges: ["writeCspFields"],
      highlightedNodes: ["sharedStateTable"],
      active: activeEdges.writeCspFields,
    },
    {
      actor: "Shared state table → Runner",
      description: activeEdges.readCspFields ? (
        <>
          <T id="read_csp_fields" asCode>read_csp_fields</T> per UE through the <T id="signalingLevelFilter">level filter</T>
          {level === 1 ? ": plan rate only." : ": all CSP fields."}
        </>
      ) : state === "master" ? (
        <>No shared state table on master.</>
      ) : (
        <>At L0 the filter returns nothing.</>
      ),
      highlightedEdges: ["readCspFields"],
      highlightedNodes: ["sharedStateTable", "runner"],
      active: activeEdges.readCspFields,
    },
    {
      actor: "Runner → Player",
      description:
        state === "master" ? (
          <>
            Sends the full <T id="network_step" asCode />
            {fikore ? ", telemetry included. The harness stores it, the SFV engine ignores it." : "."}
          </>
        ) : (
          <>
            Sends <T id="network_step" asCode /> without telemetry, plus <T id="collaboration" asCode />
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
          {state === "pr8" && level >= 1 && (
            <>
              , stores CSP fields with <T id="applyCspUpdate" asCode>applyCspUpdate</T>
            </>
          )}
          , applies download events and swipes; the {ruleTerm} picks the next requests.
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
          Runner asks for <T id="cap_reports" asCode />; SFV <T id="buildCapReport" asCode>buildCapReport</T> answers; each report goes to{" "}
          <T id="write_cap_report" asCode>write_cap_report</T>
          {state === "pr8" && level < 3 ? " (audit only below L3)." : "."}
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
          <>
            Reads CAP reports and calls <T id="set_ue_control" asCode>set_ue_control</T> with <T id="UeControl" asCode />, applied at a stated TTI and acknowledged.
          </>
        ) : (
          <>
            <T id="DummyCSPController" asCode /> reads CAP reports with <T id="read_cap_report" asCode>read_cap_report</T> and logs a proposal to{" "}
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
          Forwards each action as <T id="submit_request" asCode>submit_request</T> or <C>cancel_request</C>, before the next <C>advance()</C>.
        </>
      ),
      highlightedEdges: ["submitOrCancel"],
      highlightedNodes: ["runner", backendNode],
      active: true,
    },
  ];
}
