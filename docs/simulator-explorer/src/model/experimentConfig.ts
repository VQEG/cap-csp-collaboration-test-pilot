import { CONTENT_PATH_FROM_CONFIG_FILE } from "@/data/contentCatalogue";
import { CONDITION_PARAMETER_BASE_VALUES, conditionParametersOf, iniValue } from "@/data/conditionParameters";
import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import { BEHAVIOR_MIXES, BEHAVIOR_PARAMETERS, PLAYER_BEHAVIORS, behaviorOfUe, type PlayerBehavior } from "@/data/playerBehaviors";
import {
  CONSTANT_RATE_CANCELLATION_TAIL_BYTES,
  CONSTANT_RATE_SYNTHETIC_DELAY_MS,
  constantRateDownlinkMbps,
  signalingLevelNumber,
  usesConstantRateBackend,
  usesFikoreBackend,
  type ExplorerSettings,
  type SignalingLevel,
} from "@/model/explorerSettings";
import { parseSwipeTimes, watchDurationRange } from "@/model/swipeSchedule";

// The experiment and grid JSON for the chosen settings. Keep the keys in sync
// with configs/experiments/, configs/grids/, capcsp/runner/run.py and
// capcsp/runner/grid_specification.py.

type JsonObject = Record<string, unknown>;

/** FikoRE seed of a run, and the base of the grid's per-replication seeds. */
export const NETWORK_SEED_BASE = 20260927;
/** Grid session seeds are replication × stride + UE ID, as in grid_specification.py. */
const GRID_SESSION_SEED_STRIDE = 1000;

/** Session seed of a UE: the condition configs use 17 + 4 × UE ID; a grid uses replication × 1000 + UE ID. */
export function sessionSeed(settings: ExplorerSettings, ueId: number, replication = 1): number {
  return settings.configOutputKind === "grid" ? replication * GRID_SESSION_SEED_STRIDE + ueId : 17 + 4 * ueId;
}

/** Simulated run length in seconds: the condition's (possibly changed) duration on FikoRE. */
export function runDurationSeconds(settings: ExplorerSettings, conditionId = settings.conditionId): number {
  if (usesFikoreBackend(settings)) return settings.conditionOverrides[conditionId]?.duration ?? NETWORK_CONDITIONS[conditionId].durationSeconds;
  if (usesConstantRateBackend(settings)) return 20;
  return 0.2;
}

/** Condition parameters that differ from the INI, split by where they go in the config. */
export function conditionOverrideBlocks(settings: ExplorerSettings, conditionId: string) {
  const changed = settings.conditionOverrides[conditionId] ?? {};
  const baseValues = CONDITION_PARAMETER_BASE_VALUES[conditionId] ?? {};
  const sectionOverrides: Record<string, JsonObject> = {};
  const ueOverrides: Record<string, JsonObject> = {};
  let durationS: number | undefined;
  for (const parameter of conditionParametersOf(conditionId)) {
    const value = changed[parameter.id];
    if (value === undefined || !Number.isFinite(value) || value === baseValues[parameter.id]) continue;
    const target = parameter.target;
    if (target.kind === "experiment") durationS = value;
    else if (target.kind === "section") (sectionOverrides[target.section] ??= {})[target.key] = iniValue(parameter, value);
    else (ueOverrides[target.group] ??= {})[target.key] = iniValue(parameter, value);
  }
  return { durationS, sectionOverrides, ueOverrides };
}

function fikoreNetworkSettings(settings: ExplorerSettings, conditionId: string, includeConditionOverrides: boolean): JsonObject {
  const { sectionOverrides, ueOverrides } = includeConditionOverrides
    ? conditionOverrideBlocks(settings, conditionId)
    : { sectionOverrides: {}, ueOverrides: {} };
  const network: JsonObject = {
    congestion_control: "cubic",
    receive_window_bytes: 1048576,
    tcp_connection_mode: settings.tcpConnectionMode,
    max_idle_tcp_connections_per_ue: 6,
    step_ms: 10,
    fikore_base_ini: `configs/fikore/${NETWORK_CONDITIONS[conditionId].fikoreIniFile}`,
    study_ues: ["studyVqeg"],
    ack_over_link: settings.acksOverFikoreUplink,
    delay_budget_s: null,
    random_v: null,
    fikore_section_overrides: { Global: { seed: NETWORK_SEED_BASE }, ...sectionOverrides },
  };
  if (Object.keys(ueOverrides).length) network.fikore_ue_overrides = ueOverrides;
  return network;
}

