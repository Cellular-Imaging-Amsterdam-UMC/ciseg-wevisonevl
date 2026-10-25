"""Curate compact, traceable local/public biological examples without changing sources."""
import argparse
from collections.abc import MutableMapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
from PIL import Image
import requests
import tifffile
import zarr
from numcodecs import Blosc

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.projection import area_downsample
from ciseg_wevisonevl.io import inspect_store,write_json

LOCAL=Path(r'V:\NL-BIOMERO\web\L-Drive\Project B\PublicData')
DATA=ROOT/'publicdata'
READY=DATA/'ome-zarr'
ORIGINALS=DATA/'originals/extra'
UNKNOWN_LICENSE='Publicly downloadable sample; no separate file-specific redistribution license identified'


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def inventory(path):
    return {p.relative_to(path).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(path.rglob('*')) if p.is_file()}


def fetch(url,name,expected_md5=None):
    ORIGINALS.mkdir(parents=True,exist_ok=True)
    target=ORIGINALS/name
    if not target.exists():
        partial=target.with_name(target.name+'.partial')
        print('DOWNLOAD',name,flush=True)
        with requests.get(url,stream=True,timeout=(30,120)) as response:
            response.raise_for_status()
            with partial.open('wb') as stream:
                for block in response.iter_content(1024*1024):stream.write(block)
        partial.rename(target)
    if expected_md5:
        assert hashlib.md5(target.read_bytes()).hexdigest()==expected_md5,target
    return target


def add_catalog(record):
    path=DATA/'catalog.json'
    rows=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else []
    by_name={row['name']:row for row in rows}
    by_name[record['name']]=record
    write_json(path,list(by_name.values()))
    print('READY',record['name'],record['shape'],round(record.get('stored_bytes',0)/1e6,2),'MB',flush=True)


def register(name,source,kind,prompts,channels='1',normalization='percentile',license=UNKNOWN_LICENSE,**extra):
    path=READY/(name+'.ome.zarr')
    field=inspect_store(path,[])[0]
    record={'name':name,'source':source,'kind':kind,'license':license,'suggested_query':prompts[0][1],
            'label_name':prompts[0][0],'channels':channels,'normalization':normalization,
            'shape':list(field.shape),'axes':field.names,'stored_bytes':sum(p.stat().st_size for p in path.rglob('*') if p.is_file()),
            'prompt_presets':[{'name':n,'text':text,'channels':channels} for n,text in prompts],**extra}
    add_catalog(record)
    return record


def copy_exact(source,target):
    before=inventory(source)
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        partial=target.with_name(target.name+'.partial')
        shutil.copytree(source,partial)
        assert inventory(partial)==before
        partial.rename(target)
    assert inventory(target)==before
    assert inventory(source)==before
    return before


def write_ngff(name,data,scale=None,offset=None,units=None,channel_names=None,provenance=None):
    """Write explicitly TCZYX data; retain every input channel and every Z/T plane."""
    assert data.ndim==5
    scale=scale or [1.]*5;offset=offset or [0.]*5;units=units or {}
    target=READY/(name+'.ome.zarr')
    if target.exists():
        np.testing.assert_array_equal(zarr.open_group(str(target),mode='r')['0'][:],data)
        return target
    partial=target.with_name(target.name+'.partial')
    root=zarr.open_group(str(partial),mode='w')
    kinds={'t':'time','c':'channel','z':'space','y':'space','x':'space'}
    axes=[{'name':a,'type':kinds[a],**({'unit':units[a]} if a in units else {})} for a in 'tczyx']
    h,w=data.shape[-2:];levels=[];factor=1
    while True:
        level=str(len(levels))
        array=root.create_dataset(level,shape=(*data.shape[:3],h,w),dtype=data.dtype,chunks=(1,1,1,min(256,h),min(256,w)),compressor=Blosc(cname='zstd',clevel=3))
        array.attrs['_ARRAY_DIMENSIONS']=list('tczyx')
        levels.append({'path':level,'coordinateTransformations':[{'type':'scale','scale':[v*(factor if a in 'xy' else 1) for a,v in zip('tczyx',scale)]},{'type':'translation','translation':offset}]})
        if max(h,w)<=256:break
        h,w=(h+1)//2,(w+1)//2;factor*=2
    for t in range(data.shape[0]):
        for c in range(data.shape[1]):
            for z in range(data.shape[2]):
                plane=data[t,c,z]
                for i in range(len(levels)):
                    root[str(i)][t,c,z]=plane
                    if i+1<len(levels):plane=area_downsample(plane)
    channel_names=channel_names or (['Red','Green','Blue'] if data.shape[1]==3 else [f'Channel {i+1}' for i in range(data.shape[1])])
    colors=['FF0000','00FF00','0000FF','FFFFFF'] if data.shape[1]>1 else ['FFFFFF']
    channels=[]
    for c in range(data.shape[1]):
        lo,hi=float(data[:,c].min()),float(data[:,c].max())
        channels.append({'label':channel_names[c],'color':colors[c%len(colors)],'active':True,'window':{'min':lo,'max':hi,'start':lo,'end':hi}})
    root.attrs.update({'multiscales':[{'version':'0.4','name':name,'axes':axes,'datasets':levels}],
                       'omero':{'name':name,'channels':channels},'publicdata_provenance':provenance or {}})
    ns='http://www.openmicroscopy.org/Schemas/OME/2016-06';ET.register_namespace('',ns)
    ome=ET.Element('{'+ns+'}OME');image=ET.SubElement(ome,'Image',ID='Image:0',Name=name)
    dtype={'float32':'float','float64':'double'}.get(str(data.dtype),str(data.dtype))
    attrs={'ID':'Pixels:0','DimensionOrder':'XYZCT','Type':dtype,**{'Size'+a.upper():str(n) for a,n in zip('tczyx',data.shape)}}
    for a in 'zyx':
        if units.get(a)=='micrometer':attrs.update({'PhysicalSize'+a.upper():str(scale['tczyx'.index(a)]),'PhysicalSize'+a.upper()+'Unit':'µm'})
    pixels=ET.SubElement(image,'Pixels',attrs)
    for c,channel in enumerate(channel_names):ET.SubElement(pixels,'Channel',ID=f'Channel:0:{c}',Name=channel,SamplesPerPixel='1')
    ET.SubElement(pixels,'MetadataOnly')
    (partial/'OME').mkdir()
    ET.ElementTree(ome).write(partial/'OME/METADATA.ome.xml',encoding='utf-8',xml_declaration=True)
    np.testing.assert_array_equal(root['0'][:],data)
    partial.rename(target)
    return target


