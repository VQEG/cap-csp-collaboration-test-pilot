import { InlineCodeText } from "@/components/GlossaryTerm";
import { cn } from "@/lib/utils";
import type { ImplementationStatus } from "@/model/implementationStatus";

const STATUS_BACKGROUND_CLASSES = {
  ok: "bg-status-ok",
  partial: "bg-status-partial",
  none: "bg-status-none",
} as const;

export function ImplementationStatusBanner({ status }: { status: ImplementationStatus }) {
  return (
    <div className={cn("flex flex-wrap gap-x-3 gap-y-1 rounded-lg px-3.5 py-2.5 text-sm", STATUS_BACKGROUND_CLASSES[status.kind])}>
      <b className="whitespace-nowrap">{status.title}</b>
      <span>
        <InlineCodeText text={status.explanation} />
      </span>
    </div>
  );
}
