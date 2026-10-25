# Implementatieonderzoek en lokale resultaten

Onderzocht en getest op 25 oktober 2026. Huidige uitvoering: uitsluitend
**WeVisOne-VL-4B**. Het eerder onderzochte 2B-model en de modelkeuze zijn op
verzoek verwijderd; historische testmetingen blijven in de genegeerde
`test-results/` staan.

## Waarom deze implementatie

De officiële WeVisOne-VL Python-interface levert naast tekst ook boxen en
pixelwaarschijnlijkheden. Een gewone Hugging Face tekstpipeline is daarom niet
voldoende voor deze workflow: de kleine `mask_decoder.pt` is een noodzakelijk
onderdeel. We gebruiken de officiële `WeVisOneVL.predict(task="segmentation")`
met de Transformers-backend en zijn getrainde promptsjabloon. Er is geen aparte
SAM-pipeline nodig. Temperatuur is nul, pixelkansdrempel standaard 0,5.

De upstream-code is vastgezet op
`40f735b8daed437ece982db9718e9c9856f52a79`, de 4B-gewichten op
`4a7bed92750ac9d8b8a124cede14759036932dc2`. De PyTorch-decoder heeft een
device-onafhankelijke implementatie; op deze Windows-machine is geen extra
CUDA-compilatie, FlashAttention of vLLM nodig. Python 3.12 was noodzakelijk voor
de upstream vastgezette SciPy 1.18.1. De lokale omgeving gebruikt PyTorch
2.11.0+cu126 en Transformers 5.12.1. `uv pip check` bevestigde compatibele
afhankelijkheden.

De technische rapportage en publieke benchmarks richten zich niet specifiek op
microscopie. De resultaten hieronder zijn daarom nodig om de biologische
toepasbaarheid te beoordelen. Er is geen training of fine-tuning uitgevoerd;
de officiële repository biedt die code nog niet als uitgewerkte workflow.

De bronbehoudende uitvoer en Bilayers-conventies volgen cisegmentation v0.6.6.
De nieuwe adapter heeft een eigen beperkte engine, zodat de oude Cellpose- en
StarDist-afhankelijkheden niet in deze VLM-omgeving terechtkomen. Er zijn
maximaal vier promptgroepen, met onafhankelijke labels en kanaalkeuze.

## Data en conversie

De vijf biologische voorbeelden zijn echte 2D-beelden. Het oorspronkelijke beeld wordt als TCZYX met
T=Z=1 naar NGFF 0.4/Zarr v2 geconverteerd. RGB wordt drie afzonderlijke kanalen.
Piramides gebruiken area-gemiddelden; de hoogste resolutie blijft exact gelijk
aan de bron. TIFF, OME-XML, hashes, herkomst en licentie zijn lokaal bewaard.

| Voorbeeld | Vorm | Biologische toepassing | Referentie |
| --- | --- | --- | --- |
| `cell` | 660 × 550, grijs | Losse cel, kwantitatieve fase | Geen handmatig masker; 0,107 µm/pixel gedocumenteerd |
| `human_mitosis` | 512 × 512, grijs | Fluorescente nuclei | Geen bijgevoegd referentiemasker |
| `immunohistochemistry` | 512 × 512, RGB | Colonglandulaire structuren en nuclei | Geen bijgevoegd referentiemasker |
| `organoids_im9` | 1040 × 1408, grijs | Veel kleine organoïden in een well | microSAM consensusmasker |
| `organoids_im10` | 1040 × 1408, grijs | Veel kleine organoïden in een well | microSAM consensusmasker |

De drie eerste beelden komen uit scikit-image; de organoïden uit de microSAM
2D-gebruikersstudie, Zenodo 14036957, `final_dataset/test/images/` met de
bijbehorende `masks/`. Alleen vier geselecteerde TIFF-leden zijn opgehaald met
HTTP byte-ranges, gecontroleerd op membergrootte en CRC32. De onvolledige brede
ZIP-download is niet als bron of geldig archief gebruikt. Consensusmaskers zijn
onafhankelijke beeldannotaties; we meten foreground-overeenkomst, niet
instance-identiteit of afzonderlijke objectdetectieprestatie.

Voor een reproduceerbare HCS-smoketest staan twee ongewijzigde kopieën van de
publieke fasecel in twee wells. Dit test bestandsstructuur en uitvoering; het
zijn geen twee onafhankelijke biologische replicaten.

