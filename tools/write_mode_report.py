"""Publish all modality prompt outcomes and distinguish positive selection from accuracy."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from tools.promote_mode_examples import REVIEW


def main():
    results=json.loads((ROOT/'test-results/imaging-modes-v3/summary.json').read_text())
    workflow=json.loads((ROOT/'test-results/imaging-mode-workflows/manifest.json').read_text())
    # Prefer the direct study for repeated cases; add only genuinely new descriptions/views.
    for key,value in workflow['cases'].items():results.setdefault(key,value)
    selected={f'{sample}-{number}' for sample,review in REVIEW.items() for number in review['labels']}
    lines=['# Whole structures and their parts','',
           'This follow-up tested **37 target descriptions across nine prepared 2D views**, covering phase contrast, EM, fluorescence and chromogenic immunohistochemistry. Seven new views with eleven reviewed labels were retained. Together with the previous 52 comparisons, 89 candidate queries have been evaluated. Repeated final workflow runs are not counted as new candidates.','',
           'The gallery is positively selected after visual review. No manual reference masks are supplied for these new examples, so object counts and nonempty masks are not accuracy measurements. These examples do not establish reliability across a modality. Unselected outputs and original images remain local.','',
           '## How the model sees the images','',
           'Every target uses one RGB view: a selected single source channel copied to R/G/B, or three source channels assigned to R/G/B in the specified order. Other source channels remain available for measurements. Intensity scaling affects only this view; it is not a choice between composite and separate-channel inference. The same channel map and scaling were used within each comparison.','',
           'The kidney overview maps source channels 1,2,3 to RGB as recorded pseudocolor. The extra glomerulus ROI maps 3,2,1 to RGB, matching the original 605/515/450 nm emission order. They are distinct, documented study views.','',
           '## Retained examples','',
           '| Mode | View | Labels and exact target descriptions | Visual review |','| --- | --- | --- | --- |']
    catalog={r['name']:r for r in json.loads((ROOT/'publicdata/catalog.json').read_text())}
    for sample,review in REVIEW.items():
        descriptions='<br>'.join(f"`{label}`: {results[f'{sample}-{number}']['text']}" for number,label in review['labels'].items())
        lines.append(f"| {catalog[sample]['imaging_mode']} | [{sample}](examples.html#{sample}) | {descriptions} | {review['review']} |")
    lines+=['','## Sources, calibration and image limitations','',
            '- **Phase contrast:** [Klaus Hausmann / Richard Allen collection, Figure 0](https://www6.pbrc.hawaii.edu/allen/ch01/00-pm.html). Two native panel crops, with source color preserved. The collection encourages educational/research use; [commercial reproduction may need permission](https://www6.pbrc.hawaii.edu/allen/foreword.html). No invented calibration.',
            '- **EM:** [Kevin Mackenzie, University of Aberdeen, Wellcome Collection](https://wellcomecollection.org/works/bx3dctp2), CC BY 4.0. The source describes the image as false-colour TEM; no extra recoloring or Z projection was applied. Its stated 4.5-micrometer field width gives approximately 0.001875 micrometers per pixel for the 2400-pixel image, using square pixels. Measurements retain this calibration derivation.',
            '- **Fluorescence, endothelial cells:** [Molecular Probes / ImageJ source](https://imagej.net/ij/images/FluorescentCells.txt). Separate red F-actin, green tubulin and blue DNA channels are retained. The native acquisition contains visible information text and cells touching the field boundary. No separate file-specific redistribution license was identified.',
            '- **Fluorescence, kidney:** [Genevieve Buckley, Monash Micro Imaging, scikit-image data.kidney](https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.kidney), CC0. One native optical section (Z index 8 of 16), not a projection. XY spacing is 1.24 micrometers; the exploratory ROI preserves its physical translation. The TIFF is ZCYX; it is explicitly transposed for ZYXC access before writing TCZYX.',
            '- **IHC:** Joseph de Nanassy and Dina El Demellawy (2017), [DOI 10.1177/1177390117690140](https://doi.org/10.1177/1177390117690140), Figures 31-33, CC BY-NC 4.0. Published insulin-stained pancreatic islet JPEGs are qualitative educational/research examples. The original annotation arrow remains visible. There is no numerical pixel calibration; magnification alone was not converted to micrometers.','',
            '## What failed','',
            'The model confused black and red food vacuoles, failed to identify chloroplast membrane stacks, and returned a near-whole-field mask for generic kidney tubules. The glomerulus crop often selected neighboring tubules instead. Several IHC cell/space prompts selected a whole islet or incomplete subregions. Those results are omitted from the gallery, not silently treated as successful biological segmentation. The retained IHC overview shows an islet outline, while the enlarged example shows brown tissue regions; neither demonstrates validated positive-cell separation.','',
            '## All additional candidates','',
            '| Study view | Description | Predicted objects | Foreground fraction | Retained |','| --- | --- | ---: | ---: | --- |']
    for key,case in results.items():
        lines.append(f"| `{case['sample']}` | {case['text']} | {case.get('objects','failed')} | {case.get('coverage',0):.3f} | {'Yes' if key in selected else 'No'} |")
    lines+=['','## Reproduction','',
            'In the eleven retained final reruns, nine binary masks matched their previous workflow masks exactly. The organism and chloroplast masks each differed at one pixel. Deterministic decoding does not guarantee bit-identical output on every rerun.','',
            'All scripts run from the repository root with the local Python environment. Full sources, stores and research results remain ignored by Git. The public site contains only compact previews, labels, CSVs and source metadata.','',
            '```powershell',
            '.venv\\Scripts\\python tools\\prepare_mode_examples.py',
            '.venv\\Scripts\\python tools\\test_prompt_candidates.py --cases work\\imaging-mode-cases.json --output test-results\\imaging-modes-v3',
            '.venv\\Scripts\\python tools\\run_mode_workflows.py --cases work\\imaging-mode-cases.json',
            '.venv\\Scripts\\python tools\\promote_mode_examples.py',
            '.venv\\Scripts\\python tools\\run_mode_workflows.py --cases work\\reviewed-mode-cases.json --output test-results\\reviewed-mode-workflows',
            '.venv\\Scripts\\python tools\\promote_mode_examples.py --publish',
            '.venv\\Scripts\\python tools\\write_mode_report.py',
            '.venv\\Scripts\\python tools\\build_docs_site.py',
            '```','',
            'Final gallery masks were produced through the actual workflow, with descriptive label names and one CSV per example download. The CLI still supports at most four active targets in any single workflow run.','']
    (ROOT/'docs/imaging-modes.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print('Reported',len(results),'modality candidates;',len(selected),'selected labels')


if __name__=='__main__':main()
