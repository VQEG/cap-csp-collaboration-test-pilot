import { SIGNALING_LEVELS } from "@/data/signalingLevels";
import { signalingLevelNumber, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

// Banner text: is the chosen level implemented in the chosen state?

export type ImplementationStatusKind = "ok" | "partial" | "none";

export interface ImplementationStatus {
  kind: ImplementationStatusKind;
  title: string;
  /** Text in `backticks` is rendered as code. */
  explanation: string;
}

export function describeImplementationStatus(settings: ExplorerSettings): ImplementationStatus {
  const level = signalingLevelNumber(settings.signalingLevel);
  const fikore = usesFikoreBackend(settings);
  const planRateConfigured = settings.planDownlinkMbps !== "";

  if (settings.implementationState === "design") {
    if (level === 3)
      return {
        kind: "partial",
        title: "Specified in parts",
        explanation:
          "The FikoRE control path (`set_ue_control`: priority, rmax_mbps) exists. The controller algorithm, its inputs, interval and damping are still open, and L3 is excluded from milestone 1.",
      };
    if (level === 4)
      return {
        kind: "partial",
        title: "Specified in parts",
        explanation:
          "Single UE: trace from an offline full-buffer FikoRE run with the same seeds. Multi-UE runs must state whether the oracle is exogenous or demand-coupled.",
      };
    return { kind: "ok", title: "Specified", explanation: SIGNALING_LEVELS[settings.signalingLevel].description };
  }

  if (settings.implementationState === "master") {
    if (level === 0) return { kind: "ok", title: "Implemented", explanation: "L0 is what every run on master does." };
    return {
      kind: "none",
      title: "Not connected",
      explanation:
        "On master, `signaling_level` is only a label in the outputs. Telemetry reaches the Node harness and is stored per UE, but the SFV engine has no input for it, so the run behaves exactly like L0.",
    };
  }

  // PR #8
  if (level === 0)
    return {
      kind: "ok",
      title: "Implemented",
      explanation:
        "Telemetry and CAP reports are still written to the table and to `shared-state.jsonl` for audit, but reads return nothing: `collaboration.csp_by_ue` is empty.",
    };
  if (level === 1) {
    if (!planRateConfigured)
      return {
        kind: "partial",
        title: "Implemented, needs a plan rate",
        explanation: "Set `plan_downlink_mbps_by_ue` in the config, otherwise the plan rate is null.",
      };
    return {
      kind: "ok",
      title: "Implemented",
      explanation:
        "The plan rate is seeded into the table at run start (also on mock), and reads return only `plan_downlink_mbps`. The player stores it via `applyCspUpdate` (SFV PR #2); B1/B2 do not use it yet.",
    };
  }
  if (level === 2) {
    if (!fikore)
      return {
        kind: "partial",
        title: "Live fields empty on mock",
        explanation: "The mock backend emits no telemetry, so only the plan rate (if set) reaches the player. The live fields stay null.",
      };
    return {
      kind: "ok",
      title: "Implemented",
      explanation:
        "Reads return all `CspFields` mapped from FikoRE telemetry. The SFV engine receives them via `applyCspUpdate`; the B1/B2 rules do not use them yet.",
    };
  }
  if (level === 3) {
    if (!settings.dummyCspControllerEnabled)
      return {
        kind: "partial",
        title: "CAP reports only",
        explanation: "CAP reports are written to the table, but without `csp_controller: \"dummy\"` nobody reads them.",
      };
    return {
      kind: "partial",
      title: "Implemented as a dry run",
      explanation:
        "`DummyCSPController` reads CAP reports and, on a stall, proposes priority × 2. Proposals go to `csp-control.jsonl`; `set_ue_control` is never called, so the network does not change.",
    };
  }
  return {
    kind: "none",
    title: "Not implemented",
    explanation: "L4 is parsed and behaves like L3: all CSP fields, CAP reports readable by the controller. There is no oracle trace.",
  };
}
