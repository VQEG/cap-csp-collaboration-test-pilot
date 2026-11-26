import { CONTENT_CATALOGUES } from "@/data/contentCatalogue";
import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import {
  PARAMETRIC_PRESET_DEFAULTS,
  isParametricCondition,
  isValidStudyDlRmaxMbps,
  loadSweepConditionSlug,
  parseLoadSweepValues,
  resolveParametricCellValues,
  usesTraverseCorridor,
  type ParametricCellValues,
} from "@/data/parametricCells";
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
// with configs/experiments/, configs/grids/, capcsp/runner/run.py,
// capcsp/runner/grid_specification.py and capcsp/network/parametric_cell.py.

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
  if (usesFikoreBackend(settings)) {
    return resolveParametricCellValues(conditionId, settings.parametricOverrides[conditionId]).duration_s;
  }
  if (usesConstantRateBackend(settings)) return 20;
  return 0.2;
}

/** Receive window sized to the cell BDP: 256 KiB for ≤40 MHz parametric cells, 1 MiB for ≥60 MHz cells. */
export function receiveWindowBytesForCondition(settings: ExplorerSettings, conditionId = settings.conditionId): number {
  const bw = resolveParametricCellValues(conditionId, settings.parametricOverrides[conditionId]).bandwidth_mhz;
  return bw >= 60 ? 1048576 : 262144;
}

/** Build the `network.parametric_cell` object for a parametric condition. */
export function buildParametricCellPayload(
  settings: ExplorerSettings,
  conditionId: string,
  options: { omitLoadRho?: boolean; forceSpatialWhenSweep?: boolean } = {},
): JsonObject {
  const overrides = settings.parametricOverrides[conditionId] ?? {};
  const resolved = resolveParametricCellValues(conditionId, overrides);
  const presetName = conditionId === "CUSTOM" ? "custom" : conditionId;

  if (conditionId !== "CUSTOM" && !options.omitLoadRho) {
    const defaults = PARAMETRIC_PRESET_DEFAULTS[conditionId];
    const payload: JsonObject = { preset: presetName };
    const keys: (keyof Omit<ParametricCellValues, "duration_s">)[] = [
      "bandwidth_mhz",
      "study_position",
      "study_distance_m",
      "study_mobility",
      "study_speed_kmh",
      "traverse_min_distance_m",
      "traverse_max_distance_m",
      "study_dl_rmax_mbps",
      "load_rho",
      "bg_spatial",
      "bg_max_distance_m",
      "bg_bitrate_mbps",
      "arrival_mode",
      "mean_hold_s",
      "burst_amplitude",
      "burst_regime_s",
      "backhaul_delay_ms",
      "backhaul_jitter_ms",
    ];
    for (const key of keys) {
      if (resolved[key] !== defaults[key]) payload[key] = resolved[key];
    }
    // Preserve explicit distance/speed when study_position or study_mobility overrides the preset,
    // preventing ParametricCellConfig.from_dict() from substituting zone/mobility defaults.
    if (resolved.study_position !== defaults.study_position && resolved.study_position === "custom") {
      payload.study_distance_m = resolved.study_distance_m;
    }
    if (resolved.study_mobility !== defaults.study_mobility) {
      payload.study_speed_kmh = resolved.study_mobility === "static" ? 0 : resolved.study_speed_kmh;
    }
    return payload;
  }

  const bgSpatial = options.forceSpatialWhenSweep && resolved.bg_spatial === "none" ? "cell_disk" : resolved.bg_spatial;
  const payload: JsonObject = {
    preset: presetName,
    bandwidth_mhz: resolved.bandwidth_mhz,
    study_position: resolved.study_position,
  };
  if (resolved.study_position === "custom") payload.study_distance_m = resolved.study_distance_m;
  payload.study_mobility = resolved.study_mobility;
  if (resolved.study_mobility !== "static") payload.study_speed_kmh = resolved.study_speed_kmh;
  if (usesTraverseCorridor(resolved.study_mobility)) {
    payload.traverse_min_distance_m = resolved.traverse_min_distance_m;
    payload.traverse_max_distance_m = resolved.traverse_max_distance_m;
  }
  if (resolved.study_dl_rmax_mbps !== null) payload.study_dl_rmax_mbps = resolved.study_dl_rmax_mbps;
  if (!options.omitLoadRho) payload.load_rho = resolved.load_rho;
  if (options.omitLoadRho || resolved.load_rho > 0) {
    payload.bg_spatial = bgSpatial;
    if (bgSpatial === "cell_disk" && resolved.bg_max_distance_m !== 630) {
      payload.bg_max_distance_m = resolved.bg_max_distance_m;
    }
    payload.bg_bitrate_mbps = resolved.bg_bitrate_mbps;
    payload.arrival_mode = resolved.arrival_mode;
    payload.mean_hold_s = resolved.mean_hold_s;
    if (resolved.arrival_mode === "mmpp") {
      payload.burst_amplitude = resolved.burst_amplitude;
      payload.burst_regime_s = resolved.burst_regime_s;
    }
  }
  if (resolved.backhaul_delay_ms !== 10) payload.backhaul_delay_ms = resolved.backhaul_delay_ms;
  if (resolved.backhaul_jitter_ms !== 1) payload.backhaul_jitter_ms = resolved.backhaul_jitter_ms;
  return payload;
}

