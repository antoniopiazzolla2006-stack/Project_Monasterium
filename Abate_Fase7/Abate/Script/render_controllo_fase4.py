# =============================================================================
#  Render di controllo della Fase 4 (usato nel cloud; funziona anche in locale)
#  Uso:  blender -b Saio_Abate_v004.blend --python render_controllo_fase4.py -- <cartella_output>
#  Lavora sul file aperto in memoria e NON lo salva: il .blend resta com'e'.
#  Motore Workbench = lo stesso aspetto della vista "Solid" di Blender.
# =============================================================================
import bpy
import math
import os
import sys
import numpy as np
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "//Render"
OUT = bpy.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)
RES = (700, 1100)

sc = bpy.context.scene
for lc in bpy.context.view_layer.layer_collection.children:
    lc.exclude = lc.name in ("REF_Originale", "TEST", "FASE3_SIMULAZIONE", "BLOCKOUT")
    lc.hide_viewport = False
sc.frame_set(1)


def mat(nome, rgba):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    m.diffuse_color = rgba
    return m


M_PELLE = mat("V_pelle", (0.86, 0.58, 0.44, 1))
M_SAIO = mat("V_saio", (0.50, 0.36, 0.24, 1))
M_RISV = mat("V_risvolto", (0.88, 0.78, 0.60, 1))
M_MANT = mat("V_mantellina", (0.32, 0.22, 0.14, 1))
M_BORDO_S = mat("V_bordo_saio", (0.62, 0.47, 0.32, 1))
M_BORDO_M = mat("V_bordo_mant", (0.45, 0.33, 0.22, 1))
M_FILO = mat("V_filo", (0.05, 0.04, 0.04, 1))

ob = {n: bpy.data.objects[n] for n in ("REF_Corpo", "Saio_Gioco", "Mantellina_Gioco", "Saio_Drappeggio",
                                         "Mantellina_Drappeggio", "Saio_Fisica", "Mantellina_Fisica")}


def colora(o, base, chiaro_mat=None, bordo_mat=None):
    o.data.materials.clear()
    for m in (base, chiaro_mat or base, bordo_mat or base):
        o.data.materials.append(m)
    ch = o.data.attributes.get("chiaro")
    bo = o.data.attributes.get("bordo")
    for p in o.data.polygons:
        k = 0
        if ch is not None and ch.data[p.index].value > 0.5:
            k = 1
        if bo is not None and bo.data[p.index].value > 0.5:
            k = 2 if k == 0 else 1
        p.material_index = k
    o.data.shade_smooth()


colora(ob["REF_Corpo"], M_PELLE)
colora(ob["Saio_Gioco"], M_SAIO, M_RISV, M_BORDO_S)
colora(ob["Saio_Drappeggio"], M_SAIO, M_RISV)
colora(ob["Mantellina_Gioco"], M_MANT, None, M_BORDO_M)
colora(ob["Mantellina_Drappeggio"], M_MANT)

# fili (spigoli) della mesh di gioco
fili = []
for n in ("Saio_Gioco", "Mantellina_Gioco"):
    f = bpy.data.objects.new(n + "_fili", ob[n].data.copy())
    sc.collection.objects.link(f)
    f.data.materials.clear()
    f.data.materials.append(M_FILO)
    w = f.modifiers.new("w", 'WIREFRAME')
    w.thickness = 0.0016
    w.use_replace = True
    fili.append(f)

# mappa "proposta fisica" come colore dei vertici (rampa blu: chiaro = segue il corpo, scuro = libera)
RAMPA = [(0.0, "#cde2fb"), (0.25, "#86b6ef"), (0.5, "#3987e5"), (0.75, "#1c5cab"), (1.0, "#0d366b")]


def hex_rgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]   # in lineare


def rampa(x):
    x = min(1.0, max(0.0, x))
    for (a, ca), (b, cb) in zip(RAMPA[:-1], RAMPA[1:]):
        if x <= b:
            t = (x - a) / (b - a)
            A, B = hex_rgb(ca), hex_rgb(cb)
            return [A[i] + (B[i] - A[i]) * t for i in range(3)] + [1.0]
    return hex_rgb(RAMPA[-1][1]) + [1.0]


