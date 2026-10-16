# =============================================================================
#  FASE 5 - UV E MAPPE DELLA LANA (normal map, ombre d'ambiente, maschere)
#  Progetto: Abate francescano  (MetaHuman UE 5.8  ->  Blender 5.2  ->  UE 5.8)
#
#  COSA FA
#   1. UV della mesh di gioco: saio + mantellina + cappuccio in UNA sola texture
#      2K (un solo materiale lana). Le cuciture sono quelle della Fase 2 (dove
#      starebbero quelle vere) piu' un taglio per ogni bordino ad anello.
#      Ogni pezzo viene steso come un cartamodello, girato col FILO della lana in
#      verticale (maniche: lungo il braccio), portato alla stessa scala degli
#      altri e impacchettato senza sovrapposizioni, con 16 pixel tra i pezzi.
#   2. UV della mesh per la fisica: gli stessi pezzi in SCALA REALE (1 = 1 cm):
#      in Unreal diventano i "pattern 2D" di Chaos Cloth.
#   3. Cuoce dal drappeggio alto (Fase 3) sulla mesh di gioco tre texture 2K:
#      - T_Lana_N        normal map (convenzione DirectX = quella di Unreal):
#                        le pieghe minute che la mesh di gioco non ha;
#      - T_Lana_AO       ombre d'ambiente: R = lato "dritto" (quello verso cui
#                        puntano le normali), G = lato "rovescio";
#      - T_Lana_Maschere R = risvolto chiaro, G = bordi (usura),
#                        B = vicino all'orlo (polvere e fango).
#   4. Materiale di anteprima in Blender, controlli, rapporto; salva
#      Saio_Abate_v005.blend (il v004 resta intatto) e le texture in Texture/.
#
#  PRIMA DI LANCIARLO
#   - Apri Saio_Abate_v004.blend (quello della Fase 4), gia' salvato su disco:
#     le texture vengono scritte nella cartella "Texture" accanto al file.
#  COME SI LANCIA
#   - Workspace "Scripting" > Text > Open > questo file > Run Script (Alt+P).
#     Ci mette alcuni minuti (la cottura delle ombre e' la parte lunga):
#     Blender sembra bloccato, ma lavora. I progressi si leggono in
#     Window > Toggle System Console.
#
#  PERCHE' COSI' (compatibilita' con tutti i MetaHuman)
#   - Le UV sono il canale 0, l'unico che il materiale usa. Per le "taglie"
#     (Fase 5b) le UV NON si rifanno: si copiano da questo file (stessa
#     topologia), cosi' le stesse texture vanno bene per tutte le taglie.
#   - La mesh di gioco riceve un modificatore "Triangola_per_UE" (metodo fisso):
#     l'export FBX (Fase 6) usera' esattamente gli stessi triangoli su cui e'
#     stata cotta la normal map, e con il metodo fisso sono gli stessi in tutte
#     le taglie.
#   - Le ombre hanno due canali perche' la stoffa e' a uno strato con materiale
#     "Two Sided": in Unreal il nodo TwoSidedSign sceglie R (davanti) o G (dietro),
#     cosi' l'interno della tonaca e delle maniche e' scuro anche se e' la stessa
#     superficie.
# =============================================================================

import bpy
import bmesh
import math
import os
import time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

CM = 0.01   # 1 cm in unita' Blender (metri)

# ----------------------------- PARAMETRI -------------------------------------
P = dict(
    RISOLUZIONE=2048,      # px delle texture finali
    SOVRACAMPIONA=2,       # cuoce a 2048 x 2 = 4096 e riduce: bordi e pieghe piu' puliti
    MARGINE_PX=16,         # px di spazio tra i pezzi (a 2048): regge le mip map lontane
                           #   (Blender lascia meta' margine attorno a ogni pezzo)
    CAMPIONI_AO=32,        # campioni per pixel delle ombre (a 4096 = 128 a 2048)
    DISTANZA_AO=10.0,      # cm: fin dove l'ombra d'ambiente "sente" gli ostacoli
    SFOCA_AO=1.0,          # px (a 2048): sfocatura leggera che toglie il rumore delle ombre
    BORDI_CM=6.0,          # maschera usura: 1 sul bordo, 0 a questa distanza (cm)
    ORLO_FINO_A=45.0,      # maschera polvere: 1 all'orlo, 0 a questa altezza da terra (cm)
    ESTRUSIONE_MIN=0.3,    # cm: "gabbia" minima della cottura (vedi cuoci_tutto)
    MAX_INCLINAZIONE=60.0, # gradi: tetto all'inclinazione della normal map (sotto le ascelle
                           #   la stoffa alta e' raggrinzita e darebbe macchie scure)
)

NOMI = dict(saio="Saio_Gioco", mant="Mantellina_Gioco", saio_f="Saio_Fisica", mant_f="Mantellina_Fisica",
            saio_a="Saio_Drappeggio", mant_a="Mantellina_Drappeggio")
NOME_FILE_V5 = "Saio_Abate_v005.blend"
CARTELLA_TEX = "Texture"
UV = "UVMap"
TEX = dict(N="T_Lana_N", AO="T_Lana_AO", M="T_Lana_Maschere")
report = []


def log(riga=""):
    print(riga, flush=True)
    report.append(riga)


# =============================================================================
#  UTILITA'
# =============================================================================
def layer_collection(nome, lc=None):
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.name == nome:
        return lc
    for figlio in lc.children:
        t = layer_collection(nome, figlio)
        if t:
            return t
    return None


