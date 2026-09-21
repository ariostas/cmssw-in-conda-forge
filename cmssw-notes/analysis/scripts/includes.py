"""Close a layer over the headers its sources include but no BuildFile declares.

CMSSW is built as one area where every package's interface/ is on the include path whether
or not a BuildFile names it in a <use>, so packages include headers they never declare. A
layer that installs only what the dependency graph names then fails to compile, minutes in.

`undeclared.py` reports those as candidates by scanning every file in a package. That is
enough to eyeball a small layer, but it over-counts badly if you act on it directly: a
header sitting in src/ that no translation unit includes is never compiled, and following
it drags in whole subsystems. Closing cmssw-reco that way added 58 packages and pulled in
egamma, tau and MET behind PhysicsTools/PatExamples, none of which anything compiles.

This walks the include graph out of the files SCRAM actually compiles -- the .cc under
src/, plugins/ and bin/, minus the ones a layer's patches remove -- and follows it through
the headers those reach. On the same layer it adds 26 packages instead of 58, and converges.

    python3 cmssw-notes/analysis/scripts/includes.py recipes/cmssw-reco [--write]

Without --write it only reports. With it, the layer's packages.txt is rewritten, keeping
its leading comment block.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reach  # noqa: E402

R = os.path.join(reach.RELEASE, "src")
INC = re.compile(
    r'#\s*include\s+"([A-Za-z][A-Za-z0-9]*/[A-Za-z0-9]+/(?:interface|src)/[^"]+)"'
)
# Files a layer's patches take out of the build, so what they include does not matter.
# Keep in step with the patches/ directory of the layers that have them.
PATCHED_OUT = ("GeometryValidate.cc", "/alpaka/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("layer", help="a layer recipe directory, e.g. recipes/cmssw-reco")
    ap.add_argument(
        "--write", action="store_true", help="rewrite the layer's packages.txt"
    )
    args = ap.parse_args()
    layer_dir = args.layer.rstrip("/")

    pkgs, names, tus = reach.load()
    libs, plugins = reach.solve(pkgs, names, set(reach.BLOCKED))
    shipped = set()
    for recipe in reach.SHIPPED:
        listing = os.path.join("recipes", recipe, "packages.txt")
        if os.path.exists(listing) and os.path.basename(layer_dir) != recipe:
            shipped |= set(reach.read_list(listing))
    src_only_file = os.path.join(layer_dir, "src-only.txt")
    src_only = (
        set(reach.read_list(src_only_file)) if os.path.exists(src_only_file) else set()
    )

    cache = {}

    def includes(path):
        if path not in cache:
            try:
                cache[path] = INC.findall(open(path, errors="ignore").read())
            except OSError:
                cache[path] = []
        return cache[path]

    def compiled(pkg):
        out = []
        for sub in ("src", "plugins", "bin"):
            if pkg in src_only and sub != "src":
                continue
            for root, _, files in os.walk(os.path.join(R, pkg, sub)):
                for n in files:
                    if n.endswith((".cc", ".cpp", ".c")):
                        f = os.path.join(root, n)
                        if not any(m in f for m in PATCHED_OUT):
                            out.append(f)
        return out

    def deps_of(p):
        uses = pkgs[p]["uses"].get("lib", [])
        if p in plugins and p not in src_only:
            uses = uses + pkgs[p]["uses"].get("plugins", [])
            uses = uses + pkgs[p]["uses"].get("bin", [])
        out = set()
        for u in uses:
            q = u if u in pkgs else names.get(u.lower())
            if q and q in libs:
                out.add(q)
        return out

    def close(seed):
        seen, stack = set(seed), list(seed)
        while stack:
            for q in deps_of(stack.pop()):
                if q not in seen:
                    seen.add(q)
                    stack.append(q)
        return seen

    listing = os.path.join(layer_dir, "packages.txt")
    layer = close(set(reach.read_list(listing))) - shipped
    added = []
    for rnd in range(1, 10):
        have = layer | shipped
        seen_files, stack, needed = set(), [], set()
        for p in layer:
            stack.extend(compiled(p))
        while stack:
            f = stack.pop()
            if f in seen_files:
                continue
            seen_files.add(f)
            for rel in includes(f):
                pkg = "/".join(rel.split("/")[:2])
                if pkg not in have and pkg in libs:
                    needed.add(pkg)
                target = os.path.join(R, rel)
                if os.path.exists(target):
                    stack.append(target)
        print(
            f"round {rnd}: {len(layer)} packages, {len(seen_files)} files, {len(needed)} new"
        )
        if not needed:
            break
        for e in sorted(needed):
            print("    +", e)
        added += sorted(needed)
        layer = close(layer | needed) - shipped

    tu = sum(
        tus[(p, "lib")]
        + (tus[(p, "plugins")] if p in plugins and p not in src_only else 0)
        for p in layer
    )
    print(f"\n{len(layer)} packages, {tu} TU ({len(added)} added over the BuildFile graph)")

    if args.write:
        header = [ln for ln in open(listing) if ln.startswith("#")]
        with open(listing, "w") as fh:
            fh.writelines(header)
            fh.write("\n".join(sorted(layer)) + "\n")
        print("wrote", listing)


if __name__ == "__main__":
    main()
