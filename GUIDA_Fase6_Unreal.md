# Fase 6 – Il saio in Unreal Engine 5.8 (senza fisica)

Tempo: circa 45-60 minuti. Lavori nel progetto **Monasterium**, con i file di `Abate_Fase6.zip` estratti in `Desktop\Blender` (cartella `Abate`).

I nomi dei comandi in **grassetto** sono quelli dell'editor in inglese. Li ho presi dalla documentazione Epic per UE 5.8 (link in fondo). Dove c'è scritto *(da verificare)*, la documentazione non lo dice e potresti trovare un nome leggermente diverso.

**L'idea in una frase.** Unreal non usa il saio come una "statua" (Static Mesh). Lo trasforma in un **Cloth Asset**, cioè una stoffa con i pesi presi dal corpo. Poi lo infila in un **Outfit Asset**, il formato dei vestiti MetaHuman che si adatta ai corpi. Infine lo prova sull'abate nel **MetaHuman Creator**.

| Pezzo | Prefisso | Cos'è (analogia) |
|---|---|---|
| Static Mesh | `SM_` | la stoffa tagliata e cucita, ferma sul manichino |
| Cloth Asset | `CA_` | la stessa stoffa "imbastita" sul corpo: sa quali ossa seguire |
| Outfit Asset | `OA_` | l'abito pronto per il guardaroba MetaHuman, che si adatta alla taglia |
| Wardrobe Item | `WI_` | la "gruccia" nel guardaroba: impostazioni, colori, corpo nascosto |

---

## 0. Prima di cominciare (5 min)

1. **Edit > Plugins**: controlla che siano attivi **MetaHuman Creator**, **Chaos Cloth Asset**, **Chaos Cloth Asset Editor** e **Python Editor Script Plugin**. Se ne attivi uno, chiudi e riapri Unreal.
2. **Edit > Project Settings > Plugins > MetaHuman SDK**: il percorso degli Outfits deve essere `/Game/Outfits` (è il valore di default).
3. Salva tutto con **Ctrl+Shift+S**.

## 1. Import automatico (2 min)

1. Nella barra in basso dell'editor, nel campo **Cmd**, scrivi (con il tuo nome utente) e premi Invio:
   `py "C:\Users\GAME2527\Desktop\Blender\Abate\Script\fase6_import_ue.py"`
2. Nell'**Output Log** compaiono righe gialle che iniziano con `[FASE6]`. L'ultima deve dire **ESITO: SUPERATO**. Lo stesso testo finisce in `Abate\Report\ue_fase6_report.txt`.
3. Nel Content Browser, sotto `/Game/Outfits/SaioAbate`, devi trovare:
   - `Mesh`: `SM_SaioAbate_Render` (7.868 triangoli) e `SM_SaioAbate_Fisica` (per la Fase 9, ora non si usa);
   - `Texture`: 5 texture;
   - `Materiali`: `M_SaioAbate_Lana` e `MI_SaioAbate_Lana`.
4. Doppio clic su `SM_SaioAbate_Render`: vedi il saio marrone-grigio con i risvolti chiari. Se è a scacchi o grigio, aspetta che finiscano gli shader (contatore in basso a destra).

## 2. Cloth Asset (10 min)

È il percorso "FBX, solo mesh render" della documentazione Epic.

1. Content Browser, cartella `/Game/Outfits/SaioAbate`: **tasto destro > Physics > Cloth Asset**. Chiamalo `CA_SaioAbate`.
2. Nella finestra **Dataflow Graph** scegli il template **USD Cloth**.
3. Doppio clic su `CA_SaioAbate`: si apre il **Dataflow Editor**. Nella scheda **Graph** cancella tutti i nodi (selezioni, **Canc**) **tranne** questi quattro: **TransferSkinWeights**, **Remesh**, **Remesh_LOD2**, **ClothAssetTerminal**.
4. Aggiungi l'import della mesh:
   - tasto destro nel grafo, cerca **StaticMeshImport** e aggiungilo;
   - in **Node Details** togli la spunta a **Import Sim Mesh** (lascia **Import Render Mesh**);
   - in **Static Mesh** scegli `SM_SaioAbate_Render`.
