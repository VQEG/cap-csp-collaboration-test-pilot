// Content catalogues available in the repository:
// - aomctc_per_title: configs/content/aomctc-a2-2k-long/<encoder>-segment-<n>s.json (per-title ladders from real
//   encodes of the 17 long AOM CTC a2_2k clips, one catalogue per encoder and segment duration)
// - portrait_hd_90s: configs/content/sfv-portrait-hd-90s.json (provisional 18 × 8 s portrait Full HD ladder)
// - fixture: sfv-reference-implementation/fixtures/content/content.json (3 × 6 s smoke-test fixture)

export type ContentCatalogueId = "aomctc_per_title" | "portrait_hd_90s" | "fixture";
/** Catalogues with one fixed ladder for all videos. */
export type FixedLadderCatalogueId = Exclude<ContentCatalogueId, "aomctc_per_title">;
export const CONTENT_CATALOGUE_IDS: ContentCatalogueId[] = ["aomctc_per_title", "portrait_hd_90s", "fixture"];

export interface ContentVideoRepresentation {
  id: string;
  width: number;
  height: number;
  /** Bitrate declared in the manifest. */
  bitrateKbps: number;
  /** Average over the segment sizes of all videos in the catalogue. */
  measuredBitrateKbps: number;
}

export interface ContentCatalogueDefinition {
  id: FixedLadderCatalogueId;
  label: string;
  filePath: string;
  /** Path relative to a config saved under configs/experiments/<dir>/ or configs/grids/. */
  pathFromSubdirConfig: string;
  /** Path relative to a config saved directly under configs/grids/ or configs/experiments/. */
  pathFromConfigsChild: string;
  videoIdsSummary: string;
  videoCount: number;
  videoDurationS: number;
  segmentDurationS: number;
  videoCodec: string;
  frameRateFps: number;
  representations: ContentVideoRepresentation[];
  audioRepresentation: { id: string; codec: string; bitrateKbps: number };
}

export const CONTENT_CATALOGUES: Record<FixedLadderCatalogueId, ContentCatalogueDefinition> = {
  portrait_hd_90s: {
    id: "portrait_hd_90s",
    label: "18 × 8 s Full HD (300–8000 kbps)",
    filePath: "configs/content/sfv-portrait-hd-90s.json",
    pathFromSubdirConfig: "../../content/sfv-portrait-hd-90s.json",
    pathFromConfigsChild: "../content/sfv-portrait-hd-90s.json",
    videoIdsSummary: "v01 … v18",
    videoCount: 18,
    videoDurationS: 8,
    segmentDurationS: 2,
    videoCodec: "avc1.640028",
    frameRateFps: 30,
    representations: [
      { id: "0", width: 270, height: 480, bitrateKbps: 300, measuredBitrateKbps: 301 },
      { id: "1", width: 360, height: 640, bitrateKbps: 650, measuredBitrateKbps: 652 },
      { id: "2", width: 540, height: 960, bitrateKbps: 1300, measuredBitrateKbps: 1304 },
      { id: "3", width: 720, height: 1280, bitrateKbps: 2400, measuredBitrateKbps: 2407 },
      { id: "4", width: 1080, height: 1920, bitrateKbps: 5200, measuredBitrateKbps: 5215 },
      { id: "5", width: 1080, height: 1920, bitrateKbps: 8000, measuredBitrateKbps: 8022 },
    ],
    audioRepresentation: { id: "audio-0", codec: "mp4a.40.2", bitrateKbps: 96 },
  },
  fixture: {
    id: "fixture",
    label: "3 × 6 s test fixture (180–650 kbps)",
    filePath: "sfv-reference-implementation/fixtures/content/content.json",
    pathFromSubdirConfig: "../../../sfv-reference-implementation/fixtures/content/content.json",
    pathFromConfigsChild: "../../sfv-reference-implementation/fixtures/content/content.json",
    videoIdsSummary: "v1, v2, v3",
    videoCount: 3,
    videoDurationS: 6,
    segmentDurationS: 2,
    videoCodec: "avc1",
    frameRateFps: 30,
    representations: [
      { id: "0", width: 180, height: 320, bitrateKbps: 180, measuredBitrateKbps: 198 },
      { id: "1", width: 270, height: 480, bitrateKbps: 350, measuredBitrateKbps: 379 },
      { id: "2", width: 360, height: 640, bitrateKbps: 650, measuredBitrateKbps: 692 },
    ],
    audioRepresentation: { id: "3", codec: "mp4a", bitrateKbps: 64 },
  },
};

