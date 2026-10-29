"""Write a CarModel to glTF 2.0 binary (.glb) and Wavefront OBJ/MTL + PNG.

Coordinate conversion: the game data is treated as left-handed (Direct3D,
+y up, front of the car towards -z). Negating z gives a right-handed glTF
scene with the car facing +z and keeps clockwise D3D triangles front-facing
as counter-clockwise.
"""
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from .car import CarModel

FLIP = np.array([1, 1, -1], np.float32)


def _png(rgba):
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def _groups(model, lod):
    """Merge every visible triangle by texture page."""
    mat_page = model.material_page()
    by_page = {}
    for _name, m in model.meshes(lod):
        for mat, first, count in m["draws"]:
            page = mat_page.get(mat, 0)
            if page not in model.pages:
                page = 0
            sl = slice(first, first + count)
            g = by_page.setdefault(page, {"p": [], "n": [], "t": []})
            g["p"].append(m["positions"][sl] * FLIP)
            g["n"].append(m["normals"][sl] * FLIP)
            g["t"].append(m["uvs"][sl])
    return {k: {kk: np.concatenate(v) for kk, v in g.items()} for k, g in sorted(by_page.items())}


def write_glb_batches(path, name, batches, repeat=False):
    """Write a .glb from batches already in the right-handed output frame.

    Each batch: dict with "p" (N,3), optional "n" (N,3), "t" (N,2), optional
    "c" (N,4 float 0..1), "rgba" texture, "mode" (OPAQUE/MASK/BLEND),
    optional "unlit" and "roughness". Winding is swapped here because the
    geometry was mirrored in z.
    """
    bin_chunks, views, accessors, meshes_prims, images, textures, materials = [], [], [], [], [], [], []

    def add_view(data: bytes, target=None):
        off = sum(len(c) for c in bin_chunks)
        pad = (-len(data)) % 4
        bin_chunks.append(data + b"\0" * pad)
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            v["target"] = target
        views.append(v)
        return len(views) - 1

    def add_acc(arr, typ, minmax=False):
        view = add_view(arr.astype(np.float32).tobytes(), 34962)
        acc = {"bufferView": view, "componentType": 5126, "count": len(arr), "type": typ}
        if minmax:
            acc["min"] = arr.min(0).tolist()
            acc["max"] = arr.max(0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    used_ext = set()
    for b in batches:
        img_view = add_view(_png(b["rgba"]))
        images.append({"bufferView": img_view, "mimeType": "image/png"})
        textures.append({"source": len(images) - 1, "sampler": 0})
        mat = {"name": b.get("name", f"mat{len(materials)}"),
               "pbrMetallicRoughness": {"baseColorTexture": {"index": len(textures) - 1},
                                        "metallicFactor": 0.0,
                                        "roughnessFactor": b.get("roughness", 0.8)},
               "alphaMode": b["mode"], "doubleSided": True}
        if b["mode"] == "MASK":
            mat["alphaCutoff"] = 0.5
        if b.get("unlit"):
            mat["extensions"] = {"KHR_materials_unlit": {}}
            used_ext.add("KHR_materials_unlit")
        materials.append(mat)
        tri = np.arange(len(b["p"])).reshape(-1, 3)[:, [0, 2, 1]].reshape(-1)
        attrs = {"POSITION": add_acc(b["p"][tri], "VEC3", True),
                 "TEXCOORD_0": add_acc(b["t"][tri], "VEC2")}
        if b.get("n") is not None:
            attrs["NORMAL"] = add_acc(b["n"][tri], "VEC3")
        if b.get("c") is not None:
            attrs["COLOR_0"] = add_acc(b["c"][tri], "VEC4")
        meshes_prims.append({"attributes": attrs, "material": len(materials) - 1})

    wrap = 10497 if repeat else 33071
    gltf = {
        "asset": {"version": "2.0", "generator": "NFS5 Format Tools"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": meshes_prims}],
        "materials": materials, "textures": textures, "images": images,
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": wrap, "wrapT": wrap}],
        "accessors": accessors, "bufferViews": views,
        "buffers": [{"byteLength": sum(len(c) for c in bin_chunks)}],
    }
    if used_ext:
        gltf["extensionsUsed"] = sorted(used_ext)
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((-len(js)) % 4)
    binary = b"".join(bin_chunks)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)
    return sum(len(b["p"]) // 3 for b in batches)


def write_glb(model: CarModel, path, lod=1):
    batches = []
    for page, g in _groups(model, lod).items():
        pg = model.pages[page]
        batches.append({"name": f"tpage{page + 1}", "p": g["p"], "n": g["n"], "t": g["t"],
                        "rgba": pg.rgba, "mode": pg.mode,
                        "roughness": 0.35 if pg.painted else 0.8})
    return write_glb_batches(path, model.name, batches)


def write_obj(model: CarModel, out_dir, lod=1):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = _groups(model, lod)
    obj = [f"mtllib {model.name}.mtl"]
    mtl = []
    base = 1
    for page, g in groups.items():
        tex = f"{model.name}_tpage{page + 1}.png"
        Image.fromarray(model.pages[page].rgba, "RGBA").save(out_dir / tex)
        mtl += [f"newmtl tpage{page + 1}", "Kd 1 1 1", f"map_Kd {tex}"]
        if model.pages[page].mode != "OPAQUE":
            mtl.append(f"map_d {tex}")
        obj.append(f"usemtl tpage{page + 1}")
        obj += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in g["p"]]
        obj += [f"vn {x:.6f} {y:.6f} {z:.6f}" for x, y, z in g["n"]]
        obj += [f"vt {u:.6f} {1 - v:.6f}" for u, v in g["t"]]
        for k in range(0, len(g["p"]), 3):
            a, b, c = base + k, base + k + 2, base + k + 1
            obj.append(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}")
        base += len(g["p"])
    (out_dir / f"{model.name}.obj").write_text("\n".join(obj) + "\n")
    (out_dir / f"{model.name}.mtl").write_text("\n".join(mtl) + "\n")


def main(argv):
    car_dir, name, out = Path(argv[1]), argv[2], Path(argv[3])
    model = CarModel(car_dir, name)
    out.mkdir(parents=True, exist_ok=True)
    tris = write_glb(model, out / f"{name}.glb")
    write_obj(model, out / name)
    print(f"{name}: {tris} triangles, {len(model.pages)} texture pages -> {out}")


if __name__ == "__main__":
    main(sys.argv)
