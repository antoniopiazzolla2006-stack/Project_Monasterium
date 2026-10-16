# =============================================================================
#  FASE 1 - Scena di riferimento + "guscio di prova" per il test con Unreal
#  Progetto: Abate francescano  (MetaHuman UE 5.8  ->  Blender 5.2  ->  UE 5.8)
#
#  COSA FA, IN ORDINE
#   1. Imposta le unita' della scena: metri, scala 1.0, misure mostrate in cm
#   2. Trova il corpo importato (mesh LOD0 + armatura) e cancella LOD1..LOD3
#   3. Crea REF_Corpo: copia statica del corpo, saldata, scala 1, a terra
#   4. Crea TEST_Guscio_1cm: la sola pelle "gonfiata" di 1 cm lungo le normali
#   5. Esporta il guscio in FBX con le impostazioni bloccate per Unreal
#   6. Scrive un rapporto (testo "REPORT_Fase1" + finestrella riassuntiva)
#
#  PRIMA DI LANCIARLO
#   - Hai importato l'FBX del MetaHuman (File > Import > FBX (.fbx))
#   - Hai SALVATO il file .blend (serve per sapere dove esportare)
#
#  COME SI LANCIA
#   - Workspace "Scripting" (linguetta in alto) > nel Text Editor: New
#   - Incolla tutto questo testo > pulsante Run Script (triangolo) o Alt+P
#   - Puoi rilanciarlo quante volte vuoi: ricrea gli oggetti senza duplicarli
# =============================================================================

import bpy
import bmesh
import math
import os
from mathutils import Vector

# ----------------------------- PARAMETRI -------------------------------------
OFFSET_GUSCIO_M = 0.01          # spessore del guscio di prova: 0.01 m = 1 cm
CARTELLA_EXPORT = "//Export"    # "//" = cartella del file .blend
NOME_FBX_TEST = "TEST_Guscio_1cm.fbx"
SALDATURA_M = 0.0001            # distanza per saldare i vertici doppi (0.1 mm)

COLL_ORIGINALE = "REF_Originale"   # import originale (nascosto, intatto)
COLL_REF = "REF_Corpo"             # copia statica di riferimento
COLL_TEST = "TEST"                 # oggetti di prova da esportare

report = []                        # righe del rapporto finale


def log(riga=""):
    """Scrive una riga sia nel rapporto sia nella console di sistema."""
    print(riga)
    report.append(riga)


# ----------------------------- UTILITA' --------------------------------------
def prendi_collezione(nome):
    """Restituisce la collezione 'nome', creandola sotto la Scene se manca."""
    coll = bpy.data.collections.get(nome)
    if coll is None:
        coll = bpy.data.collections.new(nome)
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    return coll


def sposta_in_collezione(obj, coll):
    """Toglie l'oggetto da tutte le collezioni e lo mette solo in 'coll'."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


def layer_collection(nome, lc=None):
    """Trova la LayerCollection (quella con occhio/freccia nell'Outliner)."""
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.name == nome:
        return lc
    for figlio in lc.children:
        trovata = layer_collection(nome, figlio)
        if trovata:
            return trovata
    return None


def materiale(nome, rgba):
    """Materiale semplice: colore in vista Solid + Base Color per l'export."""
    mat = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    mat.diffuse_color = rgba
    if mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
    return mat


def rimuovi_oggetto(nome):
    """Cancella un oggetto (e la sua mesh, se non usata da altri)."""
    obj = bpy.data.objects.get(nome)
    if obj is None:
        return
    dati = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if dati is not None and dati.users == 0 and isinstance(dati, bpy.types.Mesh):
        bpy.data.meshes.remove(dati)


def tieni_pezzo_piu_grande(bm):
    """Elimina dal BMesh tutti i pezzi staccati tranne il piu' grande (la pelle)."""
    bm.verts.ensure_lookup_table()
    visti, pezzi = set(), []
    for v in bm.verts:
        if v.index in visti:
            continue
        pila, pezzo = [v], []
        visti.add(v.index)
        while pila:
            x = pila.pop()
            pezzo.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in visti:
                    visti.add(o.index)
                    pila.append(o)
        pezzi.append(pezzo)
    pezzi.sort(key=len, reverse=True)
    da_togliere = [v for pezzo in pezzi[1:] for v in pezzo]
    bmesh.ops.delete(bm, geom=da_togliere, context='VERTS')
    return len(pezzi)


# ----------------------------- 1. UNITA' --------------------------------------
def imposta_unita():
    us = bpy.context.scene.unit_settings
    vecchia_scala = us.scale_length
    us.system = 'METRIC'
    us.scale_length = 1.0            # 1 unita' Blender = 1 metro (NON cambiarla)
    us.length_unit = 'CENTIMETERS'   # solo visualizzazione: leggi i cm di MetaHuman
    log("[1] Unita': METRIC, Unit Scale 1.0, Length = Centimeters")
    if abs(vecchia_scala - 1.0) > 1e-6:
        log(f"    ATTENZIONE: Unit Scale era {vecchia_scala}, riportata a 1.0")


# ----------------------------- 2. TROVA IL CORPO ------------------------------
def trova_corpo():
    """Cerca le mesh deformate da un'armatura e sceglie la LOD0."""
    candidati = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        arm = next((m.object for m in obj.modifiers
                    if m.type == 'ARMATURE' and m.object), None)
        if arm is None and obj.parent and obj.parent.type == 'ARMATURE':
            arm = obj.parent
        if arm is not None:
            candidati.append((obj, arm))
    if not candidati:
        return None, None, []
    lod0 = next((c for c in candidati if "LOD0" in c[0].name), None)
    if lod0 is None:  # niente nome "LOD0": prendo la mesh con piu' vertici
        lod0 = max(candidati, key=lambda c: len(c[0].data.vertices))
    altri = [c[0] for c in candidati
             if c[0] is not lod0[0] and c[1] is lod0[1] and "_LOD" in c[0].name]
    return lod0[0], lod0[1], altri


def radice(obj):
    while obj.parent:
        obj = obj.parent
    return obj


def discendenti(obj):
    out = [obj]
    for figlio in obj.children:
        out += discendenti(figlio)
    return out


# ----------------------------- 3. REF_Corpo -----------------------------------
def crea_ref_corpo(lod0):
    """Copia statica: modificatori valutati, coordinate mondo, vertici saldati."""
    rimuovi_oggetto("REF_Corpo")
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(lod0.evaluated_get(dg),
                                         preserve_all_data_layers=True,
                                         depsgraph=dg)
    me.transform(lod0.matrix_world)       # porta scala 0.01 e posizione dentro i vertici
    bm = bmesh.new()
    bm.from_mesh(me)
    n_prima = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=SALDATURA_M)
    n_dopo = len(bm.verts)
    bm.to_mesh(me)
    bm.free()
    me.name = "REF_Corpo"
    obj = bpy.data.objects.new("REF_Corpo", me)
    prendi_collezione(COLL_REF).objects.link(obj)
    me.materials.clear()
    me.materials.append(materiale("M_REF_Pelle", (0.80, 0.62, 0.52, 1.0)))
    obj.hide_select = True                # non selezionabile: non lo sposti per sbaglio
    log(f"[3] REF_Corpo creato: vertici {n_prima} -> {n_dopo} dopo la saldatura")
    return obj


