import type { ImplementationState } from "@/model/explorerSettings";

// The implementation states that can be compared in the explorer.
export const IMPLEMENTATION_STATES: Record<ImplementationState, { label: string; hint: string }> = {
  design: { label: "Design (spec)", hint: "What docs/signaling.md and docs/architecture.md on master describe." },
  master: { label: "master", hint: "What the code on master does today." },
};
