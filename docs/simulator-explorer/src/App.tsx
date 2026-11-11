import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ArchitectureDiagram } from "@/components/diagram/ArchitectureDiagram";
import { DiagramLegend } from "@/components/diagram/DiagramLegend";
import { ExperimentConfigCard } from "@/components/ExperimentConfigCard";
import { ImplementationStatusBanner } from "@/components/ImplementationStatusBanner";
import { SettingsPanel } from "@/components/SettingsPanel";
import { SetupNotesCard } from "@/components/SetupNotesCard";
import { StepWalkthroughStrip } from "@/components/StepWalkthroughStrip";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { VisibilityTablesCard } from "@/components/VisibilityTablesCard";
import { useHashBackedSettings } from "@/hooks/useHashBackedSettings";
import { useStepPlayback } from "@/hooks/useStepPlayback";
import { computeComponentTopology } from "@/model/componentTopology";
import { describeImplementationStatus } from "@/model/implementationStatus";
import { buildNetworkStepWalkthrough } from "@/model/networkStepWalkthrough";

export default function App() {
  const { settings, updateSetting } = useHashBackedSettings();
  const topology = useMemo(() => computeComponentTopology(settings), [settings]);
  const steps = useMemo(() => buildNetworkStepWalkthrough(settings, topology), [settings, topology]);
  const playback = useStepPlayback(steps);
  const selectedStep = steps[playback.selectedStepIndex];

  return (
    <TooltipProvider>
      <main className="space-y-4 px-[clamp(16px,2.5vw,40px)] pt-6 pb-16">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">CAP–CSP simulator explorer</h1>
            <p className="mt-1 max-w-[900px] text-sm text-muted-foreground">
              Pick a signaling level, a backend and a network condition to see which components take part in a run, what flows between them in each 10 ms step,
              and what the player can see. Switch between the design, the code on master and PR #8 to compare. Hover any dotted-underlined term for details.
            </p>
          </div>
          <ThemeToggleButton />
        </header>

        <SettingsPanel settings={settings} updateSetting={updateSetting} />
        <ImplementationStatusBanner status={describeImplementationStatus(settings)} />

        <Card className="gap-3 px-4">
          <div className="overflow-x-auto">
            <ArchitectureDiagram
              settings={settings}
              topology={topology}
              highlightedEdges={selectedStep?.highlightedEdges ?? []}
              highlightedNodes={selectedStep?.highlightedNodes ?? []}
            />
          </div>
          <DiagramLegend />
        </Card>

        <StepWalkthroughStrip steps={steps} {...playback} />

        <div className="grid gap-4 lg:grid-cols-2">
          <VisibilityTablesCard settings={settings} topology={topology} />
          <ExperimentConfigCard settings={settings} />
        </div>
        <SetupNotesCard settings={settings} />
      </main>
    </TooltipProvider>
  );
}
