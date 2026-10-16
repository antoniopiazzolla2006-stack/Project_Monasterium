# =============================================================================
#  FASE 6 (parte Blender) - TEXTURE FINALI, CORPO NASCOSTO, EXPORT FBX PER UNREAL
#  Progetto: Abate francescano  (MetaHuman UE 5.8  ->  Blender 5.2  ->  UE 5.8)
#
#  COSA FA
#   1. "Body Hidden Face Map": un'immagine nelle UV del CORPO MetaHuman che dice
#      a Unreal quali facce del corpo sono sempre coperte dal saio (nere) e si
#      possono togliere: niente pelle che "buca" la stoffa, meno triangoli.
#      Si nasconde solo cio' che e' coperto in ogni posa: busto, attaccatura del
#      collo, meta' alta delle braccia, cosce e ginocchia (non avambracci,
#      polpacci, mani, piedi). Vale per tutti i MetaHuman (stesse UV del corpo).
#   2. Texture finali della lana (2048 px):
#      - T_Lana_BC   colore (sRGB): lana bruno-grigia non tinta con variazioni
#                    "a macchie" come la lana vera, risvolto piu' chiaro, bordi
#                    consumati e polvere verso l'orlo (dalle maschere della Fase 5);
#      - T_Lana_ORM  dati: R = ombre lato dritto, G = ruvidezza, B = ombre lato
#                    rovescio (la lana non e' metallo: il canale B e' libero).
#      Le variazioni nascono da un "rumore" calcolato nello SPAZIO 3D e poi cotto
#      nelle UV: cosi' non si vedono stacchi sulle cuciture tra i pezzi.
#   3. Export FBX (stesse impostazioni del test riuscito della Fase 1):
#      - Export/SM_SaioAbate_Render.fbx  saio + mantellina in UN pezzo, gia' in
#        triangoli (modificatore Triangola_per_UE), con tangenti, materiale M_Lana
#      - Export/SM_SaioAbate_Fisica.fbx  la mesh per la fisica (UV in cm): servira'
#        nella Fase 9, in Unreal la importi ma non la usi ancora
#      e li rilegge per controllo.
#   4. Anteprima del materiale in Blender, rapporto; salva Saio_Abate_v006.blend.
#
#  PRIMA DI LANCIARLO
#   - Apri Saio_Abate_v005.blend (Fase 5), con la cartella Texture della Fase 5.
#  COME SI LANCIA
#   - Workspace "Scripting" > Text > Open > questo file > Run Script (Alt+P).
#     Circa un minuto.
# =============================================================================

import bpy
import bmesh
import math
import os
import time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CM = 0.01

# ----------------------------- PARAMETRI -------------------------------------
P = dict(
    RISOLUZIONE=2048,        # texture della lana
    SOVRACAMPIONA=2,         # il rumore si cuoce a 4096 e si riduce
    RISOLUZIONE_CORPO=2048,  # mappa del corpo nascosto
    BRACCIO_FINO_A=0.5,      # quota della parte alta del braccio da nascondere (0 = spalla, 1 = gomito)
    POLPACCIO_FINO_A=0.12,   # sotto il ginocchio si nasconde solo questo tratto (0 = ginocchio, 1 = caviglia)
    RAGGIO_COPERTURA=1.0,    # m: una faccia del corpo e' "coperta" se lungo la sua normale c'e' la stoffa
    # colori lineari (come nel Color Picker di Blender, valori "Linear")
    LANA=(0.105, 0.078, 0.056),          # bruno-grigia non tinta
    LANA_FREDDA=(0.100, 0.083, 0.064),   # fili un po' piu' grigi (lana "screziata")
    RISVOLTO=(0.33, 0.27, 0.19),
    CONSUMATO=(0.17, 0.145, 0.12),       # lana sbiadita sui bordi
    POLVERE=(0.25, 0.225, 0.19),
    RUVIDEZZA=0.86,
)

