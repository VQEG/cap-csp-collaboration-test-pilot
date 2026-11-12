import type { GlossaryTermId } from "@/data/glossary";
import { usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";
import type { ComponentTopology } from "@/model/componentTopology";

// Files written to the output directory of a run.

export interface RunOutputFile {
  fileName: GlossaryTermId;
  collaborationLog: boolean;
}

export function listRunOutputFiles(settings: ExplorerSettings, topology: ComponentTopology): RunOutputFile[] {
  const files: RunOutputFile[] = (
    ["run-manifest.json", "sessions/", "network-steps.jsonl", "telemetry.jsonl", "kpis.csv", "report.md", "player.log"] as const
  ).map((fileName) => ({ fileName, collaborationLog: false }));
  if (usesFikoreBackend(settings)) {
    files.push({ fileName: "fikore-effective.ini", collaborationLog: false }, { fileName: "fikore.log", collaborationLog: false });
  }
  files.push({ fileName: "shared-state.jsonl", collaborationLog: true });
  if (topology.activeEdges.controllerLogsProposal) files.push({ fileName: "csp-control.jsonl", collaborationLog: true });
  return files;
}
