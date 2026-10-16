# =============================================================================
#  FASE 7 - ACCESSORI: CORDONE, CORONA, TAU, SANDALI, ANELLO
#  Progetto: Abate francescano  (MetaHuman UE 5.8  ->  Blender 5.2  ->  UE 5.8)
#
#  COSA FA
#   Costruisce gli accessori SUL saio e SUL corpo dell'abate (posa di riferimento):
#    - cordone bianco (Ø 1,3 cm) stretto in vita sulla linea della Fase 3, nodo a
#      destra, coda pendente con tre nodi "a barilotto" e la punta sfilacciata;
#    - corona francescana a 7 poste (7 x [1 Pater + 10 Ave] = 77 grani) appesa
#      al cordone a sinistra, chiusa da un grano piu' grande con 2 Ave, 1 Pater
#      e una crocetta;
#    - Tau di legno sul petto, appoggiato alla mantellina, col cordino che
#      sparisce sotto il collo arrotolato;
#    - sandali di cuoio (suola + 3 cinghie) sotto i piedi;
#    - anello di ferro sull'anulare destro (osso ring_01_r).
#   Per ognuno fa una mesh di GIOCO (leggera) e una mesh ALTA (solo per cuocere
#   la normal map: trefoli della corda, bordi arrotondati, incisioni).
#   Poi UV in un unico atlante, cotture, texture, export (vedi le sezioni sotto).
#
#  DOVE VANNO IN UNREAL (scelta della Fase 7)
#   - cordone, corona, Tau, sandali: dentro l'Outfit, nella stessa Static Mesh
#     del saio (SM_SaioAbate_Render, secondo materiale M_Accessori). Prendono i
#     pesi dal corpo con la stessa regola del saio (TransferSkinWeights), quindi
#     si muovono insieme alla stoffa.
#   - anello: Skeletal Mesh a parte (SKM_AnelloAbate) tutta sull'osso ring_01_r:
#     tra le dita ci sono 3-4 mm e il trasferimento automatico lo deformerebbe.
#
#  PRIMA DI LANCIARLO
#   - Apri Saio_Abate_v006.blend (Fase 6), con le cartelle Texture ed Export.
#  COME SI LANCIA
#   - Workspace "Scripting" > Text > Open > questo file > Run Script (Alt+P).
#     Diversi minuti (la cottura delle texture e' la parte lunga).
# =============================================================================

import bpy
import bmesh
import math
import os
import time
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import tessellate_polygon

CM = 0.01

# ----------------------------- PARAMETRI (cm e gradi) ------------------------
P = dict(
    # cordone
    CORDA_D=1.30,            # diametro del cordone
    CORDA_Z=115.2,           # quota della linea del cordone (Fase 3)
    CORDA_GIOCO=0.12,        # aria tra corda e lana
    CORDA_LATI=8,            # lati della sezione nella mesh di gioco
    CORDA_PASSO=2.5,         # lunghezza massima di un segmento (mesh di gioco)
    CORDA_TORSIONE=4.6,      # passo dell'elica dei trefoli
    CODA_AZIMUT=35.0,        # dove pende la coda: gradi dal centro davanti verso la DESTRA dell'abate
    CODA_FINE_Z=50.0,        # quota della punta della coda (ginocchio ~50)
    NODI_Z=(80.0, 69.0, 58.0),
    NODO_GIRI=2.5,           # giri del nodo a barilotto
    SFILACCIATA=2.6,         # punta della coda: legatura con lo spago + trefoli appena aperti
    # corona
    CORONA_AZIMUT=-42.0,     # verso la SINISTRA dell'abate
    AVE_D=0.70, PATER_D=1.00, GIUNTO_D=1.10, GRANO_GIOCO=0.10,
    FILO_D=0.25, FILI_DISTANZA=1.0,
    # Tau
    TAU_ALTO=7.0, TAU_LARGO=6.0, TAU_SPESSO=0.9, TAU_Z=133.5,
    TAU_CORDINO_D=0.35, TAU_TASCA_X=3.5, TAU_TASCA_Z=149.0,
    # sandali
    SUOLA_SPESSA=1.0, SUOLA_MARGINE=0.45, CINGHIA_SPESSA=0.30, CINGHIA_GIOCO=0.15,
    # anello
    ANELLO_POS=0.60,         # 0 = nocca, 1 = articolazione successiva (falange prossimale)
    ANELLO_LARGO=0.50, ANELLO_SPESSO=0.13, ANELLO_SOPRA=0.24, ANELLO_GIOCO=0.05,
    # texture
    RISOLUZIONE=2048, SOVRACAMPIONA=2, MARGINE_PX=8,
    DISTANZA_AO=1.5,         # cm: ombre di contatto (corda sulla lana, piede sulla suola, solchi)
)

NOMI = dict(saio="Saio_Gioco", mant="Mantellina_Gioco", corpo="REF_Corpo", arm="root",
            corpo_orig="MHC_Abate_FullBody_LOD0")
NOME_FILE_V7 = "Saio_Abate_v007.blend"
# codici delle parti (decidono il "materiale" dipinto nella texture)
PARTI = dict(cordone=10, filo=11, cordino=12, tau=20, grani=21, crocetta=22,
             suola_bordo=30, suola_sopra=31, suola_sotto=32, cinghie=33, anello=40)
UV = "UVMap"
report = []


def log(riga=""):
    print(riga, flush=True)
    report.append(riga)


# =============================================================================
#  UTILITA' GENERALI
# =============================================================================
def modo_oggetto():
    if bpy.context.object is not None and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def mesh_mondo(o):
    """Vertici (mondo) e triangoli della mesh valutata (modificatori compresi)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(o.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    tri = np.zeros(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get("vertices", tri)
    ev.to_mesh_clear()
    return co, tri.reshape(-1, 3)


def albero(co, tri):
    return BVHTree.FromPolygons([Vector(c) for c in co], tri.tolist())


def norm(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def inviluppo_convesso(pts):
    """Inviluppo convesso 2D (catena monotona), in senso antiorario."""
    pts = np.unique(np.round(np.asarray(pts, float), 7), axis=0)
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]
    def croce(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    basso, alto = [], []
    for p in pts:
        while len(basso) >= 2 and croce(basso[-2], basso[-1], p) <= 0:
            basso.pop()
        basso.append(p)
    for p in pts[::-1]:
        while len(alto) >= 2 and croce(alto[-2], alto[-1], p) <= 0:
            alto.pop()
        alto.append(p)
    return np.array(basso[:-1] + alto[:-1])


def dentro_poligono(p, poli):
    """Il punto 2D e' dentro il poligono? (regola pari/dispari)"""
    x, y = p
    dentro = False
    n = len(poli)
    for i in range(n):
        x1, y1 = poli[i]
        x2, y2 = poli[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def lunghezze(Pts, chiuso=False):
    d = np.linalg.norm(np.diff(np.vstack([Pts, Pts[:1]]) if chiuso else Pts, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(d)])


def ricampiona(Pts, passo, chiuso=False):
    """Punti a distanza costante lungo la polilinea."""
    Q = np.vstack([Pts, Pts[:1]]) if chiuso else Pts
    s = lunghezze(Pts, chiuso)
    n = max(int(round(s[-1] / passo)), 2)
    t = np.linspace(0.0, s[-1], n + (0 if chiuso else 1), endpoint=not chiuso)
    return np.stack([np.interp(t, s, Q[:, k]) for k in range(3)], 1)


def catmull_rom(Pts, n=8, chiuso=False):
    """Curva morbida che passa per i punti (Catmull-Rom centripeta)."""
    Pts = np.asarray(Pts, float)
    if chiuso:
        Q = np.vstack([Pts[-1:], Pts, Pts[:2]])
    else:
        Q = np.vstack([2 * Pts[0] - Pts[1], Pts, 2 * Pts[-1] - Pts[-2]])
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-9) ** 0.5
        t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-9) ** 0.5
        t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-9) ** 0.5
        for t in np.linspace(t1, t2, n, endpoint=False):
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    if not chiuso:
        out.append(Pts[-1])
    return np.array(out)


def tangenti(Pts, chiuso=False):
    if chiuso:
        T = np.roll(Pts, -1, 0) - np.roll(Pts, 1, 0)
    else:
        T = np.gradient(Pts, axis=0)
    return norm(T)


def cornici(Pts, U0, chiuso=False):
    """Cornici che non ruotano su se stesse lungo la curva (metodo della doppia
    riflessione). U0 = direzione iniziale della cucitura del tubo."""
    T = tangenti(Pts, chiuso)
    U = np.zeros_like(Pts)
    u = np.asarray(U0, float) - np.dot(U0, T[0]) * T[0]
    if np.linalg.norm(u) < 1e-6:          # direzione iniziale parallela alla curva: ne scelgo un'altra
        alt = np.array([1.0, 0, 0]) if abs(T[0][0]) < 0.9 else np.array([0, 1.0, 0])
        u = alt - np.dot(alt, T[0]) * T[0]
    U[0] = u / np.linalg.norm(u)
    for i in range(len(Pts) - 1):
        v1 = Pts[i + 1] - Pts[i]
        c1 = v1 @ v1
        if c1 < 1e-16:
            U[i + 1] = U[i]
            continue
        rL = U[i] - (2 / c1) * (v1 @ U[i]) * v1
        tL = T[i] - (2 / c1) * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        U[i + 1] = rL - (2 / c2) * (v2 @ rL) * v2 if c2 > 1e-16 else rL
    if chiuso:      # distribuisce lo scarto di chiusura lungo l'anello
        v1 = Pts[0] - Pts[-1]
        c1 = v1 @ v1
        rL = U[-1] - (2 / c1) * (v1 @ U[-1]) * v1
        tL = T[-1] - (2 / c1) * (v1 @ T[-1]) * v1
        v2 = T[0] - tL
        c2 = v2 @ v2
        Uf = rL - (2 / c2) * (v2 @ rL) * v2 if c2 > 1e-16 else rL
        ang = math.atan2(np.cross(Uf, U[0]) @ T[0], Uf @ U[0])
        s = lunghezze(Pts, True)[:-1]
        s = s / (s[-1] + np.linalg.norm(Pts[0] - Pts[-1]))
        for i in range(len(Pts)):
            a = ang * s[i]
            U[i] = U[i] * math.cos(a) + np.cross(T[i], U[i]) * math.sin(a)
    U = norm(U - (U * T).sum(1)[:, None] * T)
    V = np.cross(T, U)
    return T, U, V


def scegli_campioni(Pts, passo_max, angolo_max=14.0, chiuso=False):
    """Indici dei punti da tenere nella mesh di gioco: piu' fitti nelle curve."""
    T = tangenti(Pts, chiuso)
    idx = [0]
    acc_l, acc_a = 0.0, 0.0
    for i in range(1, len(Pts)):
        acc_l += np.linalg.norm(Pts[i] - Pts[i - 1])
        acc_a += math.degrees(math.acos(np.clip(T[i] @ T[i - 1], -1, 1)))
        if acc_l >= passo_max or acc_a >= angolo_max:
            idx.append(i)
            acc_l, acc_a = 0.0, 0.0
    if not chiuso and idx[-1] != len(Pts) - 1:
        if np.linalg.norm(Pts[-1] - Pts[idx[-1]]) < 0.3 * passo_max and len(idx) > 1:
            idx[-1] = len(Pts) - 1
        else:
            idx.append(len(Pts) - 1)
    if chiuso and len(idx) > 1 and np.linalg.norm(Pts[0] - Pts[idx[-1]]) < 0.3 * passo_max:
        idx.pop()
    return np.array(idx)


def colpi(bvh, o, d, maxd=2.0):
    """Tutti i punti in cui un raggio attraversa la mesh: (distanza, normale . direzione)."""
    out, t = [], 0.0
    o, d = Vector(o), Vector(d).normalized()
    while len(out) < 12:
        h = bvh.ray_cast(o + d * t, d, maxd - t)
        if h[0] is None:
            break
        dist = (h[0] - o).length
        out.append((dist, h[1].dot(d)))
        t = dist + 1e-5
    return out


# =============================================================================
#  PEZZI: contenitore di mesh (vertici, facce, UV per angolo di faccia)
# =============================================================================
class Pezzo:
    """Un pezzo di mesh. uv: per ogni faccia la lista delle UV dei suoi angoli
    (in cm, prima dell'impacchettamento). isola: per ogni faccia l'indice dell'isola UV."""
    def __init__(self, nome, tipo, densita=1.0):
        self.nome, self.tipo, self.densita = nome, tipo, densita
        self.v = []
        self.f = []
        self.uv = []
        self.isola = []
        self.parti = []          # codice della parte (materiale procedurale) per faccia
        self.parte_attiva = 0
        self.dens_isola = {}     # isola -> fattore di densita' dei pixel (parti poco visibili)
        self.n_isole = 0

    def aggiungi_v(self, pts):
        b = len(self.v)
        self.v.extend([tuple(p) for p in np.asarray(pts, float)])
        return b

    def faccia(self, idx, uv, isola):
        self.f.append(tuple(int(i) for i in idx))
        self.uv.append([tuple(map(float, x)) for x in uv])
        self.isola.append(isola)
        self.parti.append(self.parte_attiva)

    def nuova_isola(self):
        self.n_isole += 1
        return self.n_isole - 1

    @property
    def triangoli(self):
        return sum(len(f) - 2 for f in self.f)


def tubo(pz, Pts, raggio, lati, chiuso=False, U0=(0, 0, 1), tappi=True, taglio=40.0, raggio_uv=None,
         isola_iniziale=None):
    """Tubo lungo la curva Pts (gia' campionata). raggio: costante o array.
    UV in cm: u = giro (circonferenza), v = lunghezza; un'isola ogni 'taglio' cm."""
    n = len(Pts)
    T, U, V = cornici(Pts, U0, chiuso)
    r = np.full(n, raggio) if np.isscalar(raggio) else np.asarray(raggio, float)
    ru = (r.mean() if raggio_uv is None else raggio_uv)
    phi = np.linspace(0, 2 * math.pi, lati, endpoint=False)
    anelli = Pts[:, None, :] + r[:, None, None] * (np.cos(phi)[None, :, None] * U[:, None, :]
                                                  + np.sin(phi)[None, :, None] * V[:, None, :])
    b = pz.aggiungi_v(anelli.reshape(-1, 3))
    s = lunghezze(Pts, chiuso)
    circ = 2 * math.pi * ru / CM
    sc = s / CM
    # isole: tagli trasversali ogni 'taglio' cm
    tot = sc[-1]
    n_pezzi = max(1, int(math.ceil(tot / taglio - 1e-6)))
    confini = np.linspace(0, tot, n_pezzi + 1)
    isole = [pz.nuova_isola() for _ in range(n_pezzi)]
    segs = n if chiuso else n - 1
    for i in range(segs):
        j = (i + 1) % n
        s0, s1 = sc[i], sc[i + 1] if i + 1 < len(sc) else tot
        m = 0.5 * (s0 + s1)
        k = min(int(np.searchsorted(confini, m, side='right') - 1), n_pezzi - 1)
        v0, v1 = s0 - confini[k], s1 - confini[k]
        for a in range(lati):
            a2 = (a + 1) % lati
            u0, u1 = a / lati * circ, (a + 1) / lati * circ
            pz.faccia([b + i * lati + a, b + i * lati + a2, b + j * lati + a2, b + j * lati + a],
                      [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], isole[k])
    if tappi and not chiuso:
        for estremo, segno in ((0, -1), (n - 1, 1)):
            isola = pz.nuova_isola()
            c = pz.aggiungi_v([Pts[estremo]])
            for a in range(lati):
                a2 = (a + 1) % lati
                ia, ib = b + estremo * lati + a, b + estremo * lati + a2
                ua = (math.cos(phi[a]) * r[estremo] / CM, math.sin(phi[a]) * r[estremo] / CM)
                ub = (math.cos(phi[a2]) * r[estremo] / CM, math.sin(phi[a2]) * r[estremo] / CM)
                if segno < 0:
                    pz.faccia([c, ib, ia], [(0, 0), ub, ua], isola)
                else:
                    pz.faccia([c, ia, ib], [(0, 0), ua, ub], isola)
    return dict(T=T, U=U, V=V, b=b)


def trefoli(Pts, raggio, chiuso=False, U0=(0, 0, 1), passo_torsione=None, lati=12, passo=None,
            sfilaccia=None, legatura=None):
    """Mesh ALTA della corda: tre trefoli attorcigliati (con le fibre a rilievo)
    attorno alla curva. Ritorna (vertici, facce). sfilaccia: s (m) da cui i trefoli
    si aprono un poco verso la fine; legatura: (s0, s1) in m, tratto avvolto dallo spago."""
    passo = passo or raggio * 0.12
    Pd = ricampiona(Pts, passo, chiuso)
    T, U, V = cornici(Pd, U0, chiuso)
    s = lunghezze(Pd, chiuso)[:len(Pd)]
    lay = (passo_torsione or P["CORDA_TORSIONE"] * CM * raggio / (P["CORDA_D"] * CM / 2))
    rs = 0.50 * raggio
    vv, ff = [], []
    for j in range(3):
        apri = np.zeros(len(Pd)) if sfilaccia is None else smoothstep(sfilaccia, s[-1], s)
        d = raggio * (0.52 + 0.12 * apri)
        psi = 2 * math.pi * s / lay + 2 * math.pi * j / 3
        C = Pd + d[:, None] * (np.cos(psi)[:, None] * U + np.sin(psi)[:, None] * V)
        Tj, Uj, Vj = cornici(C, U[0], chiuso)
        sj = lunghezze(C, chiuso)[:len(C)]
        th = np.linspace(0, 2 * math.pi, lati, endpoint=False)
        # fibre: rilievi elicoidali sul trefolo (torsione opposta)
        bump = 1.0 + 0.07 * np.cos(6 * th[None, :] + 2 * math.pi * sj[:, None] / (lay * 0.55))
        rr = rs * bump
        R = C[:, None, :] + rr[..., None] * (np.cos(th)[None, :, None] * Uj[:, None, :]
                                             + np.sin(th)[None, :, None] * Vj[:, None, :])
        b = len(vv)
        vv.extend(R.reshape(-1, 3))
        m = len(C)
        segs = m if chiuso else m - 1
        for i in range(segs):
            i2 = (i + 1) % m
            for a in range(lati):
                a2 = (a + 1) % lati
                ff.append((b + i * lati + a, b + i * lati + a2, b + i2 * lati + a2, b + i2 * lati + a))
        if not chiuso:
            for estremo, rev in ((0, True), (m - 1, False)):
                c = len(vv)
                vv.append(C[estremo])
                for a in range(lati):
                    a2 = (a + 1) % lati
                    t = (c, b + estremo * lati + a, b + estremo * lati + a2)
                    ff.append(t[::-1] if rev else t)
    if legatura is not None:
        s0, s1 = legatura
        r_sp = 0.055 * CM                      # spago di ~1 mm
        m0, m1 = np.searchsorted(s, s0), np.searchsorted(s, s1)
        giri = (s1 - s0) / (2.3 * r_sp)
        tt = np.linspace(0, 1, int(giri * 24))
        ss = s0 + (s1 - s0) * tt
        idx = np.clip(np.searchsorted(s, ss), 0, len(Pd) - 1)
        ang = 2 * math.pi * giri * tt
        R_ = raggio * 1.02 + r_sp
        H = Pd[idx] + R_ * (np.cos(ang)[:, None] * U[idx] + np.sin(ang)[:, None] * V[idx])
        hv, hf = tubo_alto(H, r_sp, lati=6)
        ff += [tuple(i + len(vv) for i in q) for q in hf]
        vv += list(hv)
    return np.array(vv), ff


