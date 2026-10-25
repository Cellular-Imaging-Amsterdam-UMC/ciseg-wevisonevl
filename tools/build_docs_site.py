"""Build portable public docs from retained images and actual gallery inference results."""
import argparse,csv,html,json,re,sys
from pathlib import Path
import numpy as np
from PIL import Image
import markdown
import zarr

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ciseg_wevisonevl.settings import ROOT
from ciseg_wevisonevl.io import inspect_store,write_json
from ciseg_wevisonevl.inference import render_rgb

REPO='https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl'
PAGES='https://cellular-imaging-amsterdam-umc.github.io/ciseg-wevisonevl/'
E=html.escape


def page(title,body,current=''):
    icon='<svg viewBox="0 0 40 40" fill="none" aria-hidden="true"><rect x="2" y="2" width="36" height="36" rx="10" stroke="currentColor"/><rect x="9" y="9" width="9" height="9" rx="2" fill="#a83469"/><rect x="22" y="9" width="9" height="9" rx="2" fill="#d1a9b8"/><rect x="9" y="22" width="9" height="9" rx="2" fill="#9bc8b5"/><rect x="22" y="22" width="9" height="9" rx="2" fill="currentColor"/></svg>'
    nav=''.join(f'<a href="{url}"'+(' aria-current="page"' if current==name else '')+f'>{label}</a>' for name,url,label in [('home','index.html','Overzicht'),('workflow','workflow.html','Workflow'),('examples','examples.html','Voorbeelden'),('research','research.html','Validatie')])
    return f'''<!doctype html><html lang="nl" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="CISegWeVisOneVL: tekstgestuurde biologische segmentatie van OME-Zarr, automatische 3D-projectie en echte publieke voorbeeldresultaten."><title>{E(title)} · CISegWeVisOneVL</title><script src="assets/theme.js"></script><link rel="stylesheet" href="assets/style.css"><link rel="stylesheet" href="assets/themes.css"><script src="assets/site.js" defer></script></head><body><a class="skip" href="#main">Naar inhoud</a><header class="topbar"><div class="shell nav"><a class="brand" href="index.html">{icon} CISegWeVisOneVL</a><nav class="navlinks" aria-label="Hoofdnavigatie">{nav}<button type="button" class="theme-toggle" data-theme-toggle aria-label="Thema: Dark. Wissel naar Bright" aria-pressed="true"><span class="theme-bright">Bright</span><span class="theme-dark">Dark</span></button><a class="repo" href="{REPO}">GitHub ↗</a></nav></div></header><main class="shell" id="main">{body}</main><footer class="footer"><div class="shell footer-row"><span>Cellular Imaging · Amsterdam UMC</span><span>WeVisOne-VL-4B · Versie 0.1.0 · Resultaten van 25 oktober 2026</span><a href="{REPO}/blob/main/NOTICE.md">Bronnen & licenties</a></div></footer></body></html>'''


def source_links(record):
    candidates=[record.get('source'),record.get('original_url')]
    for key in ['source_provenance','selection']:
        obj=record.get(key,{})
        candidates.extend(obj.get(k) for k in ['source_url','reference','source'])
    if record['name']=='local-CMU1-whole-section':candidates.append('https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/')
    if record['name']=='local-REAL-LYSOSOME':candidates.append('https://zenodo.org/records/14043236')
    return list(dict.fromkeys(c for c in candidates if isinstance(c,str) and c.startswith(('https://','http://'))))


def category(record):
    name=record['name'];kind=record.get('kind','').lower()
    if '-em-' in name:return 'EM'
    if any(x in name for x in ['skin','adipose','section','ki67','immunohistochemistry']):return 'Histologie & weefsel'
    if any(x in name for x in ['neur','dendrit','brain','retina']):return 'Neuronaal & vaten'
    if any(x in name for x in ['lily','diatoms','embryos']):return 'Overige structuren'
    return 'Cellen & organoïden'


def public_error(message):
    return re.sub(r'[A-Za-z]:[\\/][^\n]+','<lokale bestandslocatie>',message or '')


