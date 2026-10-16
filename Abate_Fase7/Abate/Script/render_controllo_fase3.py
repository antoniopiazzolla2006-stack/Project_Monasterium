# =============================================================================
#  Render di controllo della Fase 3 (usato nel cloud; funziona anche in locale)
#  Uso:  blender -b Saio_Abate_v003.blend --python render_controllo_fase3.py -- <cartella_output>
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
    lc.exclude = lc.name in ("REF_Originale", "TEST", "FASE3_SIMULAZIONE")
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

corpo = bpy.data.objects["REF_Corpo"]
oggetti = {n: bpy.data.objects[n] for n in
           ("Saio_Drappeggio", "Mantellina_Drappeggio", "Saio_Blockout", "Mantellina_Blockout")}


def assegna(obj, *mats):
    obj.data.materials.clear()
    for m in mats:
        obj.data.materials.append(m)


def colora_saio(obj):
    assegna(obj, M_SAIO, M_RISV)
    chiaro = obj.data.attributes.get("chiaro")
    for p in obj.data.polygons:
        p.material_index = 1 if (chiaro and chiaro.data[p.index].value > 0.5) else 0


assegna(corpo, M_PELLE)
for p in corpo.data.polygons:
    p.material_index = 0
colora_saio(oggetti["Saio_Drappeggio"])
colora_saio(oggetti["Saio_Blockout"])
assegna(oggetti["Mantellina_Drappeggio"], M_MANT)
assegna(oggetti["Mantellina_Blockout"], M_MANT)
for o in oggetti.values():
    o.show_wire = False
    o.data.shade_smooth()

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
sh.shadow_intensity = 0.35
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


DOPO = [corpo, oggetti["Saio_Drappeggio"], oggetti["Mantellina_Drappeggio"]]
PRIMA = [corpo, oggetti["Saio_Blockout"], oggetti["Mantellina_Blockout"]]

# 1) drappeggio: viste ortogonali
visibili(DOPO)
for v in ("fronte", "fianco", "retro"):
    orto(v)
    render("drappeggio_" + v)
# 2) prima (blockout) per il confronto
visibili(PRIMA)
for v in ("fronte", "fianco"):
    orto(v)
    render("blockout_" + v)
# 3) dettagli del drappeggio
visibili(DOPO)
prospettiva((2.75, -4.30, 1.50), (0.0, 0.0, 0.91), 85)
render("d_34", (900, 900))
prospettiva((0.95, -1.75, 1.22), (0.0, -0.02, 1.08), 55)
render("d_vita", (900, 900))
prospettiva((1.45, -1.55, 1.32), (0.36, -0.05, 1.16), 60)
render("d_manica", (900, 900))
prospettiva((0.75, -1.45, 1.66), (0.02, -0.02, 1.42), 70)
render("d_collo", (900, 900))
prospettiva((-1.15, 1.55, 1.72), (-0.04, 0.04, 1.40), 70)
render("d_cappuccio", (900, 900))
prospettiva((1.10, -2.30, 0.30), (0.0, 0.0, 0.36), 45)
render("d_orlo", (900, 900))
print("RENDER OK ->", OUT)
