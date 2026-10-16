# =============================================================================
#  FASE 2 - BLOCKOUT: saio, mantellina e cappuccio abbassato
#  Progetto: Abate francescano  (MetaHuman UE 5.8  ->  Blender 5.2  ->  UE 5.8)
#
#  COSA FA
#   Costruisce attorno a REF_Corpo (il corpo della Fase 1) una "gabbia"
#   (blockout) low-poly, tutta in quad (facce a 4 lati), in A-pose:
#     - Saio_Blockout       : saio fino alle caviglie, sprone sulle spalle,
#                             maniche ampie con risvolto, balza all'orlo,
#                             anello di vertici sulla linea del cordone
#     - Mantellina_Blockout : mantellina corta sulle spalle, cucita al
#                             cappuccio abbassato (collo arrotolato + cappuccio
#                             adagiato sul dorso)
#   Poi: segna le cuciture (seam) dove starebbero quelle vere, controlla le
#   distanze dal corpo, scrive un rapporto e salva Saio_Abate_v002.blend
#   (il file v001 resta intatto).
#
#  PERCHE' UNA GABBIA
#   E' lo "scheletro" del vestito: poche facce ordinate che decidono forma,
#   aria intorno al corpo e cuciture. Nella Fase 3 la suddivideremo (ogni quad
#   diventa 4, poi 16) e la faremo cadere con la simulazione di stoffa.
#
#  PRIMA DI LANCIARLO
#   - Apri Saio_Abate_v001.blend (quello creato nella Fase 1).
#  COME SI LANCIA
#   - Workspace "Scripting" > Text > Open > questo file > Run Script (Alt+P)
#   - Puoi rilanciarlo quante volte vuoi: ricrea i due oggetti da zero.
#   - Per cambiare la forma modifica i numeri in PARAMETRI (sono centimetri)
#     e rilancia.
# =============================================================================

import bpy
import bmesh
import math
import os
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CM = 0.01   # 1 cm in unita' Blender (metri)

# ----------------------------- PARAMETRI (cm) --------------------------------
P = dict(
    # --- saio: altezze da terra ---
    Z_ORLO=10.0,            # orlo: poco sopra la caviglia (osso a 8,7 cm)
    Z_BALZA=21.0,           # cucitura della balza (fascia in fondo, come nella foto)
    Z_CORDONE=115.0,        # linea del cordone = vita naturale
    Z_ASCELLA=129.0,        # fondo del giro manica (3-4 cm sotto l'ascella)
    Z_ANCA=91.0,            # da qui in giu' la gonna si allarga
    Z_INVILUPPO_MAX=131.0,  # il saio "cade" dal punto piu' sporgente sotto questa quota
    # --- saio: aria tra corpo e stoffa ---
    AGIO=3.0,               # davanti e ai fianchi
    AGIO_SCHIENA=3.5,       # dietro (serve per chinarsi)
    ARIA_MIN=2.5,           # distanza minima dalla pelle (sprone, maniche)
    ARIA_SPALLA=1.5,        # sulle spalle il saio appoggia
    ARIA_COLLO=3.0,         # scollo staccato dalla mesh della testa (non nascondibile)
    ARIA_LISCIA=1.5,        # minimo per la superficie liscia (dopo la suddivisione)
    ARIA_TESTA=2.5,         # ... e vicino alla mesh della testa
    # --- gonna: orlo ellittico ---
    ORLO_SEMIASSE_X=33.0,   # meta' larghezza dell'orlo (fianco-fianco)
    ORLO_SEMIASSE_Y=29.0,   # meta' profondita' dell'orlo (davanti-dietro)
    SVASATURA=1.1,          # >1: la gonna si apre di piu' verso il fondo
    # --- spalle e scollo ---
    SPALLA_X=22.0,          # punto spalla (fine cucitura spalla, inizio manica)
    SCOLLO_Z_DAVANTI=147.5,
    SCOLLO_Z_FIANCO=152.5,
    SCOLLO_Z_DIETRO=153.0,
    # --- maniche: anelli lungo il braccio (cm dalla spalla) ---
    #   (posizione sopra, posizione sotto, raggio, spostamento verso l'alto)
    #   sopra e sotto diversi = anello inclinato (vicino all'ascella)
    MANICA_ANELLI=[(4, 16, 8.5, 1.5), (12, 21, 9.0, 1.0), (20, 26, 9.4, 0.5),
                   (29, 31, 9.8, 0.0), (37, 37, 10.1, 0.0), (43, 43, 10.6, 0.0),
                   (49, 49, 10.8, 0.0), (55, 55, 11.0, 0.0)],
    ANELLO_RISVOLTO=6,      # dall'anello 6 al 8: risvolto rivoltato (colore chiaro)
    # --- mantellina ---
    STRATO=1.2,             # distanza tra mantellina e saio (spessore lana + aria)
    STRATO_CAPPUCCIO=1.6,   # distanza tra cappuccio (rotolo e lembo) e mantellina
    MANT_DAVANTI=21.0,      # lunghezza dal collo, misurata sulla stoffa
    MANT_FIANCO=15.0,
    MANT_DIETRO=25.0,
    # --- cappuccio abbassato ---
    ROTOLO_SALITA_DIETRO=4.0,   # quanto sale il collo arrotolato dietro
    ROTOLO_SALITA_DAVANTI=1.6,  # ... e davanti (forma a U)
    ROTOLO_SPESSORE=4.6,        # quanto sporge il rotolo
    CAPPUCCIO_LUNGH=20.0,       # quanto scende il cappuccio sul dorso
    CAPPUCCIO_PUNTA=3.0,        # punta arrotondata in fondo
)

N_TORSO = 24                    # colonne attorno al busto (15 gradi l'una)
N_MANICA = 12                   # vertici attorno a ogni manica
N_COLLO = 24                    # colonne attorno al collo (mantellina)

COLL_BLOCKOUT = "BLOCKOUT"
NOME_SAIO = "Saio_Blockout"
NOME_MANT = "Mantellina_Blockout"
NOME_FILE_V2 = "Saio_Abate_v002.blend"

report = []


def log(riga=""):
    print(riga)
    report.append(riga)


