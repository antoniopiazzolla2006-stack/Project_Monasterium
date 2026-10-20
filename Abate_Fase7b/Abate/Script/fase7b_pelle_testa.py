# =============================================================================
#  FASE 7b - PELLE DELLA TESTA SENZA CANOTTIERA (ritocco delle texture del MetaHuman)
#  Progetto: Abate francescano
#
#  Uso (Python 3 con numpy, scipy, opencv, pillow; NON serve Blender):
#      python fase7b_pelle_testa.py <cartella_originali> <cartella_uscita> <cartella_diagnostica>
#
#  COSA FA
#   1. Trova la canottiera dipinta nelle texture della testa (T_Head_LOD3_*, 2048 px):
#      nella SRMF le spalline hanno ruvidezza 1 (canale G = 255), nel colore sono grigie
#      (saturazione ~0 contro ~0,5 della pelle). Allarga la maschera di 4 px per prendere il
#      bordo sfumato e il rilievo della normal map.
#   2. Divide ogni mappa in due "strati":
#      - TONO (basse frequenze): dentro la maschera si ricava per interpolazione armonica dai
#        bordi (come una membrana elastica tesa sul buco): nessuno stacco di colore possibile;
#      - GRANA (alte frequenze: pori, rilievo fine, macchioline): si clona dalla pelle vera
#        vicina (entro ~300 px, cioe' collo e petto) con un completamento "a toppe"
#        (PatchMatch multi-scala). Le toppe si scelgono guardando INSIEME colore, normal map e
#        SRMF e anche "quanto e' marcata la grana" nel punto: la pelle vicina al bordo basso e'
#        piu' liscia di quella sotto il collo, e le toppe rispettano questa differenza.
#        La STESSA mappa delle toppe vale per tutte le texture: pori, lucidita' e rilievo
#        restano allineati.
#      La grana clonata si riscala all'intensita' del punto in cui va (interpolata dai bordi).
#   3. Raccorda ai bordi (fusione di Poisson).
#   4. LOD5to7 (1024 px): ricavato dal risultato del LOD3 (le texture del LOD5to7 sono il LOD3
#      rimpicciolito: scarto medio < 1,5/255), raccordato ai suoi bordi.
#      Scatter (512/256 px): attorno alle spalline e' uniforme (dev. std 2/255) -> interpolazione armonica.
#   Fuori dalla maschera i pixel restano IDENTICI agli originali (e' controllato).
#   Il canale A della SRMF (F) non contiene la canottiera e non si tocca.
# =============================================================================
import json
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

RNG = np.random.default_rng(7)
PATCH_R = 3                     # toppe 7 x 7
DILATA_2048 = 4                 # px di bordo aggiunti alla maschera (2048)
DILATA_1024 = 2
RIGA_SORGENTE_MIN = 0.74        # pelle sorgente: fascia bassa (collo e petto)
RIGA_SORGENTE_MAX = 2034 / 2048
BORDO_SORGENTE = 12             # px lontani dai bordi dell'immagine (margini UV)
RAGGIO_SORGENTE = 300           # px (a 2048): le toppe si prendono vicino al punto da riempire
SIGMA_TONO = 8.0                # px: separazione tono / grana
SIGMA_INTENSITA = 14.0          # px: finestra per misurare l'intensita' della grana

T0 = time.time()


def log(*a):
    print("[%6.1f s]" % (time.time() - T0), *a, flush=True)


def ridimensiona(img, w, h, interp=cv2.INTER_AREA):
    """cv2.resize a gruppi di <= 4 canali."""
    if img.ndim == 2 or img.shape[2] <= 4:
        r = cv2.resize(img, (w, h), interpolation=interp)
        return r if (img.ndim == 2 or r.ndim == 3) else r[..., None]
    parti = [cv2.resize(np.ascontiguousarray(img[..., a:a + 4]), (w, h), interpolation=interp)
             for a in range(0, img.shape[2], 4)]
    parti = [p if p.ndim == 3 else p[..., None] for p in parti]
    return np.concatenate(parti, -1)