NOMI = dict(saio="Saio_Gioco", mant="Mantellina_Gioco", saio_f="Saio_Fisica", mant_f="Mantellina_Fisica",
            corpo_orig="MHC_Abate_FullBody_LOD0")
NOME_FILE_V6 = "Saio_Abate_v006.blend"
FBX_RENDER = "SM_SaioAbate_Render"
FBX_FISICA = "SM_SaioAbate_Fisica"
UV = "UVMap"
report = []


def log(riga=""):
    print(riga, flush=True)
    report.append(riga)


# =============================================================================
#  UTILITA' (come nella Fase 5)
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


def coordinate(obj, mesh=None):
    me = mesh or obj.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(obj.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


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


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


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


def riempi(val, valido, passi=16):
    """Allarga i bordi dei pezzi nello spazio vuoto (come nella Fase 5)."""
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
    """PNG 8 bit RGB scritto con Blender. 'rgb' e' gia' nella codifica finale (0-1)."""
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


def leggi_png(percorso):
    """Pixel di un PNG come array (righe dal basso, come le UV)."""
    img = bpy.data.images.load(percorso, check_existing=False)
    img.colorspace_settings.name = 'Non-Color'
    w, h = img.size
    px = np.zeros(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def lineare_a_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def triangolata(o, nome, coll):
    """Copia con i modificatori applicati (Triangola_per_UE compreso)."""
    if len(o.modifiers):
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    else:
        me = o.data.copy()
    ob = bpy.data.objects.new(nome, me)
    coll.objects.link(ob)
    ob.matrix_world = o.matrix_world.copy()
    return ob


def rasterizza_maschera(tri, res, maschera):
    """Accende nella maschera i pixel il cui centro cade nei triangoli (coordinate 0-1)."""
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
        dentro = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
        maschera[y0:y1 + 1, x0:x1 + 1] |= dentro


# =============================================================================
#  1. CORPO NASCOSTO (Body Hidden Face Map)
# =============================================================================
REGIONI = {"pelvis": "busto", "spine_01": "busto", "spine_02": "busto", "spine_03": "busto",
           "spine_04": "busto", "spine_05": "busto", "clavicle_l": "busto", "clavicle_r": "busto",
           "neck_01": "collo", "neck_02": "collo", "head": "testa",
           "upperarm_l": "braccio_l", "upperarm_r": "braccio_r", "lowerarm_l": "avambraccio",
           "lowerarm_r": "avambraccio", "hand_l": "mano", "hand_r": "mano",
           "thigh_l": "coscia", "thigh_r": "coscia", "calf_l": "polpaccio_l", "calf_r": "polpaccio_r",
           "foot_l": "piede", "foot_r": "piede", "ball_l": "piede", "ball_r": "piede"}


def regione_di_ogni_osso(arm):
    out = {}
    for b in arm.data.bones:
        x = b
        while x is not None and x.name not in REGIONI:
            x = x.parent
        out[b.name] = REGIONI[x.name] if x is not None else "testa"
    return out


def facce_del_corpo_coperte(corpo, arm):
    """Per ogni faccia del corpo (riquadro UV 1-2): da nascondere o no."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = corpo.evaluated_get(dg)
    me = ev.to_mesh()                              # posa di riferimento (A-pose)
    co = coordinate(corpo, me)
    uv = np.zeros(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.zeros(len(me.polygons), int)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.zeros(len(me.polygons), int)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.zeros(len(me.loops), int)
    me.loops.foreach_get("vertex_index", lv)
    nor = np.zeros(len(me.polygons) * 3)
    me.polygons.foreach_get("normal", nor)
    nor = nor.reshape(-1, 3)
    cen = np.zeros(len(me.polygons) * 3)
    me.polygons.foreach_get("center", cen)
    M = np.array(corpo.matrix_world)
    cen = cen.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    nor = nor @ np.linalg.inv(M[:3, :3])                       # normali in spazio mondo
    nor /= np.maximum(np.linalg.norm(nor, axis=1), 1e-12)[:, None]
    fl = np.repeat(np.arange(len(me.polygons)), lt)
    umin = np.full(len(me.polygons), np.inf)
    np.minimum.at(umin, fl, uv[:, 0])
    corpo_f = np.where(umin >= 1.0)[0]                          # il corpo sta nel riquadro UV 1-2
    # regione di ogni vertice: l'osso che pesa di piu' (risalendo agli ossi principali)
    reg_osso = regione_di_ogni_osso(arm)
    nome_gruppo = {g.index: g.name for g in corpo.vertex_groups}
    reg_v = np.empty(len(corpo.data.vertices), object)
    for v in corpo.data.vertices:
        somma = {}
        for g in v.groups:
            r = reg_osso.get(nome_gruppo.get(g.group, ""), None)
            if r is not None:
                somma[r] = somma.get(r, 0.0) + g.weight
        reg_v[v.index] = max(somma, key=somma.get) if somma else "testa"
    # posizione lungo braccio e polpaccio
    def segmento(a, b):
        A = np.array(arm.matrix_world @ arm.data.bones[a].head_local)
        B = np.array(arm.matrix_world @ arm.data.bones[b].head_local)
        return A, B
    segmenti = {"braccio_l": segmento("upperarm_l", "lowerarm_l"), "braccio_r": segmento("upperarm_r", "lowerarm_r"),
                "polpaccio_l": segmento("calf_l", "foot_l"), "polpaccio_r": segmento("calf_r", "foot_r")}
    # stoffa (mesh di gioco) per il controllo di copertura
    stoffa_v, stoffa_f = [], []
    for nome in (NOMI["saio"], NOMI["mant"]):
        o = bpy.data.objects[nome]
        base = len(stoffa_v)
        stoffa_v += [Vector(c) for c in coordinate(o)]
        stoffa_f += [[base + i for i in p.vertices] for p in o.data.polygons]
    bvh = BVHTree.FromPolygons(stoffa_v, stoffa_f)
    candidata = np.zeros(len(me.polygons), bool)
    coperta = np.zeros(len(me.polygons), bool)
    regione_f = np.empty(len(me.polygons), object)
    for f in corpo_f:
        vs = lv[ls[f]:ls[f] + lt[f]]
        regs = [reg_v[i] for i in vs]
        r = max(set(regs), key=regs.count)
        regione_f[f] = r
        if r in ("busto", "collo", "coscia"):
            candidata[f] = True
        elif r in segmenti:
            A, B = segmenti[r]
            t = float(np.dot(cen[f] - A, B - A) / np.dot(B - A, B - A))
            limite = P["BRACCIO_FINO_A"] if r.startswith("braccio") else P["POLPACCIO_FINO_A"]
            candidata[f] = t < limite
        if candidata[f]:
            hit = bvh.ray_cast(Vector(cen[f] + nor[f] * 0.001), Vector(nor[f]), P["RAGGIO_COPERTURA"])
            coperta[f] = hit[0] is not None
    nascosta = candidata & coperta
    # pulizia: niente puntini isolati (filtro "a maggioranza" sulle facce vicine)
    vf = {}
    for f in corpo_f:
        for i in lv[ls[f]:ls[f] + lt[f]]:
            vf.setdefault(i, []).append(f)
    vicine = {f: list({g for i in lv[ls[f]:ls[f] + lt[f]] for g in vf[i] if g != f}) for f in corpo_f}
    for _ in range(2):
        nuova = nascosta.copy()
        for f in corpo_f:
            if not vicine[f]:
                continue
            q = nascosta[vicine[f]].mean()
            if nascosta[f] and q < 0.25:
                nuova[f] = False
            elif not nascosta[f] and candidata[f] and q > 0.75:
                nuova[f] = True
        nascosta = nuova
    tri = []
    for f in np.where(nascosta)[0]:
        L = list(range(ls[f], ls[f] + lt[f]))
        for k in range(1, len(L) - 1):
            tri.append(uv[[L[0], L[k], L[k + 1]]] - np.array([1.0, 0.0]))
    stat = dict(corpo=len(corpo_f), candidate=int(candidata.sum()), scoperte=int((candidata & ~coperta).sum()),
                nascoste=int(nascosta.sum()), regioni={r: int(((regione_f == r) & nascosta).sum())
                                                     for r in set(regione_f[corpo_f])})
    ev.to_mesh_clear()
    return np.array(tri), nascosta, corpo_f, stat


def corpo_nascosto(cartella):
    corpo = bpy.data.objects[NOMI["corpo_orig"]]
    arm = corpo.find_armature() or corpo.parent
    tri, nascosta, corpo_f, st = facce_del_corpo_coperte(corpo, arm)
    R = P["RISOLUZIONE_CORPO"]
    m = np.zeros((R, R), bool)
    rasterizza_maschera(tri, R, m)
    # 1 pixel in piu' attorno al nero: i vertici sul confine risultano neri anche loro
    m = m | sposta(m, 1, 0) | sposta(m, -1, 0) | sposta(m, 0, 1) | sposta(m, 0, -1)
    img = np.where(m, 0.0, 1.0).astype(np.float32)
    salva_png("T_Corpo_Nascosto", np.dstack([img, img, img]), cartella)
    log(f"[1] Corpo nascosto: {st['nascoste']} facce del corpo su {st['corpo']} "
        f"({st['nascoste'] / st['corpo'] * 100:.0f}%) sono sempre sotto il saio e si possono togliere")
    nomi_it = {"busto": "busto", "collo": "attaccatura del collo", "braccio_l": "braccio sinistro (meta' alta)",
               "braccio_r": "braccio destro (meta' alta)", "coscia": "cosce", "polpaccio_l": "ginocchio sinistro",
               "polpaccio_r": "ginocchio destro"}
    log("    " + ", ".join(f"{nomi_it.get(r, r)} {n}" for r, n in sorted(st["regioni"].items()) if n))
    log(f"    candidate ma lasciate visibili perche' la stoffa non le copre lungo la normale: {st['scoperte']}")
    log(f"    nera il {m.mean() * 100:.1f}% dell'immagine T_Corpo_Nascosto.png ({R} px, nero = nascosto)")
    return nascosta, corpo_f, st


# =============================================================================
#  2. TEXTURE DELLA LANA
# =============================================================================
def cuoci_rumore():
    """Tre rumori nello spazio 3D (macchie larghe, medie, fini) cotti nelle UV."""
    sc = bpy.context.scene
    R4 = P["RISOLUZIONE"] * P["SOVRACAMPIONA"]
    coll = bpy.data.collections.new("TEMP_FASE6")
    sc.collection.children.link(coll)
    stato = dict(engine=sc.render.engine, nascosti={o.name: o.hide_render for o in sc.objects},
                 samples=sc.cycles.samples, device=sc.cycles.device)
    img = bpy.data.images.new("TEMP_Rumore", R4, R4, alpha=True, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    mat = bpy.data.materials.new("TEMP_Rumore")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    comb = nt.nodes.new("ShaderNodeCombineColor")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    for k, (scala, dettaglio) in enumerate(((1.8, 3.0), (22.0, 3.0), (180.0, 2.0))):
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.noise_dimensions = '3D'
        nz.inputs["Scale"].default_value = scala
        nz.inputs["Detail"].default_value = dettaglio
        nz.inputs["Roughness"].default_value = 0.55
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        nt.links.new(nz.outputs["Fac"], comb.inputs[k])
    nt.links.new(comb.outputs[0], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    copie = []
    try:
        for o in sc.objects:
            o.hide_render = True
        for nome in (NOMI["saio"], NOMI["mant"]):
            c = triangolata(bpy.data.objects[nome], "TEMP_" + nome, coll)
            c.data.materials.clear()
            c.data.materials.append(mat)
            c.hide_render = False
            copie.append(c)
        sc.render.engine = 'CYCLES'
        sc.cycles.device = 'CPU'
        sc.cycles.samples = 1
        img.pixels.foreach_set(np.zeros(R4 * R4 * 4, np.float32))
        acc = np.zeros(R4 * R4 * 4, np.float32)
        for c in copie:                      # una cottura per pezzo, nello stesso quadro
            seleziona(c)
            bpy.ops.object.bake(type='EMIT', margin=0, margin_type='EXTEND', use_clear=False, use_cage=False,
                                uv_layer=UV, target='IMAGE_TEXTURES', save_mode='INTERNAL',
                                use_selected_to_active=False)
        img.pixels.foreach_get(acc)
        x = acc.reshape(R4, R4, 4)
        f = P["SOVRACAMPIONA"]
        ok = x[..., 3] > 0.5
        cnt = riduci(ok.astype(np.float32), f)
        rum = riduci(x[..., :3] * ok[..., None], f) / np.maximum(cnt, 1e-9)[..., None]
        valido = cnt > 0
    finally:
        for c in copie:
            me = c.data
            bpy.data.objects.remove(c, do_unlink=True)
            bpy.data.meshes.remove(me)
        bpy.data.collections.remove(coll)
        bpy.data.materials.remove(mat)
        bpy.data.images.remove(img)
        sc.render.engine = stato["engine"]
        sc.cycles.samples = stato["samples"]
        sc.cycles.device = stato["device"]
        for o in sc.objects:
            if o.name in stato["nascosti"]:
                o.hide_render = stato["nascosti"][o.name]
    return rum, valido


def texture_lana(cartella):
    R2 = P["RISOLUZIONE"]
    rum, valido = cuoci_rumore()
    z = np.zeros_like(rum)
    for k in range(3):                       # rumore "standardizzato": media 0, deviazione 1
        v = rum[..., k][valido]
        z[..., k] = np.clip((rum[..., k] - v.mean()) / max(v.std(), 1e-6), -2.5, 2.5)
    z1, z2, z3 = z[..., 0][..., None], z[..., 1][..., None], z[..., 2][..., None]
    M = leggi_png(os.path.join(cartella, "T_Lana_Maschere.png"))
    A = leggi_png(os.path.join(cartella, "T_Lana_AO.png"))
    if M.shape[0] != R2 or A.shape[0] != R2:
        raise RuntimeError("Le texture della Fase 5 non sono a 2048 px")
    mR, mG, mB = M[..., 0:1], M[..., 1:2], M[..., 2:3]
    c = lambda k: np.array(P[k], np.float32)
    # lana screziata
    lana = c("LANA") * (1 + 0.10 * z1 + 0.06 * z2 + 0.05 * z3)
    lana = lana + (c("LANA_FREDDA") - c("LANA")) * np.clip(0.5 + 0.25 * z2, 0, 1)
    risvolto = c("RISVOLTO") * (1 + 0.06 * z2 + 0.05 * z3)
    col = lana + (risvolto - lana) * mR
    usura = mG * 0.45 * np.clip(0.6 + 0.25 * z2, 0, 1)
    col = col + (c("CONSUMATO") * (1 + 0.05 * z3) - col) * usura
    polvere = np.power(mB, 1.3) * 0.55 * np.clip(0.7 + 0.2 * z1, 0, 1)
    col = col + (c("POLVERE") * (1 + 0.04 * z3) - col) * polvere
    rug = P["RUVIDEZZA"] + 0.025 * z2 + 0.02 * z3 - 0.12 * mG * np.clip(0.6 + 0.25 * z2, 0, 1) + 0.07 * mB
    rug = np.clip(rug, 0.55, 0.98)
    col = riempi(col.astype(np.float32), valido)
    orm = np.dstack([A[..., 0], rug[..., 0], A[..., 1]]).astype(np.float32)
    orm = riempi(orm, valido)
    salva_png("T_Lana_BC", lineare_a_srgb(col), cartella)
    salva_png("T_Lana_ORM", orm, cartella)
    st = dict(col=col[valido].mean(0), rug=(rug[..., 0][valido].min(), rug[..., 0][valido].mean(), rug[..., 0][valido].max()))
    log(f"[2] T_Lana_BC: colore medio (lineare) {st['col'][0]:.3f} {st['col'][1]:.3f} {st['col'][2]:.3f}; "
        f"T_Lana_ORM: ruvidezza {st['rug'][0]:.2f}-{st['rug'][2]:.2f} (media {st['rug'][1]:.2f})")
    return st


# =============================================================================
#  3. MATERIALE DI ANTEPRIMA (come sara' in Unreal)
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


def materiale_lana(cartella):
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
    tb, tn, to = N("ShaderNodeTexImage"), N("ShaderNodeTexImage"), N("ShaderNodeTexImage")
    for t, nome, colore in ((tb, "T_Lana_BC", 'sRGB'), (tn, "T_Lana_N", 'Non-Color'), (to, "T_Lana_ORM", 'Non-Color')):
        t.image = immagine(cartella, nome, colore)
        t.label = nome
        nt.links.new(uvn.outputs["UV"], t.inputs["Vector"])
    # normal map DirectX -> verde rovesciato per Blender
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
    # ORM: ruvidezza (G); ombre R davanti / B dietro (in Blender si moltiplicano sul colore, solo anteprima)
    so = N("ShaderNodeSeparateColor")
    nt.links.new(to.outputs["Color"], so.inputs["Color"])
    nt.links.new(so.outputs[1], bsdf.inputs["Roughness"])
    geo = N("ShaderNodeNewGeometry")
    mix_ao = N("ShaderNodeMix")
    mix_ao.data_type = 'FLOAT'
    nt.links.new(geo.outputs["Backfacing"], mix_ao.inputs["Factor"])
    nt.links.new(so.outputs[0], mix_ao.inputs["A"])
    nt.links.new(so.outputs[2], mix_ao.inputs["B"])
    tinta = N("ShaderNodeRGB")
    tinta.label = "Tinta_Lana"
    tinta.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    m1 = N("ShaderNodeMix")
    m1.data_type = 'RGBA'
    m1.blend_type = 'MULTIPLY'
    m1.inputs["Factor"].default_value = 1.0
    nt.links.new(tb.outputs["Color"], m1.inputs[6])
    nt.links.new(tinta.outputs[0], m1.inputs[7])
    m2 = N("ShaderNodeMix")
    m2.data_type = 'RGBA'
    m2.blend_type = 'MULTIPLY'
    m2.inputs["Factor"].default_value = 1.0
    nt.links.new(m1.outputs[2], m2.inputs[6])
    nt.links.new(mix_ao.outputs[0], m2.inputs[7])
    nt.links.new(m2.outputs[2], bsdf.inputs["Base Color"])
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.3
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    pos = {out: (950, 0), bsdf: (600, 0), uvn: (-1150, 0), tb: (-850, 350), tn: (-850, -350), to: (-850, 0),
           sep: (-500, -350), inv: (-300, -420), comb: (-100, -350), nmap: (150, -350), so: (-500, 0),
           geo: (-500, -150), mix_ao: (-250, 0), tinta: (-500, 550), m1: (-100, 400), m2: (250, 250)}
    for nodo, xy in pos.items():
        nodo.location = xy
    return mat


# =============================================================================
#  4. EXPORT FBX
# =============================================================================
def esporta(oggetti, nome, cartella):
    """Unisce le copie (modificatori applicati) in UN oggetto e lo esporta in FBX
    con le impostazioni della Fase 1 (+ tangenti)."""
    modo_oggetto()
    coll = bpy.data.collections.new("TEMP_EXPORT")
    bpy.context.scene.collection.children.link(coll)
    copie = [triangolata(o, f"TEMP_{o.name}", coll) for o in oggetti]
    try:
        seleziona(copie[0], copie[1:])
        if len(copie) > 1:
            bpy.ops.object.join()
        unito = bpy.context.view_layer.objects.active
        unito.name = nome
        unito.data.name = nome
        for m in list(unito.modifiers):
            unito.modifiers.remove(m)
        seleziona(unito)
        percorso = os.path.join(cartella, nome + ".fbx")
        bpy.ops.export_scene.fbx(
            filepath=percorso,
            use_selection=True, use_visible=False, use_active_collection=False,
            object_types={'MESH'}, use_custom_props=False,
            global_scale=1.0, apply_scale_options='FBX_SCALE_UNITS',
            axis_forward='-Z', axis_up='Y',
            apply_unit_scale=True, use_space_transform=True, bake_space_transform=False,
            mesh_smooth_type='FACE', use_subsurf=False, use_mesh_modifiers=True,
            use_mesh_edges=False, use_triangles=False, use_tspace=True,
            colors_type='NONE',
            add_leaf_bones=False, bake_anim=False,
            path_mode='AUTO', embed_textures=False, batch_mode='OFF')
        me = unito.data
        dati = dict(vert=len(me.vertices), tri=sum(len(p.vertices) - 2 for p in me.polygons), co=coordinate(unito),
                    materiali=[m.name for m in me.materials if m], uv=[u.name for u in me.uv_layers])
        uvv = np.zeros(len(me.loops) * 2)
        me.uv_layers[UV].data.foreach_get("uv", uvv)
        dati["uv_range"] = (uvv.reshape(-1, 2).min(0), uvv.reshape(-1, 2).max(0))
    finally:
        for o in list(coll.objects):
            m = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if m.users == 0:
                bpy.data.meshes.remove(m)
        bpy.data.collections.remove(coll)
    return percorso, dati


def verifica_fbx(percorso, dati):
    """Rilegge l'FBX in una scena vuota e confronta con quello che e' stato esportato."""
    prima = set(bpy.data.objects)
    prime_mesh = set(bpy.data.meshes)
    coll = bpy.data.collections.new("TEMP_VERIFICA")
    bpy.context.scene.collection.children.link(coll)
    lc = layer_collection("TEMP_VERIFICA")
    bpy.context.view_layer.active_layer_collection = lc
    try:
        bpy.ops.import_scene.fbx(filepath=percorso)
        nuovi = [o for o in bpy.data.objects if o not in prima and o.type == 'MESH']
        if len(nuovi) != 1:
            raise RuntimeError(f"FBX {os.path.basename(percorso)}: attesi 1 oggetto, letti {len(nuovi)}")
        o = nuovi[0]
        me = o.data
        co = coordinate(o)
        a, b = dati["co"], co
        scarto_bbox = max(np.abs(a.min(0) - b.min(0)).max(), np.abs(a.max(0) - b.max(0)).max())
        tri = sum(len(p.vertices) - 2 for p in me.polygons)
        esito = dict(nome=o.name, vert=len(me.vertices), tri=tri, scarto_cm=scarto_bbox / CM,
                     uv=[u.name for u in me.uv_layers], materiali=[m.name for m in me.materials if m],
                     bbox=(b.min(0) / CM, b.max(0) / CM))
    finally:
        for o in [o for o in bpy.data.objects if o not in prima]:
            bpy.data.objects.remove(o, do_unlink=True)
        for m in [m for m in bpy.data.meshes if m not in prime_mesh and m.users == 0]:
            bpy.data.meshes.remove(m)
        for m in [m for m in bpy.data.materials if m.users == 0 and m.name.startswith(("M_Lana.", "M_Fisica."))]:
            bpy.data.materials.remove(m)
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection
        bpy.data.collections.remove(coll)
    return esito


# =============================================================================
#  MAIN
# =============================================================================
def main(salva=True):
    t0 = time.time()
    log("=== REPORT FASE 6 (Blender) - TEXTURE FINALI, CORPO NASCOSTO, EXPORT PER UNREAL ===")
    for nome in list(NOMI.values()) + ["REF_Corpo"]:
        if bpy.data.objects.get(nome) is None:
            raise RuntimeError(f"Manca {nome}: apri Saio_Abate_v005.blend (Fase 5).")
    if not bpy.data.filepath:
        raise RuntimeError("Salva prima il file .blend: texture ed export vanno nelle cartelle accanto.")
    modo_oggetto()
    base = os.path.dirname(bpy.data.filepath)
    tex = os.path.join(base, "Texture")
    exp = os.path.join(base, "Export")
    os.makedirs(exp, exist_ok=True)
    for f in ("T_Lana_N.png", "T_Lana_AO.png", "T_Lana_Maschere.png"):
        if not os.path.isfile(os.path.join(tex, f)):
            raise RuntimeError(f"Manca Texture/{f} (Fase 5)")
    for o in (bpy.data.objects[NOMI["saio"]], bpy.data.objects[NOMI["mant"]]):
        if o.modifiers.get("Triangola_per_UE") is None:
            raise RuntimeError(f"{o.name}: manca il modificatore Triangola_per_UE (Fase 5)")
    ok = True

    # 1) corpo nascosto
    nascosta, corpo_f, st_c = corpo_nascosto(tex)
    ok &= 0.2 < st_c["nascoste"] / st_c["corpo"] < 0.8

    # 2) texture della lana
    texture_lana(tex)

    # 3) materiale di anteprima
    materiale_lana(tex)
    log("[3] M_Lana (anteprima in Blender) ora usa T_Lana_BC, T_Lana_ORM e T_Lana_N come fara' Unreal")

    # 4) export
    gioco = [bpy.data.objects[NOMI["saio"]], bpy.data.objects[NOMI["mant"]]]
    fisica = [bpy.data.objects[NOMI["saio_f"]], bpy.data.objects[NOMI["mant_f"]]]
    for oggetti, nome, attesi_tri in ((gioco, FBX_RENDER, 7868), (fisica, FBX_FISICA, 7040)):
        percorso, dati = esporta(oggetti, nome, exp)
        v = verifica_fbx(percorso, dati)
        buono = (v["tri"] == dati["tri"] == attesi_tri and v["vert"] == dati["vert"] and v["scarto_cm"] < 0.01
                 and v["uv"] == [UV] and len(v["materiali"]) == 1)
        ok &= buono
        log(f"[4] Export/{nome}.fbx: {dati['tri']} triangoli, {dati['vert']} vertici, UV {dati['uv']}, "
            f"materiale {dati['materiali']}, UV da {dati['uv_range'][0].round(2)} a {dati['uv_range'][1].round(2)}")
        log(f"    riletto: {v['tri']} triangoli, {v['vert']} vertici, scarto dell'ingombro {v['scarto_cm']:.3f} cm, "
            f"ingombro {v['bbox'][0].round(1)} - {v['bbox'][1].round(1)} cm -> {'OK' if buono else 'DIVERSO'}")

    nuovo = os.path.join(base, NOME_FILE_V6)
    if salva:
        log(f"[5] Salvo come {nuovo} (il file v005 resta intatto); {time.time() - t0:.0f} s")
    log("ESITO: " + ("tutti i controlli superati" if ok else "ATTENZIONE: qualche controllo non e' passato"))
    testo = bpy.data.texts.get("REPORT_Fase6") or bpy.data.texts.new("REPORT_Fase6")
    testo.clear()
    testo.write("\n".join(report) + "\n")
    if salva:
        bpy.ops.wm.save_as_mainfile(filepath=nuovo)
    return ok, testo, st_c


if __name__ == "__main__":
    ok, testo, _ = main()
    spazio = getattr(bpy.context, "space_data", None)
    if spazio is not None and spazio.type == 'TEXT_EDITOR':
        spazio.text = testo
    wm = bpy.context.window_manager
    if wm.windows and not bpy.app.background:
        def disegna(self, context):
            for riga in report[:20]:
                self.layout.label(text=riga)
        wm.popup_menu(disegna, title="Fase 6: fatto" if ok else "Fase 6: controlla il report",
                      icon='INFO' if ok else 'ERROR')
