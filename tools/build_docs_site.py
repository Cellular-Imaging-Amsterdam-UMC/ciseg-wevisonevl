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
    nav=''.join(f'<a href="{url}"'+(' aria-current="page"' if current==name else '')+f'>{label}</a>' for name,url,label in [('home','index.html','Overview'),('workflow','workflow.html','Workflow'),('examples','examples.html','Examples'),('tiling','tiling.html','Large images'),('research','research.html','Validation')])
    return f'''<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="CISegWeVisOneVL: text-prompted biological segmentation for OME-Zarr, automatic 3D projection and actual public example results."><title>{E(title)} · CISegWeVisOneVL</title><script src="assets/theme.js"></script><link rel="stylesheet" href="assets/style.css"><link rel="stylesheet" href="assets/themes.css"><script src="assets/site.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a><header class="topbar"><div class="shell nav"><a class="brand" href="index.html">{icon} CISegWeVisOneVL</a><nav class="navlinks" aria-label="Main navigation">{nav}<button type="button" class="theme-toggle" data-theme-toggle aria-label="Theme: Dark. Switch to Bright" aria-pressed="true"><span class="theme-bright">Bright</span><span class="theme-dark">Dark</span></button><a class="repo" href="{REPO}">GitHub ↗</a></nav></div></header><main class="shell" id="main">{body}</main><footer class="footer"><div class="shell footer-row"><span>Cellular Imaging · Amsterdam UMC</span><span>WeVisOne-VL-4B · Version 0.1.0 · Results from 25 October 2026</span><a href="{REPO}/blob/main/NOTICE.md">Sources & licenses</a></div></footer></body></html>'''


def source_links(record):
    candidates=[record.get('source'),record.get('original_url')]
    for key in ['source_provenance','selection']:
        obj=record.get(key,{})
        candidates.extend(obj.get(k) for k in ['source_url','reference','source'])
    if record['name']=='local-CMU1-whole-section':candidates.append('https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/')
    if record['name']=='local-REAL-LYSOSOME':candidates.append('https://zenodo.org/records/14043236')
    if 'em-mitolab' in record['name']:candidates.append('https://doi.org/10.1016/j.cels.2022.12.006')
    return list(dict.fromkeys(c for c in candidates if isinstance(c,str) and c.startswith(('https://','http://'))))


def category(record):
    name=record['name'];kind=record.get('kind','').lower()
    if '-em-' in name:return 'EM'
    if any(x in name for x in ['skin','adipose','section','ki67','immunohistochemistry']):return 'Histology & tissue'
    if any(x in name for x in ['neur','dendrit','brain','retina']):return 'Neurites & vessels'
    if any(x in name for x in ['lily','diatoms','embryos']):return 'Other structures'
    return 'Cells & organoids'


def imaging_mode(record):
    if record.get('imaging_mode'):return record['imaging_mode']
    name=record['name'];kind=record.get('kind','').lower()
    if '-em-' in name:return 'EM'
    if 'ki67' in name or 'immunohistochemistry' in name:return 'Immunohistochemistry'
    if any(part in name for part in ['dendrit','drosophila','brain','lily','neurofilament']):return 'Fluorescence'
    if any(part in name for part in ['skin','CMU1']):return 'Histology (H&E)'
    return 'Transmitted / other light microscopy'


def public_error(message):
    return re.sub(r'[A-Za-z]:[\\/][^\n]+','<local file location>',message or '')


