# CISegWeVisOneVL

[Website and workflow guide](https://cellular-imaging-amsterdam-umc.github.io/ciseg-wevisonevl/) ·
[Public examples with actual masks](https://cellular-imaging-amsterdam-umc.github.io/ciseg-wevisonevl/examples.html) ·
[Markdown example gallery](docs/examples.md)

Text-prompted biological image segmentation using **WeVisOne-VL-4B**, with up to
**four independent prompts**. **3D images are automatically projected to 2D per
channel and timepoint: Max is the default; Mean is an advanced Bilayers option.**
Regular images, time series and HCS screens use the same workflow. The source
store remains untouched. Outputs contain 2D images or projections with native
label groups and one CSV for the complete run.

This is an inference adapter using existing foundation-model weights, not a newly
trained microscopy model. Accuracy varies across images and prompts. See the
[research and validation notes](docs/research.md).

## Local setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```powershell
git clone https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl.git
cd ciseg-wevisonevl
create_env.cmd
.venv\Scripts\python.exe tools\download_models.py
launch.cmd
```

The setup creates `.venv/` with Python 3.12, PyTorch 2.11/CUDA 12.6 and the pinned
Transformers backend. Python 3.12 is required by upstream SciPy 1.18.1. The validated
Windows environment is recorded in `requirements-lock.windows.txt`. vLLM, Gradio
and a separate Triton installation are not workflow requirements.

The pinned snapshot under `models/WeVisOne-VL-4B` is approximately 19.37 GB,
including the required `mask_decoder.pt` and licensing notices. Inference checks
the local inventory and stays offline. Another cache can be selected with
`--models-root` or `CISEGWEVISONEVL_MODELS`. This workflow uses 4B exclusively;
there is no model-selection menu.

## Launcher and CLI

For a local GUI with a parameter sidebar and one zoomable image/label viewer,
run **`launch_gui.cmd`** (or `gui\run.cmd`). Successful runs automatically display
the computed instance labels over the image. Existing outputs can be reopened,
with independent layer visibility, opacity, timepoint, HCS field and Z-section
controls. See [the GUI guide](gui/README.md). The original `launch.cmd` remains
available.

Choose a retained example or input directory, use **Check input**, then **Run
local Python**. Example selection fills suggested prompts and channels. Blank
prompts disable their slots. Fresh forms start with four blank prompts and
generic names `target1` through `target4`. Start with a reviewed example such
as `organoids_im10`. Extra parameters are initially collapsed under **Advanced
parameters**; the main form shows the four prompt/channel inputs and intensity
scaling of the model RGB view.

Each slot has an English description, a unique label name and a one-based channel
selection. `1` renders one grayscale channel as RGB; `1,2,3` maps channels to red,
green and blue. Each target sees one composed RGB view, without automatic inference
on separate channels. **Full data-type range (8-bit / 16-bit)** maps the source
range (0-255 or 0-65535) to the model's 8-bit RGB view without per-channel contrast
stretching. This supports 16-bit RGB as well as 8-bit RGB. **Use OME-Zarr metadata
display windows** (`--normalization metadata`) applies each selected channel's
saved `omero.channels[].window.start` and `window.end`. Missing, non-finite or
reversed windows fail input checks before loading the model; there is no silent
fallback. Percentile stretching remains available. Original intensities are
retained for measurements.

Label names are available in the basic form, next to each prompt and channel map.
The basic **Existing input labels** option keeps existing 2D label groups by
default, or removes them from the new result with **Remove existing labels from
result** (`--input-labels remove`). The input store is unchanged. Keep requires a
new label name if one already exists; Remove allows that name to be recomputed.
Existing labels in Z stacks are still omitted from projected 2D outputs rather
than projecting instance IDs. The CSV measures the newly predicted labels.

```powershell
.venv\Scripts\python.exe wrapper.py `
  --infolder publicdata\ome-zarr\human_mitosis.ome.zarr `
  --outfolder outputfolder\nuclei-test `
  --device cuda:0 `
  --prompt-1 "each bright fluorescent cell nucleus" --name-1 nuclei --channels-1 1 `
  --prompt-2 "bright round cell nuclei" --name-2 bright_nuclei --channels-2 1
```

The local GUI and launcher default to **Existing results: Replace after successful
run**, so a rerun can use the same output directory. New results are staged until
the complete run succeeds, then replace matching result stores and
`measurements.csv`. Failed runs retain the previous completed results. Use
**Keep existing results** to prevent replacement. The CLI keeps existing results
unless `--overwrite 1` is supplied. `--preflight-only` checks all fields without loading a model or
writing results.

## Projection and data contract

Inputs must be NGFF 0.4/Zarr v2 with explicit axes. Z>1 stacks are automatically
projected per channel and timepoint. `--projection Max` is the default;
`--projection Mean` writes the average as float32. Timepoints are never merged.
Existing 2D pixels are preserved even when Mean is selected.

Output uses OMERO-compatible TCZYX with Z=1. Projected Z carries no source-volume
physical plane position; XY/time calibration and origins remain intact. Existing
volume labels are omitted from the new projection output instead of numerically
projecting instance IDs. They remain in the original source store.

At most 16 megapixels are accepted per XY plane. Projection streams planes rather
than loading the full T/C/Z stack. Model views have a maximum side of 1024 pixels
by default, configurable from 128 to 2048. Masks return to native XY coordinates.
Automatic tiling with object fusion and tracking are not included.

## Label outputs

Each input produces `<source>__wevisonevl.ome.zarr`, preserving canonical 2D source
pixels/pyramids or writing a new projection pyramid for 3D input. Other supported
axis orders are normalized to TCZYX without changing full-resolution 2D values.
HCS structure and every timepoint are retained.

```text
labels/wevisone_<name>/0       uint32 labels at native XY coordinates
labels/wevisone_<name>/1,...   nearest-neighbor label pyramids
wevisone-run.json             prompts, provenance, counts and timings
wevisone_previews/            model inputs and overlays per timepoint
```

Prompt groups are independent and may overlap. Within one group, highest pixel
probability owns overlap; the first prediction wins ties. Instance mode retains
model-predicted IDs. `--label-mode semantic` merges a prompt into a binary mask.
The default probability threshold is 0.5.

Large foreground coverage gets a review note. Invalid coordinates or truncated
generation fail the run. Diagnostic `.partial-*` stores remain available and
are not published as completed results. Empty masks are not proof of absence.

## Basic measurements in one CSV

Every completed run writes **measurements.csv** in the output directory. One row
describes a label ID within its source, field, timepoint and prompt.

- Pixel area, centroid, bounding box with exclusive maximum and perimeter.
- Equivalent diameter, major/minor axes, eccentricity, solidity, extent and
  orientation in radians.
- Physical area in µm² and perimeter, diameters, axis lengths, centroid and
  bounding-box coordinates in µm when calibrated. Pixel columns remain available.
- Valid pixel count and min/max/mean/total intensity for every image channel,
  including channels not supplied to the model.

Intensities use original 2D pixels or the projection before model normalization.
NaN/Inf pixels are excluded and reflected in the valid count. Empty masks create
no object rows; empty runs still write headers. Semantic label 1 describes the
entire merged region for that prompt.

Physical coordinates include NGFF XY origins. X/Y spacings are applied
independently; shape axes and eccentricity use physical spacing instead of an
average pixel size. `shape_basis` records whether shape ratios/angles use physical
or pixel geometry. Isotropic perimeter scales the pixel estimator; anisotropic
perimeter uses scaled closed contours, recorded in `perimeter_um_method`.
Intensities retain their original units, ratios remain dimensionless and angles
remain radians. Physical columns are blank when calibration is unavailable.

The final CSV is published only after the whole run succeeds. Failed runs retain
`measurements.partial-*`. The Bilayers descriptor declares one measurement output
with CSV format under `/data/out`; this was checked with the installed BIOMERO
parser. A live attachment-import test remains for the later Docker/BIOMERO phase.

## Curated public examples and gallery

The original local collection had 27 examples, approximately 206 MB of OME-Zarr inputs:
EM organelles, histology, Ki67/DAB, adipocytes, skin, plant vascular bundles,
diatoms, embryos, dendritic spines, neurites and vessels. Original WSI files,
archives and downloaded EM chunks are retained separately. EM includes volumes
and explicit 2D sections because projections can superimpose ultrastructures.

The main gallery now retains **22 reviewed examples with 29 selected labels**,
after 89 candidate prompt comparisons and visual inspection. It excludes weak/empty
predictions and every EM Z projection. Original runs remain local, with an
image-free audits in [the original prompt study](docs/prompt-study.md) and
[the whole/part modality study](docs/imaging-modes.md). This positively
selected demonstration set is not a representative accuracy benchmark.

New native 2D CEM-MitoLab examples have paired references and selected foreground
Dice scores near 0.965 and 0.936. A recorded native Ki67 ROI distinguishes brown
positive nuclei from blue tissue. More concrete fluorescence descriptions retain
the vessel profile, green plant bundles and a white filament network. The site
provides real overlays, prompts, source attribution, NPZ labels, reference
overlays when available and calibrated CSV measurements.

The modality follow-up adds phase-contrast Paramecium, chloroplast TEM,
endothelial fluorescence, a native kidney section and insulin IHC. The gallery
can be filtered by imaging mode. Whole organisms/cell bodies and selected
interior structures have separate labels. New IHC examples show islet outlines
or brown tissue regions; they do not establish reliable positive-cell separation.

```powershell
.venv\Scripts\python.exe tools\prepare_publicdata.py --organoids
.venv\Scripts\python.exe tools\run_gallery_inference.py
.venv\Scripts\python.exe -m pytest -q
```

Additional curation uses `requirements_publicdata.txt`,
`tools/curate_extra_publicdata.py` and `tools/curate_remote_examples.py`. Some
examples originate in the original local PublicData collection. Exact copies,
checksums, selections, resolutions and licenses are recorded. Basic preparation
preserves additional catalog entries.

The reviewed selection is tracked in `gallery_selection.json`; the launcher uses
it to keep exploratory/archived inputs out of its example selector. The study
and curation tools preserve all original images and unselected experiments.
Regenerating curated results requires the retained inputs/comparison records;
the committed site can be viewed without downloading any models or source stores.

## Large-image research

[The tile study](docs/tiling.md) compares 512/128, 768/192 and 1024/256 windows
and nominal overlaps against 87 consensus organoid instances. The 768/192
prototype scored foreground Dice 0.917 and instance F1 0.939, versus 0.881 and
0.906 for the earlier whole-image run. This is one controlled example, not a
universal tile-size optimum. Edge alignment increases actual overlap.

The prototype fuses unambiguous instance IDs across overlaps and flags ambiguous
matches. Production gigapixel support is **not enabled**: input/projection,
label storage, pyramids and measurements still need bounded streaming. The
16-megapixel production guard remains. Proposed advanced user controls are
documented; no unsupported production tiling option has been added to the launcher.

## Documentation and publication

GitHub Pages serves the committed `docs/` directory, including HTML and Markdown
guides. Dark is the default; a Bright/Dark toggle remembers explicit selections.

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements_docs.txt
.venv\Scripts\python.exe tools\build_docs_site.py
.venv\Scripts\python.exe tools\check_site.py docs
```

The Pages workflow validates and publishes static files. It does not download
models or run inference. `.venv/`, full models, source stores, raw results and
working files are excluded from Git. Public assets contain small derived previews
and mask results only.

The display name is **CISegWeVisOneVL**; use `cisegwevisonevl` as a BIOMERO key.
`Dockerfile.models` prepares a separate internal cache; `Dockerfile` prepares a
headless image. No new image has been built, published or deployed. See
[NOTICE.md](NOTICE.md) for component and data attribution.
