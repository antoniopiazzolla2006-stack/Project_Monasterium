# =============================================================================
#  FASE 3 - SIMULAZIONE DELLA STOFFA: saio e mantellina "cadono" sul corpo
#  Progetto: Abate francescano  (MetaHuman UE 5.8  ->  Blender 5.2  ->  UE 5.8)
#
#  COSA FA
#   Prende il blockout approvato (Fase 2) e lo fa cadere sul corpo con la
#   simulazione di stoffa di Blender (modificatore Cloth), in due strati:
#     1. il SAIO cade sul corpo; il cordone si stringe in vita (115 cm) e
#        raccoglie la lana in pieghe sopra e sotto; maniche e gonna si
#        appesantiscono e fanno le pieghe larghe della lana pesante;
#     2. MANTELLINA + CAPPUCCIO cadono sopra il saio gia' drappeggiato; la
#        cucitura del collo resta ferma, il collo arrotolato si assesta ma
#        tiene la forma.
#   Il risultato sono due mesh FERME (Saio_Drappeggio, Mantellina_Drappeggio)
#   nella collezione DRAPPEGGIO: sono la versione "alta" con tutte le pieghe.
#   Nella Fase 4 da qui ricaviamo la mesh di gioco, piu' leggera.
#   Poi: controlla compenetrazioni e distanze, scrive un rapporto e salva
#   Saio_Abate_v003.blend (il file v002 resta intatto).
#
#  PRIMA DI LANCIARLO
#   - Apri Saio_Abate_v002.blend (quello della Fase 2).
#  COME SI LANCIA
#   - Workspace "Scripting" > Text > Open > questo file > Run Script (Alt+P)
#   - ATTENZIONE: ci mette parecchi minuti e Blender sembra bloccato finche'
#     non finisce. Per vedere l'avanzamento: Window > Toggle System Console.
#   - Puoi rilanciarlo: ricrea da zero gli oggetti della Fase 3.
#  PER RIVEDERE LA CADUTA
#   - Nel file v003 la collezione FASE3_SIMULAZIONE (esclusa) contiene gli
#     oggetti con la simulazione vera: spunta la casella della collezione
#     nell'Outliner, vai al fotogramma 1 e premi Spazio (e' lenta: la calcola).
# =============================================================================

import bpy
import bmesh
import math
import os
import time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CM = 0.01   # 1 cm in unita' Blender (metri)

# ----------------------------- PARAMETRI -------------------------------------
P = dict(
    # --- tempi (fotogrammi a 24 al secondo) ---
    FOTOGRAMMI_SAIO=130,       # durata della caduta del saio
    FOTOGRAMMI_MANT=160,       # durata della caduta della mantellina
    CORDONE_DA=1,              # il cordone comincia a stringere...
    CORDONE_A=30,              # ...e ha finito qui
    # --- lana pesante (valori del pannello Physics > Cloth) ---
    MASSA=0.25,                # kg per vertice (la mesh e' fitta: tanti vertici leggeri)
    TENSIONE=60.0,             # resistenza ad allungarsi (la lana quasi non cede)
    COMPRESSIONE=30.0,         # piu' bassa della tensione: niente grinze minute
    TAGLIO=30.0,
    PIEGATURA=10.0,            # rigidita' alle pieghe: alto = pieghe larghe e tonde
    PIEGATURA_RINFORZI=40.0,   # balza e risvolti sono a doppio strato: piu' rigidi
    SMORZ_TENSIONE=10.0,
    SMORZ_PIEGATURA=1.0,
    SMORZ_ARIA=4.0,            # attrito con l'aria: aiuta la stoffa a fermarsi
    QUALITA=10,                # passi di calcolo per fotogramma
    QUALITA_COLLISIONI=5,
    # --- collisioni (cm) ---
    DIST_CORPO=0.8,            # la stoffa si ferma a DIST_CORPO + SPESSORE_CORPO
    SPESSORE_CORPO=0.7,        #   dalla pelle (= 1,5 cm: margine per le animazioni)
    ATTRITO_CORPO=8.0,         # la lana "fa presa" sulle spalle
    DIST_SE_STESSA=0.25,       # tra due pieghe che si toccano Blender tiene il DOPPIO
                               #   (0,5 cm): piu' alto, le parti vicine del blockout
                               #   (sotto le ascelle) partirebbero gia' "in urto"
    # --- cordone e scollo ---
    CORDONE_ARIA=1.5,          # cm tra pelle e stoffa sotto il cordone stretto
    #   scollo del saio: la fila del bordo e' ferma (1), le file sotto sempre meno
    PIN_SCOLLO=(1.0, 0.5, 0.3, 0.15, 0.05),
    # --- mantellina e cappuccio ---
    #   quanto resta "ancorato" ogni anello del cappuccio, dalla cucitura del
    #   collo (1 = fermo) verso l'esterno del collo arrotolato e poi lungo il
    #   lembo adagiato sul dorso (valori piccoli = lo tengono appoggiato)
    PIN_CAPPUCCIO=(1.0, 0.6, 0.35, 0.15, 0.1, 0.08, 0.06, 0.04, 0.02),
    RIGIDITA_PIN=3.0,
    STACCO_CAPPUCCIO=0.9,      # cm minimi tra cappuccio adagiato e mantellina alla partenza
    PIEGATURA_CAPPUCCIO=40.0,  # il cappuccio e' a doppio strato: piu' rigido (0 = come la mantellina)
    DIST_MANT=0.4,             # mantellina sopra il saio: DIST_MANT + SPESSORE_SAIO
    SPESSORE_SAIO=0.3,
)

