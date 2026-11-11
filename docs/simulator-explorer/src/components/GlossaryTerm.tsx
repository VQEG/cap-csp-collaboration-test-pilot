import type { ReactNode } from "react";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { Badge } from "@/components/ui/badge";
import { GLOSSARY, type GlossaryEntry, type GlossaryTermId } from "@/data/glossary";
import { REPOSITORIES } from "@/data/repositories";
import { cn } from "@/lib/utils";

const REPOSITORY_BADGE_CLASSES = {
  harness: "border-repo-harness text-repo-harness bg-repo-harness-soft",
  sfv: "border-repo-sfv text-repo-sfv bg-repo-sfv-soft",
  fikore: "border-repo-fikore text-repo-fikore bg-repo-fikore-soft",
} as const;

export function isGlossaryTermId(value: string): value is GlossaryTermId {
  return Object.hasOwn(GLOSSARY, value);
}

/** Renders text with `backtick` spans as inline code. Code spans that match a glossary id become hoverable terms. */
export function InlineCodeText({ text, linkGlossaryTerms = true }: { text: string; linkGlossaryTerms?: boolean }) {
  const parts = text.split(/(`[^`]+`)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (!part.startsWith("`")) return part;
        const code = part.slice(1, -1);
        const termId = code.replace(/\(.*\)$/, "");
        if (linkGlossaryTerms && isGlossaryTermId(termId)) {
          return (
            <GlossaryTerm key={index} id={termId} asCode>
              {code}
            </GlossaryTerm>
          );
        }
        return <InlineCode key={index}>{code}</InlineCode>;
      })}
    </>
  );
}

export function InlineCode({ children, className }: { children: ReactNode; className?: string }) {
  return <code className={cn("rounded bg-muted px-1 py-px font-mono text-[0.88em]", className)}>{children}</code>;
}

export function GlossaryCardContent({ entry }: { entry: GlossaryEntry }) {
  return (
    <div className="space-y-2 text-[13px] leading-snug">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-sm font-semibold">{entry.name}</span>
      </div>
      <div className="flex flex-wrap gap-1">
        <Badge variant="secondary" className="text-[11px]">
          {entry.kind}
        </Badge>
        {entry.repository && (
          <Badge variant="outline" className={cn("text-[11px]", REPOSITORY_BADGE_CLASSES[entry.repository])}>
            {REPOSITORIES[entry.repository].fullName}
          </Badge>
        )}
        {entry.availability && (
          <Badge variant="outline" className="border-amber-500/60 text-[11px] text-amber-700 dark:text-amber-300">
            {entry.availability}
          </Badge>
        )}
      </div>
      <p className="text-foreground/90">
        <InlineCodeText text={entry.summary} linkGlossaryTerms={false} />
      </p>
      {entry.fields && (
        <table className="w-full text-[12px]">
          <tbody>
            {entry.fields.map((field) => (
              <tr key={field.name} className="border-t border-border/70 align-top">
                <td className="py-1 pr-2 font-mono whitespace-nowrap">{field.name}</td>
                <td className="py-1 text-muted-foreground">
                  <span className="font-mono text-[11px]">{field.type}</span> · {field.description}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {entry.definedIn && <p className="font-mono text-[11px] break-words text-muted-foreground">{entry.definedIn}</p>}
    </div>
  );
}

interface GlossaryTermProps {
  id: GlossaryTermId;
  children?: ReactNode;
  /** Render the trigger as inline code. */
  asCode?: boolean;
  className?: string;
}

/** A word or code span that explains itself on hover (and on focus or tap). */
export function GlossaryTerm({ id, children, asCode = false, className }: GlossaryTermProps) {
  const entry: GlossaryEntry = GLOSSARY[id];
  const label = children ?? entry.name;
  return (
    <HoverCard openDelay={120} closeDelay={80}>
      <HoverCardTrigger asChild>
        <span
          tabIndex={0}
          className={cn(
            "cursor-help underline decoration-dotted decoration-from-font underline-offset-2 outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
            asCode && "rounded bg-muted px-1 py-px font-mono text-[0.88em]",
            className,
          )}
        >
          {label}
        </span>
      </HoverCardTrigger>
      <HoverCardContent className="w-[380px] max-w-[calc(100vw-32px)]" collisionPadding={12}>
        <GlossaryCardContent entry={entry} />
      </HoverCardContent>
    </HoverCard>
  );
}
