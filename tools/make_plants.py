#!/usr/bin/env python3
"""
Generates stylised sample potted plants as .glb files (glTF 2.0 binary).

Output: www/models/<plant>_<pot>_<size>.glb  and  www/plants.json
Units are metres, origin at the centre of the pot base, +Y up.
These are placeholder models for AR testing - swap in real product scans later
(keep the same file naming and update www/plants.json).

Run:  python3 tools/make_plants.py      (needs only numpy)
"""
import json
import math
import os
import struct

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "www", "models")

POTS = {
    "terracotta": {"label": "Terracotta", "hex": "#B5603A"},
    "cream": {"label": "Cream", "hex": "#EFE8D8"},
    "charcoal": {"label": "Charcoal", "hex": "#2B2F2C"},
}
SIZES = {"S": 0.7, "M": 1.0, "L": 1.35}


def hex_rgba(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    # glTF baseColorFactor is linear; convert from sRGB
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return [round(v, 4) for v in lin] + [1.0]


# --------------------------------------------------------------------------
# Mesh helpers.  A "mesh part" is (verts Nx3, tris Mx3 int, material_name)
# --------------------------------------------------------------------------
def normals_for(v, t):
    n = np.zeros_like(v)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    fn = np.cross(b - a, c - a)
    for i in range(3):
        np.add.at(n, t[:, i], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return n / ln


def lathe(profile, seg=40):
    """Revolve [(r, y), ...] around Y. Path should run up the outside, over the
    rim and down/in so that normals point outward."""
    prof = np.array(profile, float)
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    verts = []
    for r, y in prof:
        for a in ang:
            verts.append([r * math.cos(a), y, r * math.sin(a)])
    verts = np.array(verts)
    tris = []
    for j in range(len(prof) - 1):
        if np.allclose(prof[j], prof[j + 1]):
            continue
        for k in range(seg):
            k2 = (k + 1) % seg
            a, b = j * seg + k, (j + 1) * seg + k
            c, d = (j + 1) * seg + k2, j * seg + k2
            tris += [[a, c, b], [a, d, c]]
    return verts, np.array(tris, dtype=np.int64)


def tube(points, radius, seg=7, r_end=None):
    pts = np.array(points, float)
    n = len(pts)
    r_end = radius if r_end is None else r_end
    verts, tris = [], []
    for i, p in enumerate(pts):
        t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t = t / (np.linalg.norm(t) + 1e-9)
        ref = np.array([1.0, 0, 0]) if abs(t[0]) < 0.9 else np.array([0, 0, 1.0])
        u = np.cross(t, ref)
        u /= np.linalg.norm(u)
        w = np.cross(t, u)
        rad = radius + (r_end - radius) * i / max(n - 1, 1)
        for k in range(seg):
            a = 2 * math.pi * k / seg
            verts.append(p + rad * (math.cos(a) * u + math.sin(a) * w))
    for i in range(n - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            a, b = i * seg + k, (i + 1) * seg + k
            c, d = (i + 1) * seg + k2, i * seg + k2
            tris += [[a, b, c], [a, c, d]]
    return np.array(verts), np.array(tris, dtype=np.int64)


def leaf(length, width, origin, yaw, pitch_deg, droop_deg, shape,
         nu=12, nv=4, fold=0.0, holes=None):
    """A bent blade. pitch = elevation of the midrib at the base (90 = up),
    droop = how much the elevation falls by the tip."""
    origin = np.array(origin, float)
    heading = np.array([math.cos(yaw), 0, math.sin(yaw)])
    side = np.array([-math.sin(yaw), 0, math.cos(yaw)])
    up = np.array([0, 1.0, 0])
    mid = [origin]
    ds = length / nu
    for i in range(nu):
        u = (i + 0.5) / nu
        el = math.radians(pitch_deg - droop_deg * u)
        d = heading * math.cos(el) + up * math.sin(el)
        mid.append(mid[-1] + d * ds)
    mid = np.array(mid)
    verts = []
    for i in range(nu + 1):
        u = i / nu
        t = mid[min(i + 1, nu)] - mid[max(i - 1, 0)]
        t /= np.linalg.norm(t) + 1e-9
        nrm = np.cross(t, side)
        nrm /= np.linalg.norm(nrm) + 1e-9
        w = 0.5 * width * float(shape(u))
        for j in range(nv + 1):
            v = -1 + 2 * j / nv
            verts.append(mid[i] + side * (v * w) + nrm * (abs(v) * fold * w))
    verts = np.array(verts)
    tris = []
    for i in range(nu):
        for j in range(nv):
            if holes and holes(i / nu, j / nv):
                continue
            a = i * (nv + 1) + j
            b, c, d = a + 1, a + (nv + 1) + 1, a + (nv + 1)
            tris += [[a, b, c], [a, c, d]]
    return verts, np.array(tris, dtype=np.int64)


def merge(parts):
    """Merge a list of (verts, tris) into one."""
    vs, ts, off = [], [], 0
    for v, t in parts:
        if len(t) == 0:
            continue
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.vstack(vs), np.vstack(ts)


# --------------------------------------------------------------------------
# Pots (return (R, H, parts)) - the soil surface sits at y = H*0.88
# --------------------------------------------------------------------------
def make_pot(R, H):
    ys = H * 0.88
    profile = [
        (0.0, 0.0), (0.62 * R, 0.0), (0.62 * R, 0.0), (0.66 * R, 0.02 * H),
        (R * 0.97, H * 0.90), (R * 1.04, H * 0.92), (R * 1.04, H),
        (R * 0.93, H), (R * 0.90, ys - 0.004), (0.0, ys - 0.004),
    ]
    pot = lathe(profile)
    soil = lathe([(R * 0.91, ys), (0.0, ys)])
    return pot, soil, ys


# --------------------------------------------------------------------------
# Plants.  Each returns list of (verts, tris, material) parts, y=0 at pot base.
# --------------------------------------------------------------------------
def snake_plant():
    R, H = 0.085, 0.15
    pot, soil, ys = make_pot(R, H)
    parts = []
    n = 11
    rng = np.random.default_rng(3)
    shape = lambda u: (0.45 + 0.55 * math.sin(math.pi * min(u, 1) ** 0.7)) * (1 - u ** 4)
    for i in range(n):
        yaw = i * 2.39996
        rad = 0.012 + 0.03 * (i % 3) / 2
        o = (rad * math.cos(yaw), ys, rad * math.sin(yaw))
        L = 0.30 + 0.30 * (1 - abs((i / (n - 1)) - 0.45) * 1.4) + rng.uniform(-0.03, 0.03)
        parts.append(leaf(L, 0.065, o, yaw, rng.uniform(78, 87), rng.uniform(4, 14),
                          shape, nu=14, nv=4, fold=0.18) + ("leaf_a" if i % 2 else "leaf_b",))
    return R, H, pot, soil, parts


def monstera():
    R, H = 0.105, 0.18
    pot, soil, ys = make_pot(R, H)
    parts = []
    rng = np.random.default_rng(11)

    def shape(u):
        return math.sin(math.pi * min(u, 1) ** 0.75) ** 0.85 * (1.0 if u > 0.08 else 0.6)

    def holes(u, v):
        # stylised splits on both sides of the midrib
        return (0.30 < u < 0.38 or 0.52 < u < 0.60 or 0.72 < u < 0.78) and v < 0.50 or \
               (0.30 < u < 0.38 or 0.52 < u < 0.60 or 0.72 < u < 0.78) and v > 0.50

    n = 7
    for i in range(n):
        yaw = i * 2.39996 + 0.4
        lean = 0.05 + 0.07 * (i % 3)
        h = 0.20 + 0.075 * i + rng.uniform(-0.02, 0.02)
        base = np.array([0.012 * math.cos(yaw), ys, 0.012 * math.sin(yaw)])
        top = base + np.array([lean * math.cos(yaw), h, lean * math.sin(yaw)])
        ctrl = base + np.array([0.0, h * 0.7, 0.0])
        pts = [(1 - t) ** 2 * base + 2 * (1 - t) * t * ctrl + t ** 2 * top for t in np.linspace(0, 1, 8)]
        tv, tt = tube(pts, 0.006, seg=6, r_end=0.004)
        parts.append((tv, tt, "stem"))
        Ls = 0.27 + 0.05 * rng.random()
        parts.append(leaf(Ls, Ls * 0.95, top, yaw + rng.uniform(-0.3, 0.3), rng.uniform(22, 45),
                          rng.uniform(25, 45), shape, nu=18, nv=14, fold=0.15,
                          holes=None if i % 3 == 0 else (lambda u, v: (0.34 < u < 0.42 or 0.58 < u < 0.66) and (v < 0.32 or v > 0.68)))
                     + ("leaf_a" if i % 2 else "leaf_b",))
    return R, H, pot, soil, parts


def succulent():
    R, H = 0.06, 0.07
    pot, soil, ys = make_pot(R, H)
    parts = []
    shape = lambda u: (math.sin(math.pi * min(u, 1) ** 0.55) ** 0.7) * (1 - 0.5 * u ** 3) * (1 - u ** 6)
    rings = [(5, 0.035, 0.045, 78, 15), (7, 0.05, 0.05, 58, 25), (9, 0.065, 0.055, 38, 30),
             (11, 0.08, 0.06, 20, 28)]
    for ri, (cnt, L, W, pitch, droop) in enumerate(rings):
        for i in range(cnt):
            yaw = (i / cnt) * 2 * math.pi + ri * 0.35
            o = (0.004 * math.cos(yaw), ys + 0.002 * (len(rings) - ri), 0.004 * math.sin(yaw))
            parts.append(leaf(L, W, o, yaw, pitch, droop, shape, nu=8, nv=4, fold=0.25)
                         + ("leaf_a" if (i + ri) % 2 else "leaf_b",))
    return R, H, pot, soil, parts


def rubber_plant():
    R, H = 0.125, 0.22
    pot, soil, ys = make_pot(R, H)
    parts = []
    rng = np.random.default_rng(21)
    top_y = ys + 0.62
    stem = [(0.01 * math.sin(t * 2.2), ys + (top_y - ys) * t, 0.008 * math.sin(t * 3.1)) for t in np.linspace(0, 1, 14)]
    sv, st = tube(stem, 0.011, seg=8, r_end=0.006)
    parts.append((sv, st, "stem"))
    shape = lambda u: math.sin(math.pi * min(u, 1) ** 0.8) ** 0.7
    n = 18
    for i in range(n):
        t = 0.18 + 0.82 * i / (n - 1)
        idx = min(int(t * 13), 13)
        o = stem[idx]
        yaw = i * 2.39996
        L = 0.24 - 0.07 * t + rng.uniform(-0.01, 0.01)
        parts.append(leaf(L, L * 0.62, o, yaw, rng.uniform(40, 60), rng.uniform(15, 30),
                          shape, nu=10, nv=4, fold=0.12) + ("leaf_a" if i % 2 else "leaf_b",))
    return R, H, pot, soil, parts


PLANTS = {
    "snake": {
        "name": "Snake Plant", "latin": "Sansevieria trifasciata", "fn": snake_plant,
        "blurb": "Tough, low-light friendly and almost impossible to kill. A great first plant.",
        "light": "Low to bright", "water": "Every 2-3 weeks",
        "leaf_a": "#2C6B3C", "leaf_b": "#3A7F49", "stem": "#6E8F4A",
    },
    "monstera": {
        "name": "Monstera", "latin": "Monstera deliciosa", "fn": monstera,
        "blurb": "Big split leaves that make a statement in any living room.",
        "light": "Bright indirect", "water": "Weekly",
        "leaf_a": "#2E7A44", "leaf_b": "#25683A", "stem": "#5E8A3C",
    },
    "succulent": {
        "name": "Echeveria Succulent", "latin": "Echeveria elegans", "fn": succulent,
        "blurb": "A compact rosette for desks, shelves and sunny windowsills.",
        "light": "Bright / direct", "water": "Every 2 weeks",
        "leaf_a": "#7DB59A", "leaf_b": "#6AA689", "stem": "#6AA689",
    },
    "rubber": {
        "name": "Rubber Plant", "latin": "Ficus elastica", "fn": rubber_plant,
        "blurb": "Glossy dark leaves on a tall, elegant stem. Fills a corner beautifully.",
        "light": "Bright indirect", "water": "Every 1-2 weeks",
        "leaf_a": "#1F4D2B", "leaf_b": "#2A5E37", "stem": "#5A4632",
    },
}


# --------------------------------------------------------------------------
# GLB writer
# --------------------------------------------------------------------------
def pad4(b, fill=b"\x00"):
    return b + fill * ((4 - len(b) % 4) % 4)


def write_glb(path, groups, materials, title):
    """groups: {material_name: (verts, tris)}; materials: {name: dict}"""
    bin_chunks, bufviews, accessors, prims, mats = bytearray(), [], [], [], []
    mat_index = {}
    for name, m in materials.items():
        if name not in groups:
            continue
        mat_index[name] = len(mats)
        mats.append({
            "name": name,
            "pbrMetallicRoughness": {
                "baseColorFactor": hex_rgba(m["hex"]),
                "metallicFactor": 0.0,
                "roughnessFactor": m.get("rough", 0.7),
            },
            "doubleSided": bool(m.get("double", False)),
        })

    def add_view(data, target):
        off = len(bin_chunks)
        bin_chunks.extend(pad4(data))
        bufviews.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
        return len(bufviews) - 1

    for name, (v, t) in groups.items():
        v = v.astype(np.float32)
        nrm = normals_for(v, t).astype(np.float32)
        use16 = len(v) < 65535
        idx = t.astype(np.uint16 if use16 else np.uint32).flatten()
        pv = add_view(v.tobytes(), 34962)
        nv = add_view(nrm.tobytes(), 34962)
        iv = add_view(idx.tobytes(), 34963)
        a0 = len(accessors)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": len(v), "type": "VEC3",
                          "min": [float(x) for x in v.min(0)], "max": [float(x) for x in v.max(0)]})
        accessors.append({"bufferView": nv, "componentType": 5126, "count": len(v), "type": "VEC3"})
        accessors.append({"bufferView": iv, "componentType": 5123 if use16 else 5125,
                          "count": int(len(idx)), "type": "SCALAR"})
        prims.append({"attributes": {"POSITION": a0, "NORMAL": a0 + 1}, "indices": a0 + 2,
                      "material": mat_index[name], "mode": 4})

    gltf = {
        "asset": {"version": "2.0", "generator": "vasukii tools/make_plants.py"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": title}],
        "meshes": [{"name": title, "primitives": prims}],
        "materials": mats, "accessors": accessors, "bufferViews": bufviews,
        "buffers": [{"byteLength": len(bin_chunks)}],
    }
    js = pad4(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    binb = bytes(bin_chunks)
    total = 12 + 8 + len(js) + 8 + len(binb)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binb), 0x004E4942) + binb)
    return total


