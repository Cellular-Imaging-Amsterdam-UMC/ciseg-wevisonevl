"""Stream per-T/per-C Z projections into a new output; never modify the source."""
from copy import deepcopy
from pathlib import Path, PurePosixPath
import shutil
import xml.etree.ElementTree as ET
import numpy as np
import zarr
from numcodecs import Blosc
from .io import canonical_axes, canonical_transforms, inspect_store


def area_downsample(plane):
    padded=np.pad(plane,[(0,plane.shape[0]%2),(0,plane.shape[1]%2)],mode="edge")
    result=padded.astype(np.float64).reshape(padded.shape[0]//2,2,padded.shape[1]//2,2).mean(axis=(1,3))
    if plane.dtype.kind in "ui":
        result=np.rint(result)
    return result.astype(plane.dtype)


def update_xml(output, method):
    # Every actual Z>1 image in the selected store is projected, including HCS.
    for file in output.rglob("METADATA.ome.xml"):
        tree=ET.parse(file)
        changed=False
        for pixels in tree.getroot().iterfind(".//{*}Pixels"):
            if int(pixels.get("SizeZ","1")) <= 1:
                continue
            pixels.set("SizeZ","1")
            if method=="Mean":
                pixels.set("Type","float")
            pixels.attrib.pop("PhysicalSizeZ",None)
            pixels.attrib.pop("PhysicalSizeZUnit",None)
            for child in list(pixels):
                tag=child.tag.rsplit("}",1)[-1]
                if tag in ("TiffData","BinData") or tag=="Plane" and child.get("TheZ","0")!="0":
                    pixels.remove(child)
                elif tag=="Plane":
                    child.attrib.pop("PositionZ",None)
                    child.attrib.pop("PositionZUnit",None)
            changed=True
        if changed:
            tree.write(file,encoding="utf-8",xml_declaration=True)


def prepare_output(source, output, fields, prompts, method):
    projected=[f for f in fields if f.z_planes>1]
    rewritten=[f for f in fields if f.z_planes>1 or f.names!=list("tczyx")]
    skipped={}
    for field in rewritten:
        base=PurePosixPath(field.path) if field.path else PurePosixPath()
        if field.z_planes>1:
            skipped.setdefault(str(base),set()).add("labels")
        for dataset in field.multiscale["datasets"]:
            path=base/PurePosixPath(dataset["path"])
            skipped.setdefault(str(path.parent),set()).add(path.name)
    def ignore(directory,names):
        relative=Path(directory).relative_to(source).as_posix()
        return (skipped.get(relative,set()) | {".zmetadata"}) & set(names)
    shutil.copytree(source,output,ignore=ignore)
    (output/".zmetadata").unlink(missing_ok=True)
    root=zarr.open_group(str(output),mode="a")
    for field in rewritten:
        group=root[field.path] if field.path else root
        axes=canonical_axes(field,projected=field.z_planes>1)
        names=list("tczyx")
        sizes=dict(zip(field.names,field.shape))
        original=zarr.open_group(str(source),mode="r")
        original=original[field.path] if field.path else original
        dtype=np.dtype("float32") if method=="Mean" and field.z_planes>1 else original[field.dataset].dtype
        height,width=sizes["y"],sizes["x"]
        levels=[]
        factor=1
        while True:
            level=str(len(levels))
            shape=(field.timepoints,sizes.get("c",1),1,height,width)
            chunks=tuple(min(n,256) if a in ("x","y") else 1 for a,n in zip(names,shape))
            arr=group.create_dataset(level,shape=shape,dtype=dtype,chunks=chunks,compressor=Blosc(cname="zstd",clevel=3))
            arr.attrs["_ARRAY_DIMENSIONS"]=names
            transforms=canonical_transforms(field.multiscale["datasets"][0].get("coordinateTransformations",[]),field.names,factor,projected=field.z_planes>1)
            if not transforms:
                transforms=[{"type":"scale","scale":[factor if a in ("x","y") else 1 for a in names]}]
            levels.append({"path":level,"coordinateTransformations":transforms})
            if max(height,width)<=256:
                break
            height,width=(height+1)//2,(width+1)//2
            factor*=2
        for time_index in range(field.timepoints):
            for channel in range(1,sizes.get("c",1)+1):
                plane=field.pixels([channel],time_index,method)[channel-1]
                for level in range(len(levels)):
                    group[str(level)][time_index,channel-1,0]=plane
                    if level<len(levels)-1:
                        plane=area_downsample(plane)
        ms=deepcopy(field.multiscale)
        ms.update(axes=axes,datasets=levels)
        if "coordinateTransformations" in ms:
            ms["coordinateTransformations"]=canonical_transforms(ms["coordinateTransformations"],field.names,projected=field.z_planes>1)
        group.attrs["multiscales"]=[ms]
        if "omero" in group.attrs:
            display=deepcopy(group.attrs["omero"])
            if "rdefs" in display:
                display["rdefs"]["defaultZ"]=0
            group.attrs["omero"]=display
        if "labels" in group.attrs:
            del group.attrs["labels"]
        group.attrs["ciseg_wevisonevl_projection"]={"method":method if field.z_planes>1 else "none","source_z_planes":field.z_planes,"timepoints":field.timepoints,
                                                   "source_dtype":str(original[field.dataset].dtype),"output_dtype":str(dtype),
                                                   "source_axes":field.names,"output_axes":names,
                                                   "existing_volume_labels":"omitted from projected output; retained in source"}
    if projected:
        update_xml(output,method)
    return {field.path:field for field in inspect_store(output,prompts)}
