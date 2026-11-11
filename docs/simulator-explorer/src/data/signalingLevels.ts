import type { SignalingLevel } from "@/model/explorerSettings";

// Names and one-line descriptions of L0–L4, from docs/signaling.md.
export const SIGNALING_LEVELS: Record<SignalingLevel, { name: string; description: string }> = {
  L0: {
    name: "Baseline",
    description: "No collaboration. The player estimates throughput only from its own past segment downloads.",
  },
  L1: {
    name: "Static subscription",
    description: "The player receives the provisioned subscriber downlink rate (plan rate) from the experiment configuration.",
  },
  L2: {
    name: "Live telemetry",
    description: "The player receives live network measurements from the backend: achieved throughput, RTT, loss and congestion rate.",
  },
  L3: {
    name: "Bidirectional",
    description:
      "In addition to L2, the player sends CAP reports (stall state, buffer, video, swipe rate). A CSP controller reads them and adjusts per-UE scheduler priority or rate caps.",
  },
  L4: {
    name: "Capacity oracle",
    description: "The player receives a lookahead trace of future available capacity, as an upper-bound reference.",
  },
};
