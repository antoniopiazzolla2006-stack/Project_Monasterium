# =============================================================================
#  Render di controllo della Fase 7b (pelle della testa senza canottiera)
#  Uso:  blender -b Saio_Abate_v007.blend --python render_controllo_fase7b.py -- <cartella_texture> <uscita> <prefisso> [campioni]
#   <cartella_texture>: dove stanno T_Head_LOD3_BC_VT.PNG, _N_VT, _SRMF_VT, _Scatter_VT (originali o ritoccate)
#  Lavora sul file aperto in memoria e NON lo salva.
#   - "pelle": solo la mesh della pelle della testa (come quando la apri da sola in Unreal),
#     davanti, tre quarti, spalla vista dall'alto, con luce radente per vedere la normal map
#   - "gioco": abate col saio e la mantellina, visto in prima persona da vicino (occhi a 1,75 m)
#  Nota: la geometria e' il LOD0 esportato nella Fase 1; in gioco la testa usa il LOD3,
#  con le stesse UV (le texture sono le stesse). La barba (Groom) qui non c'e'.
# =============================================================================
import bpy
import bmesh
import math
import os
import sys
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
TEX, OUT, PREF = argv[0], argv[1], argv[2]
CAMPIONI = int(argv[3]) if len(argv) > 3 else 64
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for lc in bpy.context.view_layer.layer_collection.children:
    lc.exclude = lc.name in ("TEST", "FASE3_SIMULAZIONE", "BLOCKOUT", "FISICA", "DRAPPEGGIO")
for o in bpy.data.collections["REF_Originale"].objects:
    o.hide_render = True

ref = bpy.data.objects["REF_Corpo"]
me = ref.data
# --- dividi REF_Corpo: pelle della testa (UV 0-1, componente piu' grande), resto della testa (occhi, denti), corpo
uvl = me.uv_layers["DiffuseUV"].data
uv = np.zeros(len(me.loops) * 2, np.float32)
uvl.foreach_get("uv", uv)
uv = uv.reshape(-1, 2)
ls = np.zeros(len(me.polygons), np.int32)
me.polygons.foreach_get("loop_start", ls)
lt = np.zeros(len(me.polygons), np.int32)
me.polygons.foreach_get("loop_total", lt)
testa = np.ones(len(me.polygons), bool)
for k in range(lt.max()):
    idx = ls + np.minimum(k, lt - 1)
    u = uv[idx]
    testa &= (u[:, 0] >= 0) & (u[:, 0] <= 1) & (u[:, 1] >= 0) & (u[:, 1] <= 1)
# componenti connesse tra le facce della testa (union-find sui vertici)
vs = [np.array(p.vertices) for p in me.polygons]
par = np.arange(len(me.vertices))


def trova(a):
    while par[a] != a:
        par[a] = par[par[a]]
        a = par[a]
    return a


for i in np.nonzero(testa)[0]:
    v = vs[i]
    r0 = trova(v[0])
    for w in v[1:]:
        r1 = trova(w)
        if r1 != r0:
            par[r1] = r0
radici = np.array([trova(vs[i][0]) for i in np.nonzero(testa)[0]])
val, cnt = np.unique(radici, return_counts=True)
pelle_radice = val[np.argmax(cnt)]
pelle = np.zeros(len(me.polygons), bool)
pelle[np.nonzero(testa)[0][radici == pelle_radice]] = True
altro_testa = testa & ~pelle
print("facce: pelle testa", pelle.sum(), "occhi/denti", altro_testa.sum(), "corpo", (~testa).sum())


def nuova_mesh(nome, sel):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    via = [f for f in bm.faces if not sel[f.index]]
    bmesh.ops.delete(bm, geom=via, context='FACES')
    m2 = bpy.data.meshes.new(nome)
    bm.to_mesh(m2)
    bm.free()
    o = bpy.data.objects.new(nome, m2)
    o.matrix_world = ref.matrix_world
    sc.collection.objects.link(o)
    for p in m2.polygons:
        p.use_smooth = True
    return o


o_pelle = nuova_mesh("V_PelleTesta", pelle)
o_occhi = nuova_mesh("V_OcchiDenti", altro_testa)
o_corpo = nuova_mesh("V_Corpo", ~testa)
ref.hide_render = True