def coordinate(obj):
    co = np.zeros(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(obj.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def pesi_gruppo(obj, nome):
    g = obj.vertex_groups.get(nome)
    w = np.zeros(len(obj.data.vertices))
    if g is None:
        return w
    for v in obj.data.vertices:
        for gg in v.groups:
            if gg.group == g.index:
                w[v.index] = gg.weight
    return w


def attributo_facce(me, nome):
    a = me.attributes.get(nome)
    x = np.zeros(len(me.polygons))
    if a is not None:
        a.data.foreach_get("value", x)
    return x


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def modo_oggetto():
    if bpy.context.object is not None and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def seleziona(attivo, altri=()):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in list(altri) + [attivo]:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = attivo


def dati_uv(me):
    """UV per angolo (loop), vertice di ogni loop, faccia di ogni loop."""
    nl = len(me.loops)
    uv = np.zeros(nl * 2)
    me.uv_layers[UV].data.foreach_get("uv", uv)
    lv = np.zeros(nl, int)
    me.loops.foreach_get("vertex_index", lv)
    lt = np.zeros(len(me.polygons), int)
    me.polygons.foreach_get("loop_total", lt)
    ls = np.zeros(len(me.polygons), int)
    me.polygons.foreach_get("loop_start", ls)
    return uv.reshape(-1, 2), lv, ls, lt


def triangoli_loop(ls, lt):
    """Triangoli (a ventaglio) in indici di loop, con la faccia di provenienza."""
    T, F = [], []
    for f, (s, n) in enumerate(zip(ls, lt)):
        for k in range(1, n - 1):
            T.append((s, s + k, s + k + 1))
            F.append(f)
    return np.array(T), np.array(F)


def aree_tri(uv, co, lv, T):
    a2 = uv[T[:, 1]] - uv[T[:, 0]]
    b2 = uv[T[:, 2]] - uv[T[:, 0]]
    auv = 0.5 * (a2[:, 0] * b2[:, 1] - a2[:, 1] * b2[:, 0])
    a3 = co[lv[T[:, 1]]] - co[lv[T[:, 0]]]
    b3 = co[lv[T[:, 2]]] - co[lv[T[:, 0]]]
    a3d = 0.5 * np.linalg.norm(np.cross(a3, b3), axis=1)
    return auv, a3d


def isole_facce(me):
    """Isola di ogni faccia: gruppi di facce non separati da cuciture."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    isola = np.full(len(bm.faces), -1)
    k = 0
    for f in bm.faces:
        if isola[f.index] >= 0:
            continue
        pila = [f]
        isola[f.index] = k
        while pila:
            x = pila.pop()
            for e in x.edges:
                if e.seam:
                    continue
                for g in e.link_faces:
                    if isola[g.index] < 0:
                        isola[g.index] = k
                        pila.append(g)
        k += 1
    bm.free()
    return isola, k


# =============================================================================
#  1. TAGLI DEI BORDINI
# =============================================================================
def taglia_bordini(obj, n_tessuto):
    """I bordini della Fase 4 (spessore della lana) sono anelli chiusi: un anello
    non si stende piatto senza tagliarlo. Si taglia dove arriva una cucitura del
    tessuto (fianchi, sotto-manica, centro dietro): li' il taglio c'e' gia'."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    nuovi = [v for v in bm.verts if v.index >= n_tessuto]       # vertici del bordino
    kd = KDTree(len(nuovi))
    for i, v in enumerate(nuovi):
        kd.insert(v.co, i)
    kd.balance()
    tagli = 0
    for v in bm.verts[:n_tessuto]:
        verso_interno = [e for e in v.link_edges if e.other_vert(v).index >= n_tessuto]
        if not verso_interno:
            continue                                            # non e' sul bordo libero
        vi = verso_interno[0].other_vert(v)
        for e in v.link_edges:
            q = e.other_vert(v)
            if q.index >= n_tessuto or not e.seam:
                continue
            if any(any(x.index >= n_tessuto for x in f.verts) for f in e.link_faces):
                continue                                        # e' il bordo stesso, non una cucitura
            co, j, d = kd.find(q.co)
            lato = bm.edges.get((vi, nuovi[j]))
            if lato is None or d > 0.6 * CM:
                raise RuntimeError(f"{obj.name}: taglio del bordino non trovato")
            verso_interno[0].seam = True
            lato.seam = True
            tagli += 1
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return tagli


# =============================================================================
#  2. UV DELLA MESH DI GIOCO
# =============================================================================
def braccio(lato):
    """Direzione spalla -> mano (dallo scheletro del MetaHuman)."""
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE' and f"upperarm_{lato}" in o.data.bones), None)
    if arm is None:
        d = np.array((0.3076, -0.1629, -0.3888))
        if lato == "r":
            d[0] = -d[0]
    else:
        a = arm.matrix_world @ arm.data.bones[f"upperarm_{lato}"].head_local
        b = arm.matrix_world @ arm.data.bones[f"hand_{lato}"].head_local
        d = np.array(b - a)
    return d / np.linalg.norm(d)


def classifica(obj, isola, k, n_tessuto):
    """Nome e tipo di ogni pezzo (serve per il filo, per la cottura e per le tavole)."""
    me = obj.data
    co = coordinate(obj)
    bordo = attributo_facce(me, "bordo")
    chiaro = attributo_facce(me, "chiaro")
    lato = pesi_gruppo(obj, "Lato_Cappuccio")
    saio = obj.name == NOMI["saio"]
    pezzi = []
    for i in range(k):
        fi = np.where(isola == i)[0]
        vi = np.unique(np.concatenate([list(me.polygons[f].vertices) for f in fi]))
        c = co[vi].mean(0)
        vt = vi[vi < n_tessuto]
        if bordo[fi].mean() > 0.5:
            tipo = "bordino"
            if saio:
                nome = ("Bordino orlo " + ("dietro" if c[1] > 0 else "davanti")) if c[2] < 0.5 else \
                       ("Bordino polsino " + ("sinistro" if c[0] > 0 else "destro"))
            else:
                nome = "Bordino cappuccio" if lato[vt].mean() > 0.5 else "Bordino mantellina"
        elif saio:
            if abs(c[0]) > 0.2:
                tipo = "risvolto" if chiaro[fi].mean() > 0.5 else "manica"
                nome = ("Risvolto " if tipo == "risvolto" else "Manica ") + ("sinistro" if c[0] > 0 else "destro")
                if tipo == "manica":
                    nome = nome.replace("sinistro", "sinistra").replace("destro", "destra")
            elif co[vi, 2].max() < 0.3:
                tipo, nome = "balza", "Balza " + ("dietro" if c[1] > 0 else "davanti")
            else:
                tipo, nome = "pannello", ("Dietro" if c[1] > 0 else "Davanti")
        else:
            if lato[vi].mean() > 0.5:
                tipo, nome = "cappuccio", "Cappuccio e collo"
            else:
                tipo, nome = "mantellina", "Mantellina"
        pezzi.append(dict(i=i, tipo=tipo, nome=nome, lato_x=float(np.sign(c[0]))))
    return pezzi


def triangolata(o, nome, coll):
    """Copia della mesh divisa in triangoli col metodo FISSO (ogni quad tagliato tra
    il primo e il terzo vertice): sono gli stessi triangoli che andranno in Unreal."""
    m = o.modifiers.new("TEMP_tri", 'TRIANGULATE')
    m.quad_method = 'FIXED'
    m.ngon_method = 'BEAUTY'
    m.min_vertices = 4
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    o.modifiers.remove(m)
    if len(me.vertices) != len(o.data.vertices):
        raise RuntimeError("copia triangolata diversa dall'originale")
    ob = bpy.data.objects.new(nome, me)
    coll.objects.link(ob)
    ob.matrix_world = o.matrix_world.copy()
    return ob


def faccia_di_ogni_triangolo(me, mt):
    """Per ogni triangolo della copia, il quad da cui viene."""
    chiave = {}
    for p in me.polygons:
        vs = list(p.vertices)
        for k in range(1, len(vs) - 1):
            chiave[frozenset((vs[0], vs[k], vs[k + 1]))] = p.index
    return [chiave[frozenset(t.vertices)] for t in mt.polygons]


def stendi(oggetti):
    """Stende i pezzi (unwrap 'Minimum Stretch': il metodo che stira meno la stoffa).
    Si stende la copia a TRIANGOLI (gli stessi dell'export): stendendo i quad,
    Blender li divide a modo suo e qualche triangolo nostro (sotto le ascelle,
    dove la stoffa e' raggrinzita) restava capovolto."""
    modo_oggetto()
    coll = bpy.context.scene.collection
    copie = [triangolata(o, "TEMP_stendi_" + o.name, coll) for o in oggetti]
    try:
        seleziona(copie[0], copie[1:])
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.unwrap(method='MINIMUM_STRETCH', fill_holes=True, correct_aspect=True, use_subsurf_data=False,
                          margin_method='ADD', margin=0.0, no_flip=True, iterations=40, use_weights=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        for o, c in zip(oggetti, copie):                 # UV dei triangoli -> angoli dei quad
            me, mt = o.data, c.data
            uvt = np.zeros(len(mt.loops) * 2)
            mt.uv_layers[UV].data.foreach_get("uv", uvt)
            uvt = uvt.reshape(-1, 2)
            uvq = np.zeros((len(me.loops), 2))
            fatto = np.zeros(len(me.loops), bool)
            for t, f in zip(mt.polygons, faccia_di_ogni_triangolo(me, mt)):
                p = me.polygons[f]
                pos = {v: p.loop_start + k for k, v in enumerate(p.vertices)}
                for li in t.loop_indices:
                    j = pos[mt.loops[li].vertex_index]
                    uvq[j] = uvt[li]
                    fatto[j] = True
            if not fatto.all():
                raise RuntimeError(f"{o.name}: UV non trasferite su tutti gli angoli")
            me.uv_layers[UV].data.foreach_set("uv", uvq.ravel())
            me.update()
    finally:
        modo_oggetto()
        for c in copie:
            me = c.data
            bpy.data.objects.remove(c, do_unlink=True)
            bpy.data.meshes.remove(me)


def orienta_e_scala(obj, isola, pezzi):
    """Filo della lana verticale (+V = verso l'alto; maniche: verso la spalla),
    bordini distesi in orizzontale, ogni pezzo alla sua misura vera (metri)."""
    me = obj.data
    uv, lv, ls, lt = dati_uv(me)
    co = coordinate(obj)
    fl = np.repeat(np.arange(len(me.polygons)), lt)
    T, TF = triangoli_loop(ls, lt)
    auv, a3d = aree_tri(uv, co, lv, T)
    righe = []
    for p in pezzi:
        L = np.where(isola[fl] == p["i"])[0]
        ti = isola[TF] == p["i"]
        m0 = uv[L].mean(0)
        if p["tipo"] == "bordino":
            D = uv[L] - m0
            w, V = np.linalg.eigh(D.T @ D)
            ang = -math.atan2(V[1, 1], V[0, 1])              # asse lungo -> U
        else:
            if p["tipo"] in ("manica", "risvolto"):
                f = -(co[lv[L]] @ braccio("l" if p["lato_x"] > 0 else "r"))
            else:
                f = co[lv[L], 2]
            g = np.linalg.lstsq(np.c_[uv[L], np.ones(len(L))], f, rcond=None)[0][:2]
            ang = math.pi / 2 - math.atan2(g[1], g[0])        # gradiente -> +V
        c, s = math.cos(ang), math.sin(ang)
        scala = math.sqrt(a3d[ti].sum() / max(np.abs(auv[ti]).sum(), 1e-12))
        R = np.array([[c, -s], [s, c]]) * scala
        uv[L] = (uv[L] - m0) @ R.T
        righe.append((p["nome"], math.degrees(ang) % 360))
    me.uv_layers[UV].data.foreach_set("uv", uv.ravel())
    me.update()
    return righe


def impacchetta(oggetti, info_isole):
    """Impacchetta i pezzi nel quadrato senza ruotarli (il filo resta verticale).
    Un pezzo girato di 180 gradi ha ancora il filo verticale e a volte si incastra
    meglio: si prova a girare i pezzi grandi uno alla volta e si tiene il giro
    solo se la texture viene sfruttata di piu' (sempre le stesse prove, quindi
    sempre lo stesso risultato)."""
    originali = {}
    for o in oggetti:
        uv = np.zeros(len(o.data.loops) * 2)
        o.data.uv_layers[UV].data.foreach_get("uv", uv)
        lt = np.zeros(len(o.data.polygons), int)
        o.data.polygons.foreach_get("loop_total", lt)
        originali[o.name] = (uv.reshape(-1, 2), np.repeat(np.arange(len(o.data.polygons)), lt))

    def prova(girati):
        modo_oggetto()
        for o in oggetti:
            uv, fl = originali[o.name]
            uv = uv.copy()
            isola = info_isole[o.name][0]
            for nome_o, i in girati:
                if nome_o == o.name:
                    L = isola[fl] == i
                    uv[L] = 2 * uv[L].mean(0) - uv[L]            # 180 gradi
            o.data.uv_layers[UV].data.foreach_set("uv", uv.ravel())
            o.data.update()
        seleziona(oggetti[0], oggetti[1:])
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=False, scale=True, merge_overlap=False,
                                margin_method='FRACTION', margin=0.5 * P["MARGINE_PX"] / P["RISOLUZIONE"],
                                pin=False, shape_method='CONCAVE')
        bpy.ops.object.mode_set(mode='OBJECT')
        return densita(oggetti)[1]

    candidati = [(o.name, p["i"], p["nome"]) for o in oggetti for p in info_isole[o.name][1]
                 if p["tipo"] in ("pannello", "manica", "mantellina", "cappuccio")]
    girati = []
    migliore = prova(girati)
    for nome_o, i, nome in candidati:
        x = prova(girati + [(nome_o, i)])
        if x > migliore * 1.002:
            girati.append((nome_o, i))
            migliore = x
    prova(girati)
    return [n for o_, i, n in candidati if (o_, i) in girati], migliore


def densita(oggetti):
    """Unita' UV per metro (uguale per tutti i pezzi dopo orienta_e_scala)."""
    tot_uv = tot_3d = 0.0
    for o in oggetti:
        uv, lv, ls, lt = dati_uv(o.data)
        T, _ = triangoli_loop(ls, lt)
        auv, a3d = aree_tri(uv, coordinate(o), lv, T)
        tot_uv += np.abs(auv).sum()
        tot_3d += a3d.sum()
    return math.sqrt(tot_uv / tot_3d), tot_uv


def uv_fisica(gioco, fisica, K):
    """Le facce della mesh per la fisica sono le prime della mesh di gioco (Fase 4):
    stesse UV, ma in centimetri veri."""
    uv, lv, ls, lt = dati_uv(gioco.data)
    me = fisica.data
    lvf = np.zeros(len(me.loops), int)
    me.loops.foreach_get("vertex_index", lvf)
    if len(lvf) > len(lv) or not np.array_equal(lvf, lv[:len(lvf)]):
        raise RuntimeError(f"{fisica.name}: non ha le stesse facce di {gioco.name}")
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name=UV)
    me.uv_layers[UV].data.foreach_set("uv", (uv[:len(lvf)] * (100.0 / K)).ravel())
    me.update()
    return uv[:len(lvf)] * (100.0 / K)


# =============================================================================
#  3. CONTROLLI DELLE UV
# =============================================================================
def rasterizza(tri, res):
    """Quanti triangoli coprono il centro di ogni pixel (per trovare sovrapposizioni)."""
    cnt = np.zeros((res, res), np.uint8)
    for a, b, c in tri * res:
        x0 = max(int(math.floor(min(a[0], b[0], c[0]) - 0.5)), 0)
        x1 = min(int(math.ceil(max(a[0], b[0], c[0]) - 0.5)), res - 1)
        y0 = max(int(math.floor(min(a[1], b[1], c[1]) - 0.5)), 0)
        y1 = min(int(math.ceil(max(a[1], b[1], c[1]) - 0.5)), res - 1)
        if x1 < x0 or y1 < y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = (b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0])
        w1 = (c[0] - b[0]) * (Y - b[1]) - (c[1] - b[1]) * (X - b[0])
        w2 = (a[0] - c[0]) * (Y - c[1]) - (a[1] - c[1]) * (X - c[0])
        dentro = ((w0 > 0) & (w1 > 0) & (w2 > 0)) | ((w0 < 0) & (w1 < 0) & (w2 < 0))
        cnt[y0:y1 + 1, x0:x1 + 1] += dentro.astype(np.uint8)
    return cnt


