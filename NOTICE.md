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
