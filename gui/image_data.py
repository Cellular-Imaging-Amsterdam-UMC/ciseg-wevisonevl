"""Read one displayed frame and independent label layers without changing stores."""
from pathlib import Path

import numpy as np
import zarr

from ciseg_wevisonevl.inference import render_rgb
from ciseg_wevisonevl.io import safe_path


def _section(array, names, time_index, z_index):
    indices = {'t': time_index, 'c': 0, 'z': z_index, 'y': slice(None), 'x': slice(None)}
    if len(names) != array.ndim or len(set(names)) != len(names) or not {'x', 'y'} <= set(names) or not set(names) <= set(indices):
        raise ValueError('Unsupported label axes')
    selection = tuple(indices[a] if a in 'xy' or size > 1 else 0 for a, size in zip(names, array.shape))
    plane = np.asarray(array[selection])
    return plane.T if [a for a in names if a in 'xy'] == ['x', 'y'] else plane


def load_frame(field, time_index, channels, normalization, projection, z_index=None):
    if not 0 <= time_index < field.timepoints:
        raise ValueError('Timepoint is outside the image')
    if len(channels) not in (1, 3) or any(not 1 <= c <= field.cyx_shape[0] for c in channels):
        raise ValueError(f'Choose one channel or three RGB channels between 1 and {field.cyx_shape[0]}')
    root = zarr.open_group(str(field.store), mode='r')
    group = root[field.path] if field.path else root
    if z_index is None:
        planes = field.pixels(channels, time_index, projection)
    else:
        if not 0 <= z_index < field.z_planes:
            raise ValueError('Z section is outside the image')
        array = group[field.dataset]
        planes = {}
        for channel in set(channels):
            selection = {'t': time_index, 'c': channel-1, 'z': z_index, 'y': slice(None), 'x': slice(None)}
            plane = np.asarray(array[tuple(selection[a] for a in field.names)])
            planes[channel-1] = plane.T if [a for a in field.names if a in 'xy'] == ['x', 'y'] else plane
    # Completed Mean projections retain their unsigned source range in provenance.
    origin = group.attrs.get('ciseg_wevisonevl_projection', {})
    if normalization == 'dtype' and group[field.dataset].dtype.kind == 'f' and origin.get('method') == 'Mean':
        options = {'source_dtype': origin.get('source_dtype', group[field.dataset].dtype)}
    else:
        options = field.render_options(normalization, channels)
    image, limits = render_rgb(planes, channels, normalization, **options)
    labels, notes = {}, []
    if 'labels' in group:
        container = group['labels']
        for name in container.attrs.get('labels', []):
            label = container[safe_path(name)]
            scales = label.attrs.get('multiscales', [])
            if len(scales) != 1:
                continue
            ms = scales[0]
            names = [a['name'] if isinstance(a, dict) else a for a in ms.get('axes', [])]
            array = label[safe_path(ms['datasets'][0]['path'])]
            if 'z' in names and array.shape[names.index('z')] > 1 and z_index is None:
                notes.append(f'{name}: volume labels require Z section view')
                continue
            plane = _section(array, names, time_index, z_index or 0)
            if plane.shape != (image.height, image.width) or plane.dtype.kind not in 'ui':
                notes.append(f'{name}: label dimensions or pixel type do not match this image')
                continue
            labels[name] = plane
    return {'rgb': np.asarray(image), 'labels': labels, 'limits': limits, 'notes': notes,
            'title': f'{Path(field.store).name} · {field.path or "image"} · T {time_index+1}/{field.timepoints}',
            'view': f'Z section {z_index+1}/{field.z_planes}' if z_index is not None else f'{projection} Z projection' if field.z_planes > 1 else '2D image'}


PROMPT_COLORS = ('#ff5a9d', '#00c8ff', '#ffb84d', '#b28dff', '#52d99b', '#ff7752')


def label_rgba(labels, layer_index=0, *, mode='instances', color='#ff5a9d'):
    """Render one prompt in a single color or stable colors per instance."""
    rgba = np.zeros((*labels.shape, 4), np.uint8)
    if mode == 'single':
        if not isinstance(color, str) or len(color) != 7 or not color.startswith('#'):
            raise ValueError('Choose an RGB color in #RRGGBB format')
        rgb = bytes.fromhex(color[1:])
        if len(rgb) != 3:
            raise ValueError('Choose an RGB color in #RRGGBB format')
        rgba[..., :3] = tuple(rgb)
    elif mode == 'instances':
        seed = labels.astype(np.uint64) * 2654435761 + 2246822519 * layer_index
        for component in range(3):
            rgba[..., component] = 65 + (((seed >> (8 * component)) & 255) * 189 // 255).astype(np.uint8)
    else:
        raise ValueError('Choose single or instances label colors')
    rgba[..., 3] = np.where(labels > 0, 255, 0).astype(np.uint8)
    return rgba
