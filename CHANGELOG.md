# Changelog

## v0.1.0 — 2026-10-25

First research release of the CISegWeVisOneVL inference adapter, using the
existing WeVisOne-VL-4B foundation-model weights.

- Up to four independent text prompts, each with its own label name and
  grayscale or explicit R,G,B channel mapping.
- NGFF 0.4 / Zarr v2 input and output, with every HCS field and timepoint
  processed. Z stacks use per-channel/per-timepoint Max or Mean projections.
- Native uint32 instance labels, previews, provenance and one measurements CSV
  covering morphology and all image channels, including physical measurements
  when calibration is known.
- Windows launcher and local PyQt GUI with one image/label viewer, distinct
  prompt colors or per-object colors, basic label-name controls, input-label
  preservation/removal and safe replacement of previous completed results.
- Support for unsigned 8-bit and 16-bit RGB scaling, percentile normalization
  and OME-Zarr metadata display windows.
- A headless `linux/amd64` Docker image with pinned offline model weights and a
  Bilayers descriptor checked with BIOMERO 2.9.0b11.
- Deployment instructions for Docker, Apptainer and Slurm. The tested and
  recommended GPU allocation is **one NVIDIA GPU with at least 24 GB VRAM**.
  Host RAM is a separate allocation; see the measured release validation.

The reviewed gallery is a selected demonstration set. Model predictions need
biological review. Production gigapixel tiling, native 3D segmentation and tracking
are not included; inputs remain limited to 16 megapixels per XY plane.

See [the deployment guide](docs/deployment.md),
[the release validation record](docs/release-v0.1.0-validation.json) and
[the research notes](docs/research.md). Container execution and descriptor parsing
are checked; OMERO reimport is an acceptance step for each deployment.
