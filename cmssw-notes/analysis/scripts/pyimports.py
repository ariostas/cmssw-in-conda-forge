"""Check that a configuration's python imports stay inside a layer and the ones below it.

The build graph says nothing about python, and a layer whose configuration imports a module
from a higher layer, or none, builds fine and only fails when someone loads it. Two cases:

  * the module's package is in a higher layer, or in no layer at all;
  * the module is a cfi generated from a plugin's parameter description (it has no source
    file) and the package is src-only, so its plugins, and with them the cfi, are not built.

The walk reads the release's sources on CVMFS and follows `import`, `from ... import` and
`process.load("...")` wherever they appear, including inside functions and behind process
modifiers, since both are still executed or imported by someone. It is therefore an upper
bound: a hit is worth checking, not necessarily a failure.

    python3 cmssw-notes/analysis/scripts/pyimports.py cmssw-reco-objects \\
        PhysicsTools.NanoAOD.nano_cff
"""

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reach  # noqa: E402

SRC = os.path.join(reach.RELEASE, "src")


def module_file(module):
    """(package, source file or None) for a dotted module name, or (None, None)."""
    parts = module.split(".")
    if len(parts) < 3:
        return None, None
    package = parts[0] + "/" + parts[1]
    if not os.path.isdir(os.path.join(SRC, package)):
        return None, None
    base = os.path.join(SRC, parts[0], parts[1], "python", *parts[2:])
    for candidate in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.exists(candidate):
            return package, candidate
    return package, None


def imports_of(path):
    for node in ast.walk(ast.parse(open(path).read(), path)):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module
            # "from A.B.c import d" may import the module A.B.c.d or the name d in A.B.c
            yield from (node.module + "." + a.name for a in node.names)
        elif (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", "") == "load"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            yield node.args[0].value


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    top = sys.argv[1].rstrip("/").split("/")[-1]
    if top not in reach.SHIPPED:
        sys.exit(f"{top} is not one of {', '.join(reach.SHIPPED)}")
    layer_of, src_only = {}, set()
    for i, recipe in enumerate(reach.SHIPPED):
        for p in reach.read_list(os.path.join("recipes", recipe, "packages.txt")):
            layer_of[p] = i
        so_file = os.path.join("recipes", recipe, "src-only.txt")
        if os.path.exists(so_file):
            src_only |= set(reach.read_list(so_file))
    limit = reach.SHIPPED.index(top)

    seen, parent = {}, {}
    stack = [(m, None) for m in sys.argv[2:]]
    while stack:
        module, via = stack.pop()
        if module in seen:
            continue
        package, path = module_file(module)
        if package is None:
            continue
        seen[module] = (package, path)
        parent[module] = via
        if path is None:
            continue
        for name in imports_of(path):
            p, f = module_file(name)
            # a name without a file is either a generated cfi or a class from "from X import Y"
            if p and (f or name.endswith("_cfi")):
                stack.append((name, module))

    problems = {}
    for module, (package, path) in seen.items():
        i = layer_of.get(package)
        if i is None or i > limit:
            where = reach.SHIPPED[i] if i is not None else "no layer"
            problems.setdefault((where, package), []).append(module)
        elif path is None and package in src_only:
            problems.setdefault(("generated, src-only", package), []).append(module)

    print(f"{len(seen)} modules")
    for (where, package), modules in sorted(problems.items()):
        chain = [sorted(modules)[0]]
        while parent.get(chain[-1]):
            chain.append(parent[chain[-1]])
        print(f"\n{package} ({where}): {len(modules)} modules")
        for m in sorted(modules):
            print(f"    {m}")
        print(f"  via {' <- '.join(chain[1:])}")
    if not problems:
        print("ok")


if __name__ == "__main__":
    main()
