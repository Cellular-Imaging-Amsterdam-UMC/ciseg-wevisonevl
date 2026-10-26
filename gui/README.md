# Local image and label GUI

Run `gui\run.cmd` or `launch_gui.cmd` from the repository root. Alternatively:

```powershell
.venv\Scripts\python.exe -m gui
```

This interface uses the same environment and segmentation workflow as the original
launcher. It adds one image viewer with a parameter sidebar, inspired by the
layout of the local CI Deconvolve GUI. It uses PyQt6 and existing image readers;
no additional GUI dependencies are required.

1. Choose a reviewed example, or browse to an input directory/OME-Zarr store and
   select **Load input**. The image selector handles multiple stores; **Field**
   selects HCS image fields and **T** selects the timepoint.
2. Enter up to four independent prompts, output label names and channel maps in
   the basic form on the left. **Existing input labels** keeps existing 2D label
   groups by default. Choose **Remove existing labels from result** to leave them
   out of the new output, allowing existing label names to be recomputed. The
   original input store is unchanged. Existing Z-stack labels stay in the source
   and are omitted from projected 2D outputs; label IDs are never projected.
   **Background** selects the image channels shown underneath all visible label
   layers. Equal channel combinations share one entry: for example, two prompts
   using `1,2,3` both use the same **RGB: 1,2,3** background. With only one unique
   combination the selector is disabled. Changing the background does not select
   a prompt's labels; the checkboxes below the image control label visibility.
   Percentile, full 8-bit/16-bit data-type range, and saved OME-Zarr display windows
   are available under intensity scaling. Each viewer refresh reads one frame in
   a background worker; it does not load the complete time series into memory.
3. Use **Check input**, then **Run local Python**. Inference runs in a separate
   process, keeping the viewer available. The log reports progress and errors.
   **Stop** retains partial diagnostics. Reruns can use the same output folder:
   **Existing results** under Advanced defaults to **Replace after successful run**.
   Matching result stores and `measurements.csv` are replaced only when the entire
   new run succeeds. A failed run keeps the previous completed results. Input
   stores and unrelated files are preserved. Select **Keep existing results** to
   prevent replacement.
4. Successful runs open their completed output automatically in the same viewer.
   **Open results…** also opens existing completed output folders or stores.
   **Load input** returns to the input images.
5. Toggle independent label layers in the list, adjust overlay opacity, or hide all
   labels. Each prompt has a distinct single color by default. Select a label row,
   then use **Single color for this prompt** and **Choose color…** to change it.
   Alternatively select **Different colors per object** for that prompt to inspect
   separate instances. The choice is independent for each prompt: one can be a
   solid color while another uses instance colors. Row icons show the color or a
   multicolor swatch. Hover for coordinates and instance IDs. Different prompt
   classes remain independent and may overlap. Display colors do not change label
   IDs, stored masks, measurements or inference; no rerun is needed.
   Visible prompts in single-color mode always get different colors, including
   after loading saved settings or switching datasets. If a chosen color is
   already used, the selected prompt keeps it and the other prompt gets an
   available color.

Use the mouse wheel to zoom, drag to pan, **Fit** for the complete image and
**1:1** for display-pixel size. Large scans use an existing overview before
reading pixels, or bounded native sampling if none exists. The status reports
native pixels per display pixel, and hover coordinates refer to native pixels.
The label list counts **visible** objects; small labels can disappear in an
overview. The viewer does not load native detail as you zoom in. The run's Max/Mean setting controls projected
previews. **Z section** inspects a native input plane; volume instance labels are
shown only in section view, never projected as IDs. Computed outputs have Z=1.

Changing the displayed prompt, field, timepoint, Z section or layer visibility
only changes the view. Completed labels are not recomputed when parameters
change; run again to apply new segmentation parameters.
The original input pixels and measurement intensities are preserved. A colored
prediction is not a validated biological annotation.

GUI parameter settings are kept in ignored `.last_gui_settings.json`, separately
from the original launcher's settings. Advanced parameters are initially collapsed. For large tilescans, choose
**Image processing → Tile by tile (large scans)**, **Source tile side: 2048** and
**Tile overlap: 256**. **Maximum model input side** is a separate model-view
limit (1024 by default, up to 2048); it is not the source tile size. Blank-tile
skipping is optional and disabled by default because it can miss faint tissue.
See the [large-image guide](../docs/tiling.md) for seam handling and the tiled
measurement estimator. These options belong to the development Python workflow;
they are not present in the released v0.1.0 container.
Label colors, per-prompt color modes, visibility and opacity are saved there on
closing the GUI and restored on reopening, without changing saved run parameters.
