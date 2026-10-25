# Publieke voorbeelden en werkelijke segmentaties

Alle voorbeelden gebruiken WeVisOne-VL-4B. De afbeeldingen tonen tijdpunt 0; bij Z-stacks wordt Max-projectie gebruikt. Labelbestanden bevatten alle met succes berekende tijdpunten. Geweigerde voorspellingen zijn geen lege achtergrondmaskers.

[Interactieve HTML-galerij](examples.html) · [Workflow](workflow.md) · [Bronnen en validatie](research.md)

## human_mitosis

![Bronbeeld: human_mitosis](gallery/human_mitosis-input.webp)

**Vorm:** `(1, 1, 1, 512, 512)` (TCZYX) · **type:** Cellen & organoïden · **opslag:** 0.14 MB

### `nuclei` — complete

Prompt: **each bright fluorescent cell nucleus** · kanaal `1`

Tijdpunt 0: 127 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 6.3%.

![Werkelijke voorspelling: nuclei](gallery/human_mitosis-nuclei-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/human_mitosis-nuclei-labels.npz)

**Herkomst:**

- https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.human_mitosis

**Attributie/licentie:**  · CC0; David Root



## immunohistochemistry

![Bronbeeld: immunohistochemistry](gallery/immunohistochemistry-input.webp)

**Vorm:** `(1, 3, 1, 512, 512)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 0.88 MB

### `glands` — complete

Prompt: **colonic glands** · kanaal `1,2,3`

Tijdpunt 0: 4 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 59.7%.

![Werkelijke voorspelling: glands](gallery/immunohistochemistry-glands-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/immunohistochemistry-glands-labels.npz)

**Herkomst:**

- https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.immunohistochemistry

**Attributie/licentie:**  · No known copyright restrictions; CMMI



## cell

![Bronbeeld: cell](gallery/cell-input.webp)

**Vorm:** `(1, 1, 1, 660, 550)` (TCZYX) · **type:** Cellen & organoïden · **opslag:** 0.17 MB

### `cell` — complete

Prompt: **cell** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 6.0%.

![Werkelijke voorspelling: cell](gallery/cell-cell-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/cell-cell-labels.npz)

**Herkomst:**

- https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.cell

**Attributie/licentie:**  · CC0; Paul Mueller et al.



## organoids_im9

![Bronbeeld: organoids_im9](gallery/organoids_im9-input.webp)

**Vorm:** `(1, 1, 1, 1040, 1408)` (TCZYX) · **type:** Cellen & organoïden · **opslag:** 1.06 MB

### `organoids` — failed

Prompt: **organoids** · kanaal `1`

Voorspelling geweigerd: Model generated 210 object tokens but 209 valid boxes. Refusing misaligned mask decoding; try a more specific prompt or an explicit smaller ROI.

**Herkomst:**

- https://zenodo.org/records/14036957

**Attributie/licentie:**  · CC BY 4.0



## organoids_im10

![Bronbeeld: organoids_im10](gallery/organoids_im10-input.webp)

**Vorm:** `(1, 1, 1, 1040, 1408)` (TCZYX) · **type:** Cellen & organoïden · **opslag:** 0.97 MB

### `organoids` — complete

Prompt: **organoids** · kanaal `1`

Tijdpunt 0: 83 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 2.4%. Foreground Dice: 0.881 tegen consensus (geen instance-score).

![Werkelijke voorspelling: organoids](gallery/organoids_im10-organoids-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/organoids_im10-organoids-labels.npz)

**Herkomst:**

- https://zenodo.org/records/14036957

**Attributie/licentie:**  · CC BY 4.0



## local-dendrite-spines

![Bronbeeld: local-dendrite-spines](gallery/local-dendrite-spines-input.webp)

**Vorm:** `(1, 1, 41, 157, 116)` (TCZYX) · **type:** Neuronaal & vaten · **opslag:** 0.09 MB

### `dendrite` — complete

Prompt: **the main dendritic shaft** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 20.4%.

![Werkelijke voorspelling: dendrite](gallery/local-dendrite-spines-dendrite-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-dendrite-spines-dendrite-labels.npz)

### `spines` — complete

Prompt: **small dendritic spines attached to the shaft** · kanaal `1`

Tijdpunt 0: 3 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 1.9%.

![Werkelijke voorspelling: spines](gallery/local-dendrite-spines-spines-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-dendrite-spines-spines-labels.npz)

**Herkomst:**

- https://raw.githubusercontent.com/morphonets/misc/3ffb1bee97666634faf12c060650a6052a30fc26/dataset-demos/SpotSpine/SpotSpine_ImageStack_Test.tif
- https://imagej.net/plugins/spot-spine

**Attributie/licentie:**  · Public SNT/Spot Spine demo; no separate data license declared in the mirror.



## local-drosophila-olfactory-neuron

![Bronbeeld: local-drosophila-olfactory-neuron](gallery/local-drosophila-olfactory-neuron-input.webp)

**Vorm:** `(1, 1, 60, 512, 512)` (TCZYX) · **type:** Neuronaal & vaten · **opslag:** 0.30 MB

### `neuron` — complete

Prompt: **the branching neuron and its neurites** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 2.5%.

![Werkelijke voorspelling: neuron](gallery/local-drosophila-olfactory-neuron-neuron-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-drosophila-olfactory-neuron-neuron-labels.npz)

**Herkomst:**

- Lokale PublicData-collectie; oorspronkelijke URL niet vastgesteld.

**Attributie/licentie:**  · Publicly downloadable sample; no separate file-specific redistribution license identified



## local-mouse-brain-astrocytes-vessels

![Bronbeeld: local-mouse-brain-astrocytes-vessels](gallery/local-mouse-brain-astrocytes-vessels-input.webp)

**Vorm:** `(1, 3, 36, 370, 370)` (TCZYX) · **type:** Neuronaal & vaten · **opslag:** 5.82 MB

### `vessels` — complete

Prompt: **blood vessels** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 93.5%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: vessels](gallery/local-mouse-brain-astrocytes-vessels-vessels-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-mouse-brain-astrocytes-vessels-vessels-labels.npz)

### `processes` — complete

Prompt: **red branching astrocyte processes** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 92.0%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: processes](gallery/local-mouse-brain-astrocytes-vessels-processes-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-mouse-brain-astrocytes-vessels-processes-labels.npz)

**Herkomst:**

- https://imagej.net/ij/images/GFAP-FVII.zip
- https://imagej.net/ij/images/GFAP-FVII.txt

**Attributie/licentie:** Tony Collins / ImageJ for Microscopy · Public ImageJ sample; no separate data license declared.



## local-neural-organoid-section

![Bronbeeld: local-neural-organoid-section](gallery/local-neural-organoid-section-input.webp)

**Vorm:** `(1, 1, 21, 2048, 2048)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 127.95 MB

