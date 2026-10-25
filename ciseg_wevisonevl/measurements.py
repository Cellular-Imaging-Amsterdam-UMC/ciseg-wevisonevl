"""Small per-label shape/intensity table, shared by all inputs in one run."""
import csv
from pathlib import Path
from uuid import uuid4
import math
import numpy as np
from skimage.measure import regionprops,find_contours
from scipy import ndimage as ndi

LENGTH_TO_UM={"micrometer":1.,"micrometre":1.,"um":1.,"µm":1.,"μm":1.,
              "nanometer":.001,"nanometre":.001,"nm":.001,"millimeter":1000.,"millimetre":1000.,"meter":1e6}
BASE_COLUMNS=["input_store","output_store","field_path","well_path","field_id","time_index","prompt_name","prompt_text",
              "label_mode","label_id","projection","source_z_planes","area_px","area_um2","pixel_size_y_um","pixel_size_x_um",
              "origin_y_um","origin_x_um","centroid_y_px","centroid_x_px","centroid_y_um","centroid_x_um",
              "bbox_min_y_px","bbox_min_x_px","bbox_max_y_px_exclusive","bbox_max_x_px_exclusive",
              "bbox_min_y_um","bbox_min_x_um","bbox_max_y_um_exclusive","bbox_max_x_um_exclusive",
              "perimeter_px","perimeter_um","perimeter_um_method","equivalent_diameter_px","equivalent_diameter_um",
              "major_axis_length_px","major_axis_length_um","minor_axis_length_px","minor_axis_length_um",
              "eccentricity","eccentricity_px","solidity","extent","orientation_rad","orientation_px_rad","shape_basis"]


def physical_calibration(field):
    """Compose NGFF transforms in order, then convert spacing and origin to µm."""
    scales={a:1. for a in field.names}
    origins={a:0. for a in field.names}
    ds=field.multiscale['datasets'][0]
    for transform in ds.get('coordinateTransformations',[])+field.multiscale.get('coordinateTransformations',[]):
        if transform['type']=='scale':
            for axis,value in zip(field.names,transform['scale']):
                scales[axis]*=float(value)
                origins[axis]*=float(value)
        elif transform['type']=='translation':
            for axis,value in zip(field.names,transform['translation']):
                origins[axis]+=float(value)
    units={a['name']:a.get('unit') for a in field.axes}
    values=[];offsets=[]
    for axis in ['y','x']:
        factor=LENGTH_TO_UM.get(units.get(axis))
        value=scales[axis]*factor if factor is not None else None
        values.append(value if value is not None and math.isfinite(value) and value>0 else None)
        origin=origins[axis]*factor if factor is not None else None
        offsets.append(origin if origin is not None and math.isfinite(origin) else None)
    return (*values,*offsets)


def physical_pixel_size(field):
    return physical_calibration(field)[:2]


def physical_perimeter(region,dy,dx):
    """Use the pixel estimator for isotropic data; scaled closed contours otherwise."""
    if math.isclose(dy,dx,rel_tol=1e-12,abs_tol=0.):
        return float(region.perimeter)*dy,'scaled_pixel_estimator'
    total=0.
    # Padding closes contours at image/ROI edges and includes inner holes.
    for contour in find_contours(np.pad(region.image,1),.5):
        differences=np.diff(contour,axis=0)*np.array([dy,dx])
        total+=float(np.hypot(differences[:,0],differences[:,1]).sum())
    return total,'anisotropic_marching_squares'


