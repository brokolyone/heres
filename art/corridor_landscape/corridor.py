"""Corridor architecture for the corridor-landscape scene (Blender / bpy 5.3).

build() ADDS the glazed corridor (curtain wall, floor, suspended ceiling with
fixtures, right wall with doors/pilasters, end walls, exterior slab/fascia) to
the current scene, in collection "Corridor".  No sky / terrain / camera / sun.

All geometry is real modelled mesh, all materials are procedural node trees.
"""
import math
import os
import sys

import bpy
import bmesh

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import common as C  # noqa: E402

COLLECTION = "Corridor"
P = "Cor_"  # name prefix for every object / mesh / material of this module

# ---------------------------------------------------------------------------
# dimensions (metres)
# ---------------------------------------------------------------------------
GX = C.GLASS_X
RW = C.RIGHT_WALL_X
Y0 = C.CORRIDOR_Y_MIN
Y1 = C.CORRIDOR_Y_MAX
CZ = C.CEILING_Z
FZ = C.FLOOR_Z
PITCH = C.MULLION_PITCH

LOBBY_LEN = 4.0                 # bright lobby behind the end wall
YE = Y1 + LOBBY_LEN + 0.2       # outer Y end of the building
YS = Y0 - 0.2                   # outer Y start of the building
ROOF_Z0, ROOF_Z1 = CZ + 0.40, CZ + 0.65

MULL_W = 0.075                  # mullion width (along Y)
MULL_D_IN = 0.19                # interior depth from the glass plane
CAP_X0, CAP_X1 = -0.036, -0.016  # exterior pressure plate / cap (rel. to GX)
TUBE_X0 = 0.016                 # interior tube starts here (rel. to GX)
LITE_OFF = 0.008                # the two lites of the IGU sit at GX +- this
KERB_H = 0.15
KERB_D = 0.20
RAIL_H = 0.06                   # bottom rail / transom height
RAIL_D = 0.10                   # interior depth of rails
TRANSOM_Z = 2.42                # centre height of the transom
HEAD_Z = 2.66                   # underside of head rail / blind box
BLIND_D = 0.20                  # blind box interior depth -> ceiling starts there

TILE = 0.6
TBAR_W = 0.015
TILE_DROP = 0.006               # tegular tile face hangs below the grid
CEIL_X0 = GX + BLIND_D          # ceiling zone: 5 tiles of 600 up to the right wall
N_TILE_X = int(round((RW - CEIL_X0) / TILE))
N_TILE_Y = int(round((Y1 - Y0) / TILE))

DOOR_W, DOOR_H, DOOR_RECESS = 1.0, 2.1, 0.10
DOOR_YS = [-4.0, 12.0, 28.0, 44.0, 60.0]
PILASTER_YS = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0, 48.0, 56.0, 64.0]
PIL_W, PIL_D = 0.50, 0.15
SKIRT_H, SKIRT_T = 0.10, 0.012

END_DOOR_W, END_DOOR_H = 1.8, 2.2


# ---------------------------------------------------------------------------
# small node helper
# ---------------------------------------------------------------------------
class NT:
    def __init__(self, name):
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name)
        if mat.node_tree is None or len(mat.node_tree.nodes) == 0:
            mat.use_nodes = True
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new("ShaderNodeOutputMaterial")

    def node(self, idname, props=None, ins=None):
        n = self.nt.nodes.new(idname)
        for k, v in (props or {}).items():
            setattr(n, k, v)
        for k, v in (ins or {}).items():
            sock = n.inputs[k]
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, sock)
            else:
                sock.default_value = v
        return n

    def math(self, op, a, b=None, clamp=False):
        ins = {0: a}
        if b is not None:
            ins[1] = b
        n = self.node("ShaderNodeMath", {"operation": op, "use_clamp": clamp}, ins)
        return n.outputs[0]

    def mixcol(self, fac, a, b, blend="MIX"):
        n = self.node("ShaderNodeMix", {"data_type": "RGBA", "blend_type": blend})
        for key, v in (("Factor_Float", fac), ("A_Color", a), ("B_Color", b)):
            sock = next(s for s in n.inputs if s.identifier == key)
            if isinstance(v, bpy.types.NodeSocket):
                self.nt.links.new(v, sock)
            else:
                sock.default_value = v
        return next(s for s in n.outputs if s.identifier == "Result_Color")

    def ramp(self, fac, stops, interp="LINEAR"):
        n = self.node("ShaderNodeValToRGB", ins={"Fac": fac})
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = col if len(col) == 4 else (col[0], col[1], col[2], 1.0)
        return n.outputs["Color"]

    def noise(self, vec, scale, detail=2.0, rough=0.5, stretch=None):
        if stretch is not None:
            vec = self.node("ShaderNodeMapping", ins={"Vector": vec, "Scale": stretch}).outputs[0]
        n = self.node("ShaderNodeTexNoise", ins={"Vector": vec, "Scale": scale,
                                                 "Detail": detail, "Roughness": rough})
        return n.outputs[0]

    def bump(self, height, distance, strength=1.0, normal=None):
        ins = {"Height": height, "Distance": distance, "Strength": strength}
        if normal is not None:
            ins["Normal"] = normal
        return self.node("ShaderNodeBump", ins=ins).outputs[0]

    def principled(self, **ins):
        n = self.node("ShaderNodeBsdfPrincipled", ins={k.replace("_", " "): v for k, v in ins.items()})
        return n

    def finish(self, shader_socket):
        self.nt.links.new(shader_socket, self.out.inputs["Surface"])
        return self.mat

    def position(self):
        return self.node("ShaderNodeNewGeometry").outputs["Position"]


def rgba(r, g, b):
    return (r, g, b, 1.0)


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------
def mat_simple(name, color, rough, metallic=0.0, coat=0.0, **extra):
    t = NT(name)
    p = t.principled(Base_Color=rgba(*color), Roughness=rough, Metallic=metallic,
                     Coat_Weight=coat, **extra)
    return t.finish(p.outputs[0])


