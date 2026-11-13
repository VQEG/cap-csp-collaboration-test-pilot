import { bandMidpoint, NETWORK_CONDITIONS } from "@/data/networkConditions";
import type { GlossaryTermId } from "@/data/glossary";
import { backendHasCspTelemetrySource, signalingLevelNumber, type ExplorerSettings } from "@/model/explorerSettings";

// CspFields rows for UE 0: where each value comes from and whether the player
// can see it. Values are midpoints of the calibration bands, not run data.

export type FieldVisibility = "visible" | "filtered" | "null";

export interface PlayerVisibleFieldRow {
  field: GlossaryTermId;
  source: string;
  minimumLevel: number;
  exampleValue: number | null;
  visibility: FieldVisibility;
}

export function computePlayerVisibleFields(settings: ExplorerSettings): PlayerVisibleFieldRow[] {
  const level = signalingLevelNumber(settings.signalingLevel);
  const hasTelemetrySource = backendHasCspTelemetrySource(settings);
  const condition = NETWORK_CONDITIONS[settings.conditionId];
  const planValue = settings.planDownlinkMbps === "" ? null : Number(settings.planDownlinkMbps);
  const rttMidpoint = bandMidpoint(condition.rttMsBand);
  const throughputShare = Math.round((bandMidpoint(condition.downlinkMbpsBand) / Math.max(1, settings.videoUeCount / 2)) * 10) / 10;

  const rows: Omit<PlayerVisibleFieldRow, "visibility">[] = [
    { field: "plan_downlink_mbps", source: "config: plan_downlink_mbps_by_ue", minimumLevel: 1, exampleValue: planValue },
    { field: "achieved_throughput_mbps", source: "telemetry sample: throughput_mbps (1 s mean)", minimumLevel: 2, exampleValue: hasTelemetrySource ? throughputShare : null },
    {
      field: "rtt_ms",
      source: "telemetry sample: rtt_ms (TCP ACK path)",
      minimumLevel: 2,
      exampleValue: hasTelemetrySource ? (settings.acksOverFikoreUplink ? rttMidpoint : Math.max(5, Math.round(rttMidpoint / 2))) : null,
    },
    {
      field: "loss_rate",
      source: "telemetry sample: drop_rate",
      minimumLevel: 2,
      exampleValue: hasTelemetrySource ? Math.round((bandMidpoint(condition.lossPercentBand) / 100) * 10000) / 10000 : null,
    },
    { field: "congestion_rate", source: "telemetry sample: ce_rate (ECN; L4S is off)", minimumLevel: 2, exampleValue: null },
  ];

  return rows.map((row) => {
    let visibility: FieldVisibility;
    if (level < row.minimumLevel) visibility = "filtered";
    else visibility = row.exampleValue === null ? "null" : "visible";
    return { ...row, visibility };
  });
}
