# =============================================================================
#  Render di controllo della Fase 2 (usato nel cloud; funziona anche in locale)
#  Uso:  blender -b Saio_Abate_v002.blend --python render_controllo_fase2.py -- <cartella_output>
#  Lavora sul file aperto in memoria e NON lo salva: il .blend resta com'e'.
#  Motore Workbench = lo stesso aspetto della vista "Solid" di Blender.
# =============================================================================
import bpy
import math
import os
import sys
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "//Render"
OUT = bpy.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)
RES = (700, 1100)

sc = bpy.context.scene
for lc in bpy.context.view_layer.layer_collection.children:
    lc.exclude = lc.name in ("REF_Originale", "TEST")


def mat(nome, rgba):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    m.diffuse_color = rgba
    return m


M_PELLE = mat("V_pelle", (0.86, 0.58, 0.44, 1))
M_SAIO = mat("V_saio", (0.50, 0.36, 0.24, 1))
M_RISV = mat("V_risvolto", (0.88, 0.78, 0.60, 1))
M_MANT = mat("V_mantellina", (0.32, 0.22, 0.14, 1))
M_FILO = mat("V_filo", (0.05, 0.04, 0.04, 1))
M_CUCI = mat("V_cucitura", (0.86, 0.07, 0.05, 1))
M_CHIARO = mat("V_chiaro", (0.80, 0.77, 0.72, 1))
M_CHIARO2 = mat("V_chiaro2", (0.66, 0.70, 0.76, 1))

corpo = bpy.data.objects["REF_Corpo"]
saio = bpy.data.objects["Saio_Blockout"]
mant = bpy.data.objects["Mantellina_Blockout"]


def assegna(obj, *mats):
    obj.data.materials.clear()
    for m in mats:
        obj.data.materials.append(m)


assegna(corpo, M_PELLE)
for p in corpo.data.polygons:
    p.material_index = 0
chiaro = saio.data.attributes.get("chiaro")
indici_saio = [1 if (chiaro and chiaro.data[i].value > 0.5) else 0 for i in range(len(saio.data.polygons))]


def colori_forma():
    assegna(saio, M_SAIO, M_RISV)
    for p, k in zip(saio.data.polygons, indici_saio):
        p.material_index = k
    assegna(mant, M_MANT)


def colori_gabbia():
    assegna(saio, M_CHIARO, M_CHIARO)
    assegna(mant, M_CHIARO2)


for o in (saio, mant):
    o.show_wire = False

# --- fili della gabbia e cuciture (oggetti aggiuntivi, solo per il render) ---
coll_vis = bpy.data.collections.new("_VIS")
sc.collection.children.link(coll_vis)


def fili(obj, spessore=0.0025):
    o = bpy.data.objects.new(obj.name + "_fili", obj.data.copy())
    coll_vis.objects.link(o)
    o.data.materials.clear()
    o.data.materials.append(M_FILO)
    w = o.modifiers.new("w", 'WIREFRAME')
    w.thickness = spessore
    w.use_replace = True
    w.use_even_offset = True
    w.use_relative_offset = False
    w.offset = 1.0
    return o


def cuciture(obj, raggio=0.0042):
    cu = bpy.data.curves.new(obj.name + "_cuciture", 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = raggio
    cu.bevel_resolution = 2
    for e in obj.data.edges:
        if e.use_seam:
            s = cu.splines.new('POLY')
            s.points.add(1)
            for k, vi in enumerate(e.vertices):
                co = obj.matrix_world @ obj.data.vertices[vi].co
                s.points[k].co = (co.x, co.y, co.z, 1)
    o = bpy.data.objects.new(obj.name + "_cuciture", cu)
    o.data.materials.append(M_CUCI)
    coll_vis.objects.link(o)
    return o


VIS_S = [fili(saio), cuciture(saio)]
VIS_M = [fili(mant), cuciture(mant)]

# --- Workbench (come la vista Solid) ---
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_shadows = True
sh.shadow_intensity = 0.3
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_specular_highlight = False
if sc.world is None:
    sc.world = bpy.data.worlds.new("W")
sc.world.color = (0.80, 0.80, 0.79)
sc.display.render_aa = '16'

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam

VISTE_ORTO = {
    "fronte": ((0, -6, 0.92), (90, 0, 0)),
    "fianco": ((6, 0, 0.92), (90, 0, 90)),
    "retro": ((0, 6, 0.92), (90, 0, 180)),
}


def orto(vista, scala=1.98):
    loc, rot = VISTE_ORTO[vista]
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = scala
    cam.location = Vector(loc)
    cam.rotation_euler = [math.radians(a) for a in rot]


def prospettiva(loc, mira, lente):
    cam_data.type = 'PERSP'
    cam_data.lens = lente
    cam_data.sensor_fit = 'AUTO'
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(mira) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def visibili(lista_on):
    for o in sc.objects:
        if o.type in ('MESH', 'CURVE'):
            o.hide_render = o not in lista_on


def render(nome, res=RES):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, nome + ".png")
    bpy.ops.render.render(write_still=True)


def suddivisione(on):
    for o in (saio, mant):
        o.modifiers["Suddivisione"].show_render = on


# 1) FORMA: superficie liscia (suddivisa) sul corpo
colori_forma()
suddivisione(True)
visibili([corpo, saio, mant])
for v in ("fronte", "fianco", "retro"):
    orto(v)
    render("forma_" + v)
prospettiva((2.75, -4.30, 1.50), (0.0, 0.0, 0.91), 85)
render("forma_34", (900, 900))
prospettiva((1.10, -1.55, 1.70), (0.04, 0.0, 1.40), 70)
render("dettaglio_collo", (900, 900))
prospettiva((-1.15, 1.55, 1.72), (-0.04, 0.04, 1.40), 70)
render("dettaglio_collo_retro", (900, 900))

# 2) GABBIA E CUCITURE (gabbia vera, senza suddivisione)
colori_gabbia()
suddivisione(False)
visibili([corpo, saio, mant] + VIS_S + VIS_M)
for v in ("fronte", "fianco", "retro"):
    orto(v)
    render("gabbia_" + v)
# 3) SOLO SAIO (mantellina nascosta): sprone, giri manica, spalle
visibili([corpo, saio] + VIS_S)
for v in ("fronte", "retro"):
    orto(v)
    render("saio_" + v)
prospettiva((1.20, -1.65, 1.62), (0.10, 0.0, 1.32), 60)
render("saio_spalla", (900, 900))
print("RENDER OK ->", OUT)
