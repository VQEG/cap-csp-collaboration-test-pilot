import { REPOSITORIES, type RepositoryId } from "@/data/repositories";
import { EDGE_COLOR_VARIABLES, type EdgeColorKey } from "@/components/diagram/diagramLayout";

const ARROW_LEGEND: [EdgeColorKey, string][] = [
  ["main", "main loop"],
  ["cspToCap", "CSP → CAP"],
  ["capToCsp", "CAP → CSP"],
  ["oracleOrLog", "oracle / log only"],
  ["internal", "inside a component"],
];

export function DiagramLegend() {
  return (
    <div className="space-y-1.5 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <b className="font-semibold text-foreground">Box color = repository</b>
        {(Object.entries(REPOSITORIES) as [RepositoryId, (typeof REPOSITORIES)[RepositoryId]][]).map(([id, repository]) => (
          <span key={id} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3.5 rounded-[3px] border-[1.5px]" style={{ borderColor: `var(--repo-${id})`, background: `var(--repo-${id}-soft)` }} />
            <span>
              <b className="font-medium text-foreground">{repository.fullName}</b> · {repository.location}
            </span>
          </span>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <b className="font-semibold text-foreground">Arrows</b>
        {ARROW_LEGEND.map(([colorKey, label]) => (
          <span key={colorKey} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-[3px] w-[18px]" style={{ background: EDGE_COLOR_VARIABLES[colorKey] }} />
            {label}
          </span>
        ))}
        <span>· Grey dashed: not active here · Thick, moving: current step · Dotted underline: hover for details</span>
      </div>
    </div>
  );
}
