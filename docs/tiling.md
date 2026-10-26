# Large scans: tile by tile

## Availability

The development Python workflow supports explicit tiled processing through the
GUI, launcher and CLI. The published v0.1.0 container retains its original
whole-image implementation; use its tagged descriptor with that image. The
development descriptor's `dev` image is a local build target, not a published
release. No new image or live BIOMERO configuration is implied by these changes.

## Controls

Open **Advanced parameters → Image processing → Tile by tile (large scans)**.

| Control | Default | Meaning |
| --- | --- | --- |
| Processing mode | Whole image | Explicit Tiled is required above 16 megapixels |
| Source tile side | 2048 native pixels | Full window including shared context; maximum 4096 |
| Overlap | 256 native pixels | Nominal stride 1792; must be less than half the tile side |
| Maximum model input side | 1024 pixels | Each source tile is downsampled to this model-view bound; maximum 2048 |
| Seam match IoU | 0.5 | Intersection/union in shared, already processed pixels |
| Skip blank RGB tiles | Disabled | Optional histology heuristic, described below |

Example in PowerShell:

```powershell
.venv\Scripts\python.exe wrapper.py `
  --infolder inputfolder\scan.ome.zarr --outfolder outputfolder\scan `
  --processing-mode tiled --tile-size 2048 --tile-overlap 256 `
  --max-side 2048 --normalization dtype --device cuda:0 `
  --prompt-1 "all separate tissue fragments, excluding the empty glass background" `
  --name-1 tissue --channels-1 1,2,3 `
  --prompt-2 "DAB staining" --name-2 DAB_staining --channels-2 1,2,3
```

These are example queries, not validated annotations. The DAB test missed visible
brown staining with an earlier query; prompt choice must be reviewed. Prompt
groups remain independent and may overlap. Each timepoint and HCS field has its
own grid and object identities. Existing input-label keep/remove and staged
overwrite behavior also apply in tiled mode.

## Memory, IO and contrast

Source reads and Z reductions use bounded XY regions. Noncanonical axes and Z
projections are rewritten in blocks; source stores remain untouched. Canonical
2D sources are copied without changing pixels. Provisional uint32 labels and
tile ownership live in Zarr on disk, with SQLite object equivalences. Final IDs,
label pyramids and measurement aggregates are streamed in bounded passes.
Source chunks larger than 256 MiB are rejected; rechunk those inputs first.

Percentile limits are computed once per prompt/timepoint from a bounded existing
overview, or deterministic native sampling when no overview is available. The
same recorded limits apply to every tile. They can differ from exact full-image
percentiles. Dtype and metadata scaling retain their normal meaning and original
measurement intensities. Model memory is controlled by the separate model-view
limit, decoder batch, tokens and object count, not by source tile size alone. A 4096-pixel source tile viewed
at 2048 pixels approached the workstation GPU's total capacity during the large
histology trial; it was stopped and retained for diagnostics. The default is now
2048-pixel source tiles with a 1024-pixel model view.

**GPU memory between calls** defaults to releasing unused CUDA cache after every
prediction, including failures. CPU result masks are retained; model weights stay
loaded. Tile traces distinguish allocated tensor bytes from reserved allocator
bytes before prediction, after prediction and after cleanup. Reusing the cache
is an advanced speed option for a dedicated GPU. Releasing cache cannot free
live model tensors and does not reduce the peak during an individual prediction.

Allow disk space for a source copy, each prompt's uint32 pyramid and temporary
uint32 IDs/uint16 ownership arrays plus SQLite files. Failed partial runs retain
their diagnostics and can consume additional disk space. There is no automatic
resume of a failed grid. The source image and earlier completed outputs remain
unchanged if a new run fails.

## Seams, IDs and review

Final windows are anchored to the image boundary, so actual overlap can exceed
the nominal value. Tiles run in row-major order. Predicted instances match only
if their overlap IoU reaches the threshold and they share at least eight pixels.
Only reciprocal one-to-one candidates merge; ambiguous splits/merges stay
separate and are counted. An iterative disk-backed union map carries identities
across multiple neighbors and four-tile junctions.

Within a model tile, highest probability owns a pixel and the first prediction
wins ties. Between tiles, the context farthest from a tile edge owns each pixel;
earlier tiles win equal-distance ties. This ownership includes background and is
not probability blending. Minimum area is applied after seam resolution to
complete objects. Semantic mode produces one binary class per prompt.

Tile traces (`wevisone_previews/*_tiles.jsonl`) retain bounds, model-view sizes,
responses, boxes, timings and skip reasons. The run report retains seam counts,
normalization limits and the active tile on failure. Invalid or truncated model
responses fail the run; they are not silently converted into background.

**Local context changes predictions.** A tile without the requested anatomy can
still produce false positives. Initial human-esophagus trials detected some
surface epithelium but also mislabeled muscle/background. Zero ambiguous seam
matches does not establish biological accuracy. A cancer-related prompt is a
model proposal, not a diagnosis or a validated tumor annotation. Inspect the
whole overlay and representative native regions before using measurements.

The optional blank-tile heuristic skips a tile when at most 0.1% of its scaled
RGB pixels fall outside near-white (all components at least 220) or near-black
(all at most 15). It is recorded per tile and can miss faint tissue. It is not
a general-purpose tissue detector and is disabled by default.

## Streamed measurements and viewer

Tiled CSV rows contain exact pixel counts, bounding boxes, centroids, coordinate
moments, covariance-based axes/eccentricity/orientation, equivalent diameters and
per-channel valid counts, min/max/mean/total. Ordered calibration transforms,
anisotropic spacing and origins are preserved. Intensities use original pixels
or the selected Z projection, including channels excluded from the model view.

Perimeter counts exposed pixel edges, including holes and image boundaries. Each
horizontal edge uses X spacing and each vertical edge uses Y spacing. This differs
from the whole-image estimator and is explicitly marked `streamed_pixel_edges`.
Solidity is blank; no giant convex-hull mask is allocated. `measurement_method`
records these distinctions. Missing calibration leaves physical columns blank.

The GUI opens existing overviews before reading large images/labels and reports
native pixels per display pixel. Hover coordinates map to native pixels. Visible
instance counts can exclude objects too small for the overview; 1:1 shows display
pixels and does not load native detail on zoom. Stored labels remain native-sized.

## Earlier organoid experiment

The original in-memory research prototype remains in `tools/experimental_tiling.py`
and keeps its own 16-megapixel guard. On one native 1408 × 1040 organoid image,
87 independent microSAM consensus instances were used for comparison:

| Method | Tile/overlap | Tiles | Foreground Dice | Instance F1 at IoU >= 0.5 | Predicted instances |
| --- | --- | --- | --- | --- | --- |
| Earlier whole image | View side 1024 | 1 | 0.881 | 0.906 | 83 |
| Prototype | 512/128 | 12 | 0.876 | 0.888 | 91 |
| Prototype | 768/192 | 6 | 0.917 | 0.939 | 92 |
| Prototype | 1024/256 | 4 | 0.911 | 0.926 | 88 |

These results do not establish a universal tile size or accuracy on histological
scans. The 2048/256 default is a large-scan starting point, not an accuracy optimum.

Sources: [official WeVisOne-VL implementation](https://github.com/Tencent/WeVisOne-VL),
[independent microSAM organoid data](https://zenodo.org/records/14036957).
