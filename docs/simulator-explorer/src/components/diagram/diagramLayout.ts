import type { GlossaryTermId } from "@/data/glossary";
import type { DiagramEdgeId, DiagramNodeId } from "@/model/componentTopology";

// Geometry of the architecture diagram, in SVG user units of a
// DIAGRAM_WIDTH × DIAGRAM_HEIGHT viewBox. Box contents are in
// ArchitectureDiagram.tsx. To move a box, change its rectangle here and the
// end points of the arrows that touch it.

export const DIAGRAM_WIDTH = 1480;
export const DIAGRAM_HEIGHT = 900;

export interface DiagramRectangle {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DiagramGroupFrame extends DiagramRectangle {
  label: string;
}

export const GROUP_FRAMES = {
  playerProcess: { x: 16, y: 16, width: 448, height: 600, label: "CAP · Player process (Node.js)" },
  harnessProcess: { x: 556, y: 16, width: 368, height: 600, label: "Harness · Python process" },
  networkBackend: { x: 1016, y: 16, width: 448, height: 600, label: "CSP · Network backend" },
  collaborationLayer: { x: 16, y: 650, width: 1448, height: 236, label: "Collaboration layer (Python process)" },
} satisfies Record<string, DiagramGroupFrame>;

export const NODE_BOXES: Record<DiagramNodeId, DiagramRectangle> = {
  networkStepHarness: { x: 40, y: 56, width: 400, height: 158 },
  sfvSimulationController: { x: 40, y: 262, width: 400, height: 126 },
  playerRule: { x: 40, y: 436, width: 400, height: 140 },
  runner: { x: 580, y: 56, width: 320, height: 198 },
  runOutputs: { x: 740, y: 330, width: 160, height: 266 },
  transportBackend: { x: 1040, y: 56, width: 400, height: 158 },
  fikoreLink: { x: 1040, y: 262, width: 400, height: 126 },
  fikore: { x: 1040, y: 436, width: 400, height: 150 },
  mockBackend: { x: 1040, y: 56, width: 400, height: 158 },
  sharedStateTable: { x: 560, y: 700, width: 380, height: 166 },
  cspController: { x: 1060, y: 700, width: 380, height: 150 },
  capacityOracle: { x: 40, y: 700, width: 380, height: 120 },
};

/** Arrow colors; each maps to a --flow-* CSS variable. */
export type EdgeColorKey = "main" | "cspToCap" | "capToCsp" | "oracleOrLog" | "internal";

export const EDGE_COLOR_VARIABLES: Record<EdgeColorKey | "inactive", string> = {
  main: "var(--flow-main)",
  cspToCap: "var(--flow-csp-to-cap)",
  capToCsp: "var(--flow-cap-to-csp)",
  oracleOrLog: "var(--flow-oracle-or-log)",
  internal: "var(--flow-internal)",
  inactive: "var(--flow-inactive)",
};

export interface DiagramEdgeGeometry {
  path: string;
  color: EdgeColorKey;
  dashed?: boolean;
  label?: string;
  labelX?: number;
  labelY?: number;
  labelAnchor?: "start" | "middle" | "end";
  /** Rotate the label by -90° to run along a vertical arrow. */
  labelVertical?: boolean;
  glossaryTerm?: GlossaryTermId;
}

export const EDGE_GEOMETRY: Record<DiagramEdgeId, DiagramEdgeGeometry> = {
  // Player ↔ runner
  networkStepToPlayer: { path: "M578,100 L442,100", color: "main", label: "network_step", labelX: 510, labelY: 93, glossaryTerm: "network_step" },
  playerActions: { path: "M442,148 L578,148", color: "main", label: "player_actions", labelX: 510, labelY: 141, glossaryTerm: "player_actions" },
  capReportsIpc: { path: "M442,196 L578,196", color: "capToCsp", label: "cap_reports", labelX: 510, labelY: 189, glossaryTerm: "cap_reports" },
  // Runner ↔ backend
  advance: { path: "M902,100 L1038,100", color: "main", label: "advance()", labelX: 970, labelY: 93, glossaryTerm: "advance" },
  networkStepToRunner: { path: "M1038,148 L902,148", color: "main", label: "NetworkStep", labelX: 970, labelY: 141, glossaryTerm: "NetworkStep" },
  submitOrCancel: { path: "M902,196 L1038,196", color: "main", label: "submit / cancel", labelX: 970, labelY: 189, glossaryTerm: "submit_request" },
  // Inside the backend
  transportToLink: { path: "M1240,214 L1240,260", color: "internal", label: "10 TTIs per step", labelX: 1250, labelY: 241, labelAnchor: "start", glossaryTerm: "TTI" },
  linkToFikore: { path: "M1240,388 L1240,434", color: "internal", label: "inject · grant · ACKs", labelX: 1250, labelY: 415, labelAnchor: "start", glossaryTerm: "FikoreLink" },
  // Runner → outputs
  runOutputs: { path: "M820,254 L820,328", color: "internal" },
  // Runner ↔ shared state table
  readCspFields: { path: "M610,698 L610,256", color: "cspToCap", label: "read_csp_fields", labelX: 603, labelY: 477, labelVertical: true, glossaryTerm: "read_csp_fields" },
  writeCspFields: { path: "M660,256 L660,698", color: "cspToCap", label: "write_csp_fields", labelX: 653, labelY: 477, labelVertical: true, glossaryTerm: "write_csp_fields" },
  writeCapReport: { path: "M710,256 L710,698", color: "capToCsp", label: "write_cap_report", labelX: 703, labelY: 477, labelVertical: true, glossaryTerm: "write_cap_report" },
  // Controller
  controllerReadsCapReport: { path: "M942,760 L1058,760", color: "capToCsp", label: "read_cap_report", labelX: 1000, labelY: 753, glossaryTerm: "read_cap_report" },
  controllerSetsUeControl: { path: "M1400,698 L1400,588", color: "capToCsp", label: "set_ue_control", labelX: 1393, labelY: 643, labelVertical: true, glossaryTerm: "set_ue_control" },
  controllerLogsProposal: {
    path: "M1090,698 C1060,640 860,670 830,598",
    color: "oracleOrLog",
    dashed: true,
    label: "proposal → csp-control.jsonl",
    labelX: 1000,
    labelY: 632,
    glossaryTerm: "csp-control.jsonl",
  },
  // Oracle
  capacityTrace: { path: "M380,698 L380,578", color: "oracleOrLog", label: "capacity trace", labelX: 373, labelY: 638, labelVertical: true, glossaryTerm: "CapacityOracle" },
};

/** Plain connectors between the boxes inside the player process. */
export const PLAIN_CONNECTORS = ["M240,214 L240,262", "M240,388 L240,436"];