## Gemeten gedrag van 4B

De RTX A5000 heeft 24 GB VRAM. In de oorspronkelijke publieke matrix piekte
PyTorch op circa **11,6 GiB toegewezen GPU-geheugen**, exclusief overige desktop-
en driverallocaties. Een eenvoudige celprompt duurde na modelladen ongeveer
2 seconden; het orgaoïdbeeld met 83 voorspellingen ongeveer 45 seconden.
Dit zijn lokale metingen, geen Slurm- of HPC-benchmark.

| Beeld / prompt | Resultaat | Betekenis |
| --- | --- | --- |
| Losse cel / `cell` | 1 instance | Visueel plausibel; geen handmatige Dice-referentie |
| Fluorescentie / `cell nuclei` | 1 zeer groot masker | Ongeschikte algemene beschrijving voor deze 4B-test |
| Fluorescentie / `each bright fluorescent cell nucleus` | 127 instances in een verkennende prompttest | Veel specifieker resultaat; handmatige validatie blijft nodig |
| Histologie / `cell nuclei` | 4 grote maskers | Geen betrouwbare nuclei-segmentatie in deze test |
| Histologie / `colonic glands` | 4 maskers | Inspectie nodig; geen objectreferenties beschikbaar |
| Organoïden im9 / `organoids` | Ongeldig aantal objecten versus geldige boxen | Run geweigerd, geen voltooid resultaat |
| Organoïden im10 / `organoids` | 83 instances; Dice **0,8808**, IoU **0,7869** | Foreground-overeenkomst met consensusmasker, één beeld |

Een specifiekere orgaoïdbeschrijving op im9 leverde in de eerdere 2B-verkenning
118 objecttokens maar 116 geldige boxen op, waaronder omgekeerde coördinaten.
De upstream-decoder filtert ongeldige boxen maar gebruikt daarna de eerste N
objectrepresentaties. Dat kan boxen en objectrepresentaties verkeerd koppelen.
Deze adapter controleert hun aantallen **vóór** maskerdecode en weigert de
voorspelling met de volledige tekstrespons in het foutverslag. Er worden geen
coördinaten verzonnen, omgewisseld of stil overgeslagen.

Een afwezige `elephant` werd als
`<ref>elephant</ref><box>none</box>` geretourneerd. Die geldige gestructureerde
afwezigheid wordt nu als lege labelgroep verwerkt. Dit onderbouwt alleen dat
specifieke controlevoorbeeld: een afwezige `organoid` op het nuclei-beeld gaf
juist een groot foutpositief masker. Algemene betrouwbare afwijzing voor
microscopie is hiermee niet aangetoond.

De oorspronkelijke 2B-orgaoïdmaskers haalden Dice 0,0890 en 0,0548. Dat model
is verwijderd en is niet meer te selecteren of te downloaden via deze workflow.

## Technische verificatie en grenzen

- De tests controleren vier afzonderlijke labelgroepen, bronbehoud, HCS-wells,
  oorspronkelijke coördinaten en transformaties, kanaalfouten, automatische
  Max/Mean-projectie per tijdpunt, incomplete runs, overlap en lege voorspellingen.
- De launcher start dezelfde wrapper via QProcess; de invoercontrole is als
  echte child-process-test uitgevoerd. De normale visuele Windowsinspectie kon
  niet worden afgerond door `GetCursorPos failed: Toegang geweigerd (0x80070005)`.
- De bestaande OMERO Server ZarrReader las een beeld met vier promptgroepen als
  vijf series. Alle tien gecontroleerde bron-/labelvensters over twee
  resoluties hadden exact dezelfde hashes als de Python-pixels.
- De volledige oorspronkelijke beeldpiramides in voltooide publieke tests zijn
  met hun invoer vergeleken; de bronstores bleven ongewijzigd.
- Een inputlimiet beschermt tegen onbedoelde zeer grote 2D-velden. De eerste
  versie heeft geen automatische tegels/objectfusie, batchconcurrentie,
  meetdatabase, tracking of fijngetraind microscopiemodel.
- Docker-recepten zijn voorbereid maar niet gebouwd, gepubliceerd of in de
  draaiende BIOMERO-stack geïnstalleerd. Readercompatibiliteit is geen
  uitgevoerde OMERO-database-import of Slurm-validatie.

