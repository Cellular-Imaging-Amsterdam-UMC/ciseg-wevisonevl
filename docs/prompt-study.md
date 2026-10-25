# Prompt comparison and gallery selection

The subsequent [whole/part modality study](imaging-modes.html) adds 37 candidate queries on phase contrast, EM, fluorescence and IHC views. This page retains the original 52-query comparison as a separate study.

The main gallery is a positively selected demonstration set, **not a representative accuracy benchmark**. Unconvincing candidates and EM Z projections are excluded. Raw comparisons remain local; this page preserves their audit without rejected overlays.

## Protocol

- Official segmentation API and trained target-description template; no rewritten freeform system instruction.
- Pinned 4B weights, temperature 0, threshold 0.5, decoder batch 1 and a 4096-token budget.
- Four descriptions per fixed fluorescence/DAB view; three per native 2D EM patch.
- Fixed recorded normalization per view. No color threshold or manual annotation was substituted for a VLM mask.
- 28 fluorescence/DAB and 24 EM candidates: **52 tested prompts**. EM exploration retrieved 33 paired patches; 8 native fields were tested.
- Selected combinations were rerun through the workflow with native labels and calibrated CSVs.
- The two retained EM patches share an acquisition and were selected after comparison; their scores are not held-out generalization estimates.

## Selected changes

| Example | Retained description / result | Selection rationale |
| --- | --- | --- |
| `local-mouse-brain-astrocytes-vessels` | the bright green vessel cross section — 1 predicted objects | A local green vessel profile replaces the previous near-whole-field prediction. |
| `public-lily-stem` | the bright green bundles, excluding the outer ring — 7 predicted objects | Visible green bundles are selected while the outer stem ring is excluded. |
| `public-neurofilament-network-roi` | the white filament network — 1 predicted objects | Network-level foreground in a recorded Max-projection ROI; not individual axon tracing. |
| `public-ki67-brown-nuclei-detail` | dark brown stained nuclei — 18 predicted objects | A recorded native 192-pixel ROI distinguishes brown positive nuclei from blue negative tissue. |
| `public-em-mitolab-folded-mitochondria` | the oval organelles with internal folds — 3 predicted objects, foreground Dice 0.965 | A native 2D EMPIAR patch with paired manual mitochondrial instance labels; selected after exploratory comparisons. |
| `public-em-mitolab-mitochondrial-cluster` | mitochondria — 7 predicted objects, foreground Dice 0.936 | A second native 2D EMPIAR patch from the same acquisition; not an independent generalization benchmark. |

## Interpretation

Concrete visible appearance helped. The green vessel profile changed from a near-whole-field mask to a local structure. The plant query names green bundles and excludes the outer ring. A native 192 × 192 Ki67 ROI makes brown nuclei distinguishable from blue negatives. The fiber example is explicitly network-level, not complete individual axon tracing.

Full-field DAB and most red-process/spine candidates were not convincing enough to retain. Technical completion or a nonempty mask was never sufficient. No manual references were supplied for fluorescence/DAB, so these improvements are qualitative.

EM used native single-frame micrographs without projection. Paired CEM-MitoLab references support foreground Dice near 0.965 and 0.936. These scores do not establish perfect instance identity or broad EM accuracy.

Repeatability check: all six selected study inputs matched the workflow RGB inputs exactly. Five rerun binary masks were identical; the neurofilament mask differed at 30 of 1,048,576 pixels (0.0029%). Temperature 0 did not guarantee bit-identical masks in every rerun. The gallery contains the final workflow outputs.

## All tested candidates

