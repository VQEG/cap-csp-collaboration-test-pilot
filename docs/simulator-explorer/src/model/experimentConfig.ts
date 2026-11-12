import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import { signalingLevelNumber, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

// The experiment JSON for the chosen settings. Keep its keys in sync with
// configs/experiments/ and capcsp/runner/run.py.

export function buildExperimentConfig(settings: ExplorerSettings): Record<string, unknown> {
  const fikore = usesFikoreBackend(settings);
  const condition = NETWORK_CONDITIONS[settings.conditionId];
  const level = signalingLevelNumber(settings.signalingLevel);
  const levelSlug = settings.signalingLevel.toLowerCase();
  const ueIds = [...Array(settings.videoUeCount).keys()];

  const config: Record<string, unknown> = {
    run_id: fikore ? `vqeg-${settings.conditionId.toLowerCase()}-${levelSlug}` : `mock-${levelSlug}`,
    network_backend: settings.networkBackend,
    network: fikore
      ? {
          congestion_control: "cubic",
          receive_window_bytes: 1048576,
          tcp_connection_mode: settings.tcpConnectionMode,
          max_idle_tcp_connections_per_ue: 6,
          step_ms: 10,
          fikore_base_ini: `configs/fikore/${condition.fikoreIniFile}`,
          study_ues: ["studyVqeg"],
          ack_over_link: settings.acksOverFikoreUplink,
          delay_budget_s: null,
          random_v: null,
          fikore_section_overrides: { Global: { seed: 20260927 } },
        }
      : { step_s: 0.01, cell_bytes_per_step: 80000, cancellation_tail_bytes: 512 },
    condition: fikore ? settings.conditionId : "example-only",
    signaling_level: settings.signalingLevel,
  };

  config.clock_mode = "simulation";
  if (level >= 1 && settings.planDownlinkMbps !== "") {
    config.plan_downlink_mbps_by_ue = Object.fromEntries(ueIds.map((ueId) => [String(ueId), Number(settings.planDownlinkMbps)]));
  }
  if (level >= 3) config.csp_controller = settings.dummyCspControllerEnabled ? "dummy" : null;

  config.duration_s = fikore ? condition.durationSeconds : 0.2;
  config.timingDefaults = {
    playbackTiming: { mode: "causal-simple", slotPreparationS: 0.01, appendDurationS: 0.005, startupDelayS: 0.005, observationIntervalS: 0.05 },
  };
  config.sessions = ueIds.map((ueId) => ({
    ue_id: ueId,
    player_behavior: settings.playerBehavior,
    config: {
      sessionId: `generic-ue${ueId}`,
      seed: 17 + 4 * ueId,
      scheduling: { maxConcurrentRequests: settings.playerBehavior === "simple" ? 2 : 3 },
      swipeTimesS: [Math.round((0.1 + 0.01 * ueId) * 100) / 100],
    },
    rule_config:
      settings.playerBehavior === "simple"
        ? { activeBufferTargetSegments: 2 }
        : { activeBufferTargetSegments: 2, max_preload_segments: 4, preload_segments_per_video: 2 },
  }));
  return config;
}
