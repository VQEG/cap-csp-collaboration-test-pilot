import type { ReactNode } from "react";
import type { RepositoryId } from "@/data/repositories";
import { cn } from "@/lib/utils";
import type { DiagramRectangle } from "@/components/diagram/diagramLayout";

const REPOSITORY_BOX_CLASSES: Record<RepositoryId, string> = {
  harness: "border-repo-harness bg-repo-harness-soft",
  sfv: "border-repo-sfv bg-repo-sfv-soft",
  fikore: "border-repo-fikore bg-repo-fikore-soft",
};

interface DiagramNodeProps {
  box: DiagramRectangle;
  repository: RepositoryId | null;
  title: ReactNode;
  codePath?: string;
  active: boolean;
  highlighted: boolean;
  children?: ReactNode;
}

/**
 * One box of the architecture diagram. The content is HTML inside a
 * foreignObject, so it wraps text and hosts hover cards; it scales with the
 * SVG viewBox.
 *
 * Avoid position, opacity, transform and filter inside the foreignObject:
 * WebKit (Safari) paints such layers outside the SVG's scaling transform, so
 * they drift out of the box and do not wrap at the box width.
 */
export function DiagramNode({ box, repository, title, codePath, active, highlighted, children }: DiagramNodeProps) {
  return (
    <foreignObject x={box.x - 4} y={box.y - 4} width={box.width + 8} height={box.height + 8}>
      <div className="h-full w-full p-[4px]">
        <div
          className={cn(
            "flex h-full w-full flex-col overflow-hidden rounded-lg border-[1.5px] px-3 py-2 text-foreground transition-shadow",
            active && repository ? REPOSITORY_BOX_CLASSES[repository] : "border-dashed border-flow-inactive bg-card",
            highlighted && active && "shadow-[0_0_0_3px_var(--highlight)]",
          )}
        >
          <div className={cn("text-[14px] leading-tight font-semibold", !active && "text-muted-foreground")}>{title}</div>
          {codePath && <div className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground" title={codePath}>{codePath}</div>}
          {children && (
            <div className={cn("mt-1.5 text-[11.5px] leading-[1.4]", active ? "text-foreground/85" : "text-muted-foreground/60")}>{children}</div>
          )}
        </div>
      </div>
    </foreignObject>
  );
}

/** Bullet list for the details inside a diagram box. */
export function NodeDetailList({ items }: { items: ReactNode[] }) {
  return (
    <ul className="space-y-0.5">
      {items.filter(Boolean).map((item, index) => (
        <li key={index} className="flex gap-2">
          <span aria-hidden className="mt-[0.6em] h-1 w-1 shrink-0 rounded-full bg-current/50" />
          <span className="min-w-0">{item}</span>
        </li>
      ))}
    </ul>
  );
}
