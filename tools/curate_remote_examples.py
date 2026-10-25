"""Additional public EM, whole-section, plant and tissue examples for the local launcher."""
import argparse,csv,hashlib,io,json,os,shutil,sys,zipfile
from collections.abc import MutableMapping
from pathlib import Path
import numpy as np
from PIL import Image
import requests,tifffile,zarr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.curate_extra_publicdata import (DATA,READY,ORIGINALS,LOCAL,sha,inventory,write_ngff,register)


def online():
    os.environ['SKIMAGE_DATADIR']=str(DATA/'.cache/skimage')
    from skimage import data
    examples=[('skin',data.skin,[('epidermis','the continuous epidermal layer'),('dermis','the underlying dermis'),('tissue','all tissue in the section')]),
              ('retina',data.retina,[('vessels','the branching retinal blood vessels'),('optic_disc','the bright optic disc'),('retina','the complete retinal field')])]
    for key,loader,prompts in examples:
        pixels=loader();original=ORIGINALS/(key+'.tif')
        if not original.exists():tifffile.imwrite(original,pixels)
        write_ngff('public-'+key,pixels.transpose(2,0,1)[None,:,None],provenance={'source':'scikit-image data.'+key,'original_sha256':sha(original)})
        register('public-'+key,'https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.'+key,
                 'histology' if key=='skin' else 'retinal fundus',prompts,'1,2,3','dtype',
                 license='See scikit-image dataset-specific attribution',original_sha256=sha(original))
    lily=data.lily();original=ORIGINALS/'lily.tif'
    if not original.exists():tifffile.imwrite(original,lily)
    write_ngff('public-lily-stem',lily.transpose(2,0,1)[None,:,None],scale=[1,1,1,1.24,1.24],units={'y':'micrometer','x':'micrometer'},
               channel_names=['Fluorescence 1','Fluorescence 2','Fluorescence 3','Fluorescence 4'],provenance={'source':'scikit-image data.lily','note':'Four fluorescence channels; channel 4 is not alpha'})
    register('public-lily-stem','https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.lily','plant stem confocal section',
             [('bundles','the vascular bundles in the plant stem'),('stem','the complete plant stem cross-section')],'1,2,3',license='CC0; Genevieve Buckley, Monash Micro Imaging',original_sha256=sha(original))
    for file,name,kind,prompts in [('diatoms.jpg','public-diatoms','diatoms',[('diatoms','the individual diatoms'),('round','round diatoms'),('elongated','elongated diatoms')]),
                                  ('embryos.jpg','public-embryos','embryos',[('embryos','the complete embryos'),('yolk','the round yolk sacs')])]:
        original=ORIGINALS/file;pixels=np.asarray(Image.open(original).convert('RGB'))
        write_ngff(name,pixels.transpose(2,0,1)[None,:,None],provenance={'original_sha256':sha(original),'operation':'decoded RGB pixels; no image enhancement'})
        register(name,'https://imagej.net/ij/images/'+('Diatoms.jpg' if file=='diatoms.jpg' else file),kind,prompts,'1,2,3','dtype',original_sha256=sha(original))
    with zipfile.ZipFile(ORIGINALS/'fat-cells.zip') as archive:payload=archive.read('fat-cells.tif')
    original=ORIGINALS/'fat-cells.tif'
    if not original.exists():original.write_bytes(payload)
    pixels=tifffile.imread(original)
    with tifffile.TiffFile(original) as tiff:info=tiff.imagej_metadata or {}
    write_ngff('public-adipose',pixels.transpose(2,0,1)[None,:,None],provenance={'source':'https://imagej.net/ij/images/fat-cells.zip','ImageJ':info,'original_sha256':sha(original)})
    register('public-adipose','https://imagej.net/ij/images/fat-cells.zip','osmium-fixed human subcutaneous adipose tissue',
             [('adipocytes','the large round adipocytes'),('fat','the entire adipose tissue region'),('septa','connective tissue between the fat cells')],
             '1,2,3','dtype',attribution='Lakishea Hawkins, Department of Clinical Nutrition, University of Maryland Baltimore',source_notes=info,original_sha256=sha(original))
    original=ORIGINALS/'mib-mito.tif';pixels=np.asarray(Image.open(original))
    write_ngff('public-em-mitochondria-mib',pixels[None,None,None],provenance={'source':'https://mib.helsinki.fi/tutorials/WatershedDemo/watershed_demo1.tif','original_sha256':sha(original)})
    register('public-em-mitochondria-mib','https://mib.helsinki.fi/help/main2/user-interface/menu/tools/tools-watershed.html','EM organelles',
             [('mitochondria','mitochondria with visible cristae'),('membranes','the membrane-enclosed organelles')],original_sha256=sha(original),download_url='https://mib.helsinki.fi/tutorials/WatershedDemo/watershed_demo1.tif')