def distanza_punti_segmenti(Pt, A, B):
    AB = B - A
    t = np.clip(((Pt[:, None, :] - A[None]) * AB[None]).sum(-1) / np.maximum((AB * AB).sum(-1), 1e-20)[None], 0, 1)
    Q = A[None] + t[..., None] * AB[None]
    return np.sqrt(((Pt[:, None, :] - Q) ** 2).sum(-1)).min()


def controlli_uv(oggetti, info_isole, K):
    res = P["RISOLUZIONE"]
    ok = True
    tutti_tri, contorni = [], []
    stat = []
    for o in oggetti:
        me = o.data
        isola, pezzi = info_isole[o.name]
        uv, lv, ls, lt = dati_uv(me)
        co = coordinate(o)
        T, TF = triangoli_loop(ls, lt)
        tutti_tri.append(uv[T])
        auv, a3d = aree_tri(uv, co, lv, T)
        # distorsione: valori singolari della mappa 3D -> UV di ogni triangolo
        e1 = co[lv[T[:, 1]]] - co[lv[T[:, 0]]]
        e2 = co[lv[T[:, 2]]] - co[lv[T[:, 0]]]
        n1 = e1 / np.linalg.norm(e1, axis=1)[:, None]
        n2 = np.cross(np.cross(e1, e2), e1)
        n2 /= np.maximum(np.linalg.norm(n2, axis=1)[:, None], 1e-12)
        p1 = np.c_[(e1 * n1).sum(1), (e1 * n2).sum(1)]
        p2 = np.c_[(e2 * n1).sum(1), (e2 * n2).sum(1)]
        q1 = uv[T[:, 1]] - uv[T[:, 0]]
        q2 = uv[T[:, 2]] - uv[T[:, 0]]
        Pm = np.stack([p1, p2], axis=2)                      # colonne = lati in 3D (piano)
        Qm = np.stack([q1, q2], axis=2)                      # colonne = lati in UV
        J = Qm @ np.linalg.inv(Pm) / K                       # 1 = misura vera
        sv = np.linalg.svd(J, compute_uv=False)
        stat.append((a3d, sv, auv))
        # pezzi rovesciati (triangoli girati al contrario)
        girati = 0
        for p in pezzi:
            ti = isola[TF] == p["i"]
            s = np.sign(auv[ti])
            girati += int(min((s > 0).sum(), (s < 0).sum()))
        if girati:
            ok = False
        log(f"    {o.name}: {len(pezzi)} pezzi, triangoli capovolti {girati}")
        # contorno di ogni pezzo (lati su cucitura o bordo) per misurare gli spazi
        bm = bmesh.new()
        bm.from_mesh(me)
        uvl = bm.loops.layers.uv[UV]
        bm.faces.ensure_lookup_table()
        seg = {}
        for f in bm.faces:
            for l in f.loops:
                if l.edge.seam or l.edge.is_boundary:
                    seg.setdefault(isola[f.index], []).append((l[uvl].uv[:], l.link_loop_next[uvl].uv[:]))
        bm.free()
        for i, s in seg.items():
            s = np.array(s)
            contorni.append((o.name, i, s[:, 0, :], s[:, 1, :]))
    # sovrapposizioni
    tri = np.concatenate(tutti_tri)
    cnt = rasterizza(tri, res)
    sovrap = int((cnt > 1).sum())
    copertura = (cnt > 0).mean() * 100
    fuori = int(((tri < 0) | (tri > 1)).any(axis=(1, 2)).sum())
    ok &= sovrap == 0 and fuori == 0
    # spazio minimo tra i pezzi (in pixel a 2048)
    minimo = 1e9
    for a in range(len(contorni)):
        for b in range(a + 1, len(contorni)):
            _, _, A0, A1 = contorni[a]
            _, _, B0, B1 = contorni[b]
            d = min(distanza_punti_segmenti(A0, B0, B1), distanza_punti_segmenti(B0, A0, A1))
            minimo = min(minimo, d)
    minimo_px = minimo * res
    ok &= minimo_px >= P["MARGINE_PX"] - 0.5
    # distorsione complessiva (pesata per area)
    a3d = np.concatenate([s[0] for s in stat])
    sv = np.concatenate([s[1] for s in stat])
    area_r = sv[:, 0] * sv[:, 1]
    aniso = sv[:, 0] / np.maximum(sv[:, 1], 1e-9)
    def quota(maschera):
        return a3d[maschera].sum() / a3d.sum() * 100
    log(f"    Sovrapposizioni: {sovrap} pixel; UV fuori dal quadrato: {fuori} triangoli; "
        f"spazio minimo tra i pezzi {minimo_px:.1f} px (a {res})")
    log(f"    Texture usata {copertura:.1f}%; densita' {K * res / 100:.2f} px/cm "
        f"(1 pixel = {100 / (K * res) * 10:.2f} mm); 1 UV = {100 / K:.1f} cm")
    log(f"    Stiramento: area entro +/-10% sul {quota(np.abs(area_r - 1) <= 0.10):.1f}% della stoffa, "
        f"entro +/-20% sul {quota(np.abs(area_r - 1) <= 0.20):.1f}%; forma (rapporto dei lati) "
        f"entro 1,15 sul {quota(aniso <= 1.15):.1f}%, peggiore {aniso.max():.2f}")
    return ok, dict(sovrap=sovrap, copertura=copertura, minimo_px=minimo_px, densita=K * res / 100)