function networkSettings(settings: ExplorerSettings, conditionId: string, includeConditionOverrides: boolean): JsonObject {
  if (usesFikoreBackend(settings)) return fikoreNetworkSettings(settings, conditionId, includeConditionOverrides);
  if (usesConstantRateBackend(settings)) {
    return {
      step_s: 0.01,
      downlink_rate_mbps: constantRateDownlinkMbps(settings),
      synthetic_delay_ms: CONSTANT_RATE_SYNTHETIC_DELAY_MS,
      cancellation_tail_bytes: CONSTANT_RATE_CANCELLATION_TAIL_BYTES,
    };
  }
  return { step_s: 0.01, cell_bytes_per_step: 80000, cancellation_tail_bytes: 512 };
}

/** The SFV `userModel` of every session. The 0.2 s mock smoke test keeps one early fixed swipe instead. */
function userModel(settings: ExplorerSettings): JsonObject {
  if (settings.networkBackend === "mock") return { type: "sequence", swipeTimesS: [0.1] };
  if (settings.swipeModel === "sequence") {
    const times = parseSwipeTimes(settings.swipeTimesS);
    return { type: "sequence", swipeTimesS: typeof times === "string" ? [] : times };
  }
  return { type: "seeded", watchDurationRangeS: watchDurationRange(settings) };
}

function parameterValue(settings: ExplorerSettings, behavior: PlayerBehavior, id: string): number | boolean {
  return settings.behaviorParameters[behavior][id] ?? PLAYER_BEHAVIORS[behavior].defaults[id];
}

/** `config.scheduling` and `rule_config` of one behaviour; optional keys only when they differ from the SFV default. */
function behaviorConfigBlocks(settings: ExplorerSettings, behavior: PlayerBehavior) {
  const definition = PLAYER_BEHAVIORS[behavior];
  const scheduling: JsonObject = {};
  const rule: JsonObject = {};
  const throughput: JsonObject = {};
  for (const parameter of BEHAVIOR_PARAMETERS) {
    if (!(parameter.id in definition.defaults)) continue;
    const value = parameterValue(settings, behavior, parameter.id);
    if (!parameter.alwaysWritten && value === definition.sfvDefaults[parameter.id]) continue;
    const target = parameter.location === "scheduling" ? scheduling : parameter.location === "rule" ? rule : throughput;
    target[parameter.key] = value;
  }
  if (Object.keys(throughput).length) rule.throughput = throughput;
  return { scheduling, rule };
}

function session(settings: ExplorerSettings, ueId: number, behavior: PlayerBehavior, seed: number): JsonObject {
  const { scheduling, rule } = behaviorConfigBlocks(settings, behavior);
  return {
    ue_id: ueId,
    player_behavior: behavior,
    config: { sessionId: `generic-ue${ueId}`, seed, scheduling, userModel: userModel(settings) },
    rule_config: rule,
  };
}

function runId(settings: ExplorerSettings): string {
  const levelSlug = settings.signalingLevel.toLowerCase();
  const prefix = usesFikoreBackend(settings) ? `vqeg-${settings.conditionId.toLowerCase()}` : usesConstantRateBackend(settings) ? "constant-rate" : "mock";
  return `${prefix}-${levelSlug}-${settings.videoUeCount}ue-${settings.behaviorMix}`;
}

interface ExperimentShape {
  conditionId: string;
  signalingLevels: SignalingLevel[];
  ueIdsWithPlanRate: number[];
  sessions: JsonObject[];
  includeConditionOverrides: boolean;
}

function experimentConfig(settings: ExplorerSettings, shape: ExperimentShape, identifier: string): JsonObject {
  const fikore = usesFikoreBackend(settings);
  const levels = shape.signalingLevels.map(signalingLevelNumber);
  const config: JsonObject = {
    run_id: identifier,
    network_backend: settings.networkBackend,
    network: networkSettings(settings, shape.conditionId, shape.includeConditionOverrides),
    condition: fikore ? shape.conditionId : "example-only",
    signaling_level: shape.signalingLevels[0],
    clock_mode: "simulation",
    content: CONTENT_PATH_FROM_CONFIG_FILE,
  };
  if (Math.max(...levels) >= 1 && settings.planDownlinkMbps !== "") {
    config.plan_downlink_mbps_by_ue = Object.fromEntries(shape.ueIdsWithPlanRate.map((ueId) => [String(ueId), Number(settings.planDownlinkMbps)]));
  }
  if (Math.max(...levels) >= 3) config.csp_controller = settings.dummyCspControllerEnabled ? "dummy" : null;
  config.duration_s = shape.includeConditionOverrides ? runDurationSeconds(settings, shape.conditionId) : runDurationSeconds({ ...settings, conditionOverrides: {} }, shape.conditionId);
  config.timingDefaults = {
    playbackTiming: { mode: "causal-simple", slotPreparationS: 0.01, appendDurationS: 0.005, startupDelayS: 0.005, observationIntervalS: 0.05 },
  };
  config.sessions = shape.sessions;
  return config;
}