interface FikoreSettingsMode {
  kind: "run" | "grid_base_conditions" | "grid_base_load_sweep";
}

function fikoreNetworkSettings(settings: ExplorerSettings, conditionId: string, mode: FikoreSettingsMode): JsonObject {
  const network: JsonObject = {
    congestion_control: "cubic",
    receive_window_bytes: receiveWindowBytesForCondition(settings, conditionId),
    tcp_connection_mode: settings.tcpConnectionMode,
    max_idle_tcp_connections_per_ue: 6,
    step_ms: 10,
    study_ues: ["studyVqeg"],
    ack_over_link: settings.acksOverFikoreUplink,
    delay_budget_s: null,
    random_v: null,
  };

  if (mode.kind === "grid_base_conditions") {
    // Condition overlays supply `parametric_cell`, and `grid_specification.py` supplies `Global.seed`.
    return network;
  }

  if (mode.kind === "grid_base_load_sweep") {
    network.parametric_cell = buildParametricCellPayload(settings, conditionId, {
      omitLoadRho: true,
      forceSpatialWhenSweep: true,
    });
    return network;
  }

  network.parametric_cell = buildParametricCellPayload(settings, conditionId);
  network.fikore_section_overrides = { Global: { seed: NETWORK_SEED_BASE } };
  return network;
}

function networkSettings(settings: ExplorerSettings, conditionId: string, mode: FikoreSettingsMode): JsonObject {
  if (usesFikoreBackend(settings)) return fikoreNetworkSettings(settings, conditionId, mode);
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
  const prefix = usesFikoreBackend(settings)
    ? `layered-${settings.conditionId.toLowerCase()}`
    : usesConstantRateBackend(settings)
      ? "constant-rate"
      : "mock";
  return `${prefix}-${levelSlug}-${settings.videoUeCount}ue-${settings.behaviorMix}`;
}

interface ExperimentShape {
  conditionId: string;
  signalingLevels: SignalingLevel[];
  ueIdsWithPlanRate: number[];
  sessions: JsonObject[];
  fikoreMode: FikoreSettingsMode;
}

/** The plan rate implied by a static study-UE cap of the condition, or null when it is uncapped. */
export function capPlanMbps(settings: ExplorerSettings, conditionId: string): number | null {
  return resolveParametricCellValues(conditionId, settings.parametricOverrides[conditionId]).study_dl_rmax_mbps;
}

function experimentConfig(settings: ExplorerSettings, shape: ExperimentShape, identifier: string): JsonObject {
  const fikore = usesFikoreBackend(settings);
  const levels = shape.signalingLevels.map(signalingLevelNumber);
  const config: JsonObject = {
    run_id: identifier,
    network_backend: settings.networkBackend,
    network: networkSettings(settings, shape.conditionId, shape.fikoreMode),
    condition: fikore ? shape.conditionId : "example-only",
    signaling_level: shape.signalingLevels[0],
    clock_mode: "simulation",
    content: CONTENT_CATALOGUES[settings.contentId].pathFromConfigsChild,
  };
  // Without an explicit plan rate, run.py derives the plan from `parametric_cell.study_dl_rmax_mbps`; mirror that here so the config shows it.
  const planRate = settings.planDownlinkMbps !== "" ? Number(settings.planDownlinkMbps) : fikore ? capPlanMbps(settings, shape.conditionId) : null;
  if (Math.max(...levels) >= 1 && planRate !== null) {
    config.plan_downlink_mbps_by_ue = Object.fromEntries(shape.ueIdsWithPlanRate.map((ueId) => [String(ueId), planRate]));
  }
  if (Math.max(...levels) >= 3) config.csp_controller = settings.dummyCspControllerEnabled ? "dummy" : null;
  config.duration_s = runDurationSeconds(settings, shape.conditionId);
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
      fikoreMode: { kind: "run" },
    },
    runId(settings),
  );
}

/** The condition overlay of a grid: parametric_cell, duration and receive window. */
function gridConditionOverlay(settings: ExplorerSettings, conditionId: string): JsonObject {
  return {
    condition: conditionId,
    duration_s: runDurationSeconds(settings, conditionId),
    network: {
      receive_window_bytes: receiveWindowBytesForCondition(settings, conditionId),
      parametric_cell: buildParametricCellPayload(settings, conditionId),
    },
  };
}

export function effectiveLoadSweepRhos(settings: ExplorerSettings): number[] {
  const parsed = parseLoadSweepValues(settings.loadSweepValues);
  return typeof parsed === "string" ? [] : parsed;
}

export function usesParametricLoadSweep(settings: ExplorerSettings): boolean {
  return (
    settings.configOutputKind === "grid" &&
    usesFikoreBackend(settings) &&
    isParametricCondition(settings.conditionId) &&
    settings.gridSweepMode === "load_sweep"
  );
}

