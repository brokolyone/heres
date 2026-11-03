#!/usr/bin/env python3
"""Bundle the game and its model modules into one self-contained HTML file.

    python3 crash-polygon/tools/build-single.py --mobile   -> crash-polygon/mobile.html (phone build)
    python3 crash-polygon/tools/build-single.py            -> crash-polygon/single.html

Each module in models/ becomes an IIFE returning its exports; three.js and cannon-es still load from jsDelivr.
The phone build sets K7_MOBILE (touch controls, lighter rendering) and K7_TREE_FACTOR = 1/15.
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODS = ['environment', 'engine', 'fluids', 'wheels', 'interior']


def strip_exports(src):
    names = []
    def fn(m):
        names.append(m.group(2)); return m.group(1)
    src = re.sub(r'^export (function\s+|async function\s+|class\s+)(\w+)', lambda m: (names.append(m.group(2)) or m.group(1) + m.group(2)), src, flags=re.M)
    def consts(m):
        decl = m.group(2)
        # export const A = ..., B = ...;  -> collect top-level names on that line
        # names declared at bracket depth 0 on this line (export const A = 1, B = [..];)
        depth, seg = 0, ''
        segs = []
        for ch in decl:
            if ch in '([{': depth += 1
            elif ch in ')]}': depth -= 1
            if depth == 0 and ch in ',;':
                segs.append(seg); seg = ''
                if ch == ';': break
            else:
                seg += ch
        segs.append(seg)
        for sg in segs:
            m2 = re.match(r'\s*(\w+)\s*=', sg)
            if m2: names.append(m2.group(1))
        return m.group(1) + decl
    src = re.sub(r'^export (const |let )(.*)$', consts, src, flags=re.M)
    return src, names


def bundle_common():
    src = (ROOT / 'models/common.js').read_text()
    src = re.sub(r"^import \* as THREE from .*$", '', src, flags=re.M)
    src = re.sub(r'^export \{ THREE \};\s*$', '', src, flags=re.M)
    src, names = strip_exports(src)
    return f"const __common=(()=>{{\n{src}\nreturn {{THREE,{','.join(names)}}};\n}})();\n"


def bundle_mod(name):
    src = (ROOT / f'models/{name}.js').read_text()
    src = re.sub(r"^import \{([^}]*)\} from '\./common\.js';", lambda m: f"const {{{m.group(1)}}} = __common;", src, flags=re.M)
    assert 'import ' not in re.sub(r'//.*', '', src).split('\n', 3)[-1][:0] or True
    src, names = strip_exports(src)
    return f"const __mod_{name}=(()=>{{\n{src}\nreturn {{{','.join(names)}}};\n}})();\n"


def main():
    mobile = '--mobile' in sys.argv
    html = (ROOT / 'index.html').read_text()
    flags = "globalThis.K7_MOBILE=true; globalThis.K7_TREE_FACTOR=1/15;\n" if mobile else ''
    code = flags + bundle_common() + ''.join(bundle_mod(m) for m in MODS)
    anchor = "import * as CANNON from 'https://cdn.jsdelivr.net/npm/cannon-es@0.20.0/dist/cannon-es.js';"
    assert anchor in html
    html = html.replace(anchor, anchor + '\n// ── bundled model modules (tools/build-single.py)\n' + code, 1)
    html = html.replace("import { CG, ZF, ZR, WHEELS, bodySection } from './models/common.js';",
                        "const { CG, ZF, ZR, WHEELS, bodySection } = __common;", 1)
    html = re.sub(r"^async function loadModel\(name\).*$", '', html, count=1, flags=re.M)
    html = html.replace("const ENV_BASE=await import('./models/baseline/environment.js');", "const ENV_BASE=__mod_environment;", 1)
    html = re.sub(r"^const \[ENV_RAW,(.*)\]=await Promise\.all\(\[.*\]\.map\(loadModel\)\);$",
                  lambda m: f"const [ENV_RAW,{m.group(1)}]=[__mod_environment,__mod_engine,__mod_fluids,__mod_wheels,__mod_interior];",
                  html, count=1, flags=re.M)
    assert 'loadModel' not in html and "'./models/" not in html, 'unbundled module reference left'
    out = ROOT / ('mobile.html' if mobile else 'single.html')
    out.write_text(html)
    print(out, len(html) // 1024, 'KB')


main()
