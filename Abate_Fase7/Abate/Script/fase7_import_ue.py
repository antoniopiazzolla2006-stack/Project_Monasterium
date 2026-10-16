# =============================================================================
#  FASE 7 - IMPORT IN UNREAL ENGINE 5.8 (Python dell'editor)
#  Progetto: Abate francescano
#
#  COSA FA (tutto in /Game/Outfits/SaioAbate)
#   1. Importa le texture degli accessori (Abate/Texture/T_Accessori_*.png) in .../Texture:
#      colore = sRGB; normal map = Normalmap; ORM = Masks (sRGB spento).
#   2. Reimporta Abate/Export/SM_SaioAbate_Render.fbx SOPRA la Static Mesh della Fase 6:
#      ora contiene saio + mantellina + accessori, con 2 materiali (M_Lana, M_Accessori).
#      Il Cloth Asset CA_SaioAbate la usa gia': va solo ricalcolato (vedi guida).
#   3. Crea il materiale M_SaioAbate_Accessori (un lato solo, Default Lit) e l'istanza
#      MI_SaioAbate_Accessori:
#        colore    = T_Accessori_BC x Tinta_Accessori
#        normali   = T_Accessori_N (DirectX, si usa cosi' com'e')
#        ombre     = ORM (R), ruvidezza = ORM (G), metallo = ORM (B: solo il ferro dell'anello)
#      Assegna: materiale 0 = MI_SaioAbate_Lana, materiale 1 = MI_SaioAbate_Accessori.
#   4. Importa Abate/Export/SKM_AnelloAbate.fbx come Skeletal Mesh sullo STESSO scheletro
#      del corpo (quello di MHC_Abate_FullBody, cioe' metahuman_base_skel) e gli assegna
#      MI_SaioAbate_Accessori.
#   5. Controlla triangoli, ingombro, materiali e scheletro (valori attesi letti da
#      Abate/Export/attesi_fase7.json, scritto da Blender) e scrive l'esito nell'Output Log
#      (righe gialle [FASE7]) e in Abate/Report/ue_fase7_report.txt.
#
#  NON FA (a mano, vedi GUIDA_Fase7_Unreal.md): ricalcolo di Cloth Asset e Outfit Asset,
#  prova nel MetaHuman Creator, anello nel guardaroba.
#
#  COME SI LANCIA
#   Barra in basso dell'editor, campo "Cmd": scrivi
#       py "C:\Users\<tu>\Desktop\Blender\Abate\Script\fase7_import_ue.py"
#   Si puo' rilanciare: rifa' tutto.
# =============================================================================
import json
import os
import unreal

try:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    BASE = os.path.join(os.path.expanduser("~"), "Desktop", "Blender", "Abate")
EXPORT = os.path.join(BASE, "Export")
TEXTURE = os.path.join(BASE, "Texture")
REPORT = os.path.join(BASE, "Report", "ue_fase7_report.txt")

DEST = "/Game/Outfits/SaioAbate"
D_MESH, D_TEX, D_MAT = DEST + "/Mesh", DEST + "/Texture", DEST + "/Materiali"
CORPO = DEST + "/Corpo/MHC_Abate_FullBody"          # importato nella Fase 1 (scheletro metahuman_base_skel)
MI_LANA = D_MAT + "/MI_SaioAbate_Lana"               # creata nella Fase 6

TC = unreal.TextureCompressionSettings
TG = unreal.TextureGroup
TEXTURE_DA_IMPORTARE = [
    # nome,              sRGB,  compressione,    gruppo
    ("T_Accessori_BC",   True,  TC.TC_DEFAULT,   TG.TEXTUREGROUP_CHARACTER),
    ("T_Accessori_N",    False, TC.TC_NORMALMAP, TG.TEXTUREGROUP_CHARACTER_NORMAL_MAP),
    ("T_Accessori_ORM",  False, TC.TC_MASKS,     TG.TEXTUREGROUP_CHARACTER_SPECULAR),
]
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
        unreal.log_error("[FASE7] " + msg)
    else:
        unreal.log_warning("[FASE7] " + msg)


def v(x):
    return "(%.2f, %.2f, %.2f)" % (x.x, x.y, x.z)


