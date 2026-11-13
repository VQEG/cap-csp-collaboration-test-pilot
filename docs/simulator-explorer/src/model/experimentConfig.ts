import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import {
  CONSTANT_RATE_CANCELLATION_TAIL_BYTES,
  CONSTANT_RATE_SYNTHETIC_DELAY_MS,
  constantRateDownlinkMbps,
  signalingLevelNumber,
  usesConstantRateBackend,
  usesFikoreBackend,
  type ExplorerSettings,
} from "@/model/explorerSettings";

// The experiment JSON for the chosen settings. Keep its keys in sync with
// configs/experiments/ and capcsp/runner/run.py.

/** Directory of the experiment file: the FikoRE condition runs are in vqeg/, the mock and constant_rate examples next to it. */
export function experimentConfigDirectory(settings: ExplorerSettings): string {
  return usesFikoreBackend(settings) ? "configs/experiments/vqeg/" : "configs/experiments/";
}

function buildNetworkSettings(settings: ExplorerSettings): Record<string, unknown> {
  if (usesFikoreBackend(settings)) {
    const condition = NETWORK_CONDITIONS[settings.conditionId];
    return {
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
    };
  }
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

function buildRunId(settings: ExplorerSettings): string {
  const levelSlug = settings.signalingLevel.toLowerCase();
  if (usesFikoreBackend(settings)) return `vqeg-${settings.conditionId.toLowerCase()}-${levelSlug}`;
  if (usesConstantRateBackend(settings)) return `constant-rate-${levelSlug}`;
  return `mock-${levelSlug}`;
}

/** Run length in seconds: the condition's duration on FikoRE, as in the b1-b2-two-ue-*.json examples otherwise. */
function runDurationSeconds(settings: ExplorerSettings): number {
  if (usesFikoreBackend(settings)) return NETWORK_CONDITIONS[settings.conditionId].durationSeconds;
  if (usesConstantRateBackend(settings)) return 20;
  return 0.2;
}

/**
 * Swipes of one session. The condition and constant-rate configurations use the seeded user model of SFV,
 * which draws the time between swipes from 2–16 s; the 0.2 s mock smoke test keeps one fixed swipe.
 */
function swipeSettings(settings: ExplorerSettings, ueId: number): Record<string, unknown> {
  if (usesFikoreBackend(settings) || usesConstantRateBackend(settings)) {
    return { userModel: { type: "seeded", watchDurationRangeS: [2, 16] } };
  }
  return { swipeTimesS: [Math.round((0.1 + 0.01 * ueId) * 100) / 100] };
}

export function buildExperimentConfig(settings: ExplorerSettings): Record<string, unknown> {
  const fikore = usesFikoreBackend(settings);
  const level = signalingLevelNumber(settings.signalingLevel);
  const ueIds = [...Array(settings.videoUeCount).keys()];

  const config: Record<string, unknown> = {
    run_id: buildRunId(settings),
    network_backend: settings.networkBackend,
    network: buildNetworkSettings(settings),
    condition: fikore ? settings.conditionId : "example-only",
    signaling_level: settings.signalingLevel,
  };

  config.clock_mode = "simulation";
  if (level >= 1 && settings.planDownlinkMbps !== "") {
    config.plan_downlink_mbps_by_ue = Object.fromEntries(ueIds.map((ueId) => [String(ueId), Number(settings.planDownlinkMbps)]));
  }
  if (level >= 3) config.csp_controller = settings.dummyCspControllerEnabled ? "dummy" : null;

  config.duration_s = runDurationSeconds(settings);
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
      ...swipeSettings(settings, ueId),
    },
    rule_config:
      settings.playerBehavior === "simple"
        ? { activeBufferTargetSegments: 2 }
        : { activeBufferTargetSegments: 2, max_preload_segments: 4, preload_segments_per_video: 2 },
  }));
  return config;
}