De exacte JSON-rapporten, overlays, mislukte responsen en GPU-controles staan in
de genegeerde `test-results/`. Succesvolle uitvoering en goede biologische
segmentatie worden daar apart beoordeeld. De geschikte vervolgstap is nu
beeld- en promptselectie in de lokale launcher. Domeintraining of een andere
segmentatiebackbone zou apart onderzoek vereisen als consistente brede
microscopieprestatie het doel wordt.

## Toegevoegde automatische 3D-projectie en tijdreeksen

De geavanceerde Bilayers-optie `projection` biedt **Max** (standaard) en
**Mean**. Z>1 wordt automatisch gereduceerd per kanaal, per tijdpunt en per
screenveld. De 2D-inferentie ontvangt elk tijdpunt afzonderlijk; tijd wordt
nooit gemiddeld of gemaximaliseerd. Bij reeds 2D-invoer blijven alle pixels
behouden. De uitvoer bevat de projectie en haar labels, de bronvolume blijft
onaangeraakt. Max behoudt dtype; Mean schrijft float32. Outputpiramides worden
na projectie opnieuw opgebouwd, zodat ze dezelfde projectie afbeelden.

Voor OMERO-compatibiliteit wordt geprojecteerde uitvoer naar TCZYX met Z=1
genormaliseerd. De oorspronkelijke fysieke Z-transformatie vervalt; XY- en
tijdtransformaties blijven intact. Ook labels krijgen TCZYX met C=Z=1.
OME-XML wordt bijgewerkt naar
SizeZ=1 en bij Mean naar het float-pixeltype. Bestaande volumelabels worden
alleen uit de nieuwe projectie-uitvoer weggelaten en niet als numerieke IDs
geprojecteerd. HCS-wells, velden, kanalen en tijdpunten blijven behouden.

De projectietests gebruiken expliciet afgeleide fixtures met verschillende
Z- en T-waarden. Dat onderbouwt correcte gegevensverwerking, geen bewezen
biologische segmentatiekwaliteit op echte 3D-acquisities. De aparte GPU-fixture
bevat twee screenvelden, twee tijdpunten en drie Z-vlakken met een verplaatste
publieke fasecel; zowel projectiepixels als labelverplaatsing worden gecontroleerd.

De live readercontrole toonde dat de geïnstalleerde ZarrReader tijdpunten in
compacte TCYX-projecties verkeerd als nul kon lezen. De compacte, op zichzelf
geldige NGFF-opslag is daarom vervangen door dezelfde vijfassige indeling als
cisegmentation. De aanvankelijke mislukte readercontrole blijft in
`test-results/projection-runtime/` staan; de actuele controles staan in
`test-results/projection-runtime-canonical/`.

## Uitbreiding: voorbeelden en compacte CSV-metingen

De lokale set bevat nu **27 voorbeelden**, waarvan **22 toegevoegd**: 14
afzonderlijke 2D-beelden, 6 Z-stacks en 2 tijdreeksen. De volledige OME-Zarr-
invoer is ongeveer 206 MB. Originele WSI-bestanden en de opgehaalde EM-chunks
staan apart bewaard. De lokale bronkopieën zijn bestand voor bestand met
SHA-256 gecontroleerd; conversies controleren hun pixelwaarden na schrijven.
Alle voorbeelden slagen voor de workflow-preflight. Hun voorgestelde prompts
zijn niet op modelkwaliteit gevalideerd.

Toegevoegd zijn onder andere dendritische spines, neurieten, bloedvaten,
orgaoïdcoupes, vetcellen, huidlagen, vaatbundels in een plantstengel,
diatomeeën en embryo's. Hele scans van CMU-1, een prostaatbeeld en een Ki67-
lymfoomcoupe zijn op een bestaande lagere piramideresolutie als compacte
voorbeelden beschikbaar. Het Ki67/DAB-detail is een expliciet geregistreerde
native uitsnede. Twee CellMap FIB-SEM-bronnen (COS-7 en muizenlever) leveren
elk een klein echt Z-volume en de middelste 2D-doorsnede; een MIB-voorbeeld
voegt een ander EM-beeld met mitochondriën toe. Downloadherkomst, uitsneden,
resoluties, kanaalbehoud en licentie-informatie staan per voorbeeld in de catalogus.