5. Collega il pin **Collection** di StaticMeshImport al pin **Collection** di **TransferSkinWeights**.
6. Seleziona **TransferSkinWeights** e in **Node Details** imposta:
   - **Target Mesh(es)**: **Render Mesh**
   - **Render Mesh Transfer Source**: **Skeletal Mesh**
   - **Skeletal Mesh**: `MHC_Abate_FullBody` (cartella `SaioAbate/Corpo`, Fase 1)
   - **Transfer Method**: **Closest Point on Surface**
7. Collega **Collection (out)** di TransferSkinWeights a **Collection LODs[0]** di **ClothAssetTerminal**.
8. Prepara i LOD. MetaHuman ne vuole 4 (0-3); i LOD sono versioni più leggere per quando l'abate è lontano. Ogni nodo **Remesh** prende l'uscita di TransferSkinWeights, e il collegamento al LOD 0 resta.
   - Su **Remesh**: togli **Remesh Sim**, metti **Remesh Render**, **Target Percent Render = 50**. Collega l'uscita a **LODs[1]**.
   - Su **Remesh_LOD2**: stesse spunte, **Target Percent Render = 30**. Collega a **LODs[2]**.
   - Copia un Remesh (**Ctrl+C**, **Ctrl+V**) e metti **Target Percent Render = 10**. Collega a **LODs[3]**. Se il terminale non ha il pin, **tasto destro > Add Option Pin**.
9. **Construction Viewport**: nel menu **Display View** (in alto a destra) scegli **Render**, se no non vedi niente. Il saio deve stare sul corpo come in Blender. Salva (**Ctrl+S**).

## 3. Outfit Asset (5 min + calcolo)

1. Cartella `/Game/Outfits/SaioAbate`: **tasto destro > Physics > Outfit Asset**. Chiamalo **`OA_SaioAbate`**: il nome deve corrispondere alla cartella `SaioAbate`.
2. Template: **Resizable Outfit**.
3. Doppio clic su `OA_SaioAbate`. Accanto a **Evaluate Dataflow Graph** clicca i tre puntini e scegli **Manual Graph Evaluation**: così non ricalcola a ogni clic.
4. Pannello **Dataflow Members**: spunta **Sized Outfit Source** e clicca **+** una volta (nasce **Index 0**). Una sola taglia, quella dell'abate.
5. Apri **Index 0** e imposta:
   - **Size Name**: `Abate`
   - **Source Asset**: `CA_SaioAbate`
   - **Source Body Parts**: `MHC_Abate_FullBody`
6. **Num Resizing Interpolation Points**: lascia 1500.
7. Clicca **Evaluate Dataflow Graph** e aspetta la barra di avanzamento (anche qualche minuto). Poi rimetti **Automatic Graph Evaluation** e salva.

## 4. Prova sull'abate nel MetaHuman Creator (10 min)

1. Apri `MHC_Abate` (`/Game/Monasterium/Monasterium/blueprints/MissionHandler`).
2. Strumento **Hair & Clothing**, in fondo la sezione **Outfit Clothing**. Se c'è un vestito indossato, toglilo con **Remove**: ogni posto tiene un capo solo.
3. Trascina **`OA_SaioAbate`** dal Content Browser nella sezione **Outfit Clothing**. Poi doppio clic o **Wear**: la prima volta ci mette un po'.
4. Nel Content Browser è comparso **`WI_SaioAbate`**. Aprilo e imposta:
   - **Principal Asset** = `OA_SaioAbate` (controlla soltanto);
   - **Pipeline** = **MetaHuman Outfit Pipeline**;
   - **Editor Pipeline > Outfit > Body Hidden Face Map** = **`T_Corpo_Nascosto`**. È l'immagine che toglie la pelle sempre coperta dal saio, così il corpo non buca la stoffa;
   - (facoltativo, per cambiare i colori dal Creator) in **Runtime Material Parameters** clicca **+** due volte:
     - indice 0: descrizione `Colore lana`, **Material Parameter** `Tinta_Lana`, **Parameter Type** **Vector**;
     - indice 1: descrizione `Colore risvolto`, **Material Parameter** `Tinta_Risvolto`, **Parameter Type** **Vector**;
     - in **Slot Names** clicca **+** una volta (una taglia).
   - Salva `WI_SaioAbate`.
