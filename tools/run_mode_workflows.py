"""Run retained and exploratory modality prompts through the actual workflow once."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT, Settings, Prompt
from ciseg_wevisonevl.inference import Predictor
from ciseg_wevisonevl.engine import run
from ciseg_wevisonevl.io import write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'test-results/imaging-mode-workflows')
    args=parser.parse_args();base=args.output.resolve();base.mkdir(parents=True,exist_ok=True)
    path=base/'manifest.json'
    manifest=json.loads(path.read_text()) if path.exists() else {'model':'4B','projection':'Max','examples':{},'cases':{}}
    settings=Settings(device='cuda:0',max_new_tokens=4096)
    predictor=Predictor(settings)
    for case in json.loads(args.cases.read_text()):
        if case['id'] in manifest['cases']:continue
        current=replace(settings,normalization=case['normalization']);predictor.settings=current
        label=case['name'];folder=base/case['sample']/label
        print('WORKFLOW',case['id'],case['text'],flush=True)
        try:
            outputs=run(ROOT/'publicdata/ome-zarr'/(case['sample']+'.ome.zarr'),folder,current,
                        [Prompt(label,case['text'],tuple(map(int,case['channels'].split(','))))],predictor_factory=lambda s:predictor)
            report=json.loads((outputs[0]/'wevisone-run.json').read_text())
            result={'name':label,'text':case['text'],'channels':list(map(int,case['channels'].split(','))),
                    'status':'complete','output':outputs[0].relative_to(base).as_posix(),
                    'measurements':(folder/'measurements.csv').relative_to(base).as_posix(),
                    'frames':report['fields'],'max_new_tokens':4096,'selected_prompt_study':case['id']}
            manifest['examples'].setdefault(case['sample'],{'labels':{}})['labels'][label]=result
            frame=result['frames'][0]
            manifest['cases'][case['id']]={**case,'status':'complete','objects':frame['retained_instances'],
                                         'coverage':frame['foreground_fraction'],'seconds':frame['seconds']}
        except Exception as exc:
            manifest['cases'][case['id']]={**case,'status':'failed','error':str(exc)}
        write_json(path,manifest)
    print('Completed',len(manifest['cases']),'workflow cases',flush=True)


if __name__=='__main__':main()
