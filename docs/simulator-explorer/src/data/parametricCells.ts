// Parametric 5G single-cell presets (M01–M11 and CUSTOM) matching
// capcsp/network/parametric_cell.py.

export type StudyPositionZone = "good" | "mid" | "edge" | "custom";
export type StudyMobilityKind = "static" | "pedestrian" | "vehicular_traverse";
export type BgSpatialKind = "none" | "homogeneous_ring" | "cell_disk";
export type ArrivalModeKind = "poisson" | "mmpp";

export const VALID_CELL_BANDWIDTHS_MHZ = [10, 20, 40, 60, 80, 100] as const;
export type CellBandwidthMhz = (typeof VALID_CELL_BANDWIDTHS_MHZ)[number];

export const STUDY_ZONE_DISTANCES_M: Record<Exclude<StudyPositionZone, "custom">, number> = {
  good: 151.26,
  mid: 350.0,
  edge: 650.0,
};

export interface ParametricCellValues {
  duration_s: number;
  bandwidth_mhz: CellBandwidthMhz;
  study_position: StudyPositionZone;
  study_distance_m: number;
  study_mobility: StudyMobilityKind;
  study_speed_kmh: number;
  traverse_min_distance_m: number;
  traverse_max_distance_m: number;
  load_rho: number;
  bg_spatial: BgSpatialKind;
  bg_max_distance_m: number;
  bg_bitrate_mbps: number;
  arrival_mode: ArrivalModeKind;
  mean_hold_s: number;
  burst_amplitude: number;
  burst_regime_s: number;
  backhaul_delay_ms: number;
  backhaul_jitter_ms: number;
}

export const CORE6_CONDITION_IDS = ["M01", "M04", "M05", "M07", "M09", "M10"] as const;
export const ALL_LAYERED_CONDITION_IDS = ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09", "M10", "M11"] as const;

const BASE_CUSTOM_CELL: ParametricCellValues = {
  duration_s: 65,
  bandwidth_mhz: 20,
  study_position: "good",
  study_distance_m: 151.26,
  study_mobility: "static",
  study_speed_kmh: 0,
  traverse_min_distance_m: 151.26,
  traverse_max_distance_m: 660,
  load_rho: 0.5,
  bg_spatial: "cell_disk",
  bg_max_distance_m: 630,
  bg_bitrate_mbps: 4.0,
  arrival_mode: "poisson",
  mean_hold_s: 8.0,
  burst_amplitude: 0.65,
  burst_regime_s: 14.0,
  backhaul_delay_ms: 10.0,
  backhaul_jitter_ms: 1.0,
};

export const PARAMETRIC_PRESET_DEFAULTS: Record<string, ParametricCellValues> = {
  M01: { ...BASE_CUSTOM_CELL, load_rho: 0.0, bg_spatial: "none" },
  M02: { ...BASE_CUSTOM_CELL, load_rho: 0.5, bg_spatial: "homogeneous_ring" },
  M03: { ...BASE_CUSTOM_CELL, load_rho: 0.75, bg_spatial: "homogeneous_ring" },
  M04: { ...BASE_CUSTOM_CELL, load_rho: 1.0, bg_spatial: "homogeneous_ring" },
  M05: { ...BASE_CUSTOM_CELL, load_rho: 1.0, bg_spatial: "homogeneous_ring", arrival_mode: "mmpp", mean_hold_s: 12.0, burst_amplitude: 0.65, burst_regime_s: 14.0 },
  M06: { ...BASE_CUSTOM_CELL, load_rho: 1.0, bg_spatial: "cell_disk" },
  M07: { ...BASE_CUSTOM_CELL, study_position: "mid", study_distance_m: 350.0, load_rho: 1.0, bg_spatial: "cell_disk" },
  M08: { ...BASE_CUSTOM_CELL, study_position: "edge", study_distance_m: 650.0, load_rho: 0.5, bg_spatial: "cell_disk" },
  M09: { ...BASE_CUSTOM_CELL, study_position: "edge", study_distance_m: 650.0, load_rho: 0.75, bg_spatial: "cell_disk" },
  M10: { ...BASE_CUSTOM_CELL, study_position: "good", study_distance_m: 151.26, study_mobility: "vehicular_traverse", study_speed_kmh: 73.26, load_rho: 0.5, bg_spatial: "cell_disk" },
  M11: { ...BASE_CUSTOM_CELL, study_position: "edge", study_distance_m: 650.0, study_mobility: "pedestrian", study_speed_kmh: 3.6, load_rho: 0.5, bg_spatial: "cell_disk" },
  CUSTOM: { ...BASE_CUSTOM_CELL },
};

export function isParametricCondition(conditionId: string): boolean {
  return conditionId in PARAMETRIC_PRESET_DEFAULTS;
}

export function isCore6Condition(conditionId: string): boolean {
  return (CORE6_CONDITION_IDS as readonly string[]).includes(conditionId);
}

export function resolveParametricCellValues(
  conditionId: string,
  overrides: Partial<ParametricCellValues> | undefined,
): ParametricCellValues {
  const base = PARAMETRIC_PRESET_DEFAULTS[conditionId] ?? BASE_CUSTOM_CELL;
  const merged: ParametricCellValues = { ...base, ...overrides };
  if (merged.load_rho > 0 && merged.bg_spatial === "none" && overrides?.bg_spatial === undefined) {
    merged.bg_spatial = "cell_disk";
  }
  return merged;
}

/** Estimate mean active background UEs (Lambda) from calibrated UMa n78 RB shares. */
export function estimateMeanActiveBgUes(values: ParametricCellValues): number {
  if (values.load_rho <= 0 || values.bg_spatial === "none") return 0;
  // Calibrated mean RB share at 4 Mbps on 20 MHz (including 0.985 HARQ framing factor)
  const baseShare4m20Mhz = values.bg_spatial === "homogeneous_ring" ? 0.06098 : 0.16467;
  const radiusFactor = values.bg_spatial === "cell_disk" ? Math.max(0.45, Math.min(1.1, values.bg_max_distance_m / 630)) : 1.0;
  const share = Math.min(
    1.0,
    baseShare4m20Mhz * radiusFactor * (values.bg_bitrate_mbps / 4.0) * (20.0 / values.bandwidth_mhz),
  );
  return Math.round((values.load_rho / Math.max(share, 1e-4)) * 10) / 10;
}

/** Parse comma-separated load_rho values for a parametric grid sweep. */
export function parseLoadSweepValues(raw: string): number[] | string {
  const parts = raw
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
  if (!parts.length) return "Enter at least one load_rho value (for example: 0, 0.25, 0.5, 0.75, 1.0)";
  const numbers: number[] = [];
  for (const part of parts) {
    const num = Number(part);
    if (!Number.isFinite(num) || num < 0 || num > 2.0) {
      return `Invalid load_rho "${part}": each value must be between 0.0 and 2.0`;
    }
    if (!numbers.some((existing) => Math.abs(existing - num) < 1e-6)) {
      numbers.push(Math.round(num * 1000) / 1000);
    }
  }
  return numbers;
}

export function loadSweepConditionSlug(rho: number): string {
  return `rho-${String(Math.round(rho * 100)).padStart(3, "0")}`;
}
