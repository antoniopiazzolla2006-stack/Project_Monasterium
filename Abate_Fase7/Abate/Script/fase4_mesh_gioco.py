# =============================================================================
#  FASE 4 - MESH DI GIOCO: topologia leggera, spessore della lana, mesh per la fisica
#  Progetto: Abate francescano  (MetaHuman UE 5.8  ->  Blender 5.2  ->  UE 5.8)
#
#  COSA FA
#   1. Sistema la punta del cappuccio nel drappeggio alto (era raggrinzita):
#      la zona attorno alla punta viene appoggiata sulla mantellina e "stirata".
#   2. Ricava dal drappeggio alto (28 mila triangoli) la MESH DI GIOCO: la stessa
#      stoffa con meta' dei vertici per lato (livello 1 invece di 2). Ogni vertice
#      della mesh di gioco e' ESATTAMENTE un vertice del drappeggio (sta sulla
#      superficie alta): niente forme inventate; le pieghe piu' fini andranno
#      nella normal map (Fase 5).
#   3. Spessore della lana sui bordi che si vedono (orlo, polsini, bordo della
#      mantellina e del cappuccio): un bordino e una fascia interna.
#   4. MESH PER LA FISICA (Unreal, Chaos Cloth): lo stesso tessuto a uno strato,
#      senza spessore, con una mappa che PROPONE dove la stoffa sara' libera.
#   5. Controlli e rapporto; salva Saio_Abate_v004.blend (v003 resta intatto).
#
#  PRIMA DI LANCIARLO
#   - Apri Saio_Abate_v003.blend (quello della Fase 3).
#  COME SI LANCIA
#   - Workspace "Scripting" > Text > Open > questo file > Run Script (Alt+P).
#     Ci mette circa un minuto.
#
#  PERCHE' COSI' (compatibilita' con tutti i MetaHuman)
#   - Le mesh restano nella posa di riferimento (A-pose) sul corpo esportato.
#   - Niente scheletro ne' skinning qui: in Unreal i pesi si trasferiscono dal
#     corpo (nodo TransferSkinWeights del Dataflow).
#   - La topologia nasce da regole fisse (gabbia della Fase 2 -> livello 1): la
#     stessa procedura su un altro corpo MetaHuman da' la stessa topologia e le
#     stesse UV. Servira' per le "taglie" del sistema Outfit di Unreal.
#   - In Unreal il materiale della lana va impostato "Two Sided": la stoffa ha uno
#     strato solo (l'interno di maniche e gonna si vede dal rovescio) e lo
#     spessore c'e' solo dove serve, sui bordi.
# =============================================================================

import bpy
import bmesh
import math
import os
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

CM = 0.01   # 1 cm in unita' Blender (metri)

# ----------------------------- PARAMETRI -------------------------------------
P = dict(
    # --- punta del cappuccio ---
    PUNTA_RAGGIO=14.0,       # cm attorno alla punta che vengono sistemati (sfumando)
    PUNTA_CICLI=8,           # giri di "appoggia + stira"
    PUNTA_STACCO=1.0,        # cm tra la punta sistemata e la mantellina sotto
    # --- spessore della lana ai bordi (cm) ---
    SPESSORE_SAIO=0.4,
    SPESSORE_MANT=0.3,       # piu' sottile: sotto c'e' il saio a mezzo centimetro
    SCOLLO_SOPRA=140.0,      # cm: i bordi del saio sopra questa quota (scollo) restano
                             #   senza spessore, tanto li copre il collo arrotolato
)

COLL_GIOCO = "GIOCO"
COLL_FISICA = "FISICA"
NOMI = dict(saio="Saio_Gioco", mant="Mantellina_Gioco", saio_f="Saio_Fisica", mant_f="Mantellina_Fisica")
NOME_FILE_V4 = "Saio_Abate_v004.blend"
report = []


def log(riga=""):
    print(riga, flush=True)
    report.append(riga)


# =============================================================================
#  UTILITA'
# =============================================================================
def prendi_collezione(nome):
    coll = bpy.data.collections.get(nome)
    if coll is None:
        coll = bpy.data.collections.new(nome)
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    return coll


