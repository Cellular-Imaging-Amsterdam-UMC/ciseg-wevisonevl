"""Export a compact scientific gallery and an offline local review report."""
import argparse
import base64
from html import escape
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import zarr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import inspect_store
from ciseg_wevisonevl.inference import render_rgb


def panel_image(source,channels=(1,),normalization="percentile"):
    field=inspect_store(source,[])[0]
    image,_=render_rgb(field.pixels(channels),channels,normalization)
    image.thumbnail((800,800),Image.Resampling.LANCZOS)
    return image


def overlay(image,labels):
    mask=np.asarray(Image.fromarray(np.squeeze(labels).astype(np.uint8)).resize(image.size,Image.Resampling.NEAREST))>0
    pixels=np.asarray(image).copy()
    pixels[mask]=(.55*pixels[mask]+.45*np.array([255,50,160])).astype(np.uint8)
    return pixels


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    cases=[("cell","cell",ROOT/"test-results/public-validation/4B/cell/cell__wevisonevl.ome.zarr","1 instance; no reference mask"),
           ("human_mitosis","nuclei",ROOT/"test-results/launcher-final-4B/human_mitosis__wevisonevl.ome.zarr","127 instances; specific prompt\nNo manual accuracy score"),
           ("immunohistochemistry","nuclei",ROOT/"test-results/public-validation/4B/immunohistochemistry/immunohistochemistry__wevisonevl.ome.zarr","4 large masks; unreliable\nnuclei segmentation in this test"),
           ("organoids_im10","organoids",ROOT/"test-results/public-validation/4B/organoids_im10/organoids_im10__wevisonevl.ome.zarr","83 instances\nForeground Dice 0.881; IoU 0.787"),
           ("organoids_im9","organoids",None,"Result rejected:\nobject and valid-box counts differ")]
    fig,axes=plt.subplots(len(cases),3,figsize=(12,17),layout="constrained")
    for index,(sample,label,output,note) in enumerate(cases):
        source=ROOT/"publicdata/ome-zarr"/(sample+".ome.zarr")
        image=panel_image(source,(1,2,3) if sample=="immunohistochemistry" else (1,),"dtype" if sample=="immunohistochemistry" else "percentile")
        axes[index,0].imshow(image)
        axes[index,0].set_title(sample.replace("_"," "),fontsize=11)
        if output:
            root=zarr.open_group(str(output),mode="r")
            labels=root[f"labels/wevisone_{label}/0"][:]>0
            axes[index,1].imshow(overlay(image,labels))
        else:
            axes[index,1].text(.5,.5,"No completed result",ha="center",va="center",color="#b3261e",fontsize=13)
        axes[index,1].set_title("4B prediction (pink)",fontsize=11)
        reference=source.parent/(sample+"_reference.npy")
        if reference.exists():
            mask=np.load(reference,allow_pickle=False)>0
            axes[index,2].imshow(overlay(image,mask))
            axes[index,2].set_title("Consensus reference",fontsize=11)
            axes[index,2].set_xlabel(note,fontsize=10)
        else:
            axes[index,2].text(.5,.5,note,ha="center",va="center",fontsize=11,wrap=True)
        for axis in axes[index]:
            axis.set_xticks([]);axis.set_yticks([])
            for spine in axis.spines.values():spine.set_visible(False)
    fig.suptitle("CISegWeVisOneVL · local 4B validation",fontsize=18)
    fig.savefig(args.output/"CISegWeVisOneVL-results.png",dpi=140)
    plt.close(fig)
    payload=base64.b64encode((args.output/"CISegWeVisOneVL-results.png").read_bytes()).decode()
    research=(ROOT/"docs/research.md").read_text(encoding="utf-8")
    reader=json.loads((ROOT/"test-results/projection-runtime-canonical/reader-checks.json").read_text())
    projection=json.loads((ROOT/"test-results/projection-runtime-canonical/checks.json").read_text())
    summary={"workflow":"CISegWeVisOneVL","model":"4B only","unit_tests_passed":31,"projection_runtime":projection,"reader":reader,
             "csv_runtime":json.loads((ROOT/'test-results/csv-projection-runtime/measurement-checks.json').read_text()),
             "biomero_descriptor":json.loads((ROOT/'test-results/biomero-descriptor-check.json').read_text(encoding='utf-8-sig'))}
    (args.output/"CISegWeVisOneVL-validation.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>CISegWeVisOneVL — research and results</title>
<style>body{{font:17px/1.55 system-ui,sans-serif;max-width:1050px;margin:45px auto;padding:0 24px;color:#203047;background:#f7f9fc}}h1,h2{{line-height:1.2}}.card{{background:white;border:1px solid #d9e1ed;border-radius:14px;padding:24px;margin:24px 0}}code,pre{{font:14px/1.5 ui-monospace,monospace}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{width:100%;height:auto}}a{{color:#135db2}}</style>
<h1>CISegWeVisOneVL</h1><p>Local WeVisOne-VL-4B workflow · 25 October 2026</p>
<div class="card"><b>Ready for local testing</b><p>Up to four prompts, OME-Zarr, time series and HCS screens. 3D stacks are automatically projected per channel and timepoint: Max by default, or Mean with float32 output. Sources remain untouched.</p><p>Start <code>{escape(str(ROOT/'launch.cmd'))}</code> and select a public example. Only the 4B model is used.</p></div>
<div class="card"><b>Examples and measurements</b><p><a href="CISegWeVisOneVL-extra-examples.html">Explore the expanded collection</a>: EM organelles, skin, adipocytes, plant tissue, diatoms, embryos and whole-section overviews with a Ki67/DAB detail. Inputs total approximately 206 MB.</p><p>Each run writes <code>measurements.csv</code> with shape and per-channel intensity features. <a href="CISegWeVisOneVL-example-measurements.csv">Actual GPU-run CSV example</a>.</p></div>
<div class="card"><b>Validated behavior</b><p>31 tests pass. GPU checks cover Max/Mean, two screen fields, two timepoints and three Z planes. Projection values, source preservation, label movement and CSV measurements were checked. The reader matched all {sum(r['matched_pixel_windows'] for r in reader)} tested pixel windows.</p><p>Docker recipes are prepared; no new image was built or deployed. A live attachment import remains for that phase.</p></div>
<div class="card"><b>Biological accuracy varies</b><p>One organoid image achieved foreground Dice 0.881; another produced an invalid response. A specific nuclear query produced 127 instances without a manual accuracy reference. The test set does not establish general microscopy accuracy.</p><img alt="Actual predictions and reference masks" src="data:image/png;base64,{payload}"></div>
<div class="card"><h2>Research and limitations</h2><pre>{escape(research)}</pre></div>
<p>Primary sources: <a href="https://github.com/Tencent/WeVisOne-VL">Tencent code</a> · <a href="https://huggingface.co/tencent/WeVisOne-VL-4B">4B model</a> · <a href="https://zenodo.org/records/14036957">microSAM organoids</a> · <a href="https://scikit-image.org/docs/stable/api/skimage.data.html">scikit-image</a>.</p></html>'''
    (args.output/"CISegWeVisOneVL-review.html").write_text(html,encoding="utf-8")
    (args.output/"Start CISegWeVisOneVL.cmd").write_text('@echo off\r\ncall "'+str(ROOT/'launch.cmd')+'"\r\n',encoding="utf-8")
    print(args.output)
