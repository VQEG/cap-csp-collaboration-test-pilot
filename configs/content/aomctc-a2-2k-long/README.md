# Per-Title Ladder Catalogues (AOM CTC a2_2k, Long Clips)

These catalogues replace synthetic bitrates with per-title ladders from real encodes. Samuel Hufen (Uni Augsburg) encoded the 17 long clips of the [AOM CTC a2_2k test set](https://media.xiph.org/video/aomctc/test_set_long/a2_2k/) (5–19 s, 25–60 fps, 14 landscape and 3 portrait clips) with five encoders, six resolutions (270p–1080p) and 13 CRF values each, at segment durations of 1, 2, 4 and 5 s with the keyframe interval set to the segment duration. He analysed the results and presented them to the group on 24 November 2026 ("Per-Title Bitrate Ladders and Segment Length"). The method follows feedback from Werner Robitza (AVEQ) on Samuel's first encodes: a resolution × CRF grid per clip, the convex hull per clip and codec, and VMAF targets instead of fixed CRF levels. The encodes reuse the FFmpeg build, encoder versions and commands of Werner's [aomctc-dynamic-optimizer](https://github.com/slhck/aomctc-dynamic-optimizer).

For each clip, encoder and segment duration, the convex hull of VMAF v1 over bitrate (all resolutions in one pool) gives one ladder rung per VMAF target 90, 80, 70, 60 and 50: the cheapest real encode on the hull that reaches the target. The catalogues use the VMAF v1.0.16 5H model (`vmaf_5h`), as the talk did. The source data also has VMAF 95 encodes, but after the 24 November call (Emir: VMAF 90 is enough as the top of the ladder) the specification leaves this target out.

## Files

The directory holds the source data, the specification and the generated catalogues:

- `per-title-ladder-encodes.csv`: one row per clip, encoder, segment duration, metric (`vmaf_3h`, `vmaf_5h`) and VMAF target, with the selected encode (resolution, CRF, keyframe interval, frame rate, duration, total bytes, bitrate, VMAF). It joins `ladder_per_title.csv` with `all_encodes.csv` of Samuel's analysis (`analysis_seg1s/`, `analysis/`, `analysis_seg4s/`, `analysis_seg5s/`). Targets that no encode reaches have the status `unreachable`.
- `catalogue-specification.json`: quality metric, VMAF targets, encoders and their RFC 6381 codec strings, segment durations, feed order, seed, segment size spread and the shortest last segment that is kept
- `<encoder>-segment-<n>s.json`: one catalogue in the SFV `content.json` format per encoder (`x264`, `x265`, `vp9`, `libaom`, `svtav1`) and segment duration (1, 2, 4 and 5 s), 20 in total

Regenerate the catalogues with:

```bash
uv run capcsp generate-content configs/content/aomctc-a2-2k-long/catalogue-specification.json
```

A test checks that the committed catalogues match the specification and that the segment sizes of every representation add up to the measured encode size (minus the share of a dropped last segment, see below).

## How the Catalogues Are Built

Each catalogue holds the same 17 videos in the same feed order (161 s in total). Portrait and landscape clips alternate with talking-head, sports and nature content. Each video keeps its source frame rate and, nearly always, its source duration, so the last segment of a video is usually shorter than the others. Some clips run a frame or two past a multiple of the segment duration (for example 5.005 s or 5.033 s). Such a last segment of 5–33 ms would be an extra request for almost no media, so the generator drops last segments shorter than 50 ms (`drop_last_segment_shorter_than_s`) and cuts the video short by that much. Each representation then loses the bytes of the dropped part at its mean bitrate. This affects 9 videos with 1 s segments, 3 with 2 s, none with 4 s and 8 with 5 s.

The ladder of a video has one rung per reachable VMAF target, in increasing bitrate. If two targets select the same encode (this happens when one CRF step jumps over a target), they become one rung. Most videos therefore have five rungs, a few have four. Each representation records its `targetVmaf`, the measured `vmaf` and the `crf` next to the SFV fields, and each video its `sourceClip`. The top-level `encodingCondition` names the encoder, codec string, segment duration and quality metric.

The encodes give only the total size of each representation, not the size of each segment. The generator therefore spreads the measured total over the segments with a seeded scene factor per segment (log-normal, mean 1, coefficient of variation 0.3). The scene factors depend only on the clip and the segment duration, so all encoders of a clip see the same pattern, and paired runs differ only in the encoding. The keyframe cost of shorter segments is part of the measured totals.

Median rung bitrates over the 17 videos in kbps (lowest and highest rung):

| Encoder | 1 s | 2 s | 4 s | 5 s |
|---|---|---|---|---|
| x264 | 642–3743 | 569–3460 | 537–3384 | 502–3375 |
| x265 | 421–2611 | 394–2961 | 382–2932 | 372–2938 |
| VP9 | 497–3266 | 455–3657 | 483–3556 | 444–3548 |
| libaom (AV1) | 264–1972 | 243–1880 | 244–1836 | 226–1837 |
| SVT-AV1 | 242–1640 | 236–1572 | 207–1535 | 199–1528 |

These are bitrates of real encodes, so they are a little higher than the hull bitrates interpolated at the exact targets in Samuel's talk (for example 443 kbps for x264 at VMAF 50 with 2 s segments). In his BD-rate analysis, 1 s segments cost 3–10 % more than 2 s segments and 4 s segments save 2–4 %, with the largest cost for AV1.

## Open Points

- Segment sizes are synthetic within a representation. Real per-segment sizes (for example from `ffprobe` packet sizes of Samuel's encodes) would replace the scene factors without changing the format.
- The sources are mostly landscape, while the pilot scores for a portrait Full HD phone. P.1204.1 Mode 0 only uses the pixel count, frame rate and bitrate, so orientation does not change the scores.
- Encodes use the source frame rate (25–60 fps). Short-form apps often deliver 30 fps.
- The feed is 161 s long. A 65 s run with 2–16 s between swipes plays about 7 videos, so the feed does not run out, but sessions longer than about 2 minutes would need more content.
- Audio is listed (64 kbps AAC) but not requested by the player yet.
