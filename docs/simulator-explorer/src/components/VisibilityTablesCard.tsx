import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { GlossaryTerm as T, InlineCode as C } from "@/components/GlossaryTerm";
import { cn } from "@/lib/utils";
import type { ComponentTopology } from "@/model/componentTopology";
import { signalingLevelNumber, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";
import { computePlayerVisibleFields, type FieldVisibility } from "@/model/playerVisibleFields";

function StateBadge({ tone, children }: { tone: "visible" | "muted" | "warning" | "cap"; children: string }) {
  const toneClasses = {
    visible: "bg-status-ok text-flow-csp-to-cap",
    muted: "bg-muted text-muted-foreground",
    warning: "bg-status-partial text-flow-oracle-or-log",
    cap: "bg-status-none text-flow-cap-to-csp",
  };
  return <Badge className={cn("rounded-full text-[11px] font-semibold", toneClasses[tone])}>{children}</Badge>;
}

const VISIBILITY_BADGE: Record<FieldVisibility, ["visible" | "muted" | "warning", string]> = {
  visible: ["visible", "visible"],
  null: ["warning", "no data"],
  filtered: ["muted", "filtered"],
};

export function VisibilityTablesCard({ settings, topology }: { settings: ExplorerSettings; topology: ComponentTopology }) {
  const level = signalingLevelNumber(settings.signalingLevel);
  const fields = computePlayerVisibleFields(settings);
  const capReportsSent = level >= 3 && settings.implementationState !== "master";
  return (
    <Card>
      <CardHeader>
        <CardTitle>What the player sees (UE 0)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead><T id="CspFields">CspFields</T></TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {fields.map((row) => {
              const [tone, label] = VISIBILITY_BADGE[row.visibility];
              return (
                <TableRow key={row.field}>
                  <TableCell><T id={row.field} asCode /></TableCell>
                  <TableCell className="text-xs whitespace-normal text-muted-foreground">{row.source}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {row.visibility === "visible" ? String(row.exampleValue) : row.visibility === "null" ? "null" : ""} <StateBadge tone={tone}>{label}</StateBadge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <p className="text-xs text-muted-foreground">
          Values are illustrative midpoints of the condition's calibration band, split among UEs. Backends must not invent missing values; they stay null.
          {usesFikoreBackend(settings) && " SINR, queue bytes and PDCP latency are logged as extensions only."}
        </p>

        <div>
          <h3 className="mb-1 text-base font-semibold">What the network sees</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead>At this level</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>Requests</TableCell>
                <TableCell className="whitespace-normal">
                  <C>UE 0, request v1.s0.q2.a0, 940000 bytes</C> <StateBadge tone="muted">opaque</StateBadge>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell><T id="CapReport" asCode /></TableCell>
                <TableCell className="whitespace-normal">
                  {capReportsSent ? (
                    <>
                      <C>is_stalled, playable_buffer_s, current_video_id, swipe_rate_per_s</C> <StateBadge tone="cap">readable</StateBadge>
                    </>
                  ) : settings.implementationState === "pr8" ? (
                    <StateBadge tone="muted">written for audit, not readable</StateBadge>
                  ) : (
                    <StateBadge tone="muted">not sent</StateBadge>
                  )}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell><T id="UeControl" asCode /></TableCell>
                <TableCell className="whitespace-normal">
                  {topology.activeEdges.controllerSetsUeControl ? (
                    <>
                      <C>priority, rmax_mbps</C> <StateBadge tone="cap">applied</StateBadge>
                    </>
                  ) : topology.activeEdges.controllerLogsProposal ? (
                    <StateBadge tone="warning">proposed, not applied</StateBadge>
                  ) : (
                    <StateBadge tone="muted">none</StateBadge>
                  )}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
