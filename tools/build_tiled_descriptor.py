"""Generate the opt-in BIOMERO tiled descriptor from the shared parameters."""
from pathlib import Path
import yaml


def build(root):
    data=yaml.safe_load((root/'config.yaml').read_text(encoding='utf-8'))
    data['algorithm_folder_name']='CISegWeVisOneVL_Tiled'
    data['citations'][0]['name']='CISegWeVisOneVL tiled'
    data['citations'][0]['description']='Tiled CISegWeVisOneVL development workflow for large OME-Zarr scans, with bounded storage and measurements. The dev container is a local build target, not a published release.'
    next(p for p in data['parameters'] if p['name']=='processing_mode')['default']='tiled'
    (root/'config-tiled.yaml').write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding='utf-8')


if __name__=='__main__':
    build(Path(__file__).resolve().parents[1])
