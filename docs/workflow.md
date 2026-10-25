# The workflow

CISegWeVisOneVL segments OME-Zarr images with WeVisOne-VL-4B and up to four
independent text prompts. It uses existing weights. The [gallery](examples.html)
shows reviewed actual predictions; the research reports document rejected candidates.

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
Python**. Blank prompts disable their slots. The local GUI and launcher default to
**Existing results: Replace after successful run** under Advanced parameters.
Reruns may reuse the output directory: matching result stores and
`measurements.csv` are replaced only after the whole new run succeeds. Failed runs
keep the previous completed results. Input images and unrelated files are
preserved. Select **Keep existing results** to retain the previous protection.
The CLI requires `--overwrite 1` to enable replacement. **Check input** never
changes existing results.

All four prompts start blank, with generic output names `target1` through
`target4`. The main form contains the four prompt, label-name and channel inputs,
**Existing input labels**, and **Model RGB view - intensity scaling**.
Z projection, mask output, probability
threshold, image size, token limit, area filter and device are under **Advanced
parameters**, collapsed initially in the local launcher. Expanding the panel
does not change parameter values.

**Existing input labels** defaults to **Keep existing labels**: label groups from
2D inputs are copied to the result alongside new predictions. **Remove existing
labels from result** omits the input label groups when preparing the new output;
it never deletes labels from the original input store. The same choice is
available with `--input-labels keep` or `--input-labels remove`. Keep requires
unique new label names; Remove allows an existing name to be recomputed. The
choice applies to every HCS field and timepoint. For Z-stack projections, existing
volume labels stay in the source and are omitted from the 2D output; instance IDs
are never numerically projected. The measurements CSV describes new predictions.

Saved local settings are restored on reopening the launcher. Choosing an example
fills its reviewed prompts and channel map; this does not change the blank
descriptor defaults.

## Images and channels

The local single-viewer GUI is available through `launch_gui.cmd` or
`gui\run.cmd`. Parameters stay on the left, and completed labels open as overlays
in the same image viewer. Existing results can be opened with **Open results…**;
the layer list and opacity slider control independent prompt overlays. Timepoint,
HCS field, projected view and native Z-section controls are available. The original
launcher remains available through `launch.cmd`.

- Input: NGFF 0.4/Zarr v2 with explicit axes.
- Regular images, time series and all HCS screen fields are processed.
- Each active target is inferred once on **one composed RGB view** per timepoint
  and field. It does not infer every channel separately.
- `1` selects source channel 1 and copies it to R, G and B, producing grayscale.
- `1,2,3` maps source channels 1, 2 and 3 to R, G and B in that order. `4,2,1`
  is also valid. No other channels are automatically mixed into this view.
- **Stretch each selected channel (1-99.8 percentile)** scales each selected
  source channel independently before composing RGB. This can make weak
  fluorescence visible but changes color balance.
- **Full data-type range (8-bit / 16-bit)** maps the unsigned source data type
  to the model's 8-bit RGB view: 0-255 for uint8 and 0-65535 for uint16. There is
  no per-channel contrast stretch, so the same input range is used across RGB
  channels. Both 8-bit and 16-bit RGB are supported. Mean projections use the
  original source data type's range even though their output pixels are float32.
- **Use OME-Zarr metadata display windows** (`--normalization metadata`) uses
  the saved `omero.channels[].window.start` and `window.end` for each selected
  source channel. Start maps to 0, end maps to 255, and values outside the window
  are clipped. Windows are read from each image field, including HCS fields,
  and reused across timepoints and Max/Mean projections. Missing, non-finite,
  equal or reversed limits fail **Check input** before model loading; there is
  no automatic fallback. The allowed `window.min`/`window.max` bounds are not
  substituted for the saved start/end display limits. See the
  [OME-NGFF channel display metadata](https://ngff.openmicroscopy.org/0.4/#omero-md).
  Only intensity limits are used: metadata colors, active flags, inversion and
  gamma do not override your explicit grayscale/RGB channel mapping.
- Full data-type range can make 12-bit data stored as uint16 look dark because
  its values occupy only part of 0-65535. Use the metadata window or percentile
  scaling when a narrower display range is intended. Floating-point source
  images require metadata or percentile scaling.
- The intensity-scaling control does not switch between combined RGB and
  separate-channel inference. For separate channel-specific targets, use
  different prompt slots with their own single-channel inputs.
- Rendering changes only the model view. Measurements include every source
  channel and use original 2D pixels or the projection before normalization.

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
| Physical geometry | Area in µm²; perimeter, equivalent diameter, major/minor axes, centroid and bounding box in µm when calibrated |
| Every image channel | Valid pixel count, minimum, maximum, mean and total intensity |

Channels outside the model input are measured too. For 3D input, measurements use
the projection before normalization. NaN/Inf pixels are excluded and reflected in
the valid count. Empty runs write headers. Failed runs retain `measurements.partial-*`
instead of a completed CSV. Semantic label 1 describes the full merged region.

Pixel columns remain as references. Physical coordinates include NGFF origins;
X/Y spacings are applied independently. Axes, eccentricity and orientation use
physical geometry when calibrated; `shape_basis` records the basis. Isotropic
perimeter scales the pixel estimator. Anisotropic perimeter uses scaled closed
contours, recorded in `perimeter_um_method`. Intensities keep their original
units, ratios are dimensionless and angles remain radians. Missing calibration
leaves physical columns blank.

## Bilayers and BIOMERO

The display name is **CISegWeVisOneVL**; the configuration key can be
`cisegwevisonevl`. The CSV is declared as one measurement output with CSV format;
the installed BIOMERO parser was tested with this declaration.

Release **v0.1.0** provides `cellularimagingcf/w_cisegwevisonevl:v0.1.0`, a
headless Linux image with the pinned model weights included. Reserve **one NVIDIA
GPU with at least 24 GB VRAM** on the Slurm partition. Host RAM is reserved
separately. The [deployment guide](deployment.html) provides measured memory use,
Docker/Apptainer commands and the versioned BIOMERO configuration. Container GPU
inference and descriptor parsing are checked; OMERO reimport remains an acceptance
step for each deployment.

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

## Curated demonstrations and large images

The current main gallery contains 22 examples and 29 reviewed labels, selected
after 89 candidate prompt comparisons. Empty or unconvincing outputs are excluded from the
main examples; audits remain in [the first comparison](prompt-study.html) and
[the whole/part modality study](imaging-modes.html). Filter the gallery by imaging
mode to find phase contrast, EM, fluorescence and immunohistochemistry examples.
EM examples are native 2D sections without Z projections. This is positive
demonstration selection, not a representative accuracy benchmark.

The [large-image study](tiling.html) benchmarks tile sizes and object fusion and
proposes advanced user controls. A bounded research prototype works on controlled
fields, but production gigapixel streaming is not enabled. The 16-megapixel guard
continues to apply to input/projection and measurement processing.