def carica(cartella, nome):
    im = Image.open(os.path.join(cartella, nome + ".PNG"))
    return np.asarray(im).copy(), im.mode


def salva(cartella, nome, arr):
    Image.fromarray(arr).save(os.path.join(cartella, nome + ".PNG"), optimize=True)


def a8(x):
    return np.clip(np.rint(x), 0, 255).astype(np.uint8)


# -----------------------------------------------------------------------------
# maschera
# -----------------------------------------------------------------------------
def maschera(bc, srmf, dilata, frazione_bassa=0.8):
    n = bc.shape[0]
    rgb = bc[..., :3].astype(np.float32)
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    banda = np.zeros(sat.shape, bool)
    banda[int(n * frazione_bassa):] = True
    nucleo = ((srmf[..., 1] >= 250) | (sat < 0.10)) & banda
    largo = ((sat < 0.45) & banda).astype(np.uint8)          # pixel di passaggio attaccati al nucleo
    nl, lab = cv2.connectedComponents(largo, connectivity=8)
    tieni = np.unique(lab[nucleo])
    tieni = tieni[tieni > 0]
    m = np.isin(lab, tieni) | nucleo
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilata + 1, 2 * dilata + 1))
    return cv2.dilate(m.astype(np.uint8), k) > 0


# -----------------------------------------------------------------------------
# sistema di Poisson sul buco (fattorizzato una volta, riusato per tutte le mappe)
# -----------------------------------------------------------------------------
class Poisson:
    """Incognite = pixel del buco. Bordo: valori noti dei vicini fuori dal buco (Dirichlet);
    bordi dell'immagine: derivata nulla (Neumann)."""

    def __init__(self, buco):
        self.buco = buco
        H, W = buco.shape
        ys, xs = np.nonzero(buco)
        self.ys, self.xs = ys, xs
        n = len(ys)
        idx = -np.ones((H, W), np.int64)
        idx[ys, xs] = np.arange(n)
        righe, colonne, valori = [], [], []
        diag = np.zeros(n)
        self.noti = []                     # (indici incognite, y, x) dei vicini noti
        for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            y2, x2 = ys + dy, xs + dx
            dentro = (y2 >= 0) & (y2 < H) & (x2 >= 0) & (x2 < W)
            diag[dentro] += 1
            k = np.nonzero(dentro)[0]
            yy, xx = y2[dentro], x2[dentro]
            nel = buco[yy, xx]
            righe.append(k[nel]); colonne.append(idx[yy[nel], xx[nel]]); valori.append(-np.ones(nel.sum()))
            self.noti.append((k[~nel], yy[~nel], xx[~nel]))
        righe.append(np.arange(n)); colonne.append(np.arange(n)); valori.append(diag)
        A = coo_matrix((np.concatenate(valori), (np.concatenate(righe), np.concatenate(colonne))),
                       shape=(n, n)).tocsc()
        self.lu = splu(A)
        self.n = n

    def armonica(self, img):
        """Riempie il buco con l'interpolazione armonica dei valori al bordo."""
        img = img.astype(np.float64)
        c = img.shape[2] if img.ndim == 3 else 1
        v = img.reshape(img.shape[0], img.shape[1], c)
        b = np.zeros((self.n, c))
        for k, yy, xx in self.noti:
            np.add.at(b, k, v[yy, xx])
        sol = self.lu.solve(b)
        out = v.copy()
        out[self.ys, self.xs] = sol
        return out.reshape(img.shape)

    def fondi(self, orig, guida):
        """guida + c, con c armonica e c = orig - guida sui vicini noti (raccordo dei bordi)."""
        o = orig.astype(np.float64)
        g = guida.astype(np.float64)
        c = o.shape[2]
        b = np.zeros((self.n, c))
        for k, yy, xx in self.noti:
            np.add.at(b, k, o[yy, xx] - g[yy, xx])
        sol = self.lu.solve(b)
        out = o.copy()
        out[self.ys, self.xs] = g[self.ys, self.xs] + sol
        return out


