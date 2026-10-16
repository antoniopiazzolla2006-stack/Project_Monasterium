# =============================================================================
#  FASE 6 - IMPORT IN UNREAL ENGINE 5.8 (Python dell'editor)
#  Progetto: Abate francescano
#
#  COSA FA (tutto in /Game/Outfits/SaioAbate)
#   1. Importa le texture di Abate/Texture in .../Texture con le impostazioni giuste
#      (colore = sRGB; normal map = Normalmap; dati e maschere = Masks, sRGB spento).
#   2. Importa Abate/Export/SM_SaioAbate_Render.fbx e SM_SaioAbate_Fisica.fbx come
#      Static Mesh in .../Mesh (opzioni di default come vuole Epic, poi Nanite spento:
#      sono solo "sorgenti" per il Cloth Asset).
#   3. Crea il materiale M_SaioAbate_Lana (Two Sided) in .../Materiali, con:
#        colore   = T_Lana_BC x tinta (Tinta_Lana, Tinta_Risvolto con la maschera R)
#                   + polvere extra regolabile (Polvere_Extra, maschera B)
#        normali  = T_Lana_N (DirectX, si usa cosi' com'e')
#        ruvidezza= T_Lana_ORM (G)
#        ombre    = T_Lana_ORM: R sul lato dritto, B sul lato rovescio (nodo TwoSidedSign)
#      e l'istanza MI_SaioAbate_Lana, che assegna alla mesh render.
#   4. Controlla ingombro e triangoli (devono essere quelli di Blender) e scrive
#      l'esito nell'Output Log (righe gialle [FASE6]) e in Abate/Report/ue_fase6_report.txt.
#
#  NON FA (si fanno a mano, vedi GUIDA_Fase6_Unreal.md): Cloth Asset, Outfit Asset,
#  prova nel MetaHuman Creator, Body Hidden Face Map nel Wardrobe Item, assemblaggio.
#
#  COME SI LANCIA
#   Barra in basso dell'editor, campo "Cmd": scrivi
#       py "C:\Users\<tu>\Desktop\Blender\Abate\Script\fase6_import_ue.py"
#   (oppure Tools > Execute Python Script...). Serve il plugin "Python Editor
#   Script Plugin" (gia' attivo dalla Fase 1). Si puo' rilanciare: rifa' tutto.
# =============================================================================
import os
import unreal

try:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    BASE = os.path.join(os.path.expanduser("~"), "Desktop", "Blender", "Abate")
EXPORT = os.path.join(BASE, "Export")
TEXTURE = os.path.join(BASE, "Texture")
REPORT = os.path.join(BASE, "Report", "ue_fase6_report.txt")

DEST = "/Game/Outfits/SaioAbate"
D_MESH, D_TEX, D_MAT = DEST + "/Mesh", DEST + "/Texture", DEST + "/Materiali"
CORPO = DEST + "/Corpo/MHC_Abate_FullBody"          # importato nella Fase 1

TC = unreal.TextureCompressionSettings
TG = unreal.TextureGroup
TEXTURE_DA_IMPORTARE = [
    # nome,              sRGB,  compressione,     gruppo
    ("T_Lana_BC",        True,  TC.TC_DEFAULT,    TG.TEXTUREGROUP_CHARACTER),
    ("T_Lana_N",         False, TC.TC_NORMALMAP,  TG.TEXTUREGROUP_CHARACTER_NORMAL_MAP),
    ("T_Lana_ORM",       False, TC.TC_MASKS,      TG.TEXTUREGROUP_CHARACTER_SPECULAR),
    ("T_Lana_Maschere",  False, TC.TC_MASKS,      TG.TEXTUREGROUP_CHARACTER_SPECULAR),
    ("T_Corpo_Nascosto", False, TC.TC_GRAYSCALE,  TG.TEXTUREGROUP_CHARACTER),
]
# Valori misurati in Blender (rilettura degli FBX), in cm e in coordinate Unreal (Y invertita)
ATTESI = {
    "SM_SaioAbate_Render": dict(tri=7868, min=unreal.Vector(-53.85, -19.70, 9.18), max=unreal.Vector(53.85, 31.56, 160.61)),
    "SM_SaioAbate_Fisica": dict(tri=7040, min=unreal.Vector(-53.85, -19.70, 9.18), max=unreal.Vector(53.85, 31.56, 160.61)),
}
TOLL = 0.3   # cm

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
esito = {"ok": True}
righe = []


