"""Retain small public 2D microscopy examples as NGFF 0.4/Zarr v2.

No invented physical calibration; no volume slices or projections. Organoid ZIP
members are retrieved using HTTP ranges and verified with ZIP CRC32.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
import numpy as np
import requests
import tifffile
import zarr
from numcodecs import Blosc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.io import write_json
from ciseg_wevisonevl.settings import ROOT

ORG_URL = "https://zenodo.org/api/records/14036957/files/2d-user-study-data.zip/content"
ORG_SIZE = 1356168001


def range_bytes(start, end):
    r = requests.get(ORG_URL, headers={"Range": f"bytes={start}-{end}"}, timeout=120)
    r.raise_for_status()
    if r.status_code != 206 or len(r.content) != end-start+1:
        raise RuntimeError("Server did not honor exact ZIP byte range")
    return r.content


def organoid_members():
    tail = range_bytes(ORG_SIZE-65536, ORG_SIZE-1)
    archive = zipfile.ZipFile(io.BytesIO(tail))
    return archive, ORG_SIZE - len(tail)


def fetch_member(member, offset, originals):
    # ZipFile adjusts header offsets relative to its buffer; restore global offset.
    position = member.header_offset + offset
    head = range_bytes(position, position + 29)
    if head[:4] != b"PK\x03\x04":
        raise RuntimeError("Invalid ZIP local header")
    name_len, extra_len = struct.unpack_from("<HH", head, 26)
    start = position + 30 + name_len + extra_len
    compressed = range_bytes(start, start + member.compress_size-1)
    if member.compress_type == zipfile.ZIP_DEFLATED:
        payload = zlib.decompress(compressed, -15)
    elif member.compress_type == zipfile.ZIP_STORED:
        payload = compressed
    else:
        raise ValueError("Unsupported ZIP compression")
    if len(payload) != member.file_size or zlib.crc32(payload) & 0xffffffff != member.CRC:
        raise RuntimeError("Organoid member failed size/CRC verification")
    destination = originals / Path(member.filename).name
    if destination.exists() and destination.read_bytes() != payload:
        raise FileExistsError(destination)
    destination.write_bytes(payload)
    return destination


def write_store(path, pixels, name, pixel_um=None, reference=None):
    if pixels.ndim == 2:
        cyx = pixels[None]
    elif pixels.ndim == 3 and pixels.shape[-1] in (3,4):
        cyx = pixels[...,:3].transpose(2,0,1)
    else:
        raise ValueError(f"Only 2D grayscale/RGB sources accepted, got {pixels.shape}")
    data = cyx[None,:,None]
    if reference is not None:
        if reference.shape != cyx.shape[-2:]:
            raise ValueError("Reference mask does not match source XY shape")
        np.save(path.parent / (path.name.removesuffix(".ome.zarr") + "_reference.npy"), reference, allow_pickle=False)
    if path.exists():
        root = zarr.open_group(str(path), mode="r")
        np.testing.assert_array_equal(root["0"][:], data)
        return
    root = zarr.open_group(str(path), mode="w")
    axes = [{"name":"t", "type":"time"}, {"name":"c", "type":"channel"},
            {"name":"z", "type":"space"}, {"name":"y", "type":"space"}, {"name":"x", "type":"space"}]
    if pixel_um is not None:
        axes[-1]["unit"] = axes[-2]["unit"] = "micrometer"
    datasets = []
    factor, level = 1, 0
    while True:
        arr = root.create_dataset(str(level), data=data, chunks=(1,1,1,min(256,data.shape[-2]),min(256,data.shape[-1])), compressor=Blosc(cname="zstd", clevel=3))
        arr.attrs["_ARRAY_DIMENSIONS"] = list("tczyx")
        scale = [1,1,1,(pixel_um or 1)*factor,(pixel_um or 1)*factor]
        datasets.append({"path": str(level), "coordinateTransformations": [{"type":"scale", "scale":scale}]})
        if max(data.shape[-2:]) <= 256:
            break
        # Intensity pyramids use area averaging with replicated odd edges.
        padded = np.pad(data, [(0,0)]*3 + [(0,data.shape[-2]%2),(0,data.shape[-1]%2)], mode="edge")
        averaged = padded.astype(np.float64).reshape(*data.shape[:3], padded.shape[-2]//2,2,padded.shape[-1]//2,2).mean(axis=(-3,-1))
        data = (np.rint(averaged) if data.dtype.kind in "ui" else averaged).astype(data.dtype)
        factor *= 2
        level += 1
    channels = ["Gray"] if len(cyx)==1 else ["Red", "Green", "Blue"]
    root.attrs.update({"multiscales":[{"version":"0.4","name":name,"axes":axes,"datasets":datasets}],
                       "omero":{"name":name,"channels":[{"label":c,"color":col,"active":True,"window":{"start":float(cyx[i].min()),"end":float(cyx[i].max()),"min":float(cyx[i].min()),"max":float(cyx[i].max())}} for i,(c,col) in enumerate(zip(channels,["FFFFFF"] if len(cyx)==1 else ["FF0000","00FF00","0000FF"]))]}})
    namespace = "http://www.openmicroscopy.org/Schemas/OME/2016-06"
    ET.register_namespace("", namespace)
    ome = ET.Element(f"{{{namespace}}}OME")
    image = ET.SubElement(ome,"Image",ID="Image:0",Name=name)
    attrs = dict(ID="Pixels:0", DimensionOrder="XYZCT", Type=str(cyx.dtype), SizeX=str(cyx.shape[-1]),SizeY=str(cyx.shape[-2]),SizeC=str(len(cyx)),SizeZ="1",SizeT="1")
    if pixel_um is not None:
        attrs.update(PhysicalSizeX=str(pixel_um),PhysicalSizeY=str(pixel_um),PhysicalSizeXUnit="µm",PhysicalSizeYUnit="µm")
    pix = ET.SubElement(image,"Pixels",attrs)
    for i,c in enumerate(channels):
        ET.SubElement(pix,"Channel",ID=f"Channel:0:{i}",Name=c,SamplesPerPixel="1")
    (path/"OME").mkdir()
    ET.ElementTree(ome).write(path/"OME"/"METADATA.ome.xml",encoding="utf-8",xml_declaration=True)
    np.testing.assert_array_equal(root["0"][:], cyx[None,:,None])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organoids", action="store_true", help="Also retrieve two 2D organoid images and consensus labels (~3 MB)")
    parser.add_argument("--root", type=Path, default=ROOT / "publicdata")
    args = parser.parse_args()
    originals = args.root / "originals"
    output = args.root / "ome-zarr"
    originals.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    os.environ["SKIMAGE_DATADIR"] = str(args.root / ".cache" / "skimage")
    from skimage import data
    samples = [("human_mitosis", data.human_mitosis, None, "CC0; David Root", "each bright fluorescent cell nucleus"),
               ("immunohistochemistry", data.immunohistochemistry, None, "No known copyright restrictions; CMMI", "colonic glands"),
               ("cell", data.cell, .107, "CC0; Paul Mueller et al.", "cell")]
    catalog = []
    for name, loader, calibration, license, query in samples:
        pixels = loader()
        original = originals / (name + ".tif")
        if not original.exists():
            tifffile.imwrite(original, pixels)
        path = output / (name + ".ome.zarr")
        write_store(path, pixels, name, calibration)
        catalog.append({"name":name,"source":"https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data."+name,
                        "license":license,"suggested_query":query,"channels":"1,2,3" if pixels.ndim==3 else "1",
                        "normalization":"dtype" if pixels.ndim==3 else "percentile", "pixel_um":calibration,
                        "original_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),"shape":list(pixels.shape)})
        print(f"READY: {path} {pixels.shape}", flush=True)
    if args.organoids:
        archive, offset = organoid_members()
        available = archive.namelist()
        for image_name in ["im9.tif", "im10.tif"]:
            member_path = "final_dataset/test/images/" + image_name
            original = fetch_member(archive.getinfo(member_path), offset, originals)
            pixels = tifffile.imread(original)
            label_path = "final_dataset/test/masks/" + image_name
            reference = None
            if label_path in available:
                member = archive.getinfo(label_path)
                labels_dir = originals/"consensus_labels"
                labels_dir.mkdir(exist_ok=True)
                ref_file = fetch_member(member, offset, labels_dir)
                reference = tifffile.imread(ref_file)
            name = "organoids_" + original.stem
            write_store(output/(name+".ome.zarr"), pixels, name, reference=reference)
            catalog.append({"name":name,"source":"https://zenodo.org/records/14036957","license":"CC BY 4.0",
                            "zip_member":member_path,"zip_member_crc32":archive.getinfo(member_path).CRC,
                            "original_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),"shape":list(pixels.shape),
                            "suggested_query":"organoids","channels":"1","normalization":"percentile",
                            "pixel_um":None,"reference":label_path if reference is not None else None})
            print(f"READY: {name} {pixels.shape}, consensus reference: {reference is not None}", flush=True)
    catalog_path=args.root/'catalog.json'
    existing=json.loads(catalog_path.read_text(encoding='utf-8-sig')) if catalog_path.exists() else []
    combined={row['name']:row for row in existing}
    combined.update({row['name']:row for row in catalog})
    write_json(catalog_path,list(combined.values()))


if __name__ == "__main__":
    main()
