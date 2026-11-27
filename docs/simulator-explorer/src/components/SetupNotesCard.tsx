import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GlossaryTerm as T, InlineCode as C } from "@/components/GlossaryTerm";
import { isParametricCondition } from "@/data/parametricCells";
import { signalingLevelNumber, usesConstantRateBackend, usesFikoreBackend, type ExplorerSettings } from "@/model/explorerSettings";

export function SetupNotesCard({ settings }: { settings: ExplorerSettings }) {
  const fikore = usesFikoreBackend(settings);
  const constantRate = usesConstantRateBackend(settings);
  const level = signalingLevelNumber(settings.signalingLevel);
  const notes: ReactNode[] = [
    constantRate && (
      <>
        The <T id="ConstantRateBackend">constant_rate backend</T> gives every UE its own rate, as assumed by the analytical model of Wehner et al. It is not a TCP, HTTP or
        radio model and has no telemetry source, so only the plan rate can reach the player.
      </>
    ),
    settings.networkBackend === "mock" && "The mock backend is for tests. It has no delay and no telemetry source. Only the plan rate can reach the player.",
    fikore && isParametricCondition(settings.conditionId) && (
      <>
        Parametric conditions (<C>M01</C>–<C>M11</C> and <C>CUSTOM</C>) deterministically synthesize <C>fikore-effective.ini</C>, <C>fikore-timeline.ndjson</C>{" "}
        and application-paced TCP background flows at run start from <C>Global.seed</C> (<T id="parametric_cell" asCode>network.parametric_cell</T>).
      </>
    ),
    settings.contentId === "aomctc_per_title" && (
      <>
        The per-title catalogues come from real encodes of the AOM CTC a2_2k long clips, with one rung per VMAF v1.0.16 5H target (90 to 50). The representation sizes
        are measured; their split into segments is synthetic. Most clips are landscape and keep their source frame rate (25–60 fps).
      </>
    ),
    settings.contentId === "portrait_hd_90s" && (
      <>
        <C>sfv-portrait-hd-90s.json</C> is a provisional synthetic 18×8 s Full HD portrait ladder used to sustain multi-swipe runs until the pilot's final SFV
        catalogue lands.
      </>
    ),
    fikore && !settings.acksOverFikoreUplink && "Without ACKs over the uplink, ACKs return after 1 ms and the measured RTT is lower than the condition's target.",
    fikore && settings.tcpConnectionMode === "fresh" && "Fresh mode opens a new TCP connection per object, with slow start each time. It is the comparison baseline.",
    fikore &&
      settings.tcpConnectionMode === "multiplexed" &&
      "Multiplexed mode shares a single RFC 9218 prioritized TCP connection per UE (HTTP/2 / HTTP/3 style), avoiding per-request connection setup and head-of-line pool contention.",
    level >= 1 && level <= 2 && "The B1 and B2 rules do not use CSP fields yet. A level only changes results once a policy reads them.",
    level === 3 && (
      <>
        L3 needs a controller design: inputs, mapping to priority and rate caps, interval, damping and persistence. FikoRE only honours priority with the <T id="PFScheduler">PF scheduler</T> (metric_type 6).
      </>
    ),
    level === 4 && "With several adaptive UEs, future capacity depends on their own demand. The run must state whether L4 is an exogenous bound or a demand-coupled trace.",
    <>
      P.1203 scoring uses the <C>frameRateFps</C> of each representation in the content file (30 fps in the fixture, 25–60 fps in the per-title catalogues).{" "}
      <T id="fallback_frame_rate_fps" asCode>scoring.fallback_frame_rate_fps</T> applies only to representations without one.
    </>,
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
