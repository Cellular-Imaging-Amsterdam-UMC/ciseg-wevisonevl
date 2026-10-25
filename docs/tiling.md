# Large images and object fusion

## Research result and current implementation status

**Yes: tile-by-tile VLM inference is possible, and the prototype fuses instance
IDs across tile overlaps. It is not yet production support for arbitrarily large
tilescans.** The production workflow still enforces the 16-megapixel XY limit.
The research stitcher also enforces this limit rather than allocating an
unbounded whole-image array.

A tile loop alone is insufficient: the current source/projection reader,
instance canvas and region-property measurements can still materialize complete
planes. Those stages must become bounded before enabling gigapixel processing.
The prototype and its tests are in `tools/experimental_tiling.py`; the controlled
GPU experiment is in `tools/benchmark_tiling.py`.

For scale, the retained native CMU-1 scan is approximately 46000 × 32914 pixels.
A 768/192 grid would require about **4560 model calls** before tissue gating.
Even a hypothetical 2 seconds per tile would exceed 2.5 hours; 20 seconds would
exceed 25 hours, excluding IO and measurements. Cost depends strongly on generated
object tokens. This illustrates the need for an overview/ROI stage and explicit
user choice; it is not a runtime prediction for that slide.

## Measured tile-size comparison

The native 1408 × 1040 organoid example was compared against its independent
microSAM consensus instance annotations: **87 reference instances**. Model
weights, query (`organoids`), threshold (0.5) and the same full-field contrast
transform were held fixed. Tile runs used deterministic decoding with a 4096
token budget and sequential inference on the local RTX A5000.

| Method | Full tile size | Nominal overlap | Tiles | Foreground Dice | Instance F1 at IoU ≥ 0.5 | Matched / predicted instances | Inference + fusion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Existing whole-image run | View reduced to maximum side 1024 | — | 1 | 0.881 | 0.906 | 77 / 83 | Approximately 45 s in the earlier run |
| Tiled prototype | 512 | 128 | 12 | 0.876 | 0.888 | 79 / 91 | 108.9 s |
| Tiled prototype | **768** | **192** | 6 | **0.917** | **0.939** | **84 / 92** | **130.3 s** |
| Tiled prototype | 1024 | 256 | 4 | 0.911 | 0.926 | 81 / 88 | 155.0 s |

The 768/192 configuration was the best of these three settings on this image,
both for foreground and instance F1. This is a **starting point, not a universal
optimum**. The whole-image timing comes from an earlier run and is not a
controlled runtime comparison. Object size, image scale, density and prompt
context can change the best setting.

The final windows are aligned to the image boundary, so **actual edge overlaps
can exceed the nominal value**. Ranges were 128–384, 192–704 and 640–1008 pixels
respectively. The example is only slightly taller than 1024, producing substantial
duplicate context in that configuration. This experiment does not identify an
independently optimal overlap percentage for a very wide tilescan.

## Recommended controls

A user option is necessary: local tiles change context, especially for prompts
such as “the entire section”, “leftmost object” or “the largest structure”.
Those referring expressions are not invariant when each tile becomes a new image.

The proposed advanced interface is:

| Control | Proposed starting value | Meaning |
| --- | --- | --- |
| Processing mode | Whole image initially; explicit experimental Tiled | Preserve existing behavior until all streaming stages are validated |
| Tile size | 768 px | **Full inference window**, including context |
| Tile overlap | 192 px | Shared width between adjacent windows; nominal stride 576 px |
| Instance match threshold | 0.5 | IoU measured only within valid shared pixels |
| Minimum shared foreground | 8 px in this experiment | Avoid matching instances on accidental tiny contacts; tune for small objects |

1024 px is a reasonable alternative when objects need more context. Overlap
must contain enough of an expected object for matching; very large structures
may require an overview-guided semantic workflow instead of instance fusion.
A future Auto mode should use tested memory/context rules, not merely bypass
the existing size guard. These are **design recommendations**; the advanced
production controls have not been added to the launcher or descriptor yet.

The tile-size convention differs from cisegmentation, whose documented default
is a 1024-pixel **core** plus 96 pixels of halo per side. That creates a larger
inference window; copying the number without its convention would be misleading.
WeVisOne-VL also has its own visual-token budget and 1024-pixel decoder canvas.

## Instance matching and seam ownership

The experimental implementation:

1. Assigns fresh IDs to each tile's predicted instances.
2. Compares only their actual shared image pixels, not full-object IoU outside
   the overlap and not bounding-box contact alone.
3. Accepts an unambiguous one-to-one match above the overlap threshold, with
   a minimum shared area. Ambiguous one-to-many/many-to-one candidates are flagged.
4. Uses a union-find map so an instance can retain one final ID across several
   neighbors and four-tile junctions.
5. Assigns overlap pixels to the prediction with more distance from its tile edge.
   This is deterministic center ownership, not probability averaging.

Tests cover odd image edges, one object crossing four tiles, adjacent touching
objects that must stay separate, ambiguous splits and the memory-allocation guard.
The real experiment matched 103, 150 and 201 overlap pairs without an ambiguity
flag for those particular outputs. Zero flags is not proof that every match is correct;
the independent instance comparison is the stronger check.

For a semantic class such as all tissue, weighted probability blending followed
by one global threshold is a useful separate design. It does not provide instance
identities and should not be presented as instance fusion. A seam cannot repair
an object that neither tile recognized or distinguish unrelated objects when
the underlying predictions are wrong.

## Requirements before production tilescan support

- **Bounded input and projection:** read OME-Zarr chunks/regions and perform
  Z reduction per tile and timepoint. Do not load a complete giant plane first.
- **Stable contrast:** reuse recorded per-channel full-field limits, computed
  with bounded integer histograms or documented deterministic float sampling.
  Independent tile normalization can create biological/contrast seams.
- **Disk-backed labels:** store provisional IDs in Zarr, maintain small overlap
  state and a union table, then remap final IDs in a bounded pass.
- **Bounded measurements:** aggregate area, centroids, moments and intensities
  per chunk. Perimeter needs neighbor halos; convex-hull features need a bounded
  algorithm. One image-sized `regionprops` call would defeat tiled inference.
- **Bounded pyramids and provenance:** build pyramids in chunks, preserve
  calibration/translations and record grid, overlap, matching and unresolved seams.
- **Validation at scale:** test genuine large tissue scans, edge-touching objects,
  different object sizes and calibration, missing chunks and failed-tile recovery.

For a whole histological section, a useful future pattern is to identify tissue
at an existing low-resolution overview and process relevant native-resolution
regions next. The overview selection and its uncertainty must remain explicit.

## Sources and reproduction

```powershell
.venv\Scripts\python tools\benchmark_tiling.py
.venv\Scripts\python tools\evaluate_tile_instances.py
.venv\Scripts\python -m pytest tests\test_experimental_tiling.py -q
```

- [Official WeVisOne-VL pixel-level cookbook](https://github.com/Tencent/WeVisOne-VL/blob/main/tutorials/03_segmentation_matting_pipeline.ipynb)
- [Official model implementation and decoder](https://github.com/Tencent/WeVisOne-VL)
- [cisegmentation large-input conventions](https://github.com/Cellular-Imaging-Amsterdam-UMC/cisegmentation/blob/main/docs/large-inputs.md)
- [Cellpose API and its separate tile conventions](https://cellpose.readthedocs.io/en/latest/api.html)
- [Independent microSAM organoid data](https://zenodo.org/records/14036957)