### `tissue` — complete

Prompt: **the complete visible tissue section** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 46.7%.

![Werkelijke voorspelling: tissue](gallery/local-neural-organoid-section-tissue-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-neural-organoid-section-tissue-labels.npz)

### `fibers` — complete

Prompt: **branching neurofilament fibers** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.3%.

![Werkelijke voorspelling: fibers](gallery/local-neural-organoid-section-fibers-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-neural-organoid-section-fibers-labels.npz)

**Herkomst:**

- https://zenodo.org/records/13899833

**Attributie/licentie:** Yuanzheng Ma, Tsinghua University / Tsinghua-Berkeley Shenzhen Institute · CC-BY-4.0



## local-REAL-LYSOSOME

![Bronbeeld: local-REAL-LYSOSOME](gallery/local-REAL-LYSOSOME-input.webp)

**Vorm:** `(19, 1, 1, 512, 512)` (TCZYX) · **type:** Cellen & organoïden · **opslag:** 1.82 MB

### `lysosomes` — complete

Prompt: **bright fluorescent lysosomes** · kanaal `1`

Tijdpunt 0: 9 voorspelde objecten. 19/19 tijdpunten berekend. Maskerdekking: 9.3%.

![Werkelijke voorspelling: lysosomes](gallery/local-REAL-LYSOSOME-lysosomes-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-REAL-LYSOSOME-lysosomes-labels.npz)

