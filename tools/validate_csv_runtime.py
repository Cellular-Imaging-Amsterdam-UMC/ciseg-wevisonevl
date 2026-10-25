"""Check actual 4B label CSVs against output pixel values for Max and Mean HCS runs."""
import csv
from pathlib import Path
import sys
import numpy as np
import zarr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import write_json


if __name__=='__main__':
    checks=[]
    for method in ['Max','Mean']:
        folder=ROOT/'test-results/csv-projection-runtime'/method
        with (folder/'measurements.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==4
        assert {(r['field_path'],r['time_index']) for r in rows}=={(f'A/1/{f}',str(t)) for f in [0,1] for t in [0,1]}
        root=zarr.open_group(str(next(folder.glob('*.ome.zarr'))),mode='r')
        for row in rows:
            image=root[row['field_path']];t=int(row['time_index']);object_id=int(row['label_id'])
            mask=image['labels/wevisone_cell/0'][t,0,0]==object_id
            pixels=image['0'][t,0,0][mask]
            assert int(row['area_px'])==int(mask.sum())
            assert np.isclose(float(row['area_um2']),mask.sum()*.107**2)
            assert float(row['channel_1_min'])==pixels.min()
            assert float(row['channel_1_max'])==pixels.max()
            assert np.isclose(float(row['channel_1_mean']),pixels.mean(dtype=np.float64))
            assert np.isclose(float(row['channel_1_total']),pixels.sum(dtype=np.float64))
        checks.append({'projection':method,'rows':len(rows),'field_time_keys_checked':True,'area_and_intensity_values_match_output_pixels':True,'passed':True})
    write_json(ROOT/'test-results/csv-projection-runtime/measurement-checks.json',checks)
    print(checks)
