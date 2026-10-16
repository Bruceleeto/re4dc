"""FAR_SHELL offline preview renders (Blender 5.2, background; guidance only, NOT Flycast pictures):
  blender -b --factory-startup --python fs_preview.py -- <work dir> <preview.json>
Arms: full (world to 25 m), short (every pass and the fog cut at the cut), opcut (opaque pass cut, rest full),
shortshell (opaque cut + the shell beyond the cut, Full fog), shellonly. Per-pixel depth cut (the runtime cuts per
cluster/meshlet and z-biases the shell behind the world instead). Fog: smoothstep to 100 % over the last 20 % before
the far plus a light linear base (approximation of the room's GX curve)."""
import bpy, json, math, sys, time
from pathlib import Path
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
argv = sys.argv[sys.argv.index("--") + 1:]
WORK, PARAMS = Path(argv[0]).resolve(), json.loads(Path(argv[1]).read_text())
OUT = Path(PARAMS.get("out", WORK))
T0 = time.time()


def log(*a):
    print("[fs %.1fs]" % (time.time() - T0), *a, flush=True)


def g2b(p):
    p = np.asarray(p, np.float64)
    return np.stack([p[..., 0], -p[..., 2], p[..., 1]], -1) / 1000.0


def soup_object(name, P, UV=None, C=None, mat_index=None, mats=()):
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
        uv[:, 1] = 1.0 - uv[:, 1]
        uvl.data.foreach_set("uv", uv.reshape(-1).astype(np.float32))
    if C is not None:
        ca = me.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
        ca.data.foreach_set("color", C.reshape(-1).astype(np.float32))
    for m in mats:
        me.materials.append(m)
    if mat_index is not None:
        me.polygons.foreach_set("material_index", mat_index.astype(np.int32))
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def math_node(nt, op, a, b):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, x in enumerate((a, b)):
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def material(name, img, near_far, fogfar, fogcol, cut, pt=False, tr=False, vcol=True):
    """near_far: None (drawn to fogfar), 'near' (depth < cut), 'far' (depth >= cut)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "REPEAT"
    colr, alpha = tex.outputs["Color"], tex.outputs["Alpha"]
    if vcol:
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "col"
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0
        nt.links.new(colr, mul.inputs[6])
        nt.links.new(vc.outputs["Color"], mul.inputs[7])
        colr = mul.outputs[2]
        alpha = math_node(nt, "MULTIPLY", alpha, vc.outputs["Alpha"])
    cam = nt.nodes.new("ShaderNodeCameraData")
    z = cam.outputs["View Z Depth"]
    r1 = nt.nodes.new("ShaderNodeMapRange")
    r1.interpolation_type = "SMOOTHSTEP"
    r1.inputs[1].default_value = 0.8 * fogfar
    r1.inputs[2].default_value = fogfar
    nt.links.new(z, r1.inputs[0])
    base = math_node(nt, "MULTIPLY", math_node(nt, "MINIMUM", math_node(nt, "DIVIDE", z, 25.0), 1.0),
                     PARAMS.get("fog_base", 0.35))
    f = math_node(nt, "MAXIMUM", r1.outputs[0], base)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(f, mix.inputs[0])
    nt.links.new(colr, mix.inputs[6])
    mix.inputs[7].default_value = list(fogcol) + [1.0]
    nt.links.new(mix.outputs[2], em.inputs["Color"])
    cov = math_node(nt, "LESS_THAN", z, fogfar)
    if pt:
        cov = math_node(nt, "MULTIPLY", cov, math_node(nt, "GREATER_THAN", alpha, 0.5))
    elif tr:
        cov = math_node(nt, "MULTIPLY", cov, alpha)
    if near_far == "near":
        cov = math_node(nt, "MULTIPLY", cov, math_node(nt, "LESS_THAN", z, cut))
    elif near_far == "far":
        cov = math_node(nt, "MULTIPLY", cov, math_node(nt, "GREATER_THAN", z, cut))
    trn = nt.nodes.new("ShaderNodeBsdfTransparent")
    ms = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(cov, ms.inputs[0])
    nt.links.new(trn.outputs[0], ms.inputs[1])
    nt.links.new(em.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs["Surface"])
    return m


def main():
    W = np.load(WORK / "world.npz")
    S = np.load(OUT / "shell.npz")
    atlas = np.load(OUT / "atlas.npy") if (OUT / "atlas.npy").exists() else np.zeros((8, 8, 3), np.float32)
    cut, full = PARAMS["cut"] / 1000.0, PARAMS["full"] / 1000.0
    fogcol = PARAMS.get("fog", [0.55, 0.52, 0.45])
    ah, aw = atlas.shape[:2]
    px = np.concatenate([atlas[::-1], np.ones((ah, aw, 1), np.float32)], -1).reshape(-1)
    P, UV, C, keys, pas = g2b(W["P"]), W["UV"], W["C"], W["key"], W["pass_"]
    kp = sorted({(int(k[0]), int(k[1]), int(p)) for k, p in zip(keys, pas)})
    kidx = {k: i for i, k in enumerate(kp)}
    mi = np.array([kidx[(int(k[0]), int(k[1]), int(p))] for k, p in zip(keys, pas)])
    for arm in PARAMS.get("arms", ["full", "short", "shortshell"]):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        imgs = {}
        mats = []
        for k in kp:
            if k[:2] not in imgs:
                im = bpy.data.images.load(str(WORK / "tex" / ("%08x-%08x.png" % k[:2])), check_existing=True)
                im.colorspace_settings.name = "Non-Color"
                imgs[k[:2]] = im
            op = k[2] == 0
            if arm == "full" or arm == "shellonly":
                nf, ff = None, full
            elif arm == "short":
                nf, ff = None, cut
            else:   # opcut / shortshell: the opaque pass stops at the cut, the rest and the fog stay Full
                nf, ff = ("near" if op else None), full
            mats.append(material("w%d" % len(mats), imgs[k[:2]], nf, ff, fogcol, cut, pt=k[2] == 1, tr=k[2] == 2))
        if arm != "shellonly":
            soup_object("world", P, UV, C, mi, mats)
        if arm in ("shortshell", "shellonly"):
            if "mat" in S.files:
                sk = sorted({tuple(int(x) for x in k) for k in S["key"]})
                si = {k: i for i, k in enumerate(sk)}
                smats = [material("s%d" % i, imgs.get(k[:2]) or bpy.data.images.load(str(WORK / "tex" / ("%08x-%08x.png" % k[:2]))),
                                  "far" if arm == "shortshell" else None, full, fogcol, cut) for i, k in enumerate(sk)]
                col = np.concatenate([S["col"], np.ones(S["col"].shape[:2] + (1,))], -1)
                soup_object("shellobj", g2b(S["pos"])[S["tri"]], S["uv"], col,
                            np.array([si[tuple(int(x) for x in k)] for k in S["key"]]), smats)
            else:
                aimg = bpy.data.images.new("atlas", aw, ah, float_buffer=True)
                aimg.colorspace_settings.name = "Non-Color"
                aimg.pixels.foreach_set(px)
                sm = material("shell", aimg, "far" if arm == "shortshell" else None, full, fogcol, cut, vcol=False)
                soup_object("shellobj", g2b(S["pos"])[S["tri"]], S["uv"], None, None, [sm])
        sc.render.engine = "CYCLES"
        prefs = bpy.context.preferences.addons["cycles"].preferences
        try:
            prefs.compute_device_type = "OPTIX"
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type == "OPTIX"
            sc.cycles.device = "GPU"
        except Exception:
            pass
        sc.cycles.samples = PARAMS.get("samples", 16)
        sc.cycles.max_bounces = 0
        sc.cycles.transparent_max_bounces = 64
        sc.cycles.use_denoising = False
        sc.view_settings.view_transform = "Raw"
        sc.render.resolution_x, sc.render.resolution_y = PARAMS.get("res", [640, 360])
        wd = bpy.data.worlds.new("w")
        wd.use_nodes = True
        wd.node_tree.nodes["Background"].inputs[0].default_value = list(fogcol) + [1]
        sc.world = wd
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.sensor_fit = "VERTICAL"
        cam.data.angle = math.radians(PARAMS.get("vfov", 50))
        cam.data.clip_start = 0.1
        cam.data.clip_end = 1000
        for name, eye, tgt in PARAMS["views"]:
            e, t = Vector(g2b(np.array(eye))), Vector(g2b(np.array(tgt)))
            cam.location = e
            cam.rotation_euler = (t - e).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = str(OUT / ("prev-%s-%s.png" % (name, arm)))
            bpy.ops.render.render(write_still=True)
            log("rendered", name, arm)


main()
