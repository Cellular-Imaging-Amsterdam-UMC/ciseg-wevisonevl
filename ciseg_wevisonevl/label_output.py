"""Disk-backed native label arrays and calibrated pyramids."""
import zarr
from numcodecs import Blosc
from .io import canonical_axes, canonical_transforms


def label_group(output, field, prompt, time_index):
    root = zarr.open_group(str(output),mode='a')
    image = root[field.path] if field.path else root
    container = image.require_group('labels')
    name = 'wevisone_'+prompt.name
    if time_index:
        return container[name]
    group = container.create_group(name)
    height,width = field.cyx_shape[1:]
    datasets = []
    factor = 1
    while True:
        level = str(len(datasets))
        array = group.create_dataset(level,shape=(field.timepoints,1,1,height,width),dtype='u4',
                                     chunks=(1,1,1,min(height,512),min(width,512)),
                                     compressor=Blosc(cname='zstd',clevel=3,shuffle=Blosc.BITSHUFFLE))
        array.attrs['_ARRAY_DIMENSIONS'] = list('tczyx')
        transforms = canonical_transforms(field.multiscale['datasets'][0].get('coordinateTransformations',[]),field.names,factor,label=True)
        if not transforms:
            transforms = [{'type':'scale','scale':[1,1,1,factor,factor]}]
        datasets.append({'path':level,'coordinateTransformations':transforms})
        if max(height,width) <= 256:
            break
        height,width = (height+1)//2,(width+1)//2
        factor *= 2
    ms = {'version':'0.4','name':name,'axes':canonical_axes(field),'datasets':datasets}
    if 'coordinateTransformations' in field.multiscale:
        ms['coordinateTransformations'] = canonical_transforms(field.multiscale['coordinateTransformations'],field.names,label=True)
    group.attrs.update({'multiscales':[ms],'image-label':{'version':'0.4','source':{'image':'../../'}}})
    declared = list(container.attrs.get('labels',[]))
    if name not in declared:
        declared.append(name)
    container.attrs['labels'] = declared
    return group

