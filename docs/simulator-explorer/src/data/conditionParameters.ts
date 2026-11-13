// FikoRE parameters of the conditions that the explorer lets you change.
// Base values are copied from configs/fikore/c*.ini. A changed value becomes
// an override in the experiment's `network` block: `fikore_section_overrides`
// for INI sections, `fikore_ue_overrides` for a UE group. `duration_s` is a
// top-level experiment key.

export type ConditionParameterTarget =
  | { kind: "experiment"; key: "duration_s" }
  | { kind: "section"; section: string; key: string }
  | { kind: "ueGroup"; group: "studyVqeg" | "backgroundVqeg"; key: string };

export interface ConditionParameter {
  id: string;
  label: string;
  unit: string;
  /** INI value = displayed value × scale. */
  scale: number;
  step: number;
  integer?: boolean;
  target: ConditionParameterTarget;
  hint: string;
}

export const CONDITION_PARAMETERS: ConditionParameter[] = [
  { id: "duration", label: "Run length", unit: "s", scale: 1, step: 10, integer: true, target: { kind: "experiment", key: "duration_s" }, hint: "Simulated time of the run" },
  { id: "studyPositionX", label: "Study UE position x", unit: "m", scale: 1, step: 10, target: { kind: "ueGroup", group: "studyVqeg", key: "pos_x" }, hint: "Distance from the gNB along x; sets SINR and MCS" },
  { id: "studySpeed", label: "Study UE speed", unit: "km/h", scale: 1, step: 5, target: { kind: "ueGroup", group: "studyVqeg", key: "speed" }, hint: "Used with mobility (C6)" },
  { id: "studyDelayBudget", label: "Study UE packet delay budget", unit: "s", scale: 1, step: 0.01, target: { kind: "ueGroup", group: "studyVqeg", key: "pkt_delay_budget" }, hint: "PDCP drops packets that wait longer" },
  { id: "backgroundCount", label: "Background UEs", unit: "UEs", scale: 1, step: 1, integer: true, target: { kind: "ueGroup", group: "backgroundVqeg", key: "n_ues" }, hint: "Competing UEs in the cell" },
  { id: "backgroundDownlink", label: "Background load per UE", unit: "Mbps", scale: 1, step: 0.5, target: { kind: "ueGroup", group: "backgroundVqeg", key: "dl_target" }, hint: "Offered downlink of each background UE" },
  { id: "backgroundPriority", label: "Background priority", unit: "", scale: 1, step: 0.5, target: { kind: "ueGroup", group: "backgroundVqeg", key: "priority" }, hint: "PF scheduler weight" },
  { id: "backgroundDelayBudget", label: "Background packet delay budget", unit: "s", scale: 1, step: 0.01, target: { kind: "ueGroup", group: "backgroundVqeg", key: "pkt_delay_budget" }, hint: "PDCP drops packets that wait longer" },
  { id: "bandwidth", label: "Cell bandwidth", unit: "MHz", scale: 1e6, step: 10, target: { kind: "section", section: "eNBConfig", key: "bandwidth" }, hint: "Shared by all UEs of the cell" },
  { id: "frequency", label: "Carrier frequency", unit: "GHz", scale: 1e9, step: 0.1, target: { kind: "section", section: "eNBConfig", key: "frequency" }, hint: "Must match the propagation map" },
  { id: "txPower", label: "gNB transmit power", unit: "dBm", scale: 1, step: 1, target: { kind: "section", section: "eNBConfig", key: "tx_power" }, hint: "" },
  { id: "backhaulDelay", label: "Backhaul delay", unit: "ms", scale: 1e-3, step: 1, target: { kind: "section", section: "PDCP_RLC", key: "backhaul_d" }, hint: "One way, adds to the RTT" },
  { id: "backhaulJitter", label: "Backhaul delay variation", unit: "ms", scale: 1e-3, step: 1, target: { kind: "section", section: "PDCP_RLC", key: "backhaul_d_var" }, hint: "" },
  { id: "interferenceUes", label: "Interfering UEs", unit: "UEs", scale: 1, step: 1, integer: true, target: { kind: "section", section: "PHYLayer", key: "interference_ues" }, hint: "Synthetic interference" },
];

/** Displayed base value of every parameter per condition; background parameters only where the INI has a background group. */
export const CONDITION_PARAMETER_BASE_VALUES: Record<string, Record<string, number>> = {
  C1: { duration: 120, studyPositionX: 151.26, studySpeed: 0, studyDelayBudget: 0.5, bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 10, backhaulJitter: 1, interferenceUes: 2 },
  C2: { duration: 120, studyPositionX: 151.26, studySpeed: 0, studyDelayBudget: 0.5, bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 12, backhaulJitter: 1, interferenceUes: 2 },
  C3: { duration: 120, studyPositionX: 775.52, studySpeed: 0, studyDelayBudget: 0.5, bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 20, backhaulJitter: 1, interferenceUes: 2 },
  C4: {
    duration: 120, studyPositionX: 151.26, studySpeed: 0, studyDelayBudget: 0.03,
    backgroundCount: 64, backgroundDownlink: 100, backgroundPriority: 1, backgroundDelayBudget: 0.03,
    bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 22, backhaulJitter: 12, interferenceUes: 2,
  },
  C5: { duration: 120, studyPositionX: 2543.49, studySpeed: 0, studyDelayBudget: 0.1, bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 1, backhaulJitter: 26, interferenceUes: 2 },
  C6: { duration: 180, studyPositionX: 400, studySpeed: 60, studyDelayBudget: 5, bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 25, backhaulJitter: 20, interferenceUes: 5 },
  C7: { duration: 120, studyPositionX: 151.26, studySpeed: 0, studyDelayBudget: 2, bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 150, backhaulJitter: 3, interferenceUes: 2 },
  C8a: {
    duration: 300, studyPositionX: 151.26, studySpeed: 0, studyDelayBudget: 2,
    backgroundCount: 20, backgroundDownlink: 0.5, backgroundPriority: 4, backgroundDelayBudget: 2,
    bandwidth: 100, frequency: 3.5, txPower: 46, backhaulDelay: 15, backhaulJitter: 20, interferenceUes: 2,
  },
  C8b: { duration: 180, studyPositionX: -25, studySpeed: 0, studyDelayBudget: 0.5, bandwidth: 20, frequency: 2.38, txPower: 43, backhaulDelay: 15, backhaulJitter: 20, interferenceUes: 2 },
};

/** The parameters that exist in a condition, in display order. */
export function conditionParametersOf(conditionId: string): ConditionParameter[] {
  const baseValues = CONDITION_PARAMETER_BASE_VALUES[conditionId] ?? {};
  return CONDITION_PARAMETERS.filter((parameter) => parameter.id in baseValues);
}

/** The value in INI units, rounded so that scaling does not add float noise. */
export function iniValue(parameter: ConditionParameter, displayedValue: number): number {
  return Number((displayedValue * parameter.scale).toPrecision(12));
}
