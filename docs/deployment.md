# Deploy the BIOMERO workflow on Slurm

Release **v0.2.0** uses the existing offline WeVisOne-VL-4B weights to process
OME-Zarr input from BIOMERO and return native-size labels and measurements to
OMERO. Match the container and descriptor versions:

- [Container v0.2.0](https://hub.docker.com/r/cellularimagingcf/w_cisegwevisonevl/tags?name=v0.2.0): `cellularimagingcf/w_cisegwevisonevl:v0.2.0`, `linux/amd64`
- [Tagged descriptor](https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/blob/v0.2.0/config.yaml)
- [Validation record](release-v0.2.0-validation.json)

The image includes approximately 19.37 GB of pinned model files. Inference stays
offline; compute nodes do not need a Hugging Face token or a model download.
The Windows GUI is an optional source interface and is not installed in this
headless workflow image.

## GPU and host resources

Reserve **one NVIDIA GPU in the 24 GB class or larger**, with BF16 support.
Start with **4 CPU cores and 32 GB host RAM**. Slurm host memory settings do not
reserve GPU VRAM. Multiple smaller GPUs do not combine their memory for this
single-device adapter. GPU passthrough requires NVIDIA Container Toolkit for
Docker, or Apptainer `--nv`.

Automatic resolution inspects the assigned CUDA device/MIG slice and currently
free memory after the model loads. A 24 GB device starts at a longest-side limit
of 3072; a 47 GB device starts at 4096. The ceiling is 4096. A reserve is kept,
busy devices can choose a smaller overview, and CUDA out-of-memory triggers a
smaller complete-field retry. The 47 GB profile requires validation on the real
device; 12 GB is not supported.

On the local RTX A5000, a full large-scan job with a **3072 × 1433** working
overview, four prompts and native **53912 × 25139** labels completed with:

| Resource | Measured |
| --- | --- |
| Peak allocated GPU memory | 11.56 GiB |
| Peak reserved GPU memory | 12.34 GiB |
| Peak process RAM | 25.85 GiB |
| Allocated CPU cores | 4 |
| Average / peak sampled CPU use | 0.80 / 1.87 cores |
| Model job, including native output writing | 7 min 8 s |

These are fixture measurements, not guaranteed maxima. Aspect ratio, object
count, prompt length and decoder settings can change memory use. A square
4096-pixel image is larger than the tested narrow overview. Host RAM must cover
model loading as well as image processing. Storage must cover the input copy,
independent uint32 label pyramids and any staged replacements. Large input
archiving, file transport and OMERO import can dominate the total runtime.

The runtime uses Python 3.12, PyTorch 2.11.0/CUDA 12.6 and Transformers 5.12.1.
Use a compatible site-supported NVIDIA driver. The container supplies CUDA
user-space libraries; the host supplies the driver. See the
[NVIDIA compatibility guide](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).

## Pull and test the container

```bash
apptainer pull w_cisegwevisonevl_v0.2.0.sif \
  docker://cellularimagingcf/w_cisegwevisonevl:v0.2.0
```

Pull once where registry access, storage and conversion resources are available.
Inference can then stay offline. For a Docker smoke test, use separate input
and output folders:

```bash
docker run --rm --gpus all --network none \
  --mount "type=bind,source=$INPUT,target=/data/in,readonly" \
  --mount "type=bind,source=$OUTPUT,target=/data/out" \
  cellularimagingcf/w_cisegwevisonevl:v0.2.0 \
  --infolder /data/in --outfolder /data/out --device cuda:0 \
  --auto-resolution 1 --prompt-1 "cell nuclei" --name-1 nuclei --channels-1 1
```

Set `INPUT` and `OUTPUT` to absolute host paths; input must be NGFF 0.4/Zarr v2
with explicit axes. A directory can contain multiple input stores or HCS plates.

## Register with BIOMERO

Merge these settings into the site's canonical `slurm-config.ini`, preserving
its existing connection/storage configuration. The `_job` entry must precede
the `_job_*` resource settings for the tested parser. Change the partition and
GPU selector to match the site's actual GPU types and memory capacities.

```ini
[WORKFLOWS]
cisegwevisonevl = cisegwevisonevl
cisegwevisonevl_repo = https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/tree/v0.2.0
cisegwevisonevl_use_gpu = true
cisegwevisonevl_job = jobs/cisegwevisonevl.sh
cisegwevisonevl_job_partition = gpu
cisegwevisonevl_job_gres = gpu:1
cisegwevisonevl_job_cpus-per-task = 4
cisegwevisonevl_job_mem = 32G
cisegwevisonevl_job_time = 04:00:00
```

Refresh workflow metadata and job scripts through the deployment's normal
administrator procedure. Cache the image as `w_cisegwevisonevl_v0.2.0.sif` in
the configured workflow image directory and select **v0.2.0** explicitly.
Retain the deployment's GPU-flag injection so Apptainer receives `--nv`.

For an existing v0.1.0 installation, a separate key such as
`cisegwevisonevl_overview` can preserve the older workflow. Point that key to
`tree/v0.2.0/config-overview.yaml` and use its own job/image directory. Do not
offer old images through the new descriptor: their supported parameters differ.

In BIOMERO, enable **Upload result CSVs as OMERO tables** for the measurement
table. Optional ROI conversion is a separate deployment feature; native label
images are returned independently. Validate the full return path on your site.

## Helios GPU/MIG examples

The [official Helios GPU guide](https://hg-aumc.gitlab.io/hpc-aumc/user-wiki/job_management/gpu_basics/)
lists `2g.24gb` and `4g.47gb` resource types within the GPU partition. Inspect
currently available resources with `sinfo` before submitting. The published
profile allocations give these site-specific examples:

```bash
sbatch --partition=gpu --gres=gpu:2g.24gb:1 --cpus-per-task=8 --mem=52G job.sh
sbatch --partition=gpu --gres=gpu:4g.47gb:1 --cpus-per-task=18 --mem=100G job.sh
```

Choose the GPU type in Slurm; the application then detects the assigned capacity.
The local demonstration's four-CPU/32G allocation is separate from these Helios
profiles. Do not copy the Helios host-memory request onto a smaller local node.
These examples are configuration guidance, not evidence of a completed Helios
hardware test.

## Labels, measurements and validation scope

Prediction uses one complete-field pyramid overview per prompt. Native labels
are streamed with per-instance distance interpolation and discrete uint32 IDs.
Measurements use only the working overview: geometry transforms per axis, while
area, finite counts and integrated intensity multiply by Y×X. Mean/min/max
retain unnormalized overview values. These are estimates; native interpolated
pixel area can differ. See the [large-image guide](tiling.html).

105 tests passed. A full local BIOMERO/Slurm run returned one RGB image, four
native label images and a measurement table to OMERO. Retained pyramid bytes
and all working-overview areas/channel statistics were independently checked.
Complete native-pixel and every-table-cell roundtrip comparisons were not
completed. The tested stack also logged incomplete storage-provenance annotations;
this deployment-specific issue does not establish complete metadata provenance.

Layer proposals overlapped broadly in the large histology case. Successful
execution is not evidence of anatomical or diagnostic accuracy. The gallery is
positively selected. Historical v0.1.0 evidence remains in its
[validation record](release-v0.1.0-validation.json).

## Rebuild

Prepare the pinned models with `tools/download_models.py`, then:

```bash
docker build --platform linux/amd64 -f Dockerfile.models \
  -t w_cisegwevisonevl-model-cache:local .
docker build --platform linux/amd64 --build-arg VERSION=0.2.0 \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  -t cellularimagingcf/w_cisegwevisonevl:v0.2.0 .
```

The model cache is an internal build artifact; publish the final workflow image.
Models, private inputs and output stores are excluded from the code build
context. The final build verifies the pinned model inventory. See
[NOTICE.md](https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl/blob/v0.2.0/NOTICE.md)
for adapter, dependency and upstream model licensing.
