# CISegWeVisOneVL working instructions

- Write all Markdown files, repository documentation, GitHub Pages content, descriptors, human-readable Python string literals, docstrings, comments, gallery labels/status messages, and user-facing UI text in English. Preserve proper names and original source titles in attribution. Keep future additions and updates in English. Do not rename established technical parameter keys or file formats solely for translation.
- GitHub Pages provides a Bright/Dark toggle on every page. Dark is the default; remember the visitor's explicit selection across pages and reloads. Do not recolor or invert scientific images when switching themes.

- Use `.venv/Scripts/python.exe` explicitly on this Windows workstation; Python 3.12 is required by the pinned upstream SciPy stack.
- Keep `.venv/`, `models/`, `publicdata/`, input/output stores and test results ignored by Git.
- Segment 2D inputs and automatically project Z>1 inputs per channel/timepoint, with advanced Max (default) or Mean. Process all timepoints and all HCS fields. Never mix the time and Z axes or invent spatial calibration.
- Preserve 2D source pixels. For 3D input, output the documented 2D projection and its labels; preserve the input volume untouched. Mean projection uses float32. Do not project instance label IDs from the input volume.
- Preserve source stores and source pixels; write results to a separate output store. When overwrite is enabled, stage the complete new run before replacing matching result stores and measurements.csv, and restore previous results if publication fails. The local GUI/launcher default to replacement; the CLI requires --overwrite 1.
- Keep a maximum of four independently optional prompt slots. Do not merge different prompt classes into one exclusive label image.
- Fresh forms use blank prompts and generic output names `target1` through `target4`. Keep prompt, label-name and channel inputs, existing-input-label handling, and RGB-view intensity scaling in the basic form; mark other parameters advanced and initially collapse them in the launcher. Explain that each target sees one composed RGB view, with one grayscale channel or three explicitly mapped R,G,B channels. Contrast scaling is not a combined/separate-channel inference switch.
- Separate successful execution and file compatibility from biological segmentation accuracy. Retain failed predictions and report poor reference agreement.
- The main example gallery is curated using `gallery_selection.json`: show reviewed results only, exclude EM Z projections, and describe positive selection explicitly. Preserve all unselected prompt experiments locally and summarize them honestly; curated demonstrations are not a representative accuracy benchmark.
- `tools/experimental_tiling.py` is a bounded in-memory research prototype. Do not remove the production 16-megapixel guard or advertise gigapixel support until input/projection, label storage, pyramids and measurements all use bounded streaming.
- When XY calibration is known, export lengths and coordinates in micrometers and areas in square micrometers alongside pixel references. Respect anisotropic spacing, ordered transforms and image origins. Do not convert intensity values or dimensionless ratios to length units, and never invent missing calibration.
- Run tests with `.venv/Scripts/python.exe -m pytest -q`; real GPU validation is `tools/validate_local.py`.
- Build or publish Docker images and change a running BIOMERO stack only when requested for that phase. Keep release tags, descriptors and model revisions consistent; validate offline GPU inference before publishing a release image.
- The public model is an inference foundation model. Do not describe this adapter as a newly trained or fine-tuned microscopy model.
