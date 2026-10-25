"""Retain compact whole/part prompt examples with explicit acquisition provenance."""
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
import requests
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import write_json
from tools.curate_extra_publicdata import write_ngff, register, sha

ORIGINALS = ROOT / 'publicdata/originals/imaging-modes'
UNKNOWN = 'Public ImageJ sample; no separate file-specific redistribution license identified'


def download(url, filename):
    path = ORIGINALS / filename
    if not path.exists():
        response = requests.get(url, timeout=(20, 120))
        response.raise_for_status()
        path.write_bytes(response.content)
    return path


def main():
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    cases = []

    def add(name, pixels, source, mode, title, prompts, original, *, roi=None,
            license=UNKNOWN, attribution='', channels='1,2,3', normalization='dtype',
            scale=None, units=None, channel_names=None, **selection):
        if roi:
            x, y, w, h = roi
            pixels = pixels[y:y+h, x:x+w]
        if pixels.ndim != 3 or pixels.shape[-1] != 3:
            raise ValueError(f'Expected a 2D three-channel view, got {pixels.shape}')
        data = pixels.transpose(2, 0, 1)[None, :, None]
        provenance = {'source': source, 'original_sha256': sha(original),
                      'operation': 'Exact published 2D pixels' if not roi else 'Recorded 2D panel ROI; no resampling or enhancement',
                      'roi_xywh': roi, 'imaging_mode': mode, **selection}
        origin=[0, 0, 0, roi[1]*scale[-2], roi[0]*scale[-1]] if roi and units else None
        write_ngff(name, data, scale=scale, offset=origin, units=units,
                   channel_names=channel_names, provenance=provenance)
        register(name, source, title, [(f'p{i}', p) for i, p in enumerate(prompts[:4], 1)],
                 channels, normalization, license=license, attribution=attribution,
                 selection=provenance, imaging_mode=mode, show_in_examples=False)
        for index, text in enumerate(prompts, 1):
            cases.append({'id': f'{name}-{index}', 'sample': name, 'name': f'p{index}',
                          'text': text, 'channels': channels, 'normalization': normalization})

    source = 'https://www6.pbrc.hawaii.edu/allen/ch01/00-pm.html'
    path = download('https://www6.pbrc.hawaii.edu/allen/ch01/tiff/00-pm.tif', 'paramecium-phase.tif')
    pixels = np.asarray(Image.open(path).convert('RGB'))
    license = 'Educational/research use encouraged; commercial reproduction may require permission. See the Richard Allen collection foreword.'
    credit = 'Klaus Hausmann; Richard D. Allen Image Collection, Pacific Biosciences Research Center, University of Hawaii'
    add('public-phase-paramecium-vacuoles', pixels, source, 'Phase contrast', 'Paramecium with contractile vacuoles',
        ['the complete oval paramecium', 'the entire ciliated organism, excluding the blue background',
         'the bright circular vacuoles inside the organism', 'the two star-shaped contractile vacuoles'],
        path, roi=[0, 0, 744, 521], license=license, attribution=credit,
        source_panel='Figure 0a', calibration='No numerical pixel spacing supplied; not inferred from organism size')
    add('public-phase-paramecium-food', pixels, source, 'Phase contrast', 'Paramecium with stained food vacuoles',
        ['the complete oval paramecium', 'the entire ciliated organism, excluding the blue background',
         'the red circular food vacuoles', 'the black circular food vacuoles'],
        path, roi=[0, 529, 744, 731], license=license, attribution=credit,
        source_panel='Figure 0b', source_notes='Food vacuoles contain red carmine or black India ink; displayed source colors are preserved.')

    url = 'https://iiif.wellcomecollection.org/image/B0009849/full/full/0/default.jpg'
    path = download(url, 'chloroplast-tem.jpg')
    pixels = np.asarray(Image.open(path).convert('RGB'))
    # The source explicitly gives a 4.5 micrometer field width for the full image.
    spacing = 4.5 / pixels.shape[1]
    add('public-em-chloroplast', pixels, 'https://wellcomecollection.org/works/bx3dctp2', 'EM', 'Bean-leaf chloroplast, TEM',
        ['the large oval chloroplast in the center', 'all chloroplasts',
         'the dark parallel membrane stacks inside the central chloroplast', 'the dark round granules inside the central chloroplast'],
        path, license='CC BY 4.0', attribution='Kevin Mackenzie, University of Aberdeen; Wellcome Collection',
        scale=[1, 1, 1, spacing, spacing], units={'x': 'micrometer', 'y': 'micrometer'},
        download_url=url, source_notes='Source-described false-colour TEM, not fluorescence. No extra recoloring or Z projection.',
        calibration='Full image width 4.5 micrometers stated by source; square-pixel spacing = 4.5 / 2400 micrometers.')

    path = download('https://imagej.net/ij/images/FluorescentCells.zip', 'FluorescentCells.zip')
    with zipfile.ZipFile(path) as archive:
        pixels = tifffile.imread(io.BytesIO(archive.read('FluorescentCells.tif'))).transpose(1, 2, 0)
    add('public-fluorescence-endothelial', pixels, 'https://imagej.net/ij/images/FluorescentCells.txt', 'Fluorescence',
        'Endothelial cells: actin, tubulin and DNA',
        ['the complete fluorescent cells', 'the large elongated cell in the lower half',
         'the blue nuclei', 'the red filament network',
         'the blue nucleus inside the large cell in the lower half'],
        path, attribution='Molecular Probes demonstration slide; ImageJ public samples',
        source_notes='Three separate source channels retained: 1 red F-actin (Texas Red X-Phalloidin), 2 green tubulin (Bodipy FL), 3 blue DNA (DAPI).',
        channel_mapping='ImageJ RGB channel order; quantitative channels retained, no rendered overlay imported')

    kidney_url = 'https://gitlab.com/scikit-image/data/-/raw/2cdc5ce89b334d28f06a58c9f0ca21aa6992a5ba/kidney-tissue-fluorescence.tif'
    path = download(kidney_url, 'kidney-tissue-fluorescence.tif')
    # The TIFF stores ZCYX; scikit-image exposes ZYXC. Preserve that channel order.
    kidney = tifffile.imread(path).transpose(0, 2, 3, 1)
    add('public-fluorescence-kidney', kidney[8], 'https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.kidney',
        'Fluorescence', 'Mouse kidney: native confocal optical section',
        ['the kidney tubules', 'the green elongated tubules',
         'the dark oval lumens inside the tubules', 'the bright round glomeruli'],
        path, normalization='percentile', license='CC0; scikit-image kidney dataset', attribution='Genevieve Buckley, Monash Micro Imaging (2018); scikit-image data.kidney',
        scale=[1, 1, 1, 1.24, 1.24], units={'x': 'micrometer', 'y': 'micrometer'},
        source_z_index=8, source_shape=list(kidney.shape), source_notes='One native optical section (Z index 8 of 16), not a projection. Channels retained as provided.',
        calibration='1.24 micrometers per X/Y pixel from the dataset documentation.',
        channel_mapping='Source emission channels 450, 515 and 605 nm in original order. The model display maps channels 1,2,3 to R,G,B as an explicit pseudocolor view, not emission-color reconstruction.')
    add('public-fluorescence-kidney-glomerulus', kidney[8],
        'https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.kidney',
        'Fluorescence', 'Kidney glomerulus and its internal nuclei',
        ['the complete round glomerulus', 'the bright oval cluster in the center',
         'the blue nuclei inside the glomerulus', 'the green mesh inside the glomerulus'],
        path, roi=[375, 245, 137, 150], channels='3,2,1', normalization='percentile',
        scale=[1, 1, 1, 1.24, 1.24], units={'x':'micrometer','y':'micrometer'},
        channel_names=['Emission 450 nm','Emission 515 nm','Emission 605 nm'],
        license='CC0', attribution='Genevieve Buckley, Monash Micro Imaging (2018)',
        source_z_index=8, source_shape=list(kidney.shape),
        source_notes='Recorded native ROI from optical section 8. Source channels remain in 450/515/605 nm order; model maps 3,2,1 to RGB. No Z projection.',
        calibration='1.24 micrometers per X/Y pixel; ROI translation retained.')

    url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5400017/supplementaryFiles'
    path = download(url, 'PMC5400017-images.zip')
    with zipfile.ZipFile(path) as archive:
        normal = np.asarray(Image.open(io.BytesIO(archive.read('10.1177_1177390117690140-fig31.jpg'))).convert('RGB'))
        enlarged = np.asarray(Image.open(io.BytesIO(archive.read('10.1177_1177390117690140-fig30.jpg'))).convert('RGB'))
    source = 'https://doi.org/10.1177/1177390117690140'
    license = 'CC BY-NC 4.0; article authors (2017). Non-commercial educational/research demonstration.'
    add('public-ihc-pancreatic-islet', normal, source, 'Immunohistochemistry', 'Normal pancreatic islet, insulin IHC',
        ['the entire pancreatic islet in the center', 'the central oval cluster containing brown cells',
         'the brown insulin-positive cells', 'the white lumen of the round duct in the upper left'],
        path, license=license, source_panel='Figure 33', attribution='Joseph de Nanassy and Dina El Demellawy (2017); DOI 10.1177/1177390117690140',
        source_notes='Published insulin immunohistochemistry image; no manual segmentation reference. Publication JPEG is suitable for qualitative prompting, not quantitative stain validation.')
    add('public-ihc-hyperplastic-islet', enlarged, source, 'Immunohistochemistry', 'Hyperplastic pancreatic islet, insulin IHC',
        ['the entire large pancreatic islet', 'the large oval structure containing brown stained cells',
         'the brown insulin-positive tissue', 'the white spaces inside the large islet'],
        path, roi=[0, 478, enlarged.shape[1], enlarged.shape[0]-478], license=license,
        source_panel='Figures 31 and 32, lower panel', attribution='Joseph de Nanassy and Dina El Demellawy (2017); DOI 10.1177/1177390117690140',
        source_notes='Native lower publication panel; the published arrow remains visible. No annotation removal or image enhancement. Qualitative example only.')
    add('public-ihc-islet-detail', normal, source, 'Immunohistochemistry', 'Insulin-positive islet: native detail',
        ['the entire pancreatic islet', 'the brown stained cells',
         'the dark brown stained areas, excluding blue cells', 'the pale interior of the pancreatic islet'],
        path, roi=[180, 160, 192, 192], license=license, source_panel='Figure 33, recorded native detail',
        attribution='Joseph de Nanassy and Dina El Demellawy (2017); DOI 10.1177/1177390117690140',
        source_notes='Explicit 192-pixel native ROI from the publication JPEG. No resampling or manual mask. Qualitative example only.')
    write_json(ROOT / 'work/imaging-mode-cases.json', cases)
    print(json.dumps({'examples': len(cases)//4, 'prompt_candidates': len(cases)}), flush=True)


if __name__ == '__main__':
    main()