# =============================================================================
#  1. IL CORPO: pelle, sezioni, ossa
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
    def __init__(self):
        ref = bpy.data.objects.get("REF_Corpo")
        if ref is None or ref.type != 'MESH':
            raise RuntimeError("Manca REF_Corpo: apri Saio_Abate_v001.blend (Fase 1).")
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
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        self.bm = bm
        self.bvh = BVHTree.FromBMesh(bm)
        # mesh della TESTA (non nascondibile in Unreal): facce con UV nel riquadro u<1
        uv = bm.loops.layers.uv.active
        testa_v, testa_f, mappa = [], [], {}
        self.facce_testa = set()
        if uv is not None:
            for f in bm.faces:
                if sum(l[uv].uv.x for l in f.loops) / len(f.loops) < 1.0:
                    self.facce_testa.add(f.index)
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
        # ossa (posizioni in metri, spazio mondo)
        self.ossa = {}
        arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'
                    and "upperarm_l" in o.data.bones), None)
        default = {"upperarm_l": (19.83, 2.17, 143.27), "lowerarm_l": (37.94, 1.37, 119.55),
                   "hand_l": (50.59, -14.12, 104.39)}
        for nome, val in default.items():
            if arm is not None:
                self.ossa[nome] = arm.matrix_world @ arm.data.bones[nome].head_local
            else:
                self.ossa[nome] = Vector(val) * CM
        log(f"[1] Corpo: pelle {len(bm.verts)} vertici, testa {len(testa_f)} facce; "
            f"ossa {'dallo scheletro' if arm else 'di riserva'}")

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

    def z_sopra(self, x, y):
        """Quota della pelle vista dall'alto nel punto (x, y)."""
        hit = self.bvh.ray_cast(Vector((x, y, 2.5)), Vector((0, 0, -1)))
        return hit[0].z if hit[0] is not None else None

    def distanza(self, p):
        """Distanza con segno dalla pelle (negativa = dentro il corpo)."""
        loc, nor, idx, dist = self.bvh.find_nearest(p)
        if loc is None:
            return 1e9
        return dist if (p - loc).dot(nor) >= 0 else -dist


def spingi_fuori(p, bvh, aria, giri=4):
    """Se p e' dentro una superficie o piu' vicino di 'aria', lo sposta fuori."""
    p = p.copy()
    for _ in range(giri):
        loc, nor, idx, dist = bvh.find_nearest(p)
        if loc is None:
            return p
        v = p - loc
        fuori = v.dot(nor) >= 0
        if fuori and dist >= aria - 1e-6:
            return p
        d = v.normalized() if (fuori and v.length > 1e-9) else nor.normalized()
        p = loc + d * aria
    return p


