import { useEffect, useMemo, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineCode as C } from "@/components/GlossaryTerm";
import type { ExplorerSettings } from "@/model/explorerSettings";
import { buildExperimentConfig, gridCellCount } from "@/model/experimentConfig";

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Clipboard API blocked, for example in a sandboxed frame: fall back to a selection
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    return copied;
  }
}

/** The complete experiment or grid JSON for the chosen settings, ready to copy. */
export function ExperimentConfigCard({ settings }: { settings: ExplorerSettings }) {
  const grid = settings.configOutputKind === "grid";
  const json = useMemo(() => JSON.stringify(buildExperimentConfig(settings), null, 2), [settings]);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  useEffect(() => setCopyState("idle"), [json]);
  const filePath = grid ? "configs/grids/my-grid.json" : "configs/experiments/my-run.json";

  return (
    <Card className="gap-3 xl:h-0 xl:min-h-full">
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle>{grid ? "Grid config" : "Experiment config"}</CardTitle>
          <CardDescription>{grid ? `${gridCellCount(settings)} cells. The base experiment is inline, so the file runs as it is.` : "The complete file for this run."}</CardDescription>
        </div>
        <Button
          variant={copyState === "copied" ? "secondary" : "outline"}
          size="sm"
          onClick={async () => setCopyState((await copyText(json)) ? "copied" : "failed")}
          aria-live="polite"
        >
          {copyState === "copied" ? <Check /> : <Copy />}
          {copyState === "copied" ? "Copied" : copyState === "failed" ? "Copy failed" : "Copy JSON"}
        </Button>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col gap-2">
        <ScrollArea type="always" className="rounded-lg bg-muted xl:min-h-0 xl:flex-1 [&>[data-slot=scroll-area-viewport]]:max-h-[640px] xl:[&>[data-slot=scroll-area-viewport]]:absolute xl:[&>[data-slot=scroll-area-viewport]]:inset-0 xl:[&>[data-slot=scroll-area-viewport]]:max-h-none">
          <pre className="p-3 font-mono text-xs leading-relaxed">{json}</pre>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
        <p className="text-xs text-muted-foreground">
          Save it as <C>{filePath}</C> and run <C>{grid ? `uv run capcsp grid ${filePath}` : `uv run capcsp run ${filePath}`}</C>. Results go to{" "}
          <C>{grid ? "output/grids/explorer" : "output/runs/<run_id>"}</C>.
        </p>
      </CardContent>
    </Card>
  );
}
