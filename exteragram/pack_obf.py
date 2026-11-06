"""Packer that strips the source bare and stores it as an opaque blob.

Pipeline:
  1. drop every comment and docstring and re-emit the code with ast.unparse,
     so what anyone recovers is nameless, comment-free Python;
  2. zlib-compress it, XOR the bytes with a repeating key (pure noise), base64;
  3. optionally pad the file to a target size.

The exteraGram loader still reads the plain metadata at the top with AST. The
body is compiled on the device at load with the device's own interpreter, so it
is not tied to any one Python version. Behaviour is identical to pack.py.

This is obfuscation, not protection: the de-XOR key and the unwrap steps are in
the file, so a determined reader can still recover the (stripped) source.

Usage: python3 pack_obf.py <source> <out> [target_bytes]
"""
import ast, base64, os, sys, textwrap, zlib

src_path, out_path = sys.argv[1], sys.argv[2]
target = int(sys.argv[3]) if len(sys.argv) > 3 else 0
source = open(src_path, encoding="utf-8").read()

meta_names = {
    "__id__", "__name__", "__description__", "__author__", "__version__",
    "__icon__", "__app_version__", "__sdk_version__", "__min_version__",
    "__requirements__",
}

tree = ast.parse(source)

# Keep the readable metadata lines verbatim for the loader to read with AST.
lines = source.splitlines()
meta_lines = []
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id in meta_names:
        meta_lines.extend(lines[node.lineno - 1:node.end_lineno])


def strip_docstrings(t):
    for node in ast.walk(t):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                # keep at least a pass so an empty body stays valid
                node.body = body[1:] or [ast.Pass()]
    return t


stripped = strip_docstrings(tree)
ast.fix_missing_locations(stripped)
minified = ast.unparse(stripped)  # no comments, no docstrings, uniform layout

raw = zlib.compress(minified.encode("utf-8"), 9)
key = b"winft-vvooices"
xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
blob = base64.b64encode(xored).decode("ascii")

out = ['"""winft."""', ""]
out += meta_lines
out += [
    "",
    "import base64 as _b, zlib as _z",
    "_K = b'winft-vvooices'",
    "_C = (",
]
out += [f'    "{c}"' for c in textwrap.wrap(blob, 120)]
out += [
    ")",
    "_x = _b.b64decode(_C)",
    "_d = bytes(c ^ _K[i % len(_K)] for i, c in enumerate(_x))",
    'exec(compile(_z.decompress(_d).decode("utf-8"), __name__ or "winft", "exec"), globals())',
]
text = "\n".join(out) + "\n"

if target and len(text.encode("utf-8")) < target:
    pad = target - len(text.encode("utf-8")) - len("\n# \n")
    filler = base64.b64encode(os.urandom(max(0, pad)))[:max(0, pad)].decode("ascii")
    text += "# " + filler + "\n"
    # fine-tune to land exactly on target
    while len(text.encode("utf-8")) < target:
        text = text[:-1] + "=\n"
    while len(text.encode("utf-8")) > target and text.rstrip().endswith("="):
        text = text[:-2] + "\n"

open(out_path, "w", encoding="utf-8").write(text)
print("meta lines:", len(meta_lines),
      "| source bytes:", len(source),
      "| minified bytes:", len(minified),
      "| blob bytes:", len(blob),
      "| file bytes:", len(text.encode("utf-8")))
