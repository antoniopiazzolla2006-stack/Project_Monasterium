# =============================================================================
#  FASE 7 - PROVA DELLE QUATTRO POSE (anteprima in Blender di quello che fara' Unreal)
#  Uso:  blender -b Saio_Abate_v007.blend --python prova_pose_fase7.py -- <cartella_output> [campioni]
#  Lavora sul file aperto in memoria e NON lo salva.
#
#  COSA FA
#   1. Copia saio, mantellina e accessori e da' a ogni vertice i pesi del punto piu'
#      vicino della pelle (interpolati sul triangolo): e' la regola "Closest Point on
#      Surface" del nodo TransferSkinWeights di Unreal. L'anello segue gia' ring_01_r.
#   2. Mette lo scheletro del MetaHuman in quattro pose semplici: camminata (passo),
#      in ginocchio, braccia alzate, seduto. Niente fisica: la stoffa segue le ossa
#      come fara' l'Outfit del MetaHuman Creator.
#   3. Conta i triangoli che si attraversano: accessori/corpo, accessori/stoffa (in
#      piu' rispetto alla posa di riferimento) e, per informazione, stoffa/corpo solo
#      sulla pelle che resta visibile (la Body Hidden Face Map toglie il resto).
#   4. Due render per posa.
#  LIMITI (onesti): in Unreal il corpo ha anche le ossa "correttive" guidate dal
#  MetaHuman (spalle, gomiti, ginocchia): qui seguono il loro osso padre e basta, quindi
#  le pieghe della pelle sono un po' diverse. Le pose sono statiche e semplificate.
# =============================================================================
import bpy
import bmesh
import math
import os
import sys
import time
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = bpy.path.abspath(argv[0] if argv else "//Render/Pose")
CAMPIONI = int(argv[1]) if len(argv) > 1 else 24
os.makedirs(OUT, exist_ok=True)
CM = 0.01
PARTI = dict(cordone=10, filo=11, cordino=12, tau=20, grani=21, crocetta=22,
             suola_bordo=30, suola_sopra=31, suola_sotto=32, cinghie=33, anello=40)
NOMI_PARTI = {v: k for k, v in PARTI.items()}
GRUPPO = {10: "cordone", 11: "corona", 12: "Tau", 20: "Tau", 21: "corona", 22: "corona",
          30: "sandali", 31: "sandali", 32: "sandali", 33: "sandali", 40: "anello"}
sc = bpy.context.scene
arm = bpy.data.objects["root"]
ref = bpy.data.objects["REF_Corpo"]
righe = []


def log(r=""):
    print(r, flush=True)
    righe.append(r)


for lc in bpy.context.view_layer.layer_collection.children:
    lc.exclude = lc.name in ("TEST", "FASE3_SIMULAZIONE", "BLOCKOUT", "FISICA", "DRAPPEGGIO", "ACCESSORI_ALTA")
    lc.hide_viewport = False
coll = bpy.data.collections.new("PROVA_POSE")
sc.collection.children.link(coll)


# -----------------------------------------------------------------------------
# 1. pesi dal corpo (punto piu' vicino della superficie)
# -----------------------------------------------------------------------------
me_c = ref.data
me_c.calc_loop_triangles()
co_c = np.array([v.co for v in me_c.vertices])
tri_c = np.array([t.vertices[:] for t in me_c.loop_triangles])
bvh_c = BVHTree.FromPolygons([Vector(c) for c in co_c], tri_c.tolist())
nomi_g = {g.index: g.name for g in ref.vertex_groups}
pesi_v = [{nomi_g[g.group]: g.weight for g in v.groups} for v in me_c.vertices]


def pesi_trasferiti(p):
    q, n, f, d = bvh_c.find_nearest(Vector(p))
    a, b, c = (co_c[i] for i in tri_c[f])
    v0, v1, v2 = b - a, c - a, np.array(q) - a
    d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
    d20, d21 = v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    w1 = (d11 * d20 - d01 * d21) / den if den else 0.0
    w2 = (d00 * d21 - d01 * d20) / den if den else 0.0
    bary = (max(1 - w1 - w2, 0), max(w1, 0), max(w2, 0))
    acc = {}
    for i, w in zip(tri_c[f], bary):
        for g, x in pesi_v[i].items():
            acc[g] = acc.get(g, 0.0) + w * x
    top = sorted(acc.items(), key=lambda kv: -kv[1])[:8]
    s = sum(x for _, x in top) or 1.0
    return [(g, x / s) for g, x in top]


