import type { ContentCatalogueId } from "@/data/contentCatalogue";
import { CORE6_CONDITION_IDS, type ParametricCellValues } from "@/data/parametricCells";
import { PLAYER_BEHAVIORS, type BehaviorMixId, type BehaviorParameterValues, type PlayerBehavior } from "@/data/playerBehaviors";

// Settings chosen in the control panel and the experiment design card. They
// are mirrored in the URL hash, so a link reproduces a view.

export type ImplementationState = "design" | "master";
export type SignalingLevel = "L0" | "L1" | "L2" | "L3" | "L4";
export type NetworkBackendKind = "transport_fikore" | "constant_rate" | "mock";
export type TcpConnectionMode = "persistent" | "fresh";
export type ConfigOutputKind = "run" | "grid";
export type SwipeModelKind = "seeded" | "sequence";
export type GridSweepMode = "conditions" | "load_sweep";

export const VIDEO_UE_COUNT_CHOICES = [1, 2, 3, 4, 6, 8];

export interface GridAxes {
  conditionIds: string[];
  signalingLevels: SignalingLevel[];
  ueCounts: number[];
  behaviorMixes: BehaviorMixId[];
  replications: number;
}

export interface ExplorerSettings {
  implementationState: ImplementationState;
  signalingLevel: SignalingLevel;
  networkBackend: NetworkBackendKind;
  /** FikoRE condition; only used with the transport_fikore backend. */
  conditionId: string;
  /** Content catalogue used by the sessions. */
  contentId: ContentCatalogueId;
  /** `downlink_rate_mbps` of the constant_rate backend, the same for every UE. */
  constantRateDownlinkMbps: string;
  /** Behaviour pattern over the UEs of the run, and of the cell shown in grid mode. */
  behaviorMix: BehaviorMixId;
  videoUeCount: number;
  behaviorParameters: Record<PlayerBehavior, BehaviorParameterValues>;
  swipeModel: SwipeModelKind;
  /** Range of the seeded model's time between swipes, in seconds. */
  watchDurationRangeS: [number, number];
  /** Session-relative swipe times of the sequence model, comma-separated. */
  swipeTimesS: string;
  /** Changed legacy C1–C8b INI parameters: condition id → parameter id → displayed value. */
  conditionOverrides: Record<string, Record<string, number>>;
  /** Changed parametric cell parameters for M01–M11 and CUSTOM. */
  parametricOverrides: Record<string, Partial<ParametricCellValues>>;
  configOutputKind: ConfigOutputKind;
  /** Grid condition source: explicit list of conditions or a load_rho sweep over the current parametric cell. */
  gridSweepMode: GridSweepMode;
  /** Comma-separated load_rho values used when gridSweepMode === "load_sweep". */
  loadSweepValues: string;
  gridAxes: GridAxes;
  acksOverFikoreUplink: boolean;
  tcpConnectionMode: TcpConnectionMode;
  /** Empty string means no plan rate in the config. */
  planDownlinkMbps: string;
  dummyCspControllerEnabled: boolean;
}

export const DEFAULT_EXPLORER_SETTINGS: ExplorerSettings = {
  implementationState: "master",
  signalingLevel: "L2",
  networkBackend: "transport_fikore",
  conditionId: "M04",
  contentId: "portrait_hd_90s",
  constantRateDownlinkMbps: "1",
  behaviorMix: "b1-b2",
  videoUeCount: 2,
  behaviorParameters: { simple: { ...PLAYER_BEHAVIORS.simple.defaults }, preload: { ...PLAYER_BEHAVIORS.preload.defaults } },
  swipeModel: "seeded",
  watchDurationRangeS: [2, 16],
  swipeTimesS: "4, 10",
  conditionOverrides: {},
  parametricOverrides: {},
  configOutputKind: "run",
  gridSweepMode: "conditions",
  loadSweepValues: "0, 0.25, 0.5, 0.75, 1.0",
  gridAxes: { conditionIds: [...CORE6_CONDITION_IDS], signalingLevels: ["L0"], ueCounts: [2], behaviorMixes: ["b1-b2"], replications: 5 },
  acksOverFikoreUplink: true,
  tcpConnectionMode: "persistent",
  planDownlinkMbps: "",
  dummyCspControllerEnabled: true,
};

export function signalingLevelNumber(level: SignalingLevel): number {
  return Number(level.slice(1));
}

export const NETWORK_BACKEND_KINDS: NetworkBackendKind[] = ["transport_fikore", "constant_rate", "mock"];

export function usesFikoreBackend(settings: ExplorerSettings): boolean {
  return settings.networkBackend === "transport_fikore";
}

export function usesConstantRateBackend(settings: ExplorerSettings): boolean {
  return settings.networkBackend === "constant_rate";
}

/** Only transport_fikore has a CSP telemetry source; mock and constant_rate write no telemetry. */
export function backendHasCspTelemetrySource(settings: ExplorerSettings): boolean {
  return usesFikoreBackend(settings);
}

/** The constant_rate per-UE rate in Mbps; falls back to the default when the input is empty or not positive. */
export function constantRateDownlinkMbps(settings: ExplorerSettings): number {
  const rate = Number(settings.constantRateDownlinkMbps);
  return settings.constantRateDownlinkMbps !== "" && Number.isFinite(rate) && rate > 0 ? rate : Number(DEFAULT_EXPLORER_SETTINGS.constantRateDownlinkMbps);
}

/** `synthetic_delay_ms` and `cancellation_tail_bytes` as in configs/experiments/b1-b2-two-ue-constant-rate.json. */
export const CONSTANT_RATE_SYNTHETIC_DELAY_MS = 25;
export const CONSTANT_RATE_CANCELLATION_TAIL_BYTES = 0;

/** Backends that get FikoreControlAdapter, so `set_ue_control` would reach them. mock gets NoOpControlAdapter. */
export function backendAcceptsUeControl(settings: ExplorerSettings): boolean {
  return settings.networkBackend === "transport_fikore" || settings.networkBackend === "constant_rate";
}
