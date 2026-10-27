# BIOMERO, Docker and Slurm deployment

The development checkout replaces tile inference with whole-field pyramid overview prediction, default maximum side 4096. The released v0.1.0 image retains its original behavior; always use the descriptor matching the source-pinned container. See [large-image selection, smooth labels and measurement scaling](tiling.html).

Large views need more working memory. Query-chunked exact attention retains full-image keys while bounding temporary workspace in both the vision and language backbones. Mask decoding also avoids unused full-sequence vocabulary logits. Actual peak still depends on dimensions, aspect ratio, prompt length and object count. Validate the requested view on the target partition; a long narrow image is not equivalent to a square 4096-pixel image. Current local validation results are recorded separately below when available.

Disk must cover the source image copy, independent native uint32 label pyramids for every prompt, and staged replacement results. Label writing is bounded; shape/intensity measurement uses only the working overview. Historical tile performance measurements do not establish the resource needs of this new route.

Release **v0.1.0** provides the headless `linux/amd64` image
[`cellularimagingcf/w_cisegwevisonevl:v0.1.0`](https://hub.docker.com/r/cellularimagingcf/w_cisegwevisonevl/tags?name=v0.1.0).
Use the versioned image and the matching
[GitHub descriptor](https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/blob/v0.1.0/config.yaml).
The image includes the pinned WeVisOne-VL-4B weights and pixel decoder, approximately
19.37 GB of model files. Inference runs offline; no model download or Hugging Face
token is required on the compute node. The desktop GUI is distributed in the
source release and is not installed in this headless image.

## Overview development validation and Helios profiles

The local RTX A5000 24 GB processed the complete esophagus overview at 4096 × 1910 for all four prompts. Each prediction took approximately 15 seconds. Maximum PyTorch allocated memory was **12.10 GiB**, reserved **13.37 GiB**; after cleanup the loaded model retained about **9.10 GiB allocated**. These measurements describe the overview GPU phase, not complete export/import runtime or every possible image. Automatic mode conservatively uses a 3072-pixel ceiling for 24 GB; a separate 3072 overview probe took about 6.2 seconds with 11.56 GiB allocated and 12.27 GiB reserved. The 47 GB profile defaults to 4096 and still requires validation on the real device. 12 GB is not a supported profile.

Helios exposes GPU types through Slurm GRES. The [official GPU guide](https://hg-aumc.gitlab.io/hpc-aumc/user-wiki/job_management/gpu_basics/) lists `2g.24gb` and `4g.47gb`; verify currently available types with `sinfo`. These are GPU/MIG resource types within the GPU partition. Host RAM is requested separately. For example:

```bash
# 24 GB GPU profile, normally a 3072-pixel overview ceiling
sbatch --partition=gpu --gres=gpu:2g.24gb:1 --cpus-per-task=8 --mem=52G job.sh
# 47 GB GPU profile, normally a 4096-pixel overview ceiling
sbatch --partition=gpu --gres=gpu:4g.47gb:1 --cpus-per-task=18 --mem=100G job.sh
```

These site-specific examples follow the published profile allocations; they do not replace the portable defaults or the local A5000 Slurm configuration. The application inspects its assigned CUDA device and free VRAM after model loading. A smaller overview is retried after CUDA out-of-memory; actual dimensions and measurement scale are retained in reports and CSV. Use Apptainer `--nv` as documented by Helios.

The release guidance below describes v0.1.0; use the separately pinned overview descriptor and local development image for the new route.

## GPU partition requirements

**Reserve one NVIDIA GPU with at least 24 GB VRAM per job.** An RTX A5000 with
24 GB is the tested deployment profile, using BF16, a maximum model-input side
of 1024, 2048 generated tokens and decoder batch size 1. Smaller GPUs have not
been validated. Multiple smaller GPUs do not combine their VRAM for this adapter.
Prompts, fields and timepoints are processed serially using the same model.

| Resource | Deployment guidance |
| --- | --- |
| GPU | One CUDA-capable NVIDIA GPU with BF16 support; 24 GB VRAM or more |
| Host RAM | Start with 32 GB per job; measured process RSS peaked at 25.42 GiB on the release fixtures |
| CPU | Start with 4 cores per job |
| Image storage | Allow at least 80 GB free for image download, Apptainer conversion and cache, plus input/output space |
| Runtime | Linux x86-64; NVIDIA Container Toolkit for Docker, or Apptainer with `--nv` |
| Software in image | Python 3.12, PyTorch 2.11.0 / CUDA 12.6, Transformers 5.12.1 |

Measured GPU memory is **not** a guaranteed maximum for all inputs. Windows
real-model validation reached 11.37 GiB of PyTorch allocated GPU memory.
The Linux container validation reached **11.37 GiB allocated** and
**12.42 GiB reserved** by PyTorch on the same 24 GB GPU.
Allocator reservations and driver/runtime overhead also need VRAM. Larger model
views, longer generated output and larger decoder batches can increase usage;
validate those settings on your partition before offering them to users.

Host RAM must also cover model loading and image/measurement processing. The
32 GB starting allocation is based on these fixtures, not a maximum for large
images or dense masks. The node must advertise enough RAM in Slurm for the
requested allocation; a node configured with only 16 GB cannot schedule this
32 GB job until its configuration/resources are adjusted by its administrator.

Slurm `--mem=...` and `--mem-per-gpu=...` reserve **host RAM**, not GPU VRAM.
Select a partition or GPU type that actually provides a 24 GB GPU; a generic
`--gres=gpu:1` alone does not guarantee its memory capacity. GPU type and
constraint names are defined by the cluster administrator. See the
[Slurm GPU resource documentation](https://slurm.schedmd.com/gres.html).

The container supplies CUDA user-space libraries, while the host supplies the
NVIDIA driver. CUDA 12.x has a driver compatibility floor of 525 with feature/PTX
limitations; this release was tested with driver 595.79 on Windows/Docker Desktop.
Use a current driver supported by your site and validate the actual node. See
[NVIDIA CUDA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).

## Test Docker before registering the workflow

On a Linux GPU host, create separate input and output folders. Input must be
NGFF 0.4 / Zarr v2 with explicit axes. The wrapper accepts an input store or a
folder containing stores. For example:

```bash
docker pull cellularimagingcf/w_cisegwevisonevl:v0.1.0
mkdir -p "$PWD/results"
docker run --rm --gpus all --network none \
  --mount "type=bind,source=$PWD/inputs,target=/data/in,readonly" \
  --mount "type=bind,source=$PWD/results,target=/data/out" \
  cellularimagingcf/w_cisegwevisonevl:v0.1.0 \
  --infolder /data/in --outfolder /data/out --device cuda:0 \
  --prompt-1 "cell" --name-1 cell --channels-1 1
```

Choose prompts and channel maps for your own images. One channel creates a
grayscale RGB view; three channels map to R,G,B in the entered order. Blank
prompts disable their slots. Results contain independent native label groups,
provenance, previews and one `measurements.csv`. Original inputs remain unchanged.
CLI replacement requires `--overwrite 1`; the Bilayers form defaults to replacing
previous results only after a successful complete run.

## Pull an Apptainer image

Pull once on a node with registry access, sufficient disk space and adequate
RAM/time for image conversion. Inference nodes can then stay offline:

```bash
apptainer pull w_cisegwevisonevl_v0.1.0.sif \
  docker://cellularimagingcf/w_cisegwevisonevl:v0.1.0
```

An example Slurm job follows. Change `gpu` and the GPU resource selector to match
the cluster's 24 GB-or-larger GPU nodes. `--mem` is independent of GPU memory.

```bash
#!/bin/bash
#SBATCH --job-name=cisegwevisonevl
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
set -euo pipefail
mkdir -p "$OUTPUT"
apptainer exec --nv \
  --bind "$INPUT:/data/in:ro" --bind "$OUTPUT:/data/out" \
  "$IMAGE_DIR/w_cisegwevisonevl_v0.1.0.sif" \
  python /app/wrapper.py \
  --infolder /data/in --outfolder /data/out --device cuda:0 \
  --prompt-1 "cell" --name-1 cell --channels-1 1
```

Set `INPUT`, `OUTPUT` and `IMAGE_DIR` to absolute host paths before submission.
The time limit is a starting point, not an estimate for every dataset. Jobs with
many fields/timepoints require longer limits. A large image pull/conversion may
also need its own Slurm job according to local cluster policy.

## Register in BIOMERO

The Bilayers descriptor and command substitutions were checked against installed
BIOMERO **2.9.0b11**. Merge the following workflow settings into the deployment's
existing configuration; keep its SSH, storage and other workflow settings.
The `_job` entry must precede the `_job_*` entries for this BIOMERO parser.

```ini
[WORKFLOWS]
cisegwevisonevl = cisegwevisonevl
cisegwevisonevl_repo = https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/tree/v0.1.0
cisegwevisonevl_job = cisegwevisonevl.sh
cisegwevisonevl_use_gpu = true
cisegwevisonevl_job_partition = gpu
cisegwevisonevl_job_gres = gpu:1
cisegwevisonevl_job_cpus-per-task = 4
cisegwevisonevl_job_mem = 32G
cisegwevisonevl_job_time = 01:00:00
```

Enable or retain the deployment's GPU passthrough (`--nv`). In BIOMERO versions
with `inject_gpu_flag`, `[SLURM] inject_gpu_flag = true` supplies `--nv` for
GPU workflows; the example's per-workflow partition and GPU request take
precedence over generic defaults. Adapt this through the deployment's normal
configuration process rather than replacing the complete configuration file.

Refresh BIOMERO workflow metadata/job scripts and pull the image using the site's
normal administrator procedure, then select version **v0.1.0**. The image filename
expected by the tested client is `w_cisegwevisonevl_v0.1.0.sif` under the configured
workflow image directory. The Bilayers adapter reads the repository/image name;
select the version explicitly rather than relying solely on `docker_image.tag`.
Input and output folder arguments are generated from `config.yaml` and the
measurement output is declared as a single CSV.

Release checks ran real GPU inference in the Linux container with networking disabled,
including the public cell and organoid inputs and a derived two-field, two-timepoint
Z-stack fixture using both Max and Mean projections. Source bytes and output pixels
were checked. The derived fixture verifies processing behavior, not biological 3D
accuracy. See [the release validation record](release-v0.1.0-validation.json).
The organoid fixture produced 84 model instances and foreground Dice 0.880
against the microSAM consensus reference. This measures foreground agreement,
not instance accuracy. The earlier Windows run gave 83 instances and Dice 0.881;
results are not assumed to be bit-identical across runtime backends. All 97
regression tests and the static website checks passed. Exact installed Linux
packages are recorded in
[`requirements-lock.linux.txt`](https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/blob/v0.1.0/requirements-lock.linux.txt).

An OMERO end-to-end image/label/CSV reimport test remains a deployment acceptance
step. Container inference and descriptor parsing do not by themselves validate
OMERO attachment import or every Slurm installation.

## Scope and limitations

This is the first research release. Successful execution does not establish
biological accuracy. Inspect masks for your images and prompts. The reviewed
gallery is positively selected, not a representative benchmark. In the earlier
Windows validation, `organoids_im9` generated inconsistent object/box counts and
was correctly rejected; some nuclei prompts produced poor masks despite a
successful run. Diagnostics are retained for failed runs.

Production inputs are limited to 16 megapixels per XY plane. Z stacks are
projected per channel and timepoint (Max or Mean); volume instance IDs are never
projected. Native 3D segmentation, automatic production tiling and tracking are
not included. See [the workflow guide](workflow.html) and
[validation notes](research.html).

The adapter is MIT licensed. The image includes upstream model weights/code and
third-party packages with their own licenses; see
[NOTICE.md](https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/blob/v0.1.0/NOTICE.md)
and `/models/WeVisOne-VL-4B/LICENSE` inside the image.

## Rebuild the release image

Download the pinned model inventory with `tools/download_models.py`, then build
the internal model cache and the final image:

```bash
docker build --platform linux/amd64 -f Dockerfile.models \
  -t w_cisegwevisonevl-model-cache:local .
docker build --platform linux/amd64 --build-arg VERSION=0.1.0 \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  -t cellularimagingcf/w_cisegwevisonevl:v0.1.0 .
```

The internal cache is a build artifact; only the final headless workflow image
is published. Public images and local output stores are excluded from the
container build context. The release validation report records the tested
runtime and memory measurements; downloaded model file sizes and pinned snapshot
revision are verified during the final build.
