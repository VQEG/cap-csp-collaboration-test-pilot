// Player behaviours and their parameters, from the SFV rules and
// configs/experiments/vqeg/*.json. SFV defaults are the values a rule uses
// when the key is missing.

export type PlayerBehavior = "simple" | "preload";
export type BehaviorMixId = "b1" | "b2" | "b1-b2";

export interface BehaviorParameter {
  id: string;
  label: string;
  /** Where the value goes in a session: `rule_config`, `rule_config.throughput` or `config.scheduling`. */
  location: "rule" | "throughput" | "scheduling";
  key: string;
  kind: "integer" | "number" | "boolean";
  min?: number;
  step?: number;
  /** Written to the config even when it equals the SFV default, as the condition configs do. */
  alwaysWritten: boolean;
  hint: string;
}

export const BEHAVIOR_PARAMETERS: BehaviorParameter[] = [
  { id: "activeBufferTargetSegments", label: "Buffer target, current video", location: "rule", key: "activeBufferTargetSegments", kind: "integer", min: 1, alwaysWritten: true, hint: "Segments of the playing video kept ahead" },
  { id: "preloadSegmentsPerVideo", label: "Preload per next video", location: "rule", key: "preload_segments_per_video", kind: "integer", min: 0, alwaysWritten: true, hint: "Segments fetched for each upcoming video" },
  { id: "maxPreloadSegments", label: "Preload limit", location: "rule", key: "max_preload_segments", kind: "integer", min: 0, alwaysWritten: true, hint: "Preloaded segments over all upcoming videos" },
  { id: "maxConcurrentRequests", label: "Concurrent requests", location: "scheduling", key: "maxConcurrentRequests", kind: "integer", min: 1, alwaysWritten: true, hint: "Open requests per UE" },
  { id: "swipeCancellation", label: "Cancel on swipe", location: "scheduling", key: "swipeCancellation", kind: "boolean", alwaysWritten: false, hint: "Abort downloads of the old video when the user swipes" },
  { id: "safetyFactor", label: "Throughput safety factor", location: "throughput", key: "safetyFactor", kind: "number", min: 0, step: 0.05, alwaysWritten: false, hint: "Quality choice uses estimate × factor (dash.js: 0.9)" },
  { id: "fastHalfLifeS", label: "Fast EWMA half-life (s)", location: "throughput", key: "fastHalfLifeS", kind: "number", min: 0.1, step: 0.5, alwaysWritten: false, hint: "dash.js: 3 s" },
  { id: "slowHalfLifeS", label: "Slow EWMA half-life (s)", location: "throughput", key: "slowHalfLifeS", kind: "number", min: 0.1, step: 0.5, alwaysWritten: false, hint: "dash.js: 8 s" },
];

export type BehaviorParameterValues = Record<string, number | boolean>;

export interface PlayerBehaviorDefinition {
  label: string;
  shortLabel: string;
  ruleName: "SFVCurrentVideoRule" | "SFVMultiVideoPrefetchRule";
  /** Parameters this behaviour has, with the values of the condition configs. */
  defaults: BehaviorParameterValues;
  /** Values the SFV code uses when a key is missing. */
  sfvDefaults: BehaviorParameterValues;
}

const SHARED_SFV_DEFAULTS = { activeBufferTargetSegments: 2, swipeCancellation: true, safetyFactor: 0.9, fastHalfLifeS: 3, slowHalfLifeS: 8 };

export const PLAYER_BEHAVIORS: Record<PlayerBehavior, PlayerBehaviorDefinition> = {
  simple: {
    label: "B1 simple",
    shortLabel: "B1",
    ruleName: "SFVCurrentVideoRule",
    defaults: { activeBufferTargetSegments: 2, maxConcurrentRequests: 2, swipeCancellation: true, safetyFactor: 0.9, fastHalfLifeS: 3, slowHalfLifeS: 8 },
    sfvDefaults: SHARED_SFV_DEFAULTS,
  },
  preload: {
    label: "B2 preload",
    shortLabel: "B2",
    ruleName: "SFVMultiVideoPrefetchRule",
    defaults: {
      activeBufferTargetSegments: 2,
      preloadSegmentsPerVideo: 2,
      maxPreloadSegments: 4,
      maxConcurrentRequests: 3,
      swipeCancellation: true,
      safetyFactor: 0.9,
      fastHalfLifeS: 3,
      slowHalfLifeS: 8,
    },
    sfvDefaults: { ...SHARED_SFV_DEFAULTS, preloadSegmentsPerVideo: 2, maxPreloadSegments: 6 },
  },
};

/** Behaviour mixes: the pattern repeats over the UEs of a cell, as in a grid's `behavior_mixes`. */
export const BEHAVIOR_MIXES: Record<BehaviorMixId, { label: string; pattern: PlayerBehavior[] }> = {
  b1: { label: "B1 only", pattern: ["simple"] },
  b2: { label: "B2 only", pattern: ["preload"] },
  "b1-b2": { label: "B1 + B2 alternating", pattern: ["simple", "preload"] },
};

export function behaviorOfUe(mix: BehaviorMixId, ueId: number): PlayerBehavior {
  const pattern = BEHAVIOR_MIXES[mix].pattern;
  return pattern[ueId % pattern.length];
}

/** The behaviours that take part in a mix with this many UEs. */
export function behaviorsInMix(mix: BehaviorMixId, ueCount: number): PlayerBehavior[] {
  return [...new Set([...Array(ueCount).keys()].map((ueId) => behaviorOfUe(mix, ueId)))];
}
