# CISegWeVisOneVL working instructions

- Use `.venv/Scripts/python.exe` explicitly on this Windows workstation; Python 3.12 is required by the pinned upstream SciPy stack.
- Keep `.venv/`, `models/`, `publicdata/`, input/output stores and test results ignored by Git.
- Segment 2D inputs and automatically project Z>1 inputs per channel/timepoint, with advanced Max (default) or Mean. Process all timepoints and all HCS fields. Never mix the time and Z axes or invent spatial calibration.
- Preserve 2D source pixels. For 3D input, output the documented 2D projection and its labels; preserve the input volume untouched. Mean projection uses float32. Do not project instance label IDs from the input volume.
- Preserve source stores and source pixels; write results to a new store. Do not overwrite completed outputs.
- Keep a maximum of four independently optional prompt slots. Do not merge different prompt classes into one exclusive label image.
- Separate successful execution and file compatibility from biological segmentation accuracy. Retain failed predictions and report poor reference agreement.
- Run tests with `.venv/Scripts/python.exe -m pytest -q`; real GPU validation is `tools/validate_local.py`.
- Docker recipes are preparation only. Do not build, publish, deploy or change the running BIOMERO stack unless requested for that phase.
- The public model is an inference foundation model. Do not describe this adapter as a newly trained or fine-tuned microscopy model.