COLL_SIM = "FASE3_SIMULAZIONE"
COLL_DRAPPEGGIO = "DRAPPEGGIO"
NOMI = dict(saio_sim="Saio_Sim", mant_sim="Mantellina_Sim",
            saio="Saio_Drappeggio", mant="Mantellina_Drappeggio")
NOME_FILE_V3 = "Saio_Abate_v003.blend"

report = []


def log(riga=""):
    print(riga, flush=True)
    report.append(riga)


# =============================================================================
#  1. IL CORPO
# =============================================================================
def scafo_convesso(P2):
    """Inviluppo convesso 2D (come un elastico teso attorno ai punti)."""
    P2 = np.unique(np.round(P2, 5), axis=0)
    P2 = P2[np.lexsort((P2[:, 1], P2[:, 0]))]

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P2:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(tuple(p))
    for p in P2[::-1]:
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(tuple(p))
    return np.array(lo[:-1] + up[:-1])


def raggio_poligono(H, origine, theta):
    """Distanza da 'origine' al bordo del poligono convesso H lungo l'angolo theta."""
    d = np.array([math.cos(theta), math.sin(theta)])
    best = 0.0
    for i in range(len(H)):
        p1, p2 = H[i], H[(i + 1) % len(H)]
        e = p2 - p1
        den = d[0] * e[1] - d[1] * e[0]
        if abs(den) < 1e-12:
            continue
        w = p1 - origine
        s = (w[0] * e[1] - w[1] * e[0]) / den
        u = (w[0] * d[1] - w[1] * d[0]) / den
        if s > 0 and -1e-9 <= u <= 1 + 1e-9:
            best = max(best, s)
    return best


class Corpo:
    """La pelle del MetaHuman (REF_Corpo): per misure, sezioni e controlli."""

    def __init__(self):
        ref = bpy.data.objects.get("REF_Corpo")
        if ref is None or ref.type != 'MESH':
            raise RuntimeError("Manca REF_Corpo: apri Saio_Abate_v002.blend (Fase 2).")
        self.ref = ref
        bm = bmesh.new()
        bm.from_mesh(ref.data)
        bm.transform(ref.matrix_world)
        # tiene solo il pezzo piu' grande (la pelle): via occhi, denti, ciglia
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
        bm.faces.ensure_lookup_table()
        self.bm = bm
        self.bvh = BVHTree.FromBMesh(bm)
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
        self.bvh_testa = BVHTree.FromPolygons(testa_v, testa_f) if testa_f else None
        tris = bm.calc_loop_triangles()
        V = np.array([v.co[:] for v in bm.verts])
        T = np.array([[l.vert.index for l in t] for t in tris])
        self.VT = V[T]
        self.tri_bvh = BVHTree.FromPolygons([Vector(p) for p in V], T.tolist())
        log(f"[1] Corpo: pelle {len(bm.verts)} vertici")

    def sezione(self, z):
        """Punti (x, y) dove il piano orizzontale z taglia la pelle."""
        VT = self.VT
        tz = VT[:, :, 2]
        out = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            za, zb = tz[:, a], tz[:, b]
            m = (za - z) * (zb - z) < 0
            if not m.any():
                continue
            t = (z - za[m]) / (zb[m] - za[m])
            p = VT[m, a] + (VT[m, b] - VT[m, a]) * t[:, None]
            out.append(p[:, :2])
        return np.vstack(out) if out else np.zeros((0, 2))

    def distanze(self, coords):
        """Distanza con segno di ogni punto dalla pelle (negativa = dentro)."""
        d = np.empty(len(coords))
        for i, c in enumerate(coords):
            p = Vector(c)
            loc, nor, idx, dist = self.bvh.find_nearest(p)
            d[i] = dist if (p - loc).dot(nor) >= 0 else -dist
        return d


