# The workflow

CISegWeVisOneVL segments OME-Zarr images with WeVisOne-VL-4B and up to four
independent text prompts. It uses existing weights. The [gallery](examples.html)
shows actual predictions, including failures.

## Getting started

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/), then
run these commands on Windows:

```powershell
git clone https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl.git
cd ciseg-wevisonevl
create_env.cmd
.venv\Scripts\python tools\download_models.py
launch.cmd
```

The environment uses Python 3.12, PyTorch 2.11/CUDA 12.6 and Transformers 5.12.1.
The pinned 4B snapshot takes approximately 19.37 GB, including the pixel decoder.
Inference uses only the local cache. GPU runs were tested on an RTX A5000 with
24 GB VRAM; CPU execution is also available.

Select an example or input directory, use **Check input**, then **Run local
Python**. Blank prompts disable their slots. Completed results are never
overwritten: choose a new output directory for each run.

## Images and channels

- Input: NGFF 0.4/Zarr v2 with explicit axes.
- Regular images, time series and all HCS screen fields are processed.
- `1` supplies a single channel as a grayscale RGB view.
- `1,2,3` maps three channels to red, green and blue.
- **Original uint8 RGB** retains histology colors.
- Percentile contrast changes only the model view. Measurements use original
  2D pixels or the projection before normalization.

Each XY plane is limited to 16 megapixels. The model view has a maximum side of
1024 pixels by default, configurable from 128 to 2048. Masks return to native XY
coordinates. Automatic tiling with object fusion is not implemented.

## Automatic 3D projection

Z stacks are automatically projected for **each channel and timepoint**. The
advanced Bilayers option provides:

| Option | Operation over Z | Output pixel type |
| --- | --- | --- |
| **Max** — default | Highest value at each pixel | Original dtype |
| **Mean** | Average value at each pixel | float32 |

Timepoints are never merged. Existing 2D inputs keep their values. Output uses
TCZYX with Z=1 for OMERO compatibility; source volumes remain untouched. XY/time
calibration is retained. Input volume label IDs are not projected numerically.

EM projections can superimpose membranes and organelles. The gallery therefore
also contains explicit 2D sections from the EM volumes.

## Four independent labels

Each slot has a unique label name, English description and channel selection.
Examples include `tissue`, `vessels`, `mitochondria` and `dab_positive`. Prompt
groups may overlap, such as vessels inside a tissue region.

**Instances** retains one ID per predicted object. Highest pixel probability owns
overlap within a prompt; the first prediction wins ties. **Semantic** merges a
prompt into a binary mask. The default probability threshold is 0.5.

Empty predictions are not proof of absence. Invalid object coordinates or
truncated generation are rejected and retained for diagnosis. The adapter never
invents coordinates or silently decodes misaligned objects.

## Command line

```powershell
.venv\Scripts\python wrapper.py `
  --infolder publicdata\ome-zarr\public-ki67-lymphoma-dab-roi.ome.zarr `
  --outfolder outputfolder\ki67-test `
  --prompt-1 "brown DAB-positive tissue" --name-1 dab_positive --channels-1 1,2,3 `
  --prompt-2 "the entire tissue section" --name-2 tissue --channels-2 1,2,3 `
  --normalization dtype --projection Max --device cuda:0
```

`--preflight-only` checks all field metadata without loading a model or writing
results. `config.yaml` is the Bilayers descriptor for the same parameters.

## Outputs and measurements

Each input creates `<source>__wevisonevl.ome.zarr`, with native groups under
`labels/wevisone_<name>/`. Label pyramids use nearest-neighbor reduction;
projection pyramids use area averaging. Run reports retain prompts, channels,
contrast limits, model revisions, coordinates, counts and timings.

One **measurements.csv** covers every image, field, timepoint and prompt in the
run. Each row describes one label ID.

| Group | Fields |
| --- | --- |
| Identification | Source, output, field, well, timepoint, prompt and label ID |
| Area and position | Pixel area, centroid, bounding box with exclusive maximum |
| Shape | Perimeter, equivalent diameter, major/minor axes, eccentricity, solidity, extent and orientation |
| Physical area | µm² only with positive NGFF XY calibration and known units |
| Every image channel | Valid pixel count, minimum, maximum, mean and total intensity |

Channels outside the model input are measured too. For 3D input, measurements use
the projection before normalization. NaN/Inf pixels are excluded and reflected in
the valid count. Empty runs write headers. Failed runs retain `measurements.partial-*`
instead of a completed CSV. Semantic label 1 describes the full merged region.

## Bilayers and BIOMERO

The display name is **CISegWeVisOneVL**; the configuration key can be
`cisegwevisonevl`. The CSV is declared as one measurement output with CSV format;
the installed BIOMERO parser was tested with this declaration.

Headless workflow and internal model-cache Docker recipes are prepared. No new
image has been built or installed in Slurm/BIOMERO. A live attachment-import
test remains part of that later validation phase.

## Reproducing the examples

```powershell
.venv\Scripts\python tools\prepare_publicdata.py --organoids
.venv\Scripts\python tools\run_gallery_inference.py
.venv\Scripts\python -m pytest -q
```

Additional examples use `requirements_publicdata.txt` and curation scripts.
Some originate from the original local PublicData collection. The gallery records
known URLs, selections, resolutions and licenses. Full source stores and models
are excluded from Git. Downloaded gallery labels are model-derived results,
not manual ground truth. NPZ files contain uint32 `labels`, `time_indices` and
the axis string `tczyx`; previews show the first timepoint.