def img(nome, colore):
    im = bpy.data.images.load(os.path.join(TEX, nome + ".PNG"), check_existing=False)
    im.colorspace_settings.name = 'sRGB' if colore else 'Non-Color'
    return im


# --- materiale pelle con le texture del MetaHuman (LOD3)
m = bpy.data.materials.new("V_PelleMH")
m.use_nodes = True
nt = m.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
outn = nt.nodes.new("ShaderNodeOutputMaterial")
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])
uvn = nt.nodes.new("ShaderNodeUVMap")
uvn.uv_map = "DiffuseUV"
t_bc = nt.nodes.new("ShaderNodeTexImage"); t_bc.image = img("T_Head_LOD3_BC_VT", True)
t_n = nt.nodes.new("ShaderNodeTexImage"); t_n.image = img("T_Head_LOD3_N_VT", False)
t_s = nt.nodes.new("ShaderNodeTexImage"); t_s.image = img("T_Head_LOD3_SRMF_VT", False)
t_sc = nt.nodes.new("ShaderNodeTexImage"); t_sc.image = img("T_Head_LOD3_Scatter_VT", False)
for t in (t_bc, t_n, t_s, t_sc):
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"])
    t.interpolation = 'Cubic'
nt.links.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
# normal map DirectX (Unreal) -> OpenGL (Blender): G invertito
sep = nt.nodes.new("ShaderNodeSeparateColor")
nt.links.new(t_n.outputs["Color"], sep.inputs["Color"])
inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
nt.links.new(sep.outputs["Green"], inv.inputs[1])
comb = nt.nodes.new("ShaderNodeCombineColor")
nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
nt.links.new(inv.outputs["Value"], comb.inputs["Green"])
nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.uv_map = "DiffuseUV"
nt.links.new(comb.outputs["Color"], nmap.inputs["Color"])
nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
sep2 = nt.nodes.new("ShaderNodeSeparateColor")
nt.links.new(t_s.outputs["Color"], sep2.inputs["Color"])
nt.links.new(sep2.outputs["Green"], bsdf.inputs["Roughness"])
nt.links.new(sep2.outputs["Red"], bsdf.inputs["Specular IOR Level"])
# subsurface: maschera Scatter (0 = niente, come la stoffa della canottiera)
sep3 = nt.nodes.new("ShaderNodeSeparateColor")
nt.links.new(t_sc.outputs["Color"], sep3.inputs["Color"])
mul = nt.nodes.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.45
nt.links.new(sep3.outputs["Red"], mul.inputs[0])
nt.links.new(mul.outputs["Value"], bsdf.inputs["Subsurface Weight"])
bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
bsdf.inputs["Subsurface Scale"].default_value = 0.004
o_pelle.data.materials.clear()
o_pelle.data.materials.append(m)


def semplice(nome, rgb, rough):
    mm = bpy.data.materials.new(nome)
    mm.use_nodes = True
    b = mm.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return mm


# occhi, ciglia e denti (solo per non disturbare l'immagine): bulbi scuri, ciglia scure, denti chiari
o_occhi.data.materials.clear()
o_occhi.data.materials.append(semplice("V_Bulbi", (0.06, 0.04, 0.03), 0.08))
o_occhi.data.materials.append(semplice("V_Ciglia", (0.025, 0.02, 0.018), 0.6))
o_occhi.data.materials.append(semplice("V_Denti", (0.7, 0.66, 0.6), 0.35))
_vs2 = [np.array(p.vertices) for p in o_occhi.data.polygons]
_par2 = np.arange(len(o_occhi.data.vertices))


def _trova2(a):
    while _par2[a] != a:
        _par2[a] = _par2[_par2[a]]
        a = _par2[a]
    return a


for v in _vs2:
    r0 = _trova2(v[0])
    for w in v[1:]:
        r1 = _trova2(w)
        if r1 != r0:
            _par2[r1] = r0