def sfoca_escluso(img, buco, sigma):
    """Sfocatura gaussiana che ignora i pixel del buco (convoluzione normalizzata)."""
    noto = (~buco).astype(np.float32)
    if img.ndim == 2:
        num = cv2.GaussianBlur(img * noto, (0, 0), sigma)
    else:
        num = np.stack([cv2.GaussianBlur(np.ascontiguousarray(img[..., k]) * noto, (0, 0), sigma)
                        for k in range(img.shape[2])], -1)
    den = cv2.GaussianBlur(noto, (0, 0), sigma)
    den = np.maximum(den, 1e-4)
    return num / (den if img.ndim == 2 else den[..., None])


# -----------------------------------------------------------------------------
# PatchMatch + voto, vettorizzato
# -----------------------------------------------------------------------------
OFFS = np.array([(dy, dx) for dy in range(-PATCH_R, PATCH_R + 1) for dx in range(-PATCH_R, PATCH_R + 1)], np.int32)


class Livello:
    def __init__(self, F, buco, sorgente_valida, raggio, votabili):
        self.F = F.astype(np.float32)
        self.H, self.W, self.C = F.shape
        self.buco = buco
        self.raggio = raggio
        self.votabili = np.asarray(votabili)
        r = PATCH_R
        k = np.ones((2 * r + 1, 2 * r + 1), np.uint8)
        self.sv = cv2.erode(sorgente_valida.astype(np.uint8), k, borderType=cv2.BORDER_CONSTANT, borderValue=0) > 0
        self.sv_y, self.sv_x = np.nonzero(self.sv)
        tg = cv2.dilate(buco.astype(np.uint8), k) > 0
        self.ty, self.tx = np.nonzero(tg)
        self.nt = len(self.ty)
        self.Wp = np.pad(np.ones((self.H, self.W), np.float32), r, mode="constant")
        self.aggiorna_pad()

    def aggiorna_pad(self):
        r = PATCH_R
        self.Fp = np.pad(self.F, ((r, r), (r, r), (0, 0)), mode="edge")

    def toppe_bersaglio(self):
        r = PATCH_R
        yy = self.ty[:, None] + OFFS[None, :, 0] + r
        xx = self.tx[:, None] + OFFS[None, :, 1] + r
        return self.Fp[yy, xx], self.Wp[yy, xx]

    def distanza(self, tv, tw, sy, sx):
        sv = self.F[sy[:, None] + OFFS[None, :, 0], sx[:, None] + OFFS[None, :, 1]]
        d = ((tv - sv) ** 2).sum(-1)
        return (d * tw).sum(-1) / np.maximum(tw.sum(-1), 1e-6)

    def valido(self, y, x, ty, tx):
        ok = (y >= 0) & (y < self.H) & (x >= 0) & (x < self.W)
        ok &= (y - ty) ** 2 + (x - tx) ** 2 <= self.raggio ** 2
        out = np.zeros(len(y), bool)
        out[ok] = self.sv[y[ok], x[ok]]
        return out

    def init_casuale(self, sel=None):
        """Sorgente casuale entro il raggio (piu' tentativi, poi il punto sorgente piu' vicino)."""
        if sel is None:
            sel = np.arange(self.nt)
        ny = np.full(len(sel), -1, np.int64)
        nx = np.full(len(sel), -1, np.int64)
        ty, tx = self.ty[sel], self.tx[sel]
        manca = np.ones(len(sel), bool)
        for _ in range(40):
            if not manca.any():
                break
            m = np.nonzero(manca)[0]
            a = RNG.uniform(0, 2 * np.pi, len(m))
            rr = self.raggio * np.sqrt(RNG.uniform(0, 1, len(m)))
            cy = np.rint(ty[m] + rr * np.sin(a)).astype(np.int64)
            cx = np.rint(tx[m] + rr * np.cos(a)).astype(np.int64)
            ok = self.valido(cy, cx, ty[m], tx[m])
            ny[m[ok]], nx[m[ok]] = cy[ok], cx[ok]
            manca[m[ok]] = False
        if manca.any():  # ripiego: il punto sorgente piu' vicino
            m = np.nonzero(manca)[0]
            for i in m:
                d = (self.sv_y - ty[i]) ** 2 + (self.sv_x - tx[i]) ** 2
                j = np.argmin(d)
                ny[i], nx[i] = self.sv_y[j], self.sv_x[j]
        return ny, nx

    def patchmatch(self, ny, nx, iterazioni, raggio_max, blocco=50000):
        indice = -np.ones((self.H, self.W), np.int64)
        indice[self.ty, self.tx] = np.arange(self.nt)
        tv_all, tw_all = self.toppe_bersaglio()
        dist = np.empty(self.nt, np.float32)
        for a in range(0, self.nt, blocco):
            s = slice(a, a + blocco)
            dist[s] = self.distanza(tv_all[s], tw_all[s], ny[s], nx[s])

        def prova(cy, cx, sel):
            ok = self.valido(cy, cx, self.ty[sel], self.tx[sel])
            if not ok.any():
                return
            sel, cy, cx = sel[ok], cy[ok], cx[ok]
            for a in range(0, len(sel), blocco):
                s = slice(a, a + blocco)
                ii = sel[s]
                d = self.distanza(tv_all[ii], tw_all[ii], cy[s], cx[s])
                meglio = d < dist[ii]
                jj = ii[meglio]
                ny[jj] = cy[s][meglio]
                nx[jj] = cx[s][meglio]
                dist[jj] = d[meglio]

        tutti = np.arange(self.nt)
        for it in range(iterazioni):
            passi = [1, 2, 4, 8] if it == 0 else [1, 2]
            for passo in passi:
                for dy, dx in ((0, passo), (passo, 0), (0, -passo), (-passo, 0)):
                    py, px = self.ty - dy, self.tx - dx
                    ok = (py >= 0) & (py < self.H) & (px >= 0) & (px < self.W)
                    j = np.full(self.nt, -1, np.int64)
                    j[ok] = indice[py[ok], px[ok]]
                    sel = tutti[j >= 0]
                    jj = j[j >= 0]
                    prova(ny[jj] + dy, nx[jj] + dx, sel)
            rr = raggio_max
            while rr >= 1:
                cy = ny + RNG.integers(-rr, rr + 1, self.nt)
                cx = nx + RNG.integers(-rr, rr + 1, self.nt)
                prova(cy, cx, tutti)
                rr //= 2
            cy, cx = self.init_casuale()
            prova(cy, cx, tutti)
        return ny, nx, dist

    def vota(self, ny, nx, dist):
        """Aggiorna nel buco i canali 'votabili' (grana) con la media pesata delle toppe."""
        s2 = np.percentile(dist, 75) + 1e-6
        w = np.exp(-dist / (2 * s2)).astype(np.float64)
        by, bx = np.nonzero(self.buco)
        nb = len(by)
        compatto = -np.ones((self.H, self.W), np.int64)
        compatto[by, bx] = np.arange(nb)
        ch = self.votabili
        acc = np.zeros((nb, len(ch)), np.float64)
        wacc = np.zeros(nb, np.float64)
        for oy, ox in OFFS:
            y = self.ty + oy
            x = self.tx + ox
            ok = (y >= 0) & (y < self.H) & (x >= 0) & (x < self.W)
            f = compatto[y[ok], x[ok]]
            inb = f >= 0
            f = f[inb]
            vals = self.F[ny[ok][inb] + oy, nx[ok][inb] + ox][:, ch].astype(np.float64)
            ww = w[ok][inb]
            for k in range(len(ch)):
                acc[:, k] += np.bincount(f, weights=ww * vals[:, k], minlength=nb)
            wacc += np.bincount(f, weights=ww, minlength=nb)
        sel = wacc > 0
        nuovo = self.F[by, bx]
        nuovo[np.ix_(sel, ch)] = (acc[sel] / wacc[sel, None]).astype(np.float32)
        self.F[by, bx] = nuovo
        self.aggiorna_pad()