def tubo_alto(Pts, raggio, chiuso=False, U0=(0, 0, 1), lati=16):
    """Mesh ALTA liscia (fili sottili)."""
    Pd = ricampiona(Pts, raggio * 0.8, chiuso)
    T, U, V = cornici(Pd, U0, chiuso)
    th = np.linspace(0, 2 * math.pi, lati, endpoint=False)
    R = Pd[:, None, :] + raggio * (np.cos(th)[None, :, None] * U[:, None, :] + np.sin(th)[None, :, None] * V[:, None, :])
    vv = list(R.reshape(-1, 3))
    ff = []
    m = len(Pd)
    for i in range(m if chiuso else m - 1):
        i2 = (i + 1) % m
        for a in range(lati):
            a2 = (a + 1) % lati
            ff.append((i * lati + a, i * lati + a2, i2 * lati + a2, i2 * lati + a))
    if not chiuso:
        for estremo, rev in ((0, True), (m - 1, False)):
            c = len(vv)
            vv.append(Pd[estremo])
            for a in range(lati):
                t = (c, estremo * lati + a, estremo * lati + (a + 1) % lati)
                ff.append(t[::-1] if rev else t)
    return np.array(vv), ff


def sfera(pz, centro, asse, raggio, seg=6, anelli=3, schiaccia=0.9, isola=None):
    """Grano (sfera bassa) con i poli lungo il filo. UV: rettangolo giro x meridiano (cm)."""
    asse = norm(asse)
    a = np.array([1.0, 0, 0]) if abs(asse[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = norm(np.cross(asse, a))
    e2 = np.cross(asse, e1)
    isola = pz.nuova_isola() if isola is None else isola
    pts = [centro - asse * raggio * schiaccia]
    for k in range(1, anelli):
        th = math.pi * k / anelli
        for j in range(seg):
            ph = 2 * math.pi * j / seg
            pts.append(centro + raggio * (-math.cos(th) * schiaccia * asse
                                          + math.sin(th) * (math.cos(ph) * e1 + math.sin(ph) * e2)))
    pts.append(centro + asse * raggio * schiaccia)
    b = pz.aggiungi_v(pts)
    circ = 2 * math.pi * raggio / CM
    mer = math.pi * raggio / CM
    def uvp(k, j):
        return (j / seg * circ, k / anelli * mer)
    for j in range(seg):
        j2 = j + 1
        pz.faccia([b, b + 1 + (j2 % seg), b + 1 + j], [(uvp(0, j + 0.5)), uvp(1, j2), uvp(1, j)], isola)
    for k in range(1, anelli - 1):
        for j in range(seg):
            j2 = j + 1
            r0, r1 = b + 1 + (k - 1) * seg, b + 1 + k * seg
            pz.faccia([r0 + j, r0 + (j2 % seg), r1 + (j2 % seg), r1 + j],
                      [uvp(k, j), uvp(k, j2), uvp(k + 1, j2), uvp(k + 1, j)], isola)
    top = b + len(pts) - 1
    rl = b + 1 + (anelli - 2) * seg
    for j in range(seg):
        j2 = j + 1
        pz.faccia([rl + j, rl + (j2 % seg), top], [uvp(anelli - 1, j), uvp(anelli - 1, j2), uvp(anelli, j + 0.5)], isola)
    return isola


def sfera_alta(centro, asse, raggio, schiaccia=0.9, foro=0.0):
    """Grano liscio con il foro accennato ai poli."""
    asse = norm(asse)
    a = np.array([1.0, 0, 0]) if abs(asse[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = norm(np.cross(asse, a))
    e2 = np.cross(asse, e1)
    nt, nph = 24, 32
    vv, ff = [], []
    for k in range(nt + 1):
        th = math.pi * k / nt
        for j in range(nph):
            ph = 2 * math.pi * j / nph
            rr = raggio
            ax = -math.cos(th) * schiaccia
            if foro > 0:      # svasatura del foro vicino ai poli
                ax *= 1.0 - 0.12 * math.exp(-((math.sin(th) * raggio) / foro) ** 2)
            vv.append(centro + rr * (ax * asse + math.sin(th) * (math.cos(ph) * e1 + math.sin(ph) * e2)))
    for k in range(nt):
        for j in range(nph):
            j2 = (j + 1) % nph
            ff.append((k * nph + j, k * nph + j2, (k + 1) * nph + j2, (k + 1) * nph + j))
    return np.array(vv), ff


def sagoma(pz, contorno, buchi, spessore, origine, ex, ey, ez, smusso, isola_fronte=None):
    """Sagoma piatta estrusa (Tau, crocetta): contorno 2D (cm) in senso antiorario,
    buchi = lista di contorni 2D. ex, ey: assi del piano; ez: verso l'esterno.
    Smusso su davanti e dietro. UV: davanti, dietro, e una fascia per il bordo
    (smusso + fianco + smusso), una per l'interno di ogni foro."""
    def to3(p2, z):
        return origine + (p2[0] * ex + p2[1] * ey) * CM + ez * z * CM

    def rientra(c, d, verso=1):
        c = np.asarray(c, float)
        n = len(c)
        out = []
        for i in range(n):
            a, b_, c2 = c[i - 1], c[i], c[(i + 1) % n]
            t1 = norm(b_ - a)
            t2 = norm(c2 - b_)
            n1 = np.array([t1[1], -t1[0]]) * verso
            n2 = np.array([t2[1], -t2[0]]) * verso
            m = norm(n1 + n2)
            out.append(b_ - m * d / max(m @ n1, 0.3))
        return np.array(out)
    h = spessore / 2
    est = np.asarray(contorno, float)
    inn = rientra(est, smusso)                     # contorno esterno: si stringe
    buchi_est = [np.asarray(bu, float) for bu in buchi]
    buchi_inn = [rientra(bu, smusso, -1) for bu in buchi_est]   # foro: si allarga
    isola_f, isola_r = pz.nuova_isola(), pz.nuova_isola()
    # facce piane (vertici propri: spigolo vivo con lo smusso)
    for lato, z_f, isola, specchio in ((+1, h, isola_f, 1), (-1, -h, isola_r, -1)):
        loops = [list(map(tuple, inn))] + [list(map(tuple, b)) for b in buchi_inn]
        pts2 = np.vstack([inn] + buchi_inn)
        tris = tessellate_polygon([[Vector((p[0], p[1], 0)) for p in L] for L in loops])
        b = pz.aggiungi_v([to3(p, z_f) for p in pts2])
        for t in tris:
            t = list(t)
            a2, b2, c2 = pts2[t[0]], pts2[t[1]], pts2[t[2]]
            area = (b2[0] - a2[0]) * (c2[1] - a2[1]) - (b2[1] - a2[1]) * (c2[0] - a2[0])
            if area * lato < 0:
                t = t[::-1]
            pz.faccia([b + i for i in t], [(specchio * pts2[i][0], pts2[i][1]) for i in t], isola)
    # fasce: smusso dietro + fianco + smusso davanti, su contorno e fori
    passo_v = [0.0, smusso * math.sqrt(2), smusso * math.sqrt(2) + spessore - 2 * smusso,
               2 * smusso * math.sqrt(2) + spessore - 2 * smusso]
    for c_out, c_in, verso in [(est, inn, 1)] + [(bo, bi, -1) for bo, bi in zip(buchi_est, buchi_inn)]:
        n = len(c_out)
        isola = pz.nuova_isola()
        righe = [pz.aggiungi_v([to3(p, -h) for p in c_in]), pz.aggiungi_v([to3(p, -h + smusso) for p in c_out]),
                 pz.aggiungi_v([to3(p, h - smusso) for p in c_out]), pz.aggiungi_v([to3(p, h) for p in c_in])]
        per = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.vstack([c_out, c_out[:1]]), axis=0), axis=1))])
        for r in range(3):
            for i in range(n):
                i2 = (i + 1) % n
                q = [righe[r] + i, righe[r] + i2, righe[r + 1] + i2, righe[r + 1] + i]
                uvq = [(per[i], passo_v[r]), (per[i + 1], passo_v[r]), (per[i + 1], passo_v[r + 1]), (per[i], passo_v[r + 1])]
                if verso < 0:
                    q, uvq = q[::-1], uvq[::-1]
                pz.faccia(q, uvq, isola)
    return dict(f=isola_f, r=isola_r)


# =============================================================================
#  IL SAIO E IL CORPO COME RIFERIMENTO
# =============================================================================
class Riferimenti:
    def __init__(self):
        self.saio_co, self.saio_tri = mesh_mondo(bpy.data.objects[NOMI["saio"]])
        self.mant_co, self.mant_tri = mesh_mondo(bpy.data.objects[NOMI["mant"]])
        self.corpo_co, self.corpo_tri = mesh_mondo(bpy.data.objects[NOMI["corpo"]])
        self.saio = albero(self.saio_co, self.saio_tri)
        self.mant = albero(self.mant_co, self.mant_tri)
        self.corpo = albero(self.corpo_co, self.corpo_tri)
        both_co = np.vstack([self.saio_co, self.mant_co])
        both_tri = np.vstack([self.saio_tri, self.mant_tri + len(self.saio_co)])
        self.stoffa = albero(both_co, both_tri)
        self.arm = bpy.data.objects[NOMI["arm"]]
        # asse verticale della vita: centro della sezione del busto alla quota del cordone
        z = P["CORDA_Z"] * CM
        sel = self.saio_co[(np.abs(self.saio_co[:, 2] - z) < 0.012) & (np.abs(self.saio_co[:, 0]) < 0.22)]
        self.cx = 0.0
        self.cy = 0.5 * (sel[:, 1].min() + sel[:, 1].max())

    def osso(self, nome):
        b = self.arm.data.bones[nome]
        return np.array(self.arm.matrix_world @ b.head_local)


def direzione(azimut):
    """Direzione orizzontale: 0 = davanti (-Y), positivo verso la destra dell'abate (-X)."""
    a = math.radians(azimut)
    return np.array([-math.sin(a), -math.cos(a), 0.0])


def primo_colpo(bvh, o, d, maxd=0.6):
    h = bvh.ray_cast(Vector(o), Vector(d), maxd)
    return None if h[0] is None else (h[0] - Vector(o)).length


def profilo_gonna(rif, azimut, z_alto, z_basso, banda, passo=0.25):
    """Raggio della stoffa (primo colpo dall'asse) lungo un piano verticale, per
    quote da z_alto a z_basso (m). banda: mezza larghezza (m) del corpo appeso:
    prende il raggio massimo in quella fascia (pieghe comprese)."""
    zs = np.arange(z_alto, z_basso - 1e-9, -passo * CM)
    d0 = direzione(azimut)
    R0 = 0.5 * (np.linalg.norm([rif.cx, rif.cy]) + 0.3)
    S = np.zeros(len(zs))
    for i, z in enumerate(zs):
        best = 0.0
        for dz in (-banda, 0.0, banda):
            for da in (-1, 0, 1):
                a = azimut + da * math.degrees(banda / 0.18)
                d = direzione(a)
                h = primo_colpo(rif.saio, (rif.cx, rif.cy, z + dz), d, 0.8)
                if h is not None:
                    best = max(best, h)
        S[i] = best
    return zs, S, d0


