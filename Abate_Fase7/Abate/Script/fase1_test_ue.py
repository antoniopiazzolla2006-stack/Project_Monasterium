# =============================================================================
#  FASE 1 - Test di andata e ritorno in Unreal Engine 5.8 (Python dell'editor) - v4
#
#  COSA FA
#   1. Importa Export/TEST_Guscio_1cm.fbx in /Game/_Test_Abate (opzioni default)
#   2. Controlla che sia una Static Mesh e confronta il suo ingombro con quello
#      misurato in Blender (in cm, asse Y invertito come fa Unreal)
#   3. Trova la Skeletal Mesh del corpo (nome con "MHC_Abate_FullBody")
#   4. Se il livello aperto NON ha modifiche non salvate: crea il livello di
#      prova /Game/_Test_Abate/L_Test_Fase1 e mette corpo e guscio in 0,0,0
#   5. Scrive l'esito nell'Output Log (righe gialle che iniziano con [FASE1])
#
#  COME SI LANCIA
#   Barra in basso dell'editor, campo "Cmd": scrivi  py "percorso\ue_fase1_test.py"
#   (oppure Tools > Execute Python Script...). Serve il plugin
#   "Python Editor Script Plugin" attivo.
# =============================================================================
import os
import unreal

# --- percorsi: lo script sta in <Abate>/Script, l'FBX in <Abate>/Export --------
try:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:  # eseguito con exec(): uso la posizione standard
    BASE = os.path.join(os.path.expanduser("~"), "Desktop", "Blender", "Abate")
FBX = os.path.join(BASE, "Export", "TEST_Guscio_1cm.fbx")
DEST = "/Game/_Test_Abate"
LIVELLO = DEST + "/L_Test_Fase1"
TEMPLATE_BASIC = "/Engine/Maps/Templates/Template_Default"

# Ingombri misurati in Blender (cm), convertiti in coordinate Unreal (Y invertita)
GUSCIO_MIN = unreal.Vector(-58.31, -13.38, -1.26)
GUSCIO_MAX = unreal.Vector(58.31, 28.36, 183.01)
CORPO_MIN = unreal.Vector(-57.32, -12.38, -0.26)
CORPO_MAX = unreal.Vector(57.32, 27.37, 182.01)
TOLL = 0.3  # cm di tolleranza

esito = {"ok": True}
righe = []
REPORT = os.path.join(BASE, "Script", "ue_fase1_report.txt")


def log(msg, errore=False):
    righe.append(("ERRORE  " if errore else "        ") + msg)
    if errore:
        esito["ok"] = False
        unreal.log_error("[FASE1] " + msg)
    else:
        unreal.log_warning("[FASE1] " + msg)


def v(vec):
    return "(%.2f, %.2f, %.2f)" % (vec.x, vec.y, vec.z)


def confronta(nome, mn, mx, att_mn, att_mx):
    diff = max(abs(mn.x - att_mn.x), abs(mn.y - att_mn.y), abs(mn.z - att_mn.z),
               abs(mx.x - att_mx.x), abs(mx.y - att_mx.y), abs(mx.z - att_mx.z))
    log("%s ingombro min %s max %s | atteso min %s max %s | scarto max %.2f cm"
        % (nome, v(mn), v(mx), v(att_mn), v(att_mx), diff), errore=diff > TOLL)
    return diff


