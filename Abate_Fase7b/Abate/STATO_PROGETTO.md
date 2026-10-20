# Abate francescano – stato del progetto

Aggiornato: 16 ottobre 2026 (Fase 7: accessori consegnati, parte Unreal da fare sul PC; Fase 7b: pelle della testa ritoccata, prima/dopo in attesa dell'ok di Nico)

## Dove sta il lavoro
| Cosa | Dove | Note |
|---|---|---|
| Copia principale (persistente) | Cloud: `/mnt/user-data/outputs/Progetto_Abate` | Sopravvive al riavvio della sessione cloud. Ogni consegna arriva anche in chat come `.zip` |
| Copia di lavoro (temporanea) | Cloud: `/home/claude/Progetto_Abate` | Può sparire dopo lunga inattività: si riparte dalla copia persistente |
| File Blender, export, script | `Blender/` (≙ `Desktop\Blender\Abate` sui PC) | Versioni numerate `Saio_Abate_v00N.blend`; ogni versione nuova lascia intatta la precedente |
| Rendering e rapporti | `Blender/Render/`, `Blender/Report/` | Tavole di controllo e rapporti delle verifiche |
| Texture | `Blender/Texture/` | Dalla Fase 5: `T_Lana_N`, `T_Lana_AO`, `T_Lana_Maschere` (PNG 2048 px, dati: in Unreal sRGB spento) |
| Sorgenti | `Sorgenti/` | FBX originale del corpo, foto di riferimento, parametri del corpo |
| Strumenti del cloud | `_strumenti_cloud/` | Script che uso nel cloud per lanciare Blender senza interfaccia, sezioni e tavole. A Nico non servono |
| Asset Unreal | Progetto `Project_Monasterium` sul PC di Nico | **Repository non toccata dal cloud** (richiesta di Nico). Unreal nel cloud non gira: le fasi in Unreal (6, 8, 9, 10) si fanno sul PC |

Consegne in chat: un file può pesare al massimo 30 MiB, quindi a ogni fase arriva uno zip con le sole novità da estrarre in `Desktop\Blender` (finiscono nella cartella `Abate`). Fase 2 = `Abate_Fase2.zip`, Fase 3 = `Abate_Fase3.zip`, Fase 4 = `Abate_Fase4.zip`, Fase 5 = `Abate_Fase5.zip`, Fase 6 = `Abate_Fase6.zip`, Fase 7 = `Abate_Fase7.zip` (27,8 MiB: le 4 tavole `Fase7_*.png` arrivano a parte, con le tavole dentro lo zip superava i 30 MiB). Il progetto completo resta nella copia persistente del cloud.

## Strumenti
- Blender 5.2.2 LTS (nel cloud come modulo Python `bpy` 5.2.2: stessa versione dei PC)
- Unreal Engine 5.8, progetto `Monasterium_prova` (cartella `Project_Monasterium`)

## Decisioni prese
- Strada iniziale (Fase 0): Outfit MetaHuman per saio, mantellina, cappuccio, cordone in vita, sandali; Skeletal Mesh con ossa proprie per cordone pendente e corona; Tau rigido; anello su socket `ring_01_r`. **Cambiata nella Fase 7** (vedi sotto).
- Personaggio: NPC unico, niente primi piani cinematici; espressioni ma niente animazione facciale; Full Rig.
- **Nuovo requisito (14/10): il vestito deve essere usabile con TUTTI i MetaHuman di UE5** (prima era "non prioritario") → Outfit Asset ridimensionabile con più taglie (vedi sotto).
- Priorità: nessuna compenetrazione visibile nelle animazioni (camminata, in ginocchio, braccia alzate, seduto).
- Requisito finale (13/10): a fine lavoro il vestito deve essere **pienamente compatibile con il MetaHuman di UE5** e il personaggio completo (corpo + vestito) **non troppo pesante**.
- Dalla foto di riferimento: cappuccio abbassato raccolto a collo morbido, maniche larghe con risvolto più chiaro, balza all'orlo, cordone in vita (~115 cm), sandali a strisce di cuoio, lana bruno‑grigia non tinta.
- Confermati il 13/10 ("vanno bene tutti i parametri"): forma del blockout della Fase 2, **Tau** (non croce latina), **niente borsa**, **cappuccio come nella foto**.
- Fase 2: saio e mantellina+cappuccio sono **due oggetti separati** (strati diversi nella simulazione); il risvolto chiaro delle maniche **non è un materiale in più**: è una maschera (attributo `chiaro`) dentro lo stesso materiale lana → restano 4 materiali in tutto.
- Fase 3: la simulazione gira sulla mesh **alta** (livello 2, ~2 cm tra i vertici) perché le pieghe della lana pesante hanno bisogno di quella risoluzione; la mesh di gioco più leggera si ricava nella Fase 4 (vedi budget).
- Drappeggio della Fase 3 approvato il 14/10; la punta del cappuccio (raggrinzita) è stata sistemata nella Fase 4: ora è arrotondata e appoggiata sulla mantellina.
- Fase 4: mesh di gioco = livello 1 dentro il drappeggio (ogni vertice di gioco è un vertice della versione alta); **un solo strato + materiale lana "Two Sided" in Unreal**, spessore solo sui bordi visibili (bordino + fascia interna); mesh per la fisica = stesso livello 1 a uno strato.
- Fase 4 approvata il 14/10 ("per il resto approvo tutto"). **Niente versione femminile**: il gioco non ha donne; il "minimo un corpo maschile e uno femminile" di Epic è solo un consiglio per coprire tutti i corpi → nella Fase 5b bastano 1-2 corpi maschili (es. uno robusto).
- 15/10: Fase 5 approvata; **taglie (5b) saltate** per tempo: l'Outfit Asset ha un solo Index (`Abate`, corpo `MHC_Abate_FullBody`); su altri MetaHuman Unreal lo adatta lo stesso, con più deformazione.
- Fase 6: **Cloth Asset solo-render** (percorso "FBX" della documentazione Epic: StaticMeshImport senza sim mesh, TransferSkinWeights con Render Mesh Transfer Source = Skeletal Mesh e Closest Point on Surface, LOD con Remesh 50/30/10); la mesh per la fisica si importa ma si collega nella Fase 9. Da Epic (forum, UE 5.8): **il percorso del MetaHuman Creator/Wardrobe toglie comunque la sim mesh** → per la fisica (Fase 9) serve un secondo Outfit col template **Resizing Graph** (Strip Sim Mesh = false) applicato con un **Chaos Cloth Component** nel blueprint, oppure il Cloth Asset direttamente (l'abate è il corpo sorgente). Materiale UE `M_SaioAbate_Lana` (Two Sided) + istanza `MI_SaioAbate_Lana`, parametri `Tinta_Lana`, `Tinta_Risvolto`, `Colore_Polvere`, `Polvere_Extra`, `Specular`. Body Hidden Face Map `T_Corpo_Nascosto` sul Wardrobe Item `WI_SaioAbate`.
- Fase 5: **una sola texture 2K per saio + mantellina + cappuccio** (materiale `M_Lana`); pezzi stesi come cartamodelli col **filo verticale** (+V = verso l'alto del vestito, maniche verso la spalla; un giro di 180° è ammesso perché il filo resta verticale), stessa scala per tutti, 16 px tra i pezzi; bordini ad anello tagliati sulle cuciture del tessuto. Normal map **DirectX**; ombre d'ambiente su **due canali** (R lato dritto, G lato rovescio → `TwoSidedSign` in Unreal); maschere R risvolto, G bordi (usura), B orlo (polvere). La mesh di gioco ha il modificatore **`Triangola_per_UE`** (metodo Fixed): l'export userà gli stessi triangoli della cottura e saranno uguali in tutte le taglie. Mesh per la fisica con UV **in centimetri** (1 = 1 cm).

- **Fase 7 (15/10): nuova strada per gli accessori.** Cordone (anello in vita, mezzo nodo, coda con 3 nodi a barilotto), corona a 7 poste, Tau col cordino e sandali stanno **dentro l'Outfit**: stessa Static Mesh del saio (`SM_SaioAbate_Render`), secondo materiale `M_Accessori`, pesi dal TransferSkinWeights come il saio. L'**anello** è una **Skeletal Mesh a parte** (`SKM_AnelloAbate`, scheletro del MetaHuman, tutti i vertici su `ring_01_r` peso 1): nel guardaroba del Creator (slot SkeletalMesh) o nel Blueprint (Fase 8). Motivi: il Creator toglie comunque la sim mesh; ossa extra non previste dal guardaroba; coda e corona con fisica propria attraverserebbero il saio rigido a ogni passo; tra le dita ci sono 3-4 mm e il trasferimento automatico piegherebbe l'anello col dito vicino.
- Fase 7: **2 materiali** invece di 4: `M_Lana` (Two Sided) + `M_Accessori` (un lato; un atlante 2K per corda, legno, cuoio e ferro; ORM con B = metallo). Mezza la quantità di draw call e un terzo della memoria rispetto a tre materiali separati.
- Fase 7, prova delle pose (Blender, pesi "come Unreal"): accessori **mai dentro il corpo**; senza fisica la gonna si ripiega su coda e corona (0,5-1,2 cm camminando, fino a ~2,4 cm in ginocchio e seduto). Prendere i pesi degli accessori dalla stoffa invece che dalla pelle **non cambia nulla** (provato): la causa sono le pieghe della gonna, la cura è la fisica della Fase 9.
- 16/10, richiesta di Nico: alla fine **tutto il MetaHuman con le sue cose in una cartella `MetaHuman`** (sottocartelle dentro). Piano: nella Fase 8 l'assemblaggio esce già lì; lo spostamento di `/Game/Outfits/SaioAbate` si fa alla fine (dopo la Fase 10) dal Content Browser + correzione dei redirector, poi si aggiornano i percorsi negli script
- 16/10: macchia viola sul naso e pixel bianchi/neri sul viso al buio → causa: **Lumen spento** nella scena; riacceso, risolto. Da controllare nella Fase 8 (Post Process Volume della scena vera)
- 16/10: nello scollo si vede l'intimo dipinto sulla pelle della mesh della testa (non nascondibile). Valutate: sottocollo di lana, stretta dello scollo (con testa solo destra/sinistra), ritocco delle texture. **Scelta di Nico: Fase 7b = ritocco delle texture della testa**, consegna con la **strada A** (PNG con gli stessi nomi + *Reimport With New File* sulle texture originali in Unreal, niente script)
- 16/10: l'abate è assemblato **senza i LOD 0-2 della testa**: il LOD0 della mesh usa `MI_Face_Skin_Baked_LOD3` (texture `T_Head_LOD3_*`, 2048), i lontani `MI_Face_Skin_Baked_LOD5to7` (`T_Head_LOD5to7_*`, 1024). L'export dei *materiali* (glTF) non serve: cuoce il materiale su una sfera di prova; vanno esportate le *texture*
- Fase 7: le suole stanno **sotto il livello dei piedi** (da -0,30 a -1,30 cm): nella Fase 8 il personaggio va alzato di 1,3 cm (Epic: da UE 5.6 le suole delle calzature finiscono sotto il piano).

## Peso del personaggio (budget, triangoli al LOD0)
| Parte | Triangoli | Note |
|---|---|---|
| MetaHuman: pelle della testa | 25.100 | non nascondibile in Unreal |
| MetaHuman: occhi, denti, ciglia… | 9.200 | |
| MetaHuman: pelle del corpo | 60.800 | mani ~23.500 e piedi ~12.500 restano visibili; almeno ~16.500 sono coperti dal saio (stima prudente) |
| **MetaHuman totale** (FBX Full Body) | **95.100** | |
| Saio + mantellina + cappuccio (mesh di gioco, con spessore ai bordi) | **7.868** (fatto, Fase 4) | la versione alta ne ha 28.160 e serve solo come fonte della normal map |
| Accessori nell'Outfit (cordone 2.896, corona 2.748 col filo, Tau 612 col cordino, sandali 2.280) | **8.536** (fatto, Fase 7) | l'obiettivo iniziale era ~5.000: la corona da sola sono 80 grani |
| Anello (Skeletal Mesh a parte) | **288** (fatto, Fase 7) | |
| **Personaggio completo** | **~111.800** | ≈ +17,5% sul MetaHuman da solo (saio + accessori = 16.404 triangoli nella mesh dell'Outfit); meno se Unreal toglie le parti di corpo coperte (Body Hidden Face Map). LOD 1-3 del vestito in Unreal col nodo Remesh (50/30/10%) |

## Misure del corpo (mesh reale, cm)
- Altezza 182,3 (suola–sommità); larghezza A-pose 114,6; profondità 39,8; volto verso −Y in Blender (+Y in Unreal)
- Torace 99–101 (z 130–132, sotto le ascelle a ~133); vita 92,5 (z 115); pancia/fianchi alti 103,5 (z 104, profondità 28,3); fianchi 103 (z 92); cavallo a 80,5; ginocchio 50,1; caviglia 8,7
- Base del collo 49 (z 156); spalla (acromion) 151,9; braccia a 53° sotto l'orizzontale
- Mesh della **testa** (non nascondibile) scende fino a ~141 cm davanti e ~147–148 ai lati/dietro → colletto e cappuccio staccati dalla pelle

## Fasi
| # | Fase | Stato |
|---|---|---|
| 1 | Export corpo + test andata/ritorno | ✅ superata (scarto 0,00 cm in Unreal) |
| 2 | Blockout | ✅ approvata il 13/10/2026 |
| 3 | Simulazione cloth in Blender | ✅ approvata il 14/10/2026 (punta del cappuccio sistemata nella Fase 4) |
| 4 | Topologia, spessore, sim mesh | ✅ approvata il 14/10/2026 |
| 5 | UV, normal map, ombre e maschere della lana | ✅ approvata il 15/10/2026 ("tutto apposto") |
| 5b | Taglie: stesso vestito su altri corpi MetaHuman | ⏭ saltata il 15/10/2026 ("per questioni di tempo"): una sola taglia, quella dell'abate; si può aggiungere più avanti |
| 6 | Outfit in UE (senza fisica) | ✅ approvata il 15/10/2026 ("va tutto benissimo"; resta la domanda sull'NPC → Fase 8) |
| 7 | Accessori | 📦 parte cloud consegnata il 15/10/2026 (geometria, UV, texture, FBX, script UE, guida, prova delle pose) – **ora tocca a Nico in Unreal** |
| 7b | Pelle della testa senza canottiera (ritocco texture) | 🔍 16/10/2026: texture ritoccate e tavole prima/dopo mandate a Nico – **in attesa del suo ok** prima del pacchetto per Unreal |
| 8 | Rig, assemblaggio, integrazione | – |
| 9 | Fisica in UE | – |
| 10 | Test delle 4 pose | – |

## Fase 1 – riepilogo
- `Saio_Abate_v001.blend`: unità metriche (scala 1, cm), `REF_Corpo` (statico, saldato, non selezionabile), `REF_Originale` (import intatto, nascosto), `TEST_Guscio_1cm`
- Export FBX bloccato (script `fase1_setup_e_test.py`): Selected Objects, Mesh, Apply Scalings = FBX Units Scale, Forward −Z / Up Y, Smoothing Face, niente leaf bones/animazione
- In Unreal: `/Game/Outfits/SaioAbate/Corpo/MHC_Abate_FullBody` (Geometry Export Full Body, scheletro `metahuman_base_skel`) = corpo sorgente per la Fase 6; `/Game/_Test_Abate` = materiale di prova da cancellare
- Nota: Unreal 5.8 importa le Static Mesh con **Nanite attivo** di default

## Fase 2 – riepilogo
- `Saio_Abate_v002.blend` = v001 + collezione `BLOCKOUT`:
  - `Saio_Blockout`: 664 quad, saio fino a 10 cm da terra, sprone sulle spalle, maniche ampie con risvolto chiaro (48 facce), balza, gruppo di vertici `Linea_Cordone` (24 vertici a 115 cm)
  - `Mantellina_Blockout`: 216 quad, mantellina (21 cm davanti, 15 ai fianchi, 25 dietro) cucita al cappuccio abbassato (collo arrotolato + cappuccio adagiato sul dorso con punta)
  - entrambi con modificatore `Suddivisione` (livello 2) e materiale `M_Lana`; testo `REPORT_Fase2` dentro il file; collezione `TEST` nascosta
- Script: `fase2_blockout.py` (parametri in cm in testa al file; si rilancia su v001 e risalva v002), `render_controllo_fase2.py` (tavole)
- Controlli superati: 0 triangoli / n-gon / spigoli non-manifold; superficie liscia del saio ≥ 1,67 cm dalla pelle (mediana 6,1), mantellina ≥ 2,82 cm; mantellina sopra il saio ≥ 0,97 cm, nessun vertice sotto; dalla mesh della testa ≥ 2,17 cm (saio) e ≥ 3,33 cm (cappuccio); cuciture 126 + 36 spigoli = 8 + 2 isole UV previste

## Fase 3 – riepilogo
- `Saio_Abate_v003.blend` = v002 + collezione `DRAPPEGGIO` (visibile) con `Saio_Drappeggio` (10.734 vertici, 21.248 triangoli) e `Mantellina_Drappeggio` (3.568 vertici, 6.912 triangoli): mesh ferme, stessa topologia del blockout al livello 2 (cuciture, attributo `chiaro`, gruppo `Linea_Cordone` conservati)
- Collezione `FASE3_SIMULAZIONE` (esclusa): `Saio_Sim` e `Mantellina_Sim` con il modificatore Cloth, per rivedere la caduta; `REF_Corpo` ha un modificatore Collision; `BLOCKOUT` nascosta; testo `REPORT_Fase3` nel file
- Script: `fase3_simulazione.py` (parametri in testa; si lancia su v002 e salva v003; ~5–8 minuti), `render_controllo_fase3.py`
- Lana pesante: massa 0,25 kg/vertice (mantellina 0,119: stessa lana al m², mesh più fitta), tensione 60, compressione 30, taglio 30, piegatura 10 (balza e risvolti 40, cappuccio 40: doppio strato), aria 4, qualità 10 / collisioni 5
- Collisioni: stoffa a 1,5 cm dalla pelle (margine per le animazioni); auto-collisione 0,25 cm (Blender tiene il doppio); mantellina sopra il saio a 0,7 cm
- Cordone: anello di 96 vertici a 115,2 cm stretto da 122 a 102 cm di giro in 30 fotogrammi (sull'inviluppo del busto + 1,5 cm); scollo fermo con 4 file sotto trattenute sempre meno; cucitura del collo ferma, collo arrotolato e lembo del cappuccio trattenuti debolmente
- Controlli superati: nessun vertice dentro il corpo, nessuna faccia che attraversa (corpo/saio, corpo/mantellina, saio/mantellina), nessuna auto-intersezione; saio ≥ 1,31 cm dalla pelle (5% 1,50, mediana 4,7), mantellina ≥ 1,98 cm; mantellina sopra il saio ≥ 0,54 cm; testa ≥ 1,60 cm (saio) e ≥ 2,81 cm (cappuccio); allungamento 99% dei lati entro +2,3% (saio) e +5,7% (mantellina), solo 3 lati tirati oltre il 20% nel cavo dell'ascella sinistra; orlo 9,2–11,1 cm da terra; stoffa ferma (ultimo fotogramma 1,4 mm saio, 0,5 mm mantellina)
- Riproducibilità: rilanciando lo script nel cloud il drappeggio esce identico (scarto 0,0000 cm)
- Da ricordare per la Fase 4: la stoffa è drappeggiata in A-pose (la posa di riferimento del MetaHuman); le pieghe "dinamiche" in movimento le darà la fisica di Unreal (Fase 9)

## Fase 4 – riepilogo
- `Saio_Abate_v004.blend` = v003 + collezione `GIOCO` (visibile) con `Saio_Gioco` (2.902 vertici, 5.696 triangoli) e `Mantellina_Gioco` (1.142 vertici, 2.172 triangoli), tutti quad + collezione `FISICA` (nascosta) con `Saio_Fisica` (2.710 vertici) e `Mantellina_Fisica` (920 vertici), uno strato, gruppo `Proposta_Fisica` (0 = segue il corpo, 1 = libera: solo una proposta per la Fase 9). `DRAPPEGGIO` e `BLOCKOUT` nascoste; nel drappeggio la punta del cappuccio è sistemata (fonte della normal map)
- Script: `fase4_mesh_gioco.py` (si lancia su v003, ~1 minuto, salva v004), `render_controllo_fase4.py`
- Fedeltà: la superficie alta si stacca da quella di gioco in media di 0,09 cm (saio) e 0,04 cm (mantellina), 95% entro 0,37 / 0,15 cm, massimo 1,09 / 0,39 cm (pieghe minute della vita → normal map)
- Spessore: saio 0,4 cm su orlo e polsini (scollo escluso: coperto dal collo), mantellina 0,3 cm sul bordo e sul cappuccio; verso "dentro" deciso per ogni bordo col corpo (il cappuccio rovesciato ha la stoffa girata); spigoli vivi e cuciture UV sui bordi
- Controlli superati: 0 n-gon, 0 spigoli non-manifold, nessuna faccia che attraversa (corpo/saio, corpo/mantellina, saio/mantellina), nessuna auto-intersezione; saio ≥ 1,00 cm dalla pelle (fascia interna compresa), mantellina ≥ 1,85; testa ≥ 1,77 / 2,81 cm; isole UV previste 11 (saio) + 4 (mantellina)

## Fase 5 – riepilogo
- `Saio_Abate_v005.blend` = v004 + UV (`UVMap`, canale 0) su `Saio_Gioco` e `Mantellina_Gioco`, UV in centimetri su `Saio_Fisica` e `Mantellina_Fisica`, modificatore `Triangola_per_UE` (Fixed) sulla mesh di gioco, materiali `M_Lana` (anteprima con le texture: è il materiale che va in Unreal), `M_Lana_Alta` (drappeggio), `M_Fisica` (solo colore, la mesh per la fisica in Unreal non si vede); testo `REPORT_Fase5`. Texture in `Blender/Texture/` (percorsi relativi `//Texture/...`)
- Script: `fase5_uv_mappe.py` (si lancia su v004; nel cloud ~19 minuti, quasi tutti di cottura delle ombre), `render_controllo_fase5.py`
- Pezzi: saio 12 (Davanti, Dietro, 2 balze, 2 maniche, 2 risvolti, 4 bordini), mantellina 4 (Mantellina, Cappuccio e collo, 2 bordini); i bordini (spessore della Fase 4) erano anelli chiusi: tagliati dove arriva una cucitura (fianchi, sotto-manica, centro dietro)
- UV: stese col metodo **Minimum Stretch** sui triangoli dell'export (stendendo i quad, 5 triangoli sotto le ascelle restavano capovolti); 0 triangoli capovolti, 0 pixel sovrapposti, spazio minimo 15,9 px; **55,7% della texture usata, 8,6 px/cm (1 pixel = 1,16 mm)**; area entro ±10% sul 94% della stoffa, entro ±20% sul 99%
- Cottura (Cycles, a 4096 px e ridotta a 2048): il drappeggio alto è diviso nei suoi pezzi e ogni gruppo (busto, maniche, risvolti, mantellina, cappuccio) vede solo il suo, così il cappuccio non "pesca" la mantellina che ha sotto; pixel colpiti 99,95–99,97%; normal map: inclinazione mediana 1,6°, 95% entro 11°, tetto a 60° sullo 0,05% dei pixel (stoffa raggrinzita sotto le ascelle); ombre 32 campioni (128 a 2048) entro 10 cm, media lato dritto 0,80, rovescio 0,53; bordini: normale piatta e ombre calcolate sulla mesh di gioco
- Maschere: risvolto (attributo `chiaro`), bordi (1 sul bordo → 0 a 6 cm lungo la stoffa), orlo (1 all'orlo → 0 a 45 cm da terra)
- Limiti noti: ombre cotte in A-pose (non si muovono con la stoffa: tenute "corte", 10 cm); il 44% della texture resta vuoto (prezzo del filo verticale: ruotando liberamente i pezzi si guadagnerebbe ~10% di risoluzione ma la trama cambierebbe verso da un pezzo all'altro); la normal map aggiunge solo le pieghe sotto 1 cm (quelle grandi sono già nella mesh)

## Fase 6 – riepilogo (parte Blender / cloud)
- `Saio_Abate_v006.blend` = v005 + anteprima di `M_Lana` con le texture finali; testo `REPORT_Fase6`. Script `fase6_texture_export.py` (si lancia su v005, ~1 minuto) e `render_controllo_fase6.py`
- Texture nuove in `Blender/Texture`: `T_Lana_BC` (sRGB: lana bruno-grigia a macchie da rumore 3D cotto nelle UV, risvolto, bordi sbiaditi, polvere all'orlo; media lineare 0,122/0,098/0,074), `T_Lana_ORM` (R ombre dritto, G ruvidezza 0,73-0,98, B ombre rovescio), `T_Corpo_Nascosto` (2048 px nelle UV del corpo = riquadro UV 1-2 del corpo combinato spostato in 0-1; nero = tolto)
- Corpo nascosto: 17.371 facce su 60.816 del corpo (29%): busto, metà alta delle braccia, cosce, ginocchia; regola = osso principale della faccia (pesi del MetaHuman) **e** stoffa davanti alla faccia lungo la normale; pulizia a maggioranza; 1 px di margine nero
- Export in `Blender/Export`: `SM_SaioAbate_Render.fbx` (saio + mantellina uniti, 7.868 triangoli, tangenti, materiale M_Lana, UV 0-1) e `SM_SaioAbate_Fisica.fbx` (7.040 triangoli, UV in cm), impostazioni della Fase 1 + tangenti; riletti in Blender: stessi triangoli e vertici, ingombro identico (in Unreal: min (-53,85, -19,70, 9,18) max (53,85, 31,56, 160,61) cm)
- Unreal: `fase6_import_ue.py` (importa texture con compressione giusta, FBX come Static Mesh con Nanite spento, crea materiale e istanza, controlla ingombro e triangoli, scrive `Report/ue_fase6_report.txt`); passi a mano in `GUIDA_Fase6_Unreal.md` (Cloth Asset, Outfit Asset, Wardrobe Item con Body Hidden Face Map, assemblaggio)
- Non verificabile dal cloud (Unreal non gira qui): compilazione del materiale (Substrate attivo di default nei progetti nuovi: i materiali "classici" vengono convertiti), comportamento del Cloth Asset solo-render, assemblaggio e struttura di `BP_Abate`

## Fase 7 – riepilogo (parte Blender / cloud)
- `Saio_Abate_v007.blend` = v006 + collezione `ACCESSORI` con `Accessori_Gioco` (cordone, corona, Tau col cordino, sandali: 8.536 triangoli, materiale `M_Accessori` con le texture finali) e `Anello_Gioco` (288 triangoli, figlio dell'armatura `root`, gruppo `ring_01_r` peso 1, modificatore Armatura); testo `REPORT_Fase7`. Le mesh alte non restano nel file: le rifà lo script
- Script: `fase7_accessori.py` (si lancia su v006; nel cloud ~12 minuti, quasi tutti di cottura a 4096 px), `render_controllo_fase7.py`, `prova_pose_fase7.py` (pesi "come Unreal" + 4 pose + conteggi), `fase7_import_ue.py` (Unreal), guida `GUIDA_Fase7_Unreal.md`
- Cordone Ø 1,3 cm: anello in vita 108,8 cm sulla linea della Fase 3 (z 115,2), stretto sulle pieghe della lana con 0,12 cm d'aria (controllo 3D, spinta in fuori dove serve); mezzo nodo di 1,5 giri sul fianco destro (35° dal davanti), coda di 99 cm di corda che scende lungo la gonna ("appesa": non rientra dove la gonna rientra) fino a 50 cm da terra, 3 nodi a barilotto (2,5 giri) a 80/69/58 cm, punta legata con lo spago
- Corona francescana: 7 poste (1 Pater Ø 1 cm + 10 Ave Ø 0,7 cm) = 77 grani su due fili affiancati appesi al cordone (legaccio) sul fianco sinistro (42°), grano di giunzione Ø 1,1 cm, 2 Ave e crocetta di 3 cm (occhiello col foro); in basso a ~75 cm da terra
- Tau di olivo 7 × 6 × 0,9 cm sul petto, appoggiato alla mantellina (0,10 cm d'aria), inclinato di 3,4° perché dietro passa il cordino; cordino Ø 0,35 cm passato nel foro, nodo sopra il Tau, due capi che salgono e spariscono nella piega del collo arrotolato (tasca tra lembo e mantellina, misurata coi raggi)
- Sandali: suola di 1 cm dall'impronta del piede (+0,45 cm, +0,7 davanti), 3 cinghie che seguono la pelle (avampiede, collo del piede, tallone che scende ai lati) con 0,15 cm d'aria e spinta automatica dove una faccia taglierebbe la pelle (provate tutte e due le diagonali di ogni quad)
- Anello a sigillo di ferro sulla falange dell'anulare destro (60% verso la seconda articolazione, oltre la membrana tra le dita): foro dalle sezioni vere del dito + 0,05 cm, più sottile sui lati verso medio e mignolo, castone piatto col Tau inciso (mesh alta)
- Mesh alte per la cottura (~267.000 facce): tre trefoli attorcigliati con le fibre a rilievo per tutte le corde, grani lisci col foro, sagome arrotondate (curve 2D riempite: il contorno si stringe prima dello smusso), cinghie a bordi tondi, anello col Tau inciso
- UV: un atlante 2048 per tutti gli accessori, 0 pixel sovrapposti, 8 px tra i pezzi, ~35-43 px/cm (4-5 volte la lana); suola sopra e sotto e lato interno delle cinghie a densità ridotta (si vedono poco). Texture `T_Accessori_BC` (sRGB), `T_Accessori_N` (DirectX), `T_Accessori_ORM` (R ombre, G ruvidezza, B metallo); colori procedurali per parte (corda bianco sporco con le fibre, olivo con le venature, noce per i grani, cuoio con i bordi consumati, ferro con la ruggine nei solchi)
- Controlli (A-pose): nessun triangolo degli accessori attraversa il corpo; con la stoffa solo il giro del mezzo nodo dietro il cordone (dentro la piega, nascosto); contatti voluti: filo dentro i grani, filo nell'occhiello della crocetta, cinghie infilate nella suola, nodo del cordino del Tau
- Export: `SM_SaioAbate_Render.fbx` (saio + mantellina + accessori, 16.404 triangoli, materiali `M_Lana` e `M_Accessori`), `SKM_AnelloAbate.fbx` (armatura MetaHuman completa, oggetto `root` esportato come osso radice, 341 ossa, anello su `ring_01_r`), `attesi_fase7.json` (valori attesi per lo script di Unreal); riletti in Blender: stessi triangoli, ossa e posizioni (scarto 0,000 cm)
- Prova delle pose (`prova_pose_fase7.py`): accessori/corpo 0 in tutte le pose; accessori/stoffa in più rispetto al riferimento: camminata ~200 triangoli, in ginocchio ~265, seduto ~340, braccia alzate 0 (la gonna senza fisica si ripiega sopra coda e corona)
- Non verificabile dal cloud: import dell'anello sullo scheletro del MetaHuman con Interchange da Python (lo script prova Interchange e poi l'importatore FBX classico; se fallisce c'è il passo a mano nella guida), slot SkeletalMesh del guardaroba e sua validazione, comportamento dei nodi Remesh sugli accessori per i LOD 1-3

## Fase 7b – riepilogo (pelle della testa senza canottiera)
- Originali di Nico (export PNG da Unreal) in `Sorgenti/Texture_Testa_Originali/` (anche occhi, denti, `T_BakedNormal_LOD3-5`: questi non contengono la canottiera e non si toccano)
- Texture ritoccate (8): `Blender/Texture/PelleTesta_Fase7b/` con gli stessi nomi: `T_Head_LOD3_BC_VT`, `_N_VT`, `_SRMF_VT`, `_Scatter_VT`, `T_Head_LOD5to7_BC_VT`, `_N_VT`, `T_Head_LOD5to7_SRMF`, `T_Head_LOD5to7_Scatter_VT` (RGBA 8 bit come gli originali)
- Script: `Blender/Script/fase7b_pelle_testa.py` (Python di sistema con numpy, scipy, opencv, pillow; ~4 minuti; seme casuale fisso → risultato identico a ogni lancio), `render_controllo_fase7b.py` (Blender: `<cartella_texture> <uscita> <prefisso> [campioni] [tutte|pelle|gioco]`), tavole `_strumenti_cloud/compose_fase7b.py`
- Maschera: SRMF G = 255 (ruvidezza 1) o colore grigio (saturazione < 0,1; pelle ~0,5) nella fascia bassa, + pixel di passaggio collegati, + 4 px (2048) / 2 px (1024). LOD3: 153.884 pixel (3,7%)
- Metodo: tono (basse frequenze, σ 8 px) interpolato dai bordi con una membrana (Laplace); grana (pori, rilievo, macchioline) clonata con PatchMatch multi-scala da collo e petto entro 300 px, con le stesse toppe per colore, normal map e SRMF, scelte anche per "intensità della grana" (la pelle vicino al bordo UV è più liscia) e riscalate all'intensità del punto; raccordo di Poisson; macchie riconoscibili (chiazza rosa del collo, nei) escluse dalle sorgenti. Scatter: uniforme attorno alle spalline → solo membrana. LOD5to7 = LOD3 ritoccato rimpicciolito + raccordo (gli originali LOD5to7 sono il LOD3 rimpicciolito, scarto medio < 1,5/255)
- Controlli: pixel fuori maschera identici (0 cambiati su tutte e 8), canali alfa identici, normali di lunghezza 1, nessun pixel grigio né ruvidezza 255 rimasto, gradiente sul bordo della maschera non più alto che altrove (nessuna cucitura); render prima/dopo `Blender/Render/Fase7b_1_prima_dopo.png`, `Fase7b_2_texture.png`
- Le UV della pelle della testa si sovrappongono in fondo all'immagine con ~265 triangoli dell'interno degli occhi (z ≈ 169 cm): non si vedono; ora prendono pelle invece del grigio
- Limite: se Nico riassembla l'abate nel Creator, le texture tornano quelle originali → rifare i reimport

## Come renderlo usabile con tutti i MetaHuman (UE 5.8, documentazione Epic)
- Outfit Asset "Resizable Outfit": nel Dataflow, sotto **Sized Outfit Source**, un Index per taglia con **Size Name**, **Source Asset** (il Cloth Asset di quella taglia) e **Source Body Parts** (il corpo `<nome>_CombinedSkelMesh`). Unreal deforma la taglia più vicina al corpo di destinazione; più taglie = meno deformazione (minimo consigliato: un corpo maschile e uno femminile). **Num Resizing Interpolation Points** 1000–2500 (default 1500)
- Cloth Asset (template **USD Cloth**): due **StaticMeshImport** (uno render, uno sim) → **MergeClothCollections** → **TransferSkinWeights** (Skeletal Mesh = corpo della taglia, metodo Closest Point on Surface) → **ClothAssetTerminal**; LOD automatici con nodi **Remesh** (Target Percent Render 50 / 30 / 10). MetaHuman si aspetta 4 LOD (0-3). Le mesh si importano come **Static Mesh**, senza skinning
- Mesh per la fisica: dalla Fase 5 ha UV **in centimetri** → nello StaticMeshImport della sim mesh bastano i valori di default **UV Channel = 0, UV Scale = (1, 1)** (verificato sul riferimento Epic del nodo). Alternativa: UV Channel = -1 (Unreal ricava da solo i pattern dal 3D). Il nodo ha anche Sim/Render Mesh Section: si potrebbe usare una sola Static Mesh con due sezioni (M_Lana = render, M_Fisica = sim)
- Body Hidden Face Map (Editor Pipeline > Outfit): texture nelle UV del corpo, bianco = visibile, nero = nascosto; non si può nascondere la testa. Da generare nella Fase 6 dalla copertura del vestito (valida per tutte le taglie: stessa UV dei corpi)
- Taglie (Fase 5b): Nico crea in UE i corpi (MetaHuman Character → Body Params / Blend), **Export Tool → Geometry Export → Full Body Skeletal Mesh**, nome `<nome>_CombinedSkelMesh`, poi **Asset Actions → Export** in FBX. Nel cloud: il vestito dell'abate si trasferisce sul nuovo corpo, si ri-simula (Fase 3) e se ne ricava la mesh di gioco (Fase 4) → stessa topologia e stesse UV per tutte le taglie. **Le UV non si rifanno: si copiano dal v005 per indice** (stesse facce, stesso ordine); per ogni taglia si ricuociono normal map e ombre (le pieghe cambiano), le maschere restano quelle
- Materiale lana: **Two Sided**; parametri colore con lo stesso nome in tutte le taglie (Runtime Material Parameters)

## Come rigenerare tutto nel cloud (promemoria tecnico)
- Ambiente: venv Python 3.13 con `pip install bpy==5.2.2 numpy matplotlib pillow`
- Dalla cartella del progetto, con `PY` = python del venv:
  - `$PY _strumenti_cloud/run_fase2.py -- Blender/Saio_Abate_v001.blend Blender/Script/fase2_blockout.py`
  - `$PY _strumenti_cloud/run_fase2.py -- Blender/Saio_Abate_v002.blend Blender/Script/fase3_simulazione.py` (apre il file e lancia lo script; vale per qualsiasi fase)
  - `$PY _strumenti_cloud/run_fase2.py -- Blender/Saio_Abate_v003.blend Blender/Script/fase4_mesh_gioco.py`
  - `$PY _strumenti_cloud/run_fase2.py -- Blender/Saio_Abate_v004.blend Blender/Script/fase5_uv_mappe.py` (~19 minuti: nel cloud va lanciato in background con `nohup`, la shell si ferma a 10 minuti)
  - `$PY _strumenti_cloud/run_fase2.py -- Blender/Saio_Abate_v005.blend Blender/Script/fase6_texture_export.py` (~1 minuto)
  - `$PY _strumenti_cloud/run_fase2.py -- Blender/Saio_Abate_v006.blend Blender/Script/fase7_accessori.py` (~12 minuti: in background con `nohup`)
  - Fase 7b: `python3 Blender/Script/fase7b_pelle_testa.py Sorgenti/Texture_Testa_Originali <uscita> <diagnostica>` (~4 minuti, Python di sistema); render `run_script.py -- Blender/Saio_Abate_v007.blend Blender/Script/render_controllo_fase7b.py <texture> <render> prima|dopo 64`; tavole `python3 _strumenti_cloud/compose_fase7b.py <render> Sorgenti/Texture_Testa_Originali <uscita> <diagnostica>/maschera_lod3.npy Blender/Render`
  - Fase 7, tavole: `run_script.py` con `render_controllo_fase7.py <viste> 48`, `prova_pose_fase7.py <pose> 24`, `_strumenti_cloud/disegna_uv_fase7.py <uv.png>`, poi `compose_fase7.py <viste> <pose> Blender/Texture <uv.png> Blender/Render`; verifica: `confronta_f7.py`
  - Fase 6, tavole: `run_script.py` con `render_controllo_fase6.py <cartella_viste>`, poi `compose_fase6.py <viste> Blender/Texture Blender/Render 29`
  - Fase 5, tavole: `run_script.py` con `render_controllo_fase5.py <cartella_viste>`, poi `disegna_uv_fase5.py -- Blender/Saio_Abate_v005.blend Blender/Script/fase5_uv_mappe.py <cartella_disegni>` e `compose_fase5.py <viste> <disegni> Blender/Texture Blender/Render 55.7 8.60`; verifica: `confronta_f5.py -- <a.blend> <b.blend> <texA> <texB>`
  - Fase 4, tavole: `run_script.py` con `render_controllo_fase4.py`, poi `render_punta.py` (punta prima/dopo) e `compose_fase4.py <viste> Blender/Render <punta_prima> <punta_dopo> 28160 7868`
  - `$PY _strumenti_cloud/run_script.py -- Blender/Saio_Abate_v003.blend Blender/Script/render_controllo_fase3.py <cartella_viste>`
  - `$PY _strumenti_cloud/sezioni.py -- Blender/Saio_Abate_v003.blend Blender/Render/Fase3_4_sezioni.png Saio_Drappeggio Mantellina_Drappeggio drappeggio`
  - `python _strumenti_cloud/compose_fase3.py <cartella_viste> Blender/Render Sorgenti/foto_riferimento.png` (Fase 2: `compose.py`)
- Render senza interfaccia: Workbench e Cycles funzionano (gli avvisi "EGL Error" sono innocui), EEVEE è lentissimo
- Copia persistente: le PNG scritte in `/mnt/user-data/outputs` ricevono un blocco `caBX` (credenziali di contenuto, ~5,8 KB) → md5 diverso ma pixel identici; per verificare la copia si confrontano i pixel delle PNG e l'md5 degli altri file (dentro gli zip le PNG restano intatte)
- Attenzione (bpy 5.2): aggiungere un layer a un BMesh rigenera gli oggetti Python degli elementi → i dizionari con chiave BMFace/BMVert non li riconoscono più; usare gli indici
- Livello 1 dentro livello 2: con "limit surface" attivo ogni vertice del livello 1 ha la STESSA posizione di un vertice del livello 2 (non lo stesso indice): si abbinano per posizione con un KDTree (scarto 0)
- Lezioni della stoffa in Blender 5.2: (1) la distanza di auto-collisione effettiva è il DOPPIO del valore impostato e due parti che partono più vicine "esplodono" al primo fotogramma; (2) con mesh di densità diverse la massa per vertice va scalata con l'area per vertice; (3) un lembo singolo e morbido appoggiato sul bordo di un altro strato trema all'infinito: più rigidità alle pieghe e pin leggerissimi lo fermano
- Lezioni della Fase 5 (bpy 5.2): (1) **stendere (unwrap) gli stessi triangoli dell'export**: stendendo i quad Blender li divide a modo suo e alcuni triangoli "nostri" restano capovolti; (2) `pack_islands` con margine FRACTION lascia quel margine attorno a OGNI pezzo → lo spazio tra due pezzi è il doppio; (3) Cycles non cuoce un oggetto con tutte le visibilità ai raggi spente (cottura diretta vuota, senza errori): per le cotture "selected to active" invece la mesh bassa può essere invisibile; (4) le cotture lasciano intatti i pixel senza colpo (alpha resta 0): così si sa quali pixel sono stati scritti; (5) le collezioni bpy non accettano lo slice con passo (`[::7]`); (6) la cottura a 4096 px occupa ~3,7 GB: con un render Cycles in parallelo la macchina del cloud (8 GB) finisce la memoria e il processo viene ucciso → lanciarli uno alla volta
- Lezioni della Fase 6: (1) nel corpo combinato del MetaHuman la testa sta nel riquadro UV 0-1 e il corpo nell'1-2: la Body Hidden Face Map va disegnata con le UV del corpo spostate di -1 in U; (2) le WebFetch su pagine `documentation/unreal-engine/...` restano spesso vuote, quelle `documentation/metahuman/...` no; (3) per l'import FBX in UE si usano le opzioni di default (Interchange): l'FBX deve contenere UN oggetto già unito, così nasce una sola Static Mesh
- Lezioni della Fase 7: (1) `bmesh.to_mesh` su una mesh nuova non copia i materiali: vanno riaggiunti; (2) l'armatura importata sta in una collezione esclusa dalla scena: per l'export va inclusa, se no l'FBX esce senza scheletro (e senza pesi); (3) Blender ha trasformato l'osso FBX `root` nell'oggetto armatura `root`: per riaverlo come osso radice in Unreal si esporta con *Armature FBXNode Type = Root*; (4) lo smusso (bevel) di una curva 2D riempita allarga la sagoma di quanto vale: il contorno va stretto prima, e gli angoli raccordati dopo (al contrario, negli angoli rientranti il raccordo si ribalta e lo smusso fa delle punte); (5) mesh alte con vertici doppi sulle cuciture: il ricalcolo delle normali le orienta a pezzi (normal map rovesciata, ombre a zero): saldare prima; (6) spigoli a 90° con vertici condivisi costringono la normal map a forti compensazioni: vertici separati agli spigoli vivi (suola, cinghie); (7) le facce piatte di una cinghia tagliano la pelle tra un vertice e l'altro: controllare tutte e due le diagonali dei quad; (8) per misurare un dito servono le sezioni vere della mesh, scartando quelle che prendono la membrana tra le dita; (9) nel Python di Blender non ci sono scipy e matplotlib: gli script per Nico non le usano; (10) `dict.setdefault(k, crea())` esegue `crea()` a ogni chiamata (in uno script di prova creava migliaia di gruppi di vertici); (11) nella prova delle pose i pesi degli accessori presi dalla stoffa non migliorano nulla rispetto alla pelle: le intersezioni vengono dalle pieghe della gonna
- Lezioni della Fase 7b: (1) clonare i *valori* con PatchMatch e raccordare solo il bordo lascia blocchi visibili dentro la zona (toni e "liscezza" diversi tra toppe vicine): separare tono (membrana) e grana (clonata e riscalata) e scegliere le toppe anche per intensità della grana; (2) cercare le toppe vicino al punto (raggio limitato) mantiene il carattere locale della pelle; (3) nelle tavole, il contorno di una maschera tagliata dal riquadro va disegnato con erosione a bordo replicato, se no compare una cornice finta