# ----------------------------- 4. GUSCIO DI PROVA -----------------------------
def crea_guscio(ref):
    rimuovi_oggetto("TEST_Guscio_1cm")
    me = ref.data.copy()
    me.name = "TEST_Guscio_1cm"
    bm = bmesh.new()
    bm.from_mesh(me)
    n_pezzi = tieni_pezzo_piu_grande(bm)  # via denti, occhi, ciglia: resta la pelle
    bm.to_mesh(me)
    bm.free()
    # niente normali personalizzate ne' colori: normali lisce e pulite
    for nome_attr in ("custom_normal", "sharp_edge", "sharp_face", "Attribute"):
        attr = me.attributes.get(nome_attr)
        if attr is not None:
            me.attributes.remove(attr)
    for vc in list(me.color_attributes):
        me.color_attributes.remove(vc)
    me.shade_smooth()
    # gonfia di OFFSET_GUSCIO_M lungo la normale di ogni vertice
    for v, n in zip(me.vertices, me.vertex_normals):
        v.co += n.vector * OFFSET_GUSCIO_M
    me.update()
    me.materials.clear()
    me.materials.append(materiale("M_TEST_Verde", (0.05, 0.85, 0.15, 1.0)))
    obj = bpy.data.objects.new("TEST_Guscio_1cm", me)
    prendi_collezione(COLL_TEST).objects.link(obj)
    log(f"[4] TEST_Guscio_1cm: tenuto 1 pezzo su {n_pezzi} (solo pelle), "
        f"{len(me.vertices)} vertici, {len(me.polygons)} facce, offset {OFFSET_GUSCIO_M*100:.1f} cm")
    return obj


# ----------------------------- 5. EXPORT PER UNREAL ---------------------------
def esporta_fbx_ue(oggetti, percorso):
    """Export FBX per Unreal con impostazioni BLOCCATE (Static Mesh, metri->cm)."""
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in oggetti:
        o.select_set(True)
    bpy.context.view_layer.objects.active = oggetti[0]
    bpy.ops.export_scene.fbx(
        filepath=percorso,
        # Include
        use_selection=True, use_visible=False, use_active_collection=False,
        object_types={'MESH'}, use_custom_props=False,
        # Transform
        global_scale=1.0, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Z', axis_up='Y',
        apply_unit_scale=True, use_space_transform=True, bake_space_transform=False,
        # Geometry
        mesh_smooth_type='FACE', use_subsurf=False, use_mesh_modifiers=True,
        use_mesh_edges=False, use_triangles=False, use_tspace=False,
        colors_type='NONE',
        # Armature / Animation (non usate qui, ma fissate)
        add_leaf_bones=False, bake_anim=False,
        # Varie
        path_mode='AUTO', embed_textures=False, batch_mode='OFF',
    )