def main():
    log("=== TEST FASE 1 === FBX: " + FBX)
    if not os.path.isfile(FBX):
        log("FBX non trovato: " + FBX, errore=True)
        return

    # --- 1. import ---------------------------------------------------------------
    task = unreal.AssetImportTask()
    task.filename = FBX
    task.destination_path = DEST
    task.automated = True          # nessuna finestra: opzioni di default
    task.replace_existing = True
    task.save = False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    unreal.EditorAssetLibrary.save_directory(DEST, only_if_is_dirty=True, recursive=True)

    guscio = None
    for percorso in unreal.EditorAssetLibrary.list_assets(DEST, recursive=True, include_folder=False):
        asset = unreal.EditorAssetLibrary.load_asset(percorso)
        log("asset in %s: %s (%s)" % (DEST, asset.get_name(), asset.get_class().get_name()))
        if isinstance(asset, unreal.StaticMesh) and asset.get_name().startswith("TEST_Guscio"):
            guscio = asset
        if isinstance(asset, unreal.SkeletalMesh):
            log("ATTENZIONE: il guscio e' entrato come Skeletal Mesh, non come Static Mesh", errore=True)

    if guscio is None:
        log("Static Mesh TEST_Guscio non trovata dopo l'import", errore=True)
        return

    # --- 2. controllo numerico del guscio -------------------------------------------
    box = guscio.get_bounding_box()
    confronta("GUSCIO", box.min, box.max, GUSCIO_MIN, GUSCIO_MAX)
    log("GUSCIO nanite=%s, triangoli mesh di riserva=%d (sorgente: 85927)"
        % (guscio.get_editor_property("nanite_settings").enabled, guscio.get_num_triangles(0)))

    # --- 3. corpo ------------------------------------------------------------------
    registro = unreal.AssetRegistryHelpers.get_asset_registry()
    candidati = []
    for dati in registro.get_assets_by_path("/Game", recursive=True):
        nome = str(dati.asset_name)
        if "abate" in nome.lower() or "/Outfits/SaioAbate" in str(dati.package_name):
            classe = str(dati.asset_class_path.asset_name)
            log("asset 'abate': %s [%s]" % (dati.package_name, classe))
            if classe == "SkeletalMesh":
                candidati.append(dati)
    corpo = None
    preferiti = [d for d in candidati if "FullBody" in str(d.asset_name) or "CombinedSkelMesh" in str(d.asset_name)]
    scelta = preferiti or (candidati if len(candidati) == 1 else [])
    if scelta:
        corpo = scelta[0].get_asset()
        log("corpo scelto: " + str(scelta[0].package_name))
    else:
        log("Skeletal Mesh del corpo non individuata (candidati: %d)" % len(candidati), errore=True)
    if corpo is not None:
        try:
            b = corpo.get_imported_bounds()
        except AttributeError:   # API non esposta: uso i bounds normali
            b = corpo.get_bounds()
        confronta("CORPO ", b.origin - b.box_extent, b.origin + b.box_extent, CORPO_MIN, CORPO_MAX)

    # --- 4. livello di prova ---------------------------------------------------------
    sporchi = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    if sporchi:
        log("Il livello aperto ha modifiche non salvate: NON creo il livello di prova "
            "(salva o chiudi il livello e rilancia). Pacchetti: "
            + ", ".join(str(p.get_name()) for p in sporchi), errore=True)
    elif corpo is not None:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        creato = False
        if unreal.EditorAssetLibrary.does_asset_exist(LIVELLO):
            creato = les.load_level(LIVELLO)
            for attore in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
                if attore.get_actor_label() in ("TEST_Corpo", "TEST_Guscio"):
                    attore.destroy_actor()
        else:
            creato = les.new_level_from_template(LIVELLO, TEMPLATE_BASIC) or les.new_level(LIVELLO)
        if not creato:
            log("Non sono riuscito a creare/aprire il livello " + LIVELLO, errore=True)
        else:
            eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            zero = unreal.Vector(0.0, 0.0, 0.0)
            nessuna = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
            a_corpo = eas.spawn_actor_from_object(corpo, zero, nessuna)
            a_guscio = eas.spawn_actor_from_object(guscio, zero, nessuna)
            a_corpo.set_actor_label("TEST_Corpo")
            a_guscio.set_actor_label("TEST_Guscio")
            for a in (a_corpo, a_guscio):
                log("%s location %s rotation %s scale %s" % (a.get_actor_label(), v(a.get_actor_location()),
                    a.get_actor_rotation(), v(a.get_actor_scale3d())))
            eas.set_selected_level_actors([a_guscio])
            # camera davanti al volto (in Unreal il personaggio guarda verso +Y)
            unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
                unreal.Vector(0.0, 330.0, 105.0), unreal.Rotator(roll=0.0, pitch=-2.0, yaw=-90.0))
            les.save_current_level()
            unreal.EditorAssetLibrary.save_directory(DEST, only_if_is_dirty=True, recursive=True)
            log("livello di prova pronto e salvato: " + LIVELLO)



import traceback
try:
    main()
except Exception:
    log("ECCEZIONE PYTHON:\n" + traceback.format_exc(), errore=True)
log("ESITO: " + ("SUPERATO - scala, assi e origine coincidono" if esito["ok"]
                  else "PROBLEMA - leggi le righe rosse qui sopra"), errore=not esito["ok"])
try:
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(righe) + "\n")
except Exception as e:
    unreal.log_error("[FASE1] impossibile scrivere il report: %s" % e)
