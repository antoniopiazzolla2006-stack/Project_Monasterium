# =============================================================================
#  Render di controllo della Fase 6 (usato nel cloud; funziona anche in locale)
#  Uso:  blender -b Saio_Abate_v006.blend --python render_controllo_fase6.py -- <cartella_output>
#  Lavora sul file aperto in memoria e NON lo salva.
#   - corpo nascosto: le parti del corpo che Unreal togliera' (blu) e quelle che restano
#   - anteprima della lana con le texture finali (Cycles)
# =============================================================================
import bpy
import math
import os
import sys
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "//Render"
OUT = bpy.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for lc in bpy.context.view_layer.layer_collection.children:
    lc.exclude = lc.name in ("TEST", "FASE3_SIMULAZIONE", "BLOCKOUT", "FISICA", "DRAPPEGGIO")
    lc.hide_viewport = False
TEXDIR = os.path.join(os.path.dirname(bpy.data.filepath), "Texture")
corpo = bpy.data.objects["MHC_Abate_FullBody_LOD0"]
saio, mant = bpy.data.objects["Saio_Gioco"], bpy.data.objects["Mantellina_Gioco"]
ref = bpy.data.objects["REF_Corpo"]


def visibili(lista):
    for o in sc.objects:
        if o.type in ('MESH', 'CURVE'):
            o.hide_render = o not in lista


cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def orto(vista, scala=1.98):
    loc, rot = {"fronte": ((0, -6, 0.92), (90, 0, 0)), "fianco": ((6, 0, 0.92), (90, 0, 90)),
                "retro": ((0, 6, 0.92), (90, 0, 180))}[vista]
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = scala
    cam.location = Vector(loc)
    cam.rotation_euler = [math.radians(a) for a in rot]


def prospettiva(loc, mira, lente):
    cam_data.type = 'PERSP'
    cam_data.lens = lente
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(mira) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def render(nome, res):
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
sc.cycles.max_bounces = 4
sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.55, 0.55, 0.54, 1)
bg.inputs["Strength"].default_value = 0.25
sole_d = bpy.data.lights.new("sole", 'SUN')
sole_d.energy = 3.5
sole_d.angle = math.radians(3)
sole = bpy.data.objects.new("sole", sole_d)
sc.collection.objects.link(sole)

# ---------------------------------------------------------------------------
# 1) corpo nascosto: la mappa letta con le UV del corpo (riquadro 1-2 -> 0-1)
# ---------------------------------------------------------------------------
img = bpy.data.images.load(os.path.join(TEXDIR, "T_Corpo_Nascosto.png"), check_existing=True)
img.colorspace_settings.name = 'Non-Color'
m = bpy.data.materials.new("V_corpo_nascosto")
m.use_nodes = True
nt = m.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
uvn = nt.nodes.new("ShaderNodeUVMap")
uvn.uv_map = corpo.data.uv_layers.active.name
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(uvn.outputs["UV"], sep.inputs[0])
mapp = nt.nodes.new("ShaderNodeMapping")
mapp.inputs["Location"].default_value = (-1.0, 0.0, 0.0)
nt.links.new(uvn.outputs["UV"], mapp.inputs["Vector"])
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
tex.interpolation = 'Closest'
nt.links.new(mapp.outputs["Vector"], tex.inputs["Vector"])
corpo_u = nt.nodes.new("ShaderNodeMath")          # 1 se la faccia e' del corpo (u >= 1)
corpo_u.operation = 'GREATER_THAN'
corpo_u.inputs[1].default_value = 1.0
nt.links.new(sep.outputs[0], corpo_u.inputs[0])
nascosto = nt.nodes.new("ShaderNodeMath")           # nero nella mappa e corpo -> nascosto
nascosto.operation = 'MULTIPLY'
inv = nt.nodes.new("ShaderNodeMath")
inv.operation = 'SUBTRACT'
inv.inputs[0].default_value = 1.0
nt.links.new(tex.outputs["Color"], inv.inputs[1])
nt.links.new(inv.outputs[0], nascosto.inputs[0])
nt.links.new(corpo_u.outputs[0], nascosto.inputs[1])
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = 'RGBA'
mix.inputs[6].default_value = (0.55, 0.32, 0.22, 1)   # pelle che resta
mix.inputs[7].default_value = (0.05, 0.25, 0.75, 1)   # pelle che Unreal toglie
nt.links.new(nascosto.outputs[0], mix.inputs["Factor"])
bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
bs.inputs["Roughness"].default_value = 0.6
nt.links.new(mix.outputs[2], bs.inputs["Base Color"])
nt.links.new(bs.outputs[0], out.inputs["Surface"])
corpo.data.materials.clear()
corpo.data.materials.append(m)
corpo.hide_render = False
visibili([corpo])
sc.cycles.samples = 24
sole.rotation_euler = (math.radians(55), 0, math.radians(-30))
for v in ("fronte", "retro"):
    orto(v)
    render("corpo_" + v, (700, 1100))
sole.rotation_euler = (math.radians(55), 0, math.radians(60))
orto("fianco")
render("corpo_fianco", (700, 1100))

# ---------------------------------------------------------------------------
# 2) anteprima della lana (materiale M_Lana del file, texture finali)
# ---------------------------------------------------------------------------
pelle = bpy.data.materials.new("V_pelle")
pelle.use_nodes = True
pelle.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.32, 0.22, 1)
ref.data.materials.clear()
ref.data.materials.append(pelle)
visibili([ref, saio, mant])
sc.cycles.samples = 64
sole.rotation_euler = (math.radians(60), 0, math.radians(-40))
prospettiva((2.75, -4.30, 1.50), (0.0, 0.0, 0.91), 85)
render("lana_34", (900, 900))
sole.rotation_euler = (math.radians(60), 0, math.radians(150))
prospettiva((-2.6, 4.2, 1.55), (0.0, 0.0, 0.95), 85)
render("lana_retro", (900, 900))
sole.rotation_euler = (math.radians(65), 0, math.radians(-50))
prospettiva((0.75, -1.15, 0.95), (0.40, -0.12, 0.98), 50)
render("lana_polsino", (900, 900))
prospettiva((0.55, -1.25, 0.30), (0.05, -0.10, 0.22), 45)
render("lana_orlo", (900, 900))
print("RENDER OK ->", OUT)
