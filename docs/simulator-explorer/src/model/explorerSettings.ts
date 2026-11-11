// Settings chosen in the control panel. They are mirrored in the URL hash,
// so a link reproduces a view.

export type ImplementationState = "design" | "master" | "pr8";
export type SignalingLevel = "L0" | "L1" | "L2" | "L3" | "L4";
export type NetworkBackendKind = "transport_fikore" | "mock";
export type PlayerBehavior = "simple" | "preload";
export type TcpConnectionMode = "persistent" | "fresh";
export type VideoUeCount = 1 | 2 | 4;

export interface ExplorerSettings {
  implementationState: ImplementationState;
  signalingLevel: SignalingLevel;
  networkBackend: NetworkBackendKind;
  conditionId: string;
  playerBehavior: PlayerBehavior;
  videoUeCount: VideoUeCount;
  acksOverFikoreUplink: boolean;
  tcpConnectionMode: TcpConnectionMode;
  /** Empty string means no plan rate in the config. */
  planDownlinkMbps: string;
  dummyCspControllerEnabled: boolean;
}

export const DEFAULT_EXPLORER_SETTINGS: ExplorerSettings = {
  implementationState: "pr8",
  signalingLevel: "L2",
  networkBackend: "transport_fikore",
  conditionId: "C2",
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

export function usesFikoreBackend(settings: ExplorerSettings): boolean {
  return settings.networkBackend === "transport_fikore";
}
