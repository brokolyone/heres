"""Packer that stores the source zlib-compressed and base64-encoded.

The exteraGram loader reads the plain metadata with AST and then runs the file,
so __id__/__name__/... stay readable at the top. The body is the source
compressed (an opaque binary blob, unreadable as text) and compiled on the
device at load time with the device's own interpreter, so it is not locked to
any one Python version. Same behaviour as pack.py.
"""
import ast, base64, sys, textwrap, zlib

src_path, out_path = sys.argv[1], sys.argv[2]
source = open(src_path, encoding="utf-8").read()

meta_names = {
    "__id__", "__name__", "__description__", "__author__", "__version__",
    "__icon__", "__app_version__", "__sdk_version__", "__min_version__",
    "__requirements__",
}
tree = ast.parse(source)
lines = source.splitlines()
meta_lines = []
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id in meta_names:
        meta_lines.extend(lines[node.lineno - 1:node.end_lineno])

blob = base64.b64encode(zlib.compress(source.encode("utf-8"), 9)).decode("ascii")

out = ['"""winft — packed build."""', ""]
out += meta_lines
out += ["", "import base64 as _b, zlib as _z", "_C = ("]
out += [f'    "{c}"' for c in textwrap.wrap(blob, 120)]
out += [")", 'exec(compile(_z.decompress(_b.b64decode(_C)).decode("utf-8"), __name__ or "winft", "exec"), globals())']
open(out_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("meta lines:", len(meta_lines), "| source bytes:", len(source), "| b64 bytes:", len(blob))