| Study view | Target description | Objects | Foreground fraction | Foreground Dice, if annotated | Selected |
| --- | --- | ---: | ---: | ---: | --- |
| `study-fluo-vessel` | the bright green vessel cross section | 1 | 0.128 | — | Yes |
| `study-fluo-vessel` | the compact bright green fluorescent structure in the center | 1 | 0.125 | — | No |
| `study-fluo-vessel` | green blood vessel wall | 0 | 0.000 | — | No |
| `study-fluo-vessel` | the green oval structure, excluding the red branching fibers | 1 | 0.126 | — | No |
| `study-fluo-processes` | the red branching fibers | 1 | 0.002 | — | No |
| `study-fluo-processes` | the thin red tree-like processes | 2 | 0.017 | — | No |
| `study-fluo-processes` | red fluorescent astrocyte processes | 1 | 0.971 | — | No |
| `study-fluo-processes` | all red filaments, excluding the green structure | 1 | 0.917 | — | No |
| `study-fluo-spines` | the small bright rounded protrusions attached to the main branch | 0 | 0.000 | — | No |
| `study-fluo-spines` | dendritic spine heads | 3 | 0.018 | — | No |
| `study-fluo-spines` | small white bulb-shaped protrusions on the dendrite | 0 | 0.000 | — | No |
| `study-fluo-spines` | the bright rounded spine at the upper left | 1 | 0.009 | — | No |
| `study-lily-bundles` | the bright green oval vascular bundles | 2 | 0.026 | — | No |
| `study-lily-bundles` | bright green circular clusters | 3 | 0.050 | — | No |
| `study-lily-bundles` | the green ring-shaped structures inside the plant stem | 3 | 0.047 | — | No |
| `study-lily-bundles` | the bright green bundles, excluding the outer ring | 7 | 0.101 | — | Yes |
| `study-fluo-fibers` | the bright white branching fibers | 1 | 0.335 | — | No |
| `study-fluo-fibers` | the white filament network | 1 | 0.239 | — | Yes |
| `study-fluo-fibers` | the individual bright elongated nerve fibers | 5 | 0.004 | — | No |
| `study-fluo-fibers` | neurofilament-positive branching processes | 1 | 0.789 | — | No |
| `study-dab-glands` | the brown stained glandular epithelium | 3 | 0.416 | — | No |
| `study-dab-glands` | the brown DAB-positive gland walls | 4 | 0.594 | — | No |
| `study-dab-glands` | all brown tissue, excluding white lumens and blue stroma | 3 | 0.418 | — | No |
| `study-dab-glands` | the brown curved glandular structures | 4 | 0.592 | — | No |
| `study-dab-nuclei` | dark brown stained nuclei | 18 | 0.112 | — | Yes |
| `study-dab-nuclei` | brown positive nuclei, excluding blue nuclei | 17 | 0.110 | — | No |
| `study-dab-nuclei` | the small dark brown oval structures | 6 | 0.032 | — | No |
| `study-dab-nuclei` | Ki67-positive brown nuclei | 13 | 0.097 | — | No |
| `study-cem-mito-26` | mitochondria | 5 | 0.133 | 0.867 | No |
| `study-cem-mito-26` | the oval organelles with internal folds | 3 | 0.149 | 0.965 | Yes |
| `study-cem-mito-26` | the dark outlined oval mitochondria with internal cristae | 1 | 0.082 | 0.691 | No |
| `study-cem-mito-02` | mitochondria | 1 | 0.002 | 0.026 | No |
| `study-cem-mito-02` | the oval organelles with internal folds | 1 | 0.281 | 0.594 | No |
| `study-cem-mito-02` | the dark outlined oval mitochondria with internal cristae | 0 | 0.000 | 0.000 | No |
| `study-cem-mito-06` | mitochondria | 7 | 0.165 | 0.764 | No |
| `study-cem-mito-06` | the oval organelles with internal folds | 2 | 0.077 | 0.791 | No |
| `study-cem-mito-06` | the dark outlined oval mitochondria with internal cristae | 1 | 0.039 | 0.471 | No |
| `study-cem-mito-07` | mitochondria | 1 | 0.001 | 0.000 | No |
| `study-cem-mito-07` | the oval organelles with internal folds | 1 | 0.052 | 0.000 | No |
| `study-cem-mito-07` | the dark outlined oval mitochondria with internal cristae | 0 | 0.000 | 0.000 | No |
| `study-cem-mito-18` | mitochondria | 9 | 0.010 | 0.002 | No |
| `study-cem-mito-18` | the oval organelles with internal folds | 1 | 0.013 | 0.272 | No |
| `study-cem-mito-18` | the dark outlined oval mitochondria with internal cristae | 0 | 0.000 | 0.000 | No |
| `study-cem-mito-25` | mitochondria | 1 | 0.015 | 0.330 | No |
| `study-cem-mito-25` | the oval organelles with internal folds | 2 | 0.038 | 0.416 | No |
| `study-cem-mito-25` | the dark outlined oval mitochondria with internal cristae | 1 | 0.015 | 0.329 | No |
| `study-cem-mito-27` | mitochondria | 7 | 0.210 | 0.936 | Yes |
| `study-cem-mito-27` | the oval organelles with internal folds | 3 | 0.116 | 0.668 | No |
| `study-cem-mito-27` | the dark outlined oval mitochondria with internal cristae | 3 | 0.116 | 0.669 | No |
| `study-cem-mito-33` | mitochondria | 0 | 0.000 | 0.000 | No |
| `study-cem-mito-33` | the oval organelles with internal folds | 3 | 0.058 | 0.514 | No |
| `study-cem-mito-33` | the dark outlined oval mitochondria with internal cristae | 0 | 0.000 | 0.000 | No |

## References

- [Official pixel-level cookbook](https://github.com/Tencent/WeVisOne-VL/blob/main/tutorials/03_segmentation_matting_pipeline.ipynb)
- [Official task prompt builder](https://github.com/Tencent/WeVisOne-VL/blob/main/wevisone_vl/prompts.py)
- [CEM-MitoLab, EMPIAR-11037](https://www.ebi.ac.uk/empiar/EMPIAR-11037/)
- [CEM/MitoNet data publication](https://doi.org/10.1016/j.cels.2022.12.006)
- [QuPath Ki67 source images](https://zenodo.org/records/18302140)
