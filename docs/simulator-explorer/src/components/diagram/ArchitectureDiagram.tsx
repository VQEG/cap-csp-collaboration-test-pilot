import { GlossaryTerm as T, InlineCode as C } from "@/components/GlossaryTerm";
import { DiagramArrowMarkers, DiagramEdge } from "@/components/diagram/DiagramEdge";
import { DiagramNode, NodeDetailList } from "@/components/diagram/DiagramNode";
import {
  DIAGRAM_HEIGHT,
  DIAGRAM_WIDTH,
  EDGE_GEOMETRY,
  GROUP_FRAMES,
  NODE_BOXES,
  PLAIN_CONNECTORS,
  type DiagramGroupFrame,
} from "@/components/diagram/diagramLayout";
import { NETWORK_CONDITIONS } from "@/data/networkConditions";
import { cn } from "@/lib/utils";
import type { ComponentTopology, DiagramEdgeId, DiagramNodeId } from "@/model/componentTopology";
import {
  CONSTANT_RATE_CANCELLATION_TAIL_BYTES,
  CONSTANT_RATE_SYNTHETIC_DELAY_MS,
  constantRateDownlinkMbps,
  signalingLevelNumber,
  usesFikoreBackend,
  type ExplorerSettings,
} from "@/model/explorerSettings";
import { listRunOutputFiles } from "@/model/runOutputFiles";

interface ArchitectureDiagramProps {
  settings: ExplorerSettings;
  topology: ComponentTopology;
  highlightedEdges: DiagramEdgeId[];
  highlightedNodes: DiagramNodeId[];
}

function GroupFrame({ frame }: { frame: DiagramGroupFrame }) {
  return (
    <g>
      <rect x={frame.x} y={frame.y} width={frame.width} height={frame.height} rx={12} fill="none" className="stroke-border" strokeWidth={1.5} strokeDasharray="2 4" />
      <text x={frame.x + 14} y={frame.y + 24} className="fill-muted-foreground text-[11.5px] font-semibold tracking-wider uppercase">
        {frame.label}
      </text>
    </g>
  );
}