**Herkomst:**

- https://zenodo.org/records/14043236

**Attributie/licentie:**  · Publicly downloadable sample; no separate file-specific redistribution license identified



## local-neurite-outgrowth-3t

![Bronbeeld: local-neurite-outgrowth-3t](gallery/local-neurite-outgrowth-3t-input.webp)

**Vorm:** `(3, 1, 1, 428, 331)` (TCZYX) · **type:** Neuronaal & vaten · **opslag:** 0.58 MB

### `neurites` — complete

Prompt: **the thin branching neuronal processes** · kanaal `1`

Tijdpunt 0: 4 voorspelde objecten. 3/3 tijdpunten berekend. Maskerdekking: 2.2%.

![Werkelijke voorspelling: neurites](gallery/local-neurite-outgrowth-3t-neurites-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-neurite-outgrowth-3t-neurites-labels.npz)

### `soma` — complete

Prompt: **the neuronal cell body** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 3/3 tijdpunten berekend. Maskerdekking: 4.5%.

![Werkelijke voorspelling: soma](gallery/local-neurite-outgrowth-3t-soma-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-neurite-outgrowth-3t-soma-labels.npz)

**Herkomst:**

- Lokale PublicData-collectie; oorspronkelijke URL niet vastgesteld.

**Attributie/licentie:**  · CIL701 Creative Commons Attribution



## local-neurites-2d

![Bronbeeld: local-neurites-2d](gallery/local-neurites-2d-input.webp)

**Vorm:** `(1, 1, 1, 428, 331)` (TCZYX) · **type:** Neuronaal & vaten · **opslag:** 0.20 MB

### `neurites` — complete

Prompt: **the thin branching neuronal processes** · kanaal `1`

Tijdpunt 0: 4 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 2.9%.

![Werkelijke voorspelling: neurites](gallery/local-neurites-2d-neurites-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-neurites-2d-neurites-labels.npz)

### `soma` — complete

Prompt: **the neuronal cell body** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 5.5%.

![Werkelijke voorspelling: soma](gallery/local-neurites-2d-soma-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-neurites-2d-soma-labels.npz)

**Herkomst:**

- Lokale PublicData-collectie; oorspronkelijke URL niet vastgesteld.

**Attributie/licentie:**  · CIL701 Creative Commons Attribution



## public-skin

![Bronbeeld: public-skin](gallery/public-skin-input.webp)

