"""FAR_SHELL offline build in Blender 5.2 (background):
  blender -b --factory-startup --python fs_blender.py -- build <work dir> <params.json>

Inputs (work dir): world.npz (fs_extract.py: level-0 PS2 world triangles, game mm), tex/<crc>-<fnv>.png, eyes.npy
(reachable eye positions, game mm). Output: shell.npz (pieces, vertices, UVs, triangles), atlas.png, build.json.

Steps:
 1. source = the world's OP triangles (+ PT if params.pt), one material per texture (emission = texel x prelit colour,
    exactly the PVR modulate the runtime draws).
 2. visibility: rays from every reachable eye; a source face is "far-seen" when some ray hits it at a depth in
    [cut - margin, full far]. The shell is built from far-seen faces (plus a dilation ring), so interiors, backs and
    ground under the play space never take shell triangles or atlas texels.
 3. weld + global collapse decimation to the triangle budget (no per-cell cracks), then pieces = an XZ grid of cells
    (the runtime culls per piece: drawn only where some of it lies beyond the cut).
 4. UVs: smart project per piece, scaled by the texel density the piece needs (nearest far-seen distance), one pack.
 5. bake: Cycles EMIT, selected-to-active (source -> shell), into one atlas.
Coordinates: Blender (x, -z, y) / 1000 = game (x, y, z) mm.
"""
import bpy, bmesh, json, math, sys, time
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
MODE, WORK, PARAMS = argv[0], Path(argv[1]).resolve(), json.loads(Path(argv[2]).read_text())
OUT = Path(PARAMS.get("out", WORK))
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()


def log(*a):
    print("[fs %.1fs]" % (time.time() - T0), *a, flush=True)


def g2b(p):
    p = np.asarray(p, np.float64)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], -1) / 1000.0


