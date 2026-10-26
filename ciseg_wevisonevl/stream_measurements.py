"""Disk-aggregated moments, pixel-edge lengths and intensities for large labels."""
import json
import math
import sqlite3
import numpy as np
from .measurements import physical_calibration
from .streaming import blocks, read_window


def axes_from_moments(vy, vx, cov):
    eigen = np.linalg.eigvalsh([[vy,cov],[cov,vx]])
    small,large = np.maximum(eigen,0)
    angle = (math.pi/4 if cov>0 else -math.pi/4) if vy==vx else .5*math.atan2(2*cov if cov else -0.,vy-vx)
    return 4*math.sqrt(large),4*math.sqrt(small),math.sqrt(max(0,1-small/large)) if large else 0.,angle


def add_streamed(table, array, field, prompt, source_field, time_index, settings, output_name, database):
    """Exact counts/moments/intensity sums. Solidity is deliberately unavailable.

    Perimeter uses the exposed pixel-edge estimator (including holes and image
    edges), rather than the small-image marching-squares estimator. The method
    is recorded in every row, so values cannot be mistaken for that estimator.
    """
    db = sqlite3.connect(str(database))
    db.execute('PRAGMA cache_size=-8192')
    db.execute('CREATE TABLE stats (id INTEGER PRIMARY KEY, value TEXT)')
    height,width = array.shape[-2:]
    channel_count = field.cyx_shape[0]
    try:
        for y,x,y1,x1 in blocks((height,width)):
            data = np.asarray(array[time_index,0,0,y:y1,x:x1])
            ids,inverse = np.unique(data,return_inverse=True)
            if not np.any(ids):
                continue
            yy,xx = np.indices(data.shape,dtype=np.float64)
            yy += y; xx += x
            iy = inverse.ravel()
            def total(values):
                return np.bincount(iy,weights=np.asarray(values).ravel(),minlength=len(ids))
            sums = [total(np.ones(data.shape)),total(yy),total(xx),total(yy*yy),total(xx*xx),total(yy*xx)]
            minima_y = np.full(len(ids),np.inf); minima_x = minima_y.copy()
            maxima_y = np.full(len(ids),-np.inf); maxima_x = maxima_y.copy()
            np.minimum.at(minima_y,iy,yy.ravel()); np.minimum.at(minima_x,iy,xx.ravel())
            np.maximum.at(maxima_y,iy,yy.ravel()); np.maximum.at(maxima_x,iy,xx.ravel())
            # A one-pixel halo prevents counting processing-block boundaries as object boundaries.
            halo = np.zeros((y1-y+2,x1-x+2),np.uint32)
            hy,hx,hy1,hx1 = max(0,y-1),max(0,x-1),min(height,y1+1),min(width,x1+1)
            halo[hy-y+1:hy1-y+1,hx-x+1:hx1-x+1] = array[time_index,0,0,hy:hy1,hx:hx1]
            horizontal = total((data != halo[:-2,1:-1]).astype(np.uint8)+(data != halo[2:,1:-1]))
            vertical = total((data != halo[1:-1,:-2]).astype(np.uint8)+(data != halo[1:-1,2:]))
            intensities = []
            # Read each original channel once per block, including channels excluded from the model view.
            for channel in range(1,channel_count+1):
                values = read_window(field,[channel],time_index,settings.projection,(y,x,y1,x1))[channel-1].astype(np.float64)
                finite = np.isfinite(values)
                counts,totals = total(finite),total(np.where(finite,values,0))
                low = np.full(len(ids),np.inf); high = np.full(len(ids),-np.inf)
                np.minimum.at(low,iy,np.where(finite,values,np.inf).ravel())
                np.maximum.at(high,iy,np.where(finite,values,-np.inf).ravel())
                intensities.append((counts,totals,low,high))
            for i,label in enumerate(ids):
                if not label:
                    continue
                state = {'s':[float(a[i]) for a in sums],
                         'box':[int(minima_y[i]),int(minima_x[i]),int(maxima_y[i])+1,int(maxima_x[i])+1],
                         'h':float(horizontal[i]),'v':float(vertical[i]),
                         'c':[[float(a[i]) for a in channel] for channel in intensities]}
                saved = db.execute('SELECT value FROM stats WHERE id=?',(int(label),)).fetchone()
                if saved:
                    previous = json.loads(saved[0])
                    state['s'] = [a+b for a,b in zip(state['s'],previous['s'])]
                    state['box'] = [min(state['box'][j],previous['box'][j]) if j<2 else max(state['box'][j],previous['box'][j]) for j in range(4)]
                    state['h'] += previous['h']; state['v'] += previous['v']
                    for current,old in zip(state['c'],previous['c']):
                        current[:] = [current[0]+old[0],current[1]+old[1],min(current[2],old[2]),max(current[3],old[3])]
                db.execute('INSERT OR REPLACE INTO stats VALUES (?,?)',(int(label),json.dumps(state)))
            db.commit()
        dy,dx,oy,ox = physical_calibration(field)
        calibrated = dy is not None and dx is not None
        parts = field.path.split('/') if field.path else []
        rows = 0
        for label,payload in db.execute('SELECT id,value FROM stats ORDER BY id'):
            state = json.loads(payload)
            n,sy,sx,syy,sxx,syx = state['s']
            cy,cx = sy/n,sx/n
            vy,vx,cov = max(0,syy/n-cy*cy),max(0,sxx/n-cx*cx),syx/n-cy*cx
            major,minor,ecc,orientation = axes_from_moments(vy,vx,cov)
            physical = axes_from_moments(vy*dy*dy,vx*dx*dx,cov*dy*dx) if calibrated else None
            ymin,xmin,ymax,xmax = state['box']
            row = {'input_store':source_field.store.name,'output_store':output_name,'field_path':field.path,
                   'well_path':'/'.join(parts[:-1]),'field_id':parts[-1] if parts else '',
                   'time_index':time_index,'prompt_name':prompt.name,'prompt_text':prompt.text,'label_mode':settings.label_mode,
                   'label_id':label,'projection':settings.projection if source_field.z_planes>1 else 'none',
                   'source_z_planes':source_field.z_planes,'area_px':int(n),'area_um2':n*dy*dx if calibrated else '',
                   'pixel_size_y_um':dy if dy is not None else '', 'pixel_size_x_um':dx if dx is not None else '',
                   'origin_y_um':oy if oy is not None else '', 'origin_x_um':ox if ox is not None else '',
                   'centroid_y_px':cy,'centroid_x_px':cx,'centroid_y_um':cy*dy+oy if dy is not None else '',
                   'centroid_x_um':cx*dx+ox if dx is not None else '',
                   'bbox_min_y_px':ymin,'bbox_min_x_px':xmin,'bbox_max_y_px_exclusive':ymax,'bbox_max_x_px_exclusive':xmax,
                   'bbox_min_y_um':ymin*dy+oy if dy is not None else '', 'bbox_min_x_um':xmin*dx+ox if dx is not None else '',
                   'bbox_max_y_um_exclusive':ymax*dy+oy if dy is not None else '', 'bbox_max_x_um_exclusive':xmax*dx+ox if dx is not None else '',
                   'perimeter_px':state['h']+state['v'],
                   'perimeter_um':state['h']*dx+state['v']*dy if calibrated else '',
                   'perimeter_um_method':'streamed_pixel_edges' if calibrated else '',
                   'equivalent_diameter_px':math.sqrt(4*n/math.pi),
                   'equivalent_diameter_um':math.sqrt(4*n*dy*dx/math.pi) if calibrated else '',
                   'major_axis_length_px':major,'minor_axis_length_px':minor,
                   'major_axis_length_um':physical[0] if physical else '', 'minor_axis_length_um':physical[1] if physical else '',
                   'eccentricity':physical[2] if physical else ecc,'eccentricity_px':ecc,
                   'orientation_rad':physical[3] if physical else orientation,'orientation_px_rad':orientation,
                   'extent':n/((ymax-ymin)*(xmax-xmin)),'solidity':'',
                   'shape_basis':'physical_um' if calibrated else 'pixels',
                   'measurement_method':'streamed_moments_pixel_edges; solidity unavailable'}
            for channel,(count,total,low,high) in enumerate(state['c'],1):
                prefix = f'channel_{channel}_'
                row.update({prefix+'valid_pixels':int(count),prefix+'min':low if count else '',prefix+'max':high if count else '',
                            prefix+'mean':total/count if count else '',prefix+'total':total if count else ''})
            table.writer.writerow(row)
            rows += 1
        table.stream.flush()
        table.rows += rows
        return rows
    finally:
        db.close()