def copia_pesata(o, nome):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(o.matrix_world)
    ob = bpy.data.objects.new(nome, me)
    coll.objects.link(ob)
    gruppi = {}
    for v in me.vertices:
        for g, w in pesi_trasferiti(v.co):
            if g not in gruppi:
                gruppi[g] = ob.vertex_groups.new(name=g)
            gruppi[g].add([v.index], w, 'REPLACE')
    m = ob.modifiers.new("Armatura", 'ARMATURE')
    m.object = arm
    for mt in o.data.materials:
        pass
    return ob


t0 = time.time()
saio = copia_pesata(bpy.data.objects["Saio_Gioco"], "P_Saio")
mant = copia_pesata(bpy.data.objects["Mantellina_Gioco"], "P_Mantellina")
acc = copia_pesata(bpy.data.objects["Accessori_Gioco"], "P_Accessori")
ann = bpy.data.objects["Anello_Gioco"]
corpo = bpy.data.objects.new("P_Corpo", ref.data.copy())
coll.objects.link(corpo)
for g in ref.vertex_groups:
    corpo.vertex_groups.new(name=g.name)
for v in ref.data.vertices:
    for g in v.groups:
        corpo.vertex_groups[nomi_g[g.group]].add([v.index], g.weight, 'REPLACE')
mc = corpo.modifiers.new("Armatura", 'ARMATURE')
mc.object = arm
log(f"[1] pesi trasferiti (punto piu' vicino della pelle, max 8 ossa per vertice) in {time.time() - t0:.0f} s")

# parte di ogni triangolo degli accessori (dopo la valutazione l'ordine dei triangoli non cambia)
acc.data.calc_loop_triangles()
pf = np.array([t.polygon_index for t in acc.data.loop_triangles])
par = np.zeros(len(acc.data.polygons), int)
acc.data.attributes["parte"].data.foreach_get("value", par)
parte_tri = par[pf]

# pelle visibile in Unreal: T_Corpo_Nascosto (UV del corpo spostate di -1 in U)
visibile_tri = np.ones(len(tri_c), bool)
percorso_mappa = bpy.path.abspath("//Texture/T_Corpo_Nascosto.png")
if os.path.isfile(percorso_mappa):
    img = bpy.data.images.load(percorso_mappa)
    w_, h_ = img.size
    px = np.zeros(w_ * h_ * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h_, w_, 4)[..., 0]
    uvl = me_c.uv_layers.active.data
    for k, t in enumerate(me_c.loop_triangles):
        uv = np.mean([uvl[l].uv for l in t.loops], axis=0)
        if uv[0] >= 1.0:
            x = int(np.clip((uv[0] - 1.0) * w_, 0, w_ - 1))
            y = int(np.clip(uv[1] * h_, 0, h_ - 1))
            visibile_tri[k] = px[y, x] > 0.5
    bpy.data.images.remove(img)


# -----------------------------------------------------------------------------
# 2. pose
# -----------------------------------------------------------------------------
def testa(nome):
    return Vector(arm.pose.bones[nome].head)          # spazio dell'armatura (cm)


def ruota(nome, asse, gradi, centro=None):
    """Ruota l'osso (e i figli) attorno a un asse del mondo passante per la sua testa."""
    pb = arm.pose.bones[nome]
    M = pb.matrix.copy()
    h = Vector(M.translation) if centro is None else centro
    R = Quaternion(Vector(asse).normalized(), math.radians(gradi)).to_matrix().to_4x4()
    pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ M
    bpy.context.view_layer.update()


def punta_verso(nome, figlio, direzione, frazione=1.0):
    """Ruota l'osso perche' il segmento testa->testa del figlio guardi verso 'direzione'."""
    a, b = testa(nome), testa(figlio)
    v = (b - a).normalized()
    d = Vector(direzione).normalized()
    ang = v.angle(d)
    if ang < 1e-4:
        return
    ruota(nome, v.cross(d), math.degrees(ang) * frazione)