def mat_powder_coat(name, color, rough=0.32):
    """Polyester powder coated aluminium: slight orange peel + roughness mottling."""
    t = NT(name)
    pos = t.position()
    n1 = t.noise(pos, 35.0, 3.0)
    r = t.math("ADD", t.math("MULTIPLY", n1, 0.10), rough - 0.05)
    peel = t.noise(pos, 900.0, 1.0)
    nrm = t.bump(peel, 0.00004, 0.6)
    p = t.principled(Base_Color=rgba(*color), Roughness=r, Metallic=0.0, IOR=1.5,
                     Coat_Weight=0.25, Coat_Roughness=0.12, Normal=nrm)
    return t.finish(p.outputs[0])


def mat_glass(name, tint=(0.935, 0.975, 0.96), f0=0.065):
    """Architectural thin glass, one zero-thickness sheet per lite.

    Transparent (tinted) + sharp glossy mixed by a hand-built, side independent
    Schlick fresnel.  f0 = 0.08 is the reflectance of a full 6 mm slab (two
    air/glass interfaces, IOR 1.52).  No refraction -> shadow / diffuse rays go
    straight through, so sun and sky light the interior without caustics noise.
    """
    t = NT(name)
    geo = t.node("ShaderNodeNewGeometry")
    dot = t.node("ShaderNodeVectorMath", {"operation": "DOT_PRODUCT"},
                 {0: geo.outputs["Normal"], 1: geo.outputs["Incoming"]}).outputs["Value"]
    c = t.math("ABSOLUTE", dot)
    one_minus = t.math("SUBTRACT", 1.0, c, clamp=True)
    p5 = t.math("POWER", one_minus, 5.0)
    fres = t.math("ADD", t.math("MULTIPLY", p5, 1.0 - f0), f0, clamp=True)
    transp = t.node("ShaderNodeBsdfTransparent", ins={"Color": rgba(*tint)})
    gloss = t.node("ShaderNodeBsdfGlossy", ins={"Color": rgba(1, 1, 1), "Roughness": 0.0})
    mix = t.node("ShaderNodeMixShader", ins={0: fres, 1: transp.outputs[0], 2: gloss.outputs[0]})
    mat = t.finish(mix.outputs[0])
    mat.use_backface_culling = False
    return mat


def mat_floor(name):
    """Polished large-format resilient floor (800x800), waxed: mirror-like coat,
    roughness clouds, traffic scuffs, micro scratches, faint joints, slight waviness."""
    t = NT(name)
    pos = t.position()
    sep = t.node("ShaderNodeSeparateXYZ", ins={0: pos})
    x, y = sep.outputs[0], sep.outputs[1]

    def joint(coord, offset, size=0.8, width=0.003):
        u = t.math("DIVIDE", t.math("SUBTRACT", coord, offset), size)
        d = t.math("ABSOLUTE", t.math("SUBTRACT", t.math("FRACT", u), 0.5))
        return t.math("GREATER_THAN", d, 0.5 - 0.5 * width / size)

    jmask = t.math("MAXIMUM", joint(x, GX), joint(y, 0.0))

    cloud = t.noise(pos, 0.9, 4.0, 0.55)                       # large polish clouds
    scuff = t.noise(pos, 3.0, 5.0, 0.65, stretch=(4.0, 0.5, 1.0))  # traffic streaks along Y
    scuff_m = t.ramp(scuff, [(0.48, (0, 0, 0)), (0.75, (1, 1, 1))])
    scratch = t.noise(pos, 140.0, 2.0, 0.6, stretch=(1.0, 0.04, 1.0))
    scratch_m = t.ramp(scratch, [(0.62, (0, 0, 0)), (0.70, (1, 1, 1))])
    fine = t.noise(pos, 60.0, 3.0, 0.6)

    col = t.mixcol(cloud, rgba(0.56, 0.63, 0.69), rgba(0.65, 0.70, 0.745))
    col = t.mixcol(t.math("MULTIPLY", fine, 0.12), col, rgba(0.70, 0.73, 0.75))
    col = t.mixcol(t.math("MULTIPLY", jmask, 0.55), col, rgba(0.20, 0.23, 0.25))

    r = t.math("ADD", 0.045, t.math("MULTIPLY", cloud, 0.05))
    r = t.math("ADD", r, t.math("MULTIPLY", scuff_m, 0.07))
    r = t.math("ADD", r, t.math("MULTIPLY", jmask, 0.30))
    coat_r = t.math("ADD", 0.008, t.math("MULTIPLY", cloud, 0.022))
    coat_r = t.math("ADD", coat_r, t.math("MULTIPLY", scuff_m, 0.035))
    coat_r = t.math("ADD", coat_r, t.math("MULTIPLY", scratch_m, 0.05))
    coat_r = t.math("ADD", coat_r, t.math("MULTIPLY", jmask, 0.25))

    wave = t.noise(pos, 1.7, 1.0, 0.4)
    n = t.bump(wave, 0.0012, 1.0)
    n = t.bump(t.math("MULTIPLY", jmask, -1.0), 0.0006, 1.0, normal=n)
    p = t.principled(Base_Color=col, Roughness=r, IOR=1.5, Normal=n, Coat_Normal=n,
                     Specular_IOR_Level=0.6, Coat_Weight=1.0, Coat_IOR=1.6,
                     Coat_Roughness=coat_r)
    return t.finish(p.outputs[0])


def mat_wall_paint(name, color=(0.86, 0.87, 0.86)):
    t = NT(name)
    pos = t.position()
    blot = t.noise(pos, 1.3, 4.0, 0.6)
    col = t.mixcol(blot, rgba(color[0] * 0.965, color[1] * 0.965, color[2] * 0.97), rgba(*color))
    peel = t.noise(pos, 450.0, 2.0, 0.6)
    roller = t.noise(pos, 14.0, 3.0, 0.5, stretch=(1.0, 1.0, 0.15))
    h = t.math("ADD", peel, t.math("MULTIPLY", roller, 2.0))
    nrm = t.bump(h, 0.00012, 1.0)
    r = t.math("ADD", 0.42, t.math("MULTIPLY", blot, 0.12))
    p = t.principled(Base_Color=col, Roughness=r, Normal=nrm)
    return t.finish(p.outputs[0])


