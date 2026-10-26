import ast, base64, sys, textwrap

src_path = sys.argv[1]
out_path = sys.argv[2]
source = open(src_path, encoding="utf-8").read()

# Find the plain top-level metadata assignments (__id__, __name__, ...), which the
# exteraGram loader reads with AST before running the file. They must stay readable.
tree = ast.parse(source)
meta_names = {
    "__id__", "__name__", "__description__", "__author__", "__version__",
    "__icon__", "__app_version__", "__sdk_version__", "__min_version__",
    "__requirements__",
}
meta_lines = []
lines = source.splitlines()
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id in meta_names:
        meta_lines.extend(lines[node.lineno - 1:node.end_lineno])

blob = base64.b64encode(source.encode("utf-8")).decode("ascii")
blob_wrapped = "\n".join(textwrap.wrap(blob, 120))

out = []
out.append('"""Local NFT Showcase — packed build. The readable source lives in the repo."""')
out.append("")
out.extend(meta_lines)
out.append("")
out.append("import base64 as _b64")
out.append('_SRC = (')
for chunk in textwrap.wrap(blob, 120):
    out.append(f'    "{chunk}"')
out.append(")")
out.append('exec(compile(_b64.b64decode(_SRC).decode("utf-8"), __name__ or "local_nft_showcase", "exec"), globals())')
open(out_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("meta lines:", len(meta_lines), "| source bytes:", len(source), "| b64 bytes:", len(blob))