def b2g(p):
    p = np.asarray(p, np.float64)
    return np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1) * 1000.0


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name, img_path, pt):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(img_path), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    tex.image = img
    tex.interpolation = "Linear"
    tex.extension = "REPEAT"
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "col"
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    nt.links.new(tex.outputs["Color"], mul.inputs[6])
    nt.links.new(vc.outputs["Color"], mul.inputs[7])
    nt.links.new(mul.outputs[2], em.inputs["Color"])
    if pt:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = 0.5
        nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
        nt.links.new(gt.outputs[0], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def soup_object(name, P, UV=None, C=None, mat_index=None, mats=()):
    """Triangle soup (n,3,3 Blender coords) -> mesh object (unwelded; UV / colour per corner)."""
    n = len(P)
    me = bpy.data.meshes.new(name)
    me.vertices.add(3 * n)
    me.vertices.foreach_set("co", P.reshape(-1).astype(np.float32))
    me.loops.add(3 * n)
    me.loops.foreach_set("vertex_index", np.arange(3 * n, dtype=np.int32))
    me.polygons.add(n)
    me.polygons.foreach_set("loop_start", np.arange(0, 3 * n, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(n, 3, np.int32))
    if UV is not None:
        uvl = me.uv_layers.new(name="uv")
        uv = UV.reshape(-1, 2).copy()
        uv[:, 1] = 1.0 - uv[:, 1]   # image row 0 = top (PVR v down) -> Blender v up
        uvl.data.foreach_set("uv", uv.reshape(-1).astype(np.float32))
    if C is not None:
        ca = me.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
        ca.data.foreach_set("color", C.reshape(-1).astype(np.float32))
    for m in mats:
        me.materials.append(m)
    if mat_index is not None:
        me.polygons.foreach_set("material_index", mat_index.astype(np.int32))
    me.update()
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def fib_dirs(n, lo_deg, hi_deg):
    i = np.arange(n) + 0.5
    zlo, zhi = math.sin(math.radians(lo_deg)), math.sin(math.radians(hi_deg))
    z = zlo + (zhi - zlo) * i / n
    phi = i * math.pi * (3 - math.sqrt(5))
    r = np.sqrt(1 - z * z)
    return np.stack([r * np.cos(phi), r * np.sin(phi), z], -1)


def build():
    reset()
    W = np.load(WORK / "world.npz")
    cut, full = PARAMS["cut"] / 1000.0, PARAMS["full"] / 1000.0
    passes = [0] + ([1] if PARAMS.get("pt") else [])
    sel = np.isin(W["pass_"], passes)
    if "exclude_placements" in PARAMS:
        sel &= ~np.isin(W["placement"], PARAMS["exclude_placements"])
    P = g2b(W["P"][sel])
    UV, C, keys, pas = W["UV"][sel], W["C"][sel], W["key"][sel], W["pass_"][sel]
    C = C.copy()
    C[..., 3] = 1.0
    # materials
    kp = sorted({(int(k[0]), int(k[1]), int(p)) for k, p in zip(keys, pas)})
    kidx = {k: i for i, k in enumerate(kp)}
    mats = [make_material("m%08x%08x_%d" % k, WORK / "tex" / ("%08x-%08x.png" % k[:2]), k[2] == 1) for k in kp]
    mi = np.array([kidx[(int(k[0]), int(k[1]), int(p))] for k, p in zip(keys, pas)])
    log("source tris", len(P), "materials", len(mats))
    # visibility: BVH over the source triangles
    verts = [Vector(v) for v in P.reshape(-1, 3)]
    polys = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(P))]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=True, epsilon=0.0)
    eyes = g2b(np.load(WORK / "eyes.npy"))
    if "lake" in PARAMS:   # open-water boat eyes: grid points at the water level with no opaque surface above them
        L = PARAMS["lake"]
        y = L["y"] / 1000.0
        extra = []
        for gx in np.arange(L["box"][0], L["box"][2], L["step"]) / 1000.0:
            for gz in np.arange(L["box"][1], L["box"][3], L["step"]) / 1000.0:
                o = Vector((gx, -gz, y + 100.0))
                loc, nrm, idx, dist = bvh.ray_cast(o, Vector((0, 0, -1)), 200.0)
                if idx is None or loc.z < y - 0.2:
                    extra.append((gx, -gz, y + 1.6))
        log("lake eyes", len(extra))
        eyes = np.concatenate([eyes, np.array(extra).reshape(-1, 3)])
    dirs = fib_dirs(PARAMS.get("rays", 20000), -50, 70)
    seen = np.zeros(len(P), bool)
    dmin = np.full(len(P), np.inf)
    lo_d = cut - PARAMS.get("vis_margin", 2000) / 1000.0
    for e in eyes:
        eo = Vector(e)
        for d in dirs:
            loc, nrm, idx, dist = bvh.ray_cast(eo, Vector(d), full + 1.0)
            if idx is not None and dist >= lo_d:
                seen[idx] = True
                if dist < dmin[idx]:
                    dmin[idx] = dist
    log("far-seen faces", int(seen.sum()), "of", len(P), "eyes", len(eyes))
    # source object for the bake: every OP/PT face (rays need the occluders too)
    src = soup_object("src", P, UV, C, mi, mats)
    # shell source: far-seen faces, welded, dilated
    bm = bmesh.new()
    loop_uv = PARAMS.get("uv_mode") == "loop"
    suv = bm.loops.layers.uv.new("suv") if loop_uv else None
    vv = [bm.verts.new(v) for v in P.reshape(-1, 3)]
    for i in range(len(P)):
        try:
            f = bm.faces.new((vv[3 * i], vv[3 * i + 1], vv[3 * i + 2]))
            f.tag = bool(seen[i])
            if loop_uv:   # uv_mode loop: the source UVs ride through the simplification as corner data
                f.material_index = int(mi[i])
                for k, l in enumerate(f.loops):
                    l[suv].uv = (float(UV[i, k, 0]), float(UV[i, k, 1]))
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=PARAMS.get("weld", 20) / 1000.0)
    bm.faces.ensure_lookup_table()
    for _ in range(PARAMS.get("dilate", 2)):
        grow = [f for f in bm.faces if not f.tag and any(l.tag for v in f.verts for l in v.link_faces)]
        for f in grow:
            f.tag = True
    drop = [f for f in bm.faces if not f.tag]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    me = bpy.data.meshes.new("shell")
    bm.to_mesh(me)
    bm.free()
    if loop_uv:
        for m in mats:
            me.materials.append(m)
    shell = bpy.data.objects.new("shell", me)
    bpy.context.scene.collection.objects.link(shell)
    n0 = len(me.polygons)
    budget = PARAMS["tris"]
    bpy.context.view_layer.objects.active = shell
    for o in bpy.context.scene.objects:
        o.select_set(o is shell)
    # 1. planar dissolve: coplanar runs (walls, ground plates) become single polygons (no visible change)
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(PARAMS.get("planar_deg", 4)), use_dissolve_boundaries=False,
                             verts=bm.verts, edges=bm.edges,
                             delimit={"MATERIAL", "UV"} if PARAMS.get("uv_mode") == "loop" else set())
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(shell.data)
    bm.free()
    n1 = len(shell.data.polygons)
    log("planar dissolve", n0, "->", n1)
    # 2. small loose parts (props seen as a few pixels) are dropped below min_part (mm, bounding diagonal)
    if PARAMS.get("min_part"):
        bm = bmesh.new()
        bm.from_mesh(shell.data)
        bm.faces.ensure_lookup_table()
        seenf, kill = set(), []
        for f in bm.faces:
            if f.index in seenf:
                continue
            comp, stack = [], [f]
            seenf.add(f.index)
            while stack:
                g = stack.pop()
                comp.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seenf:
                            seenf.add(h.index)
                            stack.append(h)
            co = np.array([v.co[:] for g in comp for v in g.verts])
            if np.linalg.norm(co.max(0) - co.min(0)) * 1000 < PARAMS["min_part"]:
                kill += comp
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(shell.data)
        bm.free()
        log("small parts dropped", len(kill))
    n1 = len(shell.data.polygons)
    if n1 > budget:
        mod = shell.modifiers.new("dec", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = budget / n1
        mod.use_collapse_triangulate = True
        if PARAMS.get("protect"):
            # importance weights (vertex cut, 10-16): the landmarks the shell is for (walls, cliffs, roofs: steep faces)
            # collapse last; flat ground (foreshortened and fogged at range) takes the cut. Blender's collapse adds
            # edge length x factor x (2 - w1 - w2) to the cost, so weight 0 = protected, 1 = free.
            vg = shell.vertex_groups.new(name="free")
            me_ = shell.data
            if PARAMS.get("protect_by") == "border":
                # the shell is open sheets (far-seen faces only): collapse erodes their borders first (cliffs and
                # roofs shrink into planes), so border vertices get a low weight
                bm_ = bmesh.new(); bm_.from_mesh(me_)
                wb = PARAMS.get("protect_w", 0.2)
                bv = [v.index for v in bm_.verts if v.is_boundary or not v.is_manifold]
                iv = [v.index for v in bm_.verts if not (v.is_boundary or not v.is_manifold)]
                bm_.free()
                vg.add(bv, wb, "REPLACE"); vg.add(iv, 1.0, "REPLACE")
                prot = np.zeros(len(bv), bool)
                log("border verts", len(bv), "interior", len(iv))
            elif PARAMS.get("protect_by") == "dist":
                # weight by the nearest distance the surface under the vertex is seen from beyond the cut: what is
                # seen just past the cut keeps its detail, what is only seen near the far plane takes the cut
                wlo = PARAMS.get("protect_w", 0.3)
                ds = np.where(np.isfinite(dmin), dmin, full)
                for v in me_.vertices:
                    h = bvh.find_nearest(v.co)
                    t = (min(ds[h[2]], full) - cut) / max(full - cut, 1e-3)
                    vg.add([v.index], float(wlo + (1 - wlo) * min(max(t, 0.0), 1.0) ** PARAMS.get("protect_pow", 1.0)),
                           "REPLACE")
                prot = np.zeros(1, bool)
            else:
                steep = PARAMS.get("steep_nz", 0.5)
                prot = np.zeros(len(me_.vertices), bool)
                for f in me_.polygons:
                    if abs(f.normal.z) < steep:
                        prot[list(f.vertices)] = True
                free = [i for i in range(len(prot)) if not prot[i]]
                vg.add([int(i) for i in np.nonzero(prot)[0]], PARAMS.get("protect_w", 0.0), "REPLACE")
                vg.add(free, 1.0, "REPLACE")
            mod.vertex_group = "free"
            mod.vertex_group_factor = PARAMS["protect"]
            log("protect steep verts", int(prot.sum()), "of", len(prot))
        bpy.ops.object.modifier_apply(modifier="dec")
    # drop slivers, then spikes: triangles with a corner or centre farther than max_dev from the source surface
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.01)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    dev = PARAMS.get("max_dev", 300) / 1000.0
    spikes = []
    for f in bm.faces:
        pts = [v.co for v in f.verts] + [f.calc_center_median()]
        if any(bvh.find_nearest(q)[3] > dev for q in pts):
            spikes.append(f)
    bmesh.ops.delete(bm, geom=spikes, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    log("spike triangles dropped", len(spikes))
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(shell.data)
    bm.free()
    log("shell tris", len(shell.data.polygons), "from", n0)
    # pieces: XZ grid cells by centroid (game x / z = Blender x / -y)
    cell = PARAMS.get("cell", 8000) / 1000.0
    me = shell.data
    cen = np.array([p.center[:] for p in me.polygons])
    cx = np.floor(cen[:, 0] / cell).astype(int)
    cy = np.floor(cen[:, 1] / cell).astype(int)
    keys2 = sorted(set(zip(cx.tolist(), cy.tolist())))
    pidx = {k: i for i, k in enumerate(keys2)}
    piece = np.array([pidx[k] for k in zip(cx.tolist(), cy.tolist())])
    # needed density per piece: the nearest distance it is seen from beyond the cut (from the source faces' dmin)
    srcc = P.mean(1)
    seen_c = srcc[seen]
    seen_d = dmin[seen]
    need = np.zeros(len(keys2))
    for i, (kx, ky) in enumerate(keys2):
        m = (np.floor(seen_c[:, 0] / cell) == kx) & (np.floor(seen_c[:, 1] / cell) == ky)
        d = seen_d[m].min() if m.any() else full
        need[i] = 1.0 / max(d, cut)
    if PARAMS.get("uv_mode") == "loop":
        return export_loop(shell, P, C, kp, bvh, piece, keys2, cell, need, seen, n0)
    if PARAMS.get("mode", "material") == "material":
        return export_material(shell, P, UV, C, mi, kp, bvh, piece, keys2, cell, need, seen, n0)
    # piece id as a face attribute
    pa = me.attributes.new("piece", "INT", "FACE")
    pa.data.foreach_set("value", piece.astype(np.int32))
    # UVs: box projection islands (faces grouped by dominant normal axis, split into edge-connected runs), each scaled
    # to its needed density (1 / nearest far-seen distance of its pieces), shelf-packed into the atlas.
    aw, ah = PARAMS["atlas"]
    nf = len(me.polygons)
    nrm = np.zeros(3 * nf); me.polygons.foreach_get("normal", nrm); nrm = nrm.reshape(-1, 3)
    tri = np.zeros(3 * nf, np.int64); me.polygons.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    co = np.zeros(3 * len(me.vertices)); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    ax = np.argmax(np.abs(nrm), 1)
    label = ax * 2 + (nrm[np.arange(nf), ax] < 0)
    edges = {}
    for f in range(nf):
        for k in range(3):
            e = tuple(sorted((tri[f, k], tri[f, (k + 1) % 3])))
            edges.setdefault(e, []).append(f)
    parent = np.arange(nf)
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for fs_ in edges.values():
        for i in range(1, len(fs_)):
            a_, b_ = fs_[0], fs_[i]
            if label[a_] == label[b_]:
                ra, rb = find(a_), find(b_)
                if ra != rb:
                    parent[ra] = rb
    root = np.array([find(f) for f in range(nf)])
    isl = np.unique(root, return_inverse=True)[1]
    nis = isl.max() + 1
    proj = {0: (1, 2), 1: (0, 2), 2: (0, 1)}
    uv = np.zeros((nf, 3, 2))
    for f in range(nf):
        i, j = proj[ax[f]]
        uv[f] = co[tri[f]][:, [i, j]]
    dens = np.zeros(nis)
    for f in range(nf):
        dens[isl[f]] = max(dens[isl[f]], need[piece[f]])
    rects = []
    for k in range(nis):
        m = isl == k
        q = uv[m].reshape(-1, 2) * dens[k]
        lo, hi = q.min(0), q.max(0)
        uv[m] = (uv[m] * dens[k]) - lo
        w, h = hi - lo
        rot = h > w
        if rot:
            uv[m] = uv[m][..., ::-1]
            w, h = h, w
        rects.append((k, w, h))
    margin = PARAMS.get("margin_px", 3)
    def pack(scale):
        """shelf pack at scale (atlas px per unit); returns offsets or None."""
        x = y = shelf = 0.0
        off = {}
        for k, w, h in sorted(rects, key=lambda r: -r[2]):
            W_, H_ = w * scale + 2 * margin, h * scale + 2 * margin
            if W_ > aw:
                return None
            if x + W_ > aw:
                x, y, shelf = 0.0, y + shelf, 0.0
            if y + H_ > ah:
                return None
            off[k] = (x + margin, y + margin)
            x += W_
            shelf = max(shelf, H_)
        return off
    lo_s, hi_s = 1e-3, 1e5
    for _ in range(60):
        mid = math.sqrt(lo_s * hi_s)
        if pack(mid) is None:
            hi_s = mid
        else:
            lo_s = mid
    off = pack(lo_s)
    for f in range(nf):
        ox, oy = off[isl[f]]
        uv[f] = (uv[f] * lo_s + (ox, oy)) / (aw, ah)
    used = sum(w * h for _, w, h in rects) * lo_s * lo_s / (aw * ah)
    texel_m = lo_s * need.max()
    log("islands %d atlas use %.2f texels/m at the nearest piece %.1f" % (nis, used, texel_m))
    uvl = me.uv_layers.new(name="uv")
    uvl.data.foreach_set("uv", uv.reshape(-1).astype(np.float32))
    # bake
    img = bpy.data.images.new("atlas", aw, ah, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    fill = PARAMS.get("fill", [0.35, 0.33, 0.30])
    img.pixels.foreach_set(np.tile(np.array(fill + [1.0], np.float32), aw * ah))
    bm_mat = bpy.data.materials.new("bake")
    bm_mat.use_nodes = True
    tn = bm_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tn.image = img
    bm_mat.node_tree.nodes.active = tn
    me.materials.clear()
    me.materials.append(bm_mat)
    me.polygons.foreach_set("material_index", np.zeros(nf, np.int32))
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "OPTIX"
        sc.cycles.device = "GPU"
    except Exception as e:
        log("GPU unavailable", e)
    sc.cycles.samples = PARAMS.get("bake_samples", 16)
    sc.render.bake.use_selected_to_active = True
    sc.render.bake.use_clear = False
    sc.render.bake.cage_extrusion = PARAMS.get("extrusion", 400) / 1000.0
    sc.render.bake.max_ray_distance = PARAMS.get("ray", 900) / 1000.0
    sc.render.bake.margin = PARAMS.get("bake_margin", 3)
    sc.render.bake.target = "IMAGE_TEXTURES"
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    shell.select_set(True)
    bpy.context.view_layer.objects.active = shell
    log("bake", aw, ah, "tris", nf)
    bpy.ops.object.bake(type="EMIT")
    px = np.zeros(aw * ah * 4, np.float32)
    img.pixels.foreach_get(px)
    px = np.clip(px.reshape(ah, aw, 4)[::-1, :, :3], 0, 1)
    np.save(OUT / "atlas.npy", px.astype(np.float32))
    # export the shell: per face 3 corners (game mm), UV (v down), piece id
    me = shell.data
    co = np.zeros(3 * len(me.vertices))
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    tri = np.zeros(3 * len(me.polygons), np.int64)
    me.polygons.foreach_get("vertices", tri)
    tri = tri.reshape(-1, 3)
    uv = np.zeros(2 * len(me.loops))
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 3, 2)
    uv[..., 1] = 1.0 - uv[..., 1]
    pc = np.zeros(len(me.polygons), np.int32)
    me.attributes["piece"].data.foreach_get("value", pc)
    np.savez_compressed(OUT / "shell.npz", pos=b2g(co), tri=tri, uv=uv, piece=pc,
                        cells=np.array(keys2), cell=cell * 1000.0, need=need)
    rep = dict(params=PARAMS, source_tris=int(len(P)), far_seen=int(seen.sum()), shell_source_tris=n0,
               shell_tris=int(len(tri)), shell_verts=int(len(co)), pieces=len(keys2), seconds=time.time() - T0)
    (OUT / "build.json").write_text(json.dumps(rep, indent=1))
    log("done", json.dumps(rep))


def bary(p, a, b, c):
    """barycentric coordinates of p's projection on the plane of (a, b, c), extrapolated outside the triangle."""
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
    d20, d21 = v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-18:
        return np.array([1.0, 0.0, 0.0])
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return np.array([1 - v - w, v, w])


def export_material(shell, P, UV, C, mi, kp, bvh, piece, keys2, cell, need, seen, n0):
    """Material shell: every shell triangle takes the texture of the source surface under it (majority of 4 probes),
    corner UVs extended from that source triangle's mapping (projected on its plane), corner colours (the prelit
    lighting) from the nearest source point. Same textures as the world, so no new VRAM."""
    me = shell.data
    nf = len(me.polygons)
    tri = np.zeros(3 * nf, np.int64); me.polygons.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    co = np.zeros(3 * len(me.vertices)); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    mat = np.zeros(nf, np.int32)
    cuv = np.zeros((nf, 3, 2))
    ccol = np.zeros((nf, 3, 3))
    for f in range(nf):
        q = co[tri[f]]
        c = q.mean(0)
        probes = [c] + [0.5 * (c + x) for x in q]
        hits = [bvh.find_nearest(Vector(x)) for x in probes]
        hits = [h for h in hits if h[2] is not None]
        votes = {}
        for h in hits:
            votes[mi[h[2]]] = votes.get(mi[h[2]], 0) + 1
        best = max(votes.items(), key=lambda kv: kv[1])[0]
        T = min((h for h in hits if mi[h[2]] == best), key=lambda h: h[3])[2]
        mat[f] = best
        A = P[T]
        for k in range(3):
            b = bary(q[k], A[0], A[1], A[2])
            cuv[f, k] = b @ UV[T]
            h = bvh.find_nearest(Vector(q[k]))
            t2 = h[2] if h[2] is not None else T
            b2 = np.clip(bary(np.array(h[0]) if h[0] is not None else q[k], *P[t2]), 0, 1)
            b2 /= max(b2.sum(), 1e-9)
            ccol[f, k] = b2 @ C[t2][:, :3]
    keys = np.array([kp[m] for m in mat], np.uint32)
    np.savez_compressed(OUT / "shell.npz", pos=b2g(co), tri=tri, uv=cuv, col=ccol, mat=mat, key=keys, piece=piece,
                        cells=np.array(keys2), cell=cell * 1000.0, need=need)
    rep = dict(params=PARAMS, mode="material", source_tris=int(len(P)), far_seen=int(seen.sum()),
               shell_source_tris=n0, shell_tris=int(nf), shell_verts=int(len(co)), pieces=len(keys2),
               materials=int(len(set(mat.tolist()))), groups=int(len(set(zip(piece.tolist(), mat.tolist())))),
               seconds=time.time() - T0)
    (OUT / "build.json").write_text(json.dumps(rep, indent=1))
    log("done", json.dumps(rep))


def export_loop(shell, P, C, kp, bvh, piece, keys2, cell, need, seen, n0):
    """uv_mode loop: every shell face keeps the material of the source faces it was simplified from and the corner UVs
    the collapse interpolated from the source UVs (continuous inside a source UV island, so corners are shared);
    corner colours (the prelit lighting) from the nearest source point, as export_material."""
    me = shell.data
    nf = len(me.polygons)
    tri = np.zeros(3 * nf, np.int64); me.polygons.foreach_get("vertices", tri); tri = tri.reshape(-1, 3)
    co = np.zeros(3 * len(me.vertices)); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    mat = np.zeros(nf, np.int32); me.polygons.foreach_get("material_index", mat)
    luv = np.zeros(2 * 3 * nf, np.float32); me.uv_layers["suv"].data.foreach_get("uv", luv)
    cuv = luv.reshape(nf, 3, 2).astype(float)
    ccol = np.zeros((nf, 3, 3))
    for f in range(nf):
        for k in range(3):
            h = bvh.find_nearest(Vector(co[tri[f, k]]))
            t2 = h[2]
            b2 = np.clip(bary(np.array(h[0]), *P[t2]), 0, 1)
            b2 /= max(b2.sum(), 1e-9)
            ccol[f, k] = b2 @ C[t2][:, :3]
    keys = np.array([kp[m] for m in mat], np.uint32)
    np.savez_compressed(OUT / "shell.npz", pos=b2g(co), tri=tri, uv=cuv, col=ccol, mat=mat, key=keys, piece=piece,
                        cells=np.array(keys2), cell=cell * 1000.0, need=need)
    rep = dict(params=PARAMS, mode="material", uv_mode="loop", source_tris=int(len(P)), far_seen=int(seen.sum()),
               shell_source_tris=n0, shell_tris=int(nf), shell_verts=int(len(co)), pieces=len(keys2),
               materials=int(len(set(mat.tolist()))), seconds=time.time() - T0)
    (OUT / "build.json").write_text(json.dumps(rep, indent=1))
    log("done", json.dumps(rep))


if MODE == "build":
    build()
