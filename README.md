# CISegWeVisOneVL

**A BIOMERO workflow for text-prompted segmentation of images in OMERO.**

Choose up to four targets in BIOMERO, run WeVisOne-VL-4B on Slurm, and return
native-size label images and a measurements table to OMERO. The workflow supports
regular images, time series and HCS plates. Z stacks are projected separately for
each channel and timepoint; Max is the default and Mean is available in Advanced.
Original inputs remain unchanged.

[Workflow guide](https://cellular-imaging-amsterdam-umc.github.io/ciseg-wevisonevl/workflow.html) ·
[Deployment and GPU requirements](docs/deployment.md) ·
[Docker Hub](https://hub.docker.com/r/cellularimagingcf/w_cisegwevisonevl) ·
[Reviewed examples](https://cellular-imaging-amsterdam-umc.github.io/ciseg-wevisonevl/examples.html)

This adapter runs the existing foundation-model weights. It is not a newly
trained or fine-tuned microscopy model. Segmentation quality depends on the
image and prompt; review each result before interpreting the measurements.

## Run from BIOMERO

Your BIOMERO administrator must first install the workflow and its container
on Slurm, as described below.

1. Select the images, dataset or plate to process in OMERO and open BIOMERO.
2. Choose **CISegWeVisOneVL**, version **v0.2.0**. The administrator chooses the
   workflow key; the standard key is `cisegwevisonevl`.
3. Enter up to four English prompts. Give each target a unique label name and
   channel selection. Leave unused prompts blank.
4. Select how to handle existing input labels and how to scale the RGB model
   view. Advanced settings include Z projection, probability threshold and
   automatic GPU-dependent overview resolution.
5. Choose the destination for the returned images and enable **Upload result
   CSVs as OMERO tables** to import `measurements.csv` as a table.
6. Run the workflow and inspect the independent label layers and measurements
   in OMERO. Different prompts may overlap; they are not exclusive tissue classes.

Each prompt sees one composed RGB image: `1` repeats one grayscale channel, and
`1,2,3` maps the selected channels to red, green and blue. Unsigned 8-bit and
16-bit RGB are supported. Intensity scaling can use the full data-type range,
per-channel percentiles, or saved OME-Zarr display windows. It changes the model
view; measurements use the working overview before contrast scaling.

The basic form includes prompt text, label name, channels, intensity scaling and
**Existing input labels**. Keep preserves existing 2D labels in the result;
Remove omits them from the new result and permits recomputing those names. The
input store is never modified. Existing volume label IDs are not projected.

## Install the BIOMERO workflow

Use the matching released descriptor and image:

- Descriptor: [v0.2.0/config.yaml](https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/blob/v0.2.0/config.yaml)
- Container: **`cellularimagingcf/w_cisegwevisonevl:v0.2.0`**, `linux/amd64`
- GPU: **one NVIDIA GPU in the 24 GB class or larger**, with BF16 support
- Host resources: start with **4 CPU cores and 32 GB RAM**; larger or denser
  results can require more. Host RAM and GPU VRAM are separate resources.

The image includes approximately **19.37 GB of pinned model files** and runs
inference offline. Compute nodes do not need a Hugging Face token or model
download. Apptainer needs GPU passthrough with `--nv`.

```bash
apptainer pull w_cisegwevisonevl_v0.2.0.sif \
  docker://cellularimagingcf/w_cisegwevisonevl:v0.2.0
```

Register the tagged descriptor in the site's canonical `slurm-config.ini`,
generate the BIOMERO job script, and select the matching container version.
Do not pair the new descriptor with an older image. The
[deployment guide](docs/deployment.md) includes registration, Slurm and Helios
GPU/MIG examples. Existing v0.1.0 installations can retain their tagged descriptor
and image until explicitly upgraded.

## Large scans and automatic GPU resolution

Prediction uses **one overview of the complete field per prompt**, preserving
anatomical context. Tile-by-tile prediction has been removed.

| Assigned GPU memory | Automatic starting limit |
| --- | --- |
| 24 GB class, including Helios `2g.24gb` | 3072 pixels on the longest side |
| 47 GB class, including Helios `4g.47gb` | 4096 pixels on the longest side |

The planner inspects the assigned CUDA device or MIG slice and currently free
memory, keeps a reserve, and respects the configured maximum of 4096 pixels.
It selects the smallest existing pyramid level still at or above the limit and
area-resizes it. Small images are not enlarged. A CUDA out-of-memory error
retries a smaller complete overview. The 47 GB profile has not been tested on
actual Helios hardware; 12 GB is not a supported profile.

Labels are smoothly restored to native dimensions using per-instance signed
distances. Integer label IDs are never interpolated. Native labels and their
pyramids are written in bounded blocks. Smoothing cannot recover biological
detail missing from the overview. See the [large-image guide](docs/tiling.md).

## Labels and measurements returned to OMERO

Every input produces `<source>__wevisonevl.ome.zarr` with independent uint32
groups under `labels/wevisone_<name>`, native-size labels, label pyramids, previews
and `wevisone-run.json`. The original 2D pixels are preserved. For Z stacks,
the new result contains the documented 2D projection; the source volume stays
untouched. All timepoints and HCS fields are processed independently.

One **`measurements.csv`** covers every source, field, timepoint and prompt.
It contains area, centroid, bounding box, perimeter, equivalent diameter,
major/minor axes, eccentricity, solidity, extent, orientation, and valid pixel
count plus min/max/mean/total intensity for **every image channel**.

Measurements are made on the working pyramid overview and transformed to the
native image scale. If `sy = native_height / working_height` and
`sx = native_width / working_width`:

- **Area, valid pixel counts and total intensity multiply by `sy * sx`.**
- Lengths, positions and shape moments use the separate Y/X scales.
- Mean, minimum and maximum intensity are not multiplied.
- Physical lengths, coordinates and areas use the original calibration,
  ordered transforms and origins. Missing calibration remains blank.

The CSV records working dimensions, scale factors and the measurement method.
These are **overview-based estimates**, not a remeasurement of the native
pixels. The interpolated native raster can have a slightly different area.

## Validation and limitations

The v0.2.0 implementation passed 105 tests, including pyramid selection,
bounded resampling, smooth label IDs, scaled intensities and geometry, automatic
GPU profiles, memory retry, all timepoints, HCS, projection and overwrite safety.
A full large-scan run and return of one RGB image, four native uint32 labels
and a CSV table succeeded through a local BIOMERO/Slurm/OMERO installation.
Working-overview statistics were independently checked against the retained
source pyramid. The complete native-pixel and every-table-cell comparison was
not completed. See [the release validation record](docs/release-v0.2.0-validation.json).

On the tested RTX A5000, a 3072 × 1433 overview reached approximately **11.56 GiB
allocated GPU memory**, **12.34 GiB reserved** and **25.85 GiB process RAM**.
The job used four allocated CPU cores. These are measured values for that run,
not guaranteed maxima for all prompts, aspect ratios or object counts.

Successful processing does not establish biological accuracy. In the large
histology test, three anatomical-layer prompts produced strongly overlapping
whole-tissue proposals. Tumor proposals are unvalidated. The public gallery is
a positively selected demonstration set, not a representative accuracy study.
See [validation notes](docs/research.md) and [the reviewed gallery](docs/examples.md).

## Optional local Python and GUI use

The repository also provides a Windows launcher and a single-viewer GUI for
development, prompt experiments and result inspection. They are additional
interfaces to the same engine; the release container is headless.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```powershell
git clone https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl.git
cd ciseg-wevisonevl
create_env.cmd
.venv\Scripts\python.exe tools\download_models.py
launch_gui.cmd
```

The environment uses Python 3.12, the pinned WeVisOne-VL revision, PyTorch/CUDA
and Transformers. `launch.cmd` opens the parameter launcher; `launch_gui.cmd`
adds the image/label viewer. See [the GUI guide](gui/README.md) for independent
layer visibility, prompt colors, per-object colors, timepoints and HCS fields.
Another model cache can be selected with `--models-root` or
`CISEGWEVISONEVL_MODELS`.

The GUI and launcher replace matching outputs only after a successful staged
run. Failed runs keep previous completed results. The CLI keeps existing output
unless `--overwrite 1` is supplied. `--preflight-only` checks metadata before
loading the model.

```powershell
.venv\Scripts\python.exe wrapper.py `
  --infolder inputfolder\scan.ome.zarr --outfolder outputfolder\scan `
  --device cuda:0 --auto-resolution 1 --normalization dtype `
  --prompt-1 "all tissue fragments" --name-1 tissue --channels-1 1,2,3
```

## Development, examples and attribution

Inputs use NGFF 0.4 / Zarr v2 with explicit axes. Output is normalized to TCZYX
with Z=1. Native 3D segmentation and tracking are not included. Prompt groups
remain independent; within one group highest probability wins overlap and the
first prediction wins ties. Invalid or truncated responses fail the run and
retain diagnostic partial outputs. Empty output is not proof of absence.

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe tools\prepare_publicdata.py --organoids
.venv\Scripts\python.exe tools\build_docs_site.py --guides-only
.venv\Scripts\python.exe tools\check_site.py docs
```

The [gallery](docs/examples.md) contains 22 reviewed examples and 29 selected
labels. `gallery_selection.json` records the reviewed selection; prompt audits
and unselected experiments are described in the [prompt study](docs/prompt-study.md)
and [whole/part study](docs/imaging-modes.md). The website can be viewed without
downloading models or source images. Its Bright/Dark toggle preserves scientific
image colors.

`Dockerfile` builds the workflow image; `Dockerfile.models` builds an internal
model cache. Model weights, source stores, private results and local environments
are excluded from Git. See [NOTICE.md](NOTICE.md) for component/data attribution,
the MIT license for this adapter, and the upstream model licenses.
