// Calibrated FikoRE conditions:
// - Parametric 4-tier 5G cell presets M01–M11 (Core-6 test plan + ablation) and CUSTOM
// - Legacy VQEG conditions C1–C8b from configs/fikore/README.md

import {
  estimateMeanActiveBgUes,
  isParametricCondition,
  resolveParametricCellValues,
  type ParametricCellValues,
} from "@/data/parametricCells";

export type ConditionFamily = "core6" | "layered_extended" | "custom" | "legacy";

export interface NetworkCondition {
  name: string;
  family: ConditionFamily;
  /** Calibration band for downlink throughput, Mbps. */
  downlinkMbpsBand: [number, number];
  /** Calibration band for RTT, ms. */
  rttMsBand: [number, number];
  /** Calibration band for loss, percent. */
  lossPercentBand: [number, number];
  dominantCause: string;
  backgroundUeCount: number;
  fikoreIniFile: string | null;
  timelineFile: string | null;
  durationSeconds: number;
  /** Plan rate preset when the condition is selected. */
  defaultPlanDownlinkMbps?: number;
}

export const NETWORK_CONDITIONS: Record<string, NetworkCondition> = {
  // Parametric 4-tier 5G cell conditions (M01–M11 + CUSTOM)
  M01: {
    name: "Base good SINR (0% load)",
    family: "core6",
    downlinkMbpsBand: [50, 62],
    rttMsBand: [35, 55],
    lossPercentBand: [0, 0.05],
    dominantCause: "none (20 MHz UMa n78 ceiling, 0.15 RBG/Mbps)",
    backgroundUeCount: 0,
    fikoreIniFile: "layered/m01_l1_base_good_static.ini",
    timelineFile: null,
    durationSeconds: 65,
  },
  M02: {
    name: "Center 50% homo load",
    family: "layered_extended",
    downlinkMbpsBand: [18, 26],
    rttMsBand: [95, 130],
    lossPercentBand: [0, 0.3],
    dominantCause: "stationary Poisson contention (ρ=0.50, ring)",
    backgroundUeCount: 8,
    fikoreIniFile: "layered/m02_l2_homo_rho050_med.ini",
    timelineFile: "m02_l2_homo_rho050_med.ndjson",
    durationSeconds: 65,
  },
  M03: {
    name: "Center 75% homo load",
    family: "layered_extended",
    downlinkMbpsBand: [6, 12],
    rttMsBand: [190, 290],
    lossPercentBand: [0.5, 1.8],
    dominantCause: "moderate Poisson contention (ρ=0.75, ring)",
    backgroundUeCount: 12,
    fikoreIniFile: "layered/m03_l2_homo_rho075_med.ini",
    timelineFile: "m03_l2_homo_rho075_med.ndjson",
    durationSeconds: 65,
  },
  M04: {
    name: "Center 100% saturation",
    family: "core6",
    downlinkMbpsBand: [3, 5],
    rttMsBand: [220, 350],
    lossPercentBand: [1, 2],
    dominantCause: "stationary cell saturation (ρ=1.00, 0.15 RBG/Mbps)",
    backgroundUeCount: 16,
    fikoreIniFile: "layered/m04_l2_homo_rho100_med.ini",
    timelineFile: "m04_l2_homo_rho100_med.ndjson",
    durationSeconds: 65,
  },
  M05: {
    name: "Center 100% MMPP bursts",
    family: "core6",
    downlinkMbpsBand: [1.5, 8],
    rttMsBand: [220, 320],
    lossPercentBand: [0.8, 2.2],
    dominantCause: "MMPP congestion waves (±65% arrival bursts, τ=12 s)",
    backgroundUeCount: 16,
    fikoreIniFile: "layered/m05_l2_homo_rho100_high.ini",
    timelineFile: "m05_l2_homo_rho100_high.ndjson",
    durationSeconds: 65,
  },
  M06: {
    name: "Center + spatial disk 100%",
    family: "layered_extended",
    downlinkMbpsBand: [18, 23],
    rttMsBand: [110, 145],
    lossPercentBand: [0.1, 0.5],
    dominantCause: "heterogeneous disk load (PF preserves good-SINR rate)",
    backgroundUeCount: 6,
    fikoreIniFile: "layered/m06_l3_good_het_rho100_med.ini",
    timelineFile: "m06_l3_good_het_rho100_med.ndjson",
    durationSeconds: 65,
  },
  M07: {
    name: "Mid-cell 100% spatial load",
    family: "core6",
    downlinkMbpsBand: [6.5, 9],
    rttMsBand: [155, 230],
    lossPercentBand: [0.4, 1.0],
    dominantCause: "mid-cell geometry + 100% disk load (0.31 RBG/Mbps)",
    backgroundUeCount: 6,
    fikoreIniFile: "layered/m07_l3_mid_het_rho100_med.ini",
    timelineFile: "m07_l3_mid_het_rho100_med.ndjson",
    durationSeconds: 65,
  },
  M08: {
    name: "Cell-edge 50% spatial load",
    family: "layered_extended",
    downlinkMbpsBand: [2.5, 4.2],
    rttMsBand: [185, 250],
    lossPercentBand: [0.5, 1.5],
    dominantCause: "cell-edge MCS 2 + 50% disk load (1.17 RBG/Mbps)",
    backgroundUeCount: 3,
    fikoreIniFile: "layered/m08_l3_edge_het_rho050_med.ini",
    timelineFile: "m08_l3_edge_het_rho050_med.ndjson",
    durationSeconds: 65,
  },
  M09: {
    name: "Cell-edge 75% spatial load",
    family: "core6",
    downlinkMbpsBand: [2.0, 3.2],
    rttMsBand: [235, 280],
    lossPercentBand: [1.0, 1.8],
    dominantCause: "congested cell edge (1.03 RBG/Mbps — costly L3 boost)",
    backgroundUeCount: 5,
    fikoreIniFile: "layered/m09_l3_edge_het_rho075_med.ini",
    timelineFile: "m09_l3_edge_het_rho075_med.ndjson",
    durationSeconds: 65,
  },
  M10: {
    name: "Vehicular traverse (73 km/h)",
    family: "core6",
    downlinkMbpsBand: [2.5, 35],
    rttMsBand: [60, 260],
    lossPercentBand: [0.2, 1.5],
    dominantCause: "radial traverse 151↔660 m + 50% disk load (non-stationary RB cost)",
    backgroundUeCount: 3,
    fikoreIniFile: "layered/m10_l4_veh_traverse_het_rho050.ini",
    timelineFile: "m10_l4_veh_traverse_het_rho050.ndjson",
    durationSeconds: 65,
  },
  M11: {
    name: "Pedestrian edge (3.6 km/h)",
    family: "layered_extended",
    downlinkMbpsBand: [2.8, 5.5],
    rttMsBand: [170, 240],
    lossPercentBand: [0.3, 1.2],
    dominantCause: "edge pedestrian walk + 50% disk load (1.00 RBG/Mbps)",
    backgroundUeCount: 3,
    fikoreIniFile: "layered/m11_l4_ped_edge_het_rho050.ini",
    timelineFile: "m11_l4_ped_edge_het_rho050.ndjson",
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
    fikoreIniFile: null,
    timelineFile: "fikore-timeline.ndjson",
    durationSeconds: 65,
  },

  // Legacy VQEG calibration conditions (C1–C8b)
  C1: { name: "Healthy 5G", family: "legacy", downlinkMbpsBand: [48, 80], rttMsBand: [15, 40], lossPercentBand: [0, 0.1], dominantCause: "none", backgroundUeCount: 0, fikoreIniFile: "c1_healthy_5g.ini", timelineFile: null, durationSeconds: 120 },
  C2: { name: "Plan-capped", family: "legacy", downlinkMbpsBand: [20, 30], rttMsBand: [20, 45], lossPercentBand: [0, 0.1], dominantCause: "rate_cap (25 Mbps per-UE grant cap)", backgroundUeCount: 0, fikoreIniFile: "c2_plan_capped.ini", timelineFile: "c2_plan_cap.ndjson", durationSeconds: 120, defaultPlanDownlinkMbps: 25 },
  C3: { name: "Borderline cell", family: "legacy", downlinkMbpsBand: [8, 16], rttMsBand: [25, 60], lossPercentBand: [0, 0.5], dominantCause: "radio_capacity (MCS 0 region)", backgroundUeCount: 0, fikoreIniFile: "c3_borderline_cell.ini", timelineFile: "c3_rtt_probe_return_path.ndjson", durationSeconds: 120 },
  C4: { name: "Congested cell", family: "legacy", downlinkMbpsBand: [4, 9], rttMsBand: [35, 90], lossPercentBand: [0.2, 2], dominantCause: "scheduler_and_queue (64 background UEs)", backgroundUeCount: 64, fikoreIniFile: "c4_congested_cell.ini", timelineFile: null, durationSeconds: 120 },
  C5: { name: "Cell edge / low SINR", family: "legacy", downlinkMbpsBand: [1.5, 5], rttMsBand: [50, 110], lossPercentBand: [2, 5], dominantCause: "radio_and_harq", backgroundUeCount: 0, fikoreIniFile: "c5_cell_edge_low_sinr.ini", timelineFile: "c5_rtt_probe_return_path.ndjson", durationSeconds: 120 },
  C6: { name: "Mobility / dropout", family: "legacy", downlinkMbpsBand: [3, 40], rttMsBand: [40, 120], lossPercentBand: [0, 3], dominantCause: "mobility (rural, three attenuation events)", backgroundUeCount: 0, fikoreIniFile: "c6_mobility_dropout.ini", timelineFile: "c6_mobility_dropouts.ndjson", durationSeconds: 180 },
  C7: { name: "Satellite-like", family: "legacy", downlinkMbpsBand: [12, 18], rttMsBand: [240, 360], lossPercentBand: [0, 1], dominantCause: "backhaul_delay (150 ms one way, 15 Mbps cap proxy)", backgroundUeCount: 0, fikoreIniFile: "c7_satellite_like.ini", timelineFile: "c7_rate_cap.ndjson", durationSeconds: 120 },
  C8a: { name: "Bursty congestion", family: "legacy", downlinkMbpsBand: [12, 28], rttMsBand: [20, 100], lossPercentBand: [0, 1.5], dominantCause: "periodic_congestion (20 background UEs in bursts)", backgroundUeCount: 20, fikoreIniFile: "c8a_bursty_congestion.ini", timelineFile: "c8a_background_bursts.ndjson", durationSeconds: 300 },
  C8b: { name: "Coverage transition", family: "legacy", downlinkMbpsBand: [3, 60], rttMsBand: [20, 120], lossPercentBand: [0, 3], dominantCause: "coverage_transition (test-only map)", backgroundUeCount: 0, fikoreIniFile: "c8b_coverage_transition.ini", timelineFile: "c8b_coverage_path.ndjson", durationSeconds: 180 },
};

export const LEGACY_CONDITION_IDS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8a", "C8b"] as const;

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
  const soloCap20 = dist <= 220 ? 58 : dist <= 450 ? 21 : 6.2;
  const soloCap = soloCap20 * bwFactor;
  const residualShare = values.bg_spatial === "homogeneous_ring"
    ? Math.max(0.06, 1 - 0.88 * Math.min(1.08, values.load_rho))
    : Math.max(0.18, 1 - 0.65 * Math.min(1.15, values.load_rho));
  const meanTp = Math.max(0.8, soloCap * residualShare);
  const spread = values.arrival_mode === "mmpp" || values.study_mobility === "vehicular_traverse" ? 0.55 : 0.25;
  const lowTp = Math.max(0.5, Math.round(meanTp * (1 - spread) * 10) / 10);
  const highTp = Math.max(lowTp + 0.5, Math.round(Math.min(soloCap, meanTp * (1 + spread)) * 10) / 10);
  const baseRtt = 2 * values.backhaul_delay_ms + 20;
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