def export_site(destination,inference):
    destination.mkdir(parents=True,exist_ok=True)
    asset=destination/'gallery';asset.mkdir(exist_ok=True)
    downloads=destination/'downloads';downloads.mkdir(exist_ok=True)
    records=json.loads((ROOT/'publicdata/catalog.json').read_text(encoding='utf-8-sig'))
    manifest=json.loads((inference/'manifest.json').read_text())
    public=[];cards=[];md=['# Publieke voorbeelden en werkelijke segmentaties','',
        'Alle voorbeelden gebruiken WeVisOne-VL-4B. De afbeeldingen tonen tijdpunt 0; bij Z-stacks wordt Max-projectie gebruikt. Labelbestanden bevatten alle met succes berekende tijdpunten. Geweigerde voorspellingen zijn geen lege achtergrondmaskers.','',
        '[Interactieve HTML-galerij](examples.html) · [Workflow](workflow.md) · [Bronnen en validatie](research.md)','']
    for record in records:
        name=record['name'];source=ROOT/'publicdata/ome-zarr'/(name+'.ome.zarr');field=inspect_store(source,[])[0]
        channels=tuple(map(int,record['channels'].split(',')))
        image,_=render_rgb(field.pixels(channels,0,'Max'),channels,record['normalization'])
        image.thumbnail((720,520),Image.Resampling.LANCZOS)
        image_file=f'gallery/{name}-input.webp';image.save(destination/image_file,quality=90)
        presets=record.get('prompt_presets') or [{'name':record.get('label_name','nuclei' if name=='human_mitosis' else 'glands' if name=='immunohistochemistry' else 'organoids' if name.startswith('organoids') else 'cell'),
                                                 'text':record['suggested_query'],'channels':record['channels']}]
        results=manifest['examples'].get(name,{}).get('labels',{})
        labels=[];measurement_rows=[];measurement_columns=[]
        md.extend([f'## {name}','',f'![Bronbeeld: {name}]({image_file})','',f'**Vorm:** `{field.shape}` (TCZYX) · **type:** {category(record)} · **opslag:** {record.get("stored_bytes",0)/1e6:.2f} MB',''])
        for preset in presets:
            label=preset['name'];result=results.get(label,{})
            frames=result.get('frames',[]);available=[int(f['time_index']) for f in frames]
            state=result.get('status','pending')
            if state=='failed' and available:state='partial'
            entry={'name':label,'text':preset['text'],'channels':list(map(int,preset.get('channels',record['channels']).split(','))),
                   'status':state,'overlay':None,'download':None,'timepoints_available':available}
            error=public_error(result.get('error',''))
            if state in ['complete','partial'] and available:
                store=inference/result.get('output',result.get('partial_output'))
                root=zarr.open_group(str(store),mode='r');array=root[f'labels/wevisone_{label}/0']
                masks=np.asarray(array.oindex[available,:,:,:,:])
                count=int(frames[0]['retained_instances'])
                mask=np.asarray(Image.fromarray((masks[0,0,0]>0).astype(np.uint8)).resize(image.size,Image.Resampling.NEAREST))>0
                overlay=np.asarray(image).copy();overlay[mask]=(.55*overlay[mask]+.45*np.array([255,50,160])).astype(np.uint8)
                overlay_file=f'gallery/{name}-{label}-overlay.webp';Image.fromarray(overlay).save(destination/overlay_file,quality=92)
                label_file=f'downloads/{name}-{label}-labels.npz'
                np.savez_compressed(destination/label_file,labels=masks.astype(np.uint32),time_indices=np.array(available,dtype=np.int32),axes=np.array('tczyx'))
                entry.update(overlay=overlay_file,download=label_file,first_frame_objects=count,
                             message=f'Tijdpunt {available[0]}: {count} voorspelde objecten. {len(available)}/{field.timepoints} tijdpunten berekend.'+(' Latere tijdpunten geweigerd: '+error if state=='partial' else ''))
                coverage=float(frames[0].get('foreground_fraction',np.count_nonzero(masks[0,0,0])/masks[0,0,0].size))
                entry['foreground_fraction']=coverage
                entry['message']+=f' Maskerdekking: {coverage:.1%}.'
                if frames[0].get('review_note'):entry['message']+=' Grote dekking: controleer voorgrond en achtergrond in de overlay.'
                if count==0:entry['message']+=' Het model gaf een leeg masker; dit is geen bewijs dat de structuur afwezig is.'
                reference=source.parent/(name+'_reference.npy')
                if reference.exists() and state=='complete':
                    truth=np.load(reference,allow_pickle=False)>0;prediction=masks[0,0,0]>0
                    intersection=int((truth&prediction).sum());denominator=int(truth.sum())+int(prediction.sum())
                    entry['foreground_dice']=2*intersection/denominator if denominator else 1.
                    entry['message']+=f' Foreground Dice: {entry["foreground_dice"]:.3f} tegen consensus (geen instance-score).'
                if result.get('measurements'):
                    with (inference/result['measurements']).open(encoding='utf-8-sig',newline='') as stream:
                        reader=csv.DictReader(stream);measurement_columns=list(reader.fieldnames);measurement_rows.extend(reader)
            else:
                entry['message']='Voorspelling geweigerd: '+error if state=='failed' else 'Nog geen nieuwe modelvoorspelling beschikbaar.'
            labels.append(entry)
            md.extend([f'### `{label}` — {state}','',f'Prompt: **{preset["text"]}** · kanaal `{preset.get("channels",record["channels"])}`','',entry['message'],''])
            if entry['overlay']:md.extend([f'![Werkelijke voorspelling: {label}]({entry["overlay"]})','',f'[Download uint32-labels en tijdindexen]({entry["download"]})',''])
        csv_file=None
        if measurement_columns:
            csv_file=f'downloads/{name}-measurements.csv'
            with (destination/csv_file).open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=measurement_columns);writer.writeheader();writer.writerows(measurement_rows)
        urls=source_links(record)
        note=record.get('note','')
        selection=record.get('selection',{})
        details={k:selection[k] for k in ['source_level','source_level0_size_xy','roi_xywh','roi_start_zyx','roi_stop_zyx_exclusive','selected_z_index_in_roi','source_time_indices','operation'] if k in selection}
        if record.get('source_time_index') is not None:details['source_time_index']=record['source_time_index']
        attribution=record.get('attribution') or record.get('source_provenance',{}).get('attribution','')
        item={'name':name,'category':category(record),'kind':record.get('kind','Publiek 2D-voorbeeld'),'shape':list(field.shape),
              'timepoints':field.timepoints,'z_planes':field.z_planes,'input':image_file,'labels':labels,'sources':urls,
              'license':record.get('license','Zie oorspronkelijke bron'),'attribution':attribution,'selection':details,
              'measurements':csv_file,'note':note,'search':name+' '+record.get('kind','')+' '+' '.join(p['text'] for p in presets)}
        public.append(item)
        first=labels[0];complete=sum(l['status']=='complete' for l in labels)
        tags=f'<span class="tag">{field.timepoints} T · {field.z_planes} Z</span><span class="tag">{record.get("stored_bytes",0)/1e6:.1f} MB</span><span class="tag {"success" if complete==len(labels) else "failed"}">{complete}/{len(labels)} labels voltooid</span>'
        status_names={'complete':'berekend','partial':'gedeeltelijk','failed':'geweigerd','pending':'nog niet berekend'}
        options=''.join(f'<option value="{i}">{E(l["name"])} · {status_names[l["status"]]}</option>' for i,l in enumerate(labels))
        sources=''.join(f'<li><a href="{E(url,quote=True)}">{E(url)}</a></li>' for url in urls) or '<li>Gekopieerd uit de lokale PublicData-collectie; oorspronkelijke URL niet vastgesteld.</li>'
        csv_link=f'<a href="{csv_file}" download>Metingen CSV ↓</a>' if csv_file else ''
        cards.append(f'''<article class="sample" id="{E(name)}" data-name="{E(name)}"><div class="sample-top"><h2>{E(name)}</h2><div class="sample-kind">{E(item['kind'])}</div><div class="tags">{tags}</div></div><div class="comparison"><figure><a href="{image_file}" target="_blank" rel="noopener"><img loading="lazy" src="{image_file}" alt="Bronweergave {E(name)}"></a><figcaption>TIJDPUNT 0 · {'MAX Z-PROJECTIE' if field.z_planes>1 else '2D-BRONBEELD'}</figcaption></figure><figure data-prediction></figure></div><div class="sample-body"><label class="fine" for="label-{E(name)}">Segmentatielabel</label><select id="label-{E(name)}" data-label>{options}</select><p class="prompt" data-prompt></p><div class="status" data-status></div><div class="downloads"><a data-mask-download download hidden>Labelbestand NPZ ↓</a>{csv_link}</div><details class="metadata"><summary>Herkomst, selectie en gebruikte kanalen</summary><p><code>{E(str(field.shape))}</code> TCZYX</p><ul>{sources}</ul><p>{E(attribution)}</p><p>{E(item['license'])}</p><p>{E(note)}</p><pre>{E(json.dumps(details,indent=2))}</pre></details></div></article>''')
        md.extend(['**Herkomst:**','']+[f'- {url}' for url in urls]+(['- Lokale PublicData-collectie; oorspronkelijke URL niet vastgesteld.'] if not urls else [])+['',f'**Attributie/licentie:** {attribution} · {item["license"]}','',note,''])
    counts={state:sum(l['status']==state for s in public for l in s['labels']) for state in ['complete','partial','failed','pending']}
    catalog={'model':'WeVisOne-VL-4B','projection':'Max','date':'2026-10-25','summary':counts,'examples':public}
    write_json(destination/'assets/examples.json',catalog)
    (destination/'examples.md').write_text('\n'.join(md).rstrip()+'\n',encoding='utf-8')
    categories=''.join(f'<option>{E(c)}</option>' for c in sorted({s['category'] for s in public}))
    data_json=json.dumps(catalog,ensure_ascii=False).replace('</','<\\/')
    intro=f'''<section class="page-head"><div class="eyebrow">Publieke beelden · werkelijke modeluitvoer</div><h1>Biologie in beeld.<br><em>Maskers om te beoordelen.</em></h1><p>27 voorbeelden met structuren van hele coupes tot ultrastructuur. Kies een label om de echte voorspelling, prompt en herkomst te bekijken.</p></section><div class="callout warning"><strong>Een berekend masker is nog geen biologische validatie.</strong> {counts['complete']} labelruns zijn voltooid, {counts['partial']} gedeeltelijk en {counts['failed']} geweigerd. {counts['pending']} zijn nog niet berekend. Roze toont modelvoorspellingen, geen handmatige annotaties. Bij tijdreeksen toont de kaart het eerste berekende tijdpunt; downloads bevatten alle beschikbare tijdpunten.</div><div class="toolbar"><label class="skip" for="search">Zoek voorbeeld of structuur</label><input id="search" type="search" data-search placeholder="Zoek op beeldnaam of Engelse prompt…"><select aria-label="Beeldcategorie" data-category><option value="">Alle categorieën</option>{categories}</select><select aria-label="Resultaatstatus" data-status-filter><option value="">Alle resultaten</option><option value="complete">Voltooid</option><option value="partial">Gedeeltelijk</option><option value="failed">Geweigerd</option><option value="pending">Nog niet berekend</option></select><span class="result-count" data-count></span></div><div class="gallery">{''.join(cards)}</div><script type="application/json" id="gallery-data">{data_json}</script>'''
    (destination/'examples.html').write_text(page('Voorbeeldgalerij',intro,'examples'),encoding='utf-8')
    build_home(destination,counts)
    for stem,title in [('workflow','Workflow & gebruik'),('research','Validatie & beperkingen')]:
        source=destination/(stem+'.md')
        content=markdown.markdown(source.read_text(encoding='utf-8'),extensions=['fenced_code','tables','toc'])
        body=f'<header class="page-head"><div class="eyebrow">Documentatie · versie 0.1.0</div><h1>{E(title)}</h1></header><article class="prose">{content}</article>'
        (destination/(stem+'.html')).write_text(page(title,body,stem),encoding='utf-8')
    (destination/'.nojekyll').write_text('')
    print(json.dumps({'examples':len(public),'labels':counts,'site':str(destination)}),flush=True)