/** The single experiment configuration of the run. */
export function buildRunConfig(settings: ExplorerSettings): JsonObject {
  const runSettings = { ...settings, configOutputKind: "run" as const };
  const ueIds = [...Array(settings.videoUeCount).keys()];
  return experimentConfig(
    runSettings,
    {
      conditionId: settings.conditionId,
      signalingLevels: [settings.signalingLevel],
      ueIdsWithPlanRate: ueIds,
      sessions: ueIds.map((ueId) => session(runSettings, ueId, behaviorOfUe(settings.behaviorMix, ueId), sessionSeed(runSettings, ueId))),
      includeConditionOverrides: true,
    },
    runId(settings),
  );
}

/** The condition overlay of a grid: FikoRE scenario, duration and changed parameters. */
function gridConditionOverlay(settings: ExplorerSettings, conditionId: string): JsonObject {
  const { durationS, sectionOverrides, ueOverrides } = conditionOverrideBlocks(settings, conditionId);
  const network: JsonObject = { fikore_base_ini: `configs/fikore/${NETWORK_CONDITIONS[conditionId].fikoreIniFile}` };
  if (Object.keys(sectionOverrides).length) network.fikore_section_overrides = sectionOverrides;
  if (Object.keys(ueOverrides).length) network.fikore_ue_overrides = ueOverrides;
  return { condition: conditionId, duration_s: durationS ?? NETWORK_CONDITIONS[conditionId].durationSeconds, network };
}

/** Selected grid axes, with empty selections replaced by the run's value. */
export function effectiveGridAxes(settings: ExplorerSettings) {
  const axes = settings.gridAxes;
  const conditionIds = usesFikoreBackend(settings) ? axes.conditionIds.filter((id) => NETWORK_CONDITIONS[id]) : [];
  return {
    conditionIds: usesFikoreBackend(settings) ? (conditionIds.length ? conditionIds : [settings.conditionId]) : [],
    signalingLevels: axes.signalingLevels.length ? axes.signalingLevels : [settings.signalingLevel],
    ueCounts: axes.ueCounts.length ? [...axes.ueCounts].sort((a, b) => a - b) : [settings.videoUeCount],
    behaviorMixes: axes.behaviorMixes.length ? axes.behaviorMixes : [settings.behaviorMix],
    replications: Number.isInteger(axes.replications) && axes.replications >= 1 ? axes.replications : 1,
  };
}

export function gridCellCount(settings: ExplorerSettings): number {
  const axes = effectiveGridAxes(settings);
  return Math.max(1, axes.conditionIds.length) * axes.signalingLevels.length * axes.ueCounts.length * axes.behaviorMixes.length * axes.replications;
}

/** The grid file: an inline base experiment plus the axes. `capcsp grid` runs it as it is. */
export function buildGridConfig(settings: ExplorerSettings): JsonObject {
  const gridSettings = { ...settings, configOutputKind: "grid" as const };
  const axes = effectiveGridAxes(settings);
  // One session template per behaviour that a mix uses
  const behaviors = [...new Set(axes.behaviorMixes.flatMap((mix) => BEHAVIOR_MIXES[mix].pattern))];
  const base = experimentConfig(
    gridSettings,
    {
      conditionId: axes.conditionIds[0] ?? settings.conditionId,
      signalingLevels: axes.signalingLevels,
      ueIdsWithPlanRate: [...Array(Math.max(...axes.ueCounts)).keys()],
      sessions: behaviors.map((behavior, ueId) => session(gridSettings, ueId, behavior, sessionSeed(gridSettings, ueId))),
      // Each condition overlay carries its own changes, so that they do not leak into the other conditions
      includeConditionOverrides: !usesFikoreBackend(settings),
    },
    "explorer-base",
  );
  const grid: JsonObject = { grid_id: "explorer", base };
  if (axes.conditionIds.length) grid.conditions = Object.fromEntries(axes.conditionIds.map((id) => [id, gridConditionOverlay(settings, id)]));
  grid.signaling_levels = axes.signalingLevels;
  grid.ue_counts = axes.ueCounts;
  grid.behavior_mixes = Object.fromEntries(axes.behaviorMixes.map((mix) => [mix, BEHAVIOR_MIXES[mix].pattern]));
  grid.replications = axes.replications;
  grid.network_seed_base = NETWORK_SEED_BASE;
  return grid;
}

export function buildExperimentConfig(settings: ExplorerSettings): JsonObject {
  return settings.configOutputKind === "grid" ? buildGridConfig(settings) : buildRunConfig(settings);
}
