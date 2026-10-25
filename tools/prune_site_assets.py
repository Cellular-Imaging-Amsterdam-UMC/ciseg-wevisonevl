"""Remove only tracked generated previews/downloads no longer referenced by the curated gallery."""
import argparse,json,subprocess
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];docs=(root/'docs').resolve()
    catalog=json.loads((docs/'assets/examples.json').read_text())
    keep=set()
    for sample in catalog['examples']:
        keep.add(sample['input'])
        if sample.get('measurements'):keep.add(sample['measurements'])
        for label in sample['labels']:
            keep.update(label[k] for k in ['overlay','download'] if label.get(k))
        if sample.get('reference'):keep.update(sample['reference'].values())
    tracked=subprocess.check_output(['git','ls-files','docs/gallery','docs/downloads'],cwd=root,text=True).splitlines()
    remove=[]
    for relative in tracked:
        path=(root/relative).resolve()
        if not path.is_relative_to(docs/'gallery') and not path.is_relative_to(docs/'downloads'):raise ValueError('Unexpected generated-asset target')
        if path.relative_to(docs).as_posix() not in keep:remove.append(relative)
    if args.apply and remove:subprocess.run(['git','rm','--',*remove],cwd=root,check=True,stdout=subprocess.DEVNULL)
    print(json.dumps({'orphaned_tracked_assets':len(remove),'removed':bool(args.apply),'source_results_preserved':True}))


if __name__=='__main__':main()