**Vorm:** `(1, 3, 1, 960, 1280)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 3.94 MB

### `epidermis` — complete

Prompt: **the continuous epidermal layer** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 20.8%.

![Werkelijke voorspelling: epidermis](gallery/public-skin-epidermis-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-skin-epidermis-labels.npz)

### `dermis` — complete

Prompt: **the underlying dermis** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 73.2%.

![Werkelijke voorspelling: dermis](gallery/public-skin-dermis-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-skin-dermis-labels.npz)

### `tissue` — complete

Prompt: **all tissue in the section** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 81.5%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: tissue](gallery/public-skin-tissue-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-skin-tissue-labels.npz)

**Herkomst:**

- https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.skin

**Attributie/licentie:**  · See scikit-image dataset-specific attribution



## public-retina

![Bronbeeld: public-retina](gallery/public-retina-input.webp)

**Vorm:** `(1, 3, 1, 1411, 1411)` (TCZYX) · **type:** Neuronaal & vaten · **opslag:** 3.23 MB

### `vessels` — complete

Prompt: **the branching retinal blood vessels** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 76.1%.

![Werkelijke voorspelling: vessels](gallery/public-retina-vessels-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-retina-vessels-labels.npz)

### `optic_disc` — complete

Prompt: **the bright optic disc** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 1.3%.

![Werkelijke voorspelling: optic_disc](gallery/public-retina-optic_disc-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-retina-optic_disc-labels.npz)

### `retina` — complete

Prompt: **the complete retinal field** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 76.1%.

![Werkelijke voorspelling: retina](gallery/public-retina-retina-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-retina-retina-labels.npz)

**Herkomst:**

- https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.retina

**Attributie/licentie:**  · See scikit-image dataset-specific attribution



## public-lily-stem

![Bronbeeld: public-lily-stem](gallery/public-lily-stem-input.webp)

**Vorm:** `(1, 4, 1, 922, 922)` (TCZYX) · **type:** Overige structuren · **opslag:** 5.68 MB

### `bundles` — complete

Prompt: **the vascular bundles in the plant stem** · kanaal `1,2,3`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: bundles](gallery/public-lily-stem-bundles-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-lily-stem-bundles-labels.npz)

### `stem` — complete

Prompt: **the complete plant stem cross-section** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 15.8%.

![Werkelijke voorspelling: stem](gallery/public-lily-stem-stem-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-lily-stem-stem-labels.npz)

**Herkomst:**

- https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.lily

**Attributie/licentie:**  · CC0; Genevieve Buckley, Monash Micro Imaging



## public-diatoms

![Bronbeeld: public-diatoms](gallery/public-diatoms-input.webp)

**Vorm:** `(1, 3, 1, 486, 512)` (TCZYX) · **type:** Overige structuren · **opslag:** 0.79 MB

### `diatoms` — complete

Prompt: **the individual diatoms** · kanaal `1,2,3`

Tijdpunt 0: 5 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 31.9%.

![Werkelijke voorspelling: diatoms](gallery/public-diatoms-diatoms-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-diatoms-diatoms-labels.npz)

### `round` — complete

Prompt: **round diatoms** · kanaal `1,2,3`

Tijdpunt 0: 2 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 14.8%.

![Werkelijke voorspelling: round](gallery/public-diatoms-round-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-diatoms-round-labels.npz)

### `elongated` — complete

Prompt: **elongated diatoms** · kanaal `1,2,3`

Tijdpunt 0: 3 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 16.9%.

![Werkelijke voorspelling: elongated](gallery/public-diatoms-elongated-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-diatoms-elongated-labels.npz)

**Herkomst:**

- https://imagej.net/ij/images/Diatoms.jpg

**Attributie/licentie:**  · Publicly downloadable sample; no separate file-specific redistribution license identified



## public-embryos

![Bronbeeld: public-embryos](gallery/public-embryos-input.webp)

**Vorm:** `(1, 3, 1, 1200, 1600)` (TCZYX) · **type:** Overige structuren · **opslag:** 3.49 MB

### `embryos` — complete

Prompt: **the complete embryos** · kanaal `1,2,3`

Tijdpunt 0: 22 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 3.7%.

![Werkelijke voorspelling: embryos](gallery/public-embryos-embryos-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-embryos-embryos-labels.npz)

### `yolk` — complete

Prompt: **the round yolk sacs** · kanaal `1,2,3`

Tijdpunt 0: 5 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.8%.

![Werkelijke voorspelling: yolk](gallery/public-embryos-yolk-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-embryos-yolk-labels.npz)

**Herkomst:**

- https://imagej.net/ij/images/embryos.jpg

**Attributie/licentie:**  · Publicly downloadable sample; no separate file-specific redistribution license identified



## public-adipose

![Bronbeeld: public-adipose](gallery/public-adipose-input.webp)

**Vorm:** `(1, 3, 1, 1200, 1600)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 4.04 MB

### `adipocytes` — complete

Prompt: **the large round adipocytes** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 92.6%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: adipocytes](gallery/public-adipose-adipocytes-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-adipose-adipocytes-labels.npz)

### `fat` — complete

Prompt: **the entire adipose tissue region** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 51.9%.

![Werkelijke voorspelling: fat](gallery/public-adipose-fat-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-adipose-fat-labels.npz)

### `septa` — complete

Prompt: **connective tissue between the fat cells** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 58.0%.

![Werkelijke voorspelling: septa](gallery/public-adipose-septa-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-adipose-septa-labels.npz)

**Herkomst:**

- https://imagej.net/ij/images/fat-cells.zip

**Attributie/licentie:** Lakishea Hawkins, Department of Clinical Nutrition, University of Maryland Baltimore · Publicly downloadable sample; no separate file-specific redistribution license identified



## public-em-cos7-3d

