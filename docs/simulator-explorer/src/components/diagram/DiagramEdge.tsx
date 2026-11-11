import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { GlossaryCardContent } from "@/components/GlossaryTerm";
import { GLOSSARY } from "@/data/glossary";
import { cn } from "@/lib/utils";
import { EDGE_COLOR_VARIABLES, type DiagramEdgeGeometry } from "@/components/diagram/diagramLayout";

export function arrowMarkerId(colorKey: string): string {
  return `diagram-arrow-${colorKey}`;
}

/** Arrowhead markers, one per arrow color. */
export function DiagramArrowMarkers() {
  return (
    <defs>
      {Object.entries(EDGE_COLOR_VARIABLES).map(([colorKey, color]) => (
        <marker
          key={colorKey}
          id={arrowMarkerId(colorKey)}
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerUnits="userSpaceOnUse"
          markerWidth="10"
          markerHeight="10"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" style={{ fill: color }} />
        </marker>
      ))}
    </defs>
  );
}

interface DiagramEdgeProps {
  geometry: DiagramEdgeGeometry;
  active: boolean;
  highlighted: boolean;
}

export function DiagramEdge({ geometry, active, highlighted }: DiagramEdgeProps) {
  const colorKey = active ? geometry.color : "inactive";
  const color = EDGE_COLOR_VARIABLES[colorKey];
  const emphasised = active && highlighted;
  const label = geometry.label && (
    <text
      x={geometry.labelX}
      y={geometry.labelY}
      textAnchor={geometry.labelAnchor ?? "middle"}
      transform={geometry.labelVertical ? `rotate(-90 ${geometry.labelX} ${geometry.labelY})` : undefined}
      className={cn("font-mono text-[11px] outline-none", geometry.glossaryTerm && "cursor-help")}
      style={{ fill: color, paintOrder: "stroke", stroke: "var(--card)", strokeWidth: 4, strokeLinejoin: "round" }}
      fontWeight={emphasised ? 700 : 500}
      tabIndex={geometry.glossaryTerm ? 0 : undefined}
    >
      {geometry.label}
    </text>
  );

  return (
    <g>
      <path
        d={geometry.path}
        fill="none"
        style={{ stroke: color }}
        strokeWidth={emphasised ? 3.5 : 1.8}
        strokeDasharray={!active ? "3 5" : geometry.dashed && !emphasised ? "7 5" : undefined}
        className={cn(emphasised && "diagram-edge-highlighted")}
        markerEnd={`url(#${arrowMarkerId(colorKey)})`}
      />
      {label && geometry.glossaryTerm ? (
        <HoverCard openDelay={120} closeDelay={80}>
          <HoverCardTrigger asChild>{label}</HoverCardTrigger>
          <HoverCardContent className="w-[380px] max-w-[calc(100vw-32px)]" collisionPadding={12}>
            <GlossaryCardContent entry={GLOSSARY[geometry.glossaryTerm]} />
          </HoverCardContent>
        </HoverCard>
      ) : (
        label
      )}
    </g>
  );
}