def importa(file, dest, opzioni=None):
    task = unreal.AssetImportTask()
    task.filename = file
    task.destination_path = dest
    task.automated = True          # nessuna finestra
    task.replace_existing = True
    task.save = False
    if opzioni is not None:
        task.options = opzioni
    tools.import_asset_tasks([task])
    out = []
    for p in task.get_editor_property("imported_object_paths"):
        a = eal.load_asset(p)
        if a is not None:
            out.append(a)
    return out


def leggi_attesi():
    f = os.path.join(EXPORT, "attesi_fase7.json")
    if not os.path.isfile(f):
        log("manca Export/attesi_fase7.json (lo scrive Blender): estrai di nuovo lo zip della Fase 7", errore=True)
        return None
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


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
        if t is None and eal.does_asset_exist(D_TEX + "/" + nome):
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
# 2. materiale degli accessori
# -----------------------------------------------------------------------------
def nodo(mat, classe, x, y, **prop):
    n = mel.create_material_expression(mat, classe, x, y)
    for k, val in prop.items():
        n.set_editor_property(k, val)
    return n


def crea_materiale(tex):
    nome = "M_SaioAbate_Accessori"
    percorso = D_MAT + "/" + nome
    if eal.does_asset_exist(percorso):
        mat = eal.load_asset(percorso)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(nome, D_MAT, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    ST = unreal.MaterialSamplerType
    E = unreal
    bc = nodo(mat, E.MaterialExpressionTextureSampleParameter2D, -900, -300, parameter_name="Colore",
              texture=tex["T_Accessori_BC"], sampler_type=ST.SAMPLERTYPE_COLOR)
    nrm = nodo(mat, E.MaterialExpressionTextureSampleParameter2D, -900, 100, parameter_name="Normali",
               texture=tex["T_Accessori_N"], sampler_type=ST.SAMPLERTYPE_NORMAL)
    orm = nodo(mat, E.MaterialExpressionTextureSampleParameter2D, -900, 450, parameter_name="ORM",
               texture=tex["T_Accessori_ORM"], sampler_type=ST.SAMPLERTYPE_MASKS)
    tinta = nodo(mat, E.MaterialExpressionVectorParameter, -600, -500, parameter_name="Tinta_Accessori",
                 default_value=unreal.LinearColor(1, 1, 1, 1))
    mul = nodo(mat, E.MaterialExpressionMultiply, -350, -320)
    mel.connect_material_expressions(bc, "RGB", mul, "A")
    mel.connect_material_expressions(tinta, "", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nrm, "RGB", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(orm, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(orm, "G", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(orm, "B", unreal.MaterialProperty.MP_METALLIC)
    spec = nodo(mat, E.MaterialExpressionScalarParameter, -350, 250, parameter_name="Specular", default_value=0.5)
    mel.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat)
    nome_i = "MI_SaioAbate_Accessori"
    percorso_i = D_MAT + "/" + nome_i
    if eal.does_asset_exist(percorso_i):
        mi = eal.load_asset(percorso_i)
    else:
        mi = tools.create_asset(nome_i, D_MAT, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, mat)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    log("materiale %s (un lato) e istanza %s creati" % (mat.get_path_name(), mi.get_path_name()))
    return mat, mi


def togli_materiali_automatici(importati):
    """I materiali creati in automatico dall'FBX (M_Lana, M_Accessori) non servono."""
    for a in importati:
        if isinstance(a, unreal.MaterialInterface):
            p = a.get_path_name().split(".")[0]
            if p.startswith(D_MAT + "/M_SaioAbate") or p.startswith(D_MAT + "/MI_SaioAbate"):
                continue
            if not eal.find_package_referencers_for_asset(p, False):
                eal.delete_asset(p)
                log("tolto il materiale automatico " + p + " (non usato)")


# -----------------------------------------------------------------------------
# 3. saio + accessori (reimport sopra la mesh della Fase 6)
# -----------------------------------------------------------------------------
def reimporta_render(attesi, mi_acc):
    nome = "SM_SaioAbate_Render"
    file = os.path.join(EXPORT, nome + ".fbx")
    if not os.path.isfile(file):
        log("FBX non trovato: " + file, errore=True)
        return None
    importati = importa(file, D_MESH)
    sm = next((a for a in importati if isinstance(a, unreal.StaticMesh)), None)
    if sm is None and eal.does_asset_exist(D_MESH + "/" + nome):
        sm = eal.load_asset(D_MESH + "/" + nome)
    if sm is None:
        log("Static Mesh non trovata dopo l'import di " + nome, errore=True)
        return None
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", False)
    sm.set_editor_property("nanite_settings", ns)
    att = attesi[nome]
    box = sm.get_bounding_box()
    amin, amax = unreal.Vector(*att["min"]), unreal.Vector(*att["max"])
    diff = max(abs(box.min.x - amin.x), abs(box.min.y - amin.y), abs(box.min.z - amin.z),
               abs(box.max.x - amax.x), abs(box.max.y - amax.y), abs(box.max.z - amax.z))
    log("%s: ingombro min %s max %s | atteso min %s max %s | scarto %.2f cm"
        % (nome, v(box.min), v(box.max), v(amin), v(amax), diff), errore=diff > TOLL)
    tri = sm.get_num_triangles(0)
    slots = sm.get_editor_property("static_materials")
    log("%s: triangoli %d (attesi %d: saio 7868 + accessori %d), sezioni di materiale %d (attese 2)"
        % (nome, tri, att["tri"], att["tri"] - 7868, len(slots)), errore=tri != att["tri"] or len(slots) != 2)
    # materiali per nome dello slot
    mi_lana = eal.load_asset(MI_LANA) if eal.does_asset_exist(MI_LANA) else None
    if mi_lana is None:
        log("non trovo " + MI_LANA + " (Fase 6): il saio restera' col materiale automatico", errore=True)
    for i, s in enumerate(slots):
        nome_slot = str(s.get_editor_property("material_slot_name"))
        if "Accessori" in nome_slot:
            sm.set_material(i, mi_acc)
            log("%s: materiale %d (%s) = %s" % (nome, i, nome_slot, mi_acc.get_name()))
        elif mi_lana is not None:
            sm.set_material(i, mi_lana)
            log("%s: materiale %d (%s) = %s" % (nome, i, nome_slot, mi_lana.get_name()))
    eal.save_loaded_asset(sm)
    togli_materiali_automatici(importati)
    return sm


# -----------------------------------------------------------------------------
# 4. anello (Skeletal Mesh sullo scheletro del MetaHuman)
# -----------------------------------------------------------------------------
def opzioni_scheletro(skel):
    """Opzioni di import con lo scheletro gia' esistente: prima Interchange (UE 5.8),
    poi il vecchio importatore FBX."""
    tentativi = []
    try:
        pl = unreal.InterchangeGenericAssetsPipeline()
        comuni = pl.get_editor_property("common_skeletal_meshes_and_animations_properties")
        comuni.set_editor_property("skeleton", skel)
        try:
            comuni.set_editor_property("import_only_animations", False)
        except Exception:
            pass
        try:
            pl.get_editor_property("animation_pipeline").set_editor_property("import_animations", False)
        except Exception:
            pass
        tentativi.append(("Interchange", pl))
    except Exception as e:
        log("opzioni Interchange non disponibili (%s)" % e)
    try:
        ui = unreal.FbxImportUI()
        ui.set_editor_property("import_as_skeletal", True)
        ui.set_editor_property("import_mesh", True)
        ui.set_editor_property("skeleton", skel)
        ui.set_editor_property("import_materials", False)
        ui.set_editor_property("import_textures", False)
        ui.set_editor_property("import_animations", False)
        ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
        tentativi.append(("FBX classico", ui))
    except Exception as e:
        log("opzioni FBX classiche non disponibili (%s)" % e)
    return tentativi


def importa_anello(attesi, mi_acc):
    nome = "SKM_AnelloAbate"
    file = os.path.join(EXPORT, nome + ".fbx")
    if not os.path.isfile(file):
        log("FBX non trovato: " + file, errore=True)
        return None
    corpo = eal.load_asset(CORPO) if eal.does_asset_exist(CORPO) else None
    if corpo is None:
        log("non trovo " + CORPO + " (Fase 1): mi serve per sapere lo scheletro del MetaHuman", errore=True)
        return None
    skel = corpo.get_editor_property("skeleton")
    log("scheletro del corpo: " + skel.get_path_name())
    skm = None
    for metodo, opz in opzioni_scheletro(skel):
        importati = importa(file, D_MESH, opz)
        cand = [a for a in importati if isinstance(a, unreal.SkeletalMesh)]
        if not cand:          # alcune versioni non elencano gli import
            for p in eal.list_assets(D_MESH, recursive=False, include_folder=False):
                a = eal.load_asset(p)
                if isinstance(a, unreal.SkeletalMesh) and ("Anello" in a.get_name()):
                    cand.append(a)
        for a in cand:
            if a.get_editor_property("skeleton") == skel:
                skm = a
                break
        togli_materiali_automatici(importati)
        if skm is not None:
            log("anello importato con l'importatore %s sullo scheletro del corpo" % metodo)
            break
        log("tentativo con l'importatore %s: l'anello non e' finito sullo scheletro del corpo" % metodo)
    if skm is None:
        log("anello NON importato sullo scheletro del MetaHuman: fallo a mano (GUIDA_Fase7_Unreal.md, passo 1, "
            "riquadro 'Se l'anello non si importa')", errore=True)
        return None
    if skm.get_name() != nome:
        vecchio = skm.get_path_name().split(".")[0]
        nuovo = D_MESH + "/" + nome
        if eal.does_asset_exist(nuovo) and nuovo != vecchio:
            eal.delete_asset(nuovo)
        eal.rename_asset(vecchio, nuovo)
        skm = eal.load_asset(nuovo)
    # materiale
    mats = skm.get_editor_property("materials")
    for m in mats:
        m.set_editor_property("material_interface", mi_acc)
    skm.set_editor_property("materials", mats)
    eal.save_loaded_asset(skm)
    # controlli
    att = attesi[nome]
    b = skm.get_bounds()
    cen = b.origin
    acen = unreal.Vector((att["min"][0] + att["max"][0]) / 2, (att["min"][1] + att["max"][1]) / 2,
                         (att["min"][2] + att["max"][2]) / 2)
    d = ((cen.x - acen.x) ** 2 + (cen.y - acen.y) ** 2 + (cen.z - acen.z) ** 2) ** 0.5
    log("SKM_AnelloAbate: centro %s, atteso %s (scarto %.2f cm), materiali %d, scheletro %s"
        % (v(cen), v(acen), d, len(mats), skm.get_editor_property("skeleton").get_name()), errore=d > 2.0)
    # scheletri nuovi nati dai tentativi non riusciti: non servono
    for p in eal.list_assets(D_MESH, recursive=False, include_folder=False):
        a = eal.load_asset(p)
        if isinstance(a, unreal.Skeleton) and a != skel:
            q = p.split(".")[0]
            if not eal.find_package_referencers_for_asset(q, False):
                eal.delete_asset(q)
                log("tolto lo scheletro in piu' " + q)
    return skm


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
def main():
    log("=== FASE 7: import degli accessori in Unreal === cartella Abate: " + BASE)
    attesi = leggi_attesi()
    if attesi is None:
        return
    tex = importa_texture()
    if len(tex) < len(TEXTURE_DA_IMPORTARE):
        log("mancano texture: mi fermo", errore=True)
        return
    mat, mi = crea_materiale(tex)
    reimporta_render(attesi, mi)
    importa_anello(attesi, mi)
    eal.save_directory(DEST, only_if_is_dirty=True, recursive=True)
    log("PROSSIMI PASSI (a mano): ricalcola CA_SaioAbate e OA_SaioAbate, rimetti il saio nel MetaHuman Creator, "
        "anello nel guardaroba -> vedi GUIDA_Fase7_Unreal.md")


main()
log("ESITO: " + ("SUPERATO" if esito["ok"] else "CONTROLLA LE RIGHE ERRORE"))
try:
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(righe) + "\n")
except Exception as e:
    unreal.log_warning("[FASE7] report non scritto: %s" % e)