def mat_ceiling_tile(name):
    """Mineral fibre acoustic tile: matt white, sanded grain, random fissures / pin holes."""
    t = NT(name)
    pos = t.position()
    fiss = t.noise(pos, 55.0, 4.0, 0.7, stretch=(1.0, 3.2, 1.0))
    fiss_m = t.ramp(fiss, [(0.30, (1, 1, 1)), (0.37, (0, 0, 0))])
    vor = t.node("ShaderNodeTexVoronoi", ins={"Vector": pos, "Scale": 260.0}).outputs["Distance"]
    pin_m = t.ramp(vor, [(0.10, (1, 1, 1)), (0.16, (0, 0, 0))])
    pits = t.math("MAXIMUM", fiss_m, t.math("MULTIPLY", pin_m, 0.6))
    grain = t.noise(pos, 700.0, 2.0, 0.6)
    col = t.mixcol(pits, rgba(0.86, 0.865, 0.855), rgba(0.50, 0.50, 0.49))
    h = t.math("SUBTRACT", t.math("MULTIPLY", grain, 0.25), pits)
    nrm = t.bump(h, 0.0006, 1.0)
    p = t.principled(Base_Color=col, Roughness=0.92, Normal=nrm, Specular_IOR_Level=0.3)
    return t.finish(p.outputs[0])


def mat_perforated(name):
    """White perforated steel speaker grille (object space dot pattern)."""
    t = NT(name)
    tc = t.node("ShaderNodeTexCoord").outputs["Object"]
    vor = t.node("ShaderNodeTexVoronoi", {"feature": "F1"},
                 {"Vector": tc, "Scale": 240.0, "Randomness": 0.0}).outputs["Distance"]
    hole = t.math("LESS_THAN", vor, 0.30)
    col = t.mixcol(hole, rgba(0.84, 0.84, 0.83), rgba(0.03, 0.03, 0.03))
    nrm = t.bump(t.math("MULTIPLY", hole, -1.0), 0.0006, 1.0)
    p = t.principled(Base_Color=col, Roughness=0.4, Normal=nrm)
    return t.finish(p.outputs[0])


def mat_concrete(name):
    t = NT(name)
    pos = t.position()
    n1 = t.noise(pos, 2.0, 6.0, 0.7)
    col = t.mixcol(n1, rgba(0.36, 0.36, 0.35), rgba(0.52, 0.52, 0.50))
    nrm = t.bump(t.noise(pos, 60.0, 4.0, 0.7), 0.002, 1.0)
    p = t.principled(Base_Color=col, Roughness=0.85, Normal=nrm)
    return t.finish(p.outputs[0])


def mat_emission(name, color, strength):
    t = NT(name)
    e = t.node("ShaderNodeEmission", ins={"Color": rgba(*color), "Strength": strength})
    return t.finish(e.outputs[0])


def make_materials():
    M = {}
    M["aluminium"] = mat_powder_coat(P + "Aluminium_PowderCoat_PaleBlue", (0.78, 0.86, 0.90))
    M["glass"] = mat_glass(P + "Glass_Glazing")
    M["gasket"] = mat_simple(P + "Gasket_EPDM_Black", (0.012, 0.012, 0.013), 0.65)
    M["spacer"] = mat_simple(P + "Glazing_Spacer_Black", (0.02, 0.02, 0.022), 0.45)
    M["silicone"] = mat_simple(P + "Silicone_Joint_Grey", (0.50, 0.53, 0.55), 0.35)
    M["floor"] = mat_floor(P + "Floor_Polished")
    M["skirting"] = mat_simple(P + "Skirting_Vinyl_GreyBlue", (0.40, 0.46, 0.51), 0.38)
    M["wall"] = mat_wall_paint(P + "Wall_Paint_White")
    M["ceiling_tile"] = mat_ceiling_tile(P + "Ceiling_Tile_Acoustic")
    M["tbar"] = mat_simple(P + "Ceiling_TBar_White", (0.84, 0.84, 0.83), 0.38)
    M["fixture_white"] = mat_simple(P + "Fixture_Trim_White", (0.82, 0.82, 0.81), 0.30, coat=0.2)
    M["reflector"] = mat_simple(P + "Downlight_Reflector", (0.86, 0.86, 0.86), 0.22, metallic=1.0)
    M["downlight_emit"] = mat_emission(P + "Downlight_Emission", (1.0, 0.95, 0.88), 6.0)
    M["speaker_grille"] = mat_perforated(P + "Speaker_Grille_Perforated")
    M["chrome"] = mat_simple(P + "Sprinkler_Chrome", (0.90, 0.90, 0.90), 0.12, metallic=1.0)
    M["diffuser_dark"] = mat_simple(P + "Diffuser_Plenum_Black", (0.10, 0.10, 0.10), 0.8)
    M["door_leaf"] = mat_powder_coat(P + "Door_Leaf_Laminate", (0.70, 0.74, 0.76), 0.30)
    M["door_frame"] = mat_powder_coat(P + "Door_Frame_Metal", (0.55, 0.58, 0.60), 0.30)
    M["steel"] = mat_simple(P + "Stainless_Brushed", (0.72, 0.72, 0.72), 0.28, metallic=1.0)
    M["concrete"] = mat_concrete(P + "Exterior_Concrete")
    M["roof"] = mat_simple(P + "Roof_Plenum_Dark", (0.10, 0.10, 0.10), 0.9)
    M["lobby_emit"] = mat_emission(P + "Lobby_Light_Emission", (1.0, 1.0, 1.0), 10.0)
    return M


