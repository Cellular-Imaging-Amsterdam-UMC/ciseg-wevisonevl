"""Promote reviewed prompt/image combinations; preserve all original experiment outputs."""
import json,os,sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import numpy as np
import zarr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings,Prompt
from ciseg_wevisonevl.io import inspect_store,write_json
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.inference import Predictor
from tools.curate_extra_publicdata import write_ngff,register

BASELINE=[
 ('organoids_im10',['organoids'],'Foreground agreement with the independent microSAM consensus mask; Dice 0.881.'),
 ('local-dendrite-spines',['dendrite'],'Main shaft only. Spine-head candidates had low recall and are not shown.'),
 ('local-drosophila-olfactory-neuron',['neuron'],'Visually reviewed arbor foreground; no manual segmentation reference.'),
 ('public-skin',['epidermis','dermis'],'Visually reviewed large histological layers; not a cell-level annotation.'),
 ('public-retina',['optic_disc'],'Optic disc only. The previous vessel prompt selected the retinal field and was rejected from the curated gallery.'),
 ('public-diatoms',['diatoms','round','elongated'],'Distinct visible diatom shapes; overlapping label classes are intentional.'),
 ('public-embryos',['embryos'],'Complete visible embryo objects; the less convincing yolk label is omitted.'),
 ('local-CMU1-whole-section',['tissue'],'Overview of the entire acquired tissue scan; not a claim of DAB or cell-level segmentation.'),
 ('public-ki67-lymphoma-section',['tissue'],'Section outline only. DAB-positive nuclei are demonstrated separately at native resolution.')]

NEW=[
 ('local-mouse-brain-astrocytes-vessels',None,'vessel_profile','the bright green vessel cross section','1,2,3','dtype','study-fluo-vessel-1','A local green vessel profile replaces the previous near-whole-field prediction.'),
 ('public-lily-stem',None,'vascular_bundles','the bright green bundles, excluding the outer ring','1,2,3','percentile','study-lily-bundles-4','Visible green bundles are selected while the outer stem ring is excluded.'),
 ('study-fluo-fibers','public-neurofilament-network-roi','fiber_network','the white filament network','1','percentile','study-fluo-fibers-2','Network-level foreground in a recorded Max-projection ROI; not individual axon tracing.'),
 ('study-dab-nuclei','public-ki67-brown-nuclei-detail','dab_positive','dark brown stained nuclei','1,2,3','dtype','study-dab-nuclei-1','A recorded native 192-pixel ROI distinguishes brown positive nuclei from blue negative tissue.'),
 ('study-cem-mito-26','public-em-mitolab-folded-mitochondria','mitochondria','the oval organelles with internal folds','1','dtype','study-cem-mito-26-2','A native 2D EMPIAR patch with paired manual mitochondrial instance labels; selected after exploratory comparisons.'),
 ('study-cem-mito-27','public-em-mitolab-mitochondrial-cluster','mitochondria','mitochondria','1','dtype','study-cem-mito-27-1','A second native 2D EMPIAR patch from the same acquisition; not an independent generalization benchmark.')]


def relative(path,base):return Path(os.path.relpath(path,base)).as_posix()


