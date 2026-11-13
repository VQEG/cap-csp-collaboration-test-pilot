// The content every run plays: sfv-reference-implementation/fixtures/content/content.json.
// The explorer cannot change it yet. The harness reads another file from the `content` config key.

export const CONTENT_FILE_PATH = "sfv-reference-implementation/fixtures/content/content.json";
/** The `content` value in a config saved under configs/experiments/ or configs/grids/: paths are relative to the config file. */
export const CONTENT_PATH_FROM_CONFIG_FILE = `../../${CONTENT_FILE_PATH}`;

/** Played in this order. Every session starts with the first video. */
export const CONTENT_VIDEO_IDS = ["v1", "v2", "v3"] as const;
export const CONTENT_VIDEO_COUNT = CONTENT_VIDEO_IDS.length;
export const CONTENT_VIDEO_DURATION_S = 6;
export const CONTENT_SEGMENT_DURATION_S = 2;

export interface ContentVideoRepresentation {
  id: string;
  width: number;
  height: number;
  /** Bitrate declared in the manifest. */
  bitrateKbps: number;
  /** Average over the segment sizes of all three videos. */
  measuredBitrateKbps: number;
}

export const CONTENT_VIDEO_CODEC = "avc1";
export const CONTENT_FRAME_RATE_FPS = 30;

export const CONTENT_VIDEO_REPRESENTATIONS: ContentVideoRepresentation[] = [
  { id: "0", width: 180, height: 320, bitrateKbps: 180, measuredBitrateKbps: 198 },
  { id: "1", width: 270, height: 480, bitrateKbps: 350, measuredBitrateKbps: 379 },
  { id: "2", width: 360, height: 640, bitrateKbps: 650, measuredBitrateKbps: 692 },
];

export const CONTENT_AUDIO_REPRESENTATION = { id: "3", codec: "mp4a", bitrateKbps: 64 };