# ----------------------------- MAIN -------------------------------------------
def main():
    log("=== REPORT FASE 1 ===")
    imposta_unita()

    lod0, arm, altri_lod = trova_corpo()
    if lod0 is None and bpy.data.objects.get("REF_Corpo") is None:
        log("ERRORE: non trovo il corpo. Importa prima l'FBX (File > Import > FBX).")
        return False

    if lod0 is not None:
        # cancella LOD1..LOD3 e l'empty LodGroup: per i vestiti serve solo LOD0
        for o in altri_lod:
            rimuovi_oggetto(o.name)
        for o in list(bpy.data.objects):
            if o.type == 'EMPTY' and "LodGroup" in o.name:
                bpy.data.objects.remove(o, do_unlink=True)
        log(f"[2] Corpo trovato: mesh '{lod0.name}', armatura '{arm.name}'; "
            f"cancellati {len(altri_lod)} LOD extra")
        # sposta tutta la gerarchia originale in REF_Originale
        orig = prendi_collezione(COLL_ORIGINALE)
        for o in discendenti(radice(lod0)):
            sposta_in_collezione(o, orig)
            o.hide_select = True
        ref = crea_ref_corpo(lod0)
    else:
        ref = bpy.data.objects["REF_Corpo"]
        log("[2-3] Corpo originale gia' sistemato: riuso REF_Corpo esistente")

    # ---- controlli sul riferimento ----
    ws = [ref.matrix_world @ v.co for v in ref.data.vertices]
    mn = Vector((min(p.x for p in ws), min(p.y for p in ws), min(p.z for p in ws)))
    mx = Vector((max(p.x for p in ws), max(p.y for p in ws), max(p.z for p in ws)))
    dim = (mx - mn) * 100
    log(f"    Dimensioni REF_Corpo (cm): larghezza X {dim.x:.1f} | profondita' Y {dim.y:.1f} | altezza Z {dim.z:.1f}")
    log(f"    Piedi: z minima {mn.z*100:.2f} cm (deve essere circa 0)")
    testa = [p for p in ws if p.z > mn.z + 0.88 * (mx.z - mn.z)]
    davanti = min(p.y for p in testa)
    dietro = max(p.y for p in testa)
    guarda = "-Y (vista Front, tasto 1 del tastierino)" if abs(davanti) > abs(dietro) else "+Y (INSOLITO!)"
    log(f"    Il volto guarda verso {guarda}")
    if arm is not None and "upperarm_l" in arm.data.bones and "lowerarm_l" in arm.data.bones:
        b = arm.data.bones
        mw = arm.matrix_world
        spalla, gomito = mw @ b["upperarm_l"].head_local, mw @ b["lowerarm_l"].head_local
        d = gomito - spalla
        log(f"    A-pose: braccio a {math.degrees(math.atan2(-d.z, abs(d.x))):.0f} gradi sotto l'orizzontale")
        for nome in ("pelvis", "neck_01", "head", "calf_l", "foot_l"):
            if nome in b:
                log(f"    Altezza osso {nome:8s}: {(mw @ b[nome].head_local).z*100:6.1f} cm")
        log(f"    Osso per l'anello trovato: {'ring_01_r' in b}")

    guscio = crea_guscio(ref)

    # ---- visibilita' nell'Outliner ----
    lc = layer_collection(COLL_ORIGINALE)
    if lc:
        lc.hide_viewport = True   # occhio chiuso: l'originale resta intatto ma nascosto

    # ---- export ----
    if not bpy.data.filepath:
        log("[5] EXPORT SALTATO: salva prima il file .blend (File > Save As), poi rilancia.")
        return True
    cartella = bpy.path.abspath(CARTELLA_EXPORT)
    os.makedirs(cartella, exist_ok=True)
    percorso = os.path.join(cartella, NOME_FBX_TEST)
    esporta_fbx_ue([guscio], percorso)
    kb = os.path.getsize(percorso) / 1024
    log(f"[5] Esportato: {percorso} ({kb:.0f} KB)")
    log("    Impostazioni: Selected Objects, Mesh, Apply Scalings = FBX Units Scale,")
    log("    Forward -Z / Up Y, Apply Unit ON, Smoothing = Face, Leaf Bones OFF, Animation OFF")
    return True


ok = main()

# ---- rapporto leggibile anche senza console ----
testo = bpy.data.texts.get("REPORT_Fase1") or bpy.data.texts.new("REPORT_Fase1")
testo.clear()
testo.write("\n".join(report) + "\n")
spazio = getattr(bpy.context, "space_data", None)
if spazio is not None and spazio.type == 'TEXT_EDITOR':
    spazio.text = testo           # il Text Editor ora mostra il rapporto

wm = bpy.context.window_manager
if wm.windows and not bpy.app.background:   # solo con l'interfaccia aperta
    def disegna(self, context):
        for riga in report[:14]:
            self.layout.label(text=riga)
    wm.popup_menu(disegna, title="Fase 1: fatto" if ok else "Fase 1: problema",
                  icon='INFO' if ok else 'ERROR')