def main():
    base=ROOT/'test-results/curated-gallery-v2';base.mkdir(parents=True,exist_ok=True)
    baseline_root=ROOT/'test-results/published-gallery';old=json.loads((baseline_root/'manifest.json').read_text())
    path=base/'manifest.json';manifest=json.loads(path.read_text()) if path.exists() else {'model':'4B','projection':'Max','examples':{}}
    catalog_path=ROOT/'publicdata/catalog.json';catalog={r['name']:r for r in json.loads(catalog_path.read_text())}
    selections=[]
    for name,labels,note in BASELINE:
        example={'labels':{},'source_shape':catalog[name]['shape']}
        for label in labels:
            result=deepcopy(old['examples'][name]['labels'][label])
            for key in ['output','measurements','previous_measurements']:
                if result.get(key):result[key]=relative(baseline_root/result[key],base)
            example['labels'][label]=result
        manifest['examples'][name]=example
        selections.append({'name':name,'labels':labels,'review':note})
    for source,alias,label,text,channels,norm,study,note in NEW:
        if not alias:continue
        source_path=ROOT/'publicdata/ome-zarr'/(source+'.ome.zarr');field=inspect_store(source_path,[])[0]
        raw=zarr.open_group(str(source_path),mode='r');data=raw['0'][:]
        ms=raw.attrs['multiscales'][0];tr=ms['datasets'][0]['coordinateTransformations']
        scale=next(t['scale'] for t in tr if t['type']=='scale');offset=next((t['translation'] for t in tr if t['type']=='translation'),[0]*5)
        units={a['name']:a['unit'] for a in ms['axes'] if 'unit' in a}
        provenance=deepcopy(catalog[source].get('selection',{}));provenance.update({'source_study':source,'reviewed_prompt_case':study})
        write_ngff(alias,data,scale=scale,offset=offset,units=units,provenance=provenance)
        ref=source_path.parent/(source+'_reference.npy')
        if ref.exists():np.save(source_path.parent/(alias+'_reference.npy'),np.load(ref,allow_pickle=False),allow_pickle=False)
        register(alias,catalog[source]['source'],'2D EM mitochondria' if 'em-' in alias else 'DAB-positive nuclei' if 'ki67' in alias else 'Fluorescent fiber network',
                 [(label,text)],channels,norm,license=catalog[source]['license'],selection=provenance,review=note)
    catalog={r['name']:r for r in json.loads(catalog_path.read_text())}
    settings=Settings(device='cuda:0',max_new_tokens=4096);predictor=Predictor(settings)
    for source,alias,label,text,channels,norm,study,note in NEW:
        name=alias or source
        result=manifest['examples'].setdefault(name,{'labels':{},'source_shape':catalog[name]['shape']})
        if label not in result['labels']:
            current=replace(settings,normalization=norm);predictor.settings=current
            folder=base/name/label
            outputs=run(ROOT/'publicdata/ome-zarr'/(name+'.ome.zarr'),folder,current,[Prompt(label,text,tuple(map(int,channels.split(','))))],predictor_factory=lambda s:predictor)
            report=json.loads((outputs[0]/'wevisone-run.json').read_text())
            result['labels'][label]={'name':label,'text':text,'channels':list(map(int,channels.split(','))),'status':'complete',
                                     'output':relative(outputs[0],base),'measurements':relative(folder/'measurements.csv',base),
                                     'frames':report['fields'],'max_new_tokens':4096,'selected_prompt_study':study}
            write_json(path,manifest)
        selections.append({'name':name,'labels':[label],'review':note,'selected_prompt_study':study})
    catalog={r['name']:r for r in json.loads(catalog_path.read_text())}
    for record in catalog.values():record['show_in_examples']=False
    for selection in selections:
        name=selection['name'];record=catalog[name];record['show_in_examples']=True;record['review']=selection['review']
        record.setdefault('previous_prompt_presets',record.get('prompt_presets'))
        results=manifest['examples'][name]['labels']
        record['prompt_presets']=[{'name':label,'text':results[label]['text'],'channels':','.join(map(str,results[label]['channels']))} for label in selection['labels']]
        record['suggested_query']=record['prompt_presets'][0]['text'];record['label_name']=record['prompt_presets'][0]['name']
        if name=='local-mouse-brain-astrocytes-vessels':record['normalization']='dtype'
    write_json(catalog_path,list(catalog.values()));write_json(path,manifest)
    write_json(ROOT/'gallery_selection.json',{'curated':True,'date':'2026-10-25','inference_directory':'test-results/curated-gallery-v2',
                                           'selection_policy':'Selected after explicit prompt comparisons and visual review. Not a representative accuracy benchmark.',
                                           'em_2d_only':True,'examples':selections})
    print(json.dumps({'curated_examples':len(selections),'labels':sum(len(s['labels']) for s in selections)}),flush=True)


if __name__=='__main__':main()