def histology():
    import openslide
    original=LOCAL/'CMU-1.svs';copy=ORIGINALS/'local-CMU-1.svs';checksum=sha(original)
    if not copy.exists():shutil.copy2(original,copy)
    assert sha(copy)==checksum and sha(original)==checksum
    inputs=[('local-CMU1-whole-section',copy,str(original),2,'H&E whole-section overview','CC0; OpenSlide test data',
             [('tissue','the entire tissue section, excluding the white background'),('fat','adipose tissue'),('stroma','pink connective tissue'),('vessels','blood vessels and their lumens')])]
    for name,file in [('public-prostate-section','prostate_5.ome.tif'),('public-ki67-lymphoma-section','ki67_lymphoma.ndpi')]:
        path=ORIGINALS/file
        if path.exists():
            inputs.append((name,path,'https://zenodo.org/records/18302140',None,'histological section','CC BY 4.0; Thierry Pecot QuPath workshop',
                           [('tissue','the entire tissue section, excluding the white background'),('dab_positive','brown DAB-positive tissue'),('stroma','connective tissue stroma')]))
    for name,path,source,level,kind,license,prompts in inputs:
        if path.name.endswith('.ome.tif'):
            with tifffile.TiffFile(path) as tiff:
                series=tiff.series[0]
                level=next((i for i,layer in enumerate(series.levels) if max(layer.shape[:2])<=3000),len(series.levels)-1)
                pixels=series.levels[level].asarray()
                level0=list(series.shape[:2][::-1])
            prov={'source':source,'original_sha256':sha(path),'source_level':level,'source_level0_size_xy':level0,
                  'operation':'Complete acquired image extent at existing OME-TIFF pyramid level; no crop','calibration':'No physical pixel calibration specified in source OME-XML'}
            write_ngff(name,pixels.transpose(2,0,1)[None,:,None],provenance=prov)
            register(name,source,kind,[('tissue','the entire tissue section, excluding the white background'),('glands','prostatic glands and their lumens'),('stroma','connective tissue stroma')],
                     '1,2,3','dtype',license=license,selection=prov)
            continue
        slide=openslide.OpenSlide(path)
        if level is None:level=next((i for i,(w,h) in enumerate(slide.level_dimensions) if max(w,h)<=3000),len(slide.level_dimensions)-1)
        pixels=np.asarray(slide.read_region((0,0),level,slide.level_dimensions[level]).convert('RGB'))
        units={};scale=[1.,1.,1.,1.,1.]
        if 'openslide.mpp-x' in slide.properties and 'openslide.mpp-y' in slide.properties:
            scale[-1]=float(slide.properties['openslide.mpp-x'])*slide.dimensions[0]/pixels.shape[1]
            scale[-2]=float(slide.properties['openslide.mpp-y'])*slide.dimensions[1]/pixels.shape[0]
            units={'x':'micrometer','y':'micrometer'}
        prov={'source':source,'original_sha256':sha(path),'source_level':level,'source_level0_size_xy':list(slide.dimensions),
              'operation':'Complete acquired image extent at an existing pyramid level; no spatial crop',
              'calibration':'MPP multiplied by independent X/Y level dimension ratios' if units else 'No physical pixel calibration supplied'}
        write_ngff(name,pixels.transpose(2,0,1)[None,:,None],scale=scale,units=units,provenance=prov)
        register(name,source,kind,prompts,'1,2,3','dtype',license=license,selection=prov)
        if 'ki67' in name:
            # Native ROI chosen deterministically from strongest brown signal in overview.
            rgb=pixels.astype(float);score=(rgb[:,:,0]-rgb[:,:,2])*(255-rgb.mean(axis=2))/255
            yy,xx=np.unravel_index(np.argmax(score),score.shape)
            x=int(np.clip(xx*slide.dimensions[0]/pixels.shape[1]-512,0,slide.dimensions[0]-1024))
            y=int(np.clip(yy*slide.dimensions[1]/pixels.shape[0]-512,0,slide.dimensions[1]-1024))
            roi=np.asarray(slide.read_region((x,y),0,(1024,1024)).convert('RGB'))
            rscale=[1,1,1,float(slide.properties.get('openslide.mpp-y',1)),float(slide.properties.get('openslide.mpp-x',1))]
            selection={**prov,'source_level':0,'roi_xywh':[x,y,1024,1024],'operation':'Native-resolution ROI centered on strongest brown pixel in overview; exploratory selection, not an annotation'}
            write_ngff('public-ki67-lymphoma-dab-roi',roi.transpose(2,0,1)[None,:,None],scale=rscale,offset=[0,0,0,y*rscale[-2] if units else 0,x*rscale[-1] if units else 0],units=units,provenance=selection)
            register('public-ki67-lymphoma-dab-roi',source,'Ki67 IHC DAB detail',prompts,'1,2,3','dtype',license=license,selection=selection)
        slide.close()