# =============================================================================
#  4. MASCHERE PER VERTICE (bordi, orlo)
# =============================================================================
def maschere_vertici(obj, n_tessuto):
    """G = vicino ai bordi liberi (usura), B = vicino all'orlo (polvere, fango)."""
    me = obj.data
    co = coordinate(obj)
    nv = len(me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    sorgenti = set()
    for v in bm.verts[:n_tessuto]:
        if v.is_boundary or any(e.other_vert(v).index >= n_tessuto for e in v.link_edges):
            sorgenti.add(v.index)                 # orlo, polsini, bordi della mantellina, scollo
    # distanza lungo la stoffa (Dijkstra sui lati del tessuto)
    import heapq
    dist = np.full(nv, np.inf)
    coda = [(0.0, i) for i in sorted(sorgenti)]
    for _, i in coda:
        dist[i] = 0.0
    heapq.heapify(coda)
    while coda:
        d, i = heapq.heappop(coda)
        if d > dist[i]:
            continue
        for e in bm.verts[i].link_edges:
            j = e.other_vert(bm.verts[i]).index
            if j >= n_tessuto:
                continue
            nd = d + e.calc_length()
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(coda, (nd, j))
    # i vertici del bordino prendono la distanza del vertice di stoffa piu' vicino
    kd = KDTree(n_tessuto)
    for i in range(n_tessuto):
        kd.insert(co[i], i)
    kd.balance()
    for i in range(n_tessuto, nv):
        dist[i] = dist[kd.find(co[i])[1]]
    bm.free()
    bordi = 1.0 - smoothstep(dist / (P["BORDI_CM"] * CM))
    z0 = co[:n_tessuto, 2].min()
    orlo = 1.0 - smoothstep((co[:, 2] - z0) / (P["ORLO_FINO_A"] * CM - z0))
    if obj.name != NOMI["saio"]:
        orlo[:] = 0.0
    return bordi, orlo


# =============================================================================
#  5. COTTURA
# =============================================================================
class Cottura:
    """Prepara una scena di cottura temporanea e la smonta alla fine.
    - mesh basse: copie triangolate (stessi triangoli dell'export) della mesh di gioco;
    - mesh alte: il drappeggio diviso nei suoi pezzi (cuciture), cosi' ogni pezzo
      di gioco "vede" solo il suo pezzo alto: il cappuccio non pesca la mantellina
      che ha sotto, il risvolto non pesca la manica, il fianco non pesca il braccio."""

    def __init__(self, oggetti_gioco, info_isole, n_tessuto):
        sc = bpy.context.scene
        self.sc = sc
        self.R = P["RISOLUZIONE"] * P["SOVRACAMPIONA"]
        self.stato = dict(engine=sc.render.engine, world=sc.world, samples=None,
                          nascosti={o.name: o.hide_render for o in sc.objects})
        self.coll = bpy.data.collections.new("TEMP_COTTURA")
        sc.collection.children.link(self.coll)
        lc = layer_collection("TEMP_COTTURA")
        lc.exclude = False
        lc.hide_viewport = False
        for o in sc.objects:
            o.hide_render = True
        self.corpo = bpy.data.objects["REF_Corpo"]
        self.corpo.hide_render = False
        if sc.world is None:
            sc.world = bpy.data.worlds.new("TEMP_Mondo")
        self.ao_vecchia = sc.world.light_settings.distance
        sc.world.light_settings.distance = P["DISTANZA_AO"] * CM
        sc.render.engine = 'CYCLES'
        self.stato["samples"] = sc.cycles.samples
        self.stato["device"] = sc.cycles.device
        sc.cycles.device = 'CPU'
        self.img = bpy.data.images.new("TEMP_Cottura", self.R, self.R, alpha=True, float_buffer=True)
        self.img.colorspace_settings.name = 'Non-Color'
        self.vuoto = np.zeros(self.R * self.R * 4, np.float32)
        self.buf = np.zeros(self.R * self.R * 4, np.float32)
        self.m_alta = bpy.data.materials.new("TEMP_Alta")
        self.m_bersaglio = self.materiale_bersaglio()
        self.basse, self.pezzi, self.gruppi = {}, [], {}
        for o in oggetti_gioco:
            self.basse[o.name] = self.copia_bassa(o, info_isole[o.name][0], n_tessuto[o.name])
        alti = {NOMI["saio"]: bpy.data.objects[NOMI["saio_a"]], NOMI["mant"]: bpy.data.objects[NOMI["mant_a"]]}
        for nome, alto in alti.items():
            self.dividi_alto(alto, bpy.data.objects[nome], info_isole[nome])

    # --- mesh basse ---------------------------------------------------------
    def copia_bassa(self, o, isola, n_tessuto):
        ob = triangolata(o, "TEMP_" + o.name, self.coll)
        me = ob.data
        idx = np.array(faccia_di_ogni_triangolo(o.data, me))      # isola di ogni triangolo = quella del suo quad
        a = me.attributes.new("isola_cottura", 'FLOAT', 'FACE')
        a.data.foreach_set("value", (isola[idx] + 1).astype(np.float32))
        bordi, orlo = maschere_vertici(o, n_tessuto)
        for nome, val in (("m_bordi", bordi), ("m_orlo", orlo)):
            at = me.attributes.new(nome, 'FLOAT', 'POINT')
            at.data.foreach_set("value", val.astype(np.float32))
        me.materials.clear()
        me.materials.append(self.m_bersaglio)
        for flag in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                     "visible_volume_scatter", "visible_shadow"):
            setattr(ob, flag, False)
        ob.hide_render = False
        return ob

    def materiale_bersaglio(self):
        m = bpy.data.materials.new("TEMP_Bersaglio")
        m.use_nodes = True
        nt = m.node_tree
        for n in list(nt.nodes):
            if n.bl_idname != "ShaderNodeOutputMaterial":
                nt.nodes.remove(n)
        out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        comb = nt.nodes.new("ShaderNodeCombineColor")
        self.attr = {}
        for k, nome in enumerate(("isola_cottura", "chiaro", "m_bordi", "m_orlo")):
            at = nt.nodes.new("ShaderNodeAttribute")
            at.attribute_type = 'GEOMETRY'
            at.attribute_name = nome
            self.attr[nome] = at
        nt.links.new(comb.outputs[0], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = self.img
        nt.nodes.active = tex
        self.nt, self.comb = nt, comb
        return m

    def canali_emissione(self, r, g, b):
        for k, nome in enumerate((r, g, b)):
            for l in list(self.comb.inputs[k].links):
                self.nt.links.remove(l)
            if nome:
                self.nt.links.new(self.attr[nome].outputs["Fac"], self.comb.inputs[k])
            else:
                self.comb.inputs[k].default_value = 0.0

    # --- mesh alte, divise per pezzo -----------------------------------------
    def dividi_alto(self, alto, gioco, info):
        isola_g, pezzi_g = info
        tipo_di = {p["i"]: p for p in pezzi_g}
        bvh = BVHTree.FromPolygons([Vector(c) for c in coordinate(gioco)], [list(p.vertices) for p in gioco.data.polygons])
        isola_a, k = isole_facce(alto.data)
        for i in range(k):
            bm = bmesh.new()
            bm.from_mesh(alto.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if isola_a[f.index] != i], context='FACES')
            bm.transform(alto.matrix_world)
            me = bpy.data.meshes.new(f"TEMP_{alto.name}_{i}")
            bm.to_mesh(me)
            bm.free()
            me.shade_smooth()
            me.materials.clear()
            me.materials.append(self.m_alta)
            ob = bpy.data.objects.new(me.name, me)
            self.coll.objects.link(ob)
            ob.hide_render = False
            # pezzo di gioco corrispondente: quello dove cade la maggior parte dei vertici
            voti = {}
            for j in range(0, len(me.vertices), 7):
                f = bvh.find_nearest(me.vertices[j].co)[2]
                voti[isola_g[f]] = voti.get(isola_g[f], 0) + 1
            ig = max(voti, key=voti.get)
            p = tipo_di[ig]
            gruppo = {"pannello": "busto", "balza": "busto", "manica": "maniche", "risvolto": "risvolti",
                      "mantellina": "mantellina", "cappuccio": "cappuccio"}[p["tipo"]]
            self.gruppi.setdefault((gioco.name, gruppo), dict(pezzi_alti=[], isole=set(), gioco=gioco.name))
            self.gruppi[(gioco.name, gruppo)]["pezzi_alti"].append(ob)
            self.gruppi[(gioco.name, gruppo)]["isole"].add(ig)
            self.pezzi.append(ob)

    # --- una cottura -----------------------------------------------------------
    def cuoci(self, tipo, attivo, sorgenti=(), campioni=1, estrusione=0.0, distanza=0.0):
        self.img.pixels.foreach_set(self.vuoto)
        seleziona(attivo, sorgenti)
        self.sc.cycles.samples = campioni
        kw = dict(type=tipo, margin=0, margin_type='EXTEND', use_clear=False, use_cage=False, uv_layer=UV,
                  target='IMAGE_TEXTURES', save_mode='INTERNAL', use_split_materials=False,
                  use_selected_to_active=bool(sorgenti), cage_extrusion=estrusione, max_ray_distance=distanza,
                  normal_space='TANGENT', normal_r='POS_X', normal_g='NEG_Y', normal_b='POS_Z')
        bpy.ops.object.bake(**kw)
        self.img.pixels.foreach_get(self.buf)
        return self.buf.reshape(self.R, self.R, 4)

    def rovescia(self, oggetti):
        for o in oggetti:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()

    def visibili_ai_raggi(self, oggetti, si):
        for o in oggetti:
            for flag in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                         "visible_volume_scatter", "visible_shadow"):
                setattr(o, flag, si)

    def smonta(self):
        sc = self.sc
        for o in list(self.coll.objects):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.collections.remove(self.coll)
        for m in (self.m_alta, self.m_bersaglio):
            bpy.data.materials.remove(m)
        bpy.data.images.remove(self.img)
        sc.world.light_settings.distance = self.ao_vecchia
        if self.stato["world"] is None:
            w = sc.world
            sc.world = None
            bpy.data.worlds.remove(w)
        sc.render.engine = self.stato["engine"]
        sc.cycles.samples = self.stato["samples"]
        sc.cycles.device = self.stato["device"]
        for o in sc.objects:
            if o.name in self.stato["nascosti"]:
                o.hide_render = self.stato["nascosti"][o.name]