# =============================================================================
#  2. SAIO
# =============================================================================
def costruisci_saio(corpo):
    th = [math.radians(15.0 * j) for j in range(N_TORSO)]   # j=0: fianco sinistro (+X)
    # --- assi e misure dal corpo ---
    z_tab = list(range(int(P["Z_ANCA"]), int(P["Z_INVILUPPO_MAX"]) + 1))
    sezioni = {}
    for zc in z_tab:
        S2 = corpo.sezione(zc * CM)
        S2 = S2[np.abs(S2[:, 0]) < 0.21]        # solo busto: le braccia stanno oltre 21 cm
        sezioni[zc] = scafo_convesso(S2)
    y_ref = float(np.mean([(H[:, 1].min() + H[:, 1].max()) / 2 for H in sezioni.values()]))
    asse = np.array([0.0, y_ref])
    rho = {zc: [raggio_poligono(H, asse, t) for t in th] for zc, H in sezioni.items()}
    collo = corpo.sezione(156 * CM)
    collo = collo[np.abs(collo[:, 0]) < 0.12]
    y_n = float((collo[:, 1].min() + collo[:, 1].max()) / 2)
    a_n = float(collo[:, 0].max() - collo[:, 0].min()) / 2
    b_n = float(collo[:, 1].max() - collo[:, 1].min()) / 2
    log(f"[2] Asse del busto y={y_ref/CM:.1f} cm; collo a z=156: semiassi "
        f"{a_n/CM:.1f} x {b_n/CM:.1f} cm, centro y={y_n/CM:.1f}")

    def agio(j):
        return (P["AGIO"] + (P["AGIO_SCHIENA"] - P["AGIO"]) * max(0.0, math.sin(th[j]))) * CM

    def dir2(j):
        return Vector((math.cos(th[j]), math.sin(th[j]), 0.0))

    # --- anelli del busto e della gonna (dall'ascella all'orlo) ---
    z_busto = [129.0, 122.0, 115.0, 109.0, 103.0, 97.0, 91.0]
    z_busto[0] = P["Z_ASCELLA"]
    z_busto[2] = P["Z_CORDONE"]
    z_busto[-1] = P["Z_ANCA"]
    n_gonna = 9
    z_gonna = [P["Z_ANCA"] + (P["Z_BALZA"] - P["Z_ANCA"]) * i / n_gonna for i in range(1, n_gonna + 1)]
    z_anelli = z_busto + z_gonna + [(P["Z_BALZA"] + P["Z_ORLO"]) / 2, P["Z_ORLO"]]

    def punto_busto(z, j):
        zc_list = [zc for zc in z_tab if zc >= z - 1e-6] or [z_tab[-1]]
        r = max(rho[zc][j] for zc in zc_list)
        return Vector((0, y_ref, z * CM)) + dir2(j) * (r + agio(j))

    a_o, b_o = P["ORLO_SEMIASSE_X"] * CM, P["ORLO_SEMIASSE_Y"] * CM
    torso = []
    for z in z_anelli:
        anello = []
        for j in range(N_TORSO):
            if z >= P["Z_ANCA"] - 1e-6:
                anello.append(punto_busto(z, j))
            else:
                p_anca = punto_busto(P["Z_ANCA"], j)
                c, s = math.cos(th[j]), math.sin(th[j])
                r_e = a_o * b_o / math.sqrt((b_o * c) ** 2 + (a_o * s) ** 2)
                p_orlo = Vector((0, y_ref, P["Z_ORLO"] * CM)) + dir2(j) * r_e
                t = ((P["Z_ANCA"] - z) / (P["Z_ANCA"] - P["Z_ORLO"])) ** P["SVASATURA"]
                q = p_anca.lerp(p_orlo, t)
                q.z = z * CM
                anello.append(q)
        torso.append(anello)

    # --- punti in cima: scollo e cuciture delle spalle ---
    def scollo(theta_deg):
        t = math.radians(theta_deg)
        s = math.sin(t)
        z = P["SCOLLO_Z_FIANCO"] + (P["SCOLLO_Z_DIETRO"] - P["SCOLLO_Z_FIANCO"]) * max(0.0, s) \
            + (P["SCOLLO_Z_DAVANTI"] - P["SCOLLO_Z_FIANCO"]) * max(0.0, -s)
        a = a_n + P["ARIA_COLLO"] * CM
        b = b_n + P["ARIA_COLLO"] * CM
        p = Vector((a * math.cos(t), y_n + b * math.sin(t), z * CM))
        return spingi_fuori(p, corpo.bvh, P["ARIA_COLLO"] * CM)

    y_spalla = corpo.ossa["upperarm_l"].y - 1.0 * CM

    def spalla(x):
        zt = corpo.z_sopra(x, y_spalla) or 1.49
        p = Vector((x, y_spalla, zt + P["ARIA_SPALLA"] * CM))
        return spingi_fuori(p, corpo.bvh, P["ARIA_SPALLA"] * CM)

    x_nk = a_n + P["ARIA_COLLO"] * CM
    x_sp = P["SPALLA_X"] * CM
    cima = {
        "Lnk": scollo(0), "B3": scollo(45), "Bc": scollo(90), "B1": scollo(135),
        "Rnk": scollo(180), "F1": scollo(225), "Fc": scollo(270), "F3": scollo(315),
        "Lsp": spalla(x_sp), "Ls1": spalla((x_nk + x_sp) / 2),
    }
    for k in ("sp", "s1"):
        q = cima["L" + k]
        cima["R" + k] = Vector((-q.x, q.y, q.z))
    cima_davanti = {14: "Rsp", 15: "Rs1", 16: "Rnk", 17: "F1", 18: "Fc", 19: "F3",
                    20: "Lnk", 21: "Ls1", 22: "Lsp"}
    cima_dietro = {10: "Rsp", 9: "Rs1", 8: "Rnk", 7: "B1", 6: "Bc", 5: "B3",
                   4: "Lnk", 3: "Ls1", 2: "Lsp"}

    # --- sprone (yoke): pannelli davanti e dietro tra ascella e spalle ---
    sprone_f, sprone_b = {}, {}
    for j, nome in cima_davanti.items():
        for r in (1, 2, 3):
            p = torso[0][j].lerp(cima[nome], r / 4)
            sprone_f[(r, j)] = spingi_fuori(p, corpo.bvh, P["ARIA_MIN"] * CM)
    for j, nome in cima_dietro.items():
        for r in (1, 2, 3):
            p = torso[0][j].lerp(cima[nome], r / 4)
            sprone_b[(r, j)] = spingi_fuori(p, corpo.bvh, P["ARIA_MIN"] * CM)

    # --- manica sinistra (la destra e' lo specchio) ---
    S = corpo.ossa["upperarm_l"]
    E = corpo.ossa["lowerarm_l"]
    W = corpo.ossa["hand_l"]
    L1, L2 = (E - S).length, (W - E).length
    a1, a2 = (E - S).normalized(), (W - E).normalized()

    def asse_braccio(s_cm):
        s = s_cm * CM
        if s <= L1:
            p = S + a1 * s
        else:
            p = E + a2 * (s - L1)
        # tangente sfumata attorno al gomito (+-4 cm)
        w = min(1.0, max(0.0, (s - (L1 - 0.04)) / 0.08))
        t = (a1 * (1 - w) + a2 * w).normalized()
        up = (Vector((0, 0, 1)) - t * t.z).normalized()
        avanti = t.cross(up).normalized()
        if avanti.y > 0:                     # deve puntare verso il davanti (-Y)
            avanti = -avanti
        return p, up, avanti

    phi_u = [2 * math.pi * k / N_MANICA for k in range(N_MANICA)]
    anelli_manica = []
    for (s_su, s_giu, R, ecc) in P["MANICA_ANELLI"]:
        anello = []
        for k in range(N_MANICA):
            ph = phi_u[k]
            s_k = s_giu + (s_su - s_giu) * (1 + math.cos(ph)) / 2
            p, up, avanti = asse_braccio(s_k)
            q = p + up * (ecc * CM) + (up * math.cos(ph) + avanti * math.sin(ph)) * (R * CM)
            anello.append(q)
        anelli_manica.append(anello)
    for i, anello in enumerate(anelli_manica):
        aria = (2.0 if i == 0 else P["ARIA_MIN"]) * CM
        anelli_manica[i] = [spingi_fuori(q, corpo.bvh, aria) for q in anello]

    # =========================================================================
    #  Topologia: un solo BMesh, vertici condivisi dove i pezzi si cuciono
    # =========================================================================
    bm = bmesh.new()
    V = {}

    def vert(chiave, co):
        if chiave not in V:
            V[chiave] = bm.verts.new(co)
        return V[chiave]

    for k, anello in enumerate(torso):
        for j, co in enumerate(anello):
            vert(("T", k, j), co)
    for nome, co in cima.items():
        vert(("C", nome), co)
    for (r, j), co in sprone_f.items():
        vert(("F", r, j), co)
    for (r, j), co in sprone_b.items():
        vert(("B", r, j), co)

    def davanti(r, j):
        if r == 0:
            return V[("T", 0, j)]
        if r == 4:
            return V[("C", cima_davanti[j])]
        return V[("F", r, j)]

    def dietro(r, j):
        if r == 0:
            return V[("T", 0, j)]
        if r == 4:
            return V[("C", cima_dietro[j])]
        return V[("B", r, j)]

    facce = []
    K = len(torso)
    for k in range(K - 1):
        for j in range(N_TORSO):
            j2 = (j + 1) % N_TORSO
            facce.append(("busto", [V[("T", k, j)], V[("T", k + 1, j)],
                                    V[("T", k + 1, j2)], V[("T", k, j2)]]))
    for r in range(4):
        for j in range(14, 22):
            facce.append(("sprone", [davanti(r, j), davanti(r + 1, j),
                                     davanti(r + 1, j + 1), davanti(r, j + 1)]))
        for j in range(2, 10):
            facce.append(("sprone", [dietro(r, j), dietro(r, j + 1),
                                     dietro(r + 1, j + 1), dietro(r + 1, j)]))

    # giro manica (anello 0): spalla, bordo davanti, sotto-ascella, bordo dietro
    giro = {
        "L": [V[("C", "Lsp")], V[("F", 3, 22)], V[("F", 2, 22)], V[("F", 1, 22)],
              V[("T", 0, 22)], V[("T", 0, 23)], V[("T", 0, 0)], V[("T", 0, 1)],
              V[("T", 0, 2)], V[("B", 1, 2)], V[("B", 2, 2)], V[("B", 3, 2)]],
        "R": [V[("C", "Rsp")], V[("F", 3, 14)], V[("F", 2, 14)], V[("F", 1, 14)],
              V[("T", 0, 14)], V[("T", 0, 13)], V[("T", 0, 12)], V[("T", 0, 11)],
              V[("T", 0, 10)], V[("B", 1, 10)], V[("B", 2, 10)], V[("B", 3, 10)]],
    }
    anelli = {"L": [giro["L"]], "R": [giro["R"]]}
    for i, anello in enumerate(anelli_manica):
        anelli["L"].append([vert(("SL", i + 1, k), co) for k, co in enumerate(anello)])
        anelli["R"].append([vert(("SR", i + 1, k), Vector((-co.x, co.y, co.z)))
                            for k, co in enumerate(anello)])
    for lato in ("L", "R"):
        A = anelli[lato]
        for i in range(len(A) - 1):
            zona = "risvolto" if i + 1 > P["ANELLO_RISVOLTO"] else "manica"
            for k in range(N_MANICA):
                k2 = (k + 1) % N_MANICA
                facce.append((zona, [A[i][k], A[i + 1][k], A[i + 1][k2], A[i][k2]]))

    zone = {}
    for zona, vv in facce:
        f = bm.faces.new(vv)
        zone[f] = zona
    bm.verts.index_update()
    bm.faces.index_update()

    # --- rilassamento: spaziatura uniforme di sprone e maniche ---
    fissi = set()
    for k in range(K):
        for j in range(N_TORSO):
            fissi.add(V[("T", k, j)])
    for nome in cima:
        fissi.add(V[("C", nome)])
    for lato in ("L", "R"):
        for i in range(P["ANELLO_RISVOLTO"], len(anelli[lato])):
            fissi.update(anelli[lato][i])
    mobili = [v for v in bm.verts if v not in fissi]
    rilassa(bm, mobili, corpo.bvh, P["ARIA_MIN"] * CM, giri=20)

    # --- simmetria perfetta sinistra/destra ---
    simmetrizza(bm)

    # --- la superficie liscia non deve toccare il corpo ---
    resto = correggi_liscia(bm, [vincolo_pelle(corpo, P["ARIA_LISCIA"] * CM, P["ARIA_TESTA"] * CM)])
    log(f"[2] Correzione superficie liscia del saio: scarto residuo {resto/CM:.2f} cm")

    # --- orientamento delle facce verso l'esterno ---
    orienta_fuori(bm, corpo.bvh)

    info = dict(y_ref=y_ref, y_n=y_n, a_n=a_n, b_n=b_n, V=V, anelli=anelli, zone=zone,
                K=K, z_anelli=z_anelli, cima=cima)
    return bm, info


