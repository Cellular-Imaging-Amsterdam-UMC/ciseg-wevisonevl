"""Compare pixel hashes from the Java reader with the corresponding local stores."""
from pathlib import Path
import hashlib
import json
import re
import sys
import zarr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import inspect_store,write_json


if __name__=="__main__":
    log=(ROOT/"test-results/projection-runtime-canonical/bioformats-reader.log").read_text(encoding="utf-8-sig")
    rows=[]
    for method in ["Max","Mean"]:
        source=ROOT/f"test-results/projection-runtime-canonical/{method}/time-volume-screen__wevisonevl.ome.zarr"
        root=zarr.open_group(str(source),mode="r")
        expected=[]
        for field in inspect_store(source,[]):
            image=root[field.path]
            groups=[image]+[image['labels'][name] for name in image['labels'].attrs['labels']]
            for group in groups:
                ms=group.attrs['multiscales'][0]
                names=[a['name'] for a in ms['axes']]
                for dataset in ms['datasets']:
                    array=group[dataset['path']]
                    sizes=dict(zip(names,array.shape))
                    for t in range(sizes.get('t',1)):
                        for c in range(sizes.get('c',1)):
                            index=tuple(t if a=='t' else c if a=='c' else slice(0,13) if a=='y' else slice(0,17) if a=='x' else 0 for a in names)
                            expected.append(hashlib.sha256(array[index].tobytes()).hexdigest())
        match=re.search(r'STORE\t[^\n]*CISegWeVisOneVL-'+method+r'[^\n]*\.ome\.zarr.*?(?=STORE\t|\Z)',log,re.S)
        assert match,method
        actual=re.findall(r'sha256=([0-9a-f]+)',match.group())
        assert sorted(actual)==sorted(expected),(method,len(actual),len(expected))
        rows.append({'projection':method,'matched_pixel_windows':len(actual),'all_timepoints_read':True,'passed':True})
    write_json(ROOT/'test-results/projection-runtime-canonical/reader-checks.json',rows)
    print(json.dumps(rows),flush=True)