// Per-title ladders (configs/content/aomctc-a2-2k-long/README.md), by Samuel Hufen with method input from Werner
// Robitza. Samuel encoded the 17 long AOM CTC a2_2k clips with five encoders, six resolutions and 13 CRFs at 1, 2, 4 and 5 s segments (keyframe interval = segment
// duration). Each video gets one rung per VMAF v1.0.16 5H target (90 to 50): the cheapest encode on the clip's
// convex hull that reaches it. The numbers below summarize the generated catalogues; regenerate them when the
// catalogues change.

export type ContentEncoder = "x264" | "x265" | "vp9" | "libaom" | "svtav1";
export const CONTENT_ENCODERS: ContentEncoder[] = ["x264", "x265", "vp9", "libaom", "svtav1"];
export type ContentSegmentDurationS = 1 | 2 | 4 | 5;
export const CONTENT_SEGMENT_DURATIONS_S: ContentSegmentDurationS[] = [1, 2, 4, 5];

export const CONTENT_ENCODER_DETAILS: Record<ContentEncoder, { label: string; codecString: string; codecFamily: string }> = {
  x264: { label: "x264", codecString: "avc1.640028", codecFamily: "H.264" },
  x265: { label: "x265", codecString: "hvc1.1.6.L120.90", codecFamily: "HEVC" },
  vp9: { label: "VP9", codecString: "vp09.00.40.08", codecFamily: "VP9" },
  libaom: { label: "libaom", codecString: "av01.0.08M.08", codecFamily: "AV1" },
  svtav1: { label: "SVT-AV1", codecString: "av01.0.08M.08", codecFamily: "AV1" },
};

export const PER_TITLE_QUALITY_METRIC = "VMAF v1.0.16 5H";
export const PER_TITLE_DIRECTORY = "configs/content/aomctc-a2-2k-long";

/** File name of one per-title catalogue. */
export function perTitleCatalogueFileName(encoder: ContentEncoder, segmentDurationS: ContentSegmentDurationS): string {
  return `${encoder}-segment-${segmentDurationS}s.json`;
}

/** Path relative to a config saved directly under configs/grids/ or configs/experiments/. */
export function perTitleCataloguePathFromConfigsChild(encoder: ContentEncoder, segmentDurationS: ContentSegmentDurationS): string {
  return `../content/aomctc-a2-2k-long/${perTitleCatalogueFileName(encoder, segmentDurationS)}`;
}

/** Name of a per-title catalogue on the grid's content_catalogues axis, for example `svtav1-seg2s`. */
export function perTitleCatalogueAxisName(encoder: ContentEncoder, segmentDurationS: ContentSegmentDurationS): string {
  return `${encoder}-seg${segmentDurationS}s`;
}

export interface PerTitleVideo {
  videoId: string;
  sourceClip: string;
  durationS: number;
  frameRateFps: number;
  portrait: boolean;
}

export interface PerTitleLadderRungSummary {
  targetVmaf: number;
  /** Median bitrate of the rungs for this target, over the clips that have one. */
  medianBitrateKbps: number;
  /** Clips with a rung for this target: a target is missing when no encode reaches it or when it shares an encode with a lower target. */
  clipCount: number;
  /** Most common short side of the rungs for this target, in pixels. */
  typicalShortSidePx: number;
}

export interface PerTitleLadderSummary {
  /** Video representations over all 17 videos. */
  representationCount: number;
  rungs: PerTitleLadderRungSummary[];
}