def rilassa(bm, mobili, bvh, aria, giri=20, forza=0.5):
    """Laplaciano tangenziale: ogni vertice scivola verso il centro dei vicini
    restando sulla superficie, poi viene rispinto fuori dal corpo."""
    for _ in range(giri):
        bm.normal_update()
        nuovi = {}
        for v in mobili:
            vic = [e.other_vert(v).co for e in v.link_edges]
            c = sum(vic, Vector()) / len(vic)
            d = c - v.co
            n = v.normal
            d_t = d - n * d.dot(n)
            nuovi[v] = v.co + d_t * forza
        for v, co in nuovi.items():
            v.co = spingi_fuori(co, bvh, aria)


def simmetrizza(bm, toll=0.02):
    """Rende la gabbia speculare rispetto al piano X=0."""
    bm.verts.ensure_lookup_table()
    co = np.array([v.co[:] for v in bm.verts])
    specchio = co * np.array([-1.0, 1.0, 1.0])
    from mathutils.kdtree import KDTree
    kd = KDTree(len(co))
    for i, c in enumerate(co):
        kd.insert(c, i)
    kd.balance()
    fatti = set()
    for i, v in enumerate(bm.verts):
        if i in fatti:
            continue
        _, j, dist = kd.find(specchio[i])
        if j is None or dist > toll:
            continue
        if j == i:
            v.co.x = 0.0
            fatti.add(i)
            continue
        a = Vector(co[i])
        b = Vector(specchio[j])
        m = (a + b) / 2
        bm.verts[i].co = m
        bm.verts[j].co = Vector((-m.x, m.y, m.z))
        fatti.update((i, j))


def superficie_da_bm(bm, livelli=2):
    """Superficie suddivisa di una gabbia ancora in BMesh (oggetto temporaneo)."""
    me = bpy.data.meshes.new("_tmp_sup")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("_tmp_sup", me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("s", 'SUBSURF')
    mod.levels = livelli
    bm_v, bvh_v = superficie_valutata(ob)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)
    return bm_v, bvh_v


def correggi_liscia(bm, vincoli, giri=10, simm=True):
    """Corregge la gabbia finche' la superficie LISCIA (suddivisa) rispetta le
    distanze minime. Serve perche' la suddivisione arrotonda e 'taglia gli
    angoli': tra due vertici a posto la superficie puo' entrare nel corpo.
    vincoli: funzioni p -> (mancanza, direzione); mancanza <= 0 vuol dire ok."""
    from mathutils.kdtree import KDTree
    peggio = 0.0
    for _ in range(giri):
        bm_v, _bvh = superficie_da_bm(bm)
        bm.verts.ensure_lookup_table()
        kd = KDTree(len(bm.verts))
        for v in bm.verts:
            kd.insert(v.co, v.index)
        kd.balance()
        spinte = {}
        peggio = 0.0
        for v in bm_v.verts:
            for f in vincoli:
                manca, d = f(v.co)
                if manca <= 0:
                    continue
                peggio = max(peggio, manca)
                for (co, i, dist), w in zip(kd.find_n(v.co, 3), (1.0, 0.7, 0.45)):
                    s = d * (manca * w)
                    if i not in spinte or s.length > spinte[i].length:
                        spinte[i] = s
        bm_v.free()
        if peggio < 0.0005:
            break
        for i, s in spinte.items():
            bm.verts[i].co += s * 1.15
        if simm:
            simmetrizza(bm)
    return peggio