def export_site(destination,inference):
    destination.mkdir(parents=True,exist_ok=True)
    asset=destination/'gallery';asset.mkdir(exist_ok=True)
    downloads=destination/'downloads';downloads.mkdir(exist_ok=True)
    records=json.loads((ROOT/'publicdata/catalog.json').read_text(encoding='utf-8-sig'))
    selection_path=ROOT/'gallery_selection.json'
    selection_config=json.loads(selection_path.read_text()) if selection_path.exists() else None
    curated=bool(selection_config and selection_config.get('curated'))
    if curated:
        by_name={r['name']:r for r in records}
        records=[by_name[s['name']] for s in selection_config['examples']]
    manifest=json.loads((inference/'manifest.json').read_text())
    public=[];cards=[];md=['# Curated public examples and actual segmentation results' if curated else '# Public examples and actual segmentation results','',
        'All examples use WeVisOne-VL-4B. Images show timepoint 0; Z stacks use Max projection. Label files include all successfully computed timepoints. Rejected predictions are not empty background masks.','',
        '[Interactive HTML gallery](examples.html) · [Workflow](workflow.md) · [Sources and validation](research.md)','']
    if curated:md.extend(['This is a positively selected demonstration gallery after prompt comparisons and visual inspection, not a representative accuracy benchmark. Unselected experiments remain in the research records. EM examples are native 2D sections, without Z projections.',''])
    for record in records:
        name=record['name'];source=ROOT/'publicdata/ome-zarr'/(name+'.ome.zarr');field=inspect_store(source,[])[0]
        channels=tuple(map(int,record['channels'].split(',')))
        image,_=render_rgb(field.pixels(channels,0,'Max'),channels,record['normalization'])
        image.thumbnail((720,520),Image.Resampling.LANCZOS)
        image_file=f'gallery/{name}-input.webp';image.save(destination/image_file,quality=90)
        presets=record.get('prompt_presets') or [{'name':record.get('label_name','nuclei' if name=='human_mitosis' else 'glands' if name=='immunohistochemistry' else 'organoids' if name.startswith('organoids') else 'cell'),
                                                 'text':record['suggested_query'],'channels':record['channels']}]
        results=manifest['examples'].get(name,{}).get('labels',{})
        if curated:
            chosen=next(s for s in selection_config['examples'] if s['name']==name)
            presets=[p for p in presets if p['name'] in chosen['labels']]
            if category(record)=='EM' and field.z_planes>1:raise ValueError('EM projection cannot enter curated gallery: '+name)
            if not presets:raise ValueError('Selected example has no selected prompt: '+name)
        labels=[];measurement_rows=[];measurement_columns=[]
        md.extend([f'## {name}','',f'![Source image: {name}]({image_file})','',f'**Shape:** `{field.shape}` (TCZYX) · **type:** {category(record)} · **storage:** {record.get("stored_bytes",0)/1e6:.2f} MB',''])
        for preset in presets:
            label=preset['name'];result=results.get(label,{})
            frames=result.get('frames',[]);available=[int(f['time_index']) for f in frames]
            state=result.get('status','pending')
            if curated and state!='complete':raise ValueError('Curated label must have a completed real result: '+name+'/'+label)
            if state=='failed' and available:state='partial'
            entry={'name':label,'text':preset['text'],'channels':list(map(int,preset.get('channels',record['channels']).split(','))),
                   'status':state,'overlay':None,'download':None,'timepoints_available':available}
            error=public_error(result.get('error',''))
            if state in ['complete','partial'] and available:
                store=inference/result.get('output',result.get('partial_output'))
                root=zarr.open_group(str(store),mode='r');array=root[f'labels/wevisone_{label}/0']
                masks=np.asarray(array.oindex[available,:,:,:,:])
                count=int(frames[0]['retained_instances'])
                if curated and count==0:raise ValueError('Curated example has an empty result: '+name+'/'+label)
                mask=np.asarray(Image.fromarray((masks[0,0,0]>0).astype(np.uint8)).resize(image.size,Image.Resampling.NEAREST))>0
                overlay=np.asarray(image).copy();overlay[mask]=(.55*overlay[mask]+.45*np.array([255,50,160])).astype(np.uint8)
                overlay_file=f'gallery/{name}-{label}-overlay.webp';Image.fromarray(overlay).save(destination/overlay_file,quality=92)
                label_file=f'downloads/{name}-{label}-labels.npz'
                np.savez_compressed(destination/label_file,labels=masks.astype(np.uint32),time_indices=np.array(available,dtype=np.int32),axes=np.array('tczyx'))
                entry.update(overlay=overlay_file,download=label_file,first_frame_objects=count,
                             message=f'Timepoint {available[0]}: {count} predicted objects. {len(available)}/{field.timepoints} timepoints completed.'+(' Later timepoints rejected: '+error if state=='partial' else ''))
                coverage=float(frames[0].get('foreground_fraction',np.count_nonzero(masks[0,0,0])/masks[0,0,0].size))
                entry['foreground_fraction']=coverage
                entry['message']+=f' Mask coverage: {coverage:.1%}.'
                if frames[0].get('review_note'):entry['message']+=' High coverage: inspect foreground and background in the overlay.'
                if count==0:entry['message']+=' The model returned an empty mask; this is not evidence that the structure is absent.'
                reference=source.parent/(name+'_reference.npy')
                if reference.exists() and state=='complete':
                    truth=np.load(reference,allow_pickle=False)>0;prediction=masks[0,0,0]>0
                    intersection=int((truth&prediction).sum());denominator=int(truth.sum())+int(prediction.sum())
                    entry['foreground_dice']=2*intersection/denominator if denominator else 1.
                    entry['message']+=f' Foreground Dice: {entry["foreground_dice"]:.3f} against consensus (not an instance score).'
                if result.get('measurements'):
                    with (inference/result['measurements']).open(encoding='utf-8-sig',newline='') as stream:
                        reader=csv.DictReader(stream);measurement_columns=list(reader.fieldnames);measurement_rows.extend(reader)
            else:
                entry['message']='Prediction rejected: '+error if state=='failed' else 'No new model prediction is available yet.'
            labels.append(entry)
            md.extend([f'### `{label}` — {state}','',f'Prompt: **{preset["text"]}** · channels `{preset.get("channels",record["channels"])}`','',entry['message'],''])
            if entry['overlay']:md.extend([f'![Actual prediction: {label}]({entry["overlay"]})','',f'[Download uint32 labels and time indices]({entry["download"]})',''])
        csv_file=None
        if measurement_columns:
            csv_file=f'downloads/{name}-measurements.csv'
            with (destination/csv_file).open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=measurement_columns);writer.writeheader();writer.writerows(measurement_rows)
        reference_assets=None
        reference_path=source.parent/(name+'_reference.npy')
        if reference_path.exists():
            reference=np.load(reference_path,allow_pickle=False)
            ref_mask=np.asarray(Image.fromarray((reference>0).astype(np.uint8)).resize(image.size,Image.Resampling.NEAREST))>0
            preview=np.asarray(image).copy();preview[ref_mask]=(.55*preview[ref_mask]+.45*np.array([0,210,225])).astype(np.uint8)
            reference_assets={'overlay':f'gallery/{name}-reference.webp','download':f'downloads/{name}-reference.npz'}
            Image.fromarray(preview).save(destination/reference_assets['overlay'],quality=92)
            np.savez_compressed(destination/reference_assets['download'],labels=reference[None,None,None].astype(np.uint32),time_indices=np.array([0],np.int32),axes=np.array('tczyx'))
        urls=source_links(record)
        note=record.get('note') or record.get('source_provenance',{}).get('note','')
        selection=record.get('selection',{})
        details={k:selection[k] for k in ['source_level','source_level0_size_xy','roi_xywh','roi_yxhw','roi_start_zyx','roi_stop_zyx_exclusive','selected_z_index_in_roi','source_time_indices','source_example','source_z_planes','source_study','roi_yxhw_relative_to_parent','image_member','mask_member','archive','operation','source_panel','source_z_index','source_shape','source_notes','channel_mapping','calibration'] if k in selection}
        if record.get('source_time_index') is not None:details['source_time_index']=record['source_time_index']
        attribution=record.get('attribution') or record.get('source_provenance',{}).get('attribution','')
        item={'name':name,'category':category(record),'imaging_mode':imaging_mode(record),'kind':record.get('kind','Public 2D example'),'shape':list(field.shape),
              'timepoints':field.timepoints,'z_planes':field.z_planes,'input':image_file,'labels':labels,'sources':urls,
              'license':record.get('license','See original source'),'attribution':attribution,'selection':details,
              'measurements':csv_file,'reference':reference_assets,'note':note,'review':record.get('review',''),'search':name+' '+record.get('kind','')+' '+' '.join(p['text'] for p in presets)}
        public.append(item)
        first=labels[0];complete=sum(l['status']=='complete' for l in labels)
        tags=f'<span class="tag">{field.timepoints} T · {field.z_planes} Z</span><span class="tag">{record.get("stored_bytes",0)/1e6:.1f} MB</span><span class="tag {"success" if complete==len(labels) else "failed"}">{complete}/{len(labels)} labels completed</span>'
        status_names={'complete':'computed','partial':'partial','failed':'rejected','pending':'not yet computed'}
        options=''.join(f'<option value="{i}">{E(l["name"])} · {status_names[l["status"]]}</option>' for i,l in enumerate(labels))
        sources=''.join(f'<li><a href="{E(url,quote=True)}">{E(url)}</a></li>' for url in urls) or '<li>Copied from the local PublicData collection; original URL not established.</li>'
        csv_link=f'<a href="{csv_file}" download>Measurements CSV ↓</a>' if csv_file else ''
        if reference_assets:csv_link+=f'<a href="{reference_assets["overlay"]}" target="_blank" rel="noopener">Dataset reference (cyan) ↗</a><a href="{reference_assets["download"]}" download>Reference labels ↓</a>'
        cards.append(f'''<article class="sample" id="{E(name)}" data-name="{E(name)}"><div class="sample-top"><h2>{E(name)}</h2><div class="sample-kind">{E(item['kind'])}</div><div class="tags">{tags}</div></div><div class="comparison"><figure><a href="{image_file}" target="_blank" rel="noopener"><img loading="lazy" src="{image_file}" alt="Source view {E(name)}"></a><figcaption>TIMEPOINT 0 · {'MAX Z-PROJECTION' if field.z_planes>1 else '2D SOURCE VIEW'}</figcaption></figure><figure data-prediction></figure></div><div class="sample-body"><label class="fine" for="label-{E(name)}">Segmentation label</label><select id="label-{E(name)}" data-label>{options}</select><p class="prompt" data-prompt></p><div class="status" data-status></div><div class="downloads"><a data-mask-download download hidden>Label file NPZ ↓</a>{csv_link}</div><details class="metadata"><summary>Sources, selection and channel mapping</summary><p><code>{E(str(field.shape))}</code> TCZYX</p><ul>{sources}</ul><p>{E(attribution)}</p><p>{E(item['license'])}</p><p>{E(note)}</p><p>{E(item['review'])}</p><pre>{E(json.dumps(details,indent=2))}</pre></details></div></article>''')
        md.extend(['**Selection review:** '+item['review'],'','**Sources:**','']+[f'- {url}' for url in urls]+(['- Local PublicData collection; original URL not established.'] if not urls else [])+['',f'**Attribution/license:** {attribution} · {item["license"]}','',note,''])
        if reference_assets:md.extend([f'[Independent dataset reference, cyan]({reference_assets["overlay"]}) · [Reference label file]({reference_assets["download"]})',''])
    counts={state:sum(l['status']==state for s in public for l in s['labels']) for state in ['complete','partial','failed','pending']}
    catalog={'model':'WeVisOne-VL-4B','projection':'Max','date':'2026-10-25','curated':curated,'summary':counts,'examples':public}
    write_json(destination/'assets/examples.json',catalog)
    (destination/'examples.md').write_text('\n'.join(md).rstrip()+'\n',encoding='utf-8')
    categories=''.join(f'<option>{E(c)}</option>' for c in sorted({s['category'] for s in public}))
    data_json=json.dumps(catalog,ensure_ascii=False).replace('</','<\\/')
    intro=f'''<section class="page-head"><div class="eyebrow">Public images · actual model output</div><h1>Biology in focus.<br><em>Masks to inspect.</em></h1><p>27 examples from whole tissue sections to ultrastructure. Select a label to inspect the actual prediction, prompt and source.</p></section><div class="callout warning"><strong>A computed mask is not biological validation.</strong> {counts['complete']} label runs completed, {counts['partial']} are partial and {counts['failed']} were rejected. {counts['pending']} remain uncomputed. Pink shows model predictions, not manual annotations. Time-series cards show the first computed frame; downloads contain all available frames.</div><div class="toolbar"><label class="skip" for="search">Search examples or structures</label><input id="search" type="search" data-search placeholder="Search by image name or English prompt…"><select aria-label="Image category" data-category><option value="">All categories</option>{categories}</select><select aria-label="Result status" data-status-filter><option value="">All results</option><option value="complete">Computed</option><option value="partial">Partial</option><option value="failed">Rejected</option><option value="pending">Not yet computed</option></select><span class="result-count" data-count></span></div><div class="gallery">{''.join(cards)}</div><script type="application/json" id="gallery-data">{data_json}</script>'''
    (destination/'examples.html').write_text(page('Example gallery',intro,'examples'),encoding='utf-8')
    if curated:
        intro=intro.replace('27 examples from whole tissue sections to ultrastructure.',f'{len(public)} selected demonstrations, from whole tissue sections to ultrastructure.')
        start=intro.index('<div class="callout warning">');end=intro.index('<div class="toolbar">',start)
        intro=intro[:start]+'<div class="callout warning"><strong>Curated demonstrations, not an accuracy benchmark.</strong> These results were selected after prompt comparisons and visual inspection. Empty, invalid and unconvincing candidates are excluded from this gallery and documented in the research report. EM images are native 2D sections, never Z projections. Cards show timepoint 0; label downloads retain every computed timepoint.</div>'+intro[end:]
        (destination/'examples.html').write_text(page('Curated example gallery',intro,'examples'),encoding='utf-8')
    modes=''.join(f'<option>{E(mode)}</option>' for mode in sorted({s['imaging_mode'] for s in public}))
    mode_filter=f'<select aria-label="Imaging mode" data-imaging-mode><option value="">All imaging modes</option>{modes}</select>'
    intro=intro.replace('<select aria-label="Image category"',mode_filter+'<select aria-label="Image category"')
    intro=intro.replace('<div class="toolbar">','<p><a href="imaging-modes.html">Whole structures and their parts: modality comparisons and sources ↗</a></p><div class="toolbar">')
    (destination/'examples.html').write_text(page('Curated example gallery' if curated else 'Example gallery',intro,'examples'),encoding='utf-8')
    build_home(destination,counts,len(public),curated)
    for stem,title in [('workflow','Workflow & usage'),('tiling','Large images & object fusion'),('prompt-study','Prompt comparison & selection'),('imaging-modes','Whole structures and their parts'),('research','Validation & limitations')]:
        source=destination/(stem+'.md')
        markdown_text=source.read_text(encoding='utf-8')
        if markdown_text.startswith('# '):markdown_text=markdown_text.split('\n',1)[1]
        content=markdown.markdown(markdown_text,extensions=['fenced_code','tables','toc'])
        body=f'<header class="page-head"><div class="eyebrow">Documentation · version 0.1.0</div><h1>{E(title)}</h1></header><article class="prose">{content}</article>'
        (destination/(stem+'.html')).write_text(page(title,body,stem),encoding='utf-8')
    (destination/'.nojekyll').write_text('')
    print(json.dumps({'examples':len(public),'labels':counts,'site':str(destination)}),flush=True)


