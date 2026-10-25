"""Prepare explicit 2D fluorescence/DAB views and prompt comparisons; retain source pixels."""
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import zarr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import inspect_store,write_json
from tools.curate_extra_publicdata import write_ngff,register


def main():
    cases=[]
    def add(name,source,channels,prompts,normalization='percentile',roi=None):
        original=ROOT/'publicdata/ome-zarr'/(source+'.ome.zarr')
        field=inspect_store(original,[])[0]
        raw=field.pixels(list(range(1,field.cyx_shape[0]+1)),0,'Max')
        pixels=np.stack([raw[c] for c in range(field.cyx_shape[0])])[None,:,None]
        if roi:
            y,x,h,w=roi;pixels=pixels[:,:,:,y:y+h,x:x+w]
        group=zarr.open_group(str(original),mode='r');ms=group.attrs['multiscales'][0]
        scales={a:1. for a in field.names};offsets={a:0. for a in field.names}
        for tr in ms['datasets'][0].get('coordinateTransformations',[])+ms.get('coordinateTransformations',[]):
            for a,value in zip(field.names,tr[tr['type']]):
                if tr['type']=='scale':scales[a]*=value;offsets[a]*=value
                else:offsets[a]+=value
        units={a['name']:a['unit'] for a in field.axes if 'unit' in a and a['name'] in 'xy'}
        origin=[0,0,0,offsets['y']+(roi[0]*scales['y'] if roi else 0),offsets['x']+(roi[1]*scales['x'] if roi else 0)]
        provenance={'source_example':source,'operation':'Explicit Max projection at timepoint 0' if field.z_planes>1 else 'Timepoint 0 without projection',
                    'roi_yxhw':roi,'source_z_planes':field.z_planes,'note':'A derived study view; original input is unchanged'}
        write_ngff(name,pixels,scale=[1,1,1,scales['y'],scales['x']],offset=origin,units=units,provenance=provenance)
        original_record=next(r for r in json.loads((ROOT/'publicdata/catalog.json').read_text()) if r['name']==source)
        register(name,original_record.get('original_url') or original_record['source'],'2D prompt study',[(f'p{i}',p) for i,p in enumerate(prompts[:4],1)],
                 channels,normalization,license=original_record['license'],selection=provenance)
        for i,text in enumerate(prompts):cases.append({'id':name+'-'+str(i+1),'sample':name,'name':'target','text':text,'channels':channels,'normalization':normalization})
    add('study-fluo-vessel','local-mouse-brain-astrocytes-vessels','1,2,3',
        ['the bright green vessel cross section','the compact bright green fluorescent structure in the center','green blood vessel wall','the green oval structure, excluding the red branching fibers'],normalization='dtype')
    add('study-fluo-processes','local-mouse-brain-astrocytes-vessels','1,2,3',
        ['the red branching fibers','the thin red tree-like processes','red fluorescent astrocyte processes','all red filaments, excluding the green structure'],normalization='dtype')
    add('study-fluo-spines','local-dendrite-spines','1',
        ['the small bright rounded protrusions attached to the main branch','dendritic spine heads','small white bulb-shaped protrusions on the dendrite','the bright rounded spine at the upper left'])
    add('study-lily-bundles','public-lily-stem','1,2,3',
        ['the bright green oval vascular bundles','bright green circular clusters','the green ring-shaped structures inside the plant stem','the bright green bundles, excluding the outer ring'])
    add('study-fluo-fibers','local-neural-organoid-section','1',
        ['the bright white branching fibers','the white filament network','the individual bright elongated nerve fibers','neurofilament-positive branching processes'],roi=(256,256,1024,1024))
    add('study-dab-glands','immunohistochemistry','1,2,3',
        ['the brown stained glandular epithelium','the brown DAB-positive gland walls','all brown tissue, excluding white lumens and blue stroma','the brown curved glandular structures'],normalization='dtype')
    # Smaller native ROI keeps sparse brown positive nuclei visible and reduces dense-output truncation.
    rgb=zarr.open_group(str(ROOT/'publicdata/ome-zarr/public-ki67-lymphoma-dab-roi.ome.zarr'),mode='r')['0'][0,:,0].transpose(1,2,0).astype(float)
    brown=(rgb[:,:,0]>1.15*rgb[:,:,2])&(rgb.mean(axis=2)<175)&(rgb[:,:,0]>40)
    from scipy.ndimage import uniform_filter
    density=uniform_filter(brown.astype(float),size=192)
    y,x=np.unravel_index(np.argmax(density[96:-96,96:-96]),density[96:-96,96:-96].shape);y+=96;x+=96
    add('study-dab-nuclei','public-ki67-lymphoma-dab-roi','1,2,3',
        ['dark brown stained nuclei','brown positive nuclei, excluding blue nuclei','the small dark brown oval structures','Ki67-positive brown nuclei'],normalization='dtype',roi=(int(y-96),int(x-96),192,192))
    write_json(ROOT/'work/prompt-study-cases.json',cases)
    print('Prepared',len(cases),'prompt candidates')


if __name__=='__main__':main()