def vincolo_pelle(corpo, aria, aria_testa):
    """Distanza minima dalla pelle; piu' aria dove c'e' la mesh della testa."""
    def f(p):
        loc, nor, idx, dist = corpo.bvh.find_nearest(p)
        if loc is None:
            return 0.0, None
        sd = dist if (p - loc).dot(nor) >= 0 else -dist
        obiettivo = aria_testa if idx in corpo.facce_testa else aria
        return obiettivo - sd, nor
    return f


def vincolo_strato(bvh_s, aria, z_scollo=1.44):
    """La mantellina deve restare SOPRA il saio di almeno 'aria'."""
    def f(p):
        loc, nor, idx, dist = bvh_s.find_nearest(p)
        if loc is None:
            return 0.0, None
        v = p - loc
        if v.dot(nor) < 0 and p.z > loc.z + 0.005 and loc.z > z_scollo:
            return 0.0, None        # sopra lo scollo del saio: non e' "sotto"
        sd = dist if v.dot(nor) >= 0 else -dist
        return aria - sd, nor
    return f


def orienta_fuori(bm, bvh):
    """Normali coerenti e rivolte via dal corpo (voto di maggioranza)."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    voti = 0
    for f in bm.faces:
        c = f.calc_center_median()
        loc, nor, idx, dist = bvh.find_nearest(c)
        if loc is not None:
            voti += 1 if f.normal.dot(c - loc) > 0 else -1
    if voti < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()


# =============================================================================
#  3. MANTELLINA + CAPPUCCIO ABBASSATO
# =============================================================================
def superficie_valutata(obj):
    """BVH della superficie suddivisa (come la vedi col modificatore attivo)."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(obj.matrix_world)
    ev.to_mesh_clear()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return bm, BVHTree.FromBMesh(bm)


