"""Retrieve small paired 2D EM images/masks from EMPIAR-11037 using verified ZIP ranges."""
import argparse,io,json,struct,sys,zlib,zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from PIL import Image
import requests,tifffile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import write_json
from tools.curate_extra_publicdata import write_ngff,register,sha

URL='https://ftp.ebi.ac.uk/empiar/world_availability/11037/data/cem_mitolab.zip'


def ranged(start,end):
    r=requests.get(URL,headers={'Range':f'bytes={start}-{end}'},timeout=(30,120));r.raise_for_status()
    if r.status_code!=206 or len(r.content)!=end-start+1:raise RuntimeError('Server did not honor exact ZIP range')
    return r.content


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include',default='',help='Comma-separated native survey indices for a documented visual follow-up')
    parser.add_argument('--cases',type=Path,default=ROOT/'work/cem-prompt-cases.json')
    args=parser.parse_args()
    folder=ROOT/'publicdata/originals/cem-mitolab';folder.mkdir(parents=True,exist_ok=True)
    index=folder/'central-directory.zip'
    if not index.exists():
        r=requests.get(URL,headers={'Range':'bytes=-65536'},timeout=60);r.raise_for_status();assert r.status_code==206
        total=int(r.headers['Content-Range'].split('/')[-1]);position=r.content.rfind(b'PK\x05\x06')
        end=struct.unpack_from('<4s4H2IH',r.content,position);offset=end[6]
        index.write_bytes(ranged(offset,total-1));write_json(folder/'archive.json',{'url':URL,'total_bytes':total,'central_offset':offset})
    info=json.loads((folder/'archive.json').read_text());archive=zipfile.ZipFile(io.BytesIO(index.read_bytes()))
    names=set(archive.namelist());groups={}
    for name in sorted(names):
        if '/images/' in name and name.endswith('.tiff') and '_2D/' in name:
            groups.setdefault(name.split('/')[1],[]).append(name)
    # Fixed broad sample, emphasizing larger genuine 2D fields and diverse acquisitions.
    order=sorted(groups,key=lambda g:(-max(archive.getinfo(n).file_size for n in groups[g]),g))
    candidates=[]
    for group in order:
        for name in groups[group][:2]:
            pair=name.replace('/images/','/masks/')
            if pair in names:candidates.append((name,pair))
        if len(candidates)>=32:break
    def extract(member,target):
        if target.exists():return
        item=archive.getinfo(member);position=item.header_offset+info['central_offset']
        header=ranged(position,position+29);assert header[:4]==b'PK\x03\x04'
        name_length,extra=struct.unpack_from('<HH',header,26);start=position+30+name_length+extra
        compressed=ranged(start,start+item.compress_size-1)
        data=zlib.decompress(compressed,-15) if item.compress_type==zipfile.ZIP_DEFLATED else compressed
        assert len(data)==item.file_size and zlib.crc32(data)&0xffffffff==item.CRC
        target.write_bytes(data)
    def pair_job(args):
        number,(image,mask)=args;extract(image,folder/f'{number:02d}-image.tif');extract(mask,folder/f'{number:02d}-mask.tif')
        return number,image,mask
    with ThreadPoolExecutor(max_workers=4) as pool:downloaded=list(pool.map(pair_job,enumerate(candidates,1)))
    records=[];cases=[]
    for number,image_member,mask_member in downloaded:
        image=tifffile.imread(folder/f'{number:02d}-image.tif');mask=tifffile.imread(folder/f'{number:02d}-mask.tif')
        assert image.ndim==mask.ndim==2 and image.shape==mask.shape
        count=len(np.unique(mask[mask>0]));fraction=float(np.count_nonzero(mask)/mask.size)
        contrast=float(np.percentile(image,95)-np.percentile(image,5))
        records.append({'number':number,'image_member':image_member,'mask_member':mask_member,'objects':count,'foreground_fraction':fraction,'contrast':contrast,'shape':list(image.shape)})
    # Retain all samples; prepare the clearest object-scale candidates for actual VLM comparison.
    qualified=[r for r in records if 1<=r['objects']<=12 and .08<=r['foreground_fraction']<=.7 and r['contrast']>75]
    qualified.sort(key=lambda r:(r['objects']>5,-r['foreground_fraction'],-r['contrast']))
    selected=[];used=set()
    for record in qualified:
        group=record['image_member'].split('/')[1]
        if group in used:continue
        selected.append(record);used.add(group)
        if len(selected)==6:break
    if args.include:
        chosen={int(v) for v in args.include.split(',')};selected=[r for r in records if r['number'] in chosen]
    for record in selected:
        number=record['number'];image=tifffile.imread(folder/f'{number:02d}-image.tif');mask=tifffile.imread(folder/f'{number:02d}-mask.tif')
        name=f'study-cem-mito-{number:02d}'
        provenance={'source':'https://www.ebi.ac.uk/empiar/EMPIAR-11037/','archive':URL,'image_member':record['image_member'],'mask_member':record['mask_member'],
                    'image_sha256':sha(folder/f'{number:02d}-image.tif'),'mask_sha256':sha(folder/f'{number:02d}-mask.tif'),
                    'operation':'Exact native 2D EM patch and paired instance annotation; no projection','calibration':'No physical pixel spacing supplied; not invented',
                    'selection':'Exploratory sample selected for visible mitochondrial foreground and low/moderate instance count; not a representative benchmark'}
        write_ngff(name,image[None,None,None],provenance=provenance)
        np.save(ROOT/'publicdata/ome-zarr'/(name+'_reference.npy'),mask,allow_pickle=False)
        prompts=['mitochondria','the oval organelles with internal folds','the dark outlined oval mitochondria with internal cristae']
        register(name,provenance['source'],'2D TEM/FIB-SEM mitochondria',[(f'p{i}',p) for i,p in enumerate(prompts,1)],'1','dtype',license='EMPIAR-11037/CEM-MitoLab; original attribution retained',selection=provenance,show_in_examples=False)
        for i,text in enumerate(prompts,1):cases.append({'id':name+'-'+str(i),'sample':name,'name':'mitochondria','text':text,'channels':'1','normalization':'dtype'})
    write_json(folder/'sample-index.json',records);write_json(args.cases,cases)
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,8,figsize=(18,10),layout='constrained')
    for ax,record in zip(axes.flat,records):
        number=record['number'];image=tifffile.imread(folder/f'{number:02d}-image.tif');mask=tifffile.imread(folder/f'{number:02d}-mask.tif')>0
        rgb=np.stack([image]*3,-1);rgb[mask]=(.7*rgb[mask]+.3*np.array([255,40,120])).astype(np.uint8)
        ax.imshow(rgb);ax.set_title(f'{number:02d}: {record["objects"]} objects, {record["foreground_fraction"]:.2f}',fontsize=8);ax.axis('off')
    fig.savefig(ROOT/'work/cem-source-survey.jpg',dpi=110);plt.close(fig)
    print(json.dumps({'downloaded_pairs':len(records),'selected_for_prompt_testing':[r['number'] for r in selected],'cases':len(cases)}),flush=True)


if __name__=='__main__':main()