export const PER_TITLE_VIDEOS: PerTitleVideo[] = [
  { videoId: "v01-vertical-carnaby", sourceClip: "Vertical_Carnaby_5994_1080x1920", durationS: 5.0, frameRateFps: 59.94, portrait: true },
  { videoId: "v02-crowd-run", sourceClip: "crowd_run_1080p50", durationS: 10.0, frameRateFps: 50.0, portrait: false },
  { videoId: "v03-meridian-talk", sourceClip: "Meridian_talk_sdr_1080p_10bit", durationS: 6.37, frameRateFps: 59.94, portrait: false },
  { videoId: "v04-ritual-dance", sourceClip: "RitualDance_1920x1080_60fps_10bit_420", durationS: 10.01, frameRateFps: 59.94, portrait: false },
  { videoId: "v05-walking-in-street", sourceClip: "raw_1080x1920@30.walking.in.street", durationS: 16.67, frameRateFps: 30.0, portrait: true },
  { videoId: "v06-world-cup", sourceClip: "WorldCup_1920x1080_30p", durationS: 5.03, frameRateFps: 30.0, portrait: false },
  { videoId: "v07-aerial", sourceClip: "Aerial3200_1920x1080_5994_10bit_420", durationS: 9.19, frameRateFps: 59.94, portrait: false },
  { videoId: "v08-food-market", sourceClip: "FoodMarket_1920x1080_60fps_10bit_420", durationS: 10.01, frameRateFps: 59.94, portrait: false },
  { videoId: "v09-vertical-bees", sourceClip: "Vertical_bees_2997_1080x1920", durationS: 5.0, frameRateFps: 29.97, portrait: true },
  { videoId: "v10-rush-field-cuts", sourceClip: "rush_field_cuts_1080p", durationS: 19.02, frameRateFps: 29.97, portrait: false },
  { videoId: "v11-skater", sourceClip: "Skater227_1920x1080_30fps", durationS: 10.0, frameRateFps: 30.0, portrait: false },
  { videoId: "v12-old-town-cross", sourceClip: "old_town_cross_1080p50", durationS: 10.0, frameRateFps: 50.0, portrait: false },
  { videoId: "v13-tunnel-flag", sourceClip: "TunnelFlag_1920x1080_60fps_10bit_420", durationS: 10.01, frameRateFps: 59.94, portrait: false },
  { videoId: "v14-pedestrian-area", sourceClip: "pedestrian_area_1080p25", durationS: 15.0, frameRateFps: 25.0, portrait: false },
  { videoId: "v15-boat", sourceClip: "Boat_1920x1080_60fps_10bit_420", durationS: 5.0, frameRateFps: 59.94, portrait: false },
  { videoId: "v16-world-cup-far", sourceClip: "WorldCup_far_1920x1080_30p", durationS: 5.03, frameRateFps: 30.0, portrait: false },
  { videoId: "v17-riverbed", sourceClip: "riverbed_1080p25", durationS: 10.0, frameRateFps: 25.0, portrait: false },
];

