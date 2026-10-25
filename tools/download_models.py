"""Prepare immutable local Hugging Face snapshots, including the required pixel decoder."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import MODELS, MODEL_REVISIONS, ROOT


def download(model, root, revision=None):
    from huggingface_hub import HfApi, snapshot_download
    api = HfApi()
    info = api.model_info(MODELS[model], revision=revision or MODEL_REVISIONS[model], files_metadata=True)
    folder = root / f"WeVisOne-VL-{model}"
    manifest = folder / "download-manifest.json"
    if manifest.exists():
        old = json.loads(manifest.read_text())
        if old["revision"] != info.sha:
            raise RuntimeError(f"Existing immutable cache is {old['revision']}; remote is {info.sha}. Use another --models-root for a new revision.")
    print(f"Downloading {MODELS[model]} @ {info.sha} to {folder}", flush=True)
    snapshot_download(MODELS[model], revision=info.sha, local_dir=folder,
                      allow_patterns=["*.json", "*.safetensors", "mask_decoder.pt", "*.txt", "*.jinja", "LICENSE*", "README.md"], max_workers=4)
    from fnmatch import fnmatch
    patterns = ["*.json", "*.safetensors", "mask_decoder.pt", "*.txt", "*.jinja", "LICENSE*", "README.md"]
    files = []
    for sibling in info.siblings:
        if not any(fnmatch(sibling.rfilename, p) for p in patterns):
            continue
        local = folder / sibling.rfilename
        if not local.is_file() or sibling.size is not None and local.stat().st_size != sibling.size:
            raise RuntimeError(f"Incomplete snapshot: {local}")
        lfs = sibling.lfs
        sha = getattr(lfs, "sha256", None) if lfs else None
        files.append({"path": sibling.rfilename, "size": local.stat().st_size, "hub_lfs_sha256": sha})
    if not (folder / "mask_decoder.pt").is_file() or not list(folder.glob("*.safetensors")):
        raise RuntimeError("Snapshot lacks language weights or mask_decoder.pt")
    value = {"repo_id": MODELS[model], "revision": info.sha, "files": files,
             "verification": "snapshot_download integrity and remote file sizes; LFS hashes recorded"}
    temporary = manifest.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(manifest)
    print(f"READY: {model} ({sum(f['size'] for f in files)/1e9:.2f} GB)", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-root", type=Path, default=ROOT / "models")
    parser.add_argument("--revision", help="Use a different pinned 4B Hugging Face revision")
    args = parser.parse_args()
    download("4B", args.models_root.resolve(), args.revision)