def local_examples():
    selections=[('dendrite-spines','dendrite and spines',[('dendrite','the main dendritic shaft'),('spines','small dendritic spines attached to the shaft')],'1'),
                ('drosophila-olfactory-neuron','neuronal arbor',[('neuron','the branching neuron and its neurites')],'1'),
                ('mouse-brain-astrocytes-vessels','brain blood vessels and astrocyte processes',[('vessels','blood vessels'),('processes','red branching astrocyte processes')],'1,2,3'),
                ('neural-organoid-section','organoid section neurofilament volume',[('tissue','the complete visible tissue section'),('fibers','branching neurofilament fibers')],'1'),
                ('REAL-LYSOSOME','lysosome time series',[('lysosomes','bright fluorescent lysosomes')],'1')]
    manifests={}
    for original,kind,prompts,channels in selections:
        source=LOCAL/(original+'.ome.zarr');name='local-'+original
        manifests[name]=copy_exact(source,READY/(name+'.ome.zarr'))
        attrs=json.loads((source/'.zattrs').read_text(encoding='utf-8-sig'));prov=attrs.get('publicdata_provenance',{})
        register(name,str(source),kind,prompts,channels,license=prov.get('license',UNKNOWN_LICENSE),
                 original_url=prov.get('source_url'),source_provenance=prov,copy_verification='All source and destination files equal in bytes and SHA-256')
    source=LOCAL/'hippocampal-outgrowth-2d-time.ome.zarr'
    copy=DATA/'local-source-copies'/source.name
    manifests['hippocampal-outgrowth-source']=copy_exact(source,copy)
    root=zarr.open_group(str(copy),mode='r');array=root['0'];attrs=root.attrs['multiscales'][0]
    native_names=[a['name'] for a in attrs['axes']]
    assert native_names==list('tcyx')
    sample=array[[0,96,192],:,:,:][:,:,None]
    transforms=attrs['datasets'][0]['coordinateTransformations']
    values=dict(zip(native_names,next(t['scale'] for t in transforms if t['type']=='scale')))
    units={a['name']:a['unit'] for a in attrs['axes'] if 'unit' in a}
    scale=[values['t']*96,1,1,values['y'],values['x']]
    prov={'source':str(source),'source_time_indices':[0,96,192],'operation':'exact temporal subsampling; no XY resampling'}
    write_ngff('local-neurite-outgrowth-3t',sample,scale=scale,units=units,provenance=prov)
    register('local-neurite-outgrowth-3t',str(source),'2D neuronal outgrowth time series',[('neurites','the thin branching neuronal processes'),('soma','the neuronal cell body')],license='CIL701 Creative Commons Attribution',selection=prov)
    write_ngff('local-neurites-2d',sample[1:2],scale=[1,1,1,values['y'],values['x']],units={a:v for a,v in units.items() if a!='t'},provenance={**prov,'source_time_indices':[96]})
    register('local-neurites-2d',str(source),'2D neuron and neurites',[('neurites','the thin branching neuronal processes'),('soma','the neuronal cell body')],license='CIL701 Creative Commons Attribution',source_time_index=96)
    write_json(DATA/'local-copy-verification.json',manifests)


def small_downloads():
    urls={'fat-cells.zip':'https://imagej.net/ij/images/fat-cells.zip','diatoms.jpg':'https://imagej.net/ij/images/Diatoms.jpg',
          'embryos.jpg':'https://imagej.net/ij/images/embryos.jpg','mib-mito.tif':'https://mib.helsinki.fi/tutorials/WatershedDemo/watershed_demo1.tif'}
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths=list(pool.map(lambda item:fetch(item[1],item[0]),urls.items()))
    for path in paths:
        if path.suffix=='.zip':
            with zipfile.ZipFile(path) as archive:print('ZIP',path.name,[(i.filename,i.file_size) for i in archive.infolist()],flush=True)
        elif path.suffix=='.tif':
            with tifffile.TiffFile(path) as tiff:print('TIFF',path.name,[(s.shape,s.axes) for s in tiff.series],tiff.imagej_metadata,flush=True)
        else:print('IMAGE',path.name,Image.open(path).size,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['local','downloads'])
    args=parser.parse_args()
    READY.mkdir(parents=True,exist_ok=True)
    if args.stage=='local':local_examples()
    elif args.stage=='downloads':small_downloads()
