import { SIGNALING_LEVELS } from "@/data/signalingLevels";
import { backendHasCspTelemetrySource, hasPlanRate, signalingLevelNumber, usesConstantRateBackend, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

// Banner text: what the chosen level does in the chosen state, in plain words.

export type ImplementationStatusKind = "ok" | "partial" | "none";

export interface ImplementationStatus {
  kind: ImplementationStatusKind;
  title: string;
  /** Text in `backticks` is rendered as code. */
  explanation: string;
}

const CONTROLLER_STILL_OPEN = "The controller itself (algorithm, inputs, interval, damping) is still to be specified. L3 is not part of milestone 1.";

export function describeImplementationStatus(settings: ExplorerSettings): ImplementationStatus {
  const level = signalingLevelNumber(settings.signalingLevel);
  const hasTelemetrySource = backendHasCspTelemetrySource(settings);
  const constantRate = usesConstantRateBackend(settings);
  // An explicit plan rate, or the static `study_dl_rmax_mbps` cap of the current condition on FikoRE.
  const planRateConfigured = hasPlanRate(settings);
  const planFromStaticCap = planRateConfigured && settings.planDownlinkMbps === "" && usesFikoreBackend(settings);

  if (settings.implementationState === "design") {
    if (level === 3 && constantRate)
      return {
        kind: "partial",
        title: "Specified in parts",
        explanation: `A controller can change how the network serves a UE with \`set_ue_control\`. On \`ConstantRateBackend\`, \`rmax_mbps\` caps the UE's rate from the next step, and \`priority\` is recorded. ${CONTROLLER_STILL_OPEN}`,
      };
    if (level === 3)
      return {
        kind: "partial",
        title: "Specified in parts",
        explanation: `A controller can change how the network serves a UE with \`set_ue_control\`. FikoRE takes a scheduling priority and a rate cap (\`rmax_mbps\`). ${CONTROLLER_STILL_OPEN}`,
      };
    if (level === 4)
      return {
        kind: "partial",
        title: "Specified in parts",
        explanation:
          "With one UE, the oracle trace comes from an offline full-buffer FikoRE run with the same seeds. With several UEs, each run states whether the trace is fixed in advance or depends on the players' demand.",
      };
    return { kind: "ok", title: "Specified", explanation: SIGNALING_LEVELS[settings.signalingLevel].description };
  }

  // master
  if (level === 0)
    return {
      kind: "ok",
      title: "Implemented",
      explanation:
        "The player gets no network information and estimates throughput from its own downloads. The harness still logs network telemetry and player reports to `shared-state.jsonl`.",
    };
  if (level === 1) {
    if (!planRateConfigured)
      return {
        kind: "partial",
        title: "Implemented, needs a plan rate",
        explanation:
          "The player gets the plan rate from `plan_downlink_mbps_by_ue` in the config, or, on FikoRE, from the static cap `parametric_cell.study_dl_rmax_mbps` of the condition. Neither is set yet, so B1 and B2 behave as at L0.",
      };
    return {
      kind: "ok",
      title: "Implemented",
      explanation: `At the start of the run, the player gets its plan rate (\`plan_downlink_mbps\`)${
        planFromStaticCap ? " from the static cap `study_dl_rmax_mbps` of the condition, as no explicit plan rate is set" : " from the config"
      }. This works with every backend. B1 and B2 use it to cap their selected ABR bitrate at \`plan_downlink_mbps * planSafetyFactor\`.`,
    };
  }
  if (level === 2) {
    if (!hasTelemetrySource)
      return {
        kind: "partial",
        title: `Live fields empty on ${settings.networkBackend}`,
        explanation:
          "The player gets the plan rate, if one is set; B1 and B2 cap their selected ABR bitrate with it, as at L1. Live network measurements come only from the FikoRE backend.",
      };
    return {
      kind: "ok",
      title: "Implemented",
      explanation:
        "Every second (`csp_telemetry_interval_s`), the player gets live measurements from FikoRE: achieved throughput, RTT and loss, plus the plan rate. B1 and B2 cap their selected ABR bitrate with the plan rate, if one is set, as at L1. The live measurements are recorded and delivered, but they do not change the rule selection yet.",
    };
  }
  if (level === 3) {
    if (!settings.dummyCspControllerEnabled)
      return {
        kind: "partial",
        title: "Player reports only",
        explanation:
          "The player also reports to the network: stalls, buffer level, current video and swipe rate. To have a controller read these reports, set `csp_controller: \"dummy\"`.",
      };
    return {
      kind: "partial",
      title: "Implemented as a dry run",
      explanation:
        "The player also reports stalls, buffer level, current video and swipe rate. `DummyCSPController` reads these reports. When a player stalls, it proposes to double that UE's priority and logs the proposal to `csp-control.jsonl`. The proposal is not applied yet.",
    };
  }
  return {
    kind: "none",
    title: "Not implemented",
    explanation: "L4 runs like L3. The trace of future capacity is not built yet.",
  };
}
