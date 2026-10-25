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

Choose a retained example or input directory, use **Check input**, then **Run
local Python**. Example selection fills suggested prompts and channels. Blank
prompts disable their slots. Start with `cell` or `organoids_im10`.

Each slot has an English description, a unique label name and a one-based channel
selection. `1` renders one grayscale channel as RGB; `1,2,3` maps channels to red,
green and blue. Use **Original uint8 RGB** for histology or percentile contrast for
a fluorescence model view. Original intensities are retained for measurements.

```powershell
.venv\Scripts\python.exe wrapper.py `
  --infolder publicdata\ome-zarr\human_mitosis.ome.zarr `
  --outfolder outputfolder\nuclei-test `
  --device cuda:0 `
  --prompt-1 "each bright fluorescent cell nucleus" --name-1 nuclei --channels-1 1 `
  --prompt-2 "bright round cell nuclei" --name-2 bright_nuclei --channels-2 1
```

Use a new output directory for each run. Completed results and CSVs are never
overwritten. `--preflight-only` checks all fields without loading a model or
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
- Physical area in µm² only with positive NGFF XY calibration in known units.
- Valid pixel count and min/max/mean/total intensity for every image channel,
  including channels not supplied to the model.

Intensities use original 2D pixels or the projection before model normalization.
NaN/Inf pixels are excluded and reflected in the valid count. Empty masks create
no object rows; empty runs still write headers. Semantic label 1 describes the
entire merged region for that prompt.

The final CSV is published only after the whole run succeeds. Failed runs retain
`measurements.partial-*`. The Bilayers descriptor declares one measurement output
with CSV format under `/data/out`; this was checked with the installed BIOMERO
parser. A live attachment-import test remains for the later Docker/BIOMERO phase.

## Public examples and gallery

The local collection has 27 examples, approximately 206 MB of OME-Zarr inputs:
EM organelles, histology, Ki67/DAB, adipocytes, skin, plant vascular bundles,
diatoms, embryos, dendritic spines, neurites and vessels. Original WSI files,
archives and downloaded EM chunks are retained separately. EM includes volumes
and explicit 2D sections because projections can superimpose ultrastructures.

The published gallery contains new 4B predictions for every example/prompt:
**63 label runs completed and 1 was rejected**. Nine completed label runs have
empty first-frame masks. Execution success is not biological validation. The
site provides real overlays, prompts, coverage, source attribution, NPZ labels
with time indices and CSV measurements.

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
