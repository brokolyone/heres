"""Download the CC0 PBR texture sets used by src/materials.py (owner: Materials & Textures artist).

Usage:  cd models/hero && python3 src/fetch_textures.py [--dest DIR] [AssetId ...]
Default: every asset referenced by materials.SPEC -> textures/<AssetId>/, plus
textures/CREDITS.json (source, URL, licence) and textures/STATS.json (mean albedo luminance and mean
roughness, used by materials.py to keep the palette colour as the perceived average).

Source: ambientCG (https://ambientcg.com), all assets CC0 1.0 Universal (public domain).
Downloads are treated as data: only image files are extracted (no paths, no scripts), 1K JPG.
"""
import argparse
import io
import json
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEST = os.path.normpath(os.path.join(HERE, "..", "textures"))
RES = "1K-JPG"
API = "https://ambientcg.com/api/v2/full_json?id={id}&include=downloadData,displayData"
GET = "https://ambientcg.com/get?file={id}_{res}.zip"
KEEP = ("_color.", "_roughness.", "_normalgl.", "_metalness.", "_ambientocclusion.", "_displacement.")
UA = {"User-Agent": "bridge-squad-texture-fetch/1.0"}


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def fetch(asset, dest):
    out = os.path.join(dest, asset)
    os.makedirs(out, exist_ok=True)
    have = [f for f in os.listdir(out) if f.lower().endswith(".jpg")]
    if not any("_color." in f.lower() for f in have):
        data = _get(GET.format(id=asset, res=RES))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                base = os.path.basename(info.filename)
                low = base.lower()
                if not base or base != info.filename or not low.endswith((".jpg", ".jpeg", ".png")):
                    continue  # skip dirs, nested paths and anything that isn't an image
                if not any(k in low for k in KEEP):
                    continue
                if "_displacement." in low:
                    continue  # not needed (no displacement in a baked game asset)
                with z.open(info) as src, open(os.path.join(out, base), "wb") as dst:
                    dst.write(src.read())
    meta = {"asset_id": asset, "source": "ambientCG", "licence": "CC0 1.0 Universal",
            "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "page": f"https://ambientcg.com/view?id={asset}",
            "download": GET.format(id=asset, res=RES),
            "files": sorted(os.listdir(out))}
    try:
        info = json.loads(_get(API.format(id=asset)))["foundAssets"][0]
        meta["name"] = info.get("displayName", asset)
    except Exception:  # metadata is nice-to-have
        pass
    return meta


def stats(asset, dest):
    import numpy as np
    from PIL import Image
    d = os.path.join(dest, asset)
    res = {}
    for f in os.listdir(d):
        low = f.lower()
        if "_color." in low:
            px = np.asarray(Image.open(os.path.join(d, f)).convert("RGB"), dtype=np.float32) / 255.0
            lin = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
            res["lum_mean"] = float((lin @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)).mean())
            res["srgb_mean"] = [float(v) for v in px.reshape(-1, 3).mean(0)]
        elif "_roughness." in low:
            px = np.asarray(Image.open(os.path.join(d, f)).convert("L"), dtype=np.float32) / 255.0
            res["rough_mean"] = float(px.mean())
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("assets", nargs="*")
    a = ap.parse_args()
    assets = a.assets
    if not assets:
        sys.path.insert(0, HERE)
        import importlib.util
        spec = importlib.util.spec_from_file_location("hero_spec_only", os.path.join(HERE, "materials.py"))
        # materials.py imports bpy; read SPEC textually if bpy is unavailable
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            assets = sorted({v["tex"] for v in mod.SPEC.values() if v.get("tex")})
        except ImportError:
            import re
            txt = open(os.path.join(HERE, "materials.py")).read()
            assets = sorted(set(re.findall(r'tex="([A-Za-z0-9]+)"', txt)))
    os.makedirs(a.dest, exist_ok=True)
    cpath = os.path.join(a.dest, "CREDITS.json")
    spath = os.path.join(a.dest, "STATS.json")
    credits = json.load(open(cpath)) if os.path.exists(cpath) else {}
    st = json.load(open(spath)) if os.path.exists(spath) else {}
    for asset in assets:
        print("fetch", asset, flush=True)
        credits[asset] = fetch(asset, a.dest)
        st[asset] = stats(asset, a.dest)
    credits = {k: credits[k] for k in sorted(credits)}
    with open(cpath, "w") as f:
        json.dump(credits, f, indent=2)
    with open(spath, "w") as f:
        json.dump({k: st[k] for k in sorted(st)}, f, indent=2)
    print("ok:", len(assets), "assets ->", a.dest)


if __name__ == "__main__":
    main()