def log(msg, errore=False):
    righe.append(("ERRORE  " if errore else "        ") + msg)
    if errore:
        esito["ok"] = False
        unreal.log_error("[FASE6] " + msg)
    else:
        unreal.log_warning("[FASE6] " + msg)


def v(x):
    return "(%.2f, %.2f, %.2f)" % (x.x, x.y, x.z)


def importa(file, dest):
    task = unreal.AssetImportTask()
    task.filename = file
    task.destination_path = dest
    task.automated = True          # nessuna finestra: opzioni di default
    task.replace_existing = True
    task.save = False
    tools.import_asset_tasks([task])
    out = []
    for p in task.get_editor_property("imported_object_paths"):
        a = eal.load_asset(p)
        if a is not None:
            out.append(a)
    return out


# -----------------------------------------------------------------------------
# 1. texture
# -----------------------------------------------------------------------------
def importa_texture():
    tex = {}
    for nome, srgb, comp, gruppo in TEXTURE_DA_IMPORTARE:
        file = os.path.join(TEXTURE, nome + ".png")
        if not os.path.isfile(file):
            log("texture non trovata: " + file, errore=True)
            continue
        t = next((a for a in importa(file, D_TEX) if isinstance(a, unreal.Texture2D)), None)
        if t is None and eal.does_asset_exist(D_TEX + "/" + nome):      # alcune versioni non elencano gli import
            t = eal.load_asset(D_TEX + "/" + nome)
        if t is None:
            log("import fallito: " + nome, errore=True)
            continue
        t.set_editor_property("srgb", srgb)
        t.set_editor_property("compression_settings", comp)
        t.set_editor_property("lod_group", gruppo)
        eal.save_loaded_asset(t)
        tex[nome] = t
        log("texture %s: %dx%d, sRGB %s, %s" % (nome, t.blueprint_get_size_x(), t.blueprint_get_size_y(),
                                               srgb, str(comp).split(".")[-1]))
    return tex


# -----------------------------------------------------------------------------
# 2. mesh
# -----------------------------------------------------------------------------
def importa_mesh(nome):
    file = os.path.join(EXPORT, nome + ".fbx")
    if not os.path.isfile(file):
        log("FBX non trovato: " + file, errore=True)
        return None, []
    importati = importa(file, D_MESH)
    if not importati:                                  # alcune versioni non elencano gli import
        importati = [eal.load_asset(p) for p in eal.list_assets(D_MESH, recursive=True, include_folder=False)]
        importati = [a for a in importati if a is not None and (not isinstance(a, unreal.StaticMesh) or a.get_name() == nome)]
    sm = next((a for a in importati if isinstance(a, unreal.StaticMesh)), None)
    altri = [a for a in importati if not isinstance(a, unreal.StaticMesh)]
    if sm is None:
        if any(isinstance(a, unreal.SkeletalMesh) for a in importati):
            log(nome + " e' entrato come Skeletal Mesh: deve essere una Static Mesh", errore=True)
        else:
            log("Static Mesh non trovata dopo l'import di " + nome, errore=True)
        return None, altri
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", False)
    sm.set_editor_property("nanite_settings", ns)
    att = ATTESI[nome]
    box = sm.get_bounding_box()
    diff = max(abs(box.min.x - att["min"].x), abs(box.min.y - att["min"].y), abs(box.min.z - att["min"].z),
               abs(box.max.x - att["max"].x), abs(box.max.y - att["max"].y), abs(box.max.z - att["max"].z))
    tri = sm.get_num_triangles(0)
    log("%s (%s): ingombro min %s max %s | atteso min %s max %s | scarto %.2f cm"
        % (nome, sm.get_name(), v(box.min), v(box.max), v(att["min"]), v(att["max"]), diff), errore=diff > TOLL)
    log("%s: triangoli %d (attesi %d), sezioni di materiale %d, Nanite %s"
        % (nome, tri, att["tri"], len(sm.get_editor_property("static_materials")),
           sm.get_editor_property("nanite_settings").enabled), errore=tri != att["tri"])
    return sm, altri