function checkCellTraverseBounds(settings: ExplorerSettings, conditionId: string): string | null {
  const values = resolveParametricCellValues(conditionId, settings.parametricOverrides[conditionId]);
  if (usesTraverseCorridor(values.study_mobility) && Math.abs(values.traverse_max_distance_m - values.traverse_min_distance_m) < 1.0) {
    return `${conditionId}: traverse_min_distance_m and traverse_max_distance_m must differ by at least 1 m.`;
  }
  if (!isValidStudyDlRmaxMbps(values.study_dl_rmax_mbps)) {
    return `${conditionId}: study_dl_rmax_mbps must be between 0.1 and 1000 Mbps when set.`;
  }
  return null;
}

/** Return a validation error string when any active text/parametric input cannot produce a runnable config. */
export function configValidationError(settings: ExplorerSettings): string | null {
  if (usesParametricLoadSweep(settings)) {
    const parsed = parseLoadSweepValues(settings.loadSweepValues);
    if (typeof parsed === "string") return parsed;
    const cellErr = checkCellTraverseBounds(settings, settings.conditionId);
    if (cellErr) return cellErr;
  } else if (usesFikoreBackend(settings)) {
    const ids = settings.configOutputKind === "grid" ? effectiveGridAxes(settings).conditionIds : [settings.conditionId];
    for (const id of ids) {
      const cellErr = checkCellTraverseBounds(settings, id);
      if (cellErr) return cellErr;
    }
  }
  if (settings.networkBackend !== "mock" && settings.swipeModel === "sequence") {
    const times = parseSwipeTimes(settings.swipeTimesS);
    if (typeof times === "string") return times;
  }
  return null;
}

/** Selected grid axes, with empty selections replaced by the run's value. */
export function effectiveGridAxes(settings: ExplorerSettings) {
  const axes = settings.gridAxes;
  const validIds = axes.conditionIds.filter((id) => NETWORK_CONDITIONS[id]);
  const conditionIds = usesFikoreBackend(settings)
    ? usesParametricLoadSweep(settings)
      ? effectiveLoadSweepRhos(settings).map(loadSweepConditionSlug)
      : validIds.length
        ? validIds
        : [settings.conditionId]
    : [];
  return {
    conditionIds,
    signalingLevels: axes.signalingLevels.length ? axes.signalingLevels : [settings.signalingLevel],
    ueCounts: axes.ueCounts.length ? [...axes.ueCounts].sort((a, b) => a - b) : [settings.videoUeCount],
    behaviorMixes: axes.behaviorMixes.length ? axes.behaviorMixes : [settings.behaviorMix],
    replications: Number.isInteger(axes.replications) && axes.replications >= 1 ? axes.replications : 1,
  };
}

export function gridCellCount(settings: ExplorerSettings): number {
  const axes = effectiveGridAxes(settings);
  if (usesParametricLoadSweep(settings) && axes.conditionIds.length === 0) return 0;
  return Math.max(1, axes.conditionIds.length) * axes.signalingLevels.length * axes.ueCounts.length * axes.behaviorMixes.length * axes.replications;
}

/** The grid file: an inline base experiment plus the axes. `capcsp grid` runs it as it is. */
export function buildGridConfig(settings: ExplorerSettings): JsonObject {
  const gridSettings = { ...settings, configOutputKind: "grid" as const };
  const loadSweep = usesParametricLoadSweep(gridSettings);
  const axes = effectiveGridAxes(gridSettings);
  // One session template per behaviour that a mix uses
  const behaviors = [...new Set(axes.behaviorMixes.flatMap((mix) => BEHAVIOR_MIXES[mix].pattern))];
  const baseConditionId = loadSweep ? gridSettings.conditionId : axes.conditionIds[0] ?? gridSettings.conditionId;
  const base = experimentConfig(
    gridSettings,
    {
      conditionId: baseConditionId,
      signalingLevels: axes.signalingLevels,
      ueIdsWithPlanRate: [...Array(Math.max(...axes.ueCounts)).keys()],
      sessions: behaviors.map((behavior, ueId) => session(gridSettings, ueId, behavior, sessionSeed(gridSettings, ueId))),
      fikoreMode: { kind: loadSweep ? "grid_base_load_sweep" : "grid_base_conditions" },
    },
    "explorer-base",
  );
  const grid: JsonObject = {
    grid_id: loadSweep ? `parametric-sweep-${gridSettings.conditionId.toLowerCase()}` : "explorer",
    base,
  };
  if (loadSweep) {
    const rhos = effectiveLoadSweepRhos(gridSettings);
    grid.conditions = Object.fromEntries(
      rhos.map((rho) => {
        const slug = loadSweepConditionSlug(rho);
        return [slug, { condition: slug, network: { parametric_cell: { load_rho: rho } } }];
      }),
    );
  } else if (axes.conditionIds.length) {
    grid.conditions = Object.fromEntries(axes.conditionIds.map((id) => [id, gridConditionOverlay(gridSettings, id)]));
  }
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
