# Research and local validation

Investigated on 25 October 2026. Current inference uses **WeVisOne-VL-4B only**.
The evaluated 2B model and selection option were removed at the user's request;
historical measurements remain in ignored local results.

## Implementation choices

The official `WeVisOneVL.predict(task="segmentation")` API returns boxes and
pixel probabilities. The required `mask_decoder.pt` is part of the model; a
generic text-only pipeline does not supply masks. We use the official trained
prompt template, Transformers backend, temperature zero and a default 0.5
probability threshold. No separate SAM pipeline is required.

Upstream code is pinned to `40f735b8daed437ece982db9718e9c9856f52a79`; 4B weights
to `4a7bed92750ac9d8b8a124cede14759036932dc2`. The device-independent PyTorch
decoder runs on Windows without custom CUDA compilation, FlashAttention or vLLM.
Python 3.12 is required by upstream SciPy 1.18.1. The environment uses PyTorch
2.11.0+cu126 and Transformers 5.12.1; dependency checks pass.

Output conventions follow cisegmentation v0.6.6. A separate engine avoids bringing
Cellpose/StarDist dependencies into this environment. No microscopy training or
fine-tuning was performed. Upstream benchmarks do not establish microscopy accuracy.

## Initial public data

The five initial examples are genuine 2D images, converted to NGFF 0.4/Zarr v2
with T=Z=1. RGB is stored as separate channels. Full-resolution values are unchanged;
pyramids use area averaging. Originals, OME-XML, checksums and attribution remain local.

| Example | Shape | Intended use | Reference |
| --- | --- | --- | --- |
| `cell` | 660 × 550 grayscale | Isolated phase cell | No manual mask; documented 0.107 µm/pixel |
| `human_mitosis` | 512 × 512 grayscale | Fluorescent nuclei | No supplied segmentation reference |
| `immunohistochemistry` | 512 × 512 RGB | Colonic glands and nuclei | No supplied segmentation reference |
| `organoids_im9` | 1040 × 1408 grayscale | Small organoids in a well | microSAM consensus mask |
| `organoids_im10` | 1040 × 1408 grayscale | Small organoids in a well | microSAM consensus mask |

The first three come from scikit-image. Organoids come from the microSAM 2D user
study, Zenodo 14036957, with matching test images and masks. Selected TIFF ZIP
members were fetched by byte range and verified against size/CRC32. The incomplete
initial full-ZIP download was not used. Foreground agreement is not an instance
identity or detection-accuracy score.

## Observed behavior

The RTX A5000 has 24 GB VRAM. The initial matrix peaked near **11.6 GiB of
PyTorch-allocated memory**, excluding desktop/driver allocations. After loading,
a cell query took about 2 seconds and the 83-object organoid query about 45 seconds.
These are local workstation measurements, not Slurm/HPC benchmarks.

| Image / query | Output | Interpretation |
| --- | --- | --- |
| Cell / `cell` | 1 instance | Visually plausible; no manual Dice reference |
| Fluorescence / `cell nuclei` | 1 very large mask | Poor generic query for this 4B image |
| Fluorescence / `each bright fluorescent cell nucleus` | 127 instances | More specific result; manual validation needed |
| Histology / `cell nuclei` | 4 large masks | Not reliable nuclei segmentation in this test |
| Histology / `colonic glands` | 4 masks | Requires inspection; no object references |
| Organoids im9 / `organoids` | Invalid token/box correspondence | Rejected; no completed mask |
| Organoids im10 / `organoids` | 83 instances; Dice **0.8808**, IoU **0.7869** | Foreground agreement on one consensus-annotated image |

The earlier 2B organoid results scored Dice 0.0890 and 0.0548. That model is no
longer available through the workflow.

## Invalid responses and absence

A dense exploratory query generated 118 object tokens but only 116 valid boxes,
including reversed coordinates. The upstream decoder filters invalid boxes and
then uses the first N object representations, which can misalign them. This
adapter checks correspondence **before decoding** and preserves invalid responses
for diagnosis. It never invents, swaps or silently skips object coordinates.

The negative query `elephant` returned
`<ref>elephant</ref><box>none</box>`, accepted as a valid empty mask. This supports
that specific negative control, not general reliable microscopy rejection:
an absent `organoid` query on nuclei instead produced a large false-positive mask.

## Projection, time series and HCS

