import {
  CONTENT_CATALOGUES,
  CONTENT_ENCODERS,
  CONTENT_SEGMENT_DURATIONS_S,
  PER_TITLE_VIDEOS,
  perTitleCatalogueAxisName,
  perTitleCataloguePathFromConfigsChild,
  type ContentEncoder,
  type ContentSegmentDurationS,
} from "@/data/contentCatalogue";
import type { ExplorerSettings } from "@/model/explorerSettings";

// The content catalogue of a run, and the content_catalogues axis of a grid. Keep the axis in sync with
// capcsp/runner/grid_specification.py and configs/grids/aomctc-encoding-conditions.json.

export function usesPerTitleContent(settings: ExplorerSettings): boolean {
  return settings.contentId === "aomctc_per_title";
}

export function selectedContentVideoCount(settings: ExplorerSettings): number {
  return usesPerTitleContent(settings) ? PER_TITLE_VIDEOS.length : CONTENT_CATALOGUES[settings.contentId as keyof typeof CONTENT_CATALOGUES].videoCount;
}

/** `content` of the run or the grid base, relative to a config saved directly under configs/experiments/ or configs/grids/. */
export function selectedContentPath(settings: ExplorerSettings): string {
  if (usesPerTitleContent(settings)) {
    const { encoder, segmentDurationS } = shownPerTitleCatalogue(settings);
    return perTitleCataloguePathFromConfigsChild(encoder, segmentDurationS);
  }
  return CONTENT_CATALOGUES[settings.contentId as keyof typeof CONTENT_CATALOGUES].pathFromConfigsChild;
}

/** Encoders and segment durations swept by a grid, with empty selections replaced by the run's value. */
export function effectiveContentAxes(settings: ExplorerSettings): { encoders: ContentEncoder[]; segmentDurationsS: ContentSegmentDurationS[] } {
  const axes = settings.gridAxes;
  return {
    encoders: CONTENT_ENCODERS.filter((encoder) => axes.contentEncoders.includes(encoder)).length
      ? CONTENT_ENCODERS.filter((encoder) => axes.contentEncoders.includes(encoder))
      : [settings.contentEncoder],
    segmentDurationsS: CONTENT_SEGMENT_DURATIONS_S.filter((duration) => axes.contentSegmentDurationsS.includes(duration)).length
      ? CONTENT_SEGMENT_DURATIONS_S.filter((duration) => axes.contentSegmentDurationsS.includes(duration))
      : [settings.contentSegmentDurationS],
  };
}

/**
 * The per-title catalogue of the run, or in Grid mode of the cell in the diagram and the grid base: the run's
 * encoder and segment duration if the grid sweeps them, otherwise the first swept ones. A grid with a single
 * selected catalogue has no content_catalogues axis, so its base must hold that catalogue.
 */
export function shownPerTitleCatalogue(settings: ExplorerSettings): { encoder: ContentEncoder; segmentDurationS: ContentSegmentDurationS } {
  if (settings.configOutputKind !== "grid") return { encoder: settings.contentEncoder, segmentDurationS: settings.contentSegmentDurationS };
  const { encoders, segmentDurationsS } = effectiveContentAxes(settings);
  return {
    encoder: encoders.includes(settings.contentEncoder) ? settings.contentEncoder : encoders[0],
    segmentDurationS: segmentDurationsS.includes(settings.contentSegmentDurationS) ? settings.contentSegmentDurationS : segmentDurationsS[0],
  };
}

/** The grid's content_catalogues axis, or an empty list when every cell uses the content of the base. */
export function gridContentCatalogues(settings: ExplorerSettings): { name: string; path: string }[] {
  if (!usesPerTitleContent(settings)) return [];
  const { encoders, segmentDurationsS } = effectiveContentAxes(settings);
  if (encoders.length * segmentDurationsS.length < 2) return [];
  return encoders.flatMap((encoder) =>
    segmentDurationsS.map((segmentDurationS) => ({
      name: perTitleCatalogueAxisName(encoder, segmentDurationS),
      path: perTitleCataloguePathFromConfigsChild(encoder, segmentDurationS),
    })),
  );
}