def appeso(zs, S, offset, z_partenza, R_partenza):
    """Raggio di un corpo appeso che scende lungo la gonna: non puo' rientrare
    verso l'asse se la stoffa sotto rientra (cade dritto), viene spinto in fuori
    dove la stoffa sporge. offset(z): raggio locale + aria (array come zs)."""
    env = np.maximum.accumulate(S)        # dall'alto in basso
    R = np.maximum(env + offset, R_partenza)
    # lisciatura verso l'alto soltanto
    k = 9
    ker = np.exp(-np.linspace(-2, 2, k) ** 2)
    ker /= ker.sum()
    for _ in range(3):
        Rp = np.convolve(np.pad(R, (k // 2, k // 2), mode='edge'), ker, mode='valid')
        R = np.maximum(Rp, env + offset)
    return R


# =============================================================================
#  1. CORDONE: anello in vita, nodo a destra, coda con tre nodi a barilotto
# =============================================================================
def cordone(rif, alte):
    r = P["CORDA_D"] / 2 * CM
    z0 = P["CORDA_Z"] * CM
    g = P["CORDA_GIOCO"] * CM
    asse = np.array([rif.cx, rif.cy, z0])
    # --- anello in vita: per ogni direzione il primo colpo sulla lana, nella fascia alta quanto la corda
    N = 240
    az = np.linspace(0, 360, N, endpoint=False)
    dirs = np.array([direzione(a) for a in az])
    Rreq = np.zeros(N)
    for i in range(N):
        best = 0.0
        for dz in np.linspace(-(r + g), r + g, 7):
            h = primo_colpo(rif.saio, asse + [0, 0, dz], dirs[i], 0.6)
            if h is not None:
                best = max(best, h)
        Rreq[i] = best + r + g
    R = Rreq.copy()
    for giro in range(4):
        for _ in range(8):
            R = np.maximum((np.roll(R, 1) + 2 * R + np.roll(R, -1)) / 4, Rreq)
        anello = asse + R[:, None] * dirs
        dens = catmull_rom(anello, 6, chiuso=True)
        # controllo 3D: distanza vera dalla lana; dove manca, spingo in fuori
        deficit = np.zeros(N)
        for p in dens:
            q = rif.saio.find_nearest(Vector(p))
            dd = (q[0] - Vector(p)).length
            if dd < r + 0.8 * g:
                a = (math.degrees(math.atan2(-(p[0] - rif.cx), -(p[1] - rif.cy))) + 360) % 360
                k = int(round(a / 360 * N)) % N
                deficit[k] = max(deficit[k], r + g - dd)
        if deficit.max() <= 0:
            break
        Rreq = Rreq + np.maximum.reduce([np.roll(deficit, s) for s in (-2, -1, 0, 1, 2)])
        R = np.maximum(R, Rreq)
    anello = asse + R[:, None] * dirs
    anello_d = ricampiona(catmull_rom(anello, 8, chiuso=True), 0.1 * CM, chiuso=True)
    giro_cm = lunghezze(anello_d, True)[-1] / CM

    # --- nodo di giunzione (mezzo nodo: 1,5 giri attorno all'anello) alla quota della coda
    aJ = P["CODA_AZIMUT"]
    azd = (np.degrees(np.arctan2(-(anello_d[:, 0] - rif.cx), -(anello_d[:, 1] - rif.cy))) + 360) % 360
    iJ = int(np.argmin(np.abs(((azd - aJ) + 180) % 360 - 180)))
    sA = lunghezze(anello_d, True)
    L_ring = sA[-1]
    passo_g = 2.15 * r
    giri = 1.5
    Lh = giri * passo_g
    Tn, Un, Vn = cornici(anello_d, (0, 0, 1), chiuso=True)
    nodo = []
    nh = 200
    for k in range(nh + 1):
        t = k / nh * giri
        s = (sA[iJ] - Lh + passo_g * t) % L_ring
        i = int(np.searchsorted(sA, s) % len(anello_d))
        base = anello_d[i]
        out = norm(np.array([base[0] - rif.cx, base[1] - rif.cy, 0.0]))
        phi = math.pi - 2 * math.pi * t
        nodo.append(base + 2.06 * r * (math.cos(phi) * out + math.sin(phi) * np.array([0, 0, 1.0])))
    nodo = np.array(nodo)
    H = nodo[-1]
    # --- coda: scende lungo la gonna
    zs, S, d0 = profilo_gonna(rif, aJ, H[2] - 0.004, P["CODA_FINE_Z"] * CM - 0.02, r + g)
    nodi_z = np.array(P["NODI_Z"]) * CM
    Lk = P["NODO_GIRI"] * passo_g
    loc = np.full(len(zs), r + g)
    for zk in nodi_z:
        loc = np.where(np.abs(zs - zk) < Lk / 2 + r, 2.15 * r + g, loc)
    fray = P["SFILACCIATA"] * CM
    zf = P["CODA_FINE_Z"] * CM
    loc = np.where(zs < zf + fray, np.maximum(loc, 1.45 * r + g), loc)
    R0 = np.linalg.norm(H[:2] - [rif.cx, rif.cy])
    Rt = appeso(zs, S, loc, H[2], R0)
    coda = np.array([[rif.cx, rif.cy, z] for z in zs]) + Rt[:, None] * d0
    coda = coda[zs >= zf]
    coda = np.vstack([nodo, catmull_rom(np.vstack([H + [0, 0, -0.003], coda]), 4)[1:]])
    coda_d = ricampiona(coda, 0.1 * CM)
    # --- nodi a barilotto: la corda si avvolge su se stessa
    T, U, V = cornici(coda_d, norm(np.array([rif.cx, rif.cy, 0]) - np.array([coda_d[0][0], coda_d[0][1], 0]) + [0, 0, 1e-3]))
    sC = lunghezze(coda_d)
    rho = np.zeros(len(coda_d))
    psi = np.zeros(len(coda_d))
    centri = []
    for zk in nodi_z:
        ik = int(np.argmin(np.abs(coda_d[:, 2] - zk) + (np.arange(len(coda_d)) < len(nodo)) * 10))
        sk = sC[ik]
        t = (sC - (sk - Lk / 2)) / Lk
        dentro = (t >= 0) & (t <= 1)
        rho = np.where(dentro, 1.0 * r * smoothstep(0, 0.14, t) * smoothstep(1, 0.86, t), rho)
        psi = np.where(dentro, 2 * math.pi * P["NODO_GIRI"] * t, psi)
        centri.append(coda_d[ik])
    coda_k = coda_d + rho[:, None] * (np.cos(psi)[:, None] * U + np.sin(psi)[:, None] * V)
    coda_k = ricampiona(coda_k, 0.1 * CM)
    # raggio: normale, poi sfilacciato in punta
    sK = lunghezze(coda_k)
    # punta: legata con lo spago per 1,8 cm, poi i trefoli si aprono appena (0,8 cm)
    leg0, leg1 = sK[-1] - fray, sK[-1] - 0.8 * CM
    rr = r * (1 + 0.08 * smoothstep(leg0 - 0.2 * CM, leg0, sK) * (1 - smoothstep(leg1, leg1 + 0.1 * CM, sK))
              + 0.16 * smoothstep(leg1, sK[-1], sK))
    # --- mesh di gioco
    pz = Pezzo("Cordone", "corda")
    pz.parte_attiva = PARTI["cordone"]
    idx = scegli_campioni(anello_d, P["CORDA_PASSO"] * CM, 14.0, chiuso=True)
    U0a = norm(np.array([rif.cx, rif.cy, z0]) - anello_d[0])
    tubo(pz, anello_d[idx], r, P["CORDA_LATI"], chiuso=True, U0=U0a)
    idx = scegli_campioni(coda_k, P["CORDA_PASSO"] * CM, 40.0)
    # in punta campioni piu' fitti per l'allargamento
    idx = np.unique(np.concatenate([idx, np.where(sK > sK[-1] - fray)[0][::6], [len(coda_k) - 1]]))
    U0c = norm(np.array([rif.cx, rif.cy, coda_k[0][2]]) - coda_k[0])
    tubo(pz, coda_k[idx], rr[idx], P["CORDA_LATI"], chiuso=False, U0=U0c, raggio_uv=r)
    # --- mesh alta (trefoli)
    alte.append(("Cordone_Alta_Anello", "corda", *trefoli(anello_d, r * 1.0, chiuso=True, U0=U0a)))
    alte.append(("Cordone_Alta_Coda", "corda", *trefoli(coda_k, r * 1.0, chiuso=False, U0=U0c,
                                                         sfilaccia=leg1, legatura=(leg0, leg1))))
    info = dict(giro_cm=giro_cm, coda_cm=sK[-1] / CM, nodi=centri, anello=anello_d, r=r, asse=asse,
                J=anello_d[iJ])
    return pz, info


# =============================================================================
#  2. CORONA FRANCESCANA (7 poste)
# =============================================================================
def corona(rif, cord, alte):
    r = cord["r"]
    g = P["CORDA_GIOCO"] * CM
    rs = P["FILO_D"] / 2 * CM
    aR = P["CORONA_AZIMUT"]
    anello_d = cord["anello"]
    azd = (np.degrees(np.arctan2(-(anello_d[:, 0] - rif.cx), -(anello_d[:, 1] - rif.cy))) + 360) % 360
    iR = int(np.argmin(np.abs(((azd - aR) + 180) % 360 - 180)))
    C = anello_d[iR]
    out = norm(np.array([C[0] - rif.cx, C[1] - rif.cy, 0.0]))
    up = np.array([0, 0, 1.0])
    # legaccio attorno al cordone
    rho_t = r + rs + 0.02 * CM
    leg = np.array([C + rho_t * (math.cos(t) * out + math.sin(t) * up) for t in np.linspace(0, 2 * math.pi, 64, endpoint=False)])
    Q = C - up * (rho_t + 0.6 * rs) + out * 0.05 * CM
    rA, rP, rJ = P["AVE_D"] / 2 * CM, P["PATER_D"] / 2 * CM, P["GIUNTO_D"] / 2 * CM
    gap = P["GRANO_GIOCO"] * CM
    seq = []
    for _ in range(7):
        seq += ["P"] + ["A"] * 10
    fili = [seq[:39], seq[39:][::-1]]
    R_cm = np.linalg.norm(C[:2] - [rif.cx, rif.cy])
    delta = math.degrees((P["FILI_DISTANZA"] / 2 * CM) / R_cm)
    grani = []          # (centro, asse, raggio, tipo)
    percorsi = []
    fine = []
    for k, (lato, filo) in enumerate(zip((-1, 1), fili)):
        a = aR + lato * delta
        zs, S, d0 = profilo_gonna(rif, a, Q[2] - 0.006, Q[2] - 0.45, rP)
        Rk = appeso(zs, S, np.full(len(zs), rA + g), Q[2], 0.0)
        pts = np.array([[rif.cx, rif.cy, z] for z in zs]) + Rk[:, None] * d0
        pts = np.vstack([Q, pts])
        dens = ricampiona(catmull_rom(pts, 4), 0.05 * CM)
        s = lunghezze(dens)
        pos = 0.9 * CM
        centri = []
        for tipo in filo:
            rb = rP if tipo == "P" else rA
            pos += rb
            centri.append((pos, rb, tipo))
            pos += rb + gap
        # il grano piu' grosso spinge il filo in fuori: ricalcolo con lo spessore locale
        loc = np.full(len(zs), rA + g)
        zc = np.interp([c[0] for c in centri], s, dens[:, 2])
        for (sp, rb, tipo), z in zip(centri, zc):
            if tipo == "P":
                loc = np.where(np.abs(zs - z) < rb * 1.2, rP + g, loc)
        Rk = appeso(zs, S, loc, Q[2], 0.0)
        pts = np.vstack([Q, np.array([[rif.cx, rif.cy, z] for z in zs]) + Rk[:, None] * d0])
        dens = ricampiona(catmull_rom(pts, 4), 0.05 * CM)
        s = lunghezze(dens)
        Td = tangenti(dens)
        for sp, rb, tipo in centri:
            i = int(np.searchsorted(s, sp))
            grani.append((dens[i], Td[i], rb, tipo))
        i_end = int(np.searchsorted(s, pos + 0.05 * CM))
        percorsi.append(dens[:i_end + 1])
        fine.append(dens[i_end])
    # grano di giunzione sotto i due fili, poi 2 Ave e la crocetta
    zJ = min(fine[0][2], fine[1][2]) - (rA + rJ + 0.12 * CM) * 0.8
    zs, S, d0 = profilo_gonna(rif, aR, zJ + 0.01, zJ - 0.10, rJ)
    locJ = np.full(len(zs), rA + g)
    locJ[np.abs(zs - zJ) < rJ * 1.2] = rJ + g
    RJ = appeso(zs, S, locJ, zs[0], 0.0)
    coda = np.array([[rif.cx, rif.cy, z] for z in zs]) + RJ[:, None] * d0
    coda_d = ricampiona(catmull_rom(coda, 4), 0.05 * CM)
    sJ = lunghezze(coda_d)
    i0 = int(np.argmin(np.abs(coda_d[:, 2] - zJ)))
    s0 = sJ[i0]
    Tc = tangenti(coda_d)
    grani.append((coda_d[i0], Tc[i0], rJ, "J"))
    sp = s0 + rJ + gap + rA
    for _ in range(2):
        i = int(np.searchsorted(sJ, sp))
        grani.append((coda_d[i], Tc[i], rA, "A"))
        sp += 2 * rA + gap
    s_croce = sp - rA + 0.22 * CM
    ic = int(np.searchsorted(sJ, s_croce))
    # filo: anello chiuso (Q -> filo 1 -> giunzione -> filo 2 -> Q) e codina (giunzione -> crocetta)
    J = coda_d[i0]
    loop = np.vstack([percorsi[0], J, percorsi[1][::-1][:-1]])
    loop = ricampiona(catmull_rom(ricampiona(loop, 0.4 * CM, chiuso=True), 4, chiuso=True), 0.1 * CM, chiuso=True)
    codina = coda_d[i0:ic + 4]
    # crocetta: piano rivolto in fuori, appoggiato alla lana
    top = coda_d[ic]
    ey = -Tc[ic]
    qn = rif.saio.find_nearest(Vector(top))
    ez = norm(np.array(top) - np.array(qn[0]))
    ez = norm(ez - (ez @ ey) * ey)
    ex = np.cross(ey, ez)
    croce_h, croce_w, braccio, sp_c = 3.0, 1.9, 0.42, 0.38
    origine = top - ey * (0.30 * CM) - ey * (croce_h / 2 - 0.30) * CM * 0
    # contorno della croce (cm): in alto un occhiello tondo col foro per il filo (y=0)
    b = braccio / 2
    yb = -0.95         # quota del braccio orizzontale
    r_occ = 0.32
    a0 = math.degrees(math.atan2(-math.sqrt(r_occ ** 2 - b ** 2), b))
    occhiello = [(r_occ * math.cos(math.radians(a)), r_occ * math.sin(math.radians(a)))
                 for a in np.linspace(a0, 180 - a0, 9)]
    cont = ([(-b, -croce_h + r_occ), (b, -croce_h + r_occ), (b, yb - b), (croce_w / 2, yb - b), (croce_w / 2, yb + b),
             (b, yb + b)] + occhiello + [(-b, yb + b), (-croce_w / 2, yb + b), (-croce_w / 2, yb - b), (-b, yb - b)])
    foro = [(0.16 * math.cos(t), 0.16 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
    # spinta in fuori finche' la crocetta non tocca la lana
    def dist_min(o):
        dm = 1.0
        for x in np.linspace(-croce_w / 2, croce_w / 2, 5):
            for y in np.linspace(-croce_h + r_occ, r_occ, 7):
                p = o + (x * ex + y * ey) * CM - ez * sp_c / 2 * CM
                q = rif.saio.find_nearest(Vector(p))
                dm = min(dm, (q[0] - Vector(p)).length * (1 if (np.array(p) - np.array(q[0])) @ ez > 0 else -1))
        return dm
    o = np.array(top, float)
    for _ in range(6):
        dm = dist_min(o)
        if dm >= g:
            break
        o = o + ez * (g - dm + 0.01 * CM)
    # mesh di gioco
    pz = Pezzo("Corona", "legno")
    pz.parte_attiva = PARTI["grani"]
    for c, ax, rb, tipo in grani:
        sfera(pz, np.array(c), ax, rb, seg=6 if tipo == "A" else 8, anelli=3 if tipo == "A" else 4)
    pz.parte_attiva = PARTI["crocetta"]
    sagoma(pz, cont, [foro], sp_c, o, ex, ey, ez, 0.04)
    alte.append(("Corona_Alta_Crocetta", "legno", *sagoma_alta("Corona_Alta_Crocetta", cont, [foro], sp_c, o, ex, ey, ez,
                                                                0.05, raccordo=0.04)))
    pf = Pezzo("Corona_Filo", "corda")
    pf.parte_attiva = PARTI["filo"]
    tubo(pf, loop[scegli_campioni(loop, 1.6 * CM, 25.0, True)], rs, 3, chiuso=True, U0=(0, 0, 1))
    cod = ricampiona(np.vstack([codina[:-3], o + ey * 0.0]), 0.1 * CM)
    tubo(pf, cod[scegli_campioni(cod, 1.6 * CM, 25.0)], rs, 3, chiuso=False, U0=(0, 0, 1))
    tubo(pf, leg[::4], rs, 3, chiuso=True, U0=out)
    # mesh alta
    vv, ff = [], []
    for c, ax, rb, tipo in grani:
        v, f = sfera_alta(np.array(c), ax, rb, foro=rs * 1.3)
        ff += [tuple(i + len(vv) for i in q) for q in f]
        vv += list(v)
    alte.append(("Corona_Alta_Grani", "legno", np.array(vv), ff))
    for nome, pts, chiuso in (("Corona_Alta_Filo", loop, True), ("Corona_Alta_Codina", cod, False),
                              ("Corona_Alta_Legaccio", leg, True)):
        alte.append((nome, "corda", *tubo_alto(pts, rs, chiuso)))
    info = dict(grani=len(grani), croce=(o, ex, ey, ez, cont, foro, sp_c), basso_cm=(o - ey * 2.7 * CM)[2] / CM, C=C,
                fili=[len(f) for f in fili])
    return pz, pf, info


# =============================================================================
#  OGGETTI BLENDER DAI PEZZI
# =============================================================================
def collezione(nome, visibile=True):
    c = bpy.data.collections.get(nome)
    if c is None:
        c = bpy.data.collections.new(nome)
        bpy.context.scene.collection.children.link(c)
    c.hide_render = not visibile
    c.hide_viewport = False
    return c


def oggetto_da_pezzo(pz, coll, materiale=None):
    me = bpy.data.meshes.new(pz.nome)
    me.from_pydata(pz.v, [], pz.f)
    uvl = me.uv_layers.new(name=UV)
    flat = np.array([uv for f in pz.uv for uv in f], np.float32).ravel()
    uvl.data.foreach_set("uv", flat)
    a = me.attributes.new("isola", 'INT', 'FACE')
    a.data.foreach_set("value", np.array(pz.isola, np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    if materiale is not None:
        me.materials.append(materiale)
    ob = bpy.data.objects.new(pz.nome, me)
    coll.objects.link(ob)
    return ob


def oggetto_alto(nome, vv, ff, coll):
    me = bpy.data.meshes.new(nome)
    me.from_pydata([tuple(v) for v in np.asarray(vv, float)], [], ff)
    bm = bmesh.new()                       # normali verso l'esterno (servono alle cotture)
    bm.from_mesh(me)
    # prima si saldano i vertici doppi (cuciture delle curve riempite, punti ripetuti dei profili):
    # su una superficie chiusa il ricalcolo delle normali e' affidabile, a pezzi no
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    ob = bpy.data.objects.new(nome, me)
    coll.objects.link(ob)
    return ob


# =============================================================================
#  SAGOME ALTE (Tau, crocetta): contorno raccordato, riempito ed estruso con
#  i bordi arrotondati (curva 2D di Blender convertita in mesh)
# =============================================================================
def raccorda(contorno, raggio, n=4):
    """Arrotonda gli angoli di un contorno 2D (cm) con archi di 'raggio'."""
    c = np.asarray(contorno, float)
    out = []
    m = len(c)
    for i in range(m):
        a, b, d = c[i - 1], c[i], c[(i + 1) % m]
        t1, t2 = norm(b - a), norm(d - b)
        ang = math.acos(np.clip(-(t1 @ t2), -1, 1))
        if ang > math.radians(170):
            out.append(b)
            continue
        dist = min(raggio / math.tan(ang / 2), 0.45 * np.linalg.norm(b - a), 0.45 * np.linalg.norm(d - b))
        p1, p2 = b - t1 * dist, b + t2 * dist
        for k in range(n + 1):
            t = k / n
            # Bezier quadratica tra i due punti di tangenza
            out.append((1 - t) ** 2 * p1 + 2 * (1 - t) * t * b + t ** 2 * p2)
    return np.array(out)


def sposta_contorno(c, d):
    """Contorno 2D (antiorario) spostato verso l'interno di d (d < 0: verso l'esterno)."""
    c = np.asarray(c, float)
    tieni = [0]                    # via i punti quasi coincidenti (direzioni instabili)
    for i in range(1, len(c)):
        if np.linalg.norm(c[i] - c[tieni[-1]]) > 1e-3:
            tieni.append(i)
    if np.linalg.norm(c[tieni[-1]] - c[0]) <= 1e-3 and len(tieni) > 3:
        tieni.pop()
    c = c[tieni]
    n = len(c)
    out = []
    for i in range(n):
        a, b_, c2 = c[i - 1], c[i], c[(i + 1) % n]
        t1, t2 = norm(b_ - a), norm(c2 - b_)
        n1, n2 = np.array([t1[1], -t1[0]]), np.array([t2[1], -t2[0]])
        m = norm(n1 + n2)
        out.append(b_ - m * d / max(m @ n1, 0.3))
    return np.array(out)


def sagoma_alta(nome, contorno, buchi, spessore, origine, ex, ey, ez, arrotonda, raccordo=0.12):
    """Nota: lo smusso (bevel) di una curva 2D riempita allarga la sagoma di 'arrotonda'
    tutto intorno: per questo il contorno si stringe prima (e i fori si allargano), cosi'
    la mesh alta ha esattamente l'ingombro di quella di gioco."""
    # prima si stringe il contorno (spigoli vivi), poi si arrotondano gli angoli: al contrario, negli
    # angoli rientranti l'arco del raccordo si ribalterebbe e lo smusso farebbe delle punte
    contorno = sposta_contorno(contorno, arrotonda)
    if raccordo > 0:
        contorno = raccorda(contorno, raccordo, 4)
    buchi = [sposta_contorno(np.asarray(b, float)[::-1], arrotonda)[::-1] for b in buchi]
    raccordo = 0.0
    cu = bpy.data.curves.new(nome, 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    cu.extrude = max(spessore / 2 - arrotonda, 0.0) * CM
    cu.bevel_depth = arrotonda * CM
    cu.bevel_resolution = 5
    for k, c in enumerate([contorno] + list(buchi)):
        pts = np.asarray(c, float)
        if k > 0:      # i buchi a piu' punti, per un bordo rotondo
            cc = np.asarray(c, float)
            ctr = cc.mean(0)
            rr = np.linalg.norm(cc - ctr, axis=1).max()
            pts = np.array([ctr + rr * np.array([math.cos(t), math.sin(t)]) for t in np.linspace(0, 2 * math.pi, 32, endpoint=False)])
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p[0] * CM, p[1] * CM, 0.0, 1.0)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(nome, cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.column_stack([ex, ey, ez])
    w = origine + co @ M.T
    ff = [tuple(p.vertices) for p in me.polygons]
    bpy.data.meshes.remove(me)
    return w, ff


# =============================================================================
#  3. TAU DI LEGNO CON IL CORDINO
# =============================================================================
def contorno_tau():
    H, W = P["TAU_ALTO"], P["TAU_LARGO"]
    t, b = H / 2, -H / 2
    return [(-1.25, b), (0.0, b + 0.10), (1.25, b), (0.98, -0.9), (0.85, 1.80), (1.9, 1.70), (W / 2 - 0.05, 1.45),
            (W / 2, t + 0.05), (0.0, t), (-W / 2, t + 0.05), (-W / 2 + 0.05, 1.45), (-1.9, 1.70), (-0.85, 1.80),
            (-0.98, -0.9)]


def tau(rif, alte):
    rc = P["TAU_CORDINO_D"] / 2 * CM
    H, W, SP = P["TAU_ALTO"], P["TAU_LARGO"], P["TAU_SPESSO"]
    zc = P["TAU_Z"] * CM
    up = np.array([0, 0, 1.0])
    # piano della mantellina sotto il Tau
    pts = []
    for x in np.linspace(-W / 2 - 0.3, W / 2 + 0.3, 9):
        for z in np.linspace(-H / 2 - 0.3, H / 2 + 0.8, 10):
            h = rif.mant.ray_cast(Vector((x * CM, -0.40, zc + z * CM)), Vector((0, 1, 0)), 1.0)
            if h[0] is not None:
                pts.append(np.array(h[0]))
    pts = np.array(pts)
    c0 = pts.mean(0)
    ez = np.linalg.svd(pts - c0)[2][2]
    if ez[1] > 0:
        ez = -ez
    ey = norm(up - (up @ ez) * ez)
    ex = np.cross(ey, ez)
    tilt = math.atan2(0.42, H)               # la cima si stacca: dietro passa il cordino
    ey, ez = ey * math.cos(tilt) + ez * math.sin(tilt), ez * math.cos(tilt) - ey * math.sin(tilt)
    h0 = rif.mant.ray_cast(Vector((0.0, -0.40, zc)), Vector((0, 1, 0)), 1.0)
    origine = np.array(h0[0]) + ez * (SP / 2 + 0.3) * CM
    cont = contorno_tau()
    foro_c, foro_r = (0.0, H / 2 - 0.85), 0.34
    foro = [(foro_c[0] + foro_r * math.cos(t), foro_c[1] + foro_r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
    campioni = [(x, y) for x in np.linspace(-W / 2, W / 2, 25) for y in np.linspace(-H / 2, H / 2, 29)
                if dentro_poligono((x, y), cont)]

    def spazio_dietro(o):
        gmin = 1.0
        for x, y in campioni:
            p = o + (x * ex + y * ey) * CM - ez * SP / 2 * CM
            h = rif.mant.ray_cast(Vector(p + ez * 0.02), Vector(-ez), 0.1)
            gap = 0.1 if h[0] is None else (h[0] - Vector(p + ez * 0.02)).length - 0.02
            gmin = min(gmin, gap)
        return gmin
    for _ in range(8):
        gm = spazio_dietro(origine)
        if abs(gm - 0.10 * CM) < 0.005 * CM:
            break
        origine = origine + ez * (0.10 * CM - gm)
    # mesh di gioco del Tau
    pz = Pezzo("Tau", "legno")
    pz.parte_attiva = PARTI["tau"]
    sagoma(pz, cont, [foro], SP, origine, ex, ey, ez, 0.12)
    alte.append(("Tau_Alta", "legno", *sagoma_alta("Tau_Alta", cont, [foro], SP, origine, ex, ey, ez, 0.16)))
    # cordino: anello stretto nel foro, nodo sopra, due capi verso il collo
    L = lambda x, y, z: origine + (x * ex + y * ey + z * ez) * CM
    yf = foro_c[1] + foro_r - P["TAU_CORDINO_D"] / 2 - 0.05
    zf = SP / 2 + P["TAU_CORDINO_D"] / 2 + 0.06
    K = L(0, H / 2 + 1.35, 0.0)
    occhiello = [K, L(0, H / 2 + 0.80, 0.42), L(0, H / 2 + 0.15, zf), L(0, foro_c[1] + 0.50, zf),
                 L(0, yf + 0.10, SP / 2 + 0.16), L(0, yf, SP / 2 - 0.05), L(0, yf, 0.0), L(0, yf, -SP / 2 + 0.05),
                 L(0, yf + 0.10, -SP / 2 - 0.16), L(0, foro_c[1] + 0.50, -zf), L(0, H / 2 + 0.15, -zf),
                 L(0, H / 2 + 0.80, -0.42)]
    occhiello = ricampiona(catmull_rom(np.array(occhiello), 10, chiuso=True), 0.05 * CM, chiuso=True)
    capi = []
    for lato in (-1, 1):
        X = lato * P["TAU_TASCA_X"] * CM
        zE = P["TAU_TASCA_Z"] * CM
        zs = np.linspace(K[2] + 0.4 * CM, zE, 40)
        punti = [K + (lato * 0.25 * ex + 0.30 * ey) * CM]
        E0 = None
        for z in zs:
            x = X * smoothstep(K[2], 146.2 * CM, z)
            cc = colpi(rif.mant, (x, -0.40, z), (0, 1, 0), 1.0)
            fronte = [d for d, nd in cc if nd < 0 and -0.40 + d < -0.05]
            if not fronte:
                continue
            y_base = -0.40 + max(fronte)
            punti.append(np.array([x, y_base - (P["TAU_CORDINO_D"] / 2 + 0.06) * CM, z]))
        punti = np.array(punti)
        # tra il nodo e il collo il cordino e' teso: non segue gli avvallamenti
        a, b_ = punti[0], punti[np.argmin(np.abs(punti[:, 2] - 146.0 * CM))]
        for i in range(1, len(punti)):
            if punti[i][2] < b_[2]:
                t = (punti[i][2] - a[2]) / (b_[2] - a[2])
                y_lin = a[1] + t * (b_[1] - a[1])
                punti[i][1] = min(punti[i][1], y_lin)
        capi.append(ricampiona(catmull_rom(punti, 4), 0.1 * CM))
    pc = Pezzo("Tau_Cordino", "corda")
    pc.parte_attiva = PARTI["cordino"]
    tubo(pc, occhiello[scegli_campioni(occhiello, 0.5 * CM, 30.0, True)], rc, 5, chiuso=True, U0=ez)
    for cp in capi:
        tubo(pc, cp[scegli_campioni(cp, 1.2 * CM, 20.0)], rc, 5, chiuso=False, U0=ez)
    sfera(pc, K, ey, 0.34 * CM, seg=6, anelli=4, schiaccia=1.15)
    for nome, pts_, chiuso in (("Tau_Alta_Occhiello", occhiello, True), ("Tau_Alta_Capo1", capi[0], False),
                               ("Tau_Alta_Capo2", capi[1], False)):
        alte.append((nome, "corda", *trefoli(pts_, rc, chiuso=chiuso, U0=ez, passo_torsione=1.3 * CM, lati=8)))
    vv, ff = sfera_alta(K, ey, 0.34 * CM, schiaccia=1.15)
    alte.append(("Tau_Alta_Nodo", "corda", vv, ff))
    info = dict(origine=origine, ex=ex, ey=ey, ez=ez, gap_cm=spazio_dietro(origine) / CM,
                tilt=math.degrees(tilt), K=K, capi=capi)
    return pz, pc, info


def orienta(pz):
    """Gira le facce di ogni parte chiusa in modo che le normali guardino fuori
    (volume con segno positivo)."""
    nf = len(pz.f)
    # vertici nella stessa posizione = stessa parte (gli spigoli vivi hanno vertici doppi)
    chiave = {}
    rappr = []
    for i, v in enumerate(pz.v):
        k = tuple(np.round(np.asarray(v) / 1e-6).astype(np.int64))
        rappr.append(chiave.setdefault(k, i))
    padre = list(range(len(pz.v)))
    def trova(a):
        while padre[a] != a:
            padre[a] = padre[padre[a]]
            a = padre[a]
        return a
    for i, r in enumerate(rappr):
        ra, rb = trova(r), trova(i)
        if ra != rb:
            padre[rb] = ra
    for f in pz.f:
        for i in f[1:]:
            ra, rb = trova(f[0]), trova(i)
            if ra != rb:
                padre[rb] = ra
    V = np.array(pz.v)
    vol = {}
    for k, f in enumerate(pz.f):
        r = trova(f[0])
        a = V[f[0]]
        for j in range(1, len(f) - 1):
            vol[r] = vol.get(r, 0.0) + np.dot(a, np.cross(V[f[j]], V[f[j + 1]])) / 6
    girate = 0
    radici = {}
    pz.seme = []
    for k, f in enumerate(pz.f):
        r = trova(f[0])
        pz.seme.append(radici.setdefault(r, len(radici)))
        if vol[r] < 0:
            pz.f[k] = tuple(reversed(f))
            pz.uv[k] = list(reversed(pz.uv[k]))
            girate += 1
    pz.n_parti = len(radici)
    return girate


# =============================================================================
#  4. SANDALI: suola di cuoio + tre cinghie (avampiede, collo del piede, tallone)
# =============================================================================
def sezione_piano(co, tri, p0, n):
    """Segmenti dell'intersezione di una mesh triangolata con un piano."""
    d = (co - p0) @ n
    segs = []
    for t in tri:
        dv = d[t]
        if (dv > 0).all() or (dv < 0).all():
            continue
        pts = []
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            if (d[a] > 0) != (d[b] > 0):
                s = d[a] / (d[a] - d[b])
                pts.append(co[a] + s * (co[b] - co[a]))
        if len(pts) == 2:
            segs.append(pts)
    return segs


def concatena(segs, tol=1e-5):
    """Unisce i segmenti in polilinee (la piu' lunga per prima)."""
    from collections import defaultdict
    key = lambda p: tuple(np.round(np.asarray(p) / tol).astype(int))
    adj = defaultdict(list)
    for i, (a, b) in enumerate(segs):
        adj[key(a)].append((i, 1))
        adj[key(b)].append((i, 0))
    usati = np.zeros(len(segs), bool)
    catene = []
    for i in range(len(segs)):
        if usati[i]:
            continue
        usati[i] = True
        catena = [segs[i][0], segs[i][1]]
        for verso in (1, 0):
            while True:
                fine = catena[-1] if verso else catena[0]
                prossimo = None
                for j, lato in adj[key(fine)]:
                    if not usati[j]:
                        prossimo = (j, lato)
                        break
                if prossimo is None:
                    break
                j, lato = prossimo
                usati[j] = True
                p = segs[j][lato]
                if verso:
                    catena.append(p)
                else:
                    catena.insert(0, p)
        catene.append(np.array(catena))
    catene.sort(key=lambda c: -len(c))
    return catene


class Piede:
    def __init__(self, rif, lato):
        self.lato = lato                    # +1 sinistro (x>0), -1 destro
        co, tri = rif.corpo_co, rif.corpo_tri
        sel = (np.sign(co[:, 0]) == lato) & (co[:, 2] < 0.16) & (np.abs(co[:, 0]) > 0.05)
        idx = np.where(sel)[0]
        mappa = -np.ones(len(co), int)
        mappa[idx] = np.arange(len(idx))
        t = mappa[tri]
        t = t[(t >= 0).all(1)]
        self.co, self.tri = co[idx], t
        self.bvh = albero(self.co, self.tri)
        self.zmin = self.co[:, 2].min()
        pl = self.co[self.co[:, 2] < self.zmin + 1.0 * CM][:, :2]
        self.impronta = inviluppo_convesso(pl)

    def bordi(self, y):
        """x del bordo mediale e laterale dell'impronta (m) alla quota y."""
        c = np.vstack([self.impronta, self.impronta[:1]])
        xs = []
        for a, b in zip(c[:-1], c[1:]):
            if (a[1] - y) * (b[1] - y) <= 0 and a[1] != b[1]:
                xs.append(a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]))
        xs = sorted(xs, key=abs)
        return xs[0], xs[-1]


def contorno_suola(pd):
    """Impronta allargata e lisciata (m, 2D), in senso antiorario visto dall'alto."""
    c = np.asarray(pd.impronta, float)
    ctr = c.mean(0)
    ang = np.arctan2(c[:, 1] - ctr[1], c[:, 0] - ctr[0])
    c = c[np.argsort(ang)]
    dens = ricampiona(np.column_stack([c, np.zeros(len(c))]), 0.2 * CM, chiuso=True)[:, :2]
    out = []
    n = len(dens)
    for i in range(n):
        t = norm(dens[(i + 1) % n] - dens[i - 1])
        nn = np.array([t[1], -t[0]])
        marg = P["SUOLA_MARGINE"] * CM
        if dens[i][1] < ctr[1] - 0.08:       # davanti alle dita un po' di piu'
            marg += 0.25 * CM * smoothstep(ctr[1] - 0.08, ctr[1] - 0.13, dens[i][1])
        out.append(dens[i] + nn * marg)
    out = np.array(out)
    # lisciatura (media mobile circolare) e ricampionamento
    for _ in range(6):
        out = (np.roll(out, 1, 0) + 2 * out + np.roll(out, -1, 0)) / 4
    out3 = ricampiona(np.column_stack([out, np.zeros(len(out))]), 1.0 * CM, chiuso=True)
    return out3[:, :2]


def suola(pz, pd, alte, nome):
    zt = pd.zmin - 0.04 * CM
    zb = zt - P["SUOLA_SPESSA"] * CM
    c = contorno_suola(pd)
    n = len(c)
    # orientamento antiorario visto dall'alto
    area = 0.5 * np.sum(c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1])
    if area < 0:
        c = c[::-1]
    loop = [Vector((p[0], p[1], 0)) for p in c]
    tris = tessellate_polygon([loop])
    isola_s, isola_g, isola_l = pz.nuova_isola(), pz.nuova_isola(), pz.nuova_isola()
    pz.dens_isola[isola_s] = 0.55       # il piede la copre quasi tutta
    pz.dens_isola[isola_g] = 0.35       # sotto: si vede solo quando il piede si alza
    bt = pz.aggiungi_v([(p[0], p[1], zt) for p in c])          # sopra
    bb = pz.aggiungi_v([(p[0], p[1], zb) for p in c])          # sotto
    rt = pz.aggiungi_v([(p[0], p[1], zt) for p in c])          # bordo: vertici propri -> spigolo vivo
    rb = pz.aggiungi_v([(p[0], p[1], zb) for p in c])
    for t in tris:
        t = list(t)
        a, b, d = c[t[0]], c[t[1]], c[t[2]]
        if (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0]) < 0:
            t = t[::-1]
        pz.parte_attiva = PARTI["suola_sopra"]
        pz.faccia([bt + i for i in t], [(c[i][0] / CM, c[i][1] / CM) for i in t], isola_s)
        pz.parte_attiva = PARTI["suola_sotto"]
        pz.faccia([bb + i for i in t[::-1]], [(-c[i][0] / CM, c[i][1] / CM) for i in t[::-1]], isola_g)
    pz.parte_attiva = PARTI["suola_bordo"]
    per = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1))]) / CM
    h = P["SUOLA_SPESSA"]
    for i in range(n):
        i2 = (i + 1) % n
        pz.faccia([rb + i, rb + i2, rt + i2, rt + i], [(per[i], 0), (per[i + 1], 0), (per[i + 1], h), (per[i], h)], isola_l)
    alte.append((nome, "cuoio", *sagoma_alta(nome, c / CM, [], P["SUOLA_SPESSA"],
                                             np.array([0, 0, 0.5 * (zt + zb)]), np.array([1.0, 0, 0]),
                                             np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), 0.22, raccordo=0.0)))
    return zt, zb, c


def arco_sulla_pelle(pd, centro, e1, e2, phi0, phi1, z_min):
    """Punti della pelle colpiti da raggi che partono da dentro il piede e girano
    nel piano (e1, e2) da phi0 a phi1 (gradi). Tiene il tratto piu' lungo sopra z_min."""
    e1, e2 = norm(e1), norm(e2)
    pts = []
    for a in np.radians(np.linspace(phi0, phi1, 361)):
        d = math.cos(a) * e1 + math.sin(a) * e2
        h = pd.bvh.ray_cast(Vector(centro), Vector(d), 0.3)
        pts.append(None if h[0] is None or h[0].z < z_min else np.array(h[0]))
    tratti, cur = [], []
    for p in pts:
        if p is None:
            if cur:
                tratti.append(cur)
            cur = []
        else:
            cur.append(p)
    if cur:
        tratti.append(cur)
    if not tratti:
        raise RuntimeError("cinghia: nessun punto sulla pelle")
    return np.array(max(tratti, key=len))


def proietta(pd, q):
    hit = pd.bvh.find_nearest(Vector(q))
    return np.array(hit[0]), np.array(hit[1])


def spingi_fuori(inn, nor, pd, passi=12, passo=0.04 * CM):
    """Dove una faccia della cinghia taglia la pelle (fra un vertice e l'altro),
    allontana un po' quei vertici lungo la normale della pelle."""
    L, M = inn.shape[:2]
    T = []
    for i in range(L - 1):
        for j in range(M - 1):
            a, b, c, d = i * M + j, (i + 1) * M + j, (i + 1) * M + j + 1, i * M + j + 1
            T += [(a, b, c), (a, c, d), (a, b, d), (b, c, d)]      # tutte e due le diagonali
    T = np.array(T)
    for _ in range(passi):
        V = inn.reshape(-1, 3)
        coppie = albero(V, T).overlap(pd.bvh)
        if not coppie:
            break
        da_spingere = set()
        for ti, _ in coppie:
            da_spingere.update(T[ti].tolist())
        for k in da_spingere:
            i, j = divmod(k, M)
            if 0 < i < L - 1:
                inn[i, j] += nor[i, j] * passo
            else:                       # estremita' sulla suola: solo in orizzontale, la quota resta
                h = np.array([nor[i, j][0], nor[i, j][1], 0.0])
                inn[i, j] += norm(h) * passo
    return inn


def cinghia(pz, pd, arco, largo, alte, nome, z_suola, segmenti=16, file=3):
    """Cinghia di cuoio aderente al piede lungo l'arco (punti sulla pelle): alle
    due estremita' scende fino alla suola. Mesh di gioco + mesh alta (bordi tondi)."""
    gap, sp = P["CINGHIA_GIOCO"] * CM, P["CINGHIA_SPESSA"] * CM
    arco = ricampiona(catmull_rom(ricampiona(arco, 0.5 * CM), 4), 0.1 * CM)
    T = tangenti(arco)
    N = np.array([proietta(pd, p)[1] for p in arco])
    A = norm(np.cross(T, N))

    def righe(n_lungo, vs):
        idx = np.unique(np.linspace(0, len(arco) - 1, n_lungo + 1).round().astype(int))
        inn = np.zeros((len(idx), len(vs), 3))
        nor = np.zeros((len(idx), len(vs), 3))
        for i, k in enumerate(idx):
            for j, v in enumerate(vs):
                s_, n_ = proietta(pd, arco[k] + A[k] * v)
                inn[i, j] = s_ + n_ * gap
                nor[i, j] = n_
        # estremita' giu' fino alla suola (stessa x, y)
        inn = np.concatenate([inn[:1], inn, inn[-1:]], 0)
        nor = np.concatenate([nor[:1], nor, nor[-1:]], 0)
        inn[0, :, 2] = z_suola - 0.03 * CM
        inn[-1, :, 2] = z_suola - 0.03 * CM
        return spingi_fuori(inn, nor, pd), nor
    # ----- mesh di gioco: 'file' file di traverso (5 per la cinghia larga dell'avampiede)
    vs = np.linspace(-largo / 2, largo / 2, file)
    inn, nor = righe(segmenti, vs)
    est = inn + nor * sp
    L, M = inn.shape[:2]
    s_cm = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(est[:, 1], axis=0), axis=1))]) / CM
    w_cm = vs / CM
    t_cm = P["CINGHIA_SPESSA"]
    bi = pz.aggiungi_v(inn.reshape(-1, 3))
    be = pz.aggiungi_v(est.reshape(-1, 3))
    I = lambda i, j: bi + i * M + j
    E = lambda i, j: be + i * M + j
    isola_e, isola_i = pz.nuova_isola(), pz.nuova_isola()
    pz.dens_isola[isola_i] = 0.5           # lato verso la pelle
    pz.parte_attiva = PARTI["cinghie"]
    for i in range(L - 1):
        for j in range(M - 1):
            pz.faccia([E(i, j), E(i + 1, j), E(i + 1, j + 1), E(i, j + 1)],
                      [(s_cm[i], w_cm[j]), (s_cm[i + 1], w_cm[j]), (s_cm[i + 1], w_cm[j + 1]), (s_cm[i], w_cm[j + 1])], isola_e)
            pz.faccia([I(i, j + 1), I(i + 1, j + 1), I(i + 1, j), I(i, j)],
                      [(s_cm[i], -w_cm[j + 1]), (s_cm[i + 1], -w_cm[j + 1]), (s_cm[i + 1], -w_cm[j]), (s_cm[i], -w_cm[j])], isola_i)
    # fianchi: vertici propri (spigolo vivo con la faccia sopra e con quella sotto)
    for j, segno in ((0, -1), (M - 1, 1)):
        isola = pz.nuova_isola()
        fi = pz.aggiungi_v(inn[:, j])
        fe = pz.aggiungi_v(est[:, j])
        wj = w_cm[j]
        for i in range(L - 1):     # UV locali oltre il bordo: per la texture e' il "taglio" consumato
            pz.faccia([fi + i, fi + i + 1, fe + i + 1, fe + i],
                      [(s_cm[i], wj + segno * t_cm), (s_cm[i + 1], wj + segno * t_cm), (s_cm[i + 1], wj), (s_cm[i], wj)],
                      isola)
    for i in (0, L - 1):         # testate
        isola = pz.nuova_isola()
        ti = pz.aggiungi_v(inn[i])
        te = pz.aggiungi_v(est[i])
        for j in range(M - 1):
            pz.faccia([ti + j, ti + j + 1, te + j + 1, te + j],
                      [(w_cm[j], 0), (w_cm[j + 1], 0), (w_cm[j + 1], t_cm), (w_cm[j], t_cm)], isola)
    # ----- mesh alta: sezione rettangolare con gli spigoli arrotondati
    rb = 0.10 * CM
    prof = []
    for v in np.linspace(-largo / 2 + rb, largo / 2 - rb, 15):
        prof.append((v, 0.0))
    for q in np.linspace(0, math.pi / 2, 5)[1:]:
        prof.append((largo / 2 - rb + rb * math.sin(q), rb - rb * math.cos(q)))
    for h in np.linspace(rb, sp - rb, 3)[1:]:
        prof.append((largo / 2, h))
    for q in np.linspace(0, math.pi / 2, 5)[1:]:
        prof.append((largo / 2 - rb + rb * math.cos(q), sp - rb + rb * math.sin(q)))
    for v in np.linspace(largo / 2 - rb, -largo / 2 + rb, 15)[1:]:
        prof.append((v, sp))
    for q in np.linspace(0, math.pi / 2, 5)[1:]:
        prof.append((-largo / 2 + rb - rb * math.sin(q), sp - rb + rb * math.cos(q)))
    for h in np.linspace(sp - rb, rb, 3)[1:]:
        prof.append((-largo / 2, h))
    for q in np.linspace(0, math.pi / 2, 5)[1:-1]:
        prof.append((-largo / 2 + rb - rb * math.cos(q), rb - rb * math.sin(q)))
    vs2 = sorted(set(round(v / CM, 6) for v, h in prof))
    vs2 = np.array(vs2) * CM
    inn2, nor2 = righe(segmenti * 7, vs2)
    vv, ff = [], []
    L2 = len(inn2)
    Pn = len(prof)
    for i in range(L2):
        for v, h in prof:
            j = int(np.argmin(np.abs(vs2 - v)))
            vv.append(inn2[i, j] + nor2[i, j] * h)
    for i in range(L2 - 1):
        for k in range(Pn):
            k2 = (k + 1) % Pn
            ff.append((i * Pn + k, (i + 1) * Pn + k, (i + 1) * Pn + k2, i * Pn + k2))
    for i, rev in ((0, False), (L2 - 1, True)):
        c = len(vv)
        vv.append(np.mean([vv[i * Pn + k] for k in range(Pn)], 0))
        for k in range(Pn):
            t = (c, i * Pn + (k + 1) % Pn, i * Pn + k)
            ff.append(t[::-1] if rev else t)
    alte.append((nome, "cuoio", np.array(vv), ff))
    return arco