The advanced projection option offers **Max** by default and **Mean**. Z stacks
are reduced per channel, timepoint and screen field. Timepoints are never merged.
Max retains dtype; Mean writes float32. Projection pyramids are rebuilt from the
projected image. Existing 2D pixel values remain unchanged.

Outputs use TCZYX with Z=1; labels use C=Z=1. Source-volume physical Z position is
omitted while XY/time transforms remain intact. OME-XML is updated to SizeZ=1 and
to float for Mean. Existing volume labels remain in the untouched source.

Derived fixtures have distinct T/Z values. A GPU fixture with two fields, two
timepoints and three Z planes uses a shifted public phase-cell image. Exact
projection values, unchanged sources and label movement were checked. This
validates data handling, not independent biological 3D accuracy.

The installed ZarrReader incorrectly read timepoints as zero from compact TCYX
arrays. Output was therefore changed to the five-axis cisegmentation layout.
The corrected reader matched all **48** checked image/label windows across both
projections, fields, timepoints and resolutions. Failed and corrected probes
remain in separate ignored local result directories.

## Measurements and descriptor

One CSV covers all inputs, fields, timepoints and prompts. It stores shape,
area/position and min/max/mean/total intensity plus a valid count for every
channel. Physical area needs positive NGFF XY calibration in known units.
Measurements use original 2D pixels or the projection before normalization.

**31 tests pass**, covering a fourth real fluorescence channel, varying channel
counts, time/label correspondence, calibration, failed runs and descriptor fields.
Actual 4B Max/Mean runs each wrote four rows; measurements matched output pixels.
The installed BIOMERO adapter validated one CSV measurement output and the correct
workflow name/description. The first citation entry supplies these fields.
A live OMERO attachment import remains for the later Docker/Slurm phase.

## Expanded collection and published masks

The collection has **27 examples**, including **22 additions**: 14 separate 2D
images, 6 Z stacks and 2 time series, about 206 MB of OME-Zarr input. Original WSI
files, archives and EM chunks remain separate. Local copies were checked with
SHA-256; conversions checked written values. All examples pass preflight.

Examples include spines, neurites, vessels, organoid tissue, adipocytes, skin,
plant vascular bundles, diatoms and embryos. Complete acquired CMU-1, prostate
and Ki67 scans use existing lower pyramid resolutions; the DAB detail is a
recorded native ROI. CellMap COS-7 and liver FIB-SEM each provide a contiguous
volume and middle 2D section; MIB supplies another mitochondrial EM example.
The catalog preserves sources, selections, resolutions, channel counts and licenses.

Every example was processed again with its prompts and all timepoints:
**64 label runs: 63 technically completed, 1 rejected**. `organoids_im9` generated
210 object tokens but 209 valid boxes; no completed mask was published. Nine
completed runs have an empty first-frame mask. Empty output is not proof that
a target structure is absent.

The gallery includes actual overlays, prompts, channels, coverage, source links,
uint32 labels with time indices (NPZ) and CSV measurements. Cards show the first
timepoint; downloads contain all available frames. "Computed" and "completed"
describe execution, not biological correctness. Performance remains variable
on ultrastructure, dense objects and staining patterns.

Automated launcher/process tests passed. Native Windows visual inspection was
unavailable because desktop access was denied; the website is tested separately
in the browser. Public assets are small derived previews and masks. Full stores,
models, local workstation paths and raw logs are excluded. Docker recipes are
prepared but no new image has been built or deployed; reader checks are not a
live OMERO database import.

## Primary sources

- [Official WeVisOne-VL code and API](https://github.com/Tencent/WeVisOne-VL)
- [Architecture and benchmark report](https://tencent.github.io/WeVisOne-VL/)
- [Official 4B model](https://huggingface.co/tencent/WeVisOne-VL-4B)
- [microSAM organoids and consensus masks](https://zenodo.org/records/14036957)
- [CellMap/Janelia FIB-SEM](https://cellmapchallenge.janelia.org/)
- [QuPath workshop, Thierry Pécot](https://zenodo.org/records/18302140)
- [ImageJ samples](https://imagej.net/ij/images/)
- [scikit-image datasets and licensing](https://scikit-image.org/docs/stable/api/skimage.data.html)
- [MIB mitochondrial example](https://mib.helsinki.fi/help/main2/user-interface/menu/tools/tools-watershed.html)