![Bronbeeld: public-em-cos7-3d](gallery/public-em-cos7-3d-input.webp)

**Vorm:** `(1, 1, 32, 512, 512)` (TCZYX) · **type:** EM · **opslag:** 7.67 MB

### `mitochondria` — complete

Prompt: **mitochondria with visible internal cristae** · kanaal `1`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: mitochondria](gallery/public-em-cos7-3d-mitochondria-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-3d-mitochondria-labels.npz)

### `er` — complete

Prompt: **endoplasmic reticulum membranes** · kanaal `1`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: er](gallery/public-em-cos7-3d-er-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-3d-er-labels.npz)

### `golgi` — complete

Prompt: **the Golgi apparatus** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 63.5%.

![Werkelijke voorspelling: golgi](gallery/public-em-cos7-3d-golgi-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-3d-golgi-labels.npz)

### `lipid_droplets` — complete

Prompt: **lipid droplets** · kanaal `1`

Tijdpunt 0: 4 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 1.7%.

![Werkelijke voorspelling: lipid_droplets](gallery/public-em-cos7-3d-lipid_droplets-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-3d-lipid_droplets-labels.npz)

**Herkomst:**

- https://cellmapchallenge.janelia.org/
- https://janelia-cosem-datasets.s3.amazonaws.com/jrc_cos7-1a/jrc_cos7-1a.zarr/recon-1/em/fibsem-uint8

**Attributie/licentie:**  · CC BY 4.0; CellMap Segmentation Challenge collection

Projection merges EM sections; use accompanying 2D slice for individual organelles

## public-em-cos7-2d

![Bronbeeld: public-em-cos7-2d](gallery/public-em-cos7-2d-input.webp)

**Vorm:** `(1, 1, 1, 512, 512)` (TCZYX) · **type:** EM · **opslag:** 0.25 MB

### `mitochondria` — complete

Prompt: **mitochondria with visible internal cristae** · kanaal `1`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: mitochondria](gallery/public-em-cos7-2d-mitochondria-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-2d-mitochondria-labels.npz)

### `er` — complete

Prompt: **endoplasmic reticulum membranes** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 63.7%.

![Werkelijke voorspelling: er](gallery/public-em-cos7-2d-er-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-2d-er-labels.npz)

### `golgi` — complete

Prompt: **the Golgi apparatus** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 63.9%.

![Werkelijke voorspelling: golgi](gallery/public-em-cos7-2d-golgi-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-2d-golgi-labels.npz)

### `lipid_droplets` — complete

Prompt: **lipid droplets** · kanaal `1`

Tijdpunt 0: 19 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 11.7%.

![Werkelijke voorspelling: lipid_droplets](gallery/public-em-cos7-2d-lipid_droplets-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-cos7-2d-lipid_droplets-labels.npz)

**Herkomst:**

- https://cellmapchallenge.janelia.org/
- https://janelia-cosem-datasets.s3.amazonaws.com/jrc_cos7-1a/jrc_cos7-1a.zarr/recon-1/em/fibsem-uint8

**Attributie/licentie:**  · CC BY 4.0; CellMap Segmentation Challenge collection



## public-em-liver-3d

![Bronbeeld: public-em-liver-3d](gallery/public-em-liver-3d-input.webp)

**Vorm:** `(1, 1, 32, 512, 512)` (TCZYX) · **type:** EM · **opslag:** 7.78 MB

### `mitochondria` — complete

Prompt: **mitochondria with visible internal cristae** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 4.1%.

![Werkelijke voorspelling: mitochondria](gallery/public-em-liver-3d-mitochondria-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-3d-mitochondria-labels.npz)

### `er` — complete

Prompt: **endoplasmic reticulum membranes** · kanaal `1`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: er](gallery/public-em-liver-3d-er-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-3d-er-labels.npz)

### `golgi` — complete

Prompt: **the Golgi apparatus** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 81.9%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: golgi](gallery/public-em-liver-3d-golgi-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-3d-golgi-labels.npz)

### `lipid_droplets` — complete

Prompt: **lipid droplets** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 1.4%.

![Werkelijke voorspelling: lipid_droplets](gallery/public-em-liver-3d-lipid_droplets-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-3d-lipid_droplets-labels.npz)