def main():
    os.makedirs(OUT, exist_ok=True)
    catalog = []
    for pid, meta in PLANTS.items():
        R, H, pot, soil, parts = meta["fn"]()
        entry = {
            "id": pid, "name": meta["name"], "latin": meta["latin"], "blurb": meta["blurb"],
            "light": meta["light"], "water": meta["water"],
            "heightsCm": {}, "widthsCm": {},
        }
        for pot_id, pot_meta in POTS.items():
            for size_id, k in SIZES.items():
                groups = {}
                groups["pot"] = pot
                groups["soil"] = soil
                by_mat = {}
                for v, t, m in parts:
                    by_mat.setdefault(m, []).append((v, t))
                for m, lst in by_mat.items():
                    groups[m] = merge(lst)
                groups = {m: (vt[0] * k, vt[1]) for m, vt in groups.items()}
                materials = {
                    "pot": {"hex": pot_meta["hex"], "rough": 0.6},
                    "soil": {"hex": "#3B2A20", "rough": 1.0},
                    "leaf_a": {"hex": meta["leaf_a"], "rough": 0.5, "double": True},
                    "leaf_b": {"hex": meta["leaf_b"], "rough": 0.5, "double": True},
                    "stem": {"hex": meta["stem"], "rough": 0.8},
                }
                fname = f"{pid}_{pot_id}_{size_id}.glb"
                size = write_glb(os.path.join(OUT, fname), groups, materials, f"{meta['name']} ({pot_id}, {size_id})")
                allv = np.vstack([g[0] for g in groups.values()])
                if pot_id == "terracotta":
                    entry["heightsCm"][size_id] = round(float(allv[:, 1].max()) * 100)
                    ext = allv.max(0) - allv.min(0)
                    entry["widthsCm"][size_id] = round(float(max(ext[0], ext[2])) * 100)
                print(f"{fname:34s} {size/1024:6.0f} KB")
        catalog.append(entry)
    catalog_out = {
        "pots": [{"id": k, "label": v["label"], "hex": v["hex"]} for k, v in POTS.items()],
        "sizes": [{"id": k, "label": {"S": "Small", "M": "Medium", "L": "Large"}[k]} for k in SIZES],
        "plants": catalog,
    }
    with open(os.path.join(ROOT, "www", "plants.json"), "w") as f:
        json.dump(catalog_out, f, indent=2)
    print("wrote www/plants.json")


if __name__ == "__main__":
    main()