# =============================================================================
#  2. UTILITA'
# =============================================================================
def prendi_collezione(nome, genitore=None):
    coll = bpy.data.collections.get(nome)
    if coll is None:
        coll = bpy.data.collections.new(nome)
    genitore = genitore or bpy.context.scene.collection
    if coll.name not in genitore.children:
        genitore.children.link(coll)
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


def coordinate(obj, valutate=True):
    """Coordinate dei vertici in spazio mondo (valutate = dopo i modificatori)."""
    if valutate:
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
    else:
        me = obj.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    if valutate:
        ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(obj.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def copia_liscia(sorgente, nome, coll, gruppi=None):
    """Nuovo oggetto con la superficie liscia (suddivisione applicata) della gabbia.
    gruppi: {nome_gruppo: {indice_vertice_gabbia: peso}} aggiunti alla gabbia
    prima della suddivisione (cosi' i pesi vengono sfumati come la superficie)."""
    tmp = sorgente.copy()
    tmp.data = sorgente.data.copy()
    bpy.context.scene.collection.objects.link(tmp)
    for gnome, pesi in (gruppi or {}).items():
        g = tmp.vertex_groups.get(gnome) or tmp.vertex_groups.new(name=gnome)
        for i, w in pesi.items():
            g.add([i], w, 'REPLACE')
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.name = nome
    ob = bpy.data.objects.new(nome, me)
    ob.matrix_world = sorgente.matrix_world.copy()
    ob.color = sorgente.color
    for nome_g in [g.name for g in tmp.vertex_groups]:   # i pesi sono gia' nella mesh
        if ob.vertex_groups.get(nome_g) is None:          # (servono solo i nomi, in ordine)
            ob.vertex_groups.new(name=nome_g)
    coll.objects.link(ob)
    vecchia = tmp.data
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.meshes.remove(vecchia)
    return ob


def pesi_gruppo(obj, nome):
    """Peso di ogni vertice nel gruppo 'nome' (0 se il vertice non c'e')."""
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


# =============================================================================
#  3. PREPARAZIONE DEL SAIO
# =============================================================================
def prepara_saio(corpo, coll):
    saio_bo = bpy.data.objects["Saio_Blockout"]
    ob = copia_liscia(saio_bo, NOMI["saio_sim"], coll)
    me = ob.data
    co = coordinate(ob, valutate=False)
    n = len(co)
    # anello del cordone: peso 1 nel gruppo della Fase 2 (sfumato dalla suddivisione)
    w_c = pesi_gruppo(ob, "Linea_Cordone")
    anello = np.where(w_c > 0.999)[0]
    # scollo: vertici di bordo sopra 1,40 m
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bordo = np.array([v.is_boundary for v in bm.verts])
    scollo = np.where(bordo & (co[:, 2] > 1.40))[0]
    # rinforzi (doppio strato): balza sotto la cucitura a 21 cm e risvolti delle maniche
    chiaro = me.attributes.get("chiaro")
    rinf = np.zeros(n)
    rinf[co[:, 2] < 0.215] = 1.0
    if chiaro is not None:
        for f in bm.faces:
            if chiaro.data[f.index].value > 0.5:
                for v in f.verts:
                    rinf[v.index] = 1.0
    bm.free()
    pin = np.zeros(n)
    pin[anello] = 1.0
    # scollo fermo + qualche fila sotto "trattenuta" sempre meno (P["PIN_SCOLLO"]):
    # lo sprone resta staccato dal collo come nel blockout
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    passi = {int(i): 0 for i in scollo}
    fronte = [int(i) for i in scollo]
    for k in range(1, len(P["PIN_SCOLLO"])):
        nuovo = []
        for i in fronte:
            for e in bm.verts[i].link_edges:
                j = e.other_vert(bm.verts[i]).index
                if j not in passi:
                    passi[j] = k
                    nuovo.append(j)
        fronte = nuovo
    bm.free()
    for i, k in passi.items():
        pin[i] = max(pin[i], P["PIN_SCOLLO"][k])
    imposta_gruppo(ob, "Pin", pin)
    imposta_gruppo(ob, "Rinforzi", rinf)

    # forma del cordone stretto: ogni vertice dell'anello va sul "giro" del corpo
    # (inviluppo convesso della sezione: il cordone non entra nelle conche) + aria
    z_c = float(np.mean(co[anello, 2]))
    sez = corpo.sezione(z_c)
    sez = sez[np.abs(sez[:, 0]) < 0.28]          # solo il busto: a quella quota ci sono anche le braccia
    H = scafo_convesso(sez)
    asse = np.array([0.0, float(np.mean(H[:, 1]))])
    stretto = co.copy()
    for i in anello:
        th = math.atan2(co[i, 1] - asse[1], co[i, 0] - asse[0])
        r = raggio_poligono(H, asse, th) + P["CORDONE_ARIA"] * CM
        stretto[i, 0] = asse[0] + r * math.cos(th)
        stretto[i, 1] = asse[1] + r * math.sin(th)

    def perimetro(pts):
        a = np.arctan2(pts[:, 1] - asse[1], pts[:, 0] - asse[0])
        q = pts[np.argsort(a)]
        return float(np.sum(np.linalg.norm(np.roll(q, -1, axis=0) - q, axis=1)))
    log(f"[2] Saio: {n} vertici; cordone a {z_c / CM:.1f} cm stringe la vita da "
        f"{perimetro(co[anello, :2]) / CM:.0f} a {perimetro(stretto[anello, :2]) / CM:.0f} cm "
        f"({len(anello)} vertici); scollo fermo ({len(scollo)} vertici); "
        f"rinforzi {int(rinf.sum())} vertici")
    if len(anello) == 0 or len(scollo) == 0:
        raise RuntimeError("anello del cordone o scollo non trovati")

    # shape key "Cordone": 0 = blockout, 1 = stretto; animata da CORDONE_DA a CORDONE_A
    Minv = np.array(ob.matrix_world.inverted())
    ob.shape_key_add(name="Basis", from_mix=False)
    sk = ob.shape_key_add(name="Cordone", from_mix=False)
    loc = stretto @ Minv[:3, :3].T + Minv[:3, 3]
    sk.data.foreach_set("co", loc.ravel())
    sk.value = 0.0
    sk.keyframe_insert("value", frame=P["CORDONE_DA"])
    sk.value = 1.0
    sk.keyframe_insert("value", frame=P["CORDONE_A"])
    return ob, anello


# =============================================================================
#  4. PREPARAZIONE DELLA MANTELLINA
# =============================================================================
def anelli_cappuccio(mant_bo):
    """Trova sulla gabbia la cucitura del collo (H0) e gli anelli del cappuccio,
    contando i passi dalla cucitura verso il collo arrotolato."""
    me = mant_bo.data
    adj = {i: set() for i in range(len(me.vertices))}
    cuc = {i: set() for i in range(len(me.vertices))}
    for e in me.edges:
        a, b = e.vertices
        adj[a].add(b)
        adj[b].add(a)
        if e.use_seam:
            cuc[a].add(b)
            cuc[b].add(a)
    # le cuciture formano un anello (collo) + linee aperte: si potano le foglie
    vivi = {i for i in cuc if cuc[i]}
    cambiato = True
    while cambiato:
        cambiato = False
        for i in list(vivi):
            if len(cuc[i] & vivi) < 2:
                vivi.discard(i)
                cambiato = True
    h0 = vivi
    if len(h0) < 8:
        raise RuntimeError("cucitura del collo non trovata sulla mantellina")
    # il grafo senza H0 si divide in due: mantellina (sotto) e cappuccio (sopra)
    z = {v.index: (mant_bo.matrix_world @ v.co).z for v in me.vertices}
    comp = {}
    for s in adj:
        if s in h0 or s in comp:
            continue
        cid = len(set(comp.values()))
        pila = [s]
        comp[s] = cid
        while pila:
            x = pila.pop()
            for y in adj[x]:
                if y not in h0 and y not in comp:
                    comp[y] = cid
                    pila.append(y)
    zmax = {}
    for i, c in comp.items():
        zmax[c] = max(zmax.get(c, -1e9), z[i])
    c_capp = max(zmax, key=zmax.get)
    # distanza (in passi) dalla cucitura, solo sul lato cappuccio
    passi = {i: 0 for i in h0}
    fronte = list(h0)
    while fronte:
        nuovo = []
        for x in fronte:
            for y in adj[x]:
                if y not in passi and comp.get(y) == c_capp:
                    passi[y] = passi[x] + 1
                    nuovo.append(y)
        fronte = nuovo
    return h0, passi


def prepara_mantellina(coll):
    mant_bo = bpy.data.objects["Mantellina_Blockout"]
    h0, passi = anelli_cappuccio(mant_bo)
    pin_pesi = {}
    for i, k in passi.items():
        if k < len(P["PIN_CAPPUCCIO"]) and P["PIN_CAPPUCCIO"][k] > 0:
            pin_pesi[i] = P["PIN_CAPPUCCIO"][k]
    # lato: 1 = cappuccio, 0 = mantellina, 0.5 = cucitura del collo
    lato = {i: (0.5 if i in h0 else (1.0 if i in passi else 0.0)) for i in range(len(mant_bo.data.vertices))}
    ob = copia_liscia(mant_bo, NOMI["mant_sim"], coll, gruppi={"Pin": pin_pesi, "Lato_Cappuccio": lato})
    w = pesi_gruppo(ob, "Pin")
    log(f"[4] Mantellina: {len(ob.data.vertices)} vertici; cucitura del collo "
        f"{len(h0)} vertici di gabbia; pin pieno {int((w > 0.999).sum())}, parziale "
        f"{int(((w > 0) & (w <= 0.999)).sum())} vertici")
    return ob


def separa_strati(ob, lato, stacco):
    """Allontana i vertici del cappuccio (lato > 0.75) dalle facce della mantellina
    (lato < 0.25) finche' non distano almeno 'stacco'."""
    me = ob.data
    Mw = ob.matrix_world
    co = [Mw @ v.co for v in me.vertices]
    facce = [list(p.vertices) for p in me.polygons if all(lato[i] < 0.25 for i in p.vertices)]
    if not facce:
        return 0
    bvh = BVHTree.FromPolygons(co, facce)
    n = 0
    Minv = Mw.inverted()
    for i, v in enumerate(me.vertices):
        if lato[i] <= 0.75:
            continue
        p = co[i]
        loc, nor, idx, dist = bvh.find_nearest(p)
        if loc is None or dist >= stacco:
            continue
        d = p - loc
        verso = d.normalized() if (d.length > 1e-6 and d.dot(nor) >= 0) else nor.normalized()
        v.co = Minv @ (loc + verso * stacco)
        n += 1
    return n


# =============================================================================
#  5. SIMULAZIONE
# =============================================================================
def collisione(obj, spessore_cm, attrito):
    mod = obj.modifiers.get("Collisione") or obj.modifiers.new("Collisione", 'COLLISION')
    c = obj.collision
    c.use = True
    c.thickness_outer = spessore_cm * CM
    c.cloth_friction = attrito
    c.damping = 0.1
    return mod


def area_per_vertice(obj):
    """Superficie di stoffa che ogni vertice rappresenta in media (m2)."""
    return sum(p.area for p in obj.data.polygons) / max(1, len(obj.data.vertices))


def stoffa(obj, gruppo_pin, rinforzi, dist_cm, rigidita_pin=1.0, fotogrammi=100, collisori=None, massa=None,
           piegatura_max=None):
    """collisori: collezione con gli unici oggetti contro cui urtare (None = tutti).
    massa: kg per vertice (None = P["MASSA"]).
    rinforzi / piegatura_max: gruppo dei vertici piu' rigidi e la loro rigidita'."""
    mod = obj.modifiers.new("Stoffa", 'CLOTH')
    s = mod.settings
    s.quality = P["QUALITA"]
    s.mass = P["MASSA"] if massa is None else massa
    s.air_damping = P["SMORZ_ARIA"]
    s.tension_stiffness = P["TENSIONE"]
    s.compression_stiffness = P["COMPRESSIONE"]
    s.shear_stiffness = P["TAGLIO"]
    s.bending_stiffness = P["PIEGATURA"]
    s.tension_damping = P["SMORZ_TENSIONE"]
    s.compression_damping = P["SMORZ_TENSIONE"]
    s.shear_damping = P["SMORZ_TENSIONE"]
    s.bending_damping = P["SMORZ_PIEGATURA"]
    s.vertex_group_mass = gruppo_pin          # in Blender il "Pin Group" si chiama cosi'
    s.pin_stiffness = rigidita_pin
    if rinforzi:
        s.vertex_group_bending = rinforzi
        s.bending_stiffness_max = P["PIEGATURA_RINFORZI"] if piegatura_max is None else piegatura_max
    c = mod.collision_settings
    c.use_collision = True
    c.distance_min = dist_cm * CM
    c.collision_quality = P["QUALITA_COLLISIONI"]
    c.use_self_collision = True
    c.self_distance_min = P["DIST_SE_STESSA"] * CM
    c.self_friction = 5.0
    if collisori is not None:
        c.collection = collisori
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = fotogrammi
    return mod


def simula(obj, fotogrammi, etichetta):
    """Fa avanzare la scena fotogramma per fotogramma (la stoffa si calcola cosi')."""
    sc = bpy.context.scene
    sc.frame_start = 1
    sc.frame_end = fotogrammi
    t0 = time.time()
    prec, moto, dove = None, [], None
    for f in range(1, fotogrammi + 1):
        sc.frame_set(f)
        if f >= fotogrammi - 3:
            co = coordinate(obj)
            if prec is not None:
                d = np.linalg.norm(co - prec, axis=1)
                moto.append(float(d.max()))
                dove = co[int(d.argmax())] / CM
            prec = co
        if f % 10 == 0 or f == fotogrammi:
            print(f"    {etichetta}: fotogramma {f}/{fotogrammi}  ({time.time() - t0:.0f} s)", flush=True)
    log(f"    {etichetta}: {fotogrammi} fotogrammi in {time.time() - t0:.0f} s; "
        f"movimento nell'ultimo fotogramma {moto[-1] / CM * 10:.2f} mm "
        f"(punto piu' mobile a x {dove[0]:.0f} y {dove[1]:.0f} z {dove[2]:.0f} cm)")
    return moto[-1]


def fissa(obj_sim, nome, coll):
    """Copia ferma della stoffa al fotogramma corrente (con cuciture e attributi)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj_sim.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.name = nome
    ob = bpy.data.objects.new(nome, me)
    ob.matrix_world = obj_sim.matrix_world.copy()
    ob.color = obj_sim.color
    for g in obj_sim.vertex_groups:
        if ob.vertex_groups.get(g.name) is None:
            ob.vertex_groups.new(name=g.name)
    coll.objects.link(ob)
    return ob


def fase_mantellina(saio_sim, saio, coll_sim, coll_dr):
    """Seconda caduta: mantellina e cappuccio sopra il saio gia' fermo."""
    sc = bpy.context.scene
    sc.frame_set(1)
    mant_sim = prepara_mantellina(coll_sim)
    collisione(saio, P["SPESSORE_SAIO"], 5.0)
    # la stoffa del saio si e' mossa: se qualche punto della mantellina e' finito
    # troppo vicino (o sotto), lo si alza prima di partire
    bvh_s, _, _ = bvh_oggetto(saio)
    serve = (P["DIST_MANT"] + P["SPESSORE_SAIO"] + 0.2) * CM
    Mw = mant_sim.matrix_world
    Minv = Mw.inverted()
    spostati = 0
    for v in mant_sim.data.vertices:
        p = Mw @ v.co
        loc, nor, idx, dist = bvh_s.find_nearest(p)
        sd = dist if (p - loc).dot(nor) >= 0 else -dist
        if sd < serve:
            v.co = Minv @ (p + nor.normalized() * (serve - sd))
            spostati += 1
    log(f"    Mantellina: {spostati} vertici alzati sopra il saio drappeggiato prima della caduta")
    # la superficie liscia avvicina la punta del cappuccio alla mantellina: se due
    # strati partono piu' vicini della distanza di auto-collisione (o incrociati),
    # la simulazione li "spara" via. Si staccano DOPO aver alzato la mantellina.
    sep = separa_strati(mant_sim, pesi_gruppo(mant_sim, "Lato_Cappuccio"), P["STACCO_CAPPUCCIO"] * CM)
    incroci = autointersezioni(mant_sim)
    log(f"    Cappuccio staccato dalla mantellina: {sep} vertici; incroci alla partenza: {incroci}")
    # le parti ferme (cucitura del collo e collo arrotolato) non partecipano alle
    # auto-collisioni: non possono spostarsi e "spingerebbero" il lembo del cappuccio
    w = pesi_gruppo(mant_sim, "Pin")
    imposta_gruppo(mant_sim, "Fermi", (w > 0.999).astype(float))
    # stessa lana del saio, ma la mesh della mantellina e' piu' fitta: ogni vertice
    # rappresenta meno stoffa, quindi pesa meno (stesso peso per metro quadro)
    massa_m = P["MASSA"] * area_per_vertice(mant_sim) / area_per_vertice(saio_sim)
    log(f"    Massa per vertice: saio {P['MASSA']:.3f} kg, mantellina {massa_m:.3f} kg (stessa lana al m2)")
    # il cappuccio vero e' un sacchetto a due strati: piu' rigido della mantellina
    mod = stoffa(mant_sim, "Pin", "Lato_Cappuccio" if P["PIEGATURA_CAPPUCCIO"] else None,
                 P["DIST_MANT"], rigidita_pin=P["RIGIDITA_PIN"], fotogrammi=P["FOTOGRAMMI_MANT"],
                 massa=massa_m, piegatura_max=P["PIEGATURA_CAPPUCCIO"])
    mod.collision_settings.vertex_group_self_collisions = "Fermi"
    log("[5] Simulazione di mantellina e cappuccio:")
    # durante la caduta della mantellina il saio e' fermo: la sua simulazione si spegne
    saio_sim.modifiers["Stoffa"].show_viewport = False
    saio_sim.modifiers["Stoffa"].show_render = False
    m_m = simula(mant_sim, P["FOTOGRAMMI_MANT"], "mantellina")
    mant = fissa(mant_sim, NOMI["mant"], coll_dr)
    return mant_sim, mant, m_m


# =============================================================================
#  6. CONTROLLI
# =============================================================================
def bvh_oggetto(obj):
    co = coordinate(obj, valutate=False)
    polys = [list(p.vertices) for p in obj.data.polygons]
    return BVHTree.FromPolygons([Vector(c) for c in co], polys), co, polys


def autointersezioni(obj):
    """Coppie di facce che si attraversano (escluse quelle che si toccano per costruzione)."""
    bvh, co, polys = bvh_oggetto(obj)
    sets = [set(p) for p in polys]
    n = 0
    for i, j in bvh.overlap(bvh):
        if i < j and not (sets[i] & sets[j]):
            n += 1
    return n


def allungamento(obj_sim, obj_fermo, escludi=()):
    """Quanto si e' allungata la stoffa rispetto alla forma di partenza (%):
    99-esimo percentile, massimo, lati tirati oltre il 20%, 1-esimo percentile."""
    a = coordinate(obj_sim, valutate=False)     # forma di riposo (blockout liscio)
    b = coordinate(obj_fermo, valutate=False)   # drappeggio
    E = np.array([e.vertices[:] for e in obj_fermo.data.edges])
    esc = set(int(i) for i in escludi)
    keep = np.array([not (int(x) in esc or int(y) in esc) for x, y in E])
    E = E[keep]
    la = np.linalg.norm(a[E[:, 0]] - a[E[:, 1]], axis=1)
    lb = np.linalg.norm(b[E[:, 0]] - b[E[:, 1]], axis=1)
    r = (lb / la - 1.0) * 100
    return np.percentile(r, 99), r.max(), int((r > 20).sum()), np.percentile(r, 1)


def controlli(corpo, saio, mant, saio_sim, mant_sim, anello):
    ok = True
    co_s = coordinate(saio, valutate=False)
    co_m = coordinate(mant, valutate=False)
    d_s = corpo.distanze(co_s) / CM
    d_m = corpo.distanze(co_m) / CM
    log(f"    Saio - pelle: min {d_s.min():.2f} cm, 5% {np.percentile(d_s, 5):.2f}, mediana {np.median(d_s):.2f}; "
        f"vertici dentro il corpo: {(d_s < 0).sum()}")
    log(f"    Mantellina - pelle: min {d_m.min():.2f} cm; vertici dentro il corpo: {(d_m < 0).sum()}")
    ok &= (d_s.min() > 0.5) and (d_m.min() > 0.5)
    bvh_s, _, _ = bvh_oggetto(saio)
    bvh_m, _, _ = bvh_oggetto(mant)
    x_cs = len(corpo.tri_bvh.overlap(bvh_s))
    x_cm = len(corpo.tri_bvh.overlap(bvh_m))
    x_sm = len(bvh_s.overlap(bvh_m))
    log(f"    Facce che attraversano: corpo/saio {x_cs}, corpo/mantellina {x_cm}, saio/mantellina {x_sm}")
    ok &= (x_cs == 0 and x_cm == 0 and x_sm == 0)
    a_s, a_m = autointersezioni(saio), autointersezioni(mant)
    log(f"    Auto-intersezioni (pieghe che si attraversano): saio {a_s}, mantellina {a_m}")
    ok &= (a_s == 0 and a_m == 0)
    # mantellina sopra il saio
    sotto, dmin = 0, 1e9
    for c in co_m:
        p = Vector(c)
        loc, nor, idx, dist = bvh_s.find_nearest(p)
        sd = dist if (p - loc).dot(nor) >= 0 else -dist
        dmin = min(dmin, sd)
    log(f"    Mantellina - saio: distanza minima {dmin / CM:.2f} cm")
    if corpo.bvh_testa is not None:
        t_s = min(corpo.bvh_testa.find_nearest(Vector(c))[3] for c in co_s) / CM
        t_m = min(corpo.bvh_testa.find_nearest(Vector(c))[3] for c in co_m) / CM
        log(f"    Dalla mesh della TESTA: saio {t_s:.2f} cm, mantellina/cappuccio {t_m:.2f} cm")
        ok &= t_s > 1.5 and t_m > 1.5
    # la lana quasi non si allunga: si guarda il 99% dei lati e i pochi lati "tirati"
    # (punti stretti come il cavo dell'ascella, dove due collisioni si stringono)
    a99, amax, a20, c01 = allungamento(saio_sim, saio, escludi=anello)
    log(f"    Allungamento del saio: 99% dei lati entro {a99:+.1f}%; lati tirati oltre il 20%: {a20} "
        f"(massimo {amax:+.1f}%)")
    m99, mmax, m20, mc01 = allungamento(mant_sim, mant)
    log(f"    Allungamento della mantellina: 99% dei lati entro {m99:+.1f}%; lati oltre il 20%: {m20} "
        f"(massimo {mmax:+.1f}%)")
    ok &= a99 < 6.0 and m99 < 8.0 and a20 <= 10 and m20 <= 10
    zs = co_s[:, 2]
    bm = bmesh.new()
    bm.from_mesh(saio.data)
    bm.verts.ensure_lookup_table()
    orlo = [v.index for v in bm.verts if v.is_boundary and co_s[v.index, 2] < 0.3]
    bm.free()
    zo = co_s[orlo, 2] / CM
    log(f"    Orlo: da {zo.min():.1f} a {zo.max():.1f} cm da terra")
    ok &= zo.min() > 5.0
    zc = co_s[anello, 2] / CM
    log(f"    Anello del cordone: z {zc.min():.1f}-{zc.max():.1f} cm")
    return ok


# =============================================================================
#  MAIN
# =============================================================================
def main(salva=True):
    t_inizio = time.time()
    log("=== REPORT FASE 3 - SIMULAZIONE DELLA STOFFA ===")
    for nome in ("REF_Corpo", "Saio_Blockout", "Mantellina_Blockout"):
        if bpy.data.objects.get(nome) is None:
            raise RuntimeError(f"Manca {nome}: apri Saio_Abate_v002.blend (Fase 2).")
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for nome in NOMI.values():
        rimuovi(nome)
    sc = bpy.context.scene
    sc.render.fps = 24
    sc.use_gravity = True
    sc.gravity = (0.0, 0.0, -9.81)
    coll_sim = prendi_collezione(COLL_SIM)
    coll_dr = prendi_collezione(COLL_DRAPPEGGIO)
    lc = layer_collection(COLL_SIM)
    if lc:
        lc.exclude = False
    corpo = Corpo()
    collisione(corpo.ref, P["SPESSORE_CORPO"], P["ATTRITO_CORPO"])

    # --- 1) saio ---
    saio_sim, anello = prepara_saio(corpo, coll_sim)
    # il saio urta solo il corpo (non la sua copia ferma, che nascera' piu' avanti)
    solo_corpo = corpo.ref.users_collection[0]
    stoffa(saio_sim, "Pin", "Rinforzi", P["DIST_CORPO"], fotogrammi=P["FOTOGRAMMI_SAIO"],
           collisori=solo_corpo)
    log("[3] Simulazione del saio:")
    m_s = simula(saio_sim, P["FOTOGRAMMI_SAIO"], "saio")
    saio = fissa(saio_sim, NOMI["saio"], coll_dr)

    # --- 2) mantellina sopra il saio fermo ---
    mant_sim, mant, m_m = fase_mantellina(saio_sim, saio, coll_sim, coll_dr)

    # --- 3) controlli ---
    log("[6] Controlli:")
    ok = controlli(corpo, saio, mant, saio_sim, mant_sim, anello)
    ok &= m_s < 0.002 and m_m < 0.002
    for o in (saio, mant):
        o.data.materials.clear()
        for m in bpy.data.objects["Saio_Blockout"].data.materials:
            o.data.materials.append(m)
        tri = sum(len(p.vertices) - 2 for p in o.data.polygons)
        log(f"    {o.name}: {len(o.data.vertices)} vertici, {tri} triangoli (versione alta, solo per le pieghe)")

    # --- visibilita' e pulizia ---
    saio_sim.modifiers["Stoffa"].show_viewport = True
    saio_sim.modifiers["Stoffa"].show_render = True
    sc.frame_set(1)
    corpo.bm.free()
    if lc:
        lc.exclude = True                     # simulazione esclusa: non si ricalcola da sola
    lb = layer_collection("BLOCKOUT")
    if lb:
        lb.hide_viewport = True
    for o in (saio, mant):
        o.data.shade_smooth()
    log(f"    Tempo totale: {(time.time() - t_inizio) / 60:.1f} minuti")
    nuovo = None
    if salva and bpy.data.filepath:
        nuovo = os.path.join(os.path.dirname(bpy.data.filepath), NOME_FILE_V3)
        log(f"[7] Salvo come {nuovo} (il file v002 resta intatto)")
    elif salva:
        log("[7] File non salvato: usa File > Save As per salvarlo.")
    log("ESITO: " + ("tutti i controlli superati" if ok else "ATTENZIONE: qualche controllo non e' passato"))
    testo = bpy.data.texts.get("REPORT_Fase3") or bpy.data.texts.new("REPORT_Fase3")
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
        wm.popup_menu(disegna, title="Fase 3: fatto" if ok else "Fase 3: controlla il report",
                      icon='INFO' if ok else 'ERROR')