def costruisci_mantellina(corpo, info, saio_obj):
    bm_s, bvh_s = superficie_valutata(saio_obj)
    y_n = info["y_n"]
    asse_collo = Vector((0, y_n, 0))
    strato = P["STRATO"] * CM
    strato_c = P["STRATO_CAPPUCCIO"] * CM

    # --- bordo dello scollo del saio (curva liscia) ---
    bordo = [e for e in bm_s.edges if e.is_boundary]
    pts = []
    for e in bordo:
        for v in e.verts:
            if v.co.z > 1.38 and abs(v.co.x) < 0.2:
                pts.append(v.co.copy())
    ang_pts = sorted(((math.atan2(p.y - y_n, p.x) % (2 * math.pi), p) for p in pts),
                     key=lambda t: t[0])

    def punto_scollo(theta):
        theta %= 2 * math.pi
        for i in range(len(ang_pts)):
            a0, p0 = ang_pts[i]
            a1, p1 = ang_pts[(i + 1) % len(ang_pts)]
            if i == len(ang_pts) - 1:
                a1 += 2 * math.pi
                if theta < a0:
                    theta += 2 * math.pi
            if a0 <= theta <= a1:
                t = (theta - a0) / max(a1 - a0, 1e-9)
                return p0.lerp(p1, t)
        return ang_pts[0][1]

    def snap(p, bvh, off):
        loc, nor, idx, dist = bvh.find_nearest(p)
        return loc + nor * off, nor

    thc = [2 * math.pi * c / N_COLLO for c in range(N_COLLO)]
    # H0: cucitura collo (mantellina + cappuccio), poco fuori e sopra lo scollo
    H0 = []
    for t in thc:
        q = punto_scollo(t)
        out = Vector((math.cos(t), math.sin(t), 0))
        p = q + out * (1.0 * CM) + Vector((0, 0, 0.5 * CM))
        p = spingi_fuori(p, corpo.bvh, P["ARIA_COLLO"] * CM)
        H0.append(p)

    # --- mantellina: si "cammina" sulla stoffa del saio dal collo verso il basso ---
    Q = Vector((0, y_n, 1.62))

    def lunghezza(t):
        s = math.sin(t)
        return (P["MANT_FIANCO"] + (P["MANT_DIETRO"] - P["MANT_FIANCO"]) * max(0.0, s) ** 1.2
                + (P["MANT_DAVANTI"] - P["MANT_FIANCO"]) * max(0.0, -s) ** 1.2) * CM

    passo = 0.4 * CM
    C = [[None] * N_COLLO for _ in range(4)]
    for c, t in enumerate(thc):
        L = lunghezza(t)
        mete = [L * i / 4 for i in (1, 2, 3, 4)]
        p = H0[c].copy()
        s_tot, im = 0.0, 0
        for _ in range(2000):
            loc, nor, idx, dist = bvh_s.find_nearest(p)
            d = p - Q
            d_t = d - nor * d.dot(nor)
            if d_t.length < 1e-9:
                d_t = Vector((0, 0, -1))
            p2, _n = snap(p + d_t.normalized() * passo, bvh_s, strato)
            s_tot += (p2 - p).length
            p = p2
            while im < 4 and s_tot >= mete[im]:
                C[im][c] = p.copy()
                im += 1
            if im >= 4:
                break

    # --- collo arrotolato (cappuccio abbassato) sopra la cucitura ---
    def salita(t):
        s = math.sin(t)
        mid = (P["ROTOLO_SALITA_DIETRO"] + P["ROTOLO_SALITA_DAVANTI"]) / 2
        amp = (P["ROTOLO_SALITA_DIETRO"] - P["ROTOLO_SALITA_DAVANTI"]) / 2
        return (mid + amp * s) * CM

    H1, H2, H3 = [], [], []
    for c, t in enumerate(thc):
        out = Vector((math.cos(t), math.sin(t), 0))
        h = salita(t)
        sp = P["ROTOLO_SPESSORE"] * CM
        H1.append(spingi_fuori(H0[c] + Vector((0, 0, h)) + out * 0.6 * CM, corpo.bvh, P["ARIA_COLLO"] * CM))
        H2.append(spingi_fuori(H0[c] + Vector((0, 0, h + 1.6 * CM)) + out * (sp * 0.52), corpo.bvh, P["ARIA_COLLO"] * CM))
        H3.append(H0[c] + Vector((0, 0, h * 0.55)) + out * sp)

    # superficie temporanea della mantellina per appoggiarci rotolo e cappuccio
    bm_tmp = bmesh.new()
    righe = [H0] + C
    vv = [[bm_tmp.verts.new(p) for p in riga] for riga in righe]
    for i in range(len(vv) - 1):
        for c in range(N_COLLO):
            c2 = (c + 1) % N_COLLO
            bm_tmp.faces.new([vv[i][c], vv[i + 1][c], vv[i + 1][c2], vv[i][c2]])
    me_tmp = bpy.data.meshes.new("_tmp_mantellina")
    bm_tmp.to_mesh(me_tmp)
    bm_tmp.free()
    ob_tmp = bpy.data.objects.new("_tmp_mantellina", me_tmp)
    bpy.context.scene.collection.objects.link(ob_tmp)
    mod = ob_tmp.modifiers.new("sub", 'SUBSURF')
    mod.levels = 2
    bm_m, bvh_m = superficie_valutata(ob_tmp)
    # appoggia un punto sulla mantellina, dal lato lontano dal corpo
    def snap_fuori(p, off):
        loc, nor, idx, dist = bvh_m.find_nearest(p)
        cl, cn, ci, cd = corpo.bvh.find_nearest(loc)
        if nor.dot(loc - cl) < 0:
            nor = -nor
        return loc + nor * off
    H4 = []
    for c, t in enumerate(thc):
        out = Vector((math.cos(t), math.sin(t), 0))
        p = H0[c] + out * ((P["ROTOLO_SPESSORE"] + 1.9) * CM) - Vector((0, 0, 1.5 * CM))
        H4.append(snap_fuori(p, strato_c))
    H3 = [spingi_fuori(p, bvh_m, strato_c) for p in H3]

    # --- cappuccio adagiato sul dorso: continua il rotolo sulle colonne dietro ---
    col_dietro = list(range(3, 10))          # da 45 a 135 gradi
    n_righe = 4
    lembo = {}
    for f in range(1, n_righe + 1):
        for c in col_dietro:
            base = H4[c]
            stringi = 1.0 - 0.5 * f / n_righe
            x = base.x * stringi
            z = base.z - (P["CAPPUCCIO_LUNGH"] * CM) * f / n_righe
            if f == n_righe:
                u = (c - 6) / 3.0
                z -= P["CAPPUCCIO_PUNTA"] * CM * (1 - u * u)
            # raggio da dietro: si prende la superficie piu' esterna della schiena
            # (mantellina se c'e' a quella quota, altrimenti saio)
            orig = Vector((x, y_n + 0.6, z))
            colpi = [h for h in (bvh_m.ray_cast(orig, Vector((0, -1, 0))),
                                 bvh_s.ray_cast(orig, Vector((0, -1, 0))))
                     if h[0] is not None]
            if colpi:
                h = max(colpi, key=lambda h: h[0].y)
                n = h[1] if h[1].y > 0 else -h[1]
                lembo[(f, c)] = h[0] + n * strato_c
            else:
                lembo[(f, c)] = Vector((x, base.y, z))
    bpy.data.objects.remove(ob_tmp, do_unlink=True)
    bpy.data.meshes.remove(me_tmp)
    bm_m.free()

    # --- topologia ---
    bm = bmesh.new()
    anelli = {"C4": C[3], "C3": C[2], "C2": C[1], "C1": C[0], "H0": H0,
              "H1": H1, "H2": H2, "H3": H3, "H4": H4}
    ordine = ["C4", "C3", "C2", "C1", "H0", "H1", "H2", "H3", "H4"]
    VV = {nome: [bm.verts.new(p) for p in anelli[nome]] for nome in ordine}
    zone = {}
    for a, b in zip(ordine[:-1], ordine[1:]):
        for c in range(N_COLLO):
            c2 = (c + 1) % N_COLLO
            f = bm.faces.new([VV[a][c], VV[b][c], VV[b][c2], VV[a][c2]])
            zone[f] = "mantellina" if a.startswith("C") else "cappuccio"
    VL = {}
    for (f_, c), p in lembo.items():
        VL[(f_, c)] = bm.verts.new(p)

    def L_(f_, c):
        return VV["H4"][c] if f_ == 0 else VL[(f_, c)]
    for f_ in range(n_righe):
        for c in col_dietro[:-1]:
            f = bm.faces.new([L_(f_, c), L_(f_ + 1, c), L_(f_ + 1, c + 1), L_(f_, c + 1)])
            zone[f] = "cappuccio"
    bm.verts.ensure_lookup_table()

    # rilassa le righe interne della mantellina (non bordo, non cucitura del collo)
    mobili = VV["C1"] + VV["C2"] + VV["C3"]
    rilassa_su(bm, mobili, bvh_s, strato, giri=10)
    simmetrizza(bm)
    resto = correggi_liscia(bm, [vincolo_pelle(corpo, 2.0 * CM, P["ARIA_TESTA"] * CM),
                                 vincolo_strato(bvh_s, 1.0 * CM)])
    log(f"[4] Correzione superficie liscia della mantellina: scarto residuo {resto/CM:.2f} cm")
    # orientamento: la parte "mantellina" rivolta via dal corpo
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    voti = 0
    for f, z in zone.items():
        if z == "mantellina":
            c = f.calc_center_median()
            loc, nor, idx, dist = corpo.bvh.find_nearest(c)
            voti += 1 if f.normal.dot(c - loc) > 0 else -1
    if voti < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()
    bm_s.free()
    info_m = dict(VV=VV, VL=VL, zone=zone, col_dietro=col_dietro, n_righe=n_righe)
    return bm, info_m


def rilassa_su(bm, mobili, bvh_supporto, strato, giri=10, forza=0.5):
    """Come rilassa(), ma i vertici restano appoggiati sul saio a distanza 'strato'."""
    for _ in range(giri):
        bm.normal_update()
        nuovi = {}
        for v in mobili:
            vic = [e.other_vert(v).co for e in v.link_edges]
            c = sum(vic, Vector()) / len(vic)
            nuovi[v] = v.co.lerp(c, forza)
        for v, co in nuovi.items():
            loc, nor, idx, dist = bvh_supporto.find_nearest(co)
            v.co = loc + nor * strato