**Herkomst:**

- https://cellmapchallenge.janelia.org/
- https://janelia-cosem-datasets.s3.amazonaws.com/jrc_mus-liver/jrc_mus-liver.zarr/recon-1/em/fibsem-uint8

**Attributie/licentie:**  · CC BY 4.0; CellMap Segmentation Challenge collection

Projection merges EM sections; use accompanying 2D slice for individual organelles

## public-em-liver-2d

![Bronbeeld: public-em-liver-2d](gallery/public-em-liver-2d-input.webp)

**Vorm:** `(1, 1, 1, 512, 512)` (TCZYX) · **type:** EM · **opslag:** 0.25 MB

### `mitochondria` — complete

Prompt: **mitochondria with visible internal cristae** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 4.2%.

![Werkelijke voorspelling: mitochondria](gallery/public-em-liver-2d-mitochondria-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-2d-mitochondria-labels.npz)

### `er` — complete

Prompt: **endoplasmic reticulum membranes** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 4.4%.

![Werkelijke voorspelling: er](gallery/public-em-liver-2d-er-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-2d-er-labels.npz)

### `golgi` — complete

Prompt: **the Golgi apparatus** · kanaal `1`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 83.9%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: golgi](gallery/public-em-liver-2d-golgi-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-2d-golgi-labels.npz)

### `lipid_droplets` — complete

Prompt: **lipid droplets** · kanaal `1`

Tijdpunt 0: 6 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 10.2%.

![Werkelijke voorspelling: lipid_droplets](gallery/public-em-liver-2d-lipid_droplets-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-liver-2d-lipid_droplets-labels.npz)

**Herkomst:**

- https://cellmapchallenge.janelia.org/
- https://janelia-cosem-datasets.s3.amazonaws.com/jrc_mus-liver/jrc_mus-liver.zarr/recon-1/em/fibsem-uint8

**Attributie/licentie:**  · CC BY 4.0; CellMap Segmentation Challenge collection



## public-em-mitochondria-mib

![Bronbeeld: public-em-mitochondria-mib](gallery/public-em-mitochondria-mib-input.webp)

**Vorm:** `(1, 1, 1, 396, 756)` (TCZYX) · **type:** EM · **opslag:** 0.32 MB

### `mitochondria` — complete

Prompt: **mitochondria with visible cristae** · kanaal `1`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: mitochondria](gallery/public-em-mitochondria-mib-mitochondria-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-mitochondria-mib-mitochondria-labels.npz)

### `membranes` — complete

Prompt: **the membrane-enclosed organelles** · kanaal `1`

Tijdpunt 0: 16 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 21.0%.

![Werkelijke voorspelling: membranes](gallery/public-em-mitochondria-mib-membranes-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-em-mitochondria-mib-membranes-labels.npz)

**Herkomst:**

- https://mib.helsinki.fi/help/main2/user-interface/menu/tools/tools-watershed.html

**Attributie/licentie:**  · Publicly downloadable sample; no separate file-specific redistribution license identified



## local-CMU1-whole-section

![Bronbeeld: local-CMU1-whole-section](gallery/local-CMU1-whole-section-input.webp)

**Vorm:** `(1, 3, 1, 2057, 2875)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 5.36 MB

### `tissue` — complete

Prompt: **the entire tissue section, excluding the white background** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 18.8%.

![Werkelijke voorspelling: tissue](gallery/local-CMU1-whole-section-tissue-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-CMU1-whole-section-tissue-labels.npz)

### `fat` — complete

Prompt: **adipose tissue** · kanaal `1,2,3`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: fat](gallery/local-CMU1-whole-section-fat-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-CMU1-whole-section-fat-labels.npz)

### `stroma` — complete

Prompt: **pink connective tissue** · kanaal `1,2,3`

Tijdpunt 0: 4 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 18.8%.

![Werkelijke voorspelling: stroma](gallery/local-CMU1-whole-section-stroma-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-CMU1-whole-section-stroma-labels.npz)

### `vessels` — complete

Prompt: **blood vessels and their lumens** · kanaal `1,2,3`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: vessels](gallery/local-CMU1-whole-section-vessels-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/local-CMU1-whole-section-vessels-labels.npz)

**Herkomst:**

- https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/

**Attributie/licentie:**  · CC0; OpenSlide test data



## public-prostate-section

![Bronbeeld: public-prostate-section](gallery/public-prostate-section-input.webp)

**Vorm:** `(1, 3, 1, 2500, 2500)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 11.74 MB

