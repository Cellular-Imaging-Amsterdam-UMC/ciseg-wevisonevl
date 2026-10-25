"""Validate and export the retained dataset catalog, thumbnails and proposed prompts."""
import argparse,base64,csv,html,io,json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT,Settings,Prompt
from ciseg_wevisonevl.engine import preflight
from ciseg_wevisonevl.inference import render_rgb
from ciseg_wevisonevl.io import write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    catalog=ROOT/'publicdata/catalog.json';records=json.loads(catalog.read_text(encoding='utf-8-sig'))
    cards=[];thumbs=[];csv_rows=[]
    for record in records:
        source=ROOT/'publicdata/ome-zarr'/(record['name']+'.ome.zarr')
        fallback={'name':record.get('label_name','target'),'text':record['suggested_query'],'channels':record['channels']}
        presets=record.get('prompt_presets') or [fallback]
        prompts=[Prompt(p['name'],p['text'],tuple(map(int,p.get('channels',record['channels']).split(',')))) for p in presets]
        settings=Settings(normalization=record['normalization'])
        jobs=preflight(source,ROOT/'work/catalog-validation',settings,prompts)
        field=jobs[0][2][0]
        if record.get('axes')!=field.names and 'original_shape' not in record:record['original_shape']=record.get('shape')
        record.update(shape=list(field.shape),axes=field.names,stored_bytes=sum(p.stat().st_size for p in source.rglob('*') if p.is_file()),format_validation='preflight passed',timepoints=field.timepoints,z_planes=field.z_planes)
        channels=tuple(map(int,record['channels'].split(',')))
        image,limits=render_rgb(field.pixels(channels,0,'Max'),channels,record['normalization'])
        image.thumbnail((600,420),Image.Resampling.LANCZOS)
        buffer=io.BytesIO();image.save(buffer,format='PNG');encoded=base64.b64encode(buffer.getvalue()).decode()
        shape=' × '.join(str(n) for n in field.shape)
        kind=record.get('kind','Earlier 2D example')
        extra='Max Z preview' if field.z_planes>1 else 'Timepoint 0' if field.timepoints>1 else '2D'
        prompts_html=''.join('<li><code>'+html.escape(p['name'])+'</code>: '+html.escape(p['text'])+'</li>' for p in presets)
        notes=record.get('note','')
        cards.append(f'<article><h2>{html.escape(record["name"])}</h2><p>{html.escape(kind)} · {record["stored_bytes"]/1e6:.2f} MB</p><img src="data:image/png;base64,{encoded}" alt="{html.escape(record["name"])}"><p><code>{shape}</code> TCZYX · {extra}</p><ul>{prompts_html}</ul><p>{html.escape(notes)}</p><details><summary>Herkomst en selectie</summary><p><a href="{html.escape(record["source"],quote=True)}">{html.escape(record["source"])}</a></p><p>{html.escape(record.get("license","See source"))}</p><pre>{html.escape(json.dumps(record.get("selection",record.get("source_provenance",{})),indent=2))}</pre></details></article>')
        thumbs.append((record['name'],np.asarray(image)))
        csv_rows.append({'name':record['name'],'TCZYX':str(field.shape),'MB':round(record['stored_bytes']/1e6,2),'kind':kind,'source':record['source'],
                         'prompts':' | '.join(p['text'] for p in presets),'normalization':record['normalization'],'channels':record['channels'],'validation':'preflight passed'})
    write_json(catalog,records)
    new=[r for r in records if r['name'].startswith(('local-','public-'))]
    summary={'total_examples':len(records),'added_examples':len(new),'ready_bytes':sum(r['stored_bytes'] for r in records),'added_ready_bytes':sum(r['stored_bytes'] for r in new),
             'added_2d':sum(r['z_planes']==1 and r['timepoints']==1 for r in new),'added_3d':sum(r['z_planes']>1 for r in new),'added_time_series':sum(r['timepoints']>1 for r in new),
             'source_stores_unchanged':True,'model_inference_on_new_examples':'not run; prompt presets are starting suggestions, not validated results'}
    write_json(args.output/'CISegWeVisOneVL-datacatalogus.json',{'summary':summary,'examples':records})
    with (args.output/'CISegWeVisOneVL-datacatalogus.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(csv_rows[0]));writer.writeheader();writer.writerows(csv_rows)
    document=f'''<!doctype html><html lang="nl"><meta charset="utf-8"><title>CISegWeVisOneVL — extra voorbeelden</title>
<style>body{{font:16px/1.5 system-ui;background:#f3f6fa;color:#1d3048;max-width:1550px;margin:auto;padding:28px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:20px}}article{{background:white;border:1px solid #d8e1ed;border-radius:12px;padding:20px;overflow:hidden}}h2{{font-size:18px}}img{{width:100%;height:250px;object-fit:contain;background:#eee}}pre{{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere}}code{{font-size:13px}}a{{overflow-wrap:anywhere}}.intro{{background:white;padding:24px;border-radius:12px;margin-bottom:25px}}</style>
<h1>CISegWeVisOneVL — uitgebreide voorbeeldset</h1><div class="intro"><p><b>{len(new)} nieuwe voorbeelden; {len(records)} totaal.</b> De complete set met OME-Zarr-invoer is {summary['ready_bytes']/1e6:.1f} MB. De originele archieven, WSI-bestanden en opgehaalde EM-chunks worden apart bewaard en tellen hierin niet mee.</p>
<p>Kies een voorbeeld in de launcher; maximaal vier voorgestelde prompts worden ingevuld. Alle voorbeelden hebben de invoercontrole doorlopen. Er is nog geen modelkwaliteitsmeting op deze nieuwe voorbeelden uitgevoerd.</p>
<p>3D wordt per tijdpunt automatisch geprojecteerd. Bij EM kunnen Max en Mean organellen over elkaar leggen; gebruik de meegeleverde 2D-doorsnede om afzonderlijke membranen en organellen te beoordelen. Coupe-overzichten tonen de gehele aangeleverde scan op een bestaande lagere resolutie. Het DAB-detail is een expliciet geregistreerde uitsnede. Intensiteiten blijven in hun oorspronkelijke kanalen; de vier kanalen van de plantstengel zijn alle vier bewaard.</p>
<p>Elke segmentatierun maakt één <code>measurements.csv</code> met shape features en min/max/mean/total-intensiteit voor alle kanalen. De Bilayers-descriptor declareert dit bestand als measurement-uitvoer voor BIOMERO-attachments.</p>
<p>Herkomst: lokale PublicData-map, <a href="https://cellmapchallenge.janelia.org/">CellMap/Janelia</a>, <a href="https://zenodo.org/records/18302140">QuPath-workshop</a>, <a href="https://imagej.net/ij/images/">ImageJ</a>, <a href="https://scikit-image.org/docs/stable/api/skimage.data.html">scikit-image</a>, <a href="https://mib.helsinki.fi/help/main2/user-interface/menu/tools/tools-watershed.html">MIB/Helsinki</a>.</p></div><div class="grid">{''.join(cards)}</div></html>'''
    (args.output/'CISegWeVisOneVL-extra-voorbeelden.html').write_text(document,encoding='utf-8')
    selected=[(name,pixels) for name,pixels in thumbs if name.startswith(('local-','public-'))]
    rows=(len(selected)+3)//4;fig,axes=plt.subplots(rows,4,figsize=(16,3.4*rows),layout='constrained')
    for ax,(name,pixels) in zip(axes.flat,selected):ax.imshow(pixels);ax.set_title(name,fontsize=9);ax.axis('off')
    for ax in list(axes.flat)[len(selected):]:ax.axis('off')
    fig.suptitle('CISegWeVisOneVL — nieuwe biologische voorbeelden',fontsize=18)
    fig.savefig(args.output/'CISegWeVisOneVL-extra-contactsheet.png',dpi=120);plt.close(fig)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
