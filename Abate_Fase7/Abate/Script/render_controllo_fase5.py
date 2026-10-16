# =============================================================================
#  Render di controllo della Fase 5 (usato nel cloud; funziona anche in locale)
#  Uso:  blender -b Saio_Abate_v005.blend --python render_controllo_fase5.py -- <cartella_output>
#  Lavora sul file aperto in memoria e NON lo salva: il .blend resta com'e'.
#   - scacchiera sulla mesh di gioco (Workbench): stessa scala ovunque, filo verticale
#   - normal map: mesh di gioco senza / con normal map / drappeggio alto (Cycles)
#   - ombre d'ambiente sul modello e anteprima del materiale (Cycles)
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
    lc.exclude = lc.name in ("REF_Originale", "TEST", "FASE3_SIMULAZIONE", "BLOCKOUT", "FISICA")
    lc.hide_viewport = False
ob = {n: bpy.data.objects[n] for n in ("REF_Corpo", "Saio_Gioco", "Mantellina_Gioco", "Saio_Drappeggio",
                                         "Mantellina_Drappeggio")}
C = ob["REF_Corpo"]
GIOCO = [C, ob["Saio_Gioco"], ob["Mantellina_Gioco"]]
ALTO = [C, ob["Saio_Drappeggio"], ob["Mantellina_Drappeggio"]]
TEXDIR = os.path.join(os.path.dirname(bpy.data.filepath), "Texture")


def immagine(nome):
    img = bpy.data.images.load(os.path.join(TEXDIR, nome + ".png"), check_existing=True)
    img.colorspace_settings.name = 'Non-Color'
    return img