# ---------------------------------------------------------------------------
# mesh helpers
# ---------------------------------------------------------------------------
_BOX_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def boxes_mesh(name, boxes):
    """boxes: iterable of (x0, x1, y0, y1, z0, z1[, material_index])."""
    verts, faces, mats = [], [], []
    for b in boxes:
        x0, x1, y0, y1, z0, z1 = b[:6]
        mi = b[6] if len(b) > 6 else 0
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        o = len(verts)
        verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                  (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for f in _BOX_FACES:
            faces.append(tuple(o + i for i in f))
            mats.append(mi)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set("material_index", mats)
    me.update()
    return me


def pydata_mesh(name, verts, faces, mat_indices=None, fix_normals=True, merge=0.0, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if mat_indices is not None:
        me.polygons.foreach_set("material_index", mat_indices)
    if fix_normals or merge > 0.0:
        bm = bmesh.new()
        bm.from_mesh(me)
        if merge > 0.0:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
        if fix_normals:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    if smooth:
        me.shade_smooth()
    me.update()
    return me


def lathe_data(profile, segs=32, mat=0, offset=(0.0, 0.0, 0.0)):
    """Revolve an (r, z) polyline around Z. Returns (verts, faces, mats)."""
    verts, faces = [], []
    ox, oy, oz = offset
    for r, z in profile:
        for s in range(segs):
            a = 2.0 * math.pi * s / segs
            verts.append((ox + r * math.cos(a), oy + r * math.sin(a), oz + z))
    for i in range(len(profile) - 1):
        for s in range(segs):
            s2 = (s + 1) % segs
            faces.append((i * segs + s, i * segs + s2, (i + 1) * segs + s2, (i + 1) * segs + s))
    return verts, faces, [mat] * len(faces)


def merge_data(*parts):
    verts, faces, mats = [], [], []
    for v, f, m in parts:
        o = len(verts)
        verts += v
        faces += [tuple(o + i for i in face) for face in f]
        mats += m
    return verts, faces, mats


class Builder:
    def __init__(self):
        self.col = C.get_collection(COLLECTION)
        self.objs = {}

    def obj(self, name, mesh, mats, bevel=None, bevel_segments=2, smooth=False, weighted=True):
        name = P + name
        if mesh is not None:
            mesh.name = name
            for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
                mesh.materials.append(m)
        ob = bpy.data.objects.new(name, mesh)
        self.col.objects.link(ob)
        if mesh is not None and (bevel or smooth):
            mesh.shade_smooth()
            mesh.set_sharp_from_angle(angle=math.radians(40.0))
        if bevel:
            mod = ob.modifiers.new("Bevel", "BEVEL")
            mod.width = bevel
            mod.segments = bevel_segments
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(40.0)
            mod.harden_normals = True
        self.objs[name] = ob
        return ob

    def array(self, ob, count, dy):
        mod = ob.modifiers.new("Array", "ARRAY")
        mod.use_relative_offset = False
        mod.use_constant_offset = True
        mod.constant_offset_displace = (0.0, dy, 0.0)
        mod.count = count
        return mod


# ---------------------------------------------------------------------------
# curtain wall
# ---------------------------------------------------------------------------
def mullion_ys():
    k0 = math.ceil((Y0 + 0.2) / PITCH)
    k1 = math.floor((Y1 - 0.2) / PITCH)
    return [k * PITCH for k in range(k0, k1 + 1)]


def build_curtain_wall(B, M):
    ys = mullion_ys()
    hw = MULL_W / 2.0
    rail_b0, rail_b1 = KERB_H, KERB_H + RAIL_H                      # bottom rail
    tr0, tr1 = TRANSOM_Z - RAIL_H / 2.0, TRANSOM_Z + RAIL_H / 2.0   # transom

    # --- vertical mullion (one mesh, arrayed) : tube, exterior cap, gaskets, spacer
    g = 0.004    # gasket overhang
    boxes = [
        (GX + TUBE_X0, GX + MULL_D_IN, -hw, hw, KERB_H, CZ + 0.02, 0),
        (GX + CAP_X0, GX + CAP_X1, -hw, hw, KERB_H - 0.02, CZ + 0.3, 0),
        (GX + LITE_OFF + 0.0005, GX + TUBE_X0, -hw - g, hw + g, rail_b1, HEAD_Z, 1),
        (GX + CAP_X1, GX - LITE_OFF - 0.0005, -hw - g, hw + g, rail_b1, HEAD_Z, 1),
        (GX - LITE_OFF + 0.0005, GX + LITE_OFF - 0.0005, -hw - 0.010, hw + 0.010, KERB_H, HEAD_Z + 0.02, 2),
    ]
    mull = B.obj("Mullion", boxes_mesh("m", boxes), [M["aluminium"], M["gasket"], M["spacer"]],
                 bevel=0.0025)
    mull.location = (0.0, ys[0], 0.0)
    B.array(mull, len(ys), PITCH)

    # --- horizontal members, continuous along Y
    ya, yb = Y0, Y1
    hb = []
    # kerb (aluminium clad upstand) + bottom rail + transom + head rail / blind box
    hb.append((GX - 0.03, GX + KERB_D, ya, yb, FZ - 0.02, KERB_H, 0))
    hb.append((GX + TUBE_X0, GX + RAIL_D, ya, yb, rail_b0, rail_b1, 0))
    hb.append((GX + TUBE_X0, GX + RAIL_D, ya, yb, tr0, tr1, 0))
    hb.append((GX + TUBE_X0, GX + BLIND_D, ya, yb, HEAD_Z, CZ + 0.06, 0))
    # blind box shadow-gap lip
    hb.append((GX + BLIND_D - 0.004, GX + BLIND_D + 0.012, ya, yb, CZ - 0.014, CZ + 0.02, 0))
    # exterior caps
    for z0, z1 in ((rail_b0 - 0.02, rail_b1), (tr0, tr1), (HEAD_Z, HEAD_Z + 0.07)):
        hb.append((GX + CAP_X0, GX + CAP_X1, ya, yb, z0, z1, 0))
    # gaskets above / below every rail, both sides of the IGU
    for z0, z1 in ((rail_b1, rail_b1 + g), (tr0 - g, tr0), (tr1, tr1 + g), (HEAD_Z - g, HEAD_Z)):
        hb.append((GX + LITE_OFF + 0.0005, GX + TUBE_X0, ya, yb, z0, z1, 1))
        hb.append((GX + CAP_X1, GX - LITE_OFF - 0.0005, ya, yb, z0, z1, 1))
    # IGU spacer bars (black edge band peeking past the gaskets)
    for z0, z1 in ((rail_b0, rail_b1 + 0.010), (tr0 - 0.010, tr1 + 0.010), (HEAD_Z - 0.010, HEAD_Z + 0.03)):
        hb.append((GX - LITE_OFF + 0.0005, GX + LITE_OFF - 0.0005, ya, yb, z0, z1, 2))
    # silicone beads: kerb/floor and kerb/bottom-rail
    hb.append((GX + KERB_D - 0.001, GX + KERB_D + 0.005, ya, yb, FZ, FZ + 0.006, 3))
    hb.append((GX + RAIL_D - 0.001, GX + RAIL_D + 0.004, ya, yb, KERB_H, KERB_H + 0.005, 3))
    B.obj("CurtainWall_Rails", boxes_mesh("m", hb),
          [M["aluminium"], M["gasket"], M["spacer"], M["silicone"]], bevel=0.0025)

    # --- glass: two lites per bay, lower and upper zone (zero-thickness sheets)
    edges = [Y0] + ys + [Y1]
    verts, faces = [], []
    zones = ((rail_b1 + 0.002, tr0 - 0.002), (tr1 + 0.002, HEAD_Z - 0.002))
    for i in range(len(edges) - 1):
        a, b = edges[i] + 0.006, edges[i + 1] - 0.006
        if b - a < 0.05:
            continue
        for x in (GX - LITE_OFF, GX + LITE_OFF):
            for z0, z1 in zones:
                o = len(verts)
                verts += [(x, a, z0), (x, b, z0), (x, b, z1), (x, a, z1)]
                faces.append((o, o + 1, o + 2, o + 3))      # normal +X (towards interior)
    glass = B.obj("Glass_Panes", pydata_mesh("m", verts, faces, fix_normals=False), M["glass"])
    return {"mullions": mull, "glass": glass, "mullion_y_positions": ys}


# ---------------------------------------------------------------------------
# floor, walls, shell
# ---------------------------------------------------------------------------
def build_floor(B, M):
    me = boxes_mesh("m", [(GX - 0.03, RW + 0.2, YS, YE, FZ - 0.30, FZ)])
    return B.obj("Floor", me, M["floor"])


def build_right_wall(B, M):
    t = 0.2
    wall, skirt = [], []
    doors = sorted(DOOR_YS)
    y = YS
    zb, zt = FZ - 0.3, ROOF_Z0
    for dy in doors:
        a, b = dy - DOOR_W / 2 - 0.05, dy + DOOR_W / 2 + 0.05   # rough opening incl. frame
        wall.append((RW, RW + t, y, a, zb, zt))
        skirt.append((RW - SKIRT_T, RW, max(y, Y0), a, FZ, FZ + SKIRT_H))
        wall.append((RW + DOOR_RECESS, RW + t, a, b, zb, DOOR_H + 0.05))
        wall.append((RW, RW + t, a, b, DOOR_H + 0.05, zt))
        y = b
    wall.append((RW, RW + t, y, YE, zb, zt))
    skirt.append((RW - SKIRT_T, RW, y, Y1, FZ, FZ + SKIRT_H))
    w = B.obj("Wall_Right", boxes_mesh("m", wall), M["wall"])

    pil = []
    for py in PILASTER_YS:
        pil.append((RW - PIL_D, RW + 0.01, py - PIL_W / 2, py + PIL_W / 2, FZ, CZ + 0.05))
        skirt.append((RW - PIL_D - SKIRT_T, RW, py - PIL_W / 2 - SKIRT_T, py + PIL_W / 2 + SKIRT_T,
                      FZ, FZ + SKIRT_H))
    B.obj("Pilasters", boxes_mesh("m", pil), M["wall"], bevel=0.003)

    # end walls' skirting
    skirt.append((GX + KERB_D, RW, Y0, Y0 + SKIRT_T, FZ, FZ + SKIRT_H))
    skirt.append((GX + KERB_D, -END_DOOR_W / 2 - 0.06, Y1 - SKIRT_T, Y1, FZ, FZ + SKIRT_H))
    skirt.append((END_DOOR_W / 2 + 0.06, RW, Y1 - SKIRT_T, Y1, FZ, FZ + SKIRT_H))
    B.obj("Skirting", boxes_mesh("m", skirt), M["skirting"], bevel=0.003)

    # --- door set (one mesh, linked objects)
    f = 0.045                         # frame face width
    hw = DOOR_W / 2
    x0 = RW - 0.006                   # frame stands 6 mm proud of the wall
    xl0, xl1 = RW + 0.045, RW + 0.085  # leaf
    d = [
        (x0, RW + DOOR_RECESS, -hw - f, -hw, FZ, DOOR_H + f, 0),
        (x0, RW + DOOR_RECESS, hw, hw + f, FZ, DOOR_H + f, 0),
        (x0, RW + DOOR_RECESS, -hw, hw, DOOR_H, DOOR_H + f, 0),
        (xl0, xl1, -hw + 0.003, hw - 0.003, FZ + 0.008, DOOR_H - 0.003, 1),
        (xl0 - 0.0015, xl0, -hw + 0.02, hw - 0.02, FZ + 0.02, FZ + 0.22, 2),          # kick plate
        (xl0 - 0.008, xl0, hw - 0.115, hw - 0.065, 0.93, 1.11, 2),                    # rose plate
        (xl0 - 0.050, xl0 - 0.008, hw - 0.100, hw - 0.080, 1.01, 1.03, 2),            # lever neck
        (xl0 - 0.050, xl0 - 0.032, hw - 0.215, hw - 0.080, 1.01, 1.03, 2),            # lever
        (xl0 - 0.004, xl0, -hw + 0.36, hw - 0.36, 1.60, 1.70, 3),                     # room sign
    ]
    dme = boxes_mesh("m", d)
    door_objs = []
    for i, dy in enumerate(doors):
        if i == 0:
            ob = B.obj("Door_00", dme, [M["door_frame"], M["door_leaf"], M["steel"], M["fixture_white"]],
                       bevel=0.002)
        else:
            ob = bpy.data.objects.new(P + "Door_%02d" % i, door_objs[0].data)   # linked mesh data
            B.col.objects.link(ob)
            B.objs[ob.name] = ob
            mod = ob.modifiers.new("Bevel", "BEVEL")
            mod.width, mod.segments, mod.limit_method = 0.002, 2, "ANGLE"
            mod.angle_limit = math.radians(40.0)
            mod.harden_normals = True
        ob.location = (0.0, dy, 0.0)
        door_objs.append(ob)
    return {"wall_right": w, "doors": door_objs}


def build_end_walls(B, M):
    t = 0.2
    hw = END_DOOR_W / 2
    zt = ROOF_Z0
    boxes = [
        # wall behind the camera
        (GX + 0.02, RW, Y0 - t, Y0, FZ - 0.3, zt),
        # far end wall with door opening
        (GX + 0.02, -hw - 0.05, Y1, Y1 + t, FZ - 0.3, zt),
        (hw + 0.05, RW, Y1, Y1 + t, FZ - 0.3, zt),
        (-hw - 0.05, hw + 0.05, Y1, Y1 + t, END_DOOR_H + 0.05, zt),
        # lobby: back wall and plain ceiling
        (GX + 0.02, RW, YE - t, YE, FZ - 0.3, zt),
        (GX + 0.02, RW, Y1 + t, YE - t, CZ, CZ + 0.05),
    ]
    B.obj("Walls_End", boxes_mesh("m", boxes), M["wall"])

    # glazed double door in the end wall
    f, s = 0.05, 0.07
    ya, yb = Y1 + 0.04, Y1 + 0.13
    fr = [
        (-hw - f, -hw, ya - 0.05, yb + 0.02, FZ, END_DOOR_H + f, 0),
        (hw, hw + f, ya - 0.05, yb + 0.02, FZ, END_DOOR_H + f, 0),
        (-hw - f, hw + f, ya - 0.05, yb + 0.02, END_DOOR_H, END_DOOR_H + f, 0),
    ]
    yl0, yl1 = Y1 + 0.06, Y1 + 0.10
    gv, gf = [], []
    for sx in (-1, 1):
        xa, xb = sorted((sx * 0.004, sx * (hw - 0.004)))
        fr += [
            (xa, xa + s, yl0, yl1, FZ + 0.008, END_DOOR_H - 0.004, 0),
            (xb - s, xb, yl0, yl1, FZ + 0.008, END_DOOR_H - 0.004, 0),
            (xa + s, xb - s, yl0, yl1, FZ + 0.008, FZ + 0.22, 0),
            (xa + s, xb - s, yl0, yl1, END_DOOR_H - 0.004 - s, END_DOOR_H - 0.004, 0),
        ]
        # pull handle near the meeting stile
        hx = sx * 0.04
        hx0, hx1 = sorted((hx, hx + sx * 0.025))
        fr += [(hx0, hx1, yl0 - 0.06, yl0 - 0.035, 0.85, 1.35, 1),
               (hx0, hx1, yl0 - 0.035, yl0, 0.90, 0.92, 1),
               (hx0, hx1, yl0 - 0.035, yl0, 1.28, 1.30, 1)]
        o = len(gv)
        ym = (yl0 + yl1) / 2
        gv += [(xa + s, ym, FZ + 0.22), (xb - s, ym, FZ + 0.22),
               (xb - s, ym, END_DOOR_H - 0.004 - s), (xa + s, ym, END_DOOR_H - 0.004 - s)]
        gf.append((o, o + 1, o + 2, o + 3))
    B.obj("EndDoor_Frame", boxes_mesh("m", fr), [M["door_frame"], M["steel"]], bevel=0.003)
    B.obj("EndDoor_Glass", pydata_mesh("m", gv, gf, fix_normals=False), M["glass"])

    # lobby: bright diffuse light panel on its ceiling + side window open to daylight
    lp = boxes_mesh("m", [(GX + 0.5, RW - 0.5, Y1 + 0.7, YE - 0.7, CZ - 0.012, CZ - 0.002)])
    light = B.obj("Lobby_LightPanel", lp, M["lobby_emit"])
    # lobby curtain wall: simple frame + one glass sheet
    lw = [
        (GX - 0.03, GX + KERB_D, Y1, YE, FZ - 0.02, KERB_H),
        (GX + CAP_X0, GX + 0.10, Y1, YE, HEAD_Z, CZ + 0.3),
        (GX + CAP_X0, GX + MULL_D_IN, Y1 + t / 2 - 0.04, Y1 + t / 2 + 0.04, KERB_H, CZ + 0.3),
        (GX + CAP_X0, GX + MULL_D_IN, YE - 0.2, YE, KERB_H, CZ + 0.3),
    ]
    B.obj("Lobby_Frame", boxes_mesh("m", lw), M["aluminium"], bevel=0.0025)
    gv = [(GX, Y1 + t / 2, KERB_H), (GX, YE - 0.1, KERB_H), (GX, YE - 0.1, HEAD_Z), (GX, Y1 + t / 2, HEAD_Z)]
    B.obj("Lobby_Glass", pydata_mesh("m", gv, [(0, 1, 2, 3)], fix_normals=False), M["glass"])
    return {"lobby_light": light}


def build_exterior(B, M):
    gz = C.GROUND_Z
    al = [
        # slab edge fascia below the glass and parapet fascia above the head
        (GX - 0.05, GX - 0.03, YS, YE, FZ - 0.55, KERB_H - 0.02),
        (GX - 0.05, GX + TUBE_X0, YS, YE, HEAD_Z + 0.07, ROOF_Z1 + 0.05),
        # drip flashing at the slab edge
        (GX - 0.075, GX - 0.03, YS, YE, FZ - 0.575, FZ - 0.55),
    ]
    B.obj("Exterior_Fascia", boxes_mesh("m", al), M["aluminium"], bevel=0.003)
    con = [
        # plinth wall under the slab down into the ground, and a perimeter apron
        (GX - 0.03, GX + 0.30, YS, YE, gz - 1.5, FZ - 0.55),
        (GX - 0.90, GX - 0.03, YS - 0.5, YE + 0.5, gz - 1.5, gz + 0.03),
        # gable ends
        (GX - 0.03, RW + 0.2, YS - 0.02, YS, gz - 1.5, ROOF_Z1),
        (GX - 0.03, RW + 0.2, YE, YE + 0.02, gz - 1.5, ROOF_Z1),
    ]
    B.obj("Exterior_Plinth", boxes_mesh("m", con), M["concrete"])
    roof = [(GX - 0.05, RW + 0.2, YS, YE, ROOF_Z0, ROOF_Z1)]
    B.obj("Roof_Slab", boxes_mesh("m", roof), M["roof"])


# ---------------------------------------------------------------------------
# ceiling
# ---------------------------------------------------------------------------
def tile_data(hole_r=None, n=32):
    """Tegular tile (origin: tile centre at grid level, face TILE_DROP below).
    Open-top shell; optional circular cut-out with collar."""
    hs = (TILE - TBAR_W - 0.004) / 2.0
    ch = 0.0015
    zf, zc, zt = -TILE_DROP, -TILE_DROP + ch, 0.012

    def square(h, z):
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            c, s = math.cos(a), math.sin(a)
            m = max(abs(c), abs(s))
            pts.append((h * c / m, h * s / m, z))
        return pts

    verts, faces = [], []
    rings = [square(hs - ch, zf), square(hs, zc), square(hs, zt)]
    if hole_r:
        circ = lambda z: [(hole_r * math.cos(2 * math.pi * k / n), hole_r * math.sin(2 * math.pi * k / n), z)
                          for k in range(n)]
        rings = [circ(zt), circ(zf)] + rings
    for r in rings:
        verts += r
    for i in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k))
    if not hole_r:
        faces.append(tuple(range(n)))
    return verts, faces, [0] * len(faces)


