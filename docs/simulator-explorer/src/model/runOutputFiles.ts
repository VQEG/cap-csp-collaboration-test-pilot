import type { GlossaryTermId } from "@/data/glossary";
import { usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";
import type { ComponentTopology } from "@/model/componentTopology";

// Files written to the output directory of a run.

export interface RunOutputFile {
  fileName: GlossaryTermId;
  addedByPr8: boolean;
}

export function listRunOutputFiles(settings: ExplorerSettings, topology: ComponentTopology): RunOutputFile[] {
  const files: RunOutputFile[] = (
    ["run-manifest.json", "sessions/", "network-steps.jsonl", "telemetry.jsonl", "kpis.csv", "report.md", "player.log"] as const
  ).map((fileName) => ({ fileName, addedByPr8: false }));
  if (usesFikoreBackend(settings)) {
    files.push({ fileName: "fikore-effective.ini", addedByPr8: false }, { fileName: "fikore.log", addedByPr8: false });
  }
  if (settings.implementationState === "pr8") files.push({ fileName: "shared-state.jsonl", addedByPr8: true });
  if (topology.activeEdges.controllerLogsProposal) files.push({ fileName: "csp-control.jsonl", addedByPr8: true });
  return files;
}
