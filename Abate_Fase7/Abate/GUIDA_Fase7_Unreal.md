# Fase 7 – Gli accessori in Unreal Engine 5.8

Tempo: circa 30-40 minuti. Lavori nel progetto **Monasterium**, dopo aver finito la Fase 6 (`CA_SaioAbate`, `OA_SaioAbate` e `WI_SaioAbate` esistono e funzionano).

I nomi in **grassetto** sono quelli dell'editor in inglese. Dove c'è scritto *(da verificare)*, la documentazione Epic non lo dice e potresti trovare un nome leggermente diverso.

**L'idea in una frase.** Cordone, corona, Tau e sandali ora stanno **dentro la stessa Static Mesh del saio**, con un secondo materiale. Unreal dà loro i pesi con la stessa regola del saio, quindi seguono la stoffa. L'**anello** invece è una piccola **Skeletal Mesh** a parte, tutta sull'osso dell'anulare.

| Pezzo | Dove sta in Unreal | Perché |
|---|---|---|
| Saio, mantellina, cappuccio | `SM_SaioAbate_Render`, materiale 0 (lana) | come nella Fase 6 |
| Cordone, nodi, corona, Tau, sandali | `SM_SaioAbate_Render`, materiale 1 (accessori) | si muovono con la stoffa: niente compenetrazioni tra corda e saio, niente lavoro nei Blueprint |
| Anello | `SKM_AnelloAbate`, Skeletal Mesh sullo scheletro del MetaHuman | tra le dita ci sono 3-4 mm: col trasferimento automatico dei pesi si piegherebbe col dito vicino |

Analogia: l'Outfit è un vestito con gli accessori **cuciti sopra**. L'anello invece si **infila** al dito, quindi va per conto suo.

---

## 0. Prima di cominciare (2 min)

1. Estrai `Abate_Fase7.zip` in `Desktop\Blender`, come le altre fasi. Sovrascrive `Abate\Export\SM_SaioAbate_Render.fbx`: la versione nuova contiene anche gli accessori. Quella vecchia resta dentro `Abate_Fase6.zip`.
2. In Unreal chiudi `MHC_Abate`, se è aperto. Salva tutto con **Ctrl+Shift+S**.

## 1. Import automatico (2 min)

1. Nella barra in basso, campo **Cmd**, scrivi e premi Invio:
   `py "C:\Users\GAME2527\Desktop\Blender\Abate\Script\fase7_import_ue.py"`
2. Nell'**Output Log** l'ultima riga `[FASE7]` deve dire **ESITO: SUPERATO**. Lo stesso testo finisce in `Abate\Report\ue_fase7_report.txt`: mandamelo.
3. Sotto `/Game/Outfits/SaioAbate` trovi:
   - `Texture`: 3 texture nuove, `T_Accessori_BC`, `T_Accessori_N`, `T_Accessori_ORM`;
   - `Materiali`: `M_SaioAbate_Accessori` e `MI_SaioAbate_Accessori`;
   - `Mesh`: `SM_SaioAbate_Render` aggiornata, con **2 materiali**, e la nuova `SKM_AnelloAbate`, una Skeletal Mesh (icona rosa).
4. Doppio clic su `SM_SaioAbate_Render`: vedi il saio con cordone, corona, Tau e sandali.
5. Doppio clic su `SKM_AnelloAbate`: in **Asset Details** la voce **Skeleton** deve essere lo stesso scheletro di `MHC_Abate_FullBody` (`metahuman_base_skel`).

> **Se l'anello non si importa** (riga ERRORE sull'anello, oppure lo scheletro è un altro). Cancella `SKM_AnelloAbate` ed eventuali `..._Skeleton` nuovi nella cartella `Mesh`. Poi trascina `Abate\Export\SKM_AnelloAbate.fbx` dentro la cartella `Mesh` del Content Browser. Nella finestra di import:
> - in **Skeleton** scegli `metahuman_base_skel`;
> - togli la spunta alle animazioni (**Import Animations**) e ai materiali;
> - clicca **Import**.
>
> Poi apri `SKM_AnelloAbate`. In **Asset Details > Material Slots** metti `MI_SaioAbate_Accessori`. *(da verificare: con Interchange le voci della finestra sono raggruppate in sezioni Common Meshes / Skeletal Meshes / Animations)*

## 2. Aggiorna il Cloth Asset (5 min)

Epic dice che dopo aver cambiato la mesh bisogna **ricalcolare il Cloth Asset e salvarlo**, poi **ricalcolare l'Outfit Asset e salvarlo**.

1. Doppio clic su `CA_SaioAbate`: si apre il **Dataflow Editor**.
2. Clicca il nodo **StaticMeshImport**. In **Node Details** il campo **Static Mesh** è già `SM_SaioAbate_Render`. Se il viewport non si aggiorna da solo, scegli di nuovo la stessa mesh nel menu: è il modo più sicuro per fargliela rileggere.
3. **Construction Viewport**, **Display View** = **Render**. Devi vedere saio, cordone, corona, Tau e sandali, tutti nella posizione di Blender. L'anello qui non c'è: è a parte.
4. Il nodo **TransferSkinWeights** non si tocca: dà i pesi anche agli accessori.
5. **LOD.** I nodi Remesh semplificano anche gli accessori (50, 30, 10%). Se nel viewport scegli LOD 1-3 *(menu dei LOD del viewport, da verificare)* e vedi corda o grani "rotti", con punte o buchi, prova così: sui nodi Remesh imposta **Remesh Method Render = Simplify** *(il nodo ha la scelta Remesh/Simplify; secondo la documentazione delle API, Target Percent Render vale con Simplify)*. Da lontano conta poco: se ti sembra a posto, lascia com'è.
6. Salva (**Ctrl+S**).

