# Source attribution

This workflow follows the source-preserving OME-Zarr/HCS-label approach and
Bilayers parameter conventions of Cellular Imaging Amsterdam UMC's
[cisegmentation](https://github.com/Cellular-Imaging-Amsterdam-UMC/cisegmentation),
inspected at v0.6.6 (main fb687cb before the separate tools-only commit).
`bilayers_cli.py` is retained from that MIT-licensed repository; its copyright
and permission notice are in LICENSE. The new adapter has its own small
inference engine and does not include the Cellpose/StarDist runtime.

[WeVisOne-VL](https://github.com/Tencent/WeVisOne-VL) is installed as a dependency
at commit `40f735b8daed437ece982db9718e9c9856f52a79`, under Apache-2.0 with its
third-party notices. It is not vendored or modified. The 4B snapshot retains
its LICENSE file and immutable revision identifier. Review each component's
license for redistribution.

Public image attribution, original member hashes, suggested prompts, and known
physical calibration are retained in `publicdata/catalog.json`. The organoid
images and consensus masks are from the microSAM 2D user study, Pape et al.,
Zenodo https://doi.org/10.5281/zenodo.14036957 (CC BY 4.0). The scikit-image
examples retain their individual authorship and licensing statements.

Additional modality examples retain their own terms; the repository's MIT
license does not relicense these images:

- Paramecium phase-contrast panels: Klaus Hausmann, Richard D. Allen Image
  Collection, University of Hawaii. The collection encourages educational and
  research use; commercial reproduction may require permission. See the
  [source](https://www6.pbrc.hawaii.edu/allen/ch01/00-pm.html) and
  [collection terms](https://www6.pbrc.hawaii.edu/allen/foreword.html).
- Chloroplast TEM: Kevin Mackenzie, University of Aberdeen, Wellcome Collection,
  [CC BY 4.0](https://wellcomecollection.org/works/bx3dctp2). The source describes
  the image as false-colour TEM; it is not fluorescence.
- Endothelial fluorescence channels: Molecular Probes demonstration slide,
  [ImageJ sample and stain attribution](https://imagej.net/ij/images/FluorescentCells.txt).
  No separate file-specific redistribution license was identified.
- Mouse kidney optical section: Genevieve Buckley, Monash Micro Imaging (2018),
  [scikit-image data.kidney](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.kidney), CC0.
- Insulin IHC figures: Joseph de Nanassy and Dina El Demellawy (2017),
  [DOI 10.1177/1177390117690140](https://doi.org/10.1177/1177390117690140),
  CC BY-NC 4.0. Publication panels are used as non-commercial qualitative
  research/educational examples; their existing arrows remain in the source.