def build_home(destination,counts,example_count=27,curated=False):
    body=f'''<section class="hero"><div><div class="eyebrow">OME-Zarr · Bilayers · BIOMERO</div><h1>From words to<br><em>biological</em><br>structures.</h1><p>Describe what you need. CISegWeVisOneVL creates pixel masks with up to four independent prompts — for EM organelles, tissue, vessels and more.</p><div class="actions"><a class="button primary" href="examples.html">Explore actual results ↗</a><a class="button" href="workflow.html#getting-started">Get started locally</a></div><p class="fine">WeVisOne-VL-4B · existing foundation-model weights · research workflow</p></div><div class="hero-visual"><div class="image-mosaic"><img src="gallery/public-em-liver-2d-input.webp" alt="FIB-SEM showing mitochondria in liver tissue"><img src="gallery/public-skin-input.webp" alt="Histological skin layers"><img src="gallery/public-lily-stem-input.webp" alt="Vascular bundles in a plant stem"></div><div class="visual-caption"><span>DIFFERENT STRUCTURES. ONE WORKFLOW.</span><span>27 IMAGES</span></div></div></section>
<div class="stats"><div><strong>4</strong><span>independent prompts per image</span></div><div><strong>2D + 3D</strong><span>automatic projection per timepoint</span></div><div><strong>1 CSV</strong><span>shape and intensity for every channel</span></div><div><strong>27</strong><span>public examples with actual predictions</span></div></div>
<section class="section"><div class="section-head"><div><div class="eyebrow">From input to result</div><h2>A small, focused<br>segmentation workflow.</h2></div><p>Regular images, time series and HCS screens follow the same route. Source stores remain intact; results receive a separate OME-Zarr store and measurement table.</p></div><div class="steps"><div class="step"><span class="number">01 / INPUT</span><h3>Open OME-Zarr</h3><p>NGFF 0.4 / Zarr v2. Every field is checked before inference. Channel numbers are one-based.</p></div><div class="step"><span class="number">02 / PROJECTION</span><h3>Max or Mean</h3><p>For Z &gt; 1, each channel and timepoint is projected to 2D. Max is the default; Mean writes float32.</p></div><div class="step"><span class="number">03 / INFERENCE</span><h3>Describe the structure</h3><p>Select up to four labels, English descriptions and channel mappings. One 4B model uses the offline local cache.</p></div><div class="step"><span class="number">04 / OUTPUT</span><h3>Inspect and measure</h3><p>Independent uint32 labels, overlays, provenance and one CSV covering every channel. Prompt labels may overlap.</p></div></div></section>
<section class="section"><div class="section-head"><div><div class="eyebrow">Open results</div><h2>See what the model<br>actually predicts.</h2></div><p>The gallery includes useful masks and failures. {counts['complete']} label runs completed; rejected or partial outputs are marked separately. Predictions are never presented as manual ground truth.</p></div><div class="feature-links"><a class="feature-card" href="examples.html"><small>01 / Gallery</small><h3>Images, labels and sources ↗</h3><p>EM, histology, plant structures, neurites and more. Filter by category and inspect each label.</p></a><a class="feature-card" href="workflow.html"><small>02 / Usage</small><h3>From launcher to CLI ↗</h3><p>Setup, projections, channels, parameters, output semantics and compact CSV measurements.</p></a><a class="feature-card" href="research.html"><small>03 / Evidence</small><h3>Validation and limitations ↗</h3><p>39 tests, actual GPU runs, reader checks and the limitations of a general VLM for microscopy.</p></a></div></section>
<section class="section split"><div><div class="eyebrow">Getting started</div><h2>Begin locally.</h2><p>The Windows launcher and headless wrapper use the same parameters. Models and full input stores stay outside Git.</p><a class="button" href="{REPO}">Code on GitHub ↗</a></div><div><pre><code>git clone {REPO}.git\ncd ciseg-wevisonevl\ncreate_env.cmd\n.venv\\Scripts\\python tools\\download_models.py\nlaunch.cmd</code></pre><p class="fine">Python 3.12 via uv · tested on RTX A5000 24 GB. Docker recipes are prepared; a BIOMERO/Slurm deployment has not been performed.</p></div></section>'''
    if curated:
        body=body.replace('27 IMAGES',f'{example_count} SELECTED IMAGES').replace('<strong>27</strong>',f'<strong>{example_count}</strong>')
        body=body.replace('public examples with actual predictions','curated examples with actual predictions')
        body=body.replace('The gallery includes useful masks and failures.', 'The gallery highlights reviewed demonstrations selected after explicit prompt comparisons.')
        body=body.replace('rejected or partial outputs are marked separately.', 'unselected and failed experiments are retained in the research report.')
        body=body.replace('gallery/public-em-liver-2d-input.webp','gallery/public-em-mitolab-folded-mitochondria-input.webp')
        body=body.replace('FIB-SEM showing mitochondria in liver tissue','Native 2D EM mitochondria with visible internal folds')
        body=body.replace('gallery/public-skin-input.webp','gallery/public-ki67-brown-nuclei-detail-input.webp').replace('Histological skin layers','Native Ki67 detail with brown positive nuclei')
    (destination/'index.html').write_text(page('Text-prompted biological segmentation',body,'home'),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs')
    parser.add_argument('--inference',type=Path)
    args=parser.parse_args()
    selection_path=ROOT/'gallery_selection.json'
    selected=json.loads(selection_path.read_text()) if selection_path.exists() else {}
    inference=args.inference or ROOT/selected.get('inference_directory','test-results/published-gallery')
    export_site(args.output,inference)