export const PER_TITLE_LADDER_SUMMARIES: Record<ContentEncoder, Record<ContentSegmentDurationS, PerTitleLadderSummary>> = {
  x264: {
    1: {
      representationCount: 82,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3743, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1774, clipCount: 17, typicalShortSidePx: 540 },
        { targetVmaf: 70, medianBitrateKbps: 983, clipCount: 16, typicalShortSidePx: 480 },
        { targetVmaf: 60, medianBitrateKbps: 844, clipCount: 15, typicalShortSidePx: 360 },
        { targetVmaf: 50, medianBitrateKbps: 642, clipCount: 17, typicalShortSidePx: 360 },
      ],
    },
    2: {
      representationCount: 83,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3460, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1849, clipCount: 17, typicalShortSidePx: 540 },
        { targetVmaf: 70, medianBitrateKbps: 1129, clipCount: 16, typicalShortSidePx: 480 },
        { targetVmaf: 60, medianBitrateKbps: 606, clipCount: 16, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 569, clipCount: 17, typicalShortSidePx: 360 },
      ],
    },
    4: {
      representationCount: 84,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3384, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1830, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 70, medianBitrateKbps: 991, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 60, medianBitrateKbps: 681, clipCount: 16, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 537, clipCount: 17, typicalShortSidePx: 360 },
      ],
    },
    5: {
      representationCount: 83,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3375, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1830, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 70, medianBitrateKbps: 991, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 60, medianBitrateKbps: 812, clipCount: 15, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 502, clipCount: 17, typicalShortSidePx: 360 },
      ],
    },
  },
  x265: {
    1: {
      representationCount: 82,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 2611, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1622, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 645, clipCount: 15, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 551, clipCount: 16, typicalShortSidePx: 720 },
        { targetVmaf: 50, medianBitrateKbps: 421, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
    2: {
      representationCount: 83,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 2961, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1617, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 743, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 604, clipCount: 15, typicalShortSidePx: 540 },
        { targetVmaf: 50, medianBitrateKbps: 394, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
    4: {
      representationCount: 82,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 2932, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1616, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 734, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 620, clipCount: 14, typicalShortSidePx: 540 },
        { targetVmaf: 50, medianBitrateKbps: 382, clipCount: 17, typicalShortSidePx: 720 },
      ],
    },
    5: {
      representationCount: 83,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 2938, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1449, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 713, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 599, clipCount: 15, typicalShortSidePx: 540 },
        { targetVmaf: 50, medianBitrateKbps: 372, clipCount: 17, typicalShortSidePx: 720 },
      ],
    },
  },
  vp9: {
    1: {
      representationCount: 85,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3266, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1725, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 1061, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 770, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 497, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
    2: {
      representationCount: 85,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3657, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1692, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 1033, clipCount: 17, typicalShortSidePx: 540 },
        { targetVmaf: 60, medianBitrateKbps: 765, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 455, clipCount: 17, typicalShortSidePx: 540 },
      ],
    },
    4: {
      representationCount: 85,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3556, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1673, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 1023, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 721, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 483, clipCount: 17, typicalShortSidePx: 540 },
      ],
    },
    5: {
      representationCount: 85,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 3548, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1647, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 1005, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 60, medianBitrateKbps: 676, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 444, clipCount: 17, typicalShortSidePx: 540 },
      ],
    },
  },
  libaom: {
    1: {
      representationCount: 84,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1972, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1152, clipCount: 17, typicalShortSidePx: 540 },
        { targetVmaf: 70, medianBitrateKbps: 631, clipCount: 17, typicalShortSidePx: 540 },
        { targetVmaf: 60, medianBitrateKbps: 437, clipCount: 16, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 264, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
    2: {
      representationCount: 84,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1880, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1041, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 583, clipCount: 17, typicalShortSidePx: 480 },
        { targetVmaf: 60, medianBitrateKbps: 412, clipCount: 16, typicalShortSidePx: 540 },
        { targetVmaf: 50, medianBitrateKbps: 243, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
    4: {
      representationCount: 83,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1836, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 1030, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 649, clipCount: 16, typicalShortSidePx: 540 },
        { targetVmaf: 60, medianBitrateKbps: 409, clipCount: 16, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 244, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
    5: {
      representationCount: 84,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1837, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 80, medianBitrateKbps: 970, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 550, clipCount: 17, typicalShortSidePx: 540 },
        { targetVmaf: 60, medianBitrateKbps: 313, clipCount: 16, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 226, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
  },
  svtav1: {
    1: {
      representationCount: 83,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1640, clipCount: 17, typicalShortSidePx: 1080 },
        { targetVmaf: 80, medianBitrateKbps: 935, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 575, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 426, clipCount: 15, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 242, clipCount: 17, typicalShortSidePx: 480 },
      ],
    },
    2: {
      representationCount: 83,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1572, clipCount: 17, typicalShortSidePx: 1080 },
        { targetVmaf: 80, medianBitrateKbps: 907, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 556, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 346, clipCount: 15, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 236, clipCount: 17, typicalShortSidePx: 360 },
      ],
    },
    4: {
      representationCount: 81,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1535, clipCount: 17, typicalShortSidePx: 1080 },
        { targetVmaf: 80, medianBitrateKbps: 886, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 554, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 351, clipCount: 13, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 207, clipCount: 17, typicalShortSidePx: 360 },
      ],
    },
    5: {
      representationCount: 81,
      rungs: [
        { targetVmaf: 90, medianBitrateKbps: 1528, clipCount: 17, typicalShortSidePx: 1080 },
        { targetVmaf: 80, medianBitrateKbps: 882, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 70, medianBitrateKbps: 536, clipCount: 17, typicalShortSidePx: 720 },
        { targetVmaf: 60, medianBitrateKbps: 395, clipCount: 13, typicalShortSidePx: 480 },
        { targetVmaf: 50, medianBitrateKbps: 199, clipCount: 17, typicalShortSidePx: 360 },
      ],
    },
  },
};