5. Torna nel Creator e fai **Remove** del saio. Poi trascina **`WI_SaioAbate`** in **Outfit Clothing** e fai **Wear**. Attenzione: da qui in poi trascina il **WI**, mai l'**OA**, altrimenti il Creator sovrascrive il WI con le impostazioni appena fatte.
6. Guarda l'abate da tutti i lati:
   - non deve uscire pelle dalla stoffa;
   - mani, avambracci, polpacci e piedi devono esserci;
   - busto, cosce e braccia alte sono tolti, ma sono sotto il saio quindi non si vedono.

## 5. Assemblare (10 min)

1. Nel Creator apri lo strumento **Assembly**. Scegli la stessa pipeline usata finora per l'abate (per un NPC di solito **UE Optimized**, qualità **Medium** o **High**) e clicca **Assemble**.
2. Salva i nuovi asset.
3. Metti l'abate assemblato in un livello di prova e guardalo.
   - *(da verificare)* Non so come è fatto il tuo `BP_Abate`. Se è il blueprint creato dall'assemblaggio, si aggiorna da solo. Se è un tuo blueprint che contiene il MetaHuman, controlla che usi la versione appena assemblata. Scrivimi com'è fatto e lo sistemiamo insieme.

## Cosa è normale in questa fase

- **La stoffa non si muove da sola.** Segue il corpo come un'armatura morbida. Camminando, la gonna segue le gambe e può tirare in mezzo: lo risolve la fisica della Fase 9.
- Se vedi strappi alle **ascelle** o all'**interno coscia** quando l'abate si muove, Epic suggerisce una mappa **Relax** (nodo **SetSkinningSelection**). Ne parliamo nella Fase 9: prima fammi vedere dove succede.
- Cordone, rosario, sandali, Tau e anello arrivano nella Fase 7.

## Se qualcosa va storto

| Sintomo | Causa probabile | Cosa fare |
|---|---|---|
| `FBX non trovato` o `texture non trovata` nell'Output Log | percorso della cartella diverso | Controlla che `Export`, `Texture` e `Script` siano tutti dentro `Desktop\Blender\Abate` |
| Saio grigio a scacchi | shader in compilazione | Aspetta il contatore in basso a destra |
| Saio nero o rosa | materiale non compilato | Apri `M_SaioAbate_Lana`, clicca **Apply**, mandami uno screenshot degli errori |
| Il Cloth Asset non mostra niente | **Display View** non è su **Render** | Rimettilo su **Render** (Epic avverte che si deseleziona facilmente) |
| Il Cloth Asset dà errori sulla sim mesh | il percorso solo-render non piace a questa versione | Mandami lo screenshot: c'è un piano B con la mesh per la fisica "ferma" |
| La pelle buca il saio in un punto | quel pezzo di corpo non è nella mappa | Dimmi dove: si aggiorna `T_Corpo_Nascosto` |
| L'abate perde un pezzo visibile (es. il gomito) | la mappa toglie troppo | Dimmi dove: si restringe la mappa |

## Fonti (documentazione Epic, UE 5.8)

- Building a MetaHuman Parametric Outfit with an FBX Export: https://dev.epicgames.com/documentation/metahuman/building-a-metahuman-parametric-outfit-with-an-fbx-export
- Create an Outfit Asset: https://dev.epicgames.com/documentation/metahuman/create-a-metahuman-parametric-outfit-asset
- Testing and Configuring your Parametric Outfit Asset: https://dev.epicgames.com/documentation/metahuman/testing-and-configuring-your-parametric-outfit-asset
- Parametric Asset Setup: https://dev.epicgames.com/documentation/metahuman/parametric-asset-setup-for-metahuman
- Assembly: https://dev.epicgames.com/documentation/metahuman/assembly
- TransferSkinWeights (nodo): https://dev.epicgames.com/documentation/unreal-engine/node-reference/Dataflow/TransferSkinWeights