# =============================================================================
#  4. CUCITURE, ZONE, OGGETTI
# =============================================================================
def segna_cuciture_saio(bm, info):
    V, anelli = info["V"], info["anelli"]
    K = info["K"]
    cuciture = set()

    def e_tra(a, b):
        e = bm.edges.get((a, b))
        if e is None:
            raise RuntimeError("spigolo mancante")
        return e
    # fianchi (colonne 0 e 12) dall'ascella all'orlo
    for j in (0, 12):
        for k in range(K - 1):
            cuciture.add(e_tra(V[("T", k, j)], V[("T", k + 1, j)]))
    # balza
    kb = info["z_anelli"].index(P["Z_BALZA"]) if P["Z_BALZA"] in info["z_anelli"] else None
    if kb is None:
        kb = min(range(K), key=lambda k: abs(info["z_anelli"][k] - P["Z_BALZA"]))
    for j in range(N_TORSO):
        cuciture.add(e_tra(V[("T", kb, j)], V[("T", kb, (j + 1) % N_TORSO)]))
    # spalle
    for a, b, c in (("Lsp", "Ls1", "Lnk"), ("Rsp", "Rs1", "Rnk")):
        cuciture.add(e_tra(V[("C", a)], V[("C", b)]))
        cuciture.add(e_tra(V[("C", b)], V[("C", c)]))
    # giri manica, sotto-manica, risvolto
    for lato in ("L", "R"):
        A = anelli[lato]
        for k in range(N_MANICA):
            cuciture.add(e_tra(A[0][k], A[0][(k + 1) % N_MANICA]))
            cuciture.add(e_tra(A[P["ANELLO_RISVOLTO"]][k], A[P["ANELLO_RISVOLTO"]][(k + 1) % N_MANICA]))
        for i in range(len(A) - 1):
            cuciture.add(e_tra(A[i][6], A[i + 1][6]))   # k=6 = sotto il braccio
    for e in cuciture:
        e.seam = True
    return len(cuciture)


def segna_cuciture_mantellina(bm, info_m):
    VV, VL = info_m["VV"], info_m["VL"]
    cuciture = set()

    def e_tra(a, b):
        e = bm.edges.get((a, b))
        if e is None:
            raise RuntimeError("spigolo mancante")
        return e
    for c in range(N_COLLO):
        cuciture.add(e_tra(VV["H0"][c], VV["H0"][(c + 1) % N_COLLO]))
    ordine = ["C4", "C3", "C2", "C1", "H0", "H1", "H2", "H3", "H4"]
    for a, b in zip(ordine[:-1], ordine[1:]):
        cuciture.add(e_tra(VV[a][6], VV[b][6]))      # centro dietro
    prec = VV["H4"][6]
    for f_ in range(1, info_m["n_righe"] + 1):
        cuciture.add(e_tra(prec, VL[(f_, 6)]))
        prec = VL[(f_, 6)]
    for e in cuciture:
        e.seam = True
    return len(cuciture)


def conta_isole(bm):
    """Isole UV previste: gruppi di facce non separati da cuciture o bordi."""
    bm.faces.ensure_lookup_table()
    visti, isole = set(), 0
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
    return isole


