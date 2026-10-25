# De workflow

CISegWeVisOneVL segmenteert OME-Zarr-beelden met WeVisOne-VL-4B en maximaal vier
onafhankelijke tekstprompts. Het gebruikt bestaande modelgewichten. De voorbeelden
op deze website laten de daadwerkelijke prestaties en fouten zien.

## Lokaal starten

Installeer Git en [uv](https://docs.astral.sh/uv/getting-started/installation/).
Gebruik vervolgens op Windows:

```powershell
git clone https://github.com/Cellular-Imaging-Amsterdam-UMC/ciseg-wevisonevl.git
cd ciseg-wevisonevl
create_env.cmd
.venv\Scripts\python tools\download_models.py
launch.cmd
```

De omgeving gebruikt Python 3.12, PyTorch 2.11/CUDA 12.6 en Transformers 5.12.1.
De vastgezette 4B-snapshot neemt circa 19,37 GB in beslag en bevat de vereiste
pixeldecoder. Inferentie gebruikt uitsluitend de lokale cache. CPU-uitvoering
is beschikbaar; de GPU-runs zijn uitgevoerd op een RTX A5000 met 24 GB VRAM.

Kies in de launcher een voorbeeld of invoermap. Gebruik **Check input** en daarna
**Run local Python**. Een leeg promptveld schakelt de betreffende stap uit.
Bestaande resultaten worden niet overschreven: gebruik voor elke nieuwe run een
nieuwe uitvoermap.

## Beelden en kanalen

- Invoer: NGFF 0.4 / Zarr v2, met expliciete asmetadata.
- Gewone beelden, tijdreeksen en alle velden van een HCS-screen worden verwerkt.
- `1` geeft één kanaal als grijswaardeweergave aan het model.
- `1,2,3` wijst drie beeldkanalen toe aan rood, groen en blauw.
- Voor uint8-RGB-histologie houdt **Original uint8 RGB** de kleuren intact.
- Percentielcontrast maakt een aparte modelweergave; de intensiteitsmetingen
  gebruiken de oorspronkelijke pixels of projectie.

Een veld mag maximaal 16 megapixels per XY-vlak bevatten. De modelweergave wordt
standaard naar maximaal 1024 pixels aan de langste zijde verkleind, instelbaar
van 128 tot 2048. Maskers komen terug op de oorspronkelijke XY-coördinaten.
Automatische tegels met objectfusie zijn niet geïmplementeerd.

## Automatische 3D-projectie

Bij meer dan één Z-vlak maakt de workflow automatisch een projectie per kanaal
en **per tijdpunt**. De geavanceerde Bilayers-optie biedt:

| Optie | Gedrag | Pixeltype |
| --- | --- | --- |
| **Max** — standaard | Hoogste pixelwaarde over Z | Oorspronkelijk pixeltype |
| **Mean** | Gemiddelde pixelwaarde over Z | float32 |

De tijdas wordt nooit samengevoegd. Reeds 2D-invoer behoudt haar pixelwaarden.
De uitvoer gebruikt voor OMERO de TCZYX-indeling met één Z-vlak, terwijl de
bronvolume onaangeraakt blijft. XY- en tijdkalibratie blijven behouden.
Input-label-ID's uit een 3D-volume worden niet numeriek geprojecteerd.

Bij EM kunnen projecties verschillende membranen en organellen op elkaar leggen.
De galerij bevat daarom ook expliciete 2D-doorsneden uit de EM-volumes.

## Vier onafhankelijke labels

Elke actieve stap heeft een unieke labelnaam, een Engelse beschrijving en een
kanaalkeuze. Mogelijke voorbeelden zijn `tissue`, `vessels`, `mitochondria` en
`dab_positive`. Verschillende promptgroepen kunnen overlappen.

**Instances** bewaart één ID per door het model voorspeld object. Binnen één
groep wint bij overlap de hoogste pixelwaarschijnlijkheid; de eerste voorspelling
wint exacte ties. **Semantic** voegt alle objecten binnen één prompt samen tot
een binair masker. De standaard waarschijnlijkheidsdrempel is 0,5.

Een afwezige structuur kan een leeg masker opleveren. Dat is een modelvoorspelling,
geen bewijs van afwezigheid. Een ongeldige objectrespons of afgebroken generatie
wordt geweigerd en als mislukte run bewaard. De workflow repareert geen coördinaten
en koppelt geen maskers aan de verkeerde objecttokens.

## Commandoregel

```powershell
.venv\Scripts\python wrapper.py `
  --infolder publicdata\ome-zarr\public-ki67-lymphoma-dab-roi.ome.zarr `
  --outfolder outputfolder\ki67-test `
  --prompt-1 "brown DAB-positive tissue" --name-1 dab_positive --channels-1 1,2,3 `
  --prompt-2 "the entire tissue section" --name-2 tissue --channels-2 1,2,3 `
  --normalization dtype --projection Max --device cuda:0
```

Gebruik `--preflight-only` om alle veldmetadata te controleren zonder modelladen
of uitvoer te schrijven. De parameters staan in `config.yaml`, de Bilayers-descriptor.

## Uitvoer en CSV-metingen

Per invoer ontstaat `<bron>__wevisonevl.ome.zarr`, met per beeld of screenveld
`labels/wevisone_<labelnaam>/`. Labelpiramides gebruiken nearest-neighbour;
projectiepiramides gebruiken area-gemiddelden. De runrapportage bewaart prompts,
contrastgrenzen, modelrevisie, coördinaten, tellingen en looptijden.

Eén **measurements.csv** in de uitvoermap bevat alle beelden, velden, tijdpunten
en promptgroepen van de volledige run. Elke rij beschrijft één label-ID.

| Groep | Kolommen |
| --- | --- |
| Identificatie | Bron, uitvoer, veld, well, tijdpunt, prompt en label-ID |
| Oppervlakte en positie | Pixeloppervlakte, centroid, bounding box met exclusief maximum |
| Vorm | Omtrek, equivalente diameter, hoofd-/nevenas, eccentriciteit, soliditeit, extent en oriëntatie |
| Fysieke oppervlakte | µm², alleen bij bekende positieve NGFF-XY-kalibratie |
| Ieder beeldkanaal | Geldige pixels, minimum, maximum, gemiddelde en totale intensiteit |

Ook kanalen buiten de modelinvoer worden gemeten. Bij 3D-invoer meten we op de
projectie, vóór RGB-normalisatie. NaN/Inf-pixels tellen niet mee; het geldige
pixelaantal maakt dit zichtbaar. Een volledig lege run schrijft alleen de
CSV-kolomkoppen. Een mislukte run bewaart `measurements.partial-*` en publiceert
geen voltooide CSV.

## Bilayers en BIOMERO

De zichtbare naam is **CISegWeVisOneVL**; de configuratiesleutel kan
`cisegwevisonevl` zijn. De descriptor declareert de CSV als measurement-uitvoer
met formaat CSV en één bestand. De geïnstalleerde BIOMERO-parser is hierop getest.

De Docker-recepten voor de headless workflow en aparte interne modelcache zijn
voorbereid. Er is nog geen nieuwe image gebouwd of in Slurm/BIOMERO geïnstalleerd.
Een daadwerkelijke attachment-import hoort bij die volgende validatiefase.

## Voorbeelden reproduceren

```powershell
.venv\Scripts\python tools\prepare_publicdata.py --organoids
.venv\Scripts\python tools\run_gallery_inference.py
.venv\Scripts\python -m pytest -q
```

De aanvullende voorbeelden gebruiken de optionele `requirements_publicdata.txt`
en de curatiescripts. Een deel komt uit de oorspronkelijke lokale PublicData-
collectie. De publieke galerij vermeldt oorspronkelijke URLs waar die bekend
zijn, selectiegrenzen, resoluties en licentie-informatie. De modelgewichten en
volledige brondata zijn niet in Git opgeslagen. Downloadbare galerijlabels zijn
afgeleide modelresultaten, geen handmatige referentiemaskers.
