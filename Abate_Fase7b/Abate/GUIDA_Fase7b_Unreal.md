# Fase 7b – Pelle della testa senza canottiera, in Unreal (10 minuti)

Le 8 texture ritoccate hanno **gli stessi nomi** di quelle dell'abate. Le sostituisci "dentro la stessa cornice": i materiali della testa non si toccano e vedono subito la pelle nuova. Impostazioni come sRGB, compressione e Virtual Texture restano quelle di prima.

## 0. Prima di cominciare
1. Estrai `Abate_Fase7b.zip` in `Desktop\Blender`. Le texture finiscono in `Abate\Texture\PelleTesta_Fase7b`.
2. Tieni da parte lo zip con le texture originali che avevi esportato (`T_Head.zip`): serve per tornare indietro. Una copia ce l'ho anch'io nel cloud.
3. In Unreal salva tutto (**Ctrl+Shift+S**). Se usi la repository, fai un commit adesso.

## 1. Reimport (8 volte)
Nel Content Browser vai nella cartella delle texture della testa dell'abate assemblato. È quella da cui le avevi esportate.

Per **ognuna** di queste texture:

| Texture in Unreal | File da scegliere (`Abate\Texture\PelleTesta_Fase7b\`) |
|---|---|
| `T_Head_LOD3_BC_VT` | `T_Head_LOD3_BC_VT.PNG` |
| `T_Head_LOD3_N_VT` | `T_Head_LOD3_N_VT.PNG` |
| `T_Head_LOD3_SRMF_VT` | `T_Head_LOD3_SRMF_VT.PNG` |
| `T_Head_LOD3_Scatter_VT` | `T_Head_LOD3_Scatter_VT.PNG` |
| `T_Head_LOD5to7_BC_VT` | `T_Head_LOD5to7_BC_VT.PNG` |
| `T_Head_LOD5to7_N_VT` | `T_Head_LOD5to7_N_VT.PNG` |
| `T_Head_LOD5to7_SRMF` | `T_Head_LOD5to7_SRMF.PNG` |
| `T_Head_LOD5to7_Scatter_VT` | `T_Head_LOD5to7_Scatter_VT.PNG` |

1. Clic destro sulla texture > **Reimport With New File** *(nome da verificare in UE 5.8: può stare anche sotto **Asset Actions**)*.
2. Scegli il file corrispondente, poi **Apri**.
3. Se compare una finestra di opzioni d'import, lascia tutto com'è e conferma.

Alla fine: **Ctrl+Shift+S**.

## 2. Controllo
1. Doppio clic su `T_Head_LOD3_BC_VT`: in basso, al centro dell'immagine, non devono più esserci le due spalline grigie.
2. In **Details** controlla che **Compression Settings**, **sRGB** e **Virtual Texture Streaming** siano uguali a prima.
3. Guarda l'abate nella scena da vicino, con **Lumen acceso**, dentro lo scollo e dall'alto. Mandami uno screenshot.

## Se qualcosa va storto

| Sintomo | Cosa fare |
|---|---|
| Collo nero, rosa o a scacchi | Aspetta la compilazione degli shader. Se resta, controlla che la texture sia ancora **Virtual Texture Streaming** come prima |
| Rilievi strani sulla pelle | Hai scambiato una normal map (`_N_`) con un'altra texture: rifai il reimport col file giusto |
| Vuoi tornare indietro | **Reimport With New File** con i PNG originali del tuo `T_Head.zip` |
| Hai riassemblato l'abate nel Creator | Le texture tornano quelle con la canottiera: rifai questi 8 reimport |