def completa(F, buco, sorgente, votabili, livelli=4):
    """Completamento multi-scala; F contiene gia' nel buco i canali fissi (tono, intensita')
    e zeri nei canali di grana. Restituisce (livello finale, nnf)."""
    piramide = [(F, buco, sorgente)]
    for _ in range(livelli - 1):
        f, b, s = piramide[-1]
        h, w = b.shape
        f2 = ridimensiona(f, w // 2, h // 2)
        b2 = cv2.resize(b.astype(np.float32), (w // 2, h // 2), interpolation=cv2.INTER_AREA) > 0
        s2 = cv2.resize(s.astype(np.float32), (w // 2, h // 2), interpolation=cv2.INTER_AREA) > 0.999
        piramide.append((f2, b2, s2))
    nnf = None
    L = None
    for lv in range(livelli - 1, -1, -1):
        f, b, s = piramide[lv]
        scala = 2 ** lv
        L = Livello(f.copy(), b, s, RAGGIO_SORGENTE / scala, votabili)
        if nnf is None:
            ny, nx = L.init_casuale()
            em, pm, rmax = 6, 5, int(RAGGIO_SORGENTE / scala)
        else:
            pmap_y, pmap_x = nnf
            gy = np.clip(L.ty // 2, 0, pmap_y.shape[0] - 1)
            gx = np.clip(L.tx // 2, 0, pmap_y.shape[1] - 1)
            cy = pmap_y[gy, gx].astype(np.int64) * 2 + (L.ty % 2)
            cx = pmap_x[gy, gx].astype(np.int64) * 2 + (L.tx % 2)
            ok = (pmap_y[gy, gx] >= 0) & L.valido(cy, cx, L.ty, L.tx)
            ny, nx = L.init_casuale()
            ny[ok], nx[ok] = cy[ok], cx[ok]
            em, pm, rmax = (4, 4, 32) if lv > 0 else (3, 4, 16)
            L.vota(ny, nx, np.ones(L.nt, np.float32))
        for e in range(em):
            ny, nx, dist = L.patchmatch(ny, nx, pm, rmax)
            L.vota(ny, nx, dist)
            rmax = max(rmax // 2, 4)
        log(f"  livello {lv} ({L.W} px): bersagli {L.nt}, distanza media {dist.mean():.3f}")
        pmap_y = -np.ones((L.H, L.W), np.int32)
        pmap_x = -np.ones((L.H, L.W), np.int32)
        pmap_y[L.ty, L.tx] = ny
        pmap_x[L.ty, L.tx] = nx
        nnf = (pmap_y, pmap_x)
    return L, nnf


def normalizza_normali(n8):
    x = n8[..., 0] / 255.0 * 2 - 1
    y = n8[..., 1] / 255.0 * 2 - 1
    l = np.sqrt(np.maximum(x * x + y * y, 1e-12))
    s = np.where(l > 0.999, 0.999 / l, 1.0)
    x, y = x * s, y * s
    z = np.sqrt(np.maximum(1 - x * x - y * y, 0))
    return np.stack([(x + 1) / 2 * 255, (y + 1) / 2 * 255, (z + 1) / 2 * 255], -1)


def main():
    src, dst, diag = sys.argv[1:4]
    os.makedirs(dst, exist_ok=True)
    os.makedirs(diag, exist_ok=True)
    rep = {}
    bc, _ = carica(src, "T_Head_LOD3_BC_VT")
    nm, _ = carica(src, "T_Head_LOD3_N_VT")
    sr, _ = carica(src, "T_Head_LOD3_SRMF_VT")
    sc, _ = carica(src, "T_Head_LOD3_Scatter_VT")
    N = bc.shape[0]

    buco = maschera(bc, sr, DILATA_2048)
    rep["LOD3_pixel_maschera"] = int(buco.sum())
    log("maschera LOD3:", buco.sum(), "pixel")
    P = Poisson(buco)
    log("sistema di Poisson pronto:", P.n, "incognite")

    # ---- tono e grana di ogni mappa (fuori dal buco) ----
    mappe = {"bc": bc[..., :3].astype(np.float32), "n": nm[..., :2].astype(np.float32),
             "s": sr[..., :2].astype(np.float32)}
    tono, grana, ampiezza = {}, {}, {}
    for k, m in mappe.items():
        t = sfoca_escluso(m, buco, SIGMA_TONO)
        g = m - t
        g[buco] = 0
        tono[k], grana[k] = t, g
        # intensita' della grana (rms locale): per bc dalla luminanza, per le altre dai canali insieme
        if k == "bc":
            gl = 0.299 * g[..., 0] + 0.587 * g[..., 1] + 0.114 * g[..., 2]
            e = gl ** 2
        else:
            e = (g ** 2).mean(-1)
        a = np.sqrt(np.maximum(sfoca_escluso(e, buco, SIGMA_INTENSITA), 1e-6))
        ampiezza[k] = a
    # dentro il buco: tono e intensita' interpolati dai bordi (membrana)
    tono_b = {k: P.armonica(v) for k, v in tono.items()}
    ampiezza_b = {k: np.exp(P.armonica(np.log(v + 1e-3)[..., None])[..., 0]) for k, v in ampiezza.items()}
    log("tono e intensita' interpolati nel buco")

    # ---- regione sorgente ----
    regione = np.zeros((N, N), bool)
    regione[int(N * RIGA_SORGENTE_MIN):int(N * RIGA_SORGENTE_MAX), BORDO_SORGENTE:N - BORDO_SORGENTE] = True
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * (PATCH_R + 6) + 1, 2 * (PATCH_R + 6) + 1))
    vicino_buco = cv2.dilate(buco.astype(np.uint8), k) > 0
    # macchie riconoscibili (nei, la chiazza rosa del collo): non si clonano
    Y = 0.299 * bc[..., 0] + 0.587 * bc[..., 1] + 0.114 * bc[..., 2]
    Cr = bc[..., 0].astype(np.float32) - Y
    anom = np.zeros((N, N), bool)
    for c in (Y.astype(np.float32), Cr):
        med = cv2.medianBlur(np.clip(c + (128 if c is Cr else 0), 0, 255).astype(np.uint8), 31).astype(np.float32)
        d = np.clip(c + (128 if c is Cr else 0), 0, 255) - med
        s_ = d[regione & ~vicino_buco].std()
        anom |= np.abs(d) > 3.5 * s_
    anom = cv2.morphologyEx(anom.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    anom = cv2.dilate(anom, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) > 0
    sorgente = regione & ~vicino_buco & ~anom
    rep["LOD3_pixel_sorgente"] = int(sorgente.sum())
    rep["LOD3_pixel_macchie_escluse"] = int((anom & regione & ~vicino_buco).sum())
    log("sorgente:", sorgente.sum(), "pixel; macchie escluse:", rep["LOD3_pixel_macchie_escluse"])

    # ---- caratteristiche per scegliere le toppe ----
    def norm(x):
        return (x - x[sorgente].mean()) / (x[sorgente].std() + 1e-6)

    gY = 0.299 * grana["bc"][..., 0] + 0.587 * grana["bc"][..., 1] + 0.114 * grana["bc"][..., 2]
    aY = ampiezza["bc"]
    canali = [
        (gY / aY, 1.0, True),                                   # grana della luminanza (normalizzata)
        ((grana["bc"][..., 0] - gY) / aY, 0.5, True),           # grana del rosso relativo
        (grana["n"][..., 0] / ampiezza["n"], 0.8, True),        # grana della normal map
        (grana["n"][..., 1] / ampiezza["n"], 0.8, True),
        (grana["s"][..., 1] / ampiezza["s"], 0.4, True),        # grana della ruvidezza
        (None, 0.6, False),                                     # log intensita' grana colore (fissa nel buco)
        (None, 0.4, False),                                     # log intensita' grana normal map
        (None, 0.15, False),                                    # tono (luminanza), fisso nel buco
    ]
    feat = []
    votabili = []
    for i, (c, w, vot) in enumerate(canali):
        if c is not None:
            c = c.copy()
            c[buco] = 0
            feat.append(w * c / (c[sorgente].std() + 1e-6))
        votabili.append(vot)
    # canali fissi (gia' noti anche dentro il buco grazie all'interpolazione dai bordi)
    feat.append(0.6 * norm(np.log(ampiezza_b["bc"])))
    feat.append(0.4 * norm(np.log(ampiezza_b["n"])))
    tY = 0.299 * tono_b["bc"][..., 0] + 0.587 * tono_b["bc"][..., 1] + 0.114 * tono_b["bc"][..., 2]
    feat.append(0.15 * norm(tY))
    F = np.stack(feat, -1).astype(np.float32)
    vot = [i for i, v in enumerate(votabili) if v]
    L, nnf = completa(F, buco, sorgente, vot, livelli=4)
    pmy, pmx = nnf
    np.savez_compressed(os.path.join(diag, "nnf_lod3.npz"), pmy=pmy, pmx=pmx, buco=buco, sorgente=sorgente)

    # ---- ricostruzione: tono interpolato + grana clonata e riscalata, poi raccordo ----
    anello = (cv2.dilate(buco.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
    yy, xx = np.nonzero(anello)
    ok = pmy[yy, xx] >= 0
    yy, xx = yy[ok], xx[ok]
    sy, sx = pmy[yy, xx], pmx[yy, xx]
    risultati = {}
    for k in ("bc", "n", "s"):
        orig = mappe[k].astype(np.float64)
        guida = orig.copy()
        rapporto = np.clip(ampiezza_b[k][yy, xx] / np.maximum(ampiezza[k][sy, sx], 1e-3), 0.5, 2.0)
        guida[yy, xx] = tono_b[k][yy, xx] + rapporto[:, None] * grana[k][sy, sx]
        risultati[k] = P.fondi(orig, guida)
    rep["LOD3_rapporto_intensita_mediano"] = float(np.median(
        np.clip(ampiezza_b["bc"][yy, xx] / np.maximum(ampiezza["bc"][sy, sx], 1e-3), 0.5, 2.0)))

    bc_n = bc.astype(np.float32).copy()
    bc_n[..., :3] = np.where(buco[..., None], risultati["bc"], bc_n[..., :3])
    nm_n = nm.astype(np.float32).copy()
    nm_n[..., :2] = np.where(buco[..., None], risultati["n"], nm_n[..., :2])
    nn = normalizza_normali(nm_n)
    nm_n[..., :3] = np.where(buco[..., None], nn, nm_n[..., :3])
    sr_n = sr.astype(np.float32).copy()
    sr_n[..., :2] = np.where(buco[..., None], risultati["s"], sr_n[..., :2])   # B (=0) e A (F) restano
    out = {"T_Head_LOD3_BC_VT": a8(bc_n), "T_Head_LOD3_N_VT": a8(nm_n), "T_Head_LOD3_SRMF_VT": a8(sr_n)}

    # ---- Scatter: uniforme attorno alle spalline -> membrana ----
    def scatter(arr, buco_ref):
        ns = arr.shape[0]
        b = cv2.resize(buco_ref.astype(np.float32), (ns, ns), interpolation=cv2.INTER_AREA) > 0
        b |= (arr[..., 0] < 60) & (np.arange(ns)[:, None] >= int(ns * 0.8))
        b = cv2.dilate(b.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        Ps = Poisson(b)
        r = arr.astype(np.float32).copy()
        r[..., :3] = Ps.armonica(r[..., :3])
        return a8(r), b

    out["T_Head_LOD3_Scatter_VT"], buco_s = scatter(sc, buco)

    # ---- LOD5to7: dal LOD3 ritoccato, rimpicciolito e raccordato ----
    bc5, _ = carica(src, "T_Head_LOD5to7_BC_VT")
    nm5, _ = carica(src, "T_Head_LOD5to7_N_VT")
    sr5, _ = carica(src, "T_Head_LOD5to7_SRMF")
    sc5, _ = carica(src, "T_Head_LOD5to7_Scatter_VT")
    n5 = bc5.shape[0]
    buco5 = maschera(bc5, sr5, DILATA_1024)
    buco5 |= cv2.resize(buco.astype(np.float32), (n5, n5), interpolation=cv2.INTER_AREA) > 0
    P5 = Poisson(buco5)
    for nome, orig, nuovo3, canali_ in (("T_Head_LOD5to7_BC_VT", bc5, bc_n, 3),
                                         ("T_Head_LOD5to7_N_VT", nm5, nm_n, 2),
                                         ("T_Head_LOD5to7_SRMF", sr5, sr_n, 2)):
        piccolo = ridimensiona(nuovo3, n5, n5)
        o = orig.astype(np.float32)
        fuso = P5.fondi(o[..., :canali_], piccolo[..., :canali_])
        r = o.copy()
        r[..., :canali_] = np.where(buco5[..., None], fuso, o[..., :canali_])
        if nome.endswith("_N_VT"):
            r[..., :3] = np.where(buco5[..., None], normalizza_normali(r), r[..., :3])
        out[nome] = a8(r)
    out["T_Head_LOD5to7_Scatter_VT"], buco_s5 = scatter(sc5, buco5)
    rep["LOD5to7_pixel_maschera"] = int(buco5.sum())

    # ---- salvataggio + controlli ----
    maschere = {"T_Head_LOD3_BC_VT": buco, "T_Head_LOD3_N_VT": buco, "T_Head_LOD3_SRMF_VT": buco,
                "T_Head_LOD3_Scatter_VT": buco_s, "T_Head_LOD5to7_BC_VT": buco5, "T_Head_LOD5to7_N_VT": buco5,
                "T_Head_LOD5to7_SRMF": buco5, "T_Head_LOD5to7_Scatter_VT": buco_s5}
    controlli = {}
    for nome, arr in out.items():
        orig, mode = carica(src, nome)
        assert arr.shape == orig.shape and arr.dtype == orig.dtype, nome
        m = maschere[nome]
        diff_fuori = int((arr[~m] != orig[~m]).any(-1).sum())
        salva(dst, nome, arr)
        rilett, _ = carica(dst, nome)
        controlli[nome] = dict(dimensione=list(orig.shape), modo=mode, pixel_cambiati_fuori_maschera=diff_fuori,
                               pixel_in_maschera=int(m.sum()), riletto_identico=bool((rilett == arr).all()))
        log(nome, controlli[nome])
    rep["controlli"] = controlli
    np.save(os.path.join(diag, "maschera_lod3.npy"), buco)
    np.save(os.path.join(diag, "maschera_lod5to7.npy"), buco5)
    with open(os.path.join(diag, "report_fase7b.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    log("FATTO")


if __name__ == "__main__":
    main()
