# Large scans: whole-field pyramid overview

Tile-by-tile inference was removed on 27 October 2026: small tissue fragments in individual tiles lost anatomical context and produced a patchwork on a large histology scan. Each prompt now sees one overview of the entire field, independently for every timepoint and HCS field.

## Image selection

The maximum overview side is **4096 pixels** (Advanced ceiling, configurable from 128 to 4096). Automatic GPU profiles are enabled by default: **3072** for the 24 GB class and **4096** for larger supported GPUs, subject to the configured ceiling and free memory. Devices below the 24 GB class, including 12 GB MIG, are not supported. The detected capacity is that of the CUDA device assigned to the job, including a MIG slice, not the sum of physical GPUs. Select the smallest existing pyramid level whose longest side is at least this limit, then area-resize it with its aspect ratio preserved. The longest output side is exactly the limit, with the other side rounded to the nearest pixel. Small images retain native dimensions. If no lower pyramid exists, bounded source reads construct the overview without loading a giant native plane.

For a 53912 × 25139 scan with a 6739 × 3142 pyramid level, inference uses a **4096 × 1910** overview. The next smaller 3369 × 1571 level is deliberately not selected. Existing pyramid pixels define the sampled intensities; model contrast scaling is applied afterwards. All image channels, including channels absent from prompts, are measured on the same working overview. Z projections remain independent per timepoint and channel.

## Automatic resolution and memory fallback

The planner keeps a reserve of at least 2 GiB or 15% of assigned device memory and uses a conservative workspace estimate after the model is loaded. Busy devices can select a smaller overview. This estimate is not a guarantee for every prompt. CUDA out-of-memory triggers a new whole-field overview at approximately 75% of the previous side (rounded down to 128-pixel steps), down to 128. A non-memory error fails the run. No failed prediction is published as a completed label; retries and actual dimensions are recorded. Per-prompt scales may differ after a retry. Configured-limit mode bypasses profile selection but retains the out-of-memory fallback.

The 24 GB profile starts at 3072; the 47 GB profile starts at 4096. The 47 GB profile has not been validated on actual Helios hardware. The user stopped the exploratory 12 GB investigation; this is not a supported profile. A larger GPU does not establish better segmentation accuracy.

## Native labels and smooth edges

Native-resolution uint32 labels and calibrated OME-Zarr pyramids are written in bounded blocks. Each instance's signed distance is interpolated bilinearly; the largest positive distance owns a pixel and lower IDs win exact ties. Integer IDs themselves are never interpolated. Different prompts remain independent and may overlap. This smooths low-resolution pixel staircases but cannot recover biological detail absent from the overview. Distance smoothing may change the native raster's pixel area slightly; measurements intentionally describe the scaled overview, not a remeasurement of that raster.

## Measurements and scale

Let `sy = native_height / overview_height` and `sx = native_width / overview_width`. Both are recorded, including differences caused by rounding odd dimensions.

| Quantity | Conversion from working overview |
| --- | --- |
| Area, valid pixel count, total intensity | Multiply by `sy * sx` |
| Minimum, maximum, mean intensity | Retain measured overview value, before contrast scaling |
| Bounding-box edges | Multiply Y by `sy`, X by `sx` |
| Centroid | Pixel-center mapping: `(y + 0.5) * sy - 0.5`, and likewise for X |
| Equivalent diameter | Multiply by `sqrt(sy * sx)` |
| Major/minor axes, eccentricity, orientation | Transform overview moments with separate Y/X spacing |
| Perimeter | Scale the pixel estimator for equal spacing; use scaled closed marching-square contours for unequal spacing |
| Physical coordinates and shapes | Apply native NGFF spacing, ordered transforms and origins after overview scaling |
| Solidity, extent | Retain dimensionless overview ratios |

`measurement_method`, `measurement_height_px`, `measurement_width_px`, `measurement_scale_y/x`, `measurement_area_px` and effective measurement pixel spacings document the basis. Pixel counts and areas can be fractional after scaling. Integrated intensity is an **estimated native-pixel sum**, not an exact sum of original native pixels. Extremes may differ from native extrema because of pyramid averaging. No physical units are invented when calibration is absent. `min_area` is specified in native pixels and converted to the overview area before filtering.

The original 2D image pixels are preserved in the output. The overview does not replace the native source. For volumes the output image is the documented Z projection; the input volume remains untouched. Staged overwrite and input-label keep/remove apply as before.

## GPU and local workflow

The 4B model remains loaded between prompts; unused CUDA cache is released after each call by default. Exact query-chunked global attention bounds temporary workspace in both backbones, while retaining all keys for every query. BF16 kernel rounding can change probabilities slightly. Mask decoding avoids constructing unused vocabulary logits for every image token, while retaining the complete hidden states needed for masks. Actual peak memory depends on view dimensions, aspect ratio and generated object count. See the deployment validation report for measured hardware requirements; a 4096-square view is larger than a 4096 × 1910 example and must not be assumed to have the same peak.

`config.yaml` is the primary v0.2.0 BIOMERO descriptor; `config-overview.yaml` provides the optional distinct overview workflow key. Use the matching v0.2.0 container and tagged descriptor. Published v0.1.0 retains its original behavior and must keep its matching tagged descriptor. Historical tile results and failed predictions remain available locally; obsolete tile inference code and controls have been removed.

Successful execution does not validate anatomical or tumor accuracy. Review every prompt overlay against the image; no diagnostic claim is made.
