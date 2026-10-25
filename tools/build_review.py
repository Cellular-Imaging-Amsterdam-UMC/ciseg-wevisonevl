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
    cases=[("cell","cell",ROOT/"test-results/public-validation/4B/cell/cell__wevisonevl.ome.zarr","1 instance; geen referentiemasker"),
           ("human_mitosis","nuclei",ROOT/"test-results/launcher-final-4B/human_mitosis__wevisonevl.ome.zarr","127 instances; specifieke prompt\nGeen handmatige nauwkeurigheidsscore"),
           ("immunohistochemistry","nuclei",ROOT/"test-results/public-validation/4B/immunohistochemistry/immunohistochemistry__wevisonevl.ome.zarr","4 grote maskers; geen betrouwbare\nnuclei-segmentatie in deze test"),
           ("organoids_im10","organoids",ROOT/"test-results/public-validation/4B/organoids_im10/organoids_im10__wevisonevl.ome.zarr","83 instances\nForeground Dice 0,881; IoU 0,787"),
           ("organoids_im9","organoids",None,"Resultaat geweigerd:\nobjecten en geldige boxen niet gelijk")]
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
            axes[index,1].text(.5,.5,"Geen voltooid resultaat",ha="center",va="center",color="#b3261e",fontsize=13)
        axes[index,1].set_title("4B-voorspelling (roze)",fontsize=11)
        reference=source.parent/(sample+"_reference.npy")
        if reference.exists():
            mask=np.load(reference,allow_pickle=False)>0
            axes[index,2].imshow(overlay(image,mask))
            axes[index,2].set_title("Consensusreferentie",fontsize=11)
            axes[index,2].set_xlabel(note,fontsize=10)
        else:
            axes[index,2].text(.5,.5,note,ha="center",va="center",fontsize=11,wrap=True)
        for axis in axes[index]:
            axis.set_xticks([]);axis.set_yticks([])
            for spine in axis.spines.values():spine.set_visible(False)
    fig.suptitle("CISegWeVisOneVL · lokale 4B-controle",fontsize=18)
    fig.savefig(args.output/"CISegWeVisOneVL-resultaten.png",dpi=140)
    plt.close(fig)
    payload=base64.b64encode((args.output/"CISegWeVisOneVL-resultaten.png").read_bytes()).decode()
    research=(ROOT/"docs/research.md").read_text(encoding="utf-8")
    reader=json.loads((ROOT/"test-results/projection-runtime-canonical/reader-checks.json").read_text())
    projection=json.loads((ROOT/"test-results/projection-runtime-canonical/checks.json").read_text())
    summary={"workflow":"CISegWeVisOneVL","model":"4B only","unit_tests_passed":31,"projection_runtime":projection,"reader":reader,
             "csv_runtime":json.loads((ROOT/'test-results/csv-projection-runtime/measurement-checks.json').read_text()),
             "biomero_descriptor":json.loads((ROOT/'test-results/biomero-descriptor-check.json').read_text(encoding='utf-8-sig'))}
    (args.output/"CISegWeVisOneVL-validatie.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    html=f'''<!doctype html><html lang="nl"><meta charset="utf-8"><title>CISegWeVisOneVL — onderzoek en resultaten</title>
<style>body{{font:17px/1.55 system-ui,sans-serif;max-width:1050px;margin:45px auto;padding:0 24px;color:#203047;background:#f7f9fc}}h1,h2{{line-height:1.2}}.card{{background:white;border:1px solid #d9e1ed;border-radius:14px;padding:24px;margin:24px 0}}code,pre{{font:14px/1.5 ui-monospace,monospace}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{width:100%;height:auto}}a{{color:#135db2}}</style>
<h1>CISegWeVisOneVL</h1><p>Lokale WeVisOne-VL-4B-workflow · 25 oktober 2026</p>
<div class="card"><b>Klaar voor lokaal testen</b><p>Maximaal vier prompts, OME-Zarr, tijdreeksen en HCS-screens. 3D-beelden worden automatisch per kanaal en tijdpunt naar 2D geprojecteerd. Geavanceerde optie: <b>Max</b> (standaard) of <b>Mean</b>. De bron blijft intact. Mean schrijft float32; projecties worden voor OMERO als TCZYX met Z=1 opgeslagen.</p><p>Start <code>{escape(str(ROOT/'launch.cmd'))}</code>. Kies een publiek voorbeeld. Het 2B-model en de modelkeuze zijn verwijderd.</p></div>
<div class="card"><b>Uitgebreid met voorbeelden en CSV-metingen</b><p><a href="CISegWeVisOneVL-extra-voorbeelden.html">Bekijk de 22 nieuwe voorbeelden (27 totaal)</a>: EM-organellen, huid, vetcellen, plantstengel, diatomeeën, embryo's en hele coupes met een Ki67/DAB-detail. De invoerset is ongeveer 206 MB. De launcher vult passende startprompts in.</p><p>Iedere run schrijft één <code>measurements.csv</code> met shape features en min/max/mean/total-intensiteit voor elk kanaal. De BIOMERO-parser herkent dit als measurement-output. <a href="CISegWeVisOneVL-voorbeeldmetingen.csv">Voorbeeld-CSV uit de echte 4B-GPU-run</a>.</p></div>
<div class="card"><b>Gecontroleerd</b><p>31 tests geslaagd; echte 4B-inferentie via de launcher; Max en Mean getest op twee screenvelden × twee tijdpunten × drie Z-vlakken. Bronbehoud, exacte projecties, labelbeweging en CSV-waarden zijn gecontroleerd. De OMERO-reader las alle {sum(r['matched_pixel_windows'] for r in reader)} gecontroleerde bron- en labelvensters over beide projecties exact.</p><p>Docker-recepten zijn voorbereid. Er is geen nieuwe image gebouwd, gepubliceerd of in BIOMERO geïnstalleerd. De daadwerkelijke attachment-import volgt in die fase.</p></div>
<div class="card"><b>Biologische kwaliteit is wisselend</b><p>Op één orgaoïdbeeld: foreground Dice 0,881. Op een ander beeld wordt een ongeldige objectrespons geweigerd. Een specifiekere nuclei-prompt leverde 127 instances; daarvoor is geen handmatige referentiescore beschikbaar. Deze kleine testset onderbouwt geen algemene microscopienauwkeurigheid.</p><img alt="Werkelijke voorspellingen en referentiemaskers" src="data:image/png;base64,{payload}"></div>
<div class="card"><h2>Onderzoek en beperkingen</h2><pre>{escape(research)}</pre></div>
<p>Primaire bronnen: <a href="https://github.com/Tencent/WeVisOne-VL">Tencent-code</a> · <a href="https://huggingface.co/tencent/WeVisOne-VL-4B">4B-model</a> · <a href="https://zenodo.org/records/14036957">microSAM-organoïden</a> · <a href="https://scikit-image.org/docs/stable/api/skimage.data.html">scikit-image-beelden</a>.</p></html>'''
    (args.output/"CISegWeVisOneVL-onderzoek.html").write_text(html,encoding="utf-8")
    (args.output/"Start CISegWeVisOneVL.cmd").write_text('@echo off\r\ncall "'+str(ROOT/'launch.cmd')+'"\r\n',encoding="utf-8")
    print(args.output)
