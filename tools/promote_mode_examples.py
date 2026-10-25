"""Prepare meaningful label names, then publish only reviewed whole/part workflows."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import write_json


# Each retained result was inspected against its source. No manual masks were supplied.
REVIEW = {
    'public-phase-paramecium-vacuoles': {
        'labels': {1:'organism', 3:'round_vacuoles'},
        'review':'Visible organism body and six bright circular interior structures. The two-contractile-vacuoles query selected the wrong structures and is excluded; circular masks are not validated contractile-vacuole identities.'},
    'public-phase-paramecium-food': {
        'labels': {1:'organism', 3:'red_food_vacuoles'},
        'review':'Organism body and red carmine-containing food vacuoles. The black-vacuole query selected red structures and is excluded. No completeness claim for every small vacuole.'},
    'public-em-chloroplast': {
        'labels': {1:'chloroplast', 4:'dark_granules'},
        'review':'Central chloroplast outline and three visible dark round granules. The membrane-stack query returned no masks; the generic all-chloroplasts query selected granules instead. Neither is shown. Source-described false-colour TEM, without projection.'},
    'public-fluorescence-endothelial': {
        'labels': {2:'cell_body', 5:'nucleus'},
        'review':'Visible body of the large lower cell and its blue nucleus in the same view. The cell extends beyond the acquired left edge; the mask covers its visible portion. Fine red actin-network prompting was unsuccessful.'},
    'public-fluorescence-kidney': {
        'labels': {4:'glomeruli'},
        'review':'Two conspicuous right-side glomerular profiles in native optical section 8. Other profiles are missed; this is a selected qualitative demonstration, not complete glomerulus counting. Tubule/lumen queries and the smaller glomerulus ROI were not convincing.'},
    'public-ihc-pancreatic-islet': {
        'labels': {1:'islet'},
        'review':'Whole central insulin-stained islet profile. Brown-cell prompting on this overview filled the entire islet instead of separating positive cells; that query is excluded. Publication JPEG, qualitative only.'},
    'public-ihc-hyperplastic-islet': {
        'labels': {3:'brown_tissue'},
        'review':'Selected brown insulin-positive tissue regions within the published enlarged islet panel. Not individual positive-cell counts or validated stain quantification. The original arrow remains visible; whole-islet and lumen queries are excluded.'},
}


def relative_result(result, old_base, new_base):
    result=deepcopy(result)
    for key in ['output','measurements','previous_measurements','partial_output']:
        if result.get(key):result[key]=Path(os.path.relpath(old_base/result[key],new_base)).as_posix()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    exploratory=ROOT/'test-results/imaging-mode-workflows'
    study=json.loads((exploratory/'manifest.json').read_text())
    cases=[]
    for sample,review in REVIEW.items():
        for number,label in review['labels'].items():
            case=deepcopy(study['cases'][f'{sample}-{number}']);case['name']=label
            cases.append({k:case[k] for k in ['id','sample','name','text','channels','normalization']})
    write_json(ROOT/'work/reviewed-mode-cases.json',cases)
    if not args.publish:
        print('Prepared',len(cases),'reviewed workflows with descriptive label names')
        return
    completed_base=ROOT/'test-results/reviewed-mode-workflows'
    completed=json.loads((completed_base/'manifest.json').read_text())
    selection_path=ROOT/'gallery_selection.json'
    selection=json.loads(selection_path.read_text())
    old_base=ROOT/selection['inference_directory']
    old=json.loads((old_base/'manifest.json').read_text())
    base=ROOT/'test-results/curated-gallery-v3';base.mkdir(parents=True,exist_ok=True)
    merged={'model':'4B','projection':'Max','examples':{}}
    # Keep all previously reviewed results and their measurements without modifying them.
    for sample,example in old['examples'].items():
        merged['examples'][sample]={**example,'labels':{name:relative_result(r,old_base,base) for name,r in example['labels'].items()}}
    catalog_path=ROOT/'publicdata/catalog.json'
    catalog={r['name']:r for r in json.loads(catalog_path.read_text())}
    entries={s['name']:s for s in selection['examples']}
    for sample,review in REVIEW.items():
        results={};presets=[]
        for case in [c for c in cases if c['sample']==sample]:
            result=completed['examples'][sample]['labels'][case['name']]
            if result['status']!='complete' or not result['frames'] or any(f['retained_instances']==0 for f in result['frames']):
                raise ValueError('Cannot publish incomplete/empty reviewed result: '+case['id'])
            results[case['name']]=relative_result(result,completed_base,base)
            presets.append({'name':case['name'],'text':case['text'],'channels':case['channels']})
        merged['examples'][sample]={'source_shape':catalog[sample]['shape'],'labels':results}
        catalog[sample].update(show_in_examples=True,prompt_presets=presets,
                               suggested_query=presets[0]['text'],label_name=presets[0]['name'],review=review['review'])
        entries[sample]={'name':sample,'labels':list(results),'review':review['review'],
                         'reviewed_prompt_cases':[c['id'] for c in cases if c['sample']==sample]}
    selection.update(inference_directory='test-results/curated-gallery-v3',examples=list(entries.values()))
    write_json(base/'manifest.json',merged)
    write_json(catalog_path,list(catalog.values()))
    write_json(selection_path,selection)
    print('Published selection:',len(entries),'examples;',sum(len(e['labels']) for e in entries.values()),'labels')


if __name__=='__main__':main()
