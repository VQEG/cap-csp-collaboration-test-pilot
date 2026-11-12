import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineCode as C } from "@/components/GlossaryTerm";
import type { ExplorerSettings } from "@/model/explorerSettings";
import { buildExperimentConfig } from "@/model/experimentConfig";

export function ExperimentConfigCard({ settings }: { settings: ExplorerSettings }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Experiment config</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <pre className="max-h-[460px] overflow-auto rounded-lg bg-muted p-3 font-mono text-xs leading-relaxed">{JSON.stringify(buildExperimentConfig(settings), null, 2)}</pre>
        <p className="text-xs text-muted-foreground">
          Shape of a file under <C>configs/experiments/</C>. Run with <C>{"uv run capcsp run <config> output/<dir>"}</C>.
        </p>
      </CardContent>
    </Card>
  );
}
