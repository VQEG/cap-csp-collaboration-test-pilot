import { useEffect, useState } from "react";
import type { WalkthroughStep } from "@/model/networkStepWalkthrough";

const PLAYBACK_INTERVAL_MS = 1600;

/** Selected walkthrough step, with Back/Next and automatic playback over the active steps. */
export function useStepPlayback(steps: WalkthroughStep[]) {
  const activeStepIndices = steps.flatMap((step, index) => (step.active ? [index] : []));
  const activeKey = activeStepIndices.join(",");
  const [selectedStepIndex, setSelectedStepIndex] = useState(activeStepIndices[0] ?? 0);
  const [playing, setPlaying] = useState(false);

  // Keep the selection on an active step when the settings change.
  useEffect(() => {
    if (!activeStepIndices.includes(selectedStepIndex)) setSelectedStepIndex(activeStepIndices[0] ?? 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey]);

  function moveSelection(offset: number) {
    setSelectedStepIndex((current) => {
      const position = activeStepIndices.indexOf(current);
      const count = activeStepIndices.length;
      return activeStepIndices[(position + offset + count) % count];
    });
  }

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => moveSelection(1), PLAYBACK_INTERVAL_MS);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, activeKey]);

  return {
    selectedStepIndex,
    selectStep: setSelectedStepIndex,
    moveSelection,
    playing,
    togglePlaying: () => setPlaying((value) => !value),
  };
}