for n in ("Saio_Fisica", "Mantellina_Fisica"):
    o = ob[n]
    g = o.vertex_groups["Proposta_Fisica"]
    w = np.zeros(len(o.data.vertices))
    for v in o.data.vertices:
        for gg in v.groups:
            if gg.group == g.index:
                w[v.index] = gg.weight
    ca = o.data.color_attributes.get("proposta") or o.data.color_attributes.new("proposta", 'FLOAT_COLOR', 'POINT')
    ca.data.foreach_set("color", np.array([rampa(x) for x in w]).ravel())
    o.data.color_attributes.active_color = ca
    o.data.shade_smooth()
pelle_rgb = list(M_PELLE.diffuse_color)
cp = ob["REF_Corpo"].data.color_attributes.get("vista_pelle") or ob["REF_Corpo"].data.color_attributes.new("vista_pelle", 'FLOAT_COLOR', 'POINT')
cp.data.foreach_set("color", np.tile(pelle_rgb, len(ob["REF_Corpo"].data.vertices)))
ob["REF_Corpo"].data.color_attributes.active_color = cp

sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_shadows = True
sh.shadow_intensity = 0.35
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_specular_highlight = False
sh.show_backface_culling = False
if sc.world is None:
    sc.world = bpy.data.worlds.new("W")
sc.world.color = (0.80, 0.80, 0.79)
sc.display.render_aa = '16'

cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
VISTE_ORTO = {"fronte": ((0, -6, 0.92), (90, 0, 0)), "fianco": ((6, 0, 0.92), (90, 0, 90)),
              "retro": ((0, 6, 0.92), (90, 0, 180))}


def orto(vista, scala=1.98):
    loc, rot = VISTE_ORTO[vista]
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = scala
    cam.location = Vector(loc)
    cam.rotation_euler = [math.radians(a) for a in rot]


def prospettiva(loc, mira, lente):
    cam_data.type = 'PERSP'
    cam_data.lens = lente
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(mira) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def visibili(lista):
    for o in sc.objects:
        if o.type in ('MESH', 'CURVE'):
            o.hide_render = o not in lista


def render(nome, res=RES):
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, nome + ".png")
    bpy.ops.render.render(write_still=True)


C = ob["REF_Corpo"]
GIOCO = [C, ob["Saio_Gioco"], ob["Mantellina_Gioco"]]
ALTO = [C, ob["Saio_Drappeggio"], ob["Mantellina_Drappeggio"]]

# 1) mesh di gioco con i fili
visibili(GIOCO + fili)
for v in ("fronte", "fianco", "retro"):
    orto(v)
    render("gioco_" + v)
# 2) alta contro gioco (senza fili)
for etichetta, gruppo in (("alto", ALTO), ("gioco", GIOCO)):
    visibili(gruppo)
    prospettiva((2.75, -4.30, 1.50), (0.0, 0.0, 0.91), 85)
    render("cf34_" + etichetta, (900, 900))
    prospettiva((0.95, -1.75, 1.22), (0.0, -0.02, 1.08), 55)
    render("cfvita_" + etichetta, (900, 900))
    prospettiva((-1.15, 1.55, 1.72), (-0.04, 0.04, 1.40), 70)
    render("cfcappuccio_" + etichetta, (900, 900))
# 3) bordi spessi
visibili(GIOCO)
prospettiva((0.95, -0.85, 0.80), (0.47, -0.10, 1.03), 55)
render("bordo_polsino", (900, 900))
prospettiva((0.65, -0.95, 1.20), (0.12, -0.10, 1.32), 55)
render("bordo_mantellina", (900, 900))
prospettiva((0.34, -0.80, 0.015), (0.05, -0.26, 0.105), 30)
render("bordo_orlo", (900, 900))
prospettiva((0.50, 0.95, 1.20), (0.02, 0.18, 1.33), 55)
render("bordo_cappuccio", (900, 900))
# 4) mesh per la fisica colorata con la proposta
sh.color_type = 'VERTEX'
visibili([C, ob["Saio_Fisica"], ob["Mantellina_Fisica"]])
for v in ("fronte", "fianco", "retro"):
    orto(v)
    render("fisica_" + v)
print("RENDER OK ->", OUT)