def riduci(a, f):
    """Somma blocchi f x f (da 4096 a 2048)."""
    h, w = a.shape[:2]
    return a.reshape(h // f, f, w // f, f, *a.shape[2:]).sum(axis=(1, 3))


def sposta(a, dy, dx):
    """a spostato di (dy, dx) con bordi a zero."""
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def sfoca(val, valido, sigma):
    """Sfocatura gaussiana che usa solo i pixel validi (non mescola lo sfondo)."""
    r = max(1, int(math.ceil(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    num = val * valido[..., None]
    den = valido.astype(np.float32)[..., None]
    for asse in (0, 1):
        n2 = np.zeros_like(num)
        d2 = np.zeros_like(den)
        for o, w in zip(range(-r, r + 1), k):
            dy, dx = (o, 0) if asse == 0 else (0, o)
            n2 += w * sposta(num, dy, dx)
            d2 += w * sposta(den, dy, dx)
        num, den = n2, d2
    out = val.copy()
    m = valido & (den[..., 0] > 1e-6)
    out[m] = num[m] / den[m]
    return out


def riempi(val, valido, passi=16):
    """Allarga i bordi dei pezzi nello spazio vuoto (cosi' le mip map lontane non
    pescano lo sfondo): prima 16 px "a macchia d'olio", poi tutto il resto."""
    v = val.copy()
    m = valido.copy()
    vicini = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    for _ in range(passi):
        acc = np.zeros_like(v)
        cnt = np.zeros(m.shape, np.float32)
        mf = m.astype(np.float32)
        for dy, dx in vicini:
            acc += sposta(v * mf[..., None], dy, dx)
            cnt += sposta(mf, dy, dx)
        nuovi = (~m) & (cnt > 0)
        v[nuovi] = acc[nuovi] / cnt[nuovi][:, None]
        m |= nuovi
    # resto: piramide (push-pull) con ingrandimento bilineare, cosi' il fondo sfuma
    livelli = [(v * m[..., None], m.astype(np.float32))]
    while livelli[-1][1].shape[0] > 1:
        s, w = livelli[-1]
        livelli.append((riduci(s, 2), riduci(w, 2)))
    s, w = livelli[-1]
    pieno = s / np.maximum(w, 1e-9)[..., None]
    for s, w in reversed(livelli[:-1]):
        su = ingrandisci(pieno)
        pieno = np.where((w > 0)[..., None], s / np.maximum(w, 1e-9)[..., None], su)
    v[~m] = pieno[~m]
    return v


def ingrandisci(c):
    """Raddoppia un'immagine (h, w, canali) con interpolazione bilineare."""
    h, w = c.shape[:2]
    p = np.pad(c, ((1, 1), (1, 1), (0, 0)), mode='edge')
    r = np.empty((2 * h, w + 2, c.shape[2]), c.dtype)
    r[0::2] = 0.75 * p[1:-1] + 0.25 * p[:-2]
    r[1::2] = 0.75 * p[1:-1] + 0.25 * p[2:]
    out = np.empty((2 * h, 2 * w, c.shape[2]), c.dtype)
    out[:, 0::2] = 0.75 * r[:, 1:-1] + 0.25 * r[:, :-2]
    out[:, 1::2] = 0.75 * r[:, 1:-1] + 0.25 * r[:, 2:]
    return out


def salva_png(nome, rgb, cartella):
    """Scrive un PNG 8 bit RGB (dati, non colore) con le funzioni di Blender."""
    h, w = rgb.shape[:2]
    img = bpy.data.images.get("TEMP_" + nome)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new("TEMP_" + nome, w, h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'Non-Color'
    px = np.ones((h, w, 4), np.float32)
    px[..., :3] = np.clip(rgb, 0.0, 1.0)
    img.pixels.foreach_set(px.ravel())
    percorso = os.path.join(cartella, nome + ".png")
    img.filepath_raw = percorso
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return percorso


def cuoci_tutto(oggetti, info_isole, n_tessuto, cartella):
    R2 = P["RISOLUZIONE"]
    f = P["SOVRACAMPIONA"]
    t0 = time.time()
    ck = Cottura(oggetti, info_isole, n_tessuto)
    try:
        # accumulatori a 2048
        acc_n = np.zeros((R2, R2, 3), np.float32)
        cnt_n = np.zeros((R2, R2), np.float32)
        acc_ao = np.zeros((R2, R2, 2), np.float32)
        cnt_ao = np.zeros((R2, R2, 2), np.float32)
        acc_m = np.zeros((R2, R2, 3), np.float32)
        cnt_m = np.zeros((R2, R2), np.float32)
        id4 = {}
        bordini = {o.name: {p["i"] for p in info_isole[o.name][1] if p["tipo"] == "bordino"} for o in oggetti}
        n_cotture = 2 * len(oggetti) + 3 * len(ck.gruppi) + len(oggetti)
        fatte = [0]

        def avanza(cosa):
            fatte[0] += 1
            print(f"    cottura {fatte[0]}/{n_cotture}: {cosa}  ({time.time() - t0:.0f} s)", flush=True)

        # (a) pezzo di ogni pixel + maschere (emissione degli attributi): la mesh
        #     bassa deve essere "visibile" per Cycles, se no non viene cotta
        ck.visibili_ai_raggi(list(ck.basse.values()), True)
        for o in oggetti:
            b = ck.basse[o.name]
            ck.canali_emissione("isola_cottura", "chiaro", "m_bordi")
            x = ck.cuoci('EMIT', b)
            valido = x[..., 3] > 0.5
            ids = np.where(valido, np.rint(x[..., 0]).astype(np.int16), 0)
            id4[o.name] = ids
            acc_m[..., 0] += riduci(x[..., 1] * valido, f)
            acc_m[..., 1] += riduci(x[..., 2] * valido, f)
            cnt_m += riduci(valido.astype(np.float32), f)
            avanza(f"pezzi e maschere di {o.name}")
            ck.canali_emissione("m_orlo", None, None)
            x = ck.cuoci('EMIT', b)
            acc_m[..., 2] += riduci(x[..., 0] * (x[..., 3] > 0.5), f)
            avanza(f"maschera dell'orlo di {o.name}")
        # (b) normal map e ombre, gruppo per gruppo (pezzi alti visibili, basse no:
        #     se no le ombre del drappeggio verrebbero coperte dalla mesh di gioco)
        ck.visibili_ai_raggi(list(ck.basse.values()), False)
        coperture = []
        for (nome_g, gruppo), g in ck.gruppi.items():
            b = ck.basse[nome_g]
            # gabbia: quanto il drappeggio si stacca dalla mesh di gioco in quel gruppo
            bvh = BVHTree.FromPolygons([Vector(c) for c in coordinate(b)], [list(p.vertices) for p in b.data.polygons])
            dev = max(bvh.find_nearest(v.co)[3] for o in g["pezzi_alti"] for v in o.data.vertices)
            estr = max(P["ESTRUSIONE_MIN"] * CM, 1.5 * dev + 0.1 * CM)
            dist = 2 * estr
            dentro = np.isin(id4[nome_g], [i + 1 for i in g["isole"]])
            x = ck.cuoci('NORMAL', b, g["pezzi_alti"], 1, estr, dist)
            ok = dentro & (x[..., 3] > 0.5)
            n = x[..., :3] * 2 - 1
            acc_n += riduci(n * ok[..., None], f)
            cnt_n += riduci(ok.astype(np.float32), f)
            coperture.append((nome_g, gruppo, ok.sum() / max(dentro.sum(), 1), estr / CM))
            avanza(f"normal map {gruppo}")
            for lato in (0, 1):
                if lato == 1:
                    ck.rovescia(g["pezzi_alti"])
                x = ck.cuoci('AO', b, g["pezzi_alti"], P["CAMPIONI_AO"], estr, dist)
                if lato == 1:
                    ck.rovescia(g["pezzi_alti"])
                ok = dentro & (x[..., 3] > 0.5)
                acc_ao[..., lato] += riduci(x[..., 0] * ok, f)
                cnt_ao[..., lato] += riduci(ok.astype(np.float32), f)
                avanza(f"ombre {gruppo} ({'dritto' if lato == 0 else 'rovescio'})")
        # (c) bordini: normal piatta; ombre dalla mesh di gioco stessa (basse visibili, alte no)
        ck.visibili_ai_raggi(ck.pezzi, False)
        ck.visibili_ai_raggi(list(ck.basse.values()), True)
        for o in oggetti:
            b = ck.basse[o.name]
            dentro = np.isin(id4[o.name], [i + 1 for i in bordini[o.name]])
            piatta = np.zeros(dentro.shape + (3,), np.float32)
            piatta[..., 2] = 1.0
            acc_n += riduci(piatta * dentro[..., None], f)
            cnt_n += riduci(dentro.astype(np.float32), f)
            x = ck.cuoci('AO', b, (), P["CAMPIONI_AO"])
            ok = dentro & (x[..., 3] > 0.5)
            for lato in (0, 1):
                acc_ao[..., lato] += riduci(x[..., 0] * ok, f)
                cnt_ao[..., lato] += riduci(ok.astype(np.float32), f)
            avanza(f"ombre dei bordini di {o.name}")
        # pezzo di ogni pixel a 2048 (serve ai controlli e alle tavole)
        id2 = np.zeros((R2, R2), np.int32)
        for k, o in enumerate(oggetti):
            m4 = id4[o.name]
            blocchi = m4.reshape(R2, f, R2, f).max(axis=(1, 3)).astype(np.int32)
            id2 = np.where(blocchi > 0, blocchi + 100 * k, id2)
    finally:
        ck.smonta()
    # --- composizione -----------------------------------------------------------
    valido = cnt_m > 0
    if not valido.any() or not (cnt_n > 0).any():
        raise RuntimeError("La cottura non ha scritto nulla: controlla che la mesh di gioco sia visibile al render")
    n = acc_n / np.maximum(cnt_n, 1e-9)[..., None]
    vn = cnt_n > 0
    n[~vn] = (0, 0, 1)
    n /= np.maximum(np.linalg.norm(n, axis=-1), 1e-9)[..., None]
    # tetto all'inclinazione: oltre MAX_INCLINAZIONE la normale viene riportata a quel valore
    tetto = math.radians(P["MAX_INCLINAZIONE"])
    xy = np.linalg.norm(n[..., :2], axis=-1)
    troppo = np.arctan2(xy, n[..., 2]) > tetto
    st_tetto = int((troppo & vn).sum())
    dir_xy = n[..., :2] / np.maximum(xy, 1e-9)[..., None]
    n[troppo, :2] = dir_xy[troppo] * math.sin(tetto)
    n[troppo, 2] = math.cos(tetto)
    n = riempi(n, vn)
    n /= np.maximum(np.linalg.norm(n, axis=-1), 1e-9)[..., None]
    ao = acc_ao / np.maximum(cnt_ao, 1e-9)
    vao = cnt_ao[..., 0] > 0
    ao = sfoca(ao, vao, P["SFOCA_AO"])
    ao = riempi(ao, vao)
    m = acc_m / np.maximum(cnt_m, 1e-9)[..., None]
    m = riempi(m, valido)
    os.makedirs(cartella, exist_ok=True)
    salva_png(TEX["N"], n * 0.5 + 0.5, cartella)
    salva_png(TEX["AO"], np.dstack([ao[..., 0], ao[..., 1], np.zeros_like(ao[..., 0])]), cartella)
    salva_png(TEX["M"], m, cartella)
    # statistiche per il rapporto
    st = {}
    pieghe = np.degrees(np.arccos(np.clip(n[valido][:, 2], -1, 1)))
    st["pieghe"] = (np.percentile(pieghe, 50), np.percentile(pieghe, 95), pieghe.max())
    st["n_vuoti"] = int((valido & ~vn).sum())
    st["tetto"] = st_tetto / max(int(vn.sum()), 1) * 100
    st["ao"] = (ao[valido][:, 0].mean(), ao[valido][:, 1].mean())
    st["coperture"] = coperture
    st["tempo"] = time.time() - t0
    st["id2"] = id2
    return st


# =============================================================================
#  6. MATERIALI (anteprima in Blender)
# =============================================================================
def immagine(cartella, nome):
    percorso = os.path.join(cartella, nome + ".png")
    img = bpy.data.images.get(nome + ".png")
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.load(percorso)
    img.colorspace_settings.name = 'Non-Color'
    if bpy.data.filepath:
        img.filepath = bpy.path.relpath(percorso)
    return img


def materiale_lana(cartella):
    """M_Lana = il materiale che andra' in Unreal. Qui e' solo un'ANTEPRIMA:
    lana bruno-grigia, risvolto piu' chiaro, ombre (dritto o rovescio secondo il
    lato che si guarda) e normal map. In Unreal (Fase 6) il materiale vero si
    rifa' con gli stessi ingressi; i due colori sono nodi RGB modificabili."""
    mat = bpy.data.materials.get("M_Lana") or bpy.data.materials.new("M_Lana")
    mat.diffuse_color = (0.33, 0.27, 0.22, 1.0)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    out = N("ShaderNodeOutputMaterial")
    bsdf = N("ShaderNodeBsdfPrincipled")
    uvn = N("ShaderNodeUVMap")
    uvn.uv_map = UV
    tn, ta, tm = (N("ShaderNodeTexImage") for _ in range(3))
    for t, nome in ((tn, TEX["N"]), (ta, TEX["AO"]), (tm, TEX["M"])):
        t.image = immagine(cartella, nome)
        t.interpolation = 'Linear'
        nt.links.new(uvn.outputs["UV"], t.inputs["Vector"])
        t.label = nome
    # normal map: Unreal (DirectX) ha il verde rovesciato rispetto a Blender (OpenGL)
    sep = N("ShaderNodeSeparateColor")
    inv = N("ShaderNodeMath")
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    comb = N("ShaderNodeCombineColor")
    nmap = N("ShaderNodeNormalMap")
    nmap.space = 'TANGENT'
    nmap.uv_map = UV
    nt.links.new(tn.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs[0], comb.inputs[0])
    nt.links.new(sep.outputs[1], inv.inputs[1])
    nt.links.new(inv.outputs[0], comb.inputs[1])
    nt.links.new(sep.outputs[2], comb.inputs[2])
    nt.links.new(comb.outputs[0], nmap.inputs["Color"])
    nt.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
    # ombre: R davanti, G dietro (Backfacing = come TwoSidedSign di Unreal)
    sep_ao = N("ShaderNodeSeparateColor")
    geo = N("ShaderNodeNewGeometry")
    mix_ao = N("ShaderNodeMix")
    mix_ao.data_type = 'FLOAT'
    nt.links.new(ta.outputs["Color"], sep_ao.inputs["Color"])
    nt.links.new(geo.outputs["Backfacing"], mix_ao.inputs["Factor"])
    nt.links.new(sep_ao.outputs[0], mix_ao.inputs["A"])
    nt.links.new(sep_ao.outputs[1], mix_ao.inputs["B"])
    # colore: lana bruno-grigia non tinta, risvolto piu' chiaro (maschera R)
    info = N("ShaderNodeRGB")
    info.label = "Lana"
    info.outputs[0].default_value = (0.105, 0.078, 0.056, 1.0)
    sep_m = N("ShaderNodeSeparateColor")
    nt.links.new(tm.outputs["Color"], sep_m.inputs["Color"])
    chiaro = N("ShaderNodeRGB")
    chiaro.label = "Risvolto"
    chiaro.outputs[0].default_value = (0.33, 0.27, 0.19, 1.0)
    mix_c = N("ShaderNodeMix")
    mix_c.data_type = 'RGBA'
    nt.links.new(sep_m.outputs[0], mix_c.inputs["Factor"])
    nt.links.new(info.outputs[0], mix_c.inputs[6])
    nt.links.new(chiaro.outputs[0], mix_c.inputs[7])
    mul = N("ShaderNodeMix")
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(mix_c.outputs[2], mul.inputs[6])
    nt.links.new(mix_ao.outputs[0], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.3
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    pos = {out: (900, 0), bsdf: (550, 0), uvn: (-1100, 0), tn: (-850, -350), ta: (-850, 0), tm: (-850, 350),
           sep: (-500, -350), inv: (-300, -420), comb: (-100, -350), nmap: (150, -350), sep_ao: (-500, 0),
           geo: (-500, -150), mix_ao: (-250, 0), info: (-500, 550), sep_m: (-500, 350), chiaro: (-500, 700),
           mix_c: (-250, 450), mul: (100, 250)}
    for nodo, xy in pos.items():
        nodo.location = xy
    return mat


def materiale_semplice(nome, colore, chiaro=False):
    mat = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    mat.diffuse_color = colore
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.92
    out.location = (300, 0)
    if chiaro:          # come il materiale della Fase 2: colore dell'oggetto + risvolto (attributo)
        info = nt.nodes.new("ShaderNodeObjectInfo")
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "chiaro"
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (0.56, 0.50, 0.42, 1.0)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = 'RGBA'
        nt.links.new(attr.outputs["Fac"], mix.inputs["Factor"])
        nt.links.new(info.outputs["Color"], mix.inputs[6])
        nt.links.new(rgb.outputs[0], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        info.location, attr.location, rgb.location, mix.location = (-600, 200), (-600, 0), (-600, -200), (-250, 0)
    else:
        bsdf.inputs["Base Color"].default_value = colore
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


# =============================================================================
#  MAIN
# =============================================================================
def main(salva=True):
    log("=== REPORT FASE 5 - UV E MAPPE DELLA LANA ===")
    for nome in list(NOMI.values()) + ["REF_Corpo"]:
        if bpy.data.objects.get(nome) is None:
            raise RuntimeError(f"Manca {nome}: apri Saio_Abate_v004.blend (Fase 4).")
    if not bpy.data.filepath:
        raise RuntimeError("Salva prima il file .blend: le texture vanno nella cartella accanto.")
    modo_oggetto()
    sc = bpy.context.scene
    for nome in ("GIOCO",):
        lc = layer_collection(nome)
        lc.exclude = False
        lc.hide_viewport = False
    saio, mant = bpy.data.objects[NOMI["saio"]], bpy.data.objects[NOMI["mant"]]
    saio_f, mant_f = bpy.data.objects[NOMI["saio_f"]], bpy.data.objects[NOMI["mant_f"]]
    gioco = [saio, mant]
    n_tessuto = {saio.name: len(saio_f.data.vertices), mant.name: len(mant_f.data.vertices)}
    for o in gioco:
        o.hide_viewport = False
        o.hide_select = False
        o.hide_set(False)

    # 1) tagli dei bordini, UV nuove
    for o in gioco:
        t = taglia_bordini(o, n_tessuto[o.name])
        while o.data.uv_layers:
            o.data.uv_layers.remove(o.data.uv_layers[0])
        o.data.uv_layers.new(name=UV)
        log(f"[1] {o.name}: bordini tagliati in {t} punti (sulle cuciture del tessuto)")
    info_isole = {}
    for o in gioco:
        isola, k = isole_facce(o.data)
        info_isole[o.name] = (isola, classifica(o, isola, k, n_tessuto[o.name]))
    vecchia_sync = sc.tool_settings.use_uv_select_sync
    sc.tool_settings.use_uv_select_sync = True
    try:
        stendi(gioco)
        for o in gioco:
            orienta_e_scala(o, *info_isole[o.name])
            log(f"[2] {o.name}: pezzi " + ", ".join(p["nome"] for p in info_isole[o.name][1]))
        girati, _ = impacchetta(gioco, info_isole)
        log(f"[2] Impacchettati col filo verticale; girati di 180 gradi: {', '.join(girati) or 'nessuno'}")
    finally:
        sc.tool_settings.use_uv_select_sync = vecchia_sync
    K, _ = densita(gioco)
    log("[3] Controlli delle UV:")
    ok, st_uv = controlli_uv(gioco, info_isole, K)

    # 2) mesh per la fisica: UV in centimetri
    for g, f in ((saio, saio_f), (mant, mant_f)):
        uvf = uv_fisica(g, f, K)
        log(f"[4] {f.name}: UV in scala reale (1 = 1 cm), pezzi da {uvf[:, 0].max() - uvf[:, 0].min():.0f} x "
            f"{uvf[:, 1].max() - uvf[:, 1].min():.0f} cm in tutto")

    # 3) triangoli per Unreal (stessi della cottura)
    for o in gioco:
        m = o.modifiers.get("Triangola_per_UE") or o.modifiers.new("Triangola_per_UE", 'TRIANGULATE')
        m.quad_method = 'FIXED'
        m.ngon_method = 'BEAUTY'
        m.min_vertices = 4
        if hasattr(m, "keep_custom_normals"):
            m.keep_custom_normals = False
        m.show_in_editmode = False

    # 4) cottura
    cartella = os.path.join(os.path.dirname(bpy.data.filepath), CARTELLA_TEX)
    log(f"[5] Cottura dal drappeggio alto ({P['RISOLUZIONE'] * P['SOVRACAMPIONA']} px, poi ridotta a {P['RISOLUZIONE']}):")
    st = cuoci_tutto(gioco, info_isole, n_tessuto, cartella)
    for nome_g, gruppo, cop, estr in st["coperture"]:
        log(f"    {gruppo:10s} ({nome_g}): pixel colpiti dal drappeggio {cop * 100:.2f}%, gabbia {estr:.2f} cm")
        ok &= cop > 0.995
    p50, p95, pmax = st["pieghe"]
    log(f"    Normal map: inclinazione delle pieghe mediana {p50:.1f} gradi, 95% entro {p95:.1f}; "
        f"riportati a {P['MAX_INCLINAZIONE']:.0f} gradi {st['tetto']:.2f}% dei pixel (stoffa raggrinzita sotto le ascelle)")
    log(f"    Ombre (1 = nessuna): media lato dritto {st['ao'][0]:.2f}, lato rovescio {st['ao'][1]:.2f}")
    log(f"    Texture scritte in {cartella}: {TEX['N']}.png, {TEX['AO']}.png, {TEX['M']}.png "
        f"({st['tempo'] / 60:.1f} minuti)")

    # 5) materiali
    materiale_lana(cartella)
    m_alta = materiale_semplice("M_Lana_Alta", (0.33, 0.27, 0.22, 1.0), chiaro=True)
    m_fis = materiale_semplice("M_Fisica", (0.45, 0.62, 0.85, 1.0))
    for nome in (NOMI["saio_a"], NOMI["mant_a"]):
        o = bpy.data.objects[nome]
        o.data.materials.clear()
        o.data.materials.append(m_alta)
    for o in (saio_f, mant_f):
        o.data.materials.clear()
        o.data.materials.append(m_fis)
    log("[6] Materiali: M_Lana (mesh di gioco, con le texture; e' quello che va in Unreal), "
        "M_Lana_Alta (drappeggio), M_Fisica (solo per riconoscere la mesh per la fisica)")

    nuovo = os.path.join(os.path.dirname(bpy.data.filepath), NOME_FILE_V5)
    if salva:
        log(f"[7] Salvo come {nuovo} (il file v004 resta intatto)")
    log("ESITO: " + ("tutti i controlli superati" if ok else "ATTENZIONE: qualche controllo non e' passato"))
    testo = bpy.data.texts.get("REPORT_Fase5") or bpy.data.texts.new("REPORT_Fase5")
    testo.clear()
    testo.write("\n".join(report) + "\n")
    if salva:
        bpy.ops.wm.save_as_mainfile(filepath=nuovo)
    return ok, testo, st, st_uv


if __name__ == "__main__":
    ok, testo, _, _ = main()
    spazio = getattr(bpy.context, "space_data", None)
    if spazio is not None and spazio.type == 'TEXT_EDITOR':
        spazio.text = testo
    wm = bpy.context.window_manager
    if wm.windows and not bpy.app.background:
        def disegna(self, context):
            for riga in report[:20]:
                self.layout.label(text=riga)
        wm.popup_menu(disegna, title="Fase 5: fatto" if ok else "Fase 5: controlla il report",
                      icon='INFO' if ok else 'ERROR')
