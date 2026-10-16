# =============================================================================
#  FASE 1 - Ricrea la Skeletal Mesh "Full Body" del MetaHuman (Geometry Export)
#  Equivale a: MetaHuman Creator > Export > Geometry Export > Full Body Skeletal
#  Mesh > Export Geometry, con cartella /Game/Outfits/SaioAbate/Corpo.
#  Serve come corpo di riferimento per il test e, nella Fase 6, come corpo
#  sorgente del vestito. Non modifica il personaggio MHC_Abate.
# =============================================================================
import os
import traceback
import unreal

PERSONAGGIO = "/Game/Monasterium/Monasterium/blueprints/MissionHandler/MHC_Abate"
CARTELLA = "/Game/Outfits/SaioAbate/Corpo"
righe = []


def log(msg):
    righe.append(msg)
    unreal.log_warning("[FASE1-EXPORT] " + msg)


def main():
    sub = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    ch = unreal.EditorAssetLibrary.load_asset(PERSONAGGIO)
    if ch is None:
        log("ERRORE personaggio non trovato: " + PERSONAGGIO)
        return
    sporchi_prima = set(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    aggiunto_qui = False
    if not sub.is_object_added_for_editing(ch):
        aggiunto_qui = bool(sub.try_add_object_to_edit(ch))
        log("try_add_object_to_edit -> %s" % aggiunto_qui)
    if not sub.is_object_added_for_editing(ch):
        log("ERRORE il personaggio non risulta aperto per la modifica")
        return
    unreal.EditorAssetLibrary.make_directory(CARTELLA)
    p = unreal.MetaHumanGeometryExportParams()
    p.project_path = CARTELLA
    p.head_skeletal_mesh = False
    p.body_skeletal_mesh = False
    p.full_body_skeletal_mesh = True
    p.overwrite_existing_assets = True
    unreal.MetaHumanCharacterExportBlueprintLibrary.export_geometry(ch, p)
    creati = unreal.EditorAssetLibrary.list_assets(CARTELLA, recursive=True, include_folder=False)
    for percorso in creati:
        a = unreal.EditorAssetLibrary.load_asset(percorso)
        info = "%s (%s)" % (percorso, a.get_class().get_name())
        if isinstance(a, unreal.SkeletalMesh):
            b = a.get_bounds()
            info += "  bounds min %s max %s  scheletro %s" % (b.origin - b.box_extent, b.origin + b.box_extent,
                                                              a.get_editor_property("skeleton").get_path_name())
        log("creato: " + info)
    if creati:
        unreal.EditorAssetLibrary.save_directory(CARTELLA, only_if_is_dirty=True, recursive=True)
        log("salvati gli asset in " + CARTELLA)
    else:
        log("ERRORE export eseguito ma nessun asset in " + CARTELLA)
    if aggiunto_qui:
        sub.remove_object_to_edit(ch)
        log("sessione di modifica chiusa")
    sporchi_dopo = set(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    nuovi_sporchi = sorted(sporchi_dopo - sporchi_prima)
    log("pacchetti non salvati rimasti (non toccati): %s" % (nuovi_sporchi or "nessuno"))


try:
    main()
except Exception:
    log("ECCEZIONE PYTHON:\n" + traceback.format_exc())
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "export_corpo_out.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(righe) + "\n")