def downlight_data():
    """Recessed downlight: trim ring (0), reflector cone + can (1), emissive lens (2)."""
    z = -TILE_DROP
    trim = lathe_data([(0.076, z + 0.004), (0.078, z - 0.0005), (0.086, z - 0.0030), (0.094, z - 0.0026),
                       (0.097, z - 0.0005), (0.097, z + 0.001)], 40, 0)
    refl = lathe_data([(0.0765, z + 0.003), (0.070, z + 0.030), (0.060, z + 0.062), (0.060, z + 0.075)], 40, 1)
    lens = lathe_data([(0.060, z + 0.060), (0.0001, z + 0.060)], 40, 2)
    can = lathe_data([(0.0001, z + 0.075), (0.061, z + 0.075)], 40, 1)
    return merge_data(trim, refl, lens, can)


def speaker_data():
    """Ceiling speaker: white bezel (0) + slightly domed perforated grille (1)."""
    z = -TILE_DROP
    bezel = lathe_data([(0.118, z + 0.0005), (0.118, z - 0.004), (0.112, z - 0.007), (0.102, z - 0.007),
                        (0.099, z - 0.004)], 48, 0)
    prof = []
    for i in range(7):
        r = 0.099 * (1 - i / 6.0)
        prof.append((max(r, 0.0001), z - 0.004 - 0.004 * (1 - (r / 0.099) ** 2)))
    grille = lathe_data(prof, 48, 1)
    return merge_data(bezel, grille)