export function ArchitectureDiagram({ settings, topology, highlightedEdges, highlightedNodes }: ArchitectureDiagramProps) {
  const fikore = usesFikoreBackend(settings);
  const level = signalingLevelNumber(settings.signalingLevel);
  const state = settings.implementationState;
  const condition = NETWORK_CONDITIONS[settings.conditionId];
  const { activeEdges, activeNodes } = topology;
  const nodeProps = (id: DiagramNodeId) => ({ box: NODE_BOXES[id], active: activeNodes[id], highlighted: highlightedNodes.includes(id) });
  const isB1 = settings.playerBehavior === "simple";

  // The tall constant-rate box covers the FikoRE-internal arrows, so they are not drawn at all
  const hiddenEdges: DiagramEdgeId[] = settings.networkBackend === "constant_rate" ? ["transportToLink", "linkToFikore"] : [];

  const visibleCspFieldsText = level === 0 ? "nothing" : level === 1 ? "plan rate only" : "all CspFields";

  return (
    <svg
      viewBox={`0 0 ${DIAGRAM_WIDTH} ${DIAGRAM_HEIGHT}`}
      className="block h-auto w-full min-w-[960px]"
      role="img"
      aria-label="Component diagram for the selected configuration"
    >
      <DiagramArrowMarkers />
      <GroupFrame frame={GROUP_FRAMES.playerProcess} />
      <GroupFrame frame={GROUP_FRAMES.harnessProcess} />
      <GroupFrame frame={GROUP_FRAMES.networkBackend} />
      <GroupFrame frame={{ ...GROUP_FRAMES.collaborationLayer, label: `${GROUP_FRAMES.collaborationLayer.label} · ${settings.signalingLevel}` }} />

      {PLAIN_CONNECTORS.map((path) => (
        <path key={path} d={path} className="stroke-border" strokeWidth={2} />
      ))}

      {/* Player process */}
      <DiagramNode {...nodeProps("networkStepHarness")} repository="sfv" title={<T id="NetworkStepHarness" />} codePath="sfv-reference-implementation/src/cosim/">
        <NodeDetailList
          items={[
            <>One worker process for all UEs; applies each <T id="network_step" asCode /> and replies <T id="player_actions" asCode /></>,
            state === "master" ? (
              <>Passes changed <T id="collaboration" asCode /> fields to <T id="applyCspUpdate" asCode>applyCspUpdate</T> and answers <T id="cap_reports" asCode /></>
            ) : (
              <>Forwards CSP fields to the engine (L1+) and returns <T id="CapReport" asCode /> (L3+)</>
            ),
          ]}
        />
      </DiagramNode>

      <DiagramNode
        {...nodeProps("sfvSimulationController")}
        repository="sfv"
        title={<><T id="SFVSimulationController" /> × {settings.videoUeCount}</>}
        codePath="sfv-reference-implementation/src/simulation/"
      >
        <NodeDetailList
          items={[
            <>One per UE: playback clock, buffer, swipes, up to {isB1 ? 2 : 3} concurrent requests</>,
            state === "master" ? (
              <>Holds the latest <T id="CspFields" asCode />; <T id="drainCapReports" asCode>drainCapReports</T> returns a report when one is due</>
            ) : (
              <>Same engine and policy code also runs in dash.js</>
            ),
          ]}
        />
      </DiagramNode>

      <DiagramNode
        {...nodeProps("playerRule")}
        repository="sfv"
        title={isB1 ? <><span className="text-muted-foreground">B1 · </span><T id="SFVCurrentVideoRule">SFVCurrentVideoRule</T></> : <><span className="text-muted-foreground">B2 · </span><T id="SFVMultiVideoPrefetchRule">SFVMultiVideoPrefetchRule</T></>}
        codePath={`sfv-reference-implementation/src/rules/${isB1 ? "SFVCurrentVideoRule" : "SFVMultiVideoPrefetchRule"}.js`}
      >
        <NodeDetailList
          items={[
            <>Keeps 2 segments of the current video buffered</>,
            !isB1 && <>Preloads 2 segments of each next video, at most 4</>,
            state === "design" ? <>A policy for L1+ would read <T id="CspFields" asCode /> here (not written yet)</> : <>Reads no <T id="CspFields" asCode /> yet; decisions as at L0</>,
          ]}
        />
      </DiagramNode>

      {/* Harness process */}
      <DiagramNode {...nodeProps("runner")} repository="harness" title={<T id="Runner" />} codePath="capcsp/runner/run.py · player/bridge.py">
        <NodeDetailList
          items={[
            <>Owns the simulation clock and the step loop</>,
            <>JSON lines to Node over the process pipes</>,
            <>Runs the <T id="byteConservation">byte conservation check</T></>,
            state === "master" && <>Collaboration tick: telemetry sample → table → <T id="collaboration" asCode />; CAP reports → table; controller</>,
            <>Applies player actions before the next <C>advance()</C></>,
          ]}
        />
      </DiagramNode>

      <DiagramNode {...nodeProps("runOutputs")} repository="harness" title={<T id="RunOutputs" />}>
        <ul className="space-y-[3px] font-mono text-[10.5px]">
          {listRunOutputFiles(settings, topology).map((file) => (
            <li key={file.fileName}>
              <T id={file.fileName} className={cn("no-underline", file.collaborationLog && "font-semibold text-repo-harness")}>
                {file.fileName}
              </T>
            </li>
          ))}
        </ul>
      </DiagramNode>

      {/* Network backend */}
      {fikore ? (
        <>
          <DiagramNode {...nodeProps("transportBackend")} repository="fikore" title={<T id="TransportBackend" />} codePath="5g-network-emulator/transport/fikore_transport/backend.py">
            <NodeDetailList
              items={[
                <>TCP CUBIC per UE · <T id="tcpConnectionMode">{settings.tcpConnectionMode}</T> connections · 1 MiB window</>,
                <>Emits download events; its <T id="NetworkTelemetrySampler">telemetry sampler</T> gives one sample per UE every 1 s</>,
                <>Accepts <T id="set_ue_control" asCode>set_ue_control</T> with <T id="UeControl" asCode /></>,
                <>ACKs {settings.acksOverFikoreUplink ? "over the FikoRE uplink" : "after a fixed 1 ms"} (<T id="acksOverUplink" asCode>ack_over_link</T>)</>,
              ]}
            />
          </DiagramNode>
          <DiagramNode {...nodeProps("fikoreLink")} repository="fikore" title={<T id="FikoreLink" />} codePath="5g-network-emulator/transport/fikore_transport/fikore_link.py">
            <NodeDetailList items={[<>FikoRE control protocol over a Unix socket</>, <>Per <T id="TTI">TTI</T>: inject packets, read grants, deliveries and drops</>]} />
          </DiagramNode>
          <DiagramNode {...nodeProps("fikore")} repository="fikore" title={<><T id="FikoRE" /> · {settings.conditionId} {condition.name}</>} codePath={`configs/fikore/${condition.fikoreIniFile}`}>
            <NodeDetailList
              items={[
                <>{condition.downlinkMbpsBand[0]}–{condition.downlinkMbpsBand[1]} Mbps · RTT {condition.rttMsBand[0]}–{condition.rttMsBand[1]} ms · loss {condition.lossPercentBand[0]}–{condition.lossPercentBand[1]} %</>,
                <>Cause: {condition.dominantCause}</>,
                <><T id="PFScheduler">PF scheduler</T> · 1 ms TTI · {condition.backgroundUeCount} background UEs</>,
                condition.timelineFile && <>Timeline <C>{condition.timelineFile}</C></>,
              ]}
            />
          </DiagramNode>
        </>
      ) : settings.networkBackend === "constant_rate" ? (
        <DiagramNode {...nodeProps("constantRateBackend")} repository="harness" title={<T id="ConstantRateBackend" />} codePath="capcsp/network/constant_rate.py">
          <NodeDetailList
            items={[
              <>{constantRateDownlinkMbps(settings)} Mbps dedicated to each UE (<T id="downlink_rate_mbps" asCode>downlink_rate_mbps</T>); UEs never compete</>,
              <>The ready requests of a UE share its rate equally (processor sharing)</>,
              <>First byte {CONSTANT_RATE_SYNTHETIC_DELAY_MS} ms after submission (<T id="synthetic_delay_ms" asCode>synthetic_delay_ms</T>)</>,
              <>Exact byte accounting; events report whole bytes at the step time</>,
              <>A cancelled request gets at most {CONSTANT_RATE_CANCELLATION_TAIL_BYTES} more bytes (<T id="cancellation_tail_bytes" asCode>cancellation_tail_bytes</T>)</>,
              <>Accepts <T id="set_ue_control" asCode>set_ue_control</T>: <C>rmax_mbps</C> caps the UE rate from the next step; <C>priority</C> is recorded only</>,
              <>No TCP, no radio, no loss, no queue</>,
              <>No telemetry source</>,
              <>Condition: example-only</>,
            ]}
          />
        </DiagramNode>
      ) : (
        <DiagramNode {...nodeProps("mockBackend")} repository="harness" title={<T id="MockNetworkBackend" />} codePath="capcsp/network/mock.py">
          <NodeDetailList items={[<>80 kB per 10 ms step (64 Mbps), shared by all requests</>, <>No radio, no TCP, no delay</>, <>No telemetry source</>, <>Condition: example-only</>]} />
        </DiagramNode>
      )}

      {/* Collaboration layer */}
      <DiagramNode
        {...nodeProps("capacityOracle")}
        repository="harness"
        title={<T id="CapacityOracle" />}
      >
        <NodeDetailList items={[<>Future capacity trace for L4</>, <>Single UE: offline full-buffer FikoRE run, same seeds</>, <>Not implemented in any state</>]} />
      </DiagramNode>

      <DiagramNode
        {...nodeProps("sharedStateTable")}
        repository="harness"
        title={<T id="SharedStateTable">Shared state table</T>}
        codePath="capcsp/shared_state/table.py"
      >
        <NodeDetailList
          items={[
            <>Per UE: latest <T id="CspFields" asCode /> (CSP → CAP) and <T id="CapReport" asCode /> (CAP → CSP)</>,
            <>Writes are always stored; changes go to <T id="shared-state.jsonl" asCode /></>,
            <><T id="signalingLevelFilter">Filter on read</T> at {settings.signalingLevel}: player gets {visibleCspFieldsText}; controller {level >= 3 ? "can" : "cannot"} read CAP reports</>,
            state === "master" && fikore && level === 0 && <>Telemetry still written at L0, for audit</>,
          ]}
        />
      </DiagramNode>

      <DiagramNode
        {...nodeProps("cspController")}
        repository="harness"
        title={state === "master" ? <T id="DummyCSPController" /> : <T id="CSPController" />}
        codePath={state === "master" ? "capcsp/collaboration/csp_controller.py" : undefined}
      >
        <NodeDetailList
          items={
            state === "master"
              ? [
                  <>Enabled by <T id="csp_controller" asCode>csp_controller: "dummy"</T> at L3+</>,
                  <>Reads each UE's latest <T id="CapReport" asCode /> every step</>,
                  <>On a stall: proposes priority × 2 as a <T id="CspControlIntent" asCode /></>,
                  <>Logs to <T id="csp-control.jsonl" asCode />, <C>applied: false</C></>,
                ]
              : [
                  <>Reads <T id="CapReport" asCode />, sets <T id="UeControl" asCode /> (priority, rate cap)</>,
                  <>Applied at a stated TTI and acknowledged</>,
                  <>Algorithm, inputs, interval and damping still open</>,
                ]
          }
        />
      </DiagramNode>

      {(Object.keys(EDGE_GEOMETRY) as DiagramEdgeId[]).filter((edgeId) => !hiddenEdges.includes(edgeId)).map((edgeId) => (
        <DiagramEdge key={edgeId} geometry={EDGE_GEOMETRY[edgeId]} active={activeEdges[edgeId]} highlighted={highlightedEdges.includes(edgeId)} />
      ))}
    </svg>
  );
}
