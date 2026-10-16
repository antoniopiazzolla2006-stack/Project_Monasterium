# =============================================================================
#  Render di controllo della Fase 7 (usato nel cloud; funziona anche in locale)
#  Uso:  blender -b Saio_Abate_v007.blend --python render_controllo_fase7.py -- <cartella_output> [campioni]
#  Lavora sul file aperto in memoria e NON lo salva.
#   - figura intera con gli accessori (davanti, tre quarti, fianco, dietro)
#   - primi piani: nodo in vita, nodi della coda, corona, Tau, sandali, anello
# =============================================================================
import bpy
import math
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = bpy.path.abspath(argv[0] if argv else "//Render")
CAMPIONI = int(argv[1]) if len(argv) > 1 else 48
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for lc in bpy.context.view_layer.layer_collection.children:
    lc.exclude = lc.name in ("TEST", "FASE3_SIMULAZIONE", "BLOCKOUT", "FISICA", "DRAPPEGGIO", "ACCESSORI_ALTA")
    lc.hide_viewport = False
# l'armatura (genitore dell'anello) deve essere valutata: la sua collezione resta inclusa ma il corpo
# importato e l'armatura non si vedono nei render
for o in bpy.data.collections["REF_Originale"].objects:
    o.hide_render = True
ref = bpy.data.objects["REF_Corpo"]
saio, mant = bpy.data.objects["Saio_Gioco"], bpy.data.objects["Mantellina_Gioco"]
acc, ann = bpy.data.objects["Accessori_Gioco"], bpy.data.objects["Anello_Gioco"]
visibili = [ref, saio, mant, acc, ann]
for o in sc.objects:
    if o.type in ('MESH', 'CURVE'):
        o.hide_render = o not in visibili
pelle = bpy.data.materials.new("V_pelle")
pelle.use_nodes = True
b = pelle.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.50, 0.33, 0.25, 1)
b.inputs["Roughness"].default_value = 0.55
ref.data.materials.clear()
ref.data.materials.append(pelle)

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def scatto(nome, loc, mira, lente, res=(900, 900), clip=0.01):
    cam_data.type = 'PERSP'
    cam_data.lens = lente
    cam_data.clip_start = clip
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(mira) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filepath = os.path.join(OUT, nome + ".png")
    bpy.ops.render.render(write_still=True)


sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
if sc.world is None:
    sc.world = bpy.data.worlds.new("W")
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.use_denoising = True
sc.cycles.samples = CAMPIONI
sc.cycles.max_bounces = 4
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.55, 0.55, 0.54, 1)
bg.inputs["Strength"].default_value = 0.30
sole_d = bpy.data.lights.new("sole", 'SUN')
sole_d.energy = 3.5
sole_d.angle = math.radians(3)
sole = bpy.data.objects.new("sole", sole_d)
sc.collection.objects.link(sole)


def sole_da(elev, azim):
    sole.rotation_euler = (math.radians(elev), 0, math.radians(azim))


# punti notevoli (presi dalla geometria)
def centro_parte(codice):
    me = acc.data
    import numpy as np
    par = np.zeros(len(me.polygons), int)
    me.attributes["parte"].data.foreach_get("value", par)
    cen = np.zeros(len(me.polygons) * 3)
    me.polygons.foreach_get("center", cen)
    cen = cen.reshape(-1, 3)[par == codice]
    return Vector(cen.mean(0)), Vector(cen.min(0)), Vector(cen.max(0))


tau_c, _, _ = centro_parte(20)
gr_c, gr_min, gr_max = centro_parte(21)
co_c, co_min, co_max = centro_parte(10)
ann_c = ann.matrix_world @ (sum((v.co for v in ann.data.vertices), Vector()) / len(ann.data.vertices))

# 1) figura intera
sole_da(55, -30)
scatto("insieme_fronte", (0.0, -5.6, 1.0), (0.0, 0.0, 0.90), 55, (700, 1100))
sole_da(58, -40)
scatto("insieme_34", (2.75, -4.30, 1.45), (0.0, 0.0, 0.90), 60, (700, 1100))
sole_da(55, 60)
scatto("insieme_fianco", (5.6, -0.4, 1.0), (0.0, 0.0, 0.90), 55, (700, 1100))
sole_da(55, 150)
scatto("insieme_retro", (-1.2, 5.4, 1.1), (0.0, 0.0, 0.90), 55, (700, 1100))
# 2) primi piani
sole_da(60, -35)
scatto("vita_nodo", (-0.55, -1.15, 1.25), (-0.11, -0.17, 1.08), 70)
scatto("coda_nodi", (-0.60, -1.05, 0.85), (-0.12, -0.20, 0.68), 70)
scatto("corona", (0.65, -1.05, 1.05), (gr_c.x, gr_c.y, gr_c.z - 0.02), 70)
sole_da(50, -20)
scatto("tau", (0.10, -0.95, 1.50), (tau_c.x, tau_c.y, tau_c.z + 0.04), 85)
sole_da(55, -45)
scatto("sandali", (0.55, -0.95, 0.40), (0.0, -0.07, 0.05), 60)
scatto("sandalo_lato", (0.75, -0.10, 0.14), (0.16, -0.08, 0.04), 75)
sole_da(40, 100)
d = (ann_c - Vector((0.0, 0.0, ann_c.z))).normalized()
scatto("anello", tuple(ann_c + d * 0.16 + Vector((0, -0.10, 0.05))), tuple(ann_c), 80)
print("RENDER OK ->", OUT)