### `tissue` — complete

Prompt: **the entire tissue section, excluding the white background** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 45.1%.

![Werkelijke voorspelling: tissue](gallery/public-prostate-section-tissue-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-prostate-section-tissue-labels.npz)

### `glands` — complete

Prompt: **prostatic glands and their lumens** · kanaal `1,2,3`

Tijdpunt 0: 6 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 1.3%.

![Werkelijke voorspelling: glands](gallery/public-prostate-section-glands-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-prostate-section-glands-labels.npz)

### `stroma` — complete

Prompt: **connective tissue stroma** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 45.2%.

![Werkelijke voorspelling: stroma](gallery/public-prostate-section-stroma-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-prostate-section-stroma-labels.npz)

**Herkomst:**

- https://zenodo.org/records/18302140

**Attributie/licentie:**  · CC BY 4.0; Thierry Pecot QuPath workshop



## public-ki67-lymphoma-section

![Bronbeeld: public-ki67-lymphoma-section](gallery/public-ki67-lymphoma-section-input.webp)

**Vorm:** `(1, 3, 1, 2176, 1800)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 7.46 MB

### `tissue` — complete

Prompt: **the entire tissue section, excluding the white background** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 49.7%.

![Werkelijke voorspelling: tissue](gallery/public-ki67-lymphoma-section-tissue-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-ki67-lymphoma-section-tissue-labels.npz)

### `dab_positive` — complete

Prompt: **brown DAB-positive tissue** · kanaal `1,2,3`

Tijdpunt 0: 0 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 0.0%. Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.

![Werkelijke voorspelling: dab_positive](gallery/public-ki67-lymphoma-section-dab_positive-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-ki67-lymphoma-section-dab_positive-labels.npz)

### `stroma` — complete

Prompt: **connective tissue stroma** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 50.4%.

![Werkelijke voorspelling: stroma](gallery/public-ki67-lymphoma-section-stroma-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-ki67-lymphoma-section-stroma-labels.npz)

**Herkomst:**

- https://zenodo.org/records/18302140

**Attributie/licentie:**  · CC BY 4.0; Thierry Pecot QuPath workshop



## public-ki67-lymphoma-dab-roi

![Bronbeeld: public-ki67-lymphoma-dab-roi](gallery/public-ki67-lymphoma-dab-roi-input.webp)

**Vorm:** `(1, 3, 1, 1024, 1024)` (TCZYX) · **type:** Histologie & weefsel · **opslag:** 3.80 MB

### `tissue` — complete

Prompt: **the entire tissue section, excluding the white background** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 99.0%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: tissue](gallery/public-ki67-lymphoma-dab-roi-tissue-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-ki67-lymphoma-dab-roi-tissue-labels.npz)

### `dab_positive` — complete

Prompt: **brown DAB-positive tissue** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 98.8%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: dab_positive](gallery/public-ki67-lymphoma-dab-roi-dab_positive-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-ki67-lymphoma-dab-roi-dab_positive-labels.npz)

### `stroma` — complete

Prompt: **connective tissue stroma** · kanaal `1,2,3`

Tijdpunt 0: 1 voorspelde objecten. 1/1 tijdpunten berekend. Maskerdekking: 99.0%. Grote dekking: controleer voorgrond en achtergrond in de overlay.

![Werkelijke voorspelling: stroma](gallery/public-ki67-lymphoma-dab-roi-stroma-overlay.webp)

[Download uint32-labels en tijdindexen](downloads/public-ki67-lymphoma-dab-roi-stroma-labels.npz)

**Herkomst:**

- https://zenodo.org/records/18302140

**Attributie/licentie:**  · CC BY 4.0; Thierry Pecot QuPath workshop
