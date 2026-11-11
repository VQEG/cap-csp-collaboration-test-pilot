// Calibrated FikoRE conditions, from configs/fikore/README.md.

export interface NetworkCondition {
  name: string;
  /** Calibration band for downlink throughput, Mbps. */
  downlinkMbpsBand: [number, number];
  /** Calibration band for RTT, ms. */
  rttMsBand: [number, number];
  /** Calibration band for loss, percent. */
  lossPercentBand: [number, number];
  dominantCause: string;
  backgroundUeCount: number;
  fikoreIniFile: string;
  timelineFile: string | null;
  durationSeconds: number;
  /** Plan rate preset when the condition is selected. */
  defaultPlanDownlinkMbps?: number;
}

export const NETWORK_CONDITIONS: Record<string, NetworkCondition> = {
  C1: { name: "Healthy 5G", downlinkMbpsBand: [48, 80], rttMsBand: [15, 40], lossPercentBand: [0, 0.1], dominantCause: "none", backgroundUeCount: 0, fikoreIniFile: "c1_healthy_5g.ini", timelineFile: null, durationSeconds: 120 },
  C2: { name: "Plan-capped", downlinkMbpsBand: [20, 30], rttMsBand: [20, 45], lossPercentBand: [0, 0.1], dominantCause: "rate_cap (25 Mbps per-UE grant cap)", backgroundUeCount: 0, fikoreIniFile: "c2_plan_capped.ini", timelineFile: "c2_plan_cap.ndjson", durationSeconds: 120, defaultPlanDownlinkMbps: 25 },
  C3: { name: "Borderline cell", downlinkMbpsBand: [8, 16], rttMsBand: [25, 60], lossPercentBand: [0, 0.5], dominantCause: "radio_capacity (MCS 0 region)", backgroundUeCount: 0, fikoreIniFile: "c3_borderline_cell.ini", timelineFile: "c3_rtt_probe_return_path.ndjson", durationSeconds: 120 },
  C4: { name: "Congested cell", downlinkMbpsBand: [4, 9], rttMsBand: [35, 90], lossPercentBand: [0.2, 2], dominantCause: "scheduler_and_queue (64 background UEs)", backgroundUeCount: 64, fikoreIniFile: "c4_congested_cell.ini", timelineFile: null, durationSeconds: 120 },
  C5: { name: "Cell edge / low SINR", downlinkMbpsBand: [1.5, 5], rttMsBand: [50, 110], lossPercentBand: [2, 5], dominantCause: "radio_and_harq", backgroundUeCount: 0, fikoreIniFile: "c5_cell_edge_low_sinr.ini", timelineFile: "c5_rtt_probe_return_path.ndjson", durationSeconds: 120 },
  C6: { name: "Mobility / dropout", downlinkMbpsBand: [3, 40], rttMsBand: [40, 120], lossPercentBand: [0, 3], dominantCause: "mobility (rural, three attenuation events)", backgroundUeCount: 0, fikoreIniFile: "c6_mobility_dropout.ini", timelineFile: "c6_mobility_dropouts.ndjson", durationSeconds: 180 },
  C7: { name: "Satellite-like", downlinkMbpsBand: [12, 18], rttMsBand: [240, 360], lossPercentBand: [0, 1], dominantCause: "backhaul_delay (150 ms one way, 15 Mbps cap proxy)", backgroundUeCount: 0, fikoreIniFile: "c7_satellite_like.ini", timelineFile: "c7_rate_cap.ndjson", durationSeconds: 120 },
  C8a: { name: "Bursty congestion", downlinkMbpsBand: [12, 28], rttMsBand: [20, 100], lossPercentBand: [0, 1.5], dominantCause: "periodic_congestion (20 background UEs in bursts)", backgroundUeCount: 20, fikoreIniFile: "c8a_bursty_congestion.ini", timelineFile: "c8a_background_bursts.ndjson", durationSeconds: 300 },
  C8b: { name: "Coverage transition", downlinkMbpsBand: [3, 60], rttMsBand: [20, 120], lossPercentBand: [0, 3], dominantCause: "coverage_transition (test-only map)", backgroundUeCount: 0, fikoreIniFile: "c8b_coverage_transition.ini", timelineFile: "c8b_coverage_path.ndjson", durationSeconds: 180 },
};

export function bandMidpoint([low, high]: [number, number]): number {
  return Math.round(((low + high) / 2) * 10) / 10;
}