_rad2 = np.array([_trova2(v[0]) for v in _vs2])
_val2, _inv2, _cnt2 = np.unique(_rad2, return_inverse=True, return_counts=True)
_zc = np.array([np.mean([o_occhi.data.vertices[i].co.z for i in v]) for v in _vs2])
for i, p in enumerate(o_occhi.data.polygons):
    n_comp = _cnt2[_inv2[i]]
    if n_comp >= 600 and _zc[i] * ref.matrix_world[2][2] + ref.matrix_world[2][3] > 1.66:
        p.material_index = 0          # bulbi oculari
    elif n_comp < 200:
        p.material_index = 1          # ciglia (tante schede piccole)
    else:
        p.material_index = 2          # denti e gengive
o_corpo.data.materials.clear()
o_corpo.data.materials.append(semplice("V_CorpoPelle", (0.36, 0.17, 0.10), 0.6))

saio, mant, acc = bpy.data.objects["Saio_Gioco"], bpy.data.objects["Mantellina_Gioco"], bpy.data.objects["Accessori_Gioco"]
ann = bpy.data.objects["Anello_Gioco"]
for o in sc.objects:
    if o.type in ('MESH', 'CURVE'):
        o.hide_render = o not in (o_pelle, o_occhi, o_corpo, saio, mant, acc, ann)

# --- camera e luci
cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = CAMPIONI
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.render.image_settings.file_format = 'PNG'
if sc.world is None:
    sc.world = bpy.data.worlds.new("W")
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
bg.inputs["Strength"].default_value = 0.35
sole = bpy.data.objects.new("sole", bpy.data.lights.new("sole", 'SUN'))
sole.data.angle = math.radians(2)
sc.collection.objects.link(sole)


def luce(elev, azim, forza):
    sole.rotation_euler = (math.radians(90 - elev), 0, math.radians(azim))
    sole.data.energy = forza


def scatto(nome, loc, mira, lente, res, oggetti_visibili=None):
    if oggetti_visibili is not None:
        for o in (o_pelle, o_occhi, o_corpo, saio, mant, acc, ann):
            o.hide_render = o not in oggetti_visibili
    cam_d.lens = lente
    cam_d.clip_start = 0.01
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(mira) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filepath = os.path.join(OUT, f"{PREF}_{nome}.png")
    bpy.ops.render.render(write_still=True)


VISTE = argv[4] if len(argv) > 4 else "tutte"
solo_pelle = [o_pelle, o_occhi]
if VISTE in ("tutte", "pelle"):
    # 1) pelle, davanti (luce morbida un po' laterale)
    luce(35, -35, 3.0)
    scatto("pelle_davanti", (0.0, -0.62, 1.52), (0.0, 0.0, 1.49), 50, (900, 700), solo_pelle)
    # 2) pelle, tre quarti (spalla sinistra dell'abate = x > 0)
    luce(30, 40, 3.0)
    scatto("pelle_34", (0.42, -0.42, 1.62), (0.06, 0.0, 1.49), 50, (900, 700), solo_pelle)
    # 3) spalla vista dall'alto, luce radente (mette in evidenza il rilievo della normal map)
    luce(12, 70, 4.0)
    scatto("pelle_spalla_radente", (0.18, -0.20, 1.78), (0.10, 0.01, 1.50), 50, (900, 700), solo_pelle)
    # 4) dietro
    luce(35, 150, 3.0)
    scatto("pelle_dietro", (0.0, 0.62, 1.55), (0.0, 0.0, 1.50), 50, (900, 700), solo_pelle)
if VISTE in ("tutte", "gioco"):
    # 5) in gioco: prima persona da vicino, occhi a 1,75 m, a ~0,5 m dall'abate
    tutti = [o_pelle, o_occhi, o_corpo, saio, mant, acc, ann]
    luce(55, -25, 3.0)
    scatto("gioco_vicino", (0.0, -0.58, 1.75), (0.0, -0.06, 1.47), 30, (900, 900), tutti)
    scatto("gioco_vicino_lato", (0.22, -0.52, 1.76), (0.03, -0.04, 1.48), 30, (900, 900), tutti)
    # 6) dentro il colletto (stessa posizione, inquadratura stretta sullo scollo)
    scatto("gioco_scollo", (0.0, -0.58, 1.75), (0.0, -0.02, 1.47), 70, (900, 600), tutti)
    scatto("gioco_scollo_lato", (0.22, -0.52, 1.76), (0.02, -0.01, 1.47), 70, (900, 600), tutti)
print("RENDER OK ->", OUT)
