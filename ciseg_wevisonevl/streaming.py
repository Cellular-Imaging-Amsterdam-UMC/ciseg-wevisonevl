"""Bounded XY reads and pyramid construction shared by tiled processing."""
from copy import deepcopy
import numpy as np
import zarr

BLOCK = 512


def blocks(shape, size=BLOCK):
    for y in range(0, shape[0], size):
        for x in range(0, shape[1], size):
            yield y, x, min(y+size, shape[0]), min(x+size, shape[1])


def read_window(field, channels, time_index=0, projection='Max', window=None, z_index=None):
    """Read/project a bounded XY region; channels remain zero-indexed in the result."""
    root = zarr.open_group(str(field.store), mode='r')
    group = root[field.path] if field.path else root
    array = group[field.dataset]
    if window is None:
        window = (0, 0, *field.cyx_shape[1:])
    y0, x0, y1, x1 = window
    result = {}
    for channel in set(channels):
        plane = None
        zs = range(field.z_planes) if z_index is None else [z_index]
        for zi in zs:
            selection = {'t': time_index, 'c': channel-1, 'z': zi,
                         'y': slice(y0, y1), 'x': slice(x0, x1)}
            part = np.asarray(array[tuple(selection[a] for a in field.names)])
            if [a for a in field.names if a in 'xy'] == ['x', 'y']:
                part = part.T
            if z_index is None and field.z_planes > 1 and projection == 'Mean':
                part = part.astype(np.float64)
            if plane is None:
                plane = part.copy()
            elif projection == 'Max':
                np.maximum(plane, part, out=plane)
            else:
                plane += part
        if z_index is None and field.z_planes > 1 and projection == 'Mean':
            plane = (plane / field.z_planes).astype(np.float32)
        result[channel-1] = plane.astype(plane.dtype.newbyteorder('='), copy=False)
    return result


def overview_field(field, max_side=2048):
    """Choose an existing overview before reading pixels; never load the native plane."""
    from .io import Field
    root = zarr.open_group(str(field.store), mode='r')
    group = root[field.path] if field.path else root
    chosen = None
    native_sizes = dict(zip(field.names,field.shape))
    for dataset in field.multiscale['datasets']:
        array = group[dataset['path']]
        sizes = dict(zip(field.names, array.shape))
        if any(sizes[a] != native_sizes[a] for a in field.names if a not in 'xy'):
            continue
        chosen = dataset
        if max(sizes['y'], sizes['x']) <= max_side:
            break
    if chosen is None:
        return None
    array = group[chosen['path']]
    if max(array.shape[field.names.index('y')], array.shape[field.names.index('x')]) > max_side:
        return None
    ms = deepcopy(field.multiscale)
    ms['datasets'] = [deepcopy(chosen)]
    return Field(field.store, field.path, chosen['path'], field.axes, array.shape, ms)


def sampled_overview(field, channels, time_index=0, projection='Max', max_side=1024, z_index=None):
    """Fallback for single-resolution stores, with bounded source reads."""
    height, width = field.cyx_shape[1:]
    step = max(1, int(np.ceil(max(height, width)/max_side)))
    planes = {}
    for y, x, y1, x1 in blocks((height, width)):
        sy, sx = ((y+step-1)//step)*step, ((x+step-1)//step)*step
        if sy >= y1 or sx >= x1:
            continue
        for c, part in read_window(field, channels, time_index, projection, (sy,sx,y1,x1),z_index).items():
            if c not in planes:
                planes[c] = np.empty(((height+step-1)//step, (width+step-1)//step), part.dtype)
            planes[c][sy//step:(y1+step-1)//step, sx//step:(x1+step-1)//step] = part[::step, ::step]
    return planes, step


def build_pyramid_level(source, target, time_index, channel=0, labels=False):
    """One level at a time, at most 1024x1024 source pixels per read."""
    from .projection import area_downsample
    for y, x, y1, x1 in blocks(target.shape[-2:]):
        part = np.asarray(source[time_index,channel,0,2*y:min(2*y1,source.shape[-2]),2*x:min(2*x1,source.shape[-1])])
        target[time_index,channel,0,y:y1,x:x1] = part[::2,::2] if labels else area_downsample(part)