def layer_collection(nome, lc=None):
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.name == nome:
        return lc
    for figlio in lc.children:
        t = layer_collection(nome, figlio)
        if t:
            return t
    return None


def rimuovi(nome):
    obj = bpy.data.objects.get(nome)
    if obj is None:
        return
    me = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def coordinate(obj):
    """Coordinate dei vertici in spazio mondo (mesh di base, senza modificatori)."""
    co = np.zeros(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(obj.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def imposta_coordinate(obj, co_mondo):
    Minv = np.array(obj.matrix_world.inverted())
    loc = co_mondo @ Minv[:3, :3].T + Minv[:3, 3]
    obj.data.vertices.foreach_set("co", loc.ravel())
    obj.data.update()


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


def imposta_gruppo(obj, nome, pesi):
    g = obj.vertex_groups.get(nome)
    if g is not None:
        obj.vertex_groups.remove(g)
    g = obj.vertex_groups.new(name=nome)
    for i in np.where(pesi > 0)[0]:
        g.add([int(i)], float(pesi[i]), 'REPLACE')
    return g


def bvh_oggetto(obj):
    co = coordinate(obj)
    polys = [list(p.vertices) for p in obj.data.polygons]
    return BVHTree.FromPolygons([Vector(c) for c in co], polys), [set(p) for p in polys]


def pelle():
    """BVH della pelle del MetaHuman (pezzo piu' grande di REF_Corpo) e della testa."""
    ref = bpy.data.objects["REF_Corpo"]
    bm = bmesh.new()
    bm.from_mesh(ref.data)
    bm.transform(ref.matrix_world)
    bm.verts.ensure_lookup_table()
    visti, pezzi = set(), []
    for v in bm.verts:
        if v.index in visti:
            continue
        pila, pezzo = [v], []
        visti.add(v.index)
        while pila:
            x = pila.pop()
            pezzo.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in visti:
                    visti.add(o.index)
                    pila.append(o)
        pezzi.append(pezzo)
    pezzi.sort(key=len, reverse=True)
    bmesh.ops.delete(bm, geom=[v for p in pezzi[1:] for v in p], context='VERTS')
    bm.verts.index_update()
    bm.faces.index_update()
    uv = bm.loops.layers.uv.active
    testa_v, testa_f, mappa = [], [], {}
    if uv is not None:
        for f in bm.faces:
            if sum(l[uv].uv.x for l in f.loops) / len(f.loops) < 1.0:
                ids = []
                for v in f.verts:
                    if v.index not in mappa:
                        mappa[v.index] = len(testa_v)
                        testa_v.append(v.co.copy())
                    ids.append(mappa[v.index])
                testa_f.append(ids)
    bvh = BVHTree.FromBMesh(bm)
    bvh_testa = BVHTree.FromPolygons(testa_v, testa_f) if testa_f else None
    bm.free()
    return bvh, bvh_testa


def distanze_con_segno(coords, bvh):
    d = np.empty(len(coords))
    for i, c in enumerate(coords):
        p = Vector(c)
        loc, nor, idx, dist = bvh.find_nearest(p)
        d[i] = dist if (p - loc).dot(nor) >= 0 else -dist
    return d


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# =============================================================================
#  1. PUNTA DEL CAPPUCCIO
# =============================================================================
def sistema_punta(mant, saio):
    """La punta del cappuccio si era raggrinzita nella simulazione: la zona attorno
    viene appoggiata sulla mantellina (a PUNTA_STACCO) e stirata, sfumando verso
    l'esterno. Il resto del cappuccio non si muove."""
    lato = pesi_gruppo(mant, "Lato_Cappuccio")       # 1 = cappuccio, 0 = mantellina
    co = coordinate(mant)
    cand = np.where((lato > 0.75) & (np.abs(co[:, 0]) < 0.06))[0]
    punta = cand[np.argmin(co[cand, 2])]
    R = P["PUNTA_RAGGIO"] * CM
    t = np.clip(1 - np.linalg.norm(co - co[punta], axis=1) / R, 0, 1)
    w = np.where(lato > 0.75, smoothstep(t), 0.0)
    bm = bmesh.new()
    bm.from_mesh(mant.data)
    bm.transform(mant.matrix_world)
    bm.verts.ensure_lookup_table()
    attivi = [v for v in bm.verts if w[v.index] > 0]
    sotto = [[v.index for v in f.verts] for f in bm.faces if all(lato[v.index] < 0.25 for v in f.verts)]
    bvh_c = BVHTree.FromPolygons([v.co.copy() for v in bm.verts], sotto)   # la mantellina sotto e' ferma
    stacco = P["PUNTA_STACCO"] * CM
    for _ in range(P["PUNTA_CICLI"]):
        for v in attivi:                       # appoggia sulla mantellina
            loc, nor, idx, dist = bvh_c.find_nearest(v.co)
            if loc is None:
                continue
            dv = v.co - loc
            n = nor.normalized()
            if dv.length > 1e-6 and dv.normalized().dot(n) < -0.5:
                n = -n
            v.co = v.co.lerp(loc + n * stacco, 0.6 * w[v.index])
        for _ in range(4):                     # stira la maglia
            nuovi = {}
            for v in attivi:
                vicini = [e.other_vert(v) for e in v.link_edges if (e.is_boundary or not v.is_boundary)]
                if vicini:
                    media = sum((x.co for x in vicini), Vector()) / len(vicini)
                    nuovi[v] = v.co + (media - v.co) * (0.4 * w[v.index])
            for v, c in nuovi.items():
                v.co = c
    # ultimo controllo: sopra la mantellina e sopra il saio
    bvh_s, _ = bvh_oggetto(saio)
    for v in attivi:
        for bvh, minimo in ((bvh_c, 0.008), (bvh_s, 0.012)):
            loc, nor, idx, dist = bvh.find_nearest(v.co)
            if loc is None:
                continue
            dv = v.co - loc
            if dv.dot(nor) < 0 or dist < minimo:
                verso = dv.normalized() if (dv.dot(nor) >= 0 and dv.length > 1e-6) else nor.normalized()
                v.co = loc + verso * minimo
    bm.transform(mant.matrix_world.inverted())
    bm.to_mesh(mant.data)
    bm.free()
    mant.data.update()
    spost = np.linalg.norm(coordinate(mant) - co, axis=1) / CM
    log(f"[1] Punta del cappuccio sistemata: {len(attivi)} vertici in un raggio di {P['PUNTA_RAGGIO']:.0f} cm, "
        f"spostamento massimo {spost.max():.1f} cm")


# =============================================================================
#  2. MESH DI GIOCO (livello 1 dentro il drappeggio)
# =============================================================================
def superficie(blockout, livello):
    """Mesh della gabbia suddivisa al livello richiesto (posizioni 'limite')."""
    mod = blockout.modifiers["Suddivisione"]
    vecchio = (mod.levels, mod.use_limit_surface)
    mod.levels = livello
    mod.use_limit_surface = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(blockout.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    mod.levels, mod.use_limit_surface = vecchio
    bpy.context.view_layer.update()
    return me


def mesh_gioco(blockout, alto, nome, coll):
    """La superficie a livello 1 ha i suoi vertici ESATTAMENTE tra quelli del
    livello 2 (stessa posizione 'limite'): si abbinano per posizione e si prendono
    le posizioni dal drappeggio alto, che ha la topologia del livello 2."""
    me1 = superficie(blockout, 1)
    me2 = superficie(blockout, 2)
    if len(me2.vertices) != len(alto.data.vertices):
        raise RuntimeError(f"{alto.name}: il drappeggio non ha la topologia del livello 2")
    c2 = np.zeros(len(me2.vertices) * 3)
    me2.vertices.foreach_get("co", c2)
    kd = KDTree(len(me2.vertices))
    for i, c in enumerate(c2.reshape(-1, 3)):
        kd.insert(c, i)
    kd.balance()
    trovati = [kd.find(v.co) for v in me1.vertices]
    mappa = np.array([t[1] for t in trovati])
    scarto = max(t[2] for t in trovati)
    if scarto > 1e-5 or len(set(mappa.tolist())) != len(mappa):
        raise RuntimeError(f"{nome}: abbinamento livello 1 / livello 2 non riuscito ({scarto:.2e})")
    bpy.data.meshes.remove(me2)
    me1.name = nome
    ob = bpy.data.objects.new(nome, me1)
    coll.objects.link(ob)
    for g in blockout.vertex_groups:                  # gruppi della gabbia (pesi gia' nella mesh)
        if ob.vertex_groups.get(g.name) is None:
            ob.vertex_groups.new(name=g.name)
    imposta_coordinate(ob, coordinate(alto)[mappa])
    for nome_g in ("Lato_Cappuccio",):                # gruppi del drappeggio, via abbinamento
        if alto.vertex_groups.get(nome_g) is not None:
            imposta_gruppo(ob, nome_g, pesi_gruppo(alto, nome_g)[mappa])
    me1.shade_smooth()
    ob.color = alto.color
    return ob, mappa


def fedelta(gioco, alto):
    """Quanto la superficie alta si stacca da quella di gioco (cm)."""
    bvh, _ = bvh_oggetto(gioco)
    d = np.array([bvh.find_nearest(Vector(c))[3] for c in coordinate(alto)]) / CM
    return d.mean(), np.percentile(d, 95), d.max()


# =============================================================================
#  3. SPESSORE AI BORDI
# =============================================================================
def aggiungi_bordi(obj, spessore, bvh_pelle, z_max=None):
    """Lungo i bordi liberi: una fascia interna (copia della prima fila di facce,
    spostata verso il corpo di 'spessore') e un bordino che la unisce al bordo
    esterno. Il verso 'dentro' si decide col corpo: nel cappuccio rovesciato la
    stoffa e' girata, quindi la normale da sola non basta."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    lay_b = bm.faces.layers.float.get("bordo") or bm.faces.layers.float.new("bordo")   # prima di creare facce
    lay_c = bm.faces.layers.float.get("chiaro")
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    lati = [e for e in bm.edges if e.is_boundary]
    if z_max is not None:
        lati = [e for e in lati if max(v.co.z for v in e.verts) < z_max]
    # liste ORDINATE (non insiemi): cosi' i nuovi vertici nascono sempre nello stesso
    # ordine, run dopo run e taglia dopo taglia (serve per riusare le stesse UV)
    fila = list(dict.fromkeys(f for e in lati for f in e.link_faces))
    fila_set = set(fila)
    # ogni bordo (anello di lati liberi) decide UNA volta, a maggioranza, da che parte
    # sta il corpo: vertice per vertice il punto di pelle piu' vicino puo' ingannare
    # (vicino ai polsi la pelle piu' vicina e' la mano)
    fila_v = list(dict.fromkeys(v for f in fila for v in f.verts))
    gruppo, visti = {}, set()
    for f0 in fila:
        if f0 in visti:
            continue
        pila, comp = [f0], []
        visti.add(f0)
        while pila:
            f = pila.pop()
            comp.append(f)
            for v in f.verts:
                for g in v.link_faces:
                    if g in fila_set and g not in visti:
                        visti.add(g)
                        pila.append(g)
        cv = list(dict.fromkeys(v for f in comp for v in f.verts))
        voto = 0.0
        for v in cv:
            loc = bvh_pelle.find_nearest(v.co)[0]
            if loc is not None:
                voto += 1.0 if v.normal.dot(v.co - loc) >= 0 else -1.0
        for v in cv:
            gruppo[v] = 1.0 if voto >= 0 else -1.0
    interno = {}
    for v in fila_v:
        n = v.normal.normalized() * gruppo[v]          # n punta via dal corpo
        interno[v] = bm.verts.new(v.co - n * spessore)
    nuove = 0
    for f in fila:                                     # fascia interna (verso rovesciato)
        nf = bm.faces.new([interno[v] for v in reversed(f.verts)])
        nf[lay_b] = 1.0
        if lay_c is not None:
            nf[lay_c] = f[lay_c]
        nf.smooth = True
        nuove += 1
    for e in lati:                                     # bordino
        f = e.link_faces[0]
        for l in f.loops:
            if l.edge == e:
                va, vb = l.vert, l.link_loop_next.vert
                break
        nf = bm.faces.new([vb, va, interno[va], interno[vb]])
        nf[lay_b] = 1.0
        if lay_c is not None:
            nf[lay_c] = f[lay_c]
        nf.smooth = True
        nuove += 1
        e.seam = True                                  # la fascia sara' un'isola UV a parte
        e.smooth = False                               # spigolo vivo tra stoffa e bordino
        ei = bm.edges.get((interno[va], interno[vb]))
        if ei is not None:
            ei.smooth = False
    bm.normal_update()
    bm.transform(obj.matrix_world.inverted())
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return len(lati), nuove


# =============================================================================
#  4. MESH PER LA FISICA
# =============================================================================
def segmento_braccio(arm, lato):
    nomi = [f"upperarm_{lato}", f"lowerarm_{lato}", f"hand_{lato}"]
    if arm is None or any(n not in arm.data.bones for n in nomi):
        base = [Vector((0.1983, 0.0217, 1.4327)), Vector((0.3794, 0.0137, 1.1955)), Vector((0.5059, -0.1412, 1.0439))]
        return [Vector((p.x if lato == "l" else -p.x, p.y, p.z)) for p in base]
    return [arm.matrix_world @ arm.data.bones[n].head_local for n in nomi]


def parametro_braccio(p, punti):
    """Distanza dall'asse del braccio e posizione lungo il braccio (0 spalla, 1 polso)."""
    lung = [(punti[i + 1] - punti[i]).length for i in range(len(punti) - 1)]
    tot, acc, best = sum(lung), 0.0, (1e9, 0.0)
    for i in range(len(punti) - 1):
        a, b = punti[i], punti[i + 1]
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        d = (p - (a + ab * t)).length
        if d < best[0]:
            best = (d, (acc + t * lung[i]) / tot)
        acc += lung[i]
    return best


def proposta_fisica(obj, tipo):
    """0 = la stoffa segue il corpo (skinning), 1 = completamente libera.
    E' solo una PROPOSTA: in Unreal (Fase 9) si regola con la Max Distance."""
    co = coordinate(obj)
    z = co[:, 2]
    w = np.zeros(len(co))
    if tipo == "saio":
        arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE' and "upperarm_l" in o.data.bones), None)
        bracci = (segmento_braccio(arm, "l"), segmento_braccio(arm, "r"))
        w = np.where(z < 1.15, smoothstep((1.15 - z) / 0.45), 0.15)          # gonna libera verso l'orlo
        w = np.where(np.abs(z - 1.152) < 0.03, 0.0, w)                        # il cordone la tiene
        w = np.where(z > 1.30, 0.15 * np.clip((1.40 - z) / 0.10, 0, 1), w)   # spalle e sprone seguono il corpo
        for i, c in enumerate(co):
            p = Vector(c)
            for punti in bracci:
                d, s = parametro_braccio(p, punti)
                if d < 0.17 and abs(c[0]) > 0.17:                                # manica
                    w[i] = float(smoothstep((s - 0.10) / 0.70))
    else:
        lato = pesi_gruppo(obj, "Lato_Cappuccio")
        w = np.where(lato < 0.25, 0.3 * smoothstep((1.50 - z) / 0.20), 0.05)           # mantellina
        w = np.where((lato > 0.75) & (z <= 1.47), 0.5 * smoothstep((1.47 - z) / 0.15), w)  # lembo del cappuccio
    imposta_gruppo(obj, "Proposta_Fisica", np.clip(w, 0.0, 1.0))
    return w


def mesh_fisica(gioco, nome, coll, tipo):
    ob = bpy.data.objects.new(nome, gioco.data.copy())
    ob.data.name = nome
    ob.matrix_world = gioco.matrix_world.copy()
    coll.objects.link(ob)
    for g in gioco.vertex_groups:                     # stessi gruppi, stesso ordine
        if ob.vertex_groups.get(g.name) is None:
            ob.vertex_groups.new(name=g.name)
    w = proposta_fisica(ob, tipo)
    return ob, w


# =============================================================================
#  5. CONTROLLI
# =============================================================================
def conta(obj):
    me = obj.data
    tri = sum(len(p.vertices) - 2 for p in me.polygons)
    quad = sum(1 for p in me.polygons if len(p.vertices) == 4)
    ngon = sum(1 for p in me.polygons if len(p.vertices) > 4)
    bm = bmesh.new()
    bm.from_mesh(me)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    bordi = sum(1 for e in bm.edges if e.is_boundary)
    visti, isole = set(), 0
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        if f.index in visti:
            continue
        isole += 1
        pila = [f]
        visti.add(f.index)
        while pila:
            x = pila.pop()
            for e in x.edges:
                if e.seam:
                    continue
                for g in e.link_faces:
                    if g.index not in visti:
                        visti.add(g.index)
                        pila.append(g)
    bm.free()
    return dict(vert=len(me.vertices), tri=tri, quad=quad, ngon=ngon, nonman=nonman, bordi=bordi, isole=isole)


def autointersezioni(obj):
    bvh, sets = bvh_oggetto(obj)
    return sum(1 for a, b in bvh.overlap(bvh) if a < b and not (sets[a] & sets[b]))


def controlli(saio, mant, saio_f, mant_f, bvh_pelle, bvh_testa):
    ok = True
    tot = 0
    for o in (saio, mant):
        c = conta(o)
        tot += c["tri"]
        log(f"    {o.name}: {c['vert']} vertici, {c['tri']} triangoli ({c['quad']} quad), n-gon {c['ngon']}, "
            f"spigoli non-manifold {c['nonman']}, isole UV previste {c['isole']}")
        ok &= c["ngon"] == 0 and c["nonman"] == 0
    log(f"    TOTALE mesh di gioco (saio + mantellina + cappuccio): {tot} triangoli")
    for o in (saio_f, mant_f):
        c = conta(o)
        log(f"    {o.name}: {c['vert']} vertici, {c['tri']} triangoli, uno strato, spigoli non-manifold {c['nonman']}")
        ok &= c["nonman"] == 0
    for o in (saio, mant):
        d = distanze_con_segno(coordinate(o), bvh_pelle) / CM
        t = min(bvh_testa.find_nearest(Vector(c))[3] for c in coordinate(o)) / CM if bvh_testa else 99
        log(f"    {o.name} - pelle: min {d.min():.2f} cm (vertici dentro: {(d < 0).sum()}); dalla testa {t:.2f} cm")
        ok &= d.min() > 0.5 and t > 1.0
    bs, _ = bvh_oggetto(saio)
    bm_, _ = bvh_oggetto(mant)
    ref = bpy.data.objects["REF_Corpo"]
    bc = BVHTree.FromPolygons([ref.matrix_world @ v.co for v in ref.data.vertices], [list(p.vertices) for p in ref.data.polygons])
    x = (len(bc.overlap(bs)), len(bc.overlap(bm_)), len(bs.overlap(bm_)))
    a = (autointersezioni(saio), autointersezioni(mant))
    log(f"    Facce che attraversano: corpo/saio {x[0]}, corpo/mantellina {x[1]}, saio/mantellina {x[2]}; "
        f"auto-intersezioni saio {a[0]}, mantellina {a[1]}")
    ok &= sum(x) == 0 and sum(a) == 0
    return ok, tot


# =============================================================================
#  MAIN
# =============================================================================
def main(salva=True):
    log("=== REPORT FASE 4 - MESH DI GIOCO ===")
    for nome in ("REF_Corpo", "Saio_Blockout", "Mantellina_Blockout", "Saio_Drappeggio", "Mantellina_Drappeggio"):
        if bpy.data.objects.get(nome) is None:
            raise RuntimeError(f"Manca {nome}: apri Saio_Abate_v003.blend (Fase 3).")
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for nome in NOMI.values():
        rimuovi(nome)
    bvh_pelle, bvh_testa = pelle()
    saio_alto = bpy.data.objects["Saio_Drappeggio"]
    mant_alto = bpy.data.objects["Mantellina_Drappeggio"]

    # 1) punta del cappuccio (sul drappeggio alto: e' anche la fonte della normal map)
    sistema_punta(mant_alto, saio_alto)
    a = autointersezioni(mant_alto)
    bs, _ = bvh_oggetto(saio_alto)
    bm_, _ = bvh_oggetto(mant_alto)
    log(f"    Drappeggio dopo la correzione: auto-intersezioni mantellina {a}, incroci saio/mantellina {len(bs.overlap(bm_))}")

    # 2) mesh di gioco
    coll_g = prendi_collezione(COLL_GIOCO)
    saio, _ = mesh_gioco(bpy.data.objects["Saio_Blockout"], saio_alto, NOMI["saio"], coll_g)
    mant, _ = mesh_gioco(bpy.data.objects["Mantellina_Blockout"], mant_alto, NOMI["mant"], coll_g)
    for o, alto in ((saio, saio_alto), (mant, mant_alto)):
        m, p95, mx = fedelta(o, alto)
        log(f"[2] {o.name}: distanza della superficie alta da quella di gioco: media {m:.2f} cm, "
            f"95% {p95:.2f}, massimo {mx:.2f} (il resto va nella normal map)")

    # 3) mesh per la fisica (prima dello spessore: uno strato solo)
    coll_f = prendi_collezione(COLL_FISICA)
    saio_f, w_s = mesh_fisica(saio, NOMI["saio_f"], coll_f, "saio")
    mant_f, w_m = mesh_fisica(mant, NOMI["mant_f"], coll_f, "mantellina")
    log(f"[3] Mesh per la fisica: {saio_f.name} {len(saio_f.data.vertices)} vertici, "
        f"{mant_f.name} {len(mant_f.data.vertices)} vertici; proposta di liberta' media "
        f"{w_s.mean():.2f} nel saio (gonna e maniche libere) e {w_m.mean():.2f} nella mantellina")

    # 4) spessore ai bordi (solo sulle mesh di gioco)
    n1, f1 = aggiungi_bordi(saio, P["SPESSORE_SAIO"] * CM, bvh_pelle, z_max=P["SCOLLO_SOPRA"] * CM)
    n2, f2 = aggiungi_bordi(mant, P["SPESSORE_MANT"] * CM, bvh_pelle)
    log(f"[4] Spessore: saio {P['SPESSORE_SAIO']} cm su {n1} lati di bordo (+{f1} facce), "
        f"mantellina {P['SPESSORE_MANT']} cm su {n2} lati (+{f2} facce)")

    # 5) materiali, visibilita'
    lana = bpy.data.materials.get("M_Lana")
    for o in (saio, mant, saio_f, mant_f):
        o.data.materials.clear()
        if lana:
            o.data.materials.append(lana)
    log("[5] Controlli:")
    ok, tot = controlli(saio, mant, saio_f, mant_f, bvh_pelle, bvh_testa)
    for nome in ("BLOCKOUT", "DRAPPEGGIO", COLL_FISICA):
        lc = layer_collection(nome)
        if lc:
            lc.hide_viewport = True
    lc = layer_collection("FASE3_SIMULAZIONE")
    if lc:
        lc.exclude = True

    nuovo = None
    if salva and bpy.data.filepath:
        nuovo = os.path.join(os.path.dirname(bpy.data.filepath), NOME_FILE_V4)
        log(f"[6] Salvo come {nuovo} (il file v003 resta intatto)")
    elif salva:
        log("[6] File non salvato: usa File > Save As per salvarlo.")
    log("ESITO: " + ("tutti i controlli superati" if ok else "ATTENZIONE: qualche controllo non e' passato"))
    testo = bpy.data.texts.get("REPORT_Fase4") or bpy.data.texts.new("REPORT_Fase4")
    testo.clear()
    testo.write("\n".join(report) + "\n")
    if nuovo:
        bpy.ops.wm.save_as_mainfile(filepath=nuovo)
    return ok, testo


if __name__ == "__main__":
    ok, testo = main()
    spazio = getattr(bpy.context, "space_data", None)
    if spazio is not None and spazio.type == 'TEXT_EDITOR':
        spazio.text = testo
    wm = bpy.context.window_manager
    if wm.windows and not bpy.app.background:
        def disegna(self, context):
            for riga in report[:18]:
                self.layout.label(text=riga)
        wm.popup_menu(disegna, title="Fase 4: fatto" if ok else "Fase 4: controlla il report",
                      icon='INFO' if ok else 'ERROR')