De CSV voegt één rij per label-ID/veld/tijdpunt/prompt toe aan één bestand
`measurements.csv` voor de hele run, met oppervlakte, centroid, bounding box,
omtrek, equivalente diameter, aslengtes, eccentriciteit, soliditeit, extent en
oriëntatie. Alle beeldkanalen krijgen min/max/mean/total-intensiteit en een
geldig-pixelaantal. Fysieke oppervlakte wordt alleen geschreven met bekende,
positieve NGFF-XY-kalibratie. De intensiteiten komen uit de oorspronkelijke
2D-invoer of de projectie, niet uit de voor het model genormaliseerde RGB-weergave.

**31 tests slagen**, inclusief behoud en metingen van een vierde echt
fluorescentiekanaal, wisselende kanaalaantallen tussen invoerbeelden,
correcte tijdpunt-/labelkoppeling, ontbrekende kalibratie en afgebroken runs.
Echte 4B-runs met twee velden en twee tijdpunten geven zowel bij Max als Mean
een CSV met vier rijen; oppervlakte en intensiteiten zijn tegen de geschreven
beeld- en labelpixels gecontroleerd.

De Bilayers-descriptor declareert CSV als measurement-output met `format: csv`
en `file_count: single`. De geïnstalleerde BIOMERO-schema-adapter valideerde dit
en bevestigde de workflownaam CISegWeVisOneVL en de juiste beschrijving.
BIOMERO gebruikt hiervoor de eerste citation-entry; die staat nu op de eigen
workflownaam. De daadwerkelijke OMERO-attachment-import is nog niet uitgevoerd;
die wordt samen met de latere Docker/Slurm-test gevalideerd.

## Gepubliceerde maskers voor alle 27 voorbeelden

Voor de GitHub Pages-galerij zijn alle 27 voorbeelden opnieuw met 4B verwerkt,
met hun vastgelegde prompts en alle tijdpunten. Dat zijn **64 labelruns**:
**63 technisch voltooid** en **1 geweigerd**. Het orgaoïdbeeld `organoids_im9`
genereerde 210 objecttokens maar 209 geldige boxen; daarvoor is geen masker
als voltooid gepubliceerd. Negen voltooide labelruns hebben op het eerste
tijdpunt een leeg masker. Dat betekent dat het model niets aanwees; het is
geen bewijs dat de gezochte structuur ontbreekt.

De galerij toont per label de echte roze overlay, de gebruikte prompt,
kanaalkeuze, maskerdekking en de bronvermelding. Downloads bevatten uint32-
maskers met tijdindexen (NPZ) en meettabellen (CSV). De kaarten tonen tijdpunt 0;
bij een volledige tijdreeks bevat het labelbestand alle berekende tijdpunten.
De beschrijvingen "berekend" en "voltooid" beoordelen de uitvoering, geen
biologische juistheid. De algemene VLM blijft duidelijk wisselend presteren
op ultrastructuur, dicht opeengepakte objecten en kleuringen.

De website bevat kleine afgeleide previews en labelresultaten. Volledige
bronstores, modelgewichten, lokale werkplekpaden en ruwe runtime-logs blijven
buiten de publieke repository.

### Aanvullende primaire databronnen

- [CellMap/Janelia FIB-SEM-data](https://cellmapchallenge.janelia.org/)
- [QuPath-workshopbeelden, Thierry Pécot](https://zenodo.org/records/18302140)
- [ImageJ publieke voorbeelden](https://imagej.net/ij/images/)
- [MIB-mitochondriënvoorbeeld](https://mib.helsinki.fi/help/main2/user-interface/menu/tools/tools-watershed.html)

### Oorspronkelijke primaire bronnen

- [Officiële WeVisOne-VL-code en API](https://github.com/Tencent/WeVisOne-VL)
- [Architectuur, benchmarks en technische rapportage](https://tencent.github.io/WeVisOne-VL/)
- [Officiële 4B-modelbestanden](https://huggingface.co/tencent/WeVisOne-VL-4B)
- [microSAM 2D-orgaoïden en consensusannotaties](https://zenodo.org/records/14036957)
- [scikit-image voorbeelden, herkomst en licenties](https://scikit-image.org/docs/stable/api/skimage.data.html)
- [BBBC038, aanvullend publiek 2D-nucleibenchmark voor later onderzoek](https://bbbc.broadinstitute.org/BBBC038)