def sposta(nome, delta_cm):
    pb = arm.pose.bones[nome]
    M = pb.matrix.copy()
    pb.matrix = Matrix.Translation(Vector(delta_cm)) @ M
    bpy.context.view_layer.update()


def riposo():
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def braccia_giu():
    for s in ("l", "r"):
        x = 1 if s == "l" else -1
        punta_verso("upperarm_" + s, "lowerarm_" + s, (0.22 * x, 0.05, -1.0))
        punta_verso("lowerarm_" + s, "hand_" + s, (0.12 * x, -0.25, -1.0))


def posa(nome):
    riposo()
    if nome == "camminata":
        braccia_giu()
        punta_verso("thigh_r", "calf_r", (0, -0.45, -1.0))          # gamba destra avanti
        punta_verso("calf_r", "foot_r", (0, -0.10, -1.0))
        punta_verso("thigh_l", "calf_l", (0, 0.32, -1.0))           # sinistra indietro
        punta_verso("calf_l", "foot_l", (0, 0.62, -1.0))
        ruota("foot_l", (1, 0, 0), -20)
        punta_verso("upperarm_l", "lowerarm_l", (0.2, -0.35, -1.0))  # braccia che oscillano
        punta_verso("upperarm_r", "lowerarm_r", (-0.2, 0.30, -1.0))
    elif nome == "in_ginocchio":
        braccia_giu()
        punta_verso("upperarm_l", "lowerarm_l", (0.15, -0.35, -1.0))
        punta_verso("upperarm_r", "lowerarm_r", (-0.15, -0.35, -1.0))
        punta_verso("lowerarm_l", "hand_l", (-0.35, -1.0, 0.25))     # mani giunte davanti
        punta_verso("lowerarm_r", "hand_r", (0.35, -1.0, 0.25))
        punta_verso("thigh_l", "calf_l", (0, -0.12, -1.0))
        punta_verso("thigh_r", "calf_r", (0, -0.12, -1.0))
        punta_verso("calf_l", "foot_l", (0, 1.0, -0.08))           # stinchi a terra, indietro
        punta_verso("calf_r", "foot_r", (0, 1.0, -0.08))
        ruota("foot_l", (1, 0, 0), 60)
        ruota("foot_r", (1, 0, 0), 60)
        ginocchio = (testa("calf_l").z + testa("calf_r").z) / 2
        sposta("pelvis", (0, 0, -(ginocchio - 6.5)))
    elif nome == "braccia_alzate":
        punta_verso("clavicle_l", "upperarm_l", (1.0, 0.0, 0.35))
        punta_verso("clavicle_r", "upperarm_r", (-1.0, 0.0, 0.35))
        punta_verso("upperarm_l", "lowerarm_l", (0.35, -0.10, 1.0))
        punta_verso("upperarm_r", "lowerarm_r", (-0.35, -0.10, 1.0))
        punta_verso("lowerarm_l", "hand_l", (0.25, -0.10, 1.0))
        punta_verso("lowerarm_r", "hand_r", (-0.25, -0.10, 1.0))
    elif nome == "seduto":
        braccia_giu()
        punta_verso("lowerarm_l", "hand_l", (0.05, -1.0, -0.35))     # mani sulle ginocchia
        punta_verso("lowerarm_r", "hand_r", (-0.05, -1.0, -0.35))
        punta_verso("thigh_l", "calf_l", (0.10, -1.0, -0.08))       # cosce orizzontali
        punta_verso("thigh_r", "calf_r", (-0.10, -1.0, -0.08))
        punta_verso("calf_l", "foot_l", (0, -0.05, -1.0))           # stinchi verticali
        punta_verso("calf_r", "foot_r", (0, -0.05, -1.0))
        caviglia = (testa("foot_l").z + testa("foot_r").z) / 2
        sposta("pelvis", (0, 0, -(caviglia - 8.7)))


