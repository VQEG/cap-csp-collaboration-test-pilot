// Content catalogues available in the repository:
// - portrait_hd_90s: configs/content/sfv-portrait-hd-90s.json (18 × 8 s portrait Full HD ladder)
// - fixture: sfv-reference-implementation/fixtures/content/content.json (3 × 6 s smoke-test fixture)

export type ContentCatalogueId = "portrait_hd_90s" | "fixture";

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
  id: ContentCatalogueId;
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

export const CONTENT_CATALOGUES: Record<ContentCatalogueId, ContentCatalogueDefinition> = {
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
