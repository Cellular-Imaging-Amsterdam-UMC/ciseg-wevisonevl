"""Recompute gallery CSVs with current measurement code; preserve previous results."""
import argparse
import json
from pathlib import Path
import sys
import zarr
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings,Prompt
from ciseg_wevisonevl.io import inspect_store,write_json
from ciseg_wevisonevl.measurements import MeasurementCSV


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inference',type=Path,default=ROOT/'test-results/published-gallery')
    parser.add_argument('--revision',default='physical-units-v1')
    args=parser.parse_args();base=args.inference.resolve()
    manifest_path=base/'manifest.json';manifest=json.loads(manifest_path.read_text())
    updated=0
    for name,example in manifest['examples'].items():
        source=ROOT/'publicdata/ome-zarr'/(name+'.ome.zarr')
        source_fields={f.path:f for f in inspect_store(source,[])}
        for label,result in example['labels'].items():
            if result['status']!='complete':continue
            output=base/result['output'];report=json.loads((output/'wevisone-run.json').read_text())
            fields={f.path:f for f in inspect_store(output,[])}
            root=zarr.open_group(str(output),mode='r')
            folder=base/name/label/args.revision
            if not (folder/'measurements.csv').exists():
                with MeasurementCSV(folder,max(f.cyx_shape[0] for f in fields.values())) as csv_output:
                    settings=Settings(**report['settings'])
                    for entry in report['fields']:
                        path=entry['field'];field=fields[path];time_index=int(entry['time_index'])
                        image=root[path] if path else root
                        labels=image[f'labels/wevisone_{label}/0'][time_index,0,0]
                        prompt=Prompt(label,result['text'],tuple(result['channels']))
                        csv_output.add(np.asarray(labels),field,prompt,source_fields[path],time_index,settings,output.name)
            result.setdefault('previous_measurements',result.get('measurements'))
            result['measurements']=str((folder/'measurements.csv').relative_to(base))
            result['measurement_schema']=args.revision
            updated+=1
            write_json(manifest_path,manifest)
    print(json.dumps({'updated_label_tables':updated,'previous_csvs_preserved':True,'inference_repeated':False}),flush=True)


if __name__=='__main__':main()
