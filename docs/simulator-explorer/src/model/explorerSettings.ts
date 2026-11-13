// Settings chosen in the control panel. They are mirrored in the URL hash,
// so a link reproduces a view.

export type ImplementationState = "design" | "master";
export type SignalingLevel = "L0" | "L1" | "L2" | "L3" | "L4";
export type NetworkBackendKind = "transport_fikore" | "constant_rate" | "mock";
export type PlayerBehavior = "simple" | "preload";
export type TcpConnectionMode = "persistent" | "fresh";
export type VideoUeCount = 1 | 2 | 4;

export interface ExplorerSettings {
  implementationState: ImplementationState;
  signalingLevel: SignalingLevel;
  networkBackend: NetworkBackendKind;
  /** FikoRE condition; only used with the transport_fikore backend. */
  conditionId: string;
  /** `downlink_rate_mbps` of the constant_rate backend, the same for every UE. */
  constantRateDownlinkMbps: string;
  playerBehavior: PlayerBehavior;
  videoUeCount: VideoUeCount;
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
  conditionId: "C2",
  constantRateDownlinkMbps: "1",
  playerBehavior: "preload",
  videoUeCount: 2,
  acksOverFikoreUplink: true,
  tcpConnectionMode: "persistent",
  planDownlinkMbps: "25",
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
