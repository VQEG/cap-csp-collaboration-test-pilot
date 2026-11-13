import { CONTENT_VIDEO_COUNT } from "@/data/contentCatalogue";
import type { ExplorerSettings } from "@/model/explorerSettings";

// The swipe times SFV resolves for one session, computed as in
// sfv-reference-implementation/src/simulation/generators/SFVGenerators.js
// (resolveUserInteractions with the mulberry32 SFVSeededGenerator).

/** A session swipes at most once per further video. */
export const MAX_SWIPES_PER_SESSION = CONTENT_VIDEO_COUNT - 1;

class SeededGenerator {
  private state: number;

  constructor(seed: number) {
    this.state = seed >>> 0;
  }

  next(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  between(min: number, max: number): number {
    return min + (max - min) * this.next();
  }
}

/** Swipe times of the sequence model, or an error text. */
export function parseSwipeTimes(text: string): number[] | string {
  const parts = text.split(",").map((part) => part.trim()).filter(Boolean);
  const times = parts.map(Number);
  if (times.some((time) => !Number.isFinite(time) || time < 0)) return "Swipe times must be non-negative numbers";
  if (times.some((time, index) => index > 0 && time <= times[index - 1])) return "Swipe times must increase";
  return times;
}

/** The valid [min, max] range of the seeded model; the default when the input is not valid. */
export function watchDurationRange(settings: ExplorerSettings): [number, number] {
  const [low, high] = settings.watchDurationRangeS;
  return Number.isFinite(low) && Number.isFinite(high) && low >= 0 && low <= high ? [low, high] : [2, 16];
}

/** Session-relative swipe times of one UE, as SFV resolves them before the session starts. */
export function resolveSwipeTimes(settings: ExplorerSettings, sessionSeed: number, horizonS: number): number[] {
  if (settings.swipeModel === "sequence") {
    const times = parseSwipeTimes(settings.swipeTimesS);
    return typeof times === "string" ? [] : times.filter((time) => time < horizonS).slice(0, MAX_SWIPES_PER_SESSION);
  }
  const [low, high] = watchDurationRange(settings);
  const generator = new SeededGenerator(sessionSeed);
  const times: number[] = [];
  let time = 0;
  for (let index = 0; index < MAX_SWIPES_PER_SESSION; index += 1) {
    time += generator.between(low, high);
    if (time >= horizonS) break;
    times.push(time);
  }
  return times;
}