class HTTPArrayStore(MutableMapping):
    def __init__(self,url,cache):self.url=url.rstrip('/');self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
    def __getitem__(self,key):
        path=self.cache/key
        if not path.exists():
            r=requests.get(self.url+'/'+key,timeout=(30,120))
            if r.status_code==404:raise KeyError(key)
            r.raise_for_status();path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(r.content)
        return path.read_bytes()
    def __setitem__(self,key,value):raise TypeError('read-only remote input')
    def __delitem__(self,key):raise TypeError('read-only remote input')
    def __iter__(self):return (p.relative_to(self.cache).as_posix() for p in self.cache.rglob('*') if p.is_file())
    def __len__(self):return sum(1 for _ in self.__iter__())


def cellmap():
    base='https://raw.githubusercontent.com/janelia-cellmap/cellmap-segmentation-challenge/main/src/cellmap_segmentation_challenge/utils/'
    response=requests.get(base+'manifest.csv',timeout=30);response.raise_for_status()
    (ORIGINALS/'cellmap-manifest.csv').write_text(response.text,encoding='utf-8')
    rows=list(csv.DictReader(io.StringIO(response.text)))
    selected=[next(r for r in rows if r['crop_number']=='234'),next(r for r in rows if r['crop_number']=='124' and 'liver' in r['collection'])]
    license_info=requests.get('https://api.figshare.com/v2/articles/28034561',timeout=30).json().get('license')
    for row in selected:
        convert=lambda url:url.replace('s3://janelia-cosem-datasets/','https://janelia-cosem-datasets.s3.amazonaws.com/')
        em_url=convert(row['em_url']);gt_url=convert(row['crop_url'])+'/mito'
        meta=requests.get(em_url+'/.zattrs',timeout=30).json();gt=requests.get(gt_url+'/.zattrs',timeout=30).json()
        level='s1' if 'cos7' in row['collection'] else 's0'
        ds=next(d for d in meta['multiscales'][0]['datasets'] if d['path']==level)
        tr={x['type']:x[x['type']] for x in ds['coordinateTransformations']}
        gtds=gt['multiscales'][0]['datasets'][0];gttr={x['type']:x[x['type']] for x in gtds['coordinateTransformations']}
        shape=requests.get(gt_url+'/'+gtds['path']+'/.zarray',timeout=30).json()['shape']
        middle=np.array(gttr['translation'])+(np.array(shape)-1)*np.array(gttr['scale'])/2
        center=np.rint((middle-np.array(tr['translation']))/np.array(tr['scale'])).astype(int)
        cache=ORIGINALS/'cellmap'/row['collection']/level;array=zarr.open_array(HTTPArrayStore(em_url+'/'+level,cache),mode='r')
        size=np.array([32,512,512]);start=np.maximum(0,np.minimum(center-size//2,np.array(array.shape)-size));stop=start+size
        print('CELLMAP ROI',row['collection'],level,start.tolist(),stop.tolist(),flush=True)
        pixels=array[tuple(slice(int(a),int(b)) for a,b in zip(start,stop))]
        assert pixels.std()>1,'Empty/constant EM ROI'
        scale=np.array(tr['scale'])/1000;origin=(np.array(tr['translation'])+start*np.array(tr['scale']))/1000
        prov={'source':em_url,'source_level':level,'crop_center_reference':row['crop_url'],'roi_start_zyx':start.tolist(),
              'roi_stop_zyx_exclusive':stop.tolist(),'source_array_shape_zyx':list(array.shape),'source_multiscale':ds,
              'downloaded_object_inventory':inventory(cache),'manifest_sha256':hashlib.sha256(response.content).hexdigest(),
              'license':license_info,'operation':'Exact contiguous EM subvolume; no XY resampling; organelle labels not downloaded'}
        name='public-em-'+('cos7' if 'cos7' in row['collection'] else 'liver')
        prompts=[('mitochondria','mitochondria with visible internal cristae'),('er','endoplasmic reticulum membranes'),('golgi','the Golgi apparatus'),('lipid_droplets','lipid droplets')]
        write_ngff(name+'-3d',pixels[None,None],scale=[1,1,*scale],offset=[0,0,*origin],units={a:'micrometer' for a in 'zyx'},provenance=prov)
        register(name+'-3d','https://cellmapchallenge.janelia.org/','3D FIB-SEM organelles',prompts,license='CC BY 4.0; CellMap Segmentation Challenge collection',selection=prov,
                 note='Projection merges EM sections; use accompanying 2D slice for individual organelles')
        mid=len(pixels)//2
        write_ngff(name+'-2d',pixels[None,None,mid:mid+1],scale=[1,1,*scale],offset=[0,0,float(origin[0]+mid*scale[0]),float(origin[1]),float(origin[2])],units={a:'micrometer' for a in 'zyx'},provenance={**prov,'selected_z_index_in_roi':mid})
        register(name+'-2d','https://cellmapchallenge.janelia.org/','2D FIB-SEM organelles',prompts,license='CC BY 4.0; CellMap Segmentation Challenge collection',selection={**prov,'selected_z_index_in_roi':mid})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['online','histology','cellmap']);args=parser.parse_args()
    {'online':online,'histology':histology,'cellmap':cellmap}[args.stage]()
