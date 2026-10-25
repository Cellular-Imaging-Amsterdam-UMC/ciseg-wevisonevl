"""NGFF 0.4/Zarr v2 I/O with independent timepoints and explicit Z reduction."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import json
import numpy as np
import zarr
from numcodecs import Blosc


def safe_path(value):
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or any(p in ("..", ".") for p in path.parts) or "\\" in str(value):
        raise ValueError(f"Unsafe NGFF path: {value}")
    return str(path)


@dataclass
class Field:
    store: Path
    path: str
    dataset: str
    axes: list
    shape: tuple
    multiscale: dict

    @property
    def names(self):
        return [a["name"] for a in self.axes]

    @property
    def cyx_shape(self):
        sizes = dict(zip(self.names, self.shape))
        return sizes.get("c", 1), sizes["y"], sizes["x"]

    @property
    def timepoints(self):
        return dict(zip(self.names, self.shape)).get("t", 1)

    @property
    def z_planes(self):
        return dict(zip(self.names, self.shape)).get("z", 1)

    def pixels(self, channels, time_index=0, projection="Max"):
        group = zarr.open_group(str(self.store), mode="r")
        group = group[self.path] if self.path else group
        array = group[self.dataset]
        planes = {}
        for channel in set(channels):
            plane = None
            for z_index in range(self.z_planes):
                indices = {"c":channel-1, "t":time_index, "z":z_index, "x":slice(None), "y":slice(None)}
                part = np.asarray(array[tuple(indices[axis] for axis in self.names)])
                if [a for a in self.names if a in ("x", "y")] == ["x", "y"]:
                    part = part.T
                if self.z_planes > 1 and projection == "Mean":
                    part = part.astype(np.float64)
                if plane is None:
                    plane = part.copy()
                elif projection == "Max":
                    np.maximum(plane, part, out=plane)
                else:
                    plane += part
            if self.z_planes > 1 and projection == "Mean":
                plane = (plane / self.z_planes).astype(np.float32)
            planes[channel - 1] = plane.astype(plane.dtype.newbyteorder("="), copy=False)
        return planes


def discover(source):
    source = Path(source).resolve()
    if not source.is_dir():
        raise ValueError(f"Input folder does not exist: {source}")
    stores = [source] if source.name.endswith(".ome.zarr") else sorted(source.glob("*.ome.zarr"))
    if not stores:
        raise ValueError("No top-level .ome.zarr stores found")
    return stores


def inspect_store(store, prompts):
    # Only the already supported BIOMERO combination; never reinterpret v3 as v2.
    if not (store / ".zgroup").is_file():
        raise ValueError(f"Expected Zarr v2 store: {store}")
    root = zarr.open_group(str(store), mode="r")
    paths = [""]
    if "plate" in root.attrs:
        paths = []
        for well in root.attrs["plate"].get("wells", []):
            wp = safe_path(well["path"])
            for image in root[wp].attrs.get("well", {}).get("images", []):
                paths.append(f"{wp}/{safe_path(image['path'])}")
        if not paths or len(paths) != len(set(paths)):
            raise ValueError("Plate has no fields or repeated field paths")
    fields = []
    for path in paths:
        group = root[path] if path else root
        scales = group.attrs.get("multiscales", [])
        if len(scales) != 1 or scales[0].get("version") != "0.4":
            raise ValueError(f"{store.name}/{path}: requires exactly one NGFF 0.4 multiscale")
        ms = scales[0]
        axes = ms.get("axes", [])
        if not axes or any(not isinstance(a, dict) or "name" not in a for a in axes):
            raise ValueError("Explicit NGFF axis metadata is required")
        names = [a["name"] for a in axes]
        dataset = safe_path(ms["datasets"][0]["path"])
        array = group[dataset]
        if len(names) != array.ndim or len(names) != len(set(names)) or not set(names) <= set("tczyx") or not {"x", "y"} <= set(names):
            raise ValueError(f"Invalid axes {names}")
        sizes = dict(zip(names, array.shape))
        if any(size < 1 for size in sizes.values()):
            raise ValueError("Every image axis must contain at least one element")
        if sizes["x"] * sizes["y"] > 16_777_216:
            raise ValueError("2D field exceeds 16 megapixels; prepare an explicit ROI first (no implicit tiling)")
        if any(c > sizes.get("c", 1) for p in prompts for c in p.channels):
            raise ValueError(f"{store.name}/{path}: requested channel does not exist (C={sizes.get('c',1)})")
        if array.dtype.kind not in "uif":
            raise ValueError(f"Unsupported pixel type: {array.dtype}")
        for ds in ms["datasets"]:
            arr = group[safe_path(ds["path"])]
            if arr.ndim != len(names):
                raise ValueError("Pyramid axis rank mismatch")
            for transform in ds.get("coordinateTransformations", []) + ms.get("coordinateTransformations", []):
                kind = transform.get("type")
                values = transform.get(kind, [])
                if kind not in ("scale", "translation") or len(values) != len(names) or not np.isfinite(values).all():
                    raise ValueError("Invalid NGFF scale/translation metadata")
                if kind == "scale" and any(float(v) <= 0 for v in values):
                    raise ValueError("NGFF scales must be positive")
        for p in prompts:
            if sizes.get("z",1) == 1 and f"labels/wevisone_{p.name}" in group:
                raise ValueError(f"Output label name already exists: wevisone_{p.name}; choose another name")
        fields.append(Field(store, path, dataset, axes, array.shape, deepcopy(ms)))
    return fields


def transform_axes(transforms, names, factor=1, remove=("c",)):
    result = []
    for tr in transforms:
        kind = tr["type"]
        values = [v for a, v in zip(names, tr[kind]) if a not in remove]
        result.append({"type": kind, kind: values})
    if factor != 1:
        # Prepend scaling in native pixel coordinates, before source transforms.
        result.insert(0, {"type": "scale", "scale": [factor if a in ("x", "y") else 1 for a in names if a not in remove]})
    return result


def canonical_axes(field, projected=False):
    kinds={"t":"time","c":"channel","z":"space","y":"space","x":"space"}
    source={a["name"]:a for a in field.axes}
    return [deepcopy(source[a]) if a in source and not (a=="z" and projected) else {"name":a,"type":kinds[a]} for a in "tczyx"]


def canonical_transforms(transforms, names, factor=1, projected=False, label=False):
    result=[]
    for tr in transforms:
        kind=tr["type"]
        old=dict(zip(names,tr[kind]))
        default=1 if kind=="scale" else 0
        result.append({"type":kind,kind:[default if a=="z" and projected or a=="c" and label else old.get(a,default) for a in "tczyx"]})
    if factor!=1:
        result.insert(0,{"type":"scale","scale":[1,1,1,factor,factor]})
    return result


def write_labels(output, field, prompt, labels, provenance, time_index=0):
    root = zarr.open_group(str(output), mode="a")
    image = root[field.path] if field.path else root
    container = image.require_group("labels")
    name = "wevisone_" + prompt.name
    group = container.create_group(name, overwrite=False) if time_index == 0 else container[name]
    axes = canonical_axes(field)
    axis_names = list("tczyx")
    data = labels
    datasets, factor, level = [], 1, 0
    while True:
        level_shape = (field.timepoints,1,1,*data.shape)
        chunks = tuple(min(n, 256) if a in ("y", "x") else 1 for a, n in zip(axis_names, level_shape))
        array = group.create_dataset(str(level), shape=level_shape, dtype=np.uint32, chunks=chunks, compressor=Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)) if time_index==0 else group[str(level)]
        array[time_index,0,0] = data
        array.attrs["_ARRAY_DIMENSIONS"] = axis_names
        transforms = canonical_transforms(field.multiscale["datasets"][0].get("coordinateTransformations", []), field.names, factor, label=True)
        if not transforms:
            transforms = [{"type": "scale", "scale": [factor if a in ("x", "y") else 1 for a in axis_names]}]
        datasets.append({"path": str(level), "coordinateTransformations": transforms})
        if max(data.shape) <= 256:
            break
        data = data[::2,::2]
        factor *= 2
        level += 1
    ms = {"version": "0.4", "name": name, "axes": axes, "datasets": datasets}
    if "coordinateTransformations" in field.multiscale:
        ms["coordinateTransformations"] = canonical_transforms(field.multiscale["coordinateTransformations"], field.names, label=True)
    history = list(group.attrs.get("ciseg_wevisonevl",{}).get("timepoints",[]))
    history.append(provenance)
    group.attrs.update({"multiscales": [ms], "image-label": {"version": "0.4", "source": {"image": "../../"}}, "ciseg_wevisonevl": {"timepoints":history}})
    declared = list(container.attrs.get("labels", []))
    if name not in declared:
        declared.append(name)
    container.attrs["labels"] = declared


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