def materiale_lana():
    mat = bpy.data.materials.get("M_Lana") or bpy.data.materials.new("M_Lana")
    mat.diffuse_color = (0.33, 0.27, 0.22, 1.0)
    nt = mat.node_tree
    if nt is None:
        return mat
    for n in list(nt.nodes):
        if n.bl_idname not in ("ShaderNodeBsdfPrincipled", "ShaderNodeOutputMaterial"):
            nt.nodes.remove(n)
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "chiaro"
    chiaro = nt.nodes.new("ShaderNodeRGB")
    chiaro.outputs[0].default_value = (0.56, 0.50, 0.42, 1.0)   # rovescio della lana
    diff = nt.nodes.new("ShaderNodeVectorMath")
    diff.operation = 'SUBTRACT'
    scala = nt.nodes.new("ShaderNodeVectorMath")
    scala.operation = 'SCALE'
    somma = nt.nodes.new("ShaderNodeVectorMath")
    somma.operation = 'ADD'
    nt.links.new(chiaro.outputs[0], diff.inputs[0])
    nt.links.new(info.outputs["Color"], diff.inputs[1])
    nt.links.new(diff.outputs[0], scala.inputs[0])
    nt.links.new(attr.outputs["Factor"], scala.inputs["Scale"])
    nt.links.new(scala.outputs[0], somma.inputs[0])
    nt.links.new(info.outputs["Color"], somma.inputs[1])
    nt.links.new(somma.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    for x, n in enumerate((info, attr, chiaro, diff, scala, somma)):
        n.location = (-900 + 150 * x, 200 - 60 * x)
    return mat


def crea_oggetto(nome, bm, colore, zone, chiaro_zone=()):
    me = bpy.data.meshes.new(nome)
    # Prima si annotano i NUMERI (indici) delle facce chiare, poi si aggiunge il
    # layer: aggiungere un layer rigenera gli "oggetti Python" delle facce e il
    # dizionario 'zone' non le riconoscerebbe piu' (il risvolto resterebbe scuro).
    bm.faces.index_update()
    chiare = {f.index for f, z in zone.items() if z in chiaro_zone}
    lay = bm.faces.layers.float.get("chiaro") or bm.faces.layers.float.new("chiaro")
    for f in bm.faces:
        f[lay] = 1.0 if f.index in chiare else 0.0
    bm.to_mesh(me)
    me.shade_smooth()
    obj = bpy.data.objects.new(nome, me)
    prendi_collezione(COLL_BLOCKOUT).objects.link(obj)
    me.materials.append(materiale_lana())
    obj.color = colore
    mod = obj.modifiers.new("Suddivisione", 'SUBSURF')
    mod.levels = 2
    mod.render_levels = 2
    mod.show_only_control_edges = True
    obj.show_wire = True
    obj["fase"] = "2 - blockout"
    return obj


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


# =============================================================================
#  5. CONTROLLI
# =============================================================================
def distanze(bm_val, bvh, maschera_z=None):
    d = []
    for v in bm_val.verts:
        if maschera_z and not (maschera_z[0] <= v.co.z <= maschera_z[1]):
            continue
        loc, nor, idx, dist = bvh.find_nearest(v.co)
        if loc is None:
            continue
        d.append(dist if (v.co - loc).dot(nor) >= 0 else -dist)
    return np.array(d) / CM if d else np.array([0.0])


def controlli(corpo, saio, mant, info, info_m, cuc_s, cuc_m):
    ok = True
    for obj, bm_c in ((saio, None), (mant, None)):
        me = obj.data
        n_tri = sum(1 for p in me.polygons if len(p.vertices) == 3)
        n_ngon = sum(1 for p in me.polygons if len(p.vertices) > 4)
        bm_c = bmesh.new()
        bm_c.from_mesh(me)
        non_manif = sum(1 for e in bm_c.edges if len(e.link_faces) > 2)
        isole = conta_isole(bm_c)
        bordi = sum(1 for e in bm_c.edges if e.is_boundary)
        bm_c.free()
        quad = len(me.polygons)
        log(f"    {obj.name}: {quad} quad, {n_tri} triangoli, {n_ngon} n-gon, "
            f"{non_manif} spigoli non-manifold, {bordi} spigoli di bordo, {isole} isole UV")
        log(f"       budget: livello 1 = {quad*4*2} tri, livello 2 = {quad*16*2} tri")
        ok &= (n_tri == 0 and n_ngon == 0 and non_manif == 0)
    # risvolto delle maniche: facce marcate "chiaro" (colore del rovescio della lana)
    a = saio.data.attributes.get("chiaro")
    n_chiare = sum(1 for d in a.data if d.value > 0.5) if a else 0
    attese = 2 * N_MANICA * (len(P["MANICA_ANELLI"]) - P["ANELLO_RISVOLTO"])
    log(f"    Risvolto delle maniche: {n_chiare} facce chiare su {attese} attese")
    ok &= n_chiare == attese
    # distanze sulla superficie suddivisa (quella che vedrai e simulerai)
    bm_s, bvh_s = superficie_valutata(saio)
    d_s = distanze(bm_s, corpo.bvh)
    log(f"    Saio (superficie liscia) - pelle: min {d_s.min():.2f} cm, "
        f"5% {np.percentile(d_s, 5):.2f}, mediana {np.median(d_s):.2f} cm")
    ok &= d_s.min() > 1.0
    bm_m, bvh_m = superficie_valutata(mant)
    d_m = distanze(bm_m, corpo.bvh)
    log(f"    Mantellina (liscia) - pelle: min {d_m.min():.2f} cm")
    ok &= d_m.min() > 1.0
    # mantellina sopra il saio: nessun vertice dentro il saio
    dentro = 0
    d_ms = []
    for v in bm_m.verts:
        loc, nor, idx, dist = bvh_s.find_nearest(v.co)
        sd = dist if (v.co - loc).dot(nor) >= 0 else -dist
        d_ms.append(sd)
        if sd < 0:
            dentro += 1
    d_ms = np.array(d_ms) / CM
    log(f"    Mantellina - saio: min {d_ms.min():.2f} cm, vertici sotto il saio: {dentro}")
    if corpo.bvh_testa is not None:
        d_t = min(corpo.bvh_testa.find_nearest(v.co)[3] for v in bm_m.verts) / CM
        d_t2 = min(corpo.bvh_testa.find_nearest(v.co)[3] for v in bm_s.verts) / CM
        log(f"    Dalla mesh della TESTA (non nascondibile): mantellina/cappuccio {d_t:.2f} cm, saio {d_t2:.2f} cm")
        ok &= d_t > 2.0 and d_t2 > 2.0
    # quote
    zs = [v.co.z / CM for v in bm_s.verts]
    log(f"    Orlo del saio a {min(zs):.1f} cm da terra; anello del cordone a {P['Z_CORDONE']:.0f} cm")
    log(f"    Cuciture: saio {cuc_s} spigoli, mantellina {cuc_m} spigoli")
    bm_s.free()
    bm_m.free()
    return ok


# =============================================================================
#  MAIN
# =============================================================================
def main():
    log("=== REPORT FASE 2 - BLOCKOUT ===")
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for nome in (NOME_SAIO, NOME_MANT):
        rimuovi(nome)
    corpo = Corpo()

    bm_s, info = costruisci_saio(corpo)
    cuc_s = segna_cuciture_saio(bm_s, info)
    saio = crea_oggetto(NOME_SAIO, bm_s, (0.36, 0.29, 0.23, 1.0), info["zone"], ("risvolto",))
    g = saio.vertex_groups.new(name="Linea_Cordone")
    k_c = info["z_anelli"].index(P["Z_CORDONE"])
    g.add([info["V"][("T", k_c, j)].index for j in range(N_TORSO)], 1.0, 'REPLACE')
    bm_s.free()
    log(f"[3] {NOME_SAIO}: creato")

    bm_m, info_m = costruisci_mantellina(corpo, info, saio)
    cuc_m = segna_cuciture_mantellina(bm_m, info_m)
    mant = crea_oggetto(NOME_MANT, bm_m, (0.26, 0.21, 0.17, 1.0), info_m["zone"])
    bm_m.free()
    log(f"[4] {NOME_MANT}: creato (mantellina + cappuccio abbassato)")

    log("[5] Controlli:")
    ok = controlli(corpo, saio, mant, info, info_m, cuc_s, cuc_m)

    # visibilita': nascondi il guscio di prova della Fase 1
    lc = layer_collection("TEST")
    if lc:
        lc.hide_viewport = True
    corpo.bm.free()

    nuovo = None
    if bpy.data.filepath:
        cartella = os.path.dirname(bpy.data.filepath)
        nuovo = os.path.join(cartella, NOME_FILE_V2)
        log(f"[6] Salvo come {nuovo} (il file v001 resta intatto)")
    else:
        log("[6] File non salvato: usa File > Save As per salvarlo.")
    log("ESITO: " + ("tutti i controlli superati" if ok else "ATTENZIONE: qualche controllo non e' passato"))
    # il rapporto entra nel file PRIMA del salvataggio, cosi' resta dentro v002
    testo = bpy.data.texts.get("REPORT_Fase2") or bpy.data.texts.new("REPORT_Fase2")
    testo.clear()
    testo.write("\n".join(report) + "\n")
    if nuovo:
        bpy.ops.wm.save_as_mainfile(filepath=nuovo)
    return ok, testo


ok, testo = main()

spazio = getattr(bpy.context, "space_data", None)
if spazio is not None and spazio.type == 'TEXT_EDITOR':
    spazio.text = testo

wm = bpy.context.window_manager
if wm.windows and not bpy.app.background:   # solo con l'interfaccia aperta
    def disegna(self, context):
        for riga in report[:16]:
            self.layout.label(text=riga)
    wm.popup_menu(disegna, title="Fase 2: fatto" if ok else "Fase 2: controlla il report",
                  icon='INFO' if ok else 'ERROR')