def sandalo(rif, lato, alte):
    pd = Piede(rif, lato)
    L = "S" if lato > 0 else "D"
    pz = Pezzo("Sandalo_" + L, "cuoio")
    zt, zb, c = suola(pz, pd, alte, f"Sandalo_{L}_Alta_Suola")
    e1 = np.array([lato, 0.0, 0.0])          # dal lato mediale al laterale
    zmin = zt + 0.25 * CM

    def centro(y, z):
        xm, xl = pd.bordi(y)
        return np.array([0.5 * (xm + xl), y, z])
    # avampiede: dietro le teste dei metatarsi
    arco = arco_sulla_pelle(pd, centro(-10.0 * CM, 2.0 * CM), e1, norm(np.array([0, 0.18, 1.0])), -30, 210, zmin)
    cinghia(pz, pd, arco, 3.2 * CM, alte, f"Sandalo_{L}_Alta_Avampiede", zt, file=5)
    # collo del piede, inclinata verso la caviglia
    arco = arco_sulla_pelle(pd, centro(-5.0 * CM, 3.0 * CM), e1, norm(np.array([0, -0.30, 1.0])), -30, 210, zmin)
    cinghia(pz, pd, arco, 2.4 * CM, alte, f"Sandalo_{L}_Alta_Collo", zt)
    # tallone: gira dietro il tallone e scende ai lati fino alla suola
    c_t = centro(1.5 * CM, 3.6 * CM)
    arco = arco_sulla_pelle(pd, c_t, e1, norm(np.array([0, 1.0, 0.30])), -12, 192, zmin)
    estremi = []
    for fine in (arco[0], arco[-1]):
        lato_x = 1 if (fine[0] - c_t[0]) * lato > 0 else -1
        xm, xl = pd.bordi(-1.2 * CM)
        x_s = xl if lato_x > 0 else xm
        mete = np.array([x_s, -1.2 * CM, zt + 0.30 * CM])
        tratto = [proietta(pd, fine + (mete - fine) * t)[0] for t in np.linspace(0.12, 1.0, 10)]
        estremi.append(np.array(tratto))
    arco = np.vstack([estremi[0][::-1], arco, estremi[1]])
    cinghia(pz, pd, arco, 2.0 * CM, alte, f"Sandalo_{L}_Alta_Tallone", zt, segmenti=20)
    return pz, dict(zt=zt / CM, zb=zb / CM, suola=c)