def materiale(nome, colore, normal_map=False, scacchi=None, ao=False, emissione_ao=False):
    m = bpy.data.materials.new(nome)
    m.diffuse_color = colore
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if scacchi is not None:                      # Workbench mostra il nodo immagine attivo
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = scacchi
        bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(t.outputs["Color"], bs.inputs["Base Color"])
        nt.links.new(bs.outputs[0], out.inputs["Surface"])
        nt.nodes.active = t
        return m
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    if emissione_ao:                             # ombre come luce propria: si vede la mappa e basta
        ta = nt.nodes.new("ShaderNodeTexImage")
        ta.image = immagine("T_Lana_AO")
        nt.links.new(uvn.outputs["UV"], ta.inputs["Vector"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = 'FLOAT'
        nt.links.new(ta.outputs["Color"], sep.inputs["Color"])
        nt.links.new(geo.outputs["Backfacing"], mix.inputs["Factor"])
        nt.links.new(sep.outputs[0], mix.inputs["A"])
        nt.links.new(sep.outputs[1], mix.inputs["B"])
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(mix.outputs[0], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        return m
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Base Color"].default_value = colore
    bs.inputs["Roughness"].default_value = 0.9
    nt.links.new(bs.outputs[0], out.inputs["Surface"])
    if normal_map:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = immagine("T_Lana_N")
        nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        comb = nt.nodes.new("ShaderNodeCombineColor")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.uv_map = "UVMap"
        nt.links.new(tn.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs[0], comb.inputs[0])
        nt.links.new(sep.outputs[1], inv.inputs[1])
        nt.links.new(inv.outputs[0], comb.inputs[1])
        nt.links.new(sep.outputs[2], comb.inputs[2])
        nt.links.new(comb.outputs[0], nm.inputs["Color"])
        nt.links.new(nm.outputs[0], bs.inputs["Normal"])
    return m


def assegna(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)


PELLE = (0.86, 0.58, 0.44, 1)     # Workbench (colori come nelle fasi precedenti)
SAIO_C = (0.16, 0.115, 0.08, 1)   # Cycles: colori lineari, piu' scuri
MANT_C = (0.11, 0.08, 0.055, 1)
PELLE_C = (0.55, 0.32, 0.22, 1)
m_pelle = materiale("V_pelle", PELLE)
assegna(C, m_pelle)

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


def visibili(lista):
    for o in sc.objects:
        if o.type in ('MESH', 'CURVE'):
            o.hide_render = o not in lista


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

# ---------------------------------------------------------------------------
# 1) scacchiera (Workbench, colore = texture)
# ---------------------------------------------------------------------------
griglia = bpy.data.images.new("V_Scacchi", 2048, 2048)
griglia.generated_type = 'COLOR_GRID'
m_sc = materiale("V_scacchi", (1, 1, 1, 1), scacchi=griglia)
assegna(ob["Saio_Gioco"], m_sc)
assegna(ob["Mantellina_Gioco"], m_sc)
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = True
sh.shadow_intensity = 0.3
sh.show_cavity = False
sh.show_specular_highlight = False
sh.show_backface_culling = False
sc.world.color = (0.80, 0.80, 0.79)
sc.display.render_aa = '16'
visibili(GIOCO)
for v in ("fronte", "fianco", "retro"):
    orto(v)
    render("scacchi_" + v, (700, 1100))

# ---------------------------------------------------------------------------
# 2) normal map: senza / con / drappeggio alto (Cycles, luce radente)
# ---------------------------------------------------------------------------
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 48
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
assegna(C, materiale("V_pelle_c", PELLE_C))
m_saio_liscio = materiale("V_saio_liscio", SAIO_C)
m_mant_liscio = materiale("V_mant_liscio", MANT_C)
m_saio_nm = materiale("V_saio_nm", SAIO_C, normal_map=True)
m_mant_nm = materiale("V_mant_nm", MANT_C, normal_map=True)
assegna(ob["Saio_Drappeggio"], m_saio_liscio)
assegna(ob["Mantellina_Drappeggio"], m_mant_liscio)
VISTE_NM = {
    "vita": (((0.95, -1.75, 1.22), (0.0, -0.02, 1.08), 55), (math.radians(70), 0, math.radians(-40))),
    "cappuccio": (((-1.15, 1.55, 1.72), (-0.04, 0.04, 1.40), 70), (math.radians(60), 0, math.radians(150))),
}
for nome, ((loc, mira, lente), rot_sole) in VISTE_NM.items():
    sole.rotation_euler = rot_sole
    prospettiva(loc, mira, lente)
    for variante, gruppo, mats in (("senza", GIOCO, (m_saio_liscio, m_mant_liscio)),
                                   ("con", GIOCO, (m_saio_nm, m_mant_nm)),
                                   ("alta", ALTO, None)):
        if mats:
            assegna(ob["Saio_Gioco"], mats[0])
            assegna(ob["Mantellina_Gioco"], mats[1])
        visibili(gruppo)
        render(f"nm_{nome}_{variante}", (900, 900))

# ---------------------------------------------------------------------------
# 3) ombre d'ambiente sul modello (la mappa come luce propria) e anteprima
# ---------------------------------------------------------------------------
m_ao = materiale("V_ombre", (1, 1, 1, 1), emissione_ao=True)
assegna(ob["Saio_Gioco"], m_ao)
assegna(ob["Mantellina_Gioco"], m_ao)
m_grigio = materiale("V_grigio", (0.25, 0.25, 0.25, 1))
assegna(C, m_grigio)
visibili(GIOCO)
sc.cycles.samples = 16
prospettiva((2.75, -4.30, 1.50), (0.0, 0.0, 0.91), 85)
render("ombre_34", (900, 900))
# spaccato: la camera "taglia" tutto quello che sta davanti al piano del corpo
# (y = 0), corpo nascosto: si vede l'interno della meta' dietro = lato rovescio (canale G)
def spaccato(nome):
    visibili([ob["Saio_Gioco"], ob["Mantellina_Gioco"]])
    orto("fronte", 1.98)
    cam_data.clip_start = 6.0
    render(nome, (900, 900))
    cam_data.clip_start = 0.1
    visibili(GIOCO)


spaccato("ombre_spaccato")
# anteprima col materiale del file (M_Lana: colori provvisori)
lana = bpy.data.materials["M_Lana"]
assegna(ob["Saio_Gioco"], lana)
assegna(ob["Mantellina_Gioco"], lana)
assegna(C, materiale("V_pelle_c2", PELLE_C))
sc.cycles.samples = 64
sole.rotation_euler = (math.radians(60), 0, math.radians(-40))
prospettiva((2.75, -4.30, 1.50), (0.0, 0.0, 0.91), 85)
render("anteprima_34", (900, 900))
print("RENDER OK ->", OUT)