# -----------------------------------------------------------------------------
# 3. controlli
# -----------------------------------------------------------------------------
def mesh_valutata(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    M = o.matrix_world
    co = [M @ v.co for v in me.vertices]
    tri = [t.vertices[:] for t in me.loop_triangles]
    ev.to_mesh_clear()
    return co, tri


def bvh_di(o):
    co, tri = mesh_valutata(o)
    return BVHTree.FromPolygons(co, tri), co, tri


def conta(nome_posa):
    b_corpo, _, _ = bvh_di(corpo)
    b_acc, _, _ = bvh_di(acc)
    b_ann, _, _ = bvh_di(ann)
    co_s, tri_s = mesh_valutata(saio)
    co_m, tri_m = mesh_valutata(mant)
    n = len(co_s)
    b_stoffa = BVHTree.FromPolygons(co_s + co_m, tri_s + [tuple(i + n for i in t) for t in tri_m])
    out = dict(acc_corpo={}, acc_stoffa={}, stoffa_corpo=0)
    for i, j in b_acc.overlap(b_corpo):
        g = GRUPPO[parte_tri[i]]
        out["acc_corpo"][g] = out["acc_corpo"].get(g, 0) + 1
    out["acc_corpo"]["anello"] = len(b_ann.overlap(b_corpo))
    tri_acc_stoffa = {}
    for i, j in b_acc.overlap(b_stoffa):
        tri_acc_stoffa.setdefault(GRUPPO[parte_tri[i]], set()).add(i)
    out["acc_stoffa"] = tri_acc_stoffa
    out["stoffa_corpo"] = len({j for i, j in b_stoffa.overlap(b_corpo) if visibile_tri[j]})
    return out


# -----------------------------------------------------------------------------
# 4. render
# -----------------------------------------------------------------------------
for o in sc.objects:
    if o.type in ('MESH', 'CURVE'):
        o.hide_render = o not in (corpo, saio, mant, acc, ann)
pelle = bpy.data.materials.new("V_pelle")
pelle.use_nodes = True
pelle.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.50, 0.33, 0.25, 1)
corpo.data.materials.clear()
corpo.data.materials.append(pelle)
for o_copia, o_orig in ((saio, "Saio_Gioco"), (mant, "Mantellina_Gioco"), (acc, "Accessori_Gioco")):
    o_copia.data.materials.clear()
    for m in bpy.data.objects[o_orig].data.materials:
        o_copia.data.materials.append(m)
cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = CAMPIONI
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.view_settings.view_transform = 'Standard'
if sc.world is None:
    sc.world = bpy.data.worlds.new("W")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.55, 0.54, 1)
sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
sole = bpy.data.objects.new("sole", bpy.data.lights.new("sole", 'SUN'))
sole.data.energy = 3.5
sc.collection.objects.link(sole)
sole.rotation_euler = (math.radians(55), 0, math.radians(-35))


def scatto(nome, loc, mira, lente=50, res=(700, 1000)):
    cam_d.lens = lente
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(mira) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, nome + ".png")
    bpy.ops.render.render(write_still=True)


riposo()
base = conta("riferimento")
log("[2] posa di riferimento: accessori/stoffa " +
    ", ".join(f"{k} {len(v)}" for k, v in base["acc_stoffa"].items()))
risultati = {}
for nome in ("camminata", "in_ginocchio", "braccia_alzate", "seduto"):
    posa(nome)
    c = conta(nome)
    nuovi = {k: len(v - base["acc_stoffa"].get(k, set())) for k, v in c["acc_stoffa"].items()}
    nuovi = {k: v for k, v in nuovi.items() if v}
    risultati[nome] = (c, nuovi)
    log(f"[3] {nome}: accessori/corpo " + (", ".join(f"{k} {v}" for k, v in c["acc_corpo"].items() if v) or "nessuno")
        + " | accessori/stoffa in piu' rispetto al riferimento " + (", ".join(f"{k} {v}" for k, v in nuovi.items()) or "nessuno")
        + f" | stoffa/pelle visibile {c['stoffa_corpo']}")
    zc = 0.55 if nome in ("in_ginocchio", "seduto") else 0.9
    scatto(f"posa_{nome}_34", (2.4, -3.6, 1.3), (0.0, 0.0, zc), 55)
    scatto(f"posa_{nome}_fianco", (4.2, 0.2, 1.1), (0.0, 0.0, zc), 55)
riposo()
with open(os.path.join(OUT, "prova_pose.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(righe) + "\n")
print("POSE OK ->", OUT)