def build_home(destination,counts):
    body=f'''<section class="hero"><div><div class="eyebrow">OME-Zarr · Bilayers · BIOMERO</div><h1>Van tekst naar<br><em>biologische</em><br>structuren.</h1><p>Beschrijf wat je zoekt. CISegWeVisOneVL maakt pixelmaskers met maximaal vier onafhankelijke prompts — voor EM-organellen, weefsel, vaten en meer.</p><div class="actions"><a class="button primary" href="examples.html">Bekijk echte voorbeelden ↗</a><a class="button" href="workflow.html#lokaal-starten">Lokaal starten</a></div><p class="fine">WeVisOne-VL-4B · bestaande foundation-modelgewichten · onderzoekstoepassing</p></div><div class="hero-visual"><div class="image-mosaic"><img src="gallery/public-em-liver-2d-input.webp" alt="FIB-SEM met mitochondriën in leverweefsel"><img src="gallery/public-skin-input.webp" alt="Histologische huidlagen"><img src="gallery/public-lily-stem-input.webp" alt="Vaatbundels in een plantstengel"></div><div class="visual-caption"><span>ANDERE STRUCTUREN. ÉÉN WORKFLOW.</span><span>27 BEELDEN</span></div></div></section>
<div class="stats"><div><strong>4</strong><span>onafhankelijke prompts per beeld</span></div><div><strong>2D + 3D</strong><span>automatische projectie per tijdpunt</span></div><div><strong>1 CSV</strong><span>shape en intensiteit van elk kanaal</span></div><div><strong>27</strong><span>publieke voorbeelden met echte resultaten</span></div></div>
<section class="section"><div class="section-head"><div><div class="eyebrow">Van invoer tot resultaat</div><h2>Een kleine, gerichte<br>segmentatieworkflow.</h2></div><p>Gewone beelden, tijdreeksen en HCS-screens volgen dezelfde route. De bronstore blijft intact; resultaten krijgen een eigen OME-Zarr-store en meetbestand.</p></div><div class="steps"><div class="step"><span class="number">01 / INVOER</span><h3>Open OME-Zarr</h3><p>NGFF 0.4 / Zarr v2. Alle velden worden vooraf gecontroleerd. Kanalen zijn één-gebaseerd.</p></div><div class="step"><span class="number">02 / PROJECTIE</span><h3>Max of Mean</h3><p>Bij Z &gt; 1 wordt iedere stack per kanaal en tijdpunt naar 2D geprojecteerd. Max is standaard; Mean schrijft float32.</p></div><div class="step"><span class="number">03 / INFERENTIE</span><h3>Beschrijf de structuur</h3><p>Kies tot vier labels, Engelse prompts en kanaalmapping. Eén 4B-model wordt lokaal geladen en gebruikt de offline modelcache.</p></div><div class="step"><span class="number">04 / UITVOER</span><h3>Beoordeel & meet</h3><p>Onafhankelijke uint32-labelgroepen, overlays, herkomst en één CSV met alle beeldkanalen. Labels mogen elkaar overlappen.</p></div></div></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">Open resultaten</div><h2>Bekijk wat het model<br>daadwerkelijk doet.</h2></div><p>De galerij bevat zowel bruikbare maskers als fouten. {counts['complete']} labelruns zijn voltooid; geweigerde of gedeeltelijke uitvoer staat apart vermeld. Geen voorspelling is als handmatige waarheid gepresenteerd.</p></div><div class="feature-links"><a class="feature-card" href="examples.html"><small>01 / Galerij</small><h3>Beelden, labels & herkomst ↗</h3><p>EM, histologie, plantstructuren, neurieten en meer. Filter op categorie en bekijk elk label afzonderlijk.</p></a><a class="feature-card" href="workflow.html"><small>02 / Gebruik</small><h3>Van launcher tot CLI ↗</h3><p>Installatie, projecties, kanaalkeuze, parameters, labelbetekenis en de compacte CSV.</p></a><a class="feature-card" href="research.html"><small>03 / Evidence</small><h3>Validatie & beperkingen ↗</h3><p>31 tests, echte GPU-runs, readercontroles en de grenzen van een algemeen VLM voor microscopie.</p></a></div></section>
<section class="section split"><div><div class="eyebrow">Aan de slag</div><h2>Lokaal beginnen.</h2><p>De Windows-launcher en de headless wrapper gebruiken dezelfde parameters. Modelgewichten en invoerdata blijven buiten Git.</p><a class="button" href="{REPO}">Code op GitHub ↗</a></div><div><pre><code>git clone {REPO}.git\ncd ciseg-wevisonevl\ncreate_env.cmd\n.venv\\Scripts\\python tools\\download_models.py\nlaunch.cmd</code></pre><p class="fine">Python 3.12 via uv · NVIDIA GPU getest op RTX A5000 24 GB. De Docker-recepten zijn voorbereid; een BIOMERO/Slurm-deploy is nog niet uitgevoerd.</p></div></section>'''
    (destination/'index.html').write_text(page('Biologische segmentatie met tekst',body,'home'),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs')
    parser.add_argument('--inference',type=Path,default=ROOT/'test-results/published-gallery')
    args=parser.parse_args();export_site(args.output,args.inference)
