# CISegWeVisOneVL

[Website en workflowuitleg](https://cellular-imaging-amsterdam-umc.github.io/ciseg-wevisonevl/) ·
[Publieke beelden met echte segmentaties](https://cellular-imaging-amsterdam-umc.github.io/ciseg-wevisonevl/examples.html) ·
[Voorbeeldgalerij als Markdown](docs/examples.md)

Lokale microscopiesegmentatie met maximaal **vier onafhankelijke tekstprompts**,
op basis van Tencent WeVisOne-VL-4B. **3D-beelden worden automatisch per kanaal en
tijdpunt naar 2D geprojecteerd: Max is standaard; Mean is een geavanceerde
Bilayers-optie.** Gewone beelden, tijdreeksen en HCS-screens worden ondersteund.
De bronstore blijft intact. De uitvoer bevat de 2D-beelden of projecties met
een native labelgroep per actieve prompt. Dezelfde parameters staan in de
Bilayers-configuratie en de Windows-launcher.

Dit is een inferentieworkflow met bestaande foundation-modelgewichten. Er is
geen nieuw microscopiemodel getraind. De biologische kwaliteit verschilt sterk
per beeld en prompt; zie [onderzoek en resultaten](docs/research.md).

## Direct lokaal testen

De omgeving en het 4B-model zijn op deze werkplek al klaargezet. Dubbelklik
op **`launch.cmd`**. Kies bovenin een publiek voorbeeld,
gebruik **Check input**, en start **Run local Python**. Een leeg promptveld
schakelt die stap uit. Begin met `cell` of `organoids_im10`.
De workflow gebruikt uitsluitend WeVisOne-VL-4B; er is geen modelkeuzemenu.

Elke stap heeft een Engelse objectbeschrijving, een unieke labelnaam en een
kanaalkeuze. `1` gebruikt één kanaal als grijswaarde-RGB; `1,2,3` betekent
respectievelijk rood, groen, blauw. Verschillende stappen kunnen verschillende
kanalen gebruiken. Voor RGB-histologie kies je **Original uint8 RGB**; voor
fluorescentie is percentielcontrast doorgaans het geschikte startpunt.

Commandoregelvoorbeeld, vanaf deze map:

```powershell
.venv\Scripts\python.exe wrapper.py `
  --infolder publicdata\ome-zarr\human_mitosis.ome.zarr `
  --outfolder outputfolder\nuclei-test `
  --device cuda:0 `
  --prompt-1 "cell nuclei" --name-1 nuclei --channels-1 1 `
  --prompt-2 "bright round cell nuclei" --name-2 bright_nuclei --channels-2 1
```

Kies bij een herhaling een nieuwe uitvoermap. Bestaande resultaten worden nooit
overschreven. `--preflight-only` controleert alle velden zonder modelinvoer of
schrijven. Bij Z>1 wordt iedere Z-stack afzonderlijk geprojecteerd, voor elk
kanaal en elk tijdpunt. `--projection Max` is standaard; `--projection Mean`
gebruikt het gemiddelde. De tijdas wordt nooit samengevoegd. Bij Z=1 blijven de
bronpixels exact behouden, ook als de projectieoptie op Mean staat.

Max behoudt het oorspronkelijke pixeltype. Mean schrijft float32 om gemiddelde
waarden niet terug te ronden naar integers. Projectie-uitvoer gebruikt de
OMERO-compatibele TCZYX-indeling met Z=1; de Z-as draagt geen fysieke
vlakpositie van het bronvolume. XY-kalibratie, tijdkalibratie en oorsprong
blijven behouden. Bestaande 3D-labels
worden niet geprojecteerd: instance-ID's middelen of maximaliseren is niet
betekenisvol. Ze blijven in de onaangeraakte bronstore beschikbaar.

## Installatie opnieuw uitvoeren

`create_env.cmd` maakt met uv een lokale **Python 3.12**-omgeving in `.venv/`.
De nieuwere SciPy-versie van de upstream-stack vereist 3.12. Het script
installeert CUDA 12.6 / PyTorch 2.11 en de vastgezette Transformers-backend;
vLLM, Triton en Gradio worden niet als aparte workflowafhankelijkheid toegevoegd.
`requirements-lock.windows.txt` legt de gevalideerde Windows-omgeving vast.

```powershell
create_env.cmd
.venv\Scripts\python.exe tools\download_models.py
.venv\Scripts\python.exe tools\prepare_publicdata.py --organoids
.venv\Scripts\python.exe -m pytest -q
```

De vaste snapshot staat onder
`models/WeVisOne-VL-4B` (19,37 GB), inclusief
de vereiste `mask_decoder.pt` en licenties. De downloadmanifesten bewaren
revisies, bestandsgroottes en upstream LFS-hashes. Inferentie gebruikt uitsluitend
lokale bestanden en controleert de inventaris. Een andere locatie kan met
`--models-root` of `CISEGWEVISONEVL_MODELS`.

`.venv/`, modellen, publieke data, testresultaten en uitvoer zijn uitgesloten van
Git. Originele downloads, herkomst en referentiemaskers blijven onder
`publicdata/` bewaard. De organoïdvoorbeelden worden als afzonderlijke ZIP-leden
met HTTP-ranges opgehaald en met CRC32 gecontroleerd; de gehele 1,4-GB-collectie
is daarvoor niet nodig.

## Uitvoer en betekenis

Per bron ontstaat `<bron>__wevisonevl.ome.zarr`, met ongewijzigde 2D-bronpixels
en bronpiramides bij TCZYX-invoer, of bij 3D-invoer een nieuwe 2D-projectiepiramide.
Andere geldige invoer-asvolgordes worden voor OMERO naar TCZYX genormaliseerd,
met behoud van de 2D-pixelwaarden op volledige resolutie. De
HCS-structuur en alle tijdpunten blijven behouden. Onder ieder beeld:

```text
labels/wevisone_<naam>/0         uint32-maskers op oorspronkelijke XY-coördinaten
labels/wevisone_<naam>/1,2,...   labelpiramides met nearest-neighbour reductie
```

Elke prompt is een afzonderlijke klasse. Labels uit verschillende prompts mogen
overlappen, zoals nuclei binnen cellen of cellen binnen een organoïd. Binnen
één prompt wint het masker met de hoogste pixelwaarschijnlijkheid; bij een
gelijke waarde wint het eerst voorspelde object. `--label-mode semantic` geeft
per prompt een binair masker; standaard blijven de voorspelde instance-ID's
behouden. Dit zijn modelinstanties, geen garantie dat iedere cel apart is herkend.

`wevisone-run.json` bevat prompts, kanalen, contrastgrenzen, modelrevisie,
gegenereerde coördinaten, aantallen en looptijden. `wevisone_previews/` bevat
modelinvoer en overlays per tijdpunt. Te grote maskerdekking krijgt een inspectiemelding.
Die melding verwijdert geen voorspellingen. Ongeldige coördinaten of afgebroken
generatie geven een fout; `.partial-*` blijft met diagnostiek bewaard en wordt
niet als voltooid resultaat gepubliceerd.

Zowel gewone beelden als HCS-platen moeten NGFF 0.4 / Zarr v2 zijn. Alle velden
worden vooraf gecontroleerd. Maximaal 16 megapixels per XY-vlak; Z-projecties
worden vlak voor vlak opgebouwd, zonder de hele T/C/Z-stack in het geheugen
te laden. Modelinvoer wordt
expliciet naar maximaal 1024 pixels aan de langste zijde verkleind (instelbaar
128–2048). Maskers worden naar de oorspronkelijke coördinaten teruggebracht.
Deze eerste versie bevat geen automatische tegels met objectfusie. Kleine of
dicht opeengepakte objecten kunnen daardoor worden gemist. Fysieke eenheden
worden behouden als ze bekend zijn en niet verzonnen. Objecttracking en
meetdatabases vallen buiten deze workflow.

## Basis-metingen in één CSV

Elke voltooide run schrijft **`measurements.csv`** direct in de uitvoermap:
één tabel voor alle invoerbeelden, HCS-velden, tijdpunten en promptgroepen.
Een rij beschrijft één label-ID; ID's zijn lokaal per veld, tijdpunt en prompt.
De tabel bevat oppervlakte in pixels, centroid, bounding box (maximum exclusief),
omtrek, equivalente diameter, hoofdas/nevenas, eccentriciteit, soliditeit,
extent en oriëntatie in radialen. `area_um2` wordt alleen ingevuld bij positieve
XY-kalibratie met bekende NGFF-eenheden. Anders blijft de fysieke oppervlakte leeg.

Voor **ieder beeldkanaal**, ook kanalen die niet in de modelinvoer zijn gekozen,
worden min/max/mean/total-intensiteit en het aantal geldige pixels vastgelegd.
Deze waarden gebruiken de oorspronkelijke 2D-pixels of de gemaakte Max/Mean-
projectie, vóór contrastnormalisatie voor het model. NaN/Inf-pixels worden niet
meegeteld; het geldige aantal maakt dit zichtbaar. Lege promptmaskers leveren
geen objectrijen op; een run zonder objecten geeft een CSV met kolomkoppen.
Bij semantic-modus is label 1 de volledige samengevoegde regio per prompt.

De CSV verschijnt pas onder zijn definitieve naam als de hele run slaagt;
een mislukte run bewaart een `measurements.partial-*` voor onderzoek.
De Bilayers-descriptor declareert de CSV als `type: measurement`, `format: csv`,
`file_count: single`, onder `/data/out`. De geïnstalleerde BIOMERO-parser is
hiermee lokaal gecontroleerd. De daadwerkelijke attachment-import in OMERO
wordt tijdens de latere BIOMERO/Docker-test uitgevoerd.

## Uitgebreide publieke voorbeelden

Er staan 27 voorbeelden onder `publicdata/ome-zarr/`, waaronder 22 nieuwe
voorbeelden uit de lokale PublicData-map en publieke bronnen. De nieuwe
selectie omvat kleine Z-stacks, dendrieten/spines, bloedvaten, orgaoïdweefsel,
vetcellen, huidlagen, plantstengelbundels, diatomeeën, embryo's,
coupe-overzichten, Ki67/DAB en 2D/3D FIB-SEM met organellen.
De volledige invoerset is ongeveer 206 MB; originele WSI-bestanden, archieven
en opgehaalde EM-chunks worden apart behouden. De grootste OME-Zarr-invoer is
de al aanwezige orgaoïdcoupe van circa 128 MB.

Kies een voorbeeld in de launcher om de voorgestelde prompts en kanalen te
laden. Deze prompts zijn startpunten, geen gemeten kwaliteitsgarantie.
Bij EM worden naast kleine volumes ook native 2D-doorsneden bewaard, omdat een
Max/Mean-projectie ultrastructuren kan laten overlappen. Volledige coupes worden
op een bestaande lagere piramideresolutie getoond; alle uitsneden en resoluties
staan expliciet in `publicdata/catalog.json`. Lokale kopieën zijn bestand voor
bestand met SHA-256 gecontroleerd, zonder de bron te wijzigen.

De optionele afhankelijkheden voor data-curatie staan in
`requirements_publicdata.txt`. Curatie en export kunnen worden herhaald met
`tools/curate_extra_publicdata.py`, `tools/curate_remote_examples.py` en
`tools/build_data_catalog.py`. De gewone datavoorbereiding behoudt aanvullende
catalogusrecords.

## Bilayers en volgende BIOMERO-fase

De zichtbare naam en `algorithm_folder_name` zijn **CISegWeVisOneVL**. BIOMERO
normaliseert configuratiesleutels intern naar kleine letters; gebruik later
`cisegwevisonevl` als sleutel. De imagenaam blijft conform Docker in kleine
letters: `cellularimagingcf/w_cisegwevisonevl`.

```powershell
.venv\Scripts\python.exe bilayers_cli.py validate
.venv\Scripts\python.exe bilayers_cli.py generate
```

`Dockerfile.models` bereidt dezelfde aparte interne modelcache-image voor als
bij cisegmentation. `Dockerfile` gebruikt die cache voor een headless workflow.
**Geen nieuwe Docker-image is gebouwd of gepubliceerd**, de imageverwijzing in
`config.yaml` is voorbereid, en deze workflow is nog niet in BIOMERO geregistreerd.
Een echte Slurm/BIOMERO-importtest volgt pas in die volgende fase. De bestaande
OMERO/Bio-Formats-reader is wel al met bron- en labelpixels getest.

De basisrepository cisegmentation is bijgewerkt naar v0.6.6. De eerder lokale
tools-commit staat op `main` als `75568fc`; die commit wijzigt alleen vijf
bestanden onder `tools/`.

Zie [NOTICE.md](NOTICE.md) voor bron-, model- en data-attributie.
