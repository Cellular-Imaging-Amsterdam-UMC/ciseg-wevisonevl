"""Compute actual masks for every catalog example/prompt, retaining individual failures."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings,Prompt
from ciseg_wevisonevl.inference import Predictor
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.io import inspect_store,write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'test-results/published-gallery')
    args=parser.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    records=json.loads((ROOT/'publicdata/catalog.json').read_text(encoding='utf-8-sig'))
    manifest_path=args.output/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'model':'4B','projection':'Max','examples':{}}
    settings=Settings(device='cuda:0')
    predictor=Predictor(settings)
    for number,record in enumerate(records,1):
        name=record['name'];source=ROOT/'publicdata/ome-zarr'/(name+'.ome.zarr')
        presets=record.get('prompt_presets') or [{'name':record.get('label_name','nuclei' if name=='human_mitosis' else 'glands' if name=='immunohistochemistry' else 'organoids' if name.startswith('organoids') else 'cell'),
                                                 'text':record['suggested_query'],'channels':record['channels']}]
        example=manifest['examples'].setdefault(name,{'labels':{},'source_shape':record['shape']})
        for preset in presets:
            label=preset['name']
            if label in example['labels']:
                continue
            prompt=Prompt(label,preset['text'],tuple(map(int,preset.get('channels',record['channels']).split(','))))
            current=replace(settings,normalization=record['normalization'])
            folder=args.output/name/label
            print(f'GALLERY {number}/{len(records)} {name} / {label}',flush=True)
            tick=time.perf_counter()
            result={'name':label,'text':prompt.text,'channels':list(prompt.channels),'status':'running'}
            for budget in [2048,4096]:
                effective=replace(current,max_new_tokens=budget)
                predictor.settings=effective
                attempt=folder/str(budget)
                try:
                    outputs=run(source,attempt,effective,[prompt],predictor_factory=lambda s:predictor)
                    output=outputs[0];report=json.loads((output/'wevisone-run.json').read_text())
                    result.update(status='complete',output=str(output.relative_to(args.output)),
                                  measurements=str((attempt/'measurements.csv').relative_to(args.output)),
                                  frames=report['fields'],max_new_tokens=budget)
                    break
                except Exception as exc:
                    result.update(status='failed',error=str(exc).replace(str(ROOT),'<repository>'),max_new_tokens=budget)
                    partials=list(attempt.glob('*.ome.zarr.partial-*'))
                    if partials:
                        partial=partials[-1]
                        report=json.loads((partial/'wevisone-run.json').read_text())
                        result.update(partial_output=str(partial.relative_to(args.output)),frames=report.get('fields',[]))
                        if 'failed_prediction' in report:
                            result['failed_prediction']=report['failed_prediction']
                    if 'token limit' not in str(exc) or budget==4096:
                        break
            result['wall_seconds']=time.perf_counter()-tick
            example['labels'][label]=result
            write_json(manifest_path,manifest)
            print(f"GALLERY RESULT {name}/{label}: {result['status']} ({result['wall_seconds']:.1f}s)",flush=True)
        write_json(manifest_path,manifest)
    counts={'examples':len(manifest['examples']),'labels_complete':sum(r['status']=='complete' for e in manifest['examples'].values() for r in e['labels'].values()),
            'labels_failed':sum(r['status']=='failed' for e in manifest['examples'].values() for r in e['labels'].values())}
    manifest['summary']=counts;write_json(manifest_path,manifest);print(json.dumps(counts),flush=True)


if __name__=='__main__':main()
