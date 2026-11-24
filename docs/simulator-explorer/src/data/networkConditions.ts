// Calibrated FikoRE conditions:
// Parametric single-cell 5G presets M01–M11 (Core-6 test plan + ablation) and CUSTOM,
// matching capcsp/network/parametric_cell.py and configs/experiments/layered/README.md.

import {
  estimateMeanActiveBgUes,
  isParametricCondition,
  resolveParametricCellValues,
  type ParametricCellValues,
} from "@/data/parametricCells";

export type ConditionFamily = "core6" | "layered_extended" | "custom";

export interface NetworkCondition {
  name: string;
  family: ConditionFamily;
  /** Calibration band for downlink throughput, Mbps (low = P10, midpoint = calibrated mean). */
  downlinkMbpsBand: [number, number];
  /** Calibration band for RTT, ms. */
  rttMsBand: [number, number];
  /** Calibration band for loss, percent. */
  lossPercentBand: [number, number];
  dominantCause: string;
  backgroundUeCount: number;
  timelineFile: string | null;
  durationSeconds: number;
  /** Plan rate preset when the condition is selected. */
  defaultPlanDownlinkMbps?: number;
}

export const NETWORK_CONDITIONS: Record<string, NetworkCondition> = {
  M01: {
    name: "Base good SINR (0% load)",
    family: "core6",
    downlinkMbpsBand: [61.0, 63.6],
    rttMsBand: [33, 36],
    lossPercentBand: [0, 0.05],
    dominantCause: "none (20 MHz UMa n78 ceiling, 0.154 RBG/Mbps)",
    backgroundUeCount: 0,
    timelineFile: null,
    durationSeconds: 65,
  },
  M02: {
    name: "Center 50% homo load",
    family: "layered_extended",
    downlinkMbpsBand: [5.6, 25.2],
    rttMsBand: [95, 210],
    lossPercentBand: [0, 0.3],
    dominantCause: "stationary Poisson contention (ρ=0.50, ring, 0.139 RBG/Mbps)",
    backgroundUeCount: 8,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M03: {
    name: "Center 75% homo load",
    family: "layered_extended",
    downlinkMbpsBand: [4.8, 20.8],
    rttMsBand: [130, 260],
    lossPercentBand: [0.3, 1.5],
    dominantCause: "moderate Poisson contention (ρ=0.75, ring, 0.137 RBG/Mbps)",
    backgroundUeCount: 12,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M04: {
    name: "Center 100% saturation",
    family: "core6",
    downlinkMbpsBand: [1.7, 5.9],
    rttMsBand: [220, 350],
    lossPercentBand: [1.0, 2.0],
    dominantCause: "stationary cell saturation (ρ=1.00, 0.147 RBG/Mbps)",
    backgroundUeCount: 16,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M05: {
    name: "Center 100% MMPP bursts",
    family: "core6",
    downlinkMbpsBand: [1.3, 6.3],
    rttMsBand: [210, 360],
    lossPercentBand: [0.8, 2.2],
    dominantCause: "MMPP congestion waves (±65% arrival bursts, τ=12 s, 0.152 RBG/Mbps)",
    backgroundUeCount: 16,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M06: {
    name: "Center + spatial disk 100%",
    family: "layered_extended",
    downlinkMbpsBand: [10.6, 32.5],
    rttMsBand: [95, 160],
    lossPercentBand: [0.1, 0.5],
    dominantCause: "heterogeneous disk load (PF preserves good-SINR rate, 0.139 RBG/Mbps)",
    backgroundUeCount: 6,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M07: {
    name: "Mid-cell 100% spatial load",
    family: "core6",
    downlinkMbpsBand: [5.1, 10.1],
    rttMsBand: [155, 230],
    lossPercentBand: [0.4, 1.0],
    dominantCause: "mid-cell geometry + 100% disk load (0.311 RBG/Mbps)",
    backgroundUeCount: 6,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M08: {
    name: "Cell-edge 50% spatial load",
    family: "layered_extended",
    downlinkMbpsBand: [2.1, 6.1],
    rttMsBand: [185, 250],
    lossPercentBand: [0.5, 1.5],
    dominantCause: "cell-edge MCS 2 + 50% disk load (1.173 RBG/Mbps)",
    backgroundUeCount: 3,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M09: {
    name: "Cell-edge 75% spatial load",
    family: "core6",
    downlinkMbpsBand: [0.9, 4.1],
    rttMsBand: [230, 290],
    lossPercentBand: [1.0, 1.8],
    dominantCause: "congested cell edge (1.026 RBG/Mbps — costly L3 boost)",
    backgroundUeCount: 5,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M10: {
    name: "Vehicular traverse (73 km/h)",
    family: "core6",
    downlinkMbpsBand: [11.1, 38.3],
    rttMsBand: [60, 260],
    lossPercentBand: [0.2, 1.5],
    dominantCause: "radial traverse 151↔660 m + 50% disk load (0.229 RBG/Mbps)",
    backgroundUeCount: 3,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  M11: {
    name: "Pedestrian edge (3.6 km/h)",
    family: "layered_extended",
    downlinkMbpsBand: [3.2, 8.1],
    rttMsBand: [165, 240],
    lossPercentBand: [0.3, 1.2],
    dominantCause: "edge pedestrian walk (study UE only) + 50% disk load (1.001 RBG/Mbps)",
    backgroundUeCount: 3,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
  CUSTOM: {
    name: "Custom parametric cell",
    family: "custom",
    downlinkMbpsBand: [8, 28],
    rttMsBand: [80, 190],
    lossPercentBand: [0.1, 1.0],
    dominantCause: "user-defined parametric 5G cell (synthesized INI + timeline)",
    backgroundUeCount: 3,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },
};

export function bandMidpoint([low, high]: [number, number]): number {
  return Math.round(((low + high) / 2) * 10) / 10;
}

/** Condition metadata adjusted for any active parametric overrides. */
export function effectiveConditionView(
  conditionId: string,
  parametricOverrides?: Partial<ParametricCellValues>,
): NetworkCondition {
  const base = NETWORK_CONDITIONS[conditionId];
  if (!isParametricCondition(conditionId)) return base;
  const hasOverrides = parametricOverrides && Object.keys(parametricOverrides).length > 0;
  if (conditionId !== "CUSTOM" && !hasOverrides) return base;

  const values = resolveParametricCellValues(conditionId, parametricOverrides);
  const lambdaBg = estimateMeanActiveBgUes(values);
  const bwFactor = values.bandwidth_mhz / 20;
  const dist = values.study_distance_m;
  const soloCap20 = dist <= 220 ? 62 : dist <= 450 ? 21 : 6.2;
  const soloCap = soloCap20 * bwFactor;
  const residualShare = values.bg_spatial === "homogeneous_ring"
    ? Math.max(0.06, 1 - 0.88 * Math.min(1.08, values.load_rho))
    : Math.max(0.18, 1 - 0.65 * Math.min(1.15, values.load_rho));
  const meanTp = Math.max(0.8, soloCap * residualShare);
  const spread = values.arrival_mode === "mmpp" || values.study_mobility === "vehicular_traverse" ? 0.55 : 0.25;
  const lowTp = Math.max(0.5, Math.round(meanTp * (1 - spread) * 10) / 10);
  const highTp = Math.max(lowTp + 0.5, Math.round(Math.min(soloCap, meanTp * (1 + spread)) * 10) / 10);
  const baseRtt = 2 * values.backhaul_delay_ms + 14;
  const queueRtt = Math.round(160 * Math.min(1.3, values.load_rho));
  return {
    ...base,
    downlinkMbpsBand: [lowTp, highTp],
    rttMsBand: [Math.round(baseRtt + 0.4 * queueRtt), Math.round(baseRtt + 1.3 * queueRtt)],
    lossPercentBand: values.load_rho <= 0 ? [0, 0.05] : [0.2, Math.round(Math.min(4, 1.8 * values.load_rho) * 10) / 10],
    backgroundUeCount: Math.round(lambdaBg),
    durationSeconds: values.duration_s,
    timelineFile: values.load_rho > 0 || values.study_mobility === "vehicular_traverse" ? "fikore-timeline.ndjson" : null,
    dominantCause: `${values.bandwidth_mhz} MHz · d=${Math.round(dist)} m (${values.study_mobility}) · ρ=${values.load_rho.toFixed(2)} (${values.bg_spatial}, ${values.arrival_mode})`,
  };
}