# -----------------------------------------------------------------------------
# 3. materiale
# -----------------------------------------------------------------------------
def nodo(mat, classe, x, y, **prop):
    n = mel.create_material_expression(mat, classe, x, y)
    for k, val in prop.items():
        n.set_editor_property(k, val)
    return n


def crea_materiale(tex):
    nome = "M_SaioAbate_Lana"
    percorso = D_MAT + "/" + nome
    if eal.does_asset_exist(percorso):
        mat = eal.load_asset(percorso)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(nome, D_MAT, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    ST = unreal.MaterialSamplerType
    E = unreal
    bc = nodo(mat, E.MaterialExpressionTextureSampleParameter2D, -1200, -400, parameter_name="Colore",
              texture=tex["T_Lana_BC"], sampler_type=ST.SAMPLERTYPE_COLOR)
    msk = nodo(mat, E.MaterialExpressionTextureSampleParameter2D, -1200, -100, parameter_name="Maschere",
               texture=tex["T_Lana_Maschere"], sampler_type=ST.SAMPLERTYPE_MASKS)
    nrm = nodo(mat, E.MaterialExpressionTextureSampleParameter2D, -1200, 250, parameter_name="Normali",
               texture=tex["T_Lana_N"], sampler_type=ST.SAMPLERTYPE_NORMAL)
    orm = nodo(mat, E.MaterialExpressionTextureSampleParameter2D, -1200, 550, parameter_name="ORM",
               texture=tex["T_Lana_ORM"], sampler_type=ST.SAMPLERTYPE_MASKS)
    tinta = nodo(mat, E.MaterialExpressionVectorParameter, -900, -650, parameter_name="Tinta_Lana",
                 default_value=unreal.LinearColor(1, 1, 1, 1))
    tinta_r = nodo(mat, E.MaterialExpressionVectorParameter, -900, -500, parameter_name="Tinta_Risvolto",
                   default_value=unreal.LinearColor(1, 1, 1, 1))
    polv_c = nodo(mat, E.MaterialExpressionVectorParameter, -500, -650, parameter_name="Colore_Polvere",
                  default_value=unreal.LinearColor(0.25, 0.225, 0.19, 1))
    polv = nodo(mat, E.MaterialExpressionScalarParameter, -700, -150, parameter_name="Polvere_Extra",
                default_value=0.0)
    lerp_t = nodo(mat, E.MaterialExpressionLinearInterpolate, -650, -550)
    mel.connect_material_expressions(tinta, "", lerp_t, "A")
    mel.connect_material_expressions(tinta_r, "", lerp_t, "B")
    mel.connect_material_expressions(msk, "R", lerp_t, "Alpha")
    mul = nodo(mat, E.MaterialExpressionMultiply, -450, -420)
    mel.connect_material_expressions(bc, "RGB", mul, "A")
    mel.connect_material_expressions(lerp_t, "", mul, "B")
    alfa_p = nodo(mat, E.MaterialExpressionMultiply, -450, -150)
    mel.connect_material_expressions(msk, "B", alfa_p, "A")
    mel.connect_material_expressions(polv, "", alfa_p, "B")
    lerp_p = nodo(mat, E.MaterialExpressionLinearInterpolate, -200, -420)
    mel.connect_material_expressions(mul, "", lerp_p, "A")
    mel.connect_material_expressions(polv_c, "", lerp_p, "B")
    mel.connect_material_expressions(alfa_p, "", lerp_p, "Alpha")
    mel.connect_material_property(lerp_p, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nrm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(orm, "G", unreal.MaterialProperty.MP_ROUGHNESS)
    spec = nodo(mat, E.MaterialExpressionScalarParameter, -200, 350, parameter_name="Specular", default_value=0.35)
    mel.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    # ombre: +1 sul lato dritto, -1 sul rovescio -> 1 / 0 -> R oppure B
    lato = nodo(mat, E.MaterialExpressionTwoSidedSign, -900, 800)
    zero_uno = nodo(mat, E.MaterialExpressionConstantBiasScale, -700, 800, bias=1.0, scale=0.5)
    mel.connect_material_expressions(lato, "", zero_uno, "")
    lerp_ao = nodo(mat, E.MaterialExpressionLinearInterpolate, -450, 650)
    mel.connect_material_expressions(orm, "B", lerp_ao, "A")
    mel.connect_material_expressions(orm, "R", lerp_ao, "B")
    mel.connect_material_expressions(zero_uno, "", lerp_ao, "Alpha")
    mel.connect_material_property(lerp_ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat)
    # istanza
    nome_i = "MI_SaioAbate_Lana"
    percorso_i = D_MAT + "/" + nome_i
    if eal.does_asset_exist(percorso_i):
        mi = eal.load_asset(percorso_i)
    else:
        mi = tools.create_asset(nome_i, D_MAT, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, mat)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    log("materiale %s (Two Sided) e istanza %s creati" % (mat.get_path_name(), mi.get_path_name()))
    return mat, mi


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
def main():
    log("=== FASE 6: import in Unreal === cartella Abate: " + BASE)
    try:
        substrate = unreal.SystemLibrary.get_console_variable_int_value("r.Substrate")
        log("Substrate nel progetto: %s (i materiali 'classici' come questo vengono convertiti da Unreal)"
            % ("attivo" if substrate else "spento"))
    except Exception:
        pass
    tex = importa_texture()
    if len(tex) < len(TEXTURE_DA_IMPORTARE):
        log("mancano texture: mi fermo", errore=True)
        return
    render, extra_r = importa_mesh("SM_SaioAbate_Render")
    fisica, extra_f = importa_mesh("SM_SaioAbate_Fisica")
    mat, mi = crea_materiale(tex)
    if render is not None:
        render.set_material(0, mi)
        eal.save_loaded_asset(render)
        log("SM_SaioAbate_Render: materiale 0 = " + mi.get_name())
        # il materiale creato in automatico dall'FBX (M_Lana) non serve piu'
        for a in extra_r:
            if isinstance(a, unreal.MaterialInterface):
                p = a.get_path_name().split(".")[0]
                ref = eal.find_package_referencers_for_asset(p, False)
                if not ref:
                    eal.delete_asset(p)
                    log("tolto il materiale automatico " + p + " (non usato)")
    if fisica is not None:
        eal.save_loaded_asset(fisica)
        log("SM_SaioAbate_Fisica: importata per la Fase 9 (per ora NON va nel Cloth Asset)")
    if eal.does_asset_exist(CORPO):
        log("corpo per i pesi e per l'Outfit: " + CORPO)
    else:
        log("non trovo " + CORPO + ": nel Cloth Asset e nell'Outfit usa il corpo esportato nella Fase 1", errore=True)
    eal.save_directory(DEST, only_if_is_dirty=True, recursive=True)
    log("PROSSIMI PASSI (a mano): Cloth Asset CA_SaioAbate, Outfit Asset OA_SaioAbate, prova nel MetaHuman Creator "
        "-> vedi GUIDA_Fase6_Unreal.md")


main()
log("ESITO: " + ("SUPERATO" if esito["ok"] else "CONTROLLA LE RIGHE ERRORE"))
try:
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(righe) + "\n")
except Exception as e:
    unreal.log_warning("[FASE6] report non scritto: %s" % e)