## 3. Aggiorna l'Outfit Asset (5 min + calcolo)

1. Doppio clic su `OA_SaioAbate`.
2. Clicca **Evaluate Dataflow Graph** e aspetta la barra di avanzamento.
3. Salva.

## 4. Prova sull'abate nel MetaHuman Creator (10 min)

1. Apri `MHC_Abate`, strumento **Hair & Clothing**, sezione **Outfit Clothing**.
2. Se il saio indossato non mostra gli accessori, fai **Remove**. Poi trascina **`WI_SaioAbate`** (il WI, non l'OA) e fai **Wear**. Così restano la Body Hidden Face Map e i colori della Fase 6.
3. Guarda l'abate da tutti i lati:
   - cordone stretto in vita, nodo e coda con 3 nodi sul **suo** fianco destro;
   - corona sul suo fianco sinistro, con la crocetta in fondo;
   - Tau sul petto, appoggiato alla mantellina, col cordino che sparisce sotto il collo arrotolato;
   - sandali ai piedi.
4. **Le suole scendono 1,3 cm sotto il pavimento.** È voluto. I piedi del MetaHuman toccano terra, e la suola non può stare dentro il piede. Epic avverte che da UE 5.6 le suole delle calzature finiscono sotto il piano. Lo sistemiamo nella Fase 8, alzando il personaggio di 1,3 cm nel Blueprint.
5. **L'anello.** Nel guardaroba cerca la sezione che accetta le **Skeletal Mesh** *(Epic la chiama slot "SkeletalMesh"; il nome che vedi nell'interfaccia è da verificare)*. Trascinaci `SKM_AnelloAbate` e fai **Wear**.
   - Se dà un avviso di validazione, il **Message Log** dice il motivo: mandami uno screenshot.
   - Epic permette di spegnere i controlli solo per il tuo progetto: **Project Settings > Wardrobe > Enable Wardrobe Item Validation** *(da verificare la posizione esatta)*. Fallo solo se te lo dico io dopo aver visto l'errore.
   - Se nessuna sezione accetta l'anello, nessun problema: nella Fase 8 lo attacchiamo nel Blueprint.
6. Colore degli accessori: apri `MI_SaioAbate_Accessori` e cambia **Tinta_Accessori**. Tinge tutti gli accessori insieme, quindi usalo con delicatezza.

## 5. Assemblare di nuovo (se ti serve già l'abate assemblato)

**Assembly** > stessa pipeline della Fase 6 > **Assemble** > salva.

## Cosa è normale in questa fase

- **Coda e corona non oscillano.** Seguono la gonna come se ci fossero cucite sopra. È il prezzo di zero compenetrazioni con il saio. Con la fisica della Fase 9 si muoveranno insieme alla stoffa.
- **Una parte del nodo in vita passa dietro il cordone, dentro la piega della lana.** Da fuori non si vede (è dietro il cordone, dentro la stoffa).
- **Il filo della corona entra nei grani**, come nei fori di una corona vera.
- **Gli accessori hanno il loro materiale** (un lato solo, come oggetti pieni). La lana resta Two Sided.

## Se qualcosa va storto

| Sintomo | Causa probabile | Cosa fare |
|---|---|---|
| `FBX non trovato`, `texture non trovata` o `manca attesi_fase7.json` | zip non estratto nella cartella giusta | Controlla che `Export`, `Texture`, `Script` stiano tutti dentro `Desktop\Blender\Abate` |
| `SM_SaioAbate_Render` ha un solo materiale | è ancora l'FBX della Fase 6 | Estrai di nuovo lo zip della Fase 7 e rilancia lo script |
| Accessori neri, rosa o a scacchi | materiale non compilato o non assegnato | Apri `SM_SaioAbate_Render`: materiale 1 = `MI_SaioAbate_Accessori`; aspetta gli shader |
| Nel Cloth Asset non vedi gli accessori | la mesh non è stata riletta | **Display View** = **Render**; nel nodo StaticMeshImport scegli di nuovo `SM_SaioAbate_Render` |
| L'anello è lontano dal dito o enorme | importato su un altro scheletro | Rifai l'import a mano (riquadro del passo 1) scegliendo `metahuman_base_skel` |
| Un accessorio si piega in modo strano quando l'abate si muove | pesi presi dal punto sbagliato del corpo | Dimmi quale e in che posa: si corregge in Blender |

## Fonti (documentazione Epic)

- Building a MetaHuman Parametric Outfit with an FBX Export (ricalcolare Cloth Asset e Outfit dopo una modifica): https://dev.epicgames.com/documentation/metahuman/building-a-metahuman-parametric-outfit-with-an-fbx-export
- Hair and Clothing Tools (guardaroba, slot SkeletalMesh, validazione): https://dev.epicgames.com/documentation/metahuman/hair-and-clothing-tools
- Tailoring your own Wardrobe Items (vestiti parametrici o Skeletal Mesh a taglia fissa): https://dev.epicgames.com/documentation/metahuman/tailoring-your-own-wardrobe-items
- Nodo Remesh del Cloth Asset (API): https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/ChaosClothAssetDataflowNodes/FChaosClothAssetRemeshNode_v2
- Opzioni di import Interchange da Python (scheletro esistente): https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/InterchangeGenericCommonSkeletalMeshesAndAnimationsProperties