def sprinkler_data():
    """Pendent sprinkler: chrome escutcheon, body, frame arms and deflector."""
    z = -TILE_DROP
    esc = lathe_data([(0.034, z + 0.0005), (0.034, z - 0.002), (0.028, z - 0.006), (0.014, z - 0.008),
                      (0.011, z - 0.008), (0.011, z - 0.020), (0.007, z - 0.024), (0.0001, z - 0.024)], 24, 0)
    defl = lathe_data([(0.0001, z - 0.046), (0.016, z - 0.046), (0.017, z - 0.048), (0.0001, z - 0.049)], 24, 0)
    parts = [esc, defl]
    for sx in (-1, 1):
        x0, x1 = sorted((sx * 0.007, sx * 0.010))
        bme_v = [(x0, -0.002, z - 0.047), (x1, -0.002, z - 0.047), (x1, 0.002, z - 0.047), (x0, 0.002, z - 0.047),
                 (x0, -0.002, z - 0.020), (x1, -0.002, z - 0.020), (x1, 0.002, z - 0.020), (x0, 0.002, z - 0.020)]
        parts.append((bme_v, list(_BOX_FACES), [0] * 6))
    return merge_data(*parts)


def diffuser_boxes():
    """600 module slot diffuser: white frame + blades (0) over a black plenum (1)."""
    hs = (TILE - TBAR_W - 0.004) / 2.0
    z0, z1 = -TILE_DROP, 0.012
    fw = 0.03
    b = [
        (-hs, hs, -hs, -hs + fw, z0, z1, 0), (-hs, hs, hs - fw, hs, z0, z1, 0),
        (-hs, -hs + fw, -hs, hs, z0, z1, 0), (hs - fw, hs, -hs, hs, z0, z1, 0),
        (-hs + 0.005, hs - 0.005, -hs + 0.005, hs - 0.005, z1 + 0.02, z1 + 0.03, 1),
    ]
    n = 9
    span = 2 * (hs - fw)
    for i in range(1, n):
        x = -hs + fw + span * i / n
        b.append((x - 0.021, x + 0.021, -hs + fw, hs - fw, z0 + 0.001, z0 + 0.004, 0))
        b.append((x - 0.0015, x + 0.0015, -hs + fw, hs - fw, z0 + 0.004, z1 + 0.02, 0))
    return b