class MeasurementCSV:
    def __init__(self,folder,max_channels):
        self.path=Path(folder)/'measurements.csv'
        self.partial=Path(folder)/('measurements.partial-'+uuid4().hex[:8])
        self.columns=BASE_COLUMNS+[f'channel_{channel}_{stat}' for channel in range(1,max_channels+1) for stat in ['valid_pixels','min','max','mean','total']]
        self.rows=0

    def __enter__(self):
        if self.path.exists():
            raise FileExistsError(f'Measurements already exist: {self.path}')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.partial.open('w',encoding='utf-8-sig',newline='')
        self.writer=csv.DictWriter(self.stream,fieldnames=self.columns)
        self.writer.writeheader()
        return self

    def __exit__(self,kind,value,traceback):
        self.stream.close()
        if kind is None:
            if self.path.exists():
                raise FileExistsError(self.path)
            self.partial.rename(self.path)
            print(f'MEASUREMENTS: {self.path} ({self.rows} rows)',flush=True)

    def add(self,labels,field,prompt,source_field,time_index,settings,output_name,plane_cache=None):
        props=regionprops(labels)
        if not props:
            return 0
        dy,dx,oy,ox=physical_calibration(field)
        calibrated=dy is not None and dx is not None
        metric={r.label:r for r in regionprops(labels,spacing=(dy,dx))} if calibrated else {}
        field_parts=field.path.split('/') if field.path else []
        rows=[]
        for region in props:
            physical=metric.get(region.label)
            ymin,xmin,ymax,xmax=region.bbox
            area=int(region.area)
            perimeter,method=physical_perimeter(region,dy,dx) if calibrated else ('','')
            rows.append({'input_store':source_field.store.name,'output_store':output_name,'field_path':field.path,
                         'well_path':'/'.join(field_parts[:-1]) if field_parts else '', 'field_id':field_parts[-1] if field_parts else '',
                         'time_index':time_index,'prompt_name':prompt.name,'prompt_text':prompt.text,'label_mode':settings.label_mode,
                         'label_id':int(region.label),'projection':settings.projection if source_field.z_planes>1 else 'none',
                         'source_z_planes':source_field.z_planes,'area_px':area,'area_um2':area*dx*dy if dx is not None and dy is not None else '',
                         'pixel_size_y_um':dy if dy is not None else '', 'pixel_size_x_um':dx if dx is not None else '',
                         'origin_y_um':oy if oy is not None else '', 'origin_x_um':ox if ox is not None else '',
                         'centroid_y_px':float(region.centroid[0]),'centroid_x_px':float(region.centroid[1]),
                         'centroid_y_um':float(region.centroid[0])*dy+oy if dy is not None else '',
                         'centroid_x_um':float(region.centroid[1])*dx+ox if dx is not None else '',
                         'bbox_min_y_px':ymin,'bbox_min_x_px':xmin,'bbox_max_y_px_exclusive':ymax,'bbox_max_x_px_exclusive':xmax,
                         'bbox_min_y_um':ymin*dy+oy if dy is not None else '', 'bbox_min_x_um':xmin*dx+ox if dx is not None else '',
                         'bbox_max_y_um_exclusive':ymax*dy+oy if dy is not None else '', 'bbox_max_x_um_exclusive':xmax*dx+ox if dx is not None else '',
                         'perimeter_px':float(region.perimeter),'equivalent_diameter_px':float(region.equivalent_diameter_area),
                         'perimeter_um':perimeter,'perimeter_um_method':method,
                         'equivalent_diameter_um':float(physical.equivalent_diameter_area) if physical is not None else '',
                         'major_axis_length_px':float(region.axis_major_length),'minor_axis_length_px':float(region.axis_minor_length),
                         'major_axis_length_um':float(physical.axis_major_length) if physical is not None else '',
                         'minor_axis_length_um':float(physical.axis_minor_length) if physical is not None else '',
                         'eccentricity':float(physical.eccentricity if physical is not None else region.eccentricity),
                         'eccentricity_px':float(region.eccentricity),'solidity':float(region.solidity),'extent':float(region.extent),
                         'orientation_rad':float(physical.orientation if physical is not None else region.orientation),
                         'orientation_px_rad':float(region.orientation),'shape_basis':'physical_um' if calibrated else 'pixels'})
        indices=[int(p.label) for p in props]
        for channel in range(1,field.cyx_shape[0]+1):
            pixels=plane_cache.get(channel-1) if plane_cache is not None else None
            if pixels is None:
                pixels=field.pixels([channel],time_index)[channel-1]
            finite=np.isfinite(pixels)
            values=np.asarray(pixels,dtype=np.float64)
            totals=ndi.sum(np.where(finite,values,0),labels,indices)
            counts=ndi.sum(finite,labels,indices)
            minima=ndi.minimum(np.where(finite,values,np.inf),labels,indices)
            maxima=ndi.maximum(np.where(finite,values,-np.inf),labels,indices)
            for i,row in enumerate(rows):
                prefix=f'channel_{channel}_'
                count=int(counts[i])
                row.update({prefix+'valid_pixels':count,prefix+'min':float(minima[i]) if count else '',
                            prefix+'max':float(maxima[i]) if count else '',prefix+'mean':float(totals[i]/count) if count else '',
                            prefix+'total':float(totals[i]) if count else ''})
        self.writer.writerows(rows)
        self.stream.flush()
        self.rows+=len(rows)
        return len(rows)
