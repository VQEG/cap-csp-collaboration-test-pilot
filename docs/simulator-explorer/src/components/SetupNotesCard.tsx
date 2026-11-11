import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GlossaryTerm as T } from "@/components/GlossaryTerm";
import { signalingLevelNumber, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

export function SetupNotesCard({ settings }: { settings: ExplorerSettings }) {
  const fikore = usesFikoreBackend(settings);
  const level = signalingLevelNumber(settings.signalingLevel);
  const notes: ReactNode[] = [
    !fikore && "The mock backend is for tests. It has no delay and no telemetry, so only the plan rate can reach the player.",
    fikore && settings.conditionId === "C2" && "C2 applies a 25 Mbps grant cap as the per-UE plan. At L1 the plan rate tells the player this limit in advance.",
    fikore && settings.conditionId === "C7" && "C7's 15 Mbps cap is a proxy for a backhaul bottleneck, not a plan rate. It should be replaced once FikoRE has a backhaul shaper.",
    fikore && !settings.acksOverFikoreUplink && "Without ACKs over the uplink, ACKs return after 1 ms and the measured RTT is lower than the condition's target.",
    settings.tcpConnectionMode === "fresh" && "Fresh mode opens a new TCP connection per object, with slow start each time. It is the comparison baseline.",
    settings.implementationState === "pr8" && "PR #8 needs the SFV hooks from SFV PR #2 (applyCspUpdate, buildCapReport).",
    level >= 1 && level <= 2 && settings.implementationState !== "master" && "The B1 and B2 rules do not use CSP fields yet. A level only changes results once a policy reads them.",
    level === 3 && (
      <>
        L3 needs a controller design: inputs, mapping to priority and rate caps, interval, damping and persistence. FikoRE only honours priority with the <T id="PFScheduler">PF scheduler</T> (metric_type 6).
      </>
    ),
    level === 4 && "With several adaptive UEs, future capacity depends on their own demand. The run must state whether L4 is an exogenous bound or a demand-coupled trace.",
    "Paired comparisons across levels use the same seeds, so only the information exchange differs.",
  ].filter(Boolean);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notes for this setup</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1.5 pl-5 text-sm">
          {notes.map((note, index) => (
            <li key={index}>{note}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