def fixture_layout():
    """(col, row) -> kind for every non-plain tile."""
    lay = {}
    for j in range(N_TILE_Y):
        if j % 10 == 0:
            lay[(3, j)] = "diffuser"
        if j % 10 == 5:
            lay[(3, j)] = "speaker"
        if j % 4 == 1:
            lay[(2, j)] = "downlight"
        if j % 6 == 3:
            lay[(1, j)] = "sprinkler"
    return lay


def build_ceiling(B, M):
    # --- T-bar grid: main runners along Y (one mesh) + cross tees (arrayed) + wall angles
    hw = TBAR_W / 2
    runners = []
    for i in range(N_TILE_X + 1):
        x = CEIL_X0 + i * TILE
        runners.append((x - hw, x + hw, Y0, Y1, CZ, CZ + 0.0012))        # flange
        runners.append((x - 0.001, x + 0.001, Y0, Y1, CZ, CZ + 0.032))  # web
    # wall angle trims
    runners.append((RW - 0.02, RW, Y0, Y1, CZ, CZ + 0.02))
    B.obj("Ceiling_TBar_Main", boxes_mesh("m", runners), M["tbar"])
    cross = [(CEIL_X0, RW, -hw, hw, CZ, CZ + 0.0012), (CEIL_X0, RW, -0.001, 0.001, CZ, CZ + 0.028)]
    ct = B.obj("Ceiling_TBar_Cross", boxes_mesh("m", cross), M["tbar"])
    ct.location = (0.0, Y0, 0.0)
    B.array(ct, N_TILE_Y + 1, TILE)

    # --- tiles & fixtures: vertex instancing (linked mesh data, one vert per tile)
    lay = fixture_layout()
    pts = {"plain": [], "downlight": [], "speaker": [], "sprinkler": [], "diffuser": []}
    for i in range(N_TILE_X):
        for j in range(N_TILE_Y):
            p = (CEIL_X0 + (i + 0.5) * TILE, Y0 + (j + 0.5) * TILE, CZ)
            kind = lay.get((i, j))
            if kind == "downlight":
                pts["downlight"].append(p)
            elif kind == "diffuser":
                pts["diffuser"].append(p)
            else:
                pts["plain"].append(p)
                if kind:
                    pts[kind].append(p)

    def instancer(name, points, children):
        me = bpy.data.meshes.new(P + name)
        # The instancer origin sits on the first point, so the (un-instanced) child
        # originals coincide exactly with instance #0 instead of lying at the world origin.
        p0 = points[0]
        me.from_pydata([(p[0] - p0[0], p[1] - p0[1], p[2] - p0[2]) for p in points], [], [])
        ob = bpy.data.objects.new(P + name, me)
        ob.location = p0
        B.col.objects.link(ob)
        ob.instance_type = "VERTS"
        ob.show_instancer_for_render = False
        ob.show_instancer_for_viewport = False
        B.objs[ob.name] = ob
        for ch in children:
            ch.parent = ob
            ch.location = (0.0, 0.0, 0.0)
        return ob

    v, f, m = tile_data()
    tile = B.obj("CeilingTile", pydata_mesh("m", v, f, m), M["ceiling_tile"])
    v, f, m = tile_data(hole_r=0.079)
    tile_h = B.obj("CeilingTile_Cutout", pydata_mesh("m", v, f, m), M["ceiling_tile"])
    v, f, m = downlight_data()
    dl = B.obj("Downlight", pydata_mesh("m", v, f, m, merge=0.00005, smooth=True),
               [M["fixture_white"], M["reflector"], M["downlight_emit"]], smooth=True)
    v, f, m = speaker_data()
    sp = B.obj("Speaker", pydata_mesh("m", v, f, m, merge=0.00005, smooth=True),
               [M["fixture_white"], M["speaker_grille"]], smooth=True)
    v, f, m = sprinkler_data()
    sk = B.obj("Sprinkler", pydata_mesh("m", v, f, m, merge=0.00005, smooth=True), M["chrome"], smooth=True)
    df = B.obj("Diffuser", boxes_mesh("m", diffuser_boxes()), [M["fixture_white"], M["diffuser_dark"]])

    inst = {
        "tiles": instancer("Inst_CeilingTiles", pts["plain"], [tile]),
        "downlights": instancer("Inst_Downlights", pts["downlight"], [tile_h, dl]),
        "speakers": instancer("Inst_Speakers", pts["speaker"], [sp]),
        "sprinklers": instancer("Inst_Sprinklers", pts["sprinkler"], [sk]),
        "diffusers": instancer("Inst_Diffusers", pts["diffuser"], [df]),
    }
    return {"instancers": inst, "counts": {k: len(v) for k, v in pts.items()}}


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def build():
    """Add the corridor to the current scene. Returns a dict describing it."""
    B = Builder()
    M = make_materials()
    cw = build_curtain_wall(B, M)
    floor = build_floor(B, M)
    rw = build_right_wall(B, M)
    ends = build_end_walls(B, M)
    build_exterior(B, M)
    ceil = build_ceiling(B, M)
    return {
        "collection": B.col,
        "objects": dict(B.objs),
        "materials": M,
        "floor": floor,
        "glass": cw["glass"],
        "mullions": cw["mullions"],
        "mullion_y_positions": cw["mullion_y_positions"],
        "wall_right": rw["wall_right"],
        "doors": rw["doors"],
        "ceiling_instancers": ceil["instancers"],
        "ceiling_counts": ceil["counts"],
        "emissive_materials": {"downlight": M["downlight_emit"], "lobby": M["lobby_emit"]},
        "lobby_light": ends["lobby_light"],
        "notes": {
            "glass_material": M["glass"].name,
            "min_transparent_bounces": 8,
            "ceiling_x_range": (CEIL_X0, RW),
            "building_y_range": (YS, YE),
            "roof_z": ROOF_Z1,
        },
    }


if __name__ == "__main__":
    build()
