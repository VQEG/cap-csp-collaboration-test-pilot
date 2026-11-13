import {
  backendAcceptsUeControl,
  backendHasCspTelemetrySource,
  signalingLevelNumber,
  usesConstantRateBackend,
  usesFikoreBackend,
  type ExplorerSettings,
} from "@/model/explorerSettings";

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
  | "constantRateBackend"
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
  const hasSharedStateTable = true;
  const constantRate = usesConstantRateBackend(settings);
  const backendEmitsTelemetry = backendHasCspTelemetrySource(settings); // mock and constant_rate have no CSP telemetry source
  const planRateConfigured = settings.planDownlinkMbps !== "";
  const dummyControllerRuns = state === "master" && level >= 3 && settings.dummyCspControllerEnabled;

  // Telemetry is written at every level (audit) and the plan rate at run start
  // from L1; the level filters reads only (docs/signaling.md).
  const writeCspFields = backendEmitsTelemetry || (level >= 1 && planRateConfigured);
  // CAP reports are collected at every level (audit); the controller reads them from L3.
  const capReportsCollected = true;
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
    controllerSetsUeControl: state === "design" && level >= 3 && backendAcceptsUeControl(settings),
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
    mockBackend: settings.networkBackend === "mock",
    constantRateBackend: constantRate,
    sharedStateTable: hasSharedStateTable,
    cspController: controllerReads,
    capacityOracle: activeEdges.capacityTrace,
  };

  return { activeEdges, activeNodes, hasSharedStateTable, backendEmitsTelemetry, planRateConfigured };
}
