import { useEffect, useRef } from "react";
import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { WalkthroughStep } from "@/model/networkStepWalkthrough";

interface StepWalkthroughStripProps {
  steps: WalkthroughStep[];
  selectedStepIndex: number;
  selectStep: (index: number) => void;
  moveSelection: (offset: number) => void;
  playing: boolean;
  togglePlaying: () => void;
}

/** Horizontally scrolling list of the steps of one NetworkStep. The selected step scrolls to the middle. */
export function StepWalkthroughStrip({ steps, selectedStepIndex, selectStep, moveSelection, playing, togglePlaying }: StepWalkthroughStripProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const stepListRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    // The scroll area's viewport is the element that scrolls
    const viewport = scrollAreaRef.current?.querySelector<HTMLElement>("[data-slot=scroll-area-viewport]");
    const item = stepListRef.current?.children[selectedStepIndex] as HTMLElement | undefined;
    if (!viewport || !item) return;
    viewport.scrollTo({ left: item.offsetLeft - (viewport.clientWidth - item.offsetWidth) / 2, behavior: "smooth" });
  }, [selectedStepIndex, steps.length]);

  return (
    <Card className="gap-3 px-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">One 10 ms step</h2>
        <div className="flex gap-1.5">
          <Button variant="outline" size="sm" onClick={() => moveSelection(-1)}>
            <ChevronLeft /> Back
          </Button>
          <Button size="sm" onClick={togglePlaying} className="min-w-20">
            {playing ? <Pause /> : <Play />} {playing ? "Pause" : "Play"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => moveSelection(1)}>
            Next <ChevronRight />
          </Button>
        </div>
      </div>
      <ScrollArea ref={scrollAreaRef} type="always" className="w-full [&>[data-slot=scroll-area-viewport]]:snap-x [&>[data-slot=scroll-area-viewport]]:snap-proximity">
        <ol ref={stepListRef} className="relative flex w-max gap-2.5 pb-3">
          {steps.map((step, index) => (
            <li
              key={index}
              onClick={() => step.active && selectStep(index)}
              className={cn(
                "relative w-[clamp(220px,21vw,280px)] shrink-0 cursor-pointer snap-start rounded-lg border py-2.5 pr-3 pl-10 text-[13px] leading-snug transition-colors",
                index === selectedStepIndex ? "border-highlight bg-highlight-soft" : "hover:bg-muted/60",
                !step.active && "cursor-default text-muted-foreground/70 line-through decoration-muted-foreground/40",
              )}
            >
              <span
                className={cn(
                  "absolute top-2.5 left-3 grid h-5 w-5 place-items-center rounded-full text-[11px]",
                  index === selectedStepIndex ? "bg-highlight text-white" : "bg-muted text-muted-foreground",
                )}
              >
                {index + 1}
              </span>
              <span className="mb-0.5 block text-[11px] text-muted-foreground no-underline">{step.actor}</span>
              {step.description}
            </li>
          ))}
        </ol>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>
    </Card>
  );
}
