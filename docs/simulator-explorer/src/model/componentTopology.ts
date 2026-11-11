import { signalingLevelNumber, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

// Which diagram arrows and boxes take part in a run for the chosen settings.
// Edge and node ids must match the ids used in diagramLayout.ts and in
// networkStepWalkthrough.tsx.

export type DiagramEdgeId =
  | "advance"
  | "networkStepToRunner"
  | "submitOrCancel"
  | "networkStepToPlayer"
  | "playerActions"
  | "capReportsIpc"
  | "transportToLink"
  | "linkToFikore"
  | "runOutputs"
  | "writeCspFields"
  | "readCspFields"
  | "writeCapReport"
  | "controllerReadsCapReport"
  | "controllerSetsUeControl"
  | "controllerLogsProposal"
  | "capacityTrace";

export type DiagramNodeId =
  | "networkStepHarness"
  | "sfvSimulationController"
  | "playerRule"
  | "runner"
  | "runOutputs"
  | "transportBackend"
  | "fikoreLink"
  | "fikore"
  | "mockBackend"
  | "sharedStateTable"
  | "cspController"
  | "capacityOracle";

export interface ComponentTopology {
  activeEdges: Record<DiagramEdgeId, boolean>;
  activeNodes: Record<DiagramNodeId, boolean>;
  hasSharedStateTable: boolean;
  backendEmitsTelemetry: boolean;
  planRateConfigured: boolean;
}

export function computeComponentTopology(settings: ExplorerSettings): ComponentTopology {
  const level = signalingLevelNumber(settings.signalingLevel);
  const fikore = usesFikoreBackend(settings);
  const state = settings.implementationState;
  const hasSharedStateTable = state !== "master";
  const backendEmitsTelemetry = fikore; // the mock backend emits no NetworkTelemetryReceived
  const planRateConfigured = settings.planDownlinkMbps !== "";
  const dummyControllerRuns = state === "pr8" && level >= 3 && settings.dummyCspControllerEnabled;

  // PR #8 writes telemetry at every level (audit) and seeds the plan rate at
  // run start from L1. The design only writes what a level exposes.
  const writeCspFields =
    state === "pr8"
      ? backendEmitsTelemetry || (level >= 1 && planRateConfigured)
      : state === "design" && level >= 1 && (backendEmitsTelemetry || planRateConfigured);
  // PR #8 collects CAP reports at every level (audit); the design from L3.
  const capReportsCollected = state === "pr8" || (state === "design" && level >= 3);
  const controllerReads = level >= 3 && (state === "design" || dummyControllerRuns);

  const activeEdges: Record<DiagramEdgeId, boolean> = {
    advance: true,
    networkStepToRunner: true,
    submitOrCancel: true,
    networkStepToPlayer: true,
    playerActions: true,
    capReportsIpc: capReportsCollected,
    transportToLink: fikore,
    linkToFikore: fikore,
    runOutputs: true,
    writeCspFields,
    readCspFields: hasSharedStateTable && level >= 1,
    writeCapReport: capReportsCollected,
    controllerReadsCapReport: controllerReads,
    controllerSetsUeControl: state === "design" && level >= 3 && fikore,
    controllerLogsProposal: dummyControllerRuns,
    capacityTrace: state === "design" && level === 4,
  };

  const activeNodes: Record<DiagramNodeId, boolean> = {
    networkStepHarness: true,
    sfvSimulationController: true,
    playerRule: true,
    runner: true,
    runOutputs: true,
    transportBackend: fikore,
    fikoreLink: fikore,
    fikore: fikore,
    mockBackend: !fikore,
    sharedStateTable: hasSharedStateTable,
    cspController: controllerReads,
    capacityOracle: activeEdges.capacityTrace,
  };

  return { activeEdges, activeNodes, hasSharedStateTable, backendEmitsTelemetry, planRateConfigured };
}