# =============================================================================
#  5. ANELLO DI FERRO (anulare destro, osso ring_01_r)
# =============================================================================
def anello(rif, alte):
    co = rif.corpo_co
    a, b = rif.osso("ring_01_r"), rif.osso("ring_02_r")
    ax = norm(b - a)
    c = a + P["ANELLO_POS"] * (b - a)
    # dorso della mano: normale del palmo, dalla parte opposta al pollice
    pol, idx_, mig, mano = rif.osso("thumb_01_r"), rif.osso("index_01_r"), rif.osso("pinky_01_r"), rif.osso("hand_r")
    npalmo = norm(np.cross(idx_ - mano, mig - mano))
    dorso = -npalmo if (pol - mano) @ npalmo > 0 else npalmo
    ed = norm(dorso - (dorso @ ax) * ax)
    es = np.cross(ax, ed)
    # pelle del dito: sezioni vere della mesh nel piano dell'anello (e poco prima e dopo)
    w = P["ANELLO_LARGO"] * CM
    nth = 24
    th = np.linspace(0, 2 * math.pi, nth, endpoint=False)
    vicino = np.linalg.norm(co - c, axis=1) < 4 * CM
    idx = np.where(vicino)[0]
    mappa = -np.ones(len(co), int)
    mappa[idx] = np.arange(len(idx))
    tri_m = mappa[rif.corpo_tri]
    tri_m = tri_m[(tri_m >= 0).all(1)]
    co_m = co[idx]

    def sezione_dito(t):
        p0 = c + ax * t
        for ch in concatena(sezione_piano(co_m, tri_m, p0, ax)):
            if len(ch) < 6 or np.linalg.norm(ch[0] - ch[-1]) > 0.05 * CM:
                continue
            q = np.stack([(ch - p0) @ ed, (ch - p0) @ es], 1)
            # solo il contorno del dito: se la sezione prende anche la piega tra le dita, la scarto
            if dentro_poligono((0.0, 0.0), q) and np.linalg.norm(q, axis=1).max() < 1.25 * CM:
                return q
        return None
    q0 = sezione_dito(0.0)
    if q0 is None:
        raise RuntimeError("anello: non trovo la sezione dell'anulare")
    cc = q0.mean(0)                                   # centro della sezione del dito
    c = c + ed * cc[0] + es * cc[1]
    pelle = np.zeros(nth)
    for t in np.linspace(-0.30 * CM, 0.45 * CM, 6):
        q = sezione_dito(t)
        if q is None:
            continue
        q = q - cc
        for k, a_ in enumerate(th):
            d = np.array([math.cos(a_), math.sin(a_)])
            # raggio: intersezione della semiretta con il contorno
            best = 0.0
            for i in range(len(q) - 1):
                p1, p2 = q[i], q[i + 1]
                M2 = np.array([[d[0], p1[0] - p2[0]], [d[1], p1[1] - p2[1]]])
                if abs(np.linalg.det(M2)) < 1e-14:
                    continue
                tt, uu = np.linalg.solve(M2, p1)
                if tt > 0 and 0 <= uu <= 1:
                    best = max(best, tt)
            pelle[k] = max(pelle[k], best)
    # forma morbida (poche armoniche) che contiene la pelle + aria
    F = np.fft.rfft(pelle)
    F[4:] = 0
    liscio = np.fft.irfft(F, nth)
    r_in = np.maximum(liscio, pelle) + P["ANELLO_GIOCO"] * CM
    for _ in range(3):
        r_in = np.maximum((np.roll(r_in, 1) + 2 * r_in + np.roll(r_in, -1)) / 4, pelle + P["ANELLO_GIOCO"] * CM)
    # spessore e larghezza: sottile ai lati e sotto, castone piatto sopra
    dist_dorso = np.abs((th + math.pi) % (2 * math.pi) - math.pi)
    sopra = smoothstep(math.radians(62), math.radians(26), dist_dorso)
    sp = P["ANELLO_SPESSO"] * CM + (P["ANELLO_SOPRA"] - P["ANELLO_SPESSO"]) * CM * sopra
    r_out = r_in + sp
    piatto = r_in[0] + P["ANELLO_SOPRA"] * CM
    r_out = np.where(dist_dorso < math.radians(30), np.maximum(r_out * 0 + piatto / np.cos(np.minimum(dist_dorso, math.radians(30))), r_in + 0.05 * CM), r_out)
    larg = w * (1 + 0.75 * sopra)

    # controllo sulla pelle vera: bordi interni a distanza dalla pelle, bordi esterni fuori dalle dita vicine
    def distanza(p):
        q, nq, _, d = rif.corpo.find_nearest(Vector(p))
        return d if (Vector(p) - q).dot(nq) >= 0 else -d
    for giro in range(6):
        manca = np.zeros(nth)
        for k in range(nth):
            dirr = math.cos(th[k]) * ed + math.sin(th[k]) * es
            for tl in (-larg[k] / 2, 0.0, larg[k] / 2):
                d = distanza(c + ax * tl + dirr * r_in[k])
                manca[k] = max(manca[k], P["ANELLO_GIOCO"] * CM - d)
        if manca.max() <= 0.002 * CM:
            break
        manca = np.maximum(manca, np.maximum(np.roll(manca, 1), np.roll(manca, -1)) * 0.5)
        r_in = r_in + np.maximum(manca, 0) + 0.005 * CM * (manca > 0)
        r_out = np.maximum(r_out, r_in + 0.08 * CM)
        r_out = np.where(dist_dorso < math.radians(30), np.maximum(r_out, r_in + 0.05 * CM), r_out)
    # spessore: dove l'esterno toccherebbe un dito vicino, piu' sottile (minimo 0,8 mm)
    for k in range(nth):
        dirr = math.cos(th[k]) * ed + math.sin(th[k]) * es
        for _ in range(6):
            dmin = min(distanza(c + ax * tl + dirr * r_out[k]) for tl in (-larg[k] / 2, 0.0, larg[k] / 2))
            if dmin > 0.03 * CM or r_out[k] - r_in[k] <= 0.08 * CM:
                break
            r_out[k] = max(r_out[k] - 0.02 * CM, r_in[k] + 0.08 * CM)

    def profilo(k, n_prof):
        """Punti (t lungo il dito, raggio) attorno alla sezione al k-esimo angolo."""
        ri, ro, lw = r_in[k], r_out[k], larg[k] / 2
        e = min(0.05 * CM, (ro - ri) * 0.4)
        if n_prof == 6:
            return [(-lw, ri), (lw, ri), (lw, ro - e), (lw - e, ro), (-lw + e, ro), (-lw, ro - e)]
        pts = [(x, ri) for x in np.linspace(-lw + e, lw - e, n_prof // 4)]
        for q in np.linspace(0, math.pi / 2, n_prof // 8 + 2)[1:-1]:
            pts.append((lw - e + e * math.sin(q), ri + e - e * math.cos(q)))
        pts += [(lw, h) for h in np.linspace(ri + e, ro - e, n_prof // 8)]
        for q in np.linspace(0, math.pi / 2, n_prof // 8 + 2)[1:-1]:
            pts.append((lw - e + e * math.cos(q), ro - e + e * math.sin(q)))
        pts += [(x, ro) for x in np.linspace(lw - e, -lw + e, n_prof // 4)]
        for q in np.linspace(0, math.pi / 2, n_prof // 8 + 2)[1:-1]:
            pts.append((-lw + e - e * math.sin(q), ro - e + e * math.cos(q)))
        pts += [(-lw, h) for h in np.linspace(ro - e, ri + e, n_prof // 8)]
        for q in np.linspace(0, math.pi / 2, n_prof // 8 + 2)[1:-1]:
            pts.append((-lw + e - e * math.cos(q), ri + e - e * math.sin(q)))
        return pts
    pz = Pezzo("Anello", "ferro")
    pz.parte_attiva = PARTI["anello"]
    prof = [profilo(k, 6) for k in range(nth)]
    np_ = len(prof[0])
    vv = []
    for k in range(nth):
        dirr = math.cos(th[k]) * ed + math.sin(th[k]) * es
        for tl, r_ in prof[k]:
            vv.append(c + ax * tl + dirr * r_)
    b0 = pz.aggiungi_v(vv)
    isola = pz.nuova_isola()
    circ = 2 * math.pi * float(r_out.mean()) / CM
    lp = []
    for j in range(np_):
        q0, q1 = np.array(prof[0][j]), np.array(prof[0][(j + 1) % np_])
        lp.append(np.linalg.norm(q1 - q0) / CM)
    vprof = np.concatenate([[0], np.cumsum(lp)])
    for k in range(nth):
        k2 = (k + 1) % nth
        for j in range(np_):
            j2 = (j + 1) % np_
            u0, u1 = k / nth * circ, (k + 1) / nth * circ
            pz.faccia([b0 + k * np_ + j, b0 + k2 * np_ + j, b0 + k2 * np_ + j2, b0 + k * np_ + j2],
                      [(u0, vprof[j]), (u1, vprof[j]), (u1, vprof[j + 1]), (u0, vprof[j + 1])], isola)
    # mesh alta: profilo arrotondato fitto + Tau inciso sul castone
    nth2 = 192
    th2 = np.linspace(0, 2 * math.pi, nth2, endpoint=False)
    interp = lambda arr: np.interp(th2, np.concatenate([th, [2 * math.pi]]), np.concatenate([arr, arr[:1]]))
    r_in2, r_out2, larg2 = interp(r_in), interp(r_out), interp(larg)
    dd2 = np.abs((th2 + math.pi) % (2 * math.pi) - math.pi)
    r_out2 = np.where(dd2 < math.radians(30), np.maximum(piatto / np.cos(np.minimum(dd2, math.radians(30))), r_in2 + 0.05 * CM), r_out2)
    tau_c = [np.array(p) * 0.085 for p in contorno_tau()]       # Tau di ~0,6 cm
    vv2, ff2 = [], []
    n2 = None
    for k in range(nth2):
        dirr = math.cos(th2[k]) * ed + math.sin(th2[k]) * es
        ri, ro, lw = r_in2[k], r_out2[k], larg2[k] / 2
        e = min(0.05 * CM, (ro - ri) * 0.4)
        pts = []
        save_rin, save_rout, save_l = r_in, r_out, larg
        prof2 = []
        for x in np.linspace(-lw + e, lw - e, 16):
            prof2.append((x, ri, False))
        for q in np.linspace(0, math.pi / 2, 6)[1:-1]:
            prof2.append((lw - e + e * math.sin(q), ri + e - e * math.cos(q), False))
        for h in np.linspace(ri + e, ro - e, 6):
            prof2.append((lw, h, False))
        for q in np.linspace(0, math.pi / 2, 6)[1:-1]:
            prof2.append((lw - e + e * math.cos(q), ro - e + e * math.sin(q), False))
        for x in np.linspace(lw - e, -lw + e, 24):
            prof2.append((x, ro, True))
        for q in np.linspace(0, math.pi / 2, 6)[1:-1]:
            prof2.append((-lw + e - e * math.sin(q), ro - e + e * math.cos(q), False))
        for h in np.linspace(ro - e, ri + e, 6):
            prof2.append((-lw, h, False))
        for q in np.linspace(0, math.pi / 2, 6)[1:-1]:
            prof2.append((-lw + e - e * math.cos(q), ri + e - e * math.sin(q), False))
        n2 = len(prof2)
        for tl, r_, sopra_ in prof2:
            pr = r_
            if sopra_ and dd2[k] < math.radians(30):
                # coordinate sul castone (cm): lungo il dito e di traverso
                u_ = tl / CM
                v_ = (piatto * math.tan(((th2[k] + math.pi) % (2 * math.pi) - math.pi))) / CM
                if dentro_poligono((v_, -u_), tau_c):
                    pr -= 0.03 * CM
            vv2.append(c + ax * tl + dirr * pr)
    for k in range(nth2):
        k2 = (k + 1) % nth2
        for j in range(n2):
            j2 = (j + 1) % n2
            ff2.append((k * n2 + j, k2 * n2 + j, k2 * n2 + j2, k * n2 + j2))
    alte.append(("Anello_Alto", "ferro", np.array(vv2), ff2))
    # distanze: pelle dell'anulare e delle dita vicine
    V = np.array(pz.v)
    dmin_dito = min((rif.corpo.find_nearest(Vector(p))[3] for p in V), default=0)
    info = dict(centro=c, asse=ax, dorso=ed, r_in_cm=(r_in.min() / CM, r_in.max() / CM),
                pelle_cm=(pelle.min() / CM, pelle.max() / CM), dmin_pelle_cm=dmin_dito / CM)
    return pz, info


# =============================================================================
#  6. TUTTI GLI ACCESSORI: costruzione e oggetti Blender
# =============================================================================
GRUPPI = dict(corda=("cordone", "filo", "cordino"), legno=("tau", "grani", "crocetta"),
              cuoio=("suola_bordo", "suola_sopra", "suola_sotto", "cinghie"), ferro=("anello",))


def gruppo_di_parte(codice):
    for g, parti in GRUPPI.items():
        if codice in [PARTI[p] for p in parti]:
            return g
    return None


def costruisci():
    rif = Riferimenti()
    alte = []
    pz_c, info_c = cordone(rif, alte)
    pz_g, pz_f, info_r = corona(rif, info_c, alte)
    pz_t, pz_tc, info_t = tau(rif, alte)
    sand = [sandalo(rif, lato, alte) for lato in (1, -1)]
    pz_a, info_a = anello(rif, alte)
    pezzi = [pz_c, pz_f, pz_tc, pz_g, pz_t, sand[0][0], sand[1][0], pz_a]
    for pz in pezzi:
        orienta(pz)
    info = dict(cordone=info_c, corona=info_r, tau=info_t, sandali=[s[1] for s in sand], anello=info_a)
    return rif, pezzi, alte, info


def svuota(coll):
    for o in list(coll.objects):
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and getattr(me, "users", 1) == 0:
            if isinstance(me, bpy.types.Mesh):
                bpy.data.meshes.remove(me)


def crea_oggetti(pezzi, alte, materiale):
    """Un solo oggetto di gioco (tutti i pezzi) + gli oggetti alti (nascosti)."""
    coll = collezione("ACCESSORI")
    coll_a = collezione("ACCESSORI_ALTA", visibile=False)
    svuota(coll)
    svuota(coll_a)
    V, F, UVa, UVl, ISO, PAR, SEM, PEZ = [], [], [], [], [], [], [], []
    isola0, seme0 = 0, 0
    for k, pz in enumerate(pezzi):
        b = len(V)
        V += pz.v
        for f, uv, isola, parte, seme in zip(pz.f, pz.uv, pz.isola, pz.parti, pz.seme):
            dens = pz.dens_isola.get(isola, 1.0)
            F.append(tuple(i + b for i in f))
            UVl += uv
            UVa += [(u * dens, v * dens) for u, v in uv]
            ISO.append(isola0 + isola)
            PAR.append(parte)
            SEM.append(seme0 + seme)
            PEZ.append(k)
        isola0 += pz.n_isole
        seme0 += pz.n_parti
    me = bpy.data.meshes.new("Accessori_Gioco")
    me.from_pydata(V, [], F)
    for nome, dati in ((UV, UVa), ("UV_Locale", UVl)):
        l = me.uv_layers.new(name=nome)
        l.data.foreach_set("uv", np.array(dati, np.float32).ravel())
    me.uv_layers.active = me.uv_layers[UV]
    for nome, dati in (("isola", ISO), ("parte", PAR), ("seme", SEM), ("pezzo", PEZ)):
        a = me.attributes.new(nome, 'INT', 'FACE')
        a.data.foreach_set("value", np.array(dati, np.int32))
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    me.materials.append(materiale)
    # triangoli (come l'export: Unreal riceve esattamente questi)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new("Accessori_Gioco", me)
    coll.objects.link(ob)
    alti = []
    for nome, tipo, vv, ff in alte:
        o = oggetto_alto(nome, vv, ff, coll_a)
        o["gruppo"] = tipo
        alti.append(o)
    return ob, alti


# =============================================================================
#  7. UV: un solo atlante per tutti gli accessori
# =============================================================================
def seleziona(attivo, altri=()):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in list(altri) + [attivo]:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = attivo


def layer_collection(nome, lc=None):
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.name == nome:
        return lc
    for figlio in lc.children:
        t = layer_collection(nome, figlio)
        if t:
            return t
    return None


def triangoli_uv(me, layer=UV):
    """UV dei triangoli (n, 3, 2) e indice della faccia."""
    me.calc_loop_triangles()
    lt = np.zeros(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get("loops", lt)
    uv = np.zeros(len(me.loops) * 2)
    me.uv_layers[layer].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    pf = np.zeros(len(me.loop_triangles), int)
    me.loop_triangles.foreach_get("polygon_index", pf)
    return uv[lt.reshape(-1, 3)], lt.reshape(-1, 3), pf


def impacchetta(ob):
    modo_oggetto()
    lc = layer_collection("ACCESSORI")
    lc.exclude = False
    seleziona(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.reveal()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=True,
                            merge_overlap=False, margin_method='FRACTION',
                            margin=0.5 * P["MARGINE_PX"] / P["RISOLUZIONE"], pin=False, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    me = ob.data
    tri_uv, lt, pf = triangoli_uv(me)
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lv = np.zeros(len(me.loops), int)
    me.loops.foreach_get("vertex_index", lv)
    p3 = co[lv[lt]]
    a3 = 0.5 * np.linalg.norm(np.cross(p3[:, 1] - p3[:, 0], p3[:, 2] - p3[:, 0]), axis=1) / CM ** 2
    e = tri_uv
    a2 = 0.5 * np.abs((e[:, 1, 0] - e[:, 0, 0]) * (e[:, 2, 1] - e[:, 0, 1]) - (e[:, 1, 1] - e[:, 0, 1]) * (e[:, 2, 0] - e[:, 0, 0]))
    parte = np.zeros(len(me.polygons), int)
    me.attributes["parte"].data.foreach_get("value", parte)
    R = P["RISOLUZIONE"]
    dens = {}
    for nome, cod in PARTI.items():
        m = parte[pf] == cod
        if m.any():
            dens[nome] = math.sqrt(a2[m].sum() * R * R / a3[m].sum())
    # sovrapposizioni: raster dei triangoli
    cont = np.zeros((R, R), np.uint8)
    for t in e * R:
        rasterizza_conta(t, R, cont)
    sovrapposti = int((cont > 1).sum())
    copertura = float((cont > 0).mean())
    return dens, copertura, sovrapposti


def rasterizza_conta(t, res, cont):
    a, b, c = t
    x0 = max(int(math.floor(min(a[0], b[0], c[0]) - 0.5)), 0)
    x1 = min(int(math.ceil(max(a[0], b[0], c[0]) - 0.5)), res - 1)
    y0 = max(int(math.floor(min(a[1], b[1], c[1]) - 0.5)), 0)
    y1 = min(int(math.ceil(max(a[1], b[1], c[1]) - 0.5)), res - 1)
    if x1 < x0 or y1 < y0:
        return
    X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    w0 = (b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0])
    w1 = (c[0] - b[0]) * (Y - b[1]) - (c[1] - b[1]) * (X - b[0])
    w2 = (a[0] - c[0]) * (Y - c[1]) - (a[1] - c[1]) * (X - c[0])
    # regola "in alto a sinistra" semplificata: bordi inclusi da un solo lato
    dentro = ((w0 > 0) & (w1 > 0) & (w2 > 0)) | ((w0 < 0) & (w1 < 0) & (w2 < 0))
    cont[y0:y1 + 1, x0:x1 + 1] += dentro.astype(np.uint8)


def rasterizza_attributi(ob, res):
    """Per ogni pixel dell'atlante: posizione 3D, UV locali (cm), parte, seme.
    (Il 'disegno' delle texture si calcola da questi.)"""
    me = ob.data
    tri_uv, lt, pf = triangoli_uv(me)
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lv = np.zeros(len(me.loops), int)
    me.loops.foreach_get("vertex_index", lv)
    ul = np.zeros(len(me.loops) * 2)
    me.uv_layers["UV_Locale"].data.foreach_get("uv", ul)
    ul = ul.reshape(-1, 2)
    parte = np.zeros(len(me.polygons), int)
    me.attributes["parte"].data.foreach_get("value", parte)
    seme = np.zeros(len(me.polygons), int)
    me.attributes["seme"].data.foreach_get("value", seme)
    pos = np.zeros((res, res, 3), np.float32)
    loc = np.zeros((res, res, 2), np.float32)
    par = np.zeros((res, res), np.int32)
    sem = np.zeros((res, res), np.int32)
    cop = np.zeros((res, res), bool)
    for k in range(len(lt)):
        a, b, c = tri_uv[k] * res
        x0 = max(int(math.floor(min(a[0], b[0], c[0]) - 0.5)), 0)
        x1 = min(int(math.ceil(max(a[0], b[0], c[0]) - 0.5)), res - 1)
        y0 = max(int(math.floor(min(a[1], b[1], c[1]) - 0.5)), 0)
        y1 = min(int(math.ceil(max(a[1], b[1], c[1]) - 0.5)), res - 1)
        if x1 < x0 or y1 < y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l0 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
        l1 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
        l2 = 1 - l0 - l1
        m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not m.any():
            continue
        L = lt[k]
        P3 = co[lv[L]]
        Q = ul[L]
        ys, xs = np.nonzero(m)
        ys, xs = ys + y0, xs + x0
        w = np.stack([l0[m], l1[m], l2[m]], 1)
        pos[ys, xs] = w @ P3
        loc[ys, xs] = w @ Q
        par[ys, xs] = parte[pf[k]]
        sem[ys, xs] = seme[pf[k]]
        cop[ys, xs] = True
    return pos, loc, par, sem, cop


# =============================================================================
#  8. COTTURA: normal map e ombre (AO) dalle mesh alte
# =============================================================================
# (estrusione della gabbia, distanza massima del raggio) in cm, per gruppo
PARAM_COTTURA = dict(corda=(0.15, 0.40), legno=(0.10, 0.25), cuoio=(0.15, 0.40), ferro=(0.06, 0.15))


def cuoci_accessori(ob, alti):
    """Cuoce normal map (DirectX) e ombre a 4096 px, una cottura per gruppo
    (corda, legno, cuoio, ferro): ogni gruppo vede solo le sue mesh alte."""
    sc = bpy.context.scene
    R4 = P["RISOLUZIONE"] * P["SOVRACAMPIONA"]
    stato = dict(engine=sc.render.engine, samples=sc.cycles.samples, device=sc.cycles.device,
                 nascosti={o.name: o.hide_render for o in sc.objects}, world=sc.world)
    coll = bpy.data.collections.new("TEMP_COTTURA7")
    sc.collection.children.link(coll)
    lc = layer_collection("ACCESSORI_ALTA")
    escl = lc.exclude
    lc.exclude = False
    coll_alta = bpy.data.collections["ACCESSORI_ALTA"]
    rend_alta = coll_alta.hide_render
    coll_alta.hide_render = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("TEMP_Mondo")
    ao_vecchia = sc.world.light_settings.distance
    sc.world.light_settings.distance = P["DISTANZA_AO"] * CM
    img = bpy.data.images.new("TEMP_Cottura7", R4, R4, alpha=True, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    m_b = bpy.data.materials.new("TEMP_Bersaglio7")
    m_b.use_nodes = True
    tex = m_b.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    m_b.node_tree.nodes.active = tex
    m_a = bpy.data.materials.new("TEMP_Alta7")
    basse = {}
    risultati = {}
    try:
        for o in sc.objects:
            o.hide_render = True
        for nome in (NOMI["corpo"], NOMI["saio"], NOMI["mant"]):
            bpy.data.objects[nome].hide_render = False
        for o in alti:
            o.hide_render = False
            o.data.materials.clear()
            o.data.materials.append(m_a)
        parte = np.zeros(len(ob.data.polygons), int)
        ob.data.attributes["parte"].data.foreach_get("value", parte)
        for g, parti in GRUPPI.items():
            codici = [PARTI[p] for p in parti]
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bm.faces.ensure_lookup_table()
            via = [f for f in bm.faces if parte[f.index] not in codici]
            bmesh.ops.delete(bm, geom=via, context='FACES')
            me = bpy.data.meshes.new("TEMP_bassa_" + g)
            bm.to_mesh(me)
            bm.free()
            me.materials.clear()
            me.materials.append(m_b)
            o = bpy.data.objects.new(me.name, me)
            coll.objects.link(o)
            o.matrix_world = ob.matrix_world.copy()
            for flag in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                         "visible_volume_scatter", "visible_shadow"):
                setattr(o, flag, False)
            o.hide_render = False
            basse[g] = o
        sc.render.engine = 'CYCLES'
        sc.cycles.device = 'CPU'
        vuoto = np.zeros(R4 * R4 * 4, np.float32)
        buf = np.zeros(R4 * R4 * 4, np.float32)
        for tipo, campioni in (("NORMAL", 2), ("AO", 24)):
            img.pixels.foreach_set(vuoto)
            sc.cycles.samples = campioni
            for g in GRUPPI:
                sorgenti = [o for o in alti if o.get("gruppo") == g]
                if not sorgenti:
                    continue
                seleziona(basse[g], sorgenti)
                est, dist = PARAM_COTTURA[g]
                bpy.ops.object.bake(type=tipo, margin=0, margin_type='EXTEND', use_clear=False, use_cage=False,
                                    uv_layer=UV, target='IMAGE_TEXTURES', save_mode='INTERNAL',
                                    use_split_materials=False, use_selected_to_active=True,
                                    cage_extrusion=est * CM, max_ray_distance=dist * CM,
                                    normal_space='TANGENT', normal_r='POS_X', normal_g='NEG_Y', normal_b='POS_Z')
            img.pixels.foreach_get(buf)
            risultati[tipo] = buf.reshape(R4, R4, 4).copy()
    finally:
        for o in list(coll.objects):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(me)
        bpy.data.collections.remove(coll)
        bpy.data.images.remove(img)
        for m in (m_b, m_a):
            bpy.data.materials.remove(m)
        sc.world.light_settings.distance = ao_vecchia
        if stato["world"] is None:
            w = sc.world
            sc.world = None
            bpy.data.worlds.remove(w)
        sc.render.engine = stato["engine"]
        sc.cycles.samples = stato["samples"]
        sc.cycles.device = stato["device"]
        for o in sc.objects:
            if o.name in stato["nascosti"]:
                o.hide_render = stato["nascosti"][o.name]
        coll_alta.hide_render = rend_alta
        lc.exclude = escl
    # 4096 -> 2048: normali mediate e rinormalizzate, ombre mediate
    f = P["SOVRACAMPIONA"]
    nr = risultati["NORMAL"]
    ok = nr[..., 3] > 0.5
    v = (nr[..., :3] * 2 - 1) * ok[..., None]
    cnt = riduci(ok.astype(np.float32), f)
    vs = riduci(v, f)
    lun = np.linalg.norm(vs, axis=-1, keepdims=True)
    n2 = np.where(lun > 1e-6, vs / np.maximum(lun, 1e-6), np.array([0, 0, 1.0]))
    ao = risultati["AO"]
    oka = ao[..., 3] > 0.5
    ao2 = riduci(ao[..., 0] * oka, f) / np.maximum(riduci(oka.astype(np.float32), f), 1e-9)
    return n2.astype(np.float32), ao2.astype(np.float32), cnt > 0


# =============================================================================
#  9. TEXTURE: colore, ruvidezza e metallo "dipinti" per parte
# =============================================================================
def riduci(a, f):
    h, w = a.shape[:2]
    return a.reshape(h // f, f, w // f, f, *a.shape[2:]).sum(axis=(1, 3))


def sposta(a, dy, dx):
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


def ingrandisci(c):
    h, w = c.shape[:2]
    p = np.pad(c, ((1, 1), (1, 1), (0, 0)), mode='edge')
    r = np.empty((2 * h, w + 2, c.shape[2]), c.dtype)
    r[0::2] = 0.75 * p[1:-1] + 0.25 * p[:-2]
    r[1::2] = 0.75 * p[1:-1] + 0.25 * p[2:]
    out = np.empty((2 * h, 2 * w, c.shape[2]), c.dtype)
    out[:, 0::2] = 0.75 * r[:, 1:-1] + 0.25 * r[:, :-2]
    out[:, 1::2] = 0.75 * r[:, 1:-1] + 0.25 * r[:, 2:]
    return out


def riempi(val, valido, passi=12):
    """Allarga i bordi dei pezzi nello spazio vuoto (come nelle Fasi 5 e 6)."""
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


def salva_png(nome, rgb, cartella):
    h, w = rgb.shape[:2]
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


def lineare_a_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def _hash(ix, iy, iz, seme):
    h = (ix * 374761393 + iy * 668265263 + iz * 1440662683 + seme * 1013904223) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float32) / np.float32(16777215.0)


def rumore(p, seme=0):
    """Rumore 'value' 3D liscio, valori 0-1 (p: array (n, 3))."""
    i = np.floor(p).astype(np.int64)
    f = (p - i).astype(np.float32)
    u = f * f * (3 - 2 * f)
    out = np.zeros(len(p), np.float32)
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                out += wx * wy * wz * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seme)
    return out


def fbm(p, ottave=4, seme=0, guadagno=0.5):
    """Somma di rumori a scale dimezzate, standardizzata (media 0, deviazione ~1)."""
    acc = np.zeros(len(p), np.float32)
    amp, tot = 1.0, 0.0
    for k in range(ottave):
        acc += amp * (rumore(p * (2.0 ** k), seme + 17 * k) - 0.5)
        tot += amp * amp
        amp *= guadagno
    return acc / (math.sqrt(tot) * 0.29)


COLORI = dict(   # lineari
    CORDA=(0.50, 0.44, 0.33), CORDA_SPORCA=(0.26, 0.21, 0.15), FILO=(0.24, 0.18, 0.115), CORDINO=(0.36, 0.29, 0.20),
    OLIVO=(0.34, 0.22, 0.10), OLIVO_VENA=(0.11, 0.065, 0.03), NOCE=(0.085, 0.048, 0.026),
    CUOIO=(0.075, 0.042, 0.022), CUOIO_CONSUMATO=(0.16, 0.10, 0.058), TAGLIO=(0.15, 0.095, 0.055),
    POLVERE=(0.20, 0.17, 0.135), FERRO=(0.20, 0.195, 0.185), RUGGINE=(0.17, 0.065, 0.022),
)


def texture_accessori(ob, n2, ao2, cot2, info, cartella):
    R = P["RISOLUZIONE"]
    pos, loc, par, sem, cop = rasterizza_attributi(ob, R)
    valido = cop | cot2
    ys, xs = np.nonzero(cop)
    p = pos[ys, xs].astype(np.float64) / CM          # cm
    L = loc[ys, xs].astype(np.float64)                # cm (UV locali)
    pa = par[ys, xs]
    se = sem[ys, xs]
    ao = np.clip(ao2[ys, xs], 0, 1)
    n = len(p)
    C = lambda k: np.array(COLORI[k], np.float32)
    col = np.zeros((n, 3), np.float32)
    rug = np.zeros(n, np.float32)
    met = np.zeros(n, np.float32)
    cav = np.ones(n, np.float32)                     # quanto le ombre scuriscono il colore
    largo = fbm(p / 9.0, 3, 1)
    medio = fbm(p / 1.2, 3, 2)
    fine = fbm(p / 0.12, 2, 3)
    # --- corda
    for codice, base in ((PARTI["cordone"], "CORDA"), (PARTI["filo"], "FILO"), (PARTI["cordino"], "CORDINO")):
        m = pa == codice
        if not m.any():
            continue
        r_cm = {PARTI["cordone"]: P["CORDA_D"] / 2, PARTI["filo"]: P["FILO_D"] / 2,
                PARTI["cordino"]: P["TAU_CORDINO_D"] / 2}[codice]
        lay = P["CORDA_TORSIONE"] * r_cm / (P["CORDA_D"] / 2) if codice != PARTI["cordino"] else 1.3
        beta = math.atan2(2 * math.pi * r_cm, lay)
        u, v = L[m, 0], L[m, 1]
        lungo = v * math.cos(beta) + u * math.sin(beta)
        trav = -v * math.sin(beta) + u * math.cos(beta)
        fibre = fbm(np.stack([lungo * 0.6, trav * 14.0, se[m] * 3.1], 1), 3, 7)
        sporco = np.clip(0.30 + 0.22 * largo[m] + 0.10 * medio[m], 0, 1)
        if codice == PARTI["cordone"]:          # la punta della coda tocca tutto: piu' sporca
            sporco = np.clip(sporco + 0.35 * smoothstep(75.0, 52.0, p[m, 2]), 0, 1)
        c = C(base) * (1 + 0.07 * fibre[:, None] + 0.04 * fine[m][:, None])
        col[m] = c + (C("CORDA_SPORCA") * (C(base) / C("CORDA")) - c) * (0.55 * sporco[:, None])
        rug[m] = 0.90 + 0.03 * fibre - 0.04 * sporco
        cav[m] = 0.45
    # --- legno del Tau (olivo): venature attorno a un "tronco" parallelo al gambo
    m = pa == PARTI["tau"]
    if m.any():
        o, ex, ey, ez = (info["tau"][k] for k in ("origine", "ex", "ey", "ez"))
        q = (pos[ys[m], xs[m]] - o) / CM
        x, y, z = q @ ex, q @ ey, q @ ez
        dist = np.hypot(x - 2.3, z + 7.0) + 0.35 * fbm(np.stack([x * 0.8, y * 0.25, z * 0.8], 1), 3, 11)
        anelli = 0.5 + 0.5 * np.sin(2 * math.pi * dist / 0.32)
        vena = np.clip((anelli - 0.72) / 0.28, 0, 1) ** 1.5
        macchie = np.clip(0.5 + 0.35 * fbm(np.stack([x * 0.5, y * 0.12, z * 0.5], 1), 3, 12), 0, 1)
        c = C("OLIVO") * (0.85 + 0.3 * macchie[:, None]) * (1 + 0.05 * fine[m][:, None])
        col[m] = c + (C("OLIVO_VENA") - c) * (0.55 * vena[:, None])
        rug[m] = 0.50 + 0.06 * medio[m] - 0.05 * vena
        cav[m] = 0.35
    # --- grani e crocetta (noce): ogni grano un po' diverso, venatura lungo il foro
    for codice, schiarisci in ((PARTI["grani"], 1.0), (PARTI["crocetta"], 1.15)):
        m = pa == codice
        if not m.any():
            continue
        tono = 0.80 + 0.40 * _hash(se[m].astype(np.int64), np.zeros(m.sum(), np.int64), np.zeros(m.sum(), np.int64), 5)
        u, v = L[m, 0], L[m, 1]
        vena = 0.5 + 0.5 * np.sin(u * 2 * math.pi * 2.2 + 1.5 * fbm(np.stack([u * 2, v * 2, se[m] * 1.7], 1), 2, 13))
        c = C("NOCE") * schiarisci * tono[:, None] * (1 - 0.18 * vena[:, None]) * (1 + 0.05 * fine[m][:, None])
        col[m] = c
        rug[m] = 0.36 + 0.05 * medio[m] + 0.04 * vena
        cav[m] = 0.30
    # --- cuoio
    m = pa == PARTI["cinghie"]
    if m.any():
        # UV locali della cinghia: v = traverso in cm (0 al centro): i bordi sono consumati
        semilarg = np.abs(L[m, 1])
        usura = np.clip(0.7 * smoothstep(0.80, 1.05, semilarg) + 0.25 * medio[m], 0, 1)
        graffi = np.clip(fbm(np.stack([p[m, 0] * 3, p[m, 1] * 3, p[m, 2] * 0.5], 1), 2, 21) - 0.9, 0, 1)
        c = C("CUOIO") * (1 + 0.12 * largo[m][:, None] + 0.06 * fine[m][:, None])
        c = c + (C("CUOIO_CONSUMATO") - c) * (0.6 * usura[:, None] + 0.4 * graffi[:, None])
        polv = smoothstep(2.5, 0.0, p[m, 2])
        col[m] = c + (C("POLVERE") - c) * (0.35 * polv[:, None])
        rug[m] = 0.62 + 0.08 * medio[m] - 0.10 * usura + 0.12 * polv
        cav[m] = 0.30
    m = pa == PARTI["suola_bordo"]
    if m.any():
        h = L[m, 1]                       # 0 = sotto, SUOLA_SPESSA = sopra
        riga = np.exp(-((h - 0.5 * P["SUOLA_SPESSA"]) / 0.06) ** 2)        # due strati di cuoio
        c = C("TAGLIO") * (1 + 0.10 * medio[m][:, None] + 0.06 * fine[m][:, None]) * (1 - 0.45 * riga[:, None])
        polv = smoothstep(0.7, 0.0, h)
        col[m] = c + (C("POLVERE") - c) * (0.45 * polv[:, None])
        rug[m] = 0.80 + 0.05 * medio[m]
        cav[m] = 0.30
    m = pa == PARTI["suola_sopra"]
    if m.any():
        lucido = np.clip(0.5 + 0.4 * largo[m], 0, 1)
        c = C("CUOIO") * 1.15 * (1 + 0.10 * medio[m][:, None] + 0.05 * fine[m][:, None])
        col[m] = c * (1 - 0.15 * lucido[:, None])
        rug[m] = 0.55 - 0.10 * lucido + 0.05 * fine[m]
        cav[m] = 0.55                     # l'impronta del piede (ombra di contatto)
    m = pa == PARTI["suola_sotto"]
    if m.any():
        col[m] = C("POLVERE") * 0.75 * (1 + 0.15 * medio[m][:, None] + 0.10 * fine[m][:, None])
        rug[m] = 0.92
        cav[m] = 0.2
    # --- ferro: base metallica scura, ruggine nei solchi e nell'incisione
    m = pa == PARTI["anello"]
    if m.any():
        rug_mask = np.clip((1 - ao[m]) * 2.2 + 0.35 * medio[m] - 0.25, 0, 1)
        c = C("FERRO") * (1 + 0.10 * medio[m][:, None] + 0.06 * fine[m][:, None])
        col[m] = c + (C("RUGGINE") - c) * rug_mask[:, None]
        met[m] = 1 - rug_mask
        rug[m] = 0.40 + 0.08 * medio[m] + 0.40 * rug_mask
        cav[m] = 0.25
    # ombre nel colore (solo i solchi: il resto lo fa la mappa AO in Unreal)
    col = col * (1 - cav[:, None] * (1 - ao[:, None]) * 0.6)
    BC = np.zeros((R, R, 3), np.float32)
    BC[ys, xs] = col
    ORM = np.zeros((R, R, 3), np.float32)
    ORM[ys, xs, 0] = ao
    ORM[ys, xs, 1] = np.clip(rug, 0.2, 0.98)
    ORM[ys, xs, 2] = np.clip(met, 0, 1)
    # fuori dai pezzi coperti dalla cottura ma non dal raster (bordi): si riempie
    BC = riempi(BC, cop)
    ORM_ao = ORM.copy()
    ORM = riempi(ORM, cop)
    ao_full = np.where(cot2, ao2, ORM[..., 0])
    ORM[..., 0] = riempi(ao_full[..., None].astype(np.float32), cot2 | cop)[..., 0]
    N = riempi(n2, cot2)
    N = N / np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-6)
    salva_png("T_Accessori_BC", lineare_a_srgb(BC), cartella)
    salva_png("T_Accessori_N", N * 0.5 + 0.5, cartella)
    salva_png("T_Accessori_ORM", ORM, cartella)
    st = {}
    for nome, cod in PARTI.items():
        mm = pa == cod
        if mm.any():
            st[nome] = dict(colore=col[mm].mean(0), rug=float(rug[mm].mean()), met=float(met[mm].mean()),
                            ao=float(ao[mm].mean()))
    return st, valido


# =============================================================================
#  10. MATERIALE DI ANTEPRIMA (come sara' in Unreal)
# =============================================================================
def immagine(cartella, nome, colore):
    percorso = os.path.join(cartella, nome + ".png")
    img = bpy.data.images.get(nome + ".png")
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.load(percorso)
    img.colorspace_settings.name = colore
    if bpy.data.filepath:
        img.filepath = bpy.path.relpath(percorso)
    return img


def materiale_accessori(cartella=None):
    mat = bpy.data.materials.get("M_Accessori") or bpy.data.materials.new("M_Accessori")
    mat.diffuse_color = (0.45, 0.38, 0.30, 1.0)
    mat.use_nodes = True
    if cartella is None:
        return mat
    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    out = N("ShaderNodeOutputMaterial")
    bsdf = N("ShaderNodeBsdfPrincipled")
    uvn = N("ShaderNodeUVMap")
    uvn.uv_map = UV
    tb, tn, to = N("ShaderNodeTexImage"), N("ShaderNodeTexImage"), N("ShaderNodeTexImage")
    for t, nome, colore in ((tb, "T_Accessori_BC", 'sRGB'), (tn, "T_Accessori_N", 'Non-Color'),
                            (to, "T_Accessori_ORM", 'Non-Color')):
        t.image = immagine(cartella, nome, colore)
        t.label = nome
        nt.links.new(uvn.outputs["UV"], t.inputs["Vector"])
    sep = N("ShaderNodeSeparateColor")
    inv = N("ShaderNodeMath")
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    comb = N("ShaderNodeCombineColor")
    nmap = N("ShaderNodeNormalMap")
    nmap.uv_map = UV
    nt.links.new(tn.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs[0], comb.inputs[0])
    nt.links.new(sep.outputs[1], inv.inputs[1])
    nt.links.new(inv.outputs[0], comb.inputs[1])
    nt.links.new(sep.outputs[2], comb.inputs[2])
    nt.links.new(comb.outputs[0], nmap.inputs["Color"])
    nt.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
    so = N("ShaderNodeSeparateColor")
    nt.links.new(to.outputs["Color"], so.inputs["Color"])
    nt.links.new(so.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(so.outputs[2], bsdf.inputs["Metallic"])
    mul = N("ShaderNodeMix")
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(tb.outputs["Color"], mul.inputs[6])
    nt.links.new(so.outputs[0], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    pos = {out: (900, 0), bsdf: (600, 0), uvn: (-1100, 0), tb: (-800, 350), tn: (-800, -350), to: (-800, 0),
           sep: (-450, -350), inv: (-250, -420), comb: (-50, -350), nmap: (200, -350), so: (-450, 0), mul: (200, 250)}
    for nodo, xy in pos.items():
        nodo.location = xy
    return mat


# =============================================================================
#  11. ANELLO A PARTE (Skeletal Mesh sull'osso ring_01_r)
# =============================================================================
def separa_anello(ob):
    """Toglie l'anello dall'oggetto degli accessori e ne fa un oggetto figlio
    dell'armatura, con tutti i vertici sull'osso ring_01_r (peso 1)."""
    arm = bpy.data.objects[NOMI["arm"]]
    parte = np.zeros(len(ob.data.polygons), int)
    ob.data.attributes["parte"].data.foreach_get("value", parte)
    coll = bpy.data.collections["ACCESSORI"]
    vecchio = bpy.data.objects.get("Anello_Gioco")
    if vecchio is not None:
        me = vecchio.data
        bpy.data.objects.remove(vecchio, do_unlink=True)
        bpy.data.meshes.remove(me)
    meshes = {}
    for nome, tenere in (("Anello_Gioco", True), ("Accessori_Gioco", False)):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        via = [f for f in bm.faces if (parte[f.index] == PARTI["anello"]) != tenere]
        bmesh.ops.delete(bm, geom=via, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        me = bpy.data.meshes.new(nome)
        bm.to_mesh(me)
        bm.free()
        meshes[nome] = me
    vecchia = ob.data
    for me in meshes.values():
        for m in vecchia.materials:
            me.materials.append(m)
    ob.data = meshes["Accessori_Gioco"]
    bpy.data.meshes.remove(vecchia)
    ob.data.name = "Accessori_Gioco"
    mea = meshes["Anello_Gioco"]
    # coordinate nello spazio dell'armatura (cm), come il corpo MetaHuman
    mea.transform(arm.matrix_world.inverted())
    ann = bpy.data.objects.new("Anello_Gioco", mea)
    coll.objects.link(ann)
    ann.parent = arm
    ann.matrix_parent_inverse = Matrix.Identity(4)
    ann.matrix_basis = Matrix.Identity(4)
    g = ann.vertex_groups.new(name="ring_01_r")
    g.add(list(range(len(mea.vertices))), 1.0, 'REPLACE')
    mod = ann.modifiers.new("Armatura", 'ARMATURE')
    mod.object = arm
    bpy.context.view_layer.update()
    return ann


# =============================================================================
#  12. CONTROLLI: distanze e compenetrazioni (posa di riferimento)
# =============================================================================
NOMI_PARTI = {v: k for k, v in PARTI.items()}


def dati_mesh(o):
    """Vertici (mondo), triangoli, parte e seme per triangolo."""
    me = o.data
    me.calc_loop_triangles()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(o.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    tri = np.zeros(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get("vertices", tri)
    pf = np.zeros(len(me.loop_triangles), int)
    me.loop_triangles.foreach_get("polygon_index", pf)
    par = np.full(len(me.polygons), PARTI["anello"], int)
    sem = np.zeros(len(me.polygons), int)
    if "parte" in me.attributes:
        me.attributes["parte"].data.foreach_get("value", par)
        me.attributes["seme"].data.foreach_get("value", sem)
    return co, tri.reshape(-1, 3), par[pf], sem[pf]


def controlli(acc, ann, rif, info):
    out = {}
    co, tri, par, sem = dati_mesh(acc)
    co2, tri2, par2, sem2 = dati_mesh(ann)
    sem2 = sem2 + sem.max() + 1
    co_all = np.vstack([co, co2])
    tri_all = np.vstack([tri, tri2 + len(co)])
    par_all = np.concatenate([par, par2])
    sem_all = np.concatenate([sem, sem2])
    bvh_acc = albero(co_all, tri_all)
    # compenetrazioni con il corpo
    pc = bvh_acc.overlap(rif.corpo)
    corpo = {}
    for i, j in pc:
        corpo[NOMI_PARTI[par_all[i]]] = corpo.get(NOMI_PARTI[par_all[i]], 0) + 1
    out["corpo"] = corpo
    # compenetrazioni con la stoffa (saio + mantellina): dove sono?
    ps = bvh_acc.overlap(rif.stoffa)
    stoffa = {}
    J, Cr = info["cordone"]["J"], info["corona"]["C"]
    asse = np.array([rif.cx, rif.cy])
    for i, j in ps:
        nome = NOMI_PARTI[par_all[i]]
        c = co_all[tri_all[i]].mean(0)
        dietro = np.linalg.norm(c[:2] - asse) < np.linalg.norm(J[:2] - asse)   # piu' vicino all'asse del cordone
        if nome == "cordone" and np.linalg.norm(c - J) < 3.0 * CM:
            nome = "mezzo nodo, giro dietro il cordone" + (" (dentro la piega, nascosto)" if dietro else "")
        elif nome == "filo" and np.linalg.norm(c - Cr) < 1.5 * CM:
            nome = "legaccio della corona, giro dietro il cordone" + (" (nascosto)" if dietro else "")
        elif nome == "cordone" and abs(c[2] - P["CORDA_Z"] * CM) < 1.5 * CM:
            nome = "anello in vita" + (" (lato verso la stoffa)" if dietro else "")
        stoffa[nome] = stoffa.get(nome, 0) + 1
    out["stoffa"] = stoffa
    # tra accessori diversi (pezzi distinti)
    pa = bvh_acc.overlap(bvh_acc)
    tra = {}
    for i, j in pa:
        if i >= j or sem_all[i] == sem_all[j]:
            continue
        a, b = sorted((NOMI_PARTI[par_all[i]], NOMI_PARTI[par_all[j]]))
        tra[(a, b)] = tra.get((a, b), 0) + 1
    out["tra"] = tra
    # distanze minime (vertici) dalla pelle, per parte, con segno (normale della pelle)
    dist = {}
    for k in np.unique(par_all):
        vv = np.unique(tri_all[par_all == k])
        dm = 1.0
        dentro = 0
        for p in co_all[vv]:
            q, nq, _, d = rif.corpo.find_nearest(Vector(p))
            s = 1 if (Vector(p) - q).dot(nq) >= 0 else -1
            dm = min(dm, s * d)
            dentro += s < 0
        dist[NOMI_PARTI[k]] = (dm / CM, dentro)
    out["pelle"] = dist
    # anello: distanza dalle dita vicine (medio e mignolo) e dall'anulare
    ref = bpy.data.objects[NOMI["corpo"]]
    out["anello_pelle_cm"] = dist.get("anello", (0, 0))[0]
    return out


# =============================================================================
#  13. EXPORT FBX
# =============================================================================
def triangolata(o, nome, coll):
    if len(o.modifiers):
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    else:
        me = o.data.copy()
    ob = bpy.data.objects.new(nome, me)
    coll.objects.link(ob)
    ob.matrix_world = o.matrix_world.copy()
    return ob


OPZIONI_FBX = dict(use_visible=False, use_active_collection=False, use_custom_props=False,
                   global_scale=1.0, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y',
                   apply_unit_scale=True, use_space_transform=True, bake_space_transform=False,
                   mesh_smooth_type='FACE', use_subsurf=False, use_mesh_modifiers=True, use_mesh_edges=False,
                   use_triangles=False, use_tspace=True, colors_type='NONE', add_leaf_bones=False,
                   bake_anim=False, path_mode='AUTO', embed_textures=False, batch_mode='OFF')


def coordinate(o, me=None):
    me = me or o.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(o.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def esporta_render(cartella):
    """Saio + mantellina + accessori in UN oggetto, materiali M_Lana (0) e M_Accessori (1)."""
    modo_oggetto()
    coll = bpy.data.collections.new("TEMP_EXPORT7")
    bpy.context.scene.collection.children.link(coll)
    nomi = (NOMI["saio"], NOMI["mant"], "Accessori_Gioco")
    copie = [triangolata(bpy.data.objects[n], "TEMP_" + n, coll) for n in nomi]
    try:
        seleziona(copie[0], copie[1:])
        bpy.ops.object.join()
        unito = bpy.context.view_layer.objects.active
        unito.name = unito.data.name = "SM_SaioAbate_Render"
        for m in list(unito.modifiers):
            unito.modifiers.remove(m)
        # solo la UV principale (UV_Locale serve solo qui) e niente attributi di lavoro
        me = unito.data
        for l in [l for l in me.uv_layers if l.name != UV]:
            me.uv_layers.remove(l)
        seleziona(unito)
        percorso = os.path.join(cartella, "SM_SaioAbate_Render.fbx")
        bpy.ops.export_scene.fbx(filepath=percorso, use_selection=True, object_types={'MESH'}, **OPZIONI_FBX)
        dati = dict(vert=len(me.vertices), tri=sum(len(p.vertices) - 2 for p in me.polygons), co=coordinate(unito),
                    materiali=[m.name for m in me.materials if m], uv=[u.name for u in me.uv_layers])
    finally:
        for o in list(coll.objects):
            m = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if m.users == 0:
                bpy.data.meshes.remove(m)
        bpy.data.collections.remove(coll)
    return percorso, dati


def esporta_anello(cartella):
    """Armatura del MetaHuman (tutte le ossa, nessuna rinominata) + anello pesato
    al 100% su ring_01_r. L'oggetto armatura 'root' diventa l'osso 'root'."""
    modo_oggetto()
    arm = bpy.data.objects[NOMI["arm"]]
    ann = bpy.data.objects["Anello_Gioco"]
    # l'armatura sta nella collezione dell'import originale (esclusa dalla scena): la includo per l'export
    stati = []
    for c in arm.users_collection:
        lc = layer_collection(c.name)
        if lc is not None:
            stati.append((lc, lc.exclude, lc.hide_viewport, c, c.hide_viewport, c.hide_select))
            lc.exclude = False
            lc.hide_viewport = False
            c.hide_viewport = False
            c.hide_select = False
    sel = {o.name: (o.hide_select, o.hide_viewport) for o in (arm, ann)}
    try:
        for o in (arm, ann):
            o.hide_select = False
            o.hide_set(False)
            o.hide_viewport = False
        bpy.context.view_layer.update()
        seleziona(ann, [arm])
        if not (arm.select_get() and ann.select_get()):
            raise RuntimeError("non riesco a selezionare armatura e anello per l'export")
        percorso = os.path.join(cartella, "SKM_AnelloAbate.fbx")
        bpy.ops.export_scene.fbx(filepath=percorso, use_selection=True, object_types={'ARMATURE', 'MESH'},
                                 primary_bone_axis='Y', secondary_bone_axis='X', armature_nodetype='ROOT',
                                 use_armature_deform_only=False, **OPZIONI_FBX)
    finally:
        for lc, escl, nasc, c, c_nasc, c_sel in stati:
            lc.exclude = escl
            lc.hide_viewport = nasc
            c.hide_viewport = c_nasc
            c.hide_select = c_sel
        for o in (arm, ann):
            o.hide_select, o.hide_viewport = sel[o.name]
    dg = bpy.context.evaluated_depsgraph_get()
    me = ann.evaluated_get(dg).to_mesh()
    co = coordinate(ann, me)
    tri = sum(len(p.vertices) - 2 for p in me.polygons)
    ann.evaluated_get(dg).to_mesh_clear()
    return percorso, dict(co=co, tri=tri)


def verifica_fbx(percorso, co_attese, n_tri, armatura=False):
    """Rilegge l'FBX e confronta posizione e triangoli (e le ossa, per l'anello)."""
    prima = set(bpy.data.objects)
    prime_mesh = set(bpy.data.meshes)
    prime_arm = set(bpy.data.armatures)
    coll = bpy.data.collections.new("TEMP_VERIFICA7")
    bpy.context.scene.collection.children.link(coll)
    lc = layer_collection("TEMP_VERIFICA7")
    bpy.context.view_layer.active_layer_collection = lc
    try:
        bpy.ops.import_scene.fbx(filepath=percorso)
        nuovi = [o for o in bpy.data.objects if o not in prima]
        mesh = [o for o in nuovi if o.type == 'MESH']
        if len(mesh) != 1:
            raise RuntimeError(f"{os.path.basename(percorso)}: attesi 1 oggetto mesh, letti {len(mesh)}")
        o = mesh[0]
        dg = bpy.context.evaluated_depsgraph_get()
        me = o.evaluated_get(dg).to_mesh()
        co = coordinate(o, me)
        tri = sum(len(p.vertices) - 2 for p in me.polygons)
        mats = [m.name.split(".")[0] for m in o.data.materials if m]
        o.evaluated_get(dg).to_mesh_clear()
        scarto = max(np.abs(co.min(0) - co_attese.min(0)).max(), np.abs(co.max(0) - co_attese.max(0)).max()) / CM
        esito = dict(tri=tri, scarto_cm=scarto, materiali=mats, bbox=(co.min(0) / CM, co.max(0) / CM))
        if armatura:
            a = next((x for x in nuovi if x.type == 'ARMATURE'), None)
            orig = bpy.data.objects[NOMI["arm"]]
            dmax = 0.0
            for b in orig.data.bones:
                bb = a.data.bones.get(b.name) if a else None
                if bb is None:
                    dmax = 99.0
                    continue
                dmax = max(dmax, ((a.matrix_world @ bb.head_local) - (orig.matrix_world @ b.head_local)).length / CM)
            esito["ossa"] = len(a.data.bones) if a else 0
            esito["ossa_scarto_cm"] = dmax
            esito["pesi"] = [g.name for g in o.vertex_groups]
    finally:
        for x in [x for x in bpy.data.objects if x not in prima]:
            bpy.data.objects.remove(x, do_unlink=True)
        for m in [m for m in bpy.data.meshes if m not in prime_mesh and m.users == 0]:
            bpy.data.meshes.remove(m)
        for a in [a for a in bpy.data.armatures if a not in prime_arm and a.users == 0]:
            bpy.data.armatures.remove(a)
        for m in [m for m in bpy.data.materials if m.users == 0 and "." in m.name and
                  m.name.split(".")[0] in ("M_Lana", "M_Accessori")]:
            bpy.data.materials.remove(m)
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection
        bpy.data.collections.remove(coll)
    return esito


def ingombro_ue(bmin, bmax):
    """Da Blender (cm) a Unreal: Y invertita."""
    return [round(float(bmin[0]), 2), round(float(-bmax[1]), 2), round(float(bmin[2]), 2)], \
           [round(float(bmax[0]), 2), round(float(-bmin[1]), 2), round(float(bmax[2]), 2)]


# =============================================================================
#  MAIN
# =============================================================================
def main(salva=True):
    import json
    t0 = time.time()
    log("=== REPORT FASE 7 - ACCESSORI: CORDONE, CORONA, TAU, SANDALI, ANELLO ===")
    for nome in NOMI.values():
        if bpy.data.objects.get(nome) is None:
            raise RuntimeError(f"Manca {nome}: apri Saio_Abate_v006.blend (Fase 6).")
    if not bpy.data.filepath:
        raise RuntimeError("Salva prima il file .blend: texture ed export vanno nelle cartelle accanto.")
    modo_oggetto()
    base = os.path.dirname(bpy.data.filepath)
    tex = os.path.join(base, "Texture")
    exp = os.path.join(base, "Export")
    os.makedirs(tex, exist_ok=True)
    os.makedirs(exp, exist_ok=True)
    ok = True

    # 1) geometria
    rif, pezzi, alte, info = costruisci()
    ic, ir, it, ia = info["cordone"], info["corona"], info["tau"], info["anello"]
    log(f"[1] Cordone: giro in vita {ic['giro_cm']:.1f} cm (Ø {P['CORDA_D']:.1f} cm, a {P['CORDA_Z']:.1f} cm da terra), "
        f"coda {ic['coda_cm']:.0f} cm di corda con {len(P['NODI_Z'])} nodi a barilotto, punta a {P['CODA_FINE_Z']:.0f} cm da terra")
    log(f"    Corona: {ir['grani']} grani (7 poste di 1 Pater + 10 Ave, poi giunto, 2 Ave e crocetta), "
        f"fili di {ir['fili'][0]} e {ir['fili'][1]} grani, crocetta fino a {ir['basso_cm']:.0f} cm da terra")
    log(f"    Tau: {P['TAU_ALTO']:.0f} x {P['TAU_LARGO']:.0f} x {P['TAU_SPESSO']:.1f} cm, a {it['gap_cm']:.2f} cm dalla mantellina "
        f"(inclinato di {it['tilt']:.1f} gradi: dietro passa il cordino), cordino nella piega del collo")
    log(f"    Sandali: suola {P['SUOLA_SPESSA']:.1f} cm (da {info['sandali'][0]['zt']:.2f} a {info['sandali'][0]['zb']:.2f} cm: "
        f"sotto il livello dei piedi), 3 cinghie per piede")
    log(f"    Anello: sulla falange dell'anulare destro, foro {ia['r_in_cm'][0] * 2:.2f}-{ia['r_in_cm'][1] * 2:.2f} cm "
        f"(il dito misura {ia['pelle_cm'][0] * 2:.2f}-{ia['pelle_cm'][1] * 2:.2f} cm nelle varie direzioni), "
        f"castone piatto col Tau inciso")
    tot = sum(pz.triangoli for pz in pezzi)
    log("    triangoli (mesh di gioco): " + ", ".join(f"{pz.nome} {pz.triangoli}" for pz in pezzi) + f" -> totale {tot}")
    log(f"    mesh alte (solo per la cottura): {sum(len(a[3]) for a in alte)} facce")

    # 2) oggetti, UV
    mat = materiale_accessori()
    ob, alti = crea_oggetti(pezzi, alte, mat)
    dens, copertura, sovrapposti = impacchetta(ob)
    ok &= sovrapposti == 0
    log(f"[2] UV: un atlante {P['RISOLUZIONE']} px per tutti gli accessori, {copertura * 100:.1f}% usato, "
        f"pixel sovrapposti {sovrapposti}, {P['MARGINE_PX']} px tra i pezzi")
    log("    pixel per cm: " + ", ".join(f"{k} {v:.0f}" for k, v in dens.items()) + " (lana del saio: 8,6)")

    # 3) cottura e texture
    t1 = time.time()
    n2, ao2, cot2 = cuoci_accessori(ob, alti)
    st, valido = texture_accessori(ob, n2, ao2, cot2, info, tex)
    materiale_accessori(tex)
    log(f"[3] Cotture (normal map DirectX + ombre, {P['RISOLUZIONE'] * P['SOVRACAMPIONA']} px ridotte a "
        f"{P['RISOLUZIONE']}): {time.time() - t1:.0f} s; pixel cotti {cot2.mean() * 100:.1f}% dell'atlante")
    for k, v in st.items():
        log(f"    {k:12s} colore medio (lineare) {v['colore'][0]:.3f} {v['colore'][1]:.3f} {v['colore'][2]:.3f}  "
            f"ruvidezza {v['rug']:.2f}  metallo {v['met']:.2f}  ombre {v['ao']:.2f}")
    log("    texture: T_Accessori_BC (sRGB), T_Accessori_N (normal map DirectX), "
        "T_Accessori_ORM (R ombre, G ruvidezza, B metallo)")

    # 4) anello a parte
    ann = separa_anello(ob)
    log(f"[4] Anello_Gioco: oggetto figlio dell'armatura, {len(ann.data.vertices)} vertici tutti su ring_01_r (peso 1)")

    # 5) controlli
    c = controlli(ob, ann, rif, info)
    log("[5] Controlli nella posa di riferimento (A-pose)")
    log("    pelle (distanza minima con segno, cm; vertici dentro): " +
        ", ".join(f"{k} {v[0]:.2f} ({v[1]})" for k, v in c["pelle"].items()))
    log("    triangoli che attraversano il corpo: " + (", ".join(f"{k} {v}" for k, v in c["corpo"].items()) or "nessuno"))
    log("    triangoli che attraversano la stoffa: " + (", ".join(f"{k} {v}" for k, v in c["stoffa"].items()) or "nessuno"))
    log("    tra accessori diversi: " + (", ".join(f"{a}/{b} {v}" for (a, b), v in c["tra"].items()) or "nessuno"))
    ok &= not c["corpo"]

    # 6) export
    percorso, dati = esporta_render(exp)
    v = verifica_fbx(percorso, dati["co"], dati["tri"])
    buono = v["tri"] == dati["tri"] and v["scarto_cm"] < 0.01 and v["materiali"] == ["M_Lana", "M_Accessori"]
    ok &= buono
    log(f"[6] Export/SM_SaioAbate_Render.fbx: {dati['tri']} triangoli (saio + mantellina 7868, accessori "
        f"{dati['tri'] - 7868}), materiali {dati['materiali']}")
    log(f"    riletto: {v['tri']} triangoli, materiali {v['materiali']}, scarto {v['scarto_cm']:.3f} cm -> "
        f"{'OK' if buono else 'DIVERSO'}")
    percorso_a, dati_a = esporta_anello(exp)
    va = verifica_fbx(percorso_a, dati_a["co"], dati_a["tri"], armatura=True)
    buono_a = (va["tri"] == dati_a["tri"] and va["scarto_cm"] < 0.01 and va["ossa_scarto_cm"] < 0.01
               and "ring_01_r" in va["pesi"])
    ok &= buono_a
    log(f"    Export/SKM_AnelloAbate.fbx: {dati_a['tri']} triangoli, scheletro MetaHuman ({va['ossa']} ossa nel file "
        f"riletto, scarto delle ossa {va['ossa_scarto_cm']:.3f} cm), anello spostato di {va['scarto_cm']:.3f} cm "
        f"-> {'OK' if buono_a else 'DIVERSO'}")
    bm_, bM_ = ingombro_ue(dati["co"].min(0) / CM, dati["co"].max(0) / CM)
    am_, aM_ = ingombro_ue(dati_a["co"].min(0) / CM, dati_a["co"].max(0) / CM)
    attesi = {"SM_SaioAbate_Render": dict(tri=dati["tri"], min=bm_, max=bM_, materiali=2),
              "SKM_AnelloAbate": dict(tri=dati_a["tri"], min=am_, max=aM_)}
    with open(os.path.join(exp, "attesi_fase7.json"), "w", encoding="utf-8") as f:
        json.dump(attesi, f, indent=1)
    log(f"    in Unreal l'ingombro atteso del saio con gli accessori e' min {bm_} max {bM_} cm (Export/attesi_fase7.json)")

    # le mesh alte servono solo alla cottura: non restano nel file (lo script le rifa' da zero)
    ca = bpy.data.collections.get("ACCESSORI_ALTA")
    if ca is not None:
        svuota(ca)
        bpy.data.collections.remove(ca)
    log(f"    nel file restano Accessori_Gioco (collezione ACCESSORI) e Anello_Gioco (figlio dell'armatura 'root'); "
        f"le mesh alte no: le rifa' lo script")
    nuovo = os.path.join(base, NOME_FILE_V7)
    log(f"[7] Salvo come {nuovo} (il file v006 resta intatto); {time.time() - t0:.0f} s")
    log("ESITO: " + ("tutti i controlli superati" if ok else "ATTENZIONE: qualche controllo non e' passato"))
    testo = bpy.data.texts.get("REPORT_Fase7") or bpy.data.texts.new("REPORT_Fase7")
    testo.clear()
    testo.write("\n".join(report) + "\n")
    if salva:
        bpy.ops.wm.save_as_mainfile(filepath=nuovo)
    return ok, testo, c


if __name__ == "__main__":
    ok, testo, _ = main()
    spazio = getattr(bpy.context, "space_data", None)
    if spazio is not None and spazio.type == 'TEXT_EDITOR':
        spazio.text = testo
    wm = bpy.context.window_manager
    if wm.windows and not bpy.app.background:
        def disegna(self, context):
            for riga in report[:24]:
                self.layout.label(text=riga)
        wm.popup_menu(disegna, title="Fase 7: fatto" if ok else "Fase 7: controlla il report",
                      icon='INFO' if ok else 'ERROR')
