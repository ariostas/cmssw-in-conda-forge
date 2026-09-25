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
# Any quoted include. Two forms matter: the full "Sub/Pkg/interface/X.h" that crosses a
# package boundary, and the plain "X.h" that a file in src/ uses for its own siblings.
# Following only the first form means the siblings are never walked and whatever *they*
# include is never seen -- which is how RecoTracker/LSTCore's src/alpaka/Hit.h, and through
# it HeterogeneousCore/AlpakaMath, went missing until the build failed on it.
# Angle brackets count too when the path is a CMSSW package's: DQM/CastorMonitor includes
# its own header as <DQM/CastorMonitor/interface/CastorMonitorModule.h>, and through it
# SimG4CMS/Calo. System headers in angle brackets are not followed.
INC = re.compile(
    r'#\s*include\s+(?:"([^"]+)"|<([A-Za-z][A-Za-z0-9]*/[A-Za-z0-9]+/(?:interface|src|plugins|bin|test)/[^>]+)>)'
)
# Any directory of a package, not only interface/ and src/: plugins include their own headers
# as "Sub/Pkg/plugins/X.h" (Validation/MuonME0Validation, and through it SimMuon/MCTruth).
PKG_INCLUDE = re.compile(
    r"^[A-Za-z][A-Za-z0-9]*/[A-Za-z0-9]+/(?:interface|src|plugins|bin|test)/"
)
# Comments have to go first. CMSSW's doxygen blocks show example code, and the examples
# contain #include lines: PhysicsTools/UtilAlgos/interface/BasicAnalyzer.h documents itself
# with an include of PhysicsTools/PatExamples, which is not a dependency at all and which
# drags in MET, Ecal and the rest of PAT behind it.
COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
# Includes only a GPU build sees. Alpaka sources are compiled once per backend, and their
# CUDA and ROCm branches include HeterogeneousCore/CUDA* and ROCm* packages that a CPU-only
# build never needs; counting them made HeterogeneousCore/AlpakaCore, which cmssw-reco
# builds, look unbuildable.
GPU = re.compile(r"CUDA|ROCM|HIP|GPU|__NVCC__")
DIRECTIVE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$")


def active_includes(text):
    """The quoted includes of `text`, minus those in branches only a GPU build compiles."""
    out, stack = [], []  # stack: whether each enclosing branch is GPU-only
    for line in text.splitlines():
        m = DIRECTIVE.match(line)
        if m:
            kind, cond = m.groups()
            gpu = bool(GPU.search(cond))
            if kind in ("if", "ifdef"):
                stack.append(("pos", gpu))
            elif kind == "ifndef":
                stack.append(("neg", gpu))
            elif kind == "elif" and stack:
                # a GPU condition after a CPU one, or vice versa: judge the branch by its own
                stack[-1] = ("pos", gpu)
            elif kind == "else" and stack:
                sense, g = stack[-1]
                stack[-1] = ("neg" if sense == "pos" else "pos", g)
            elif kind == "endif" and stack:
                stack.pop()
            continue
        if any(sense == "pos" and g for sense, g in stack):
            continue
        m = INC.search(line)
        if m:
            out.append(m.group(1) or m.group(2))
    return out


# Files a layer's patches take out of the build, so what they include does not matter.
# Keep in step with the patches/ directory of the layers that have them, and keep the
# entries specific: "/alpaka/" was used here at first to skip one package's alpaka plugins
# and silently skipped every alpaka directory in the release, which hid
# HeterogeneousCore/AlpakaCore's need for HeterogeneousCore/AlpakaServices until the build
# failed on it.
PATCHED_OUT = (
    "Geometry/CSCGeometryBuilder/plugins/CSCGeometryValidate.cc",
    "Geometry/DTGeometryBuilder/plugins/DTGeometryValidate.cc",
    "Geometry/GEMGeometryBuilder/plugins/GEMGeometryValidate.cc",
    "Geometry/GEMGeometryBuilder/plugins/ME0GeometryValidate.cc",
    "Geometry/RPCGeometryBuilder/plugins/RPCGeometryValidate.cc",
    "RecoTracker/FinalTrackSelectors/plugins/alpaka/",
    "RecoEcal/EgammaCoreTools/src/DeepSCGraphEvaluation.cc",
    "RecoEcal/EgammaCoreTools/src/EcalClustersGraph.cc",
)


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
                text = COMMENTS.sub("", open(path, errors="ignore").read())
                cache[path] = active_includes(text)
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
        seen_files, stack, needed, blocked = set(), [], set(), {}
        for p in layer:
            stack.extend((f, f) for f in compiled(p))
        while stack:
            f, root = stack.pop()
            if f in seen_files:
                continue
            seen_files.add(f)
            for rel in includes(f):
                if PKG_INCLUDE.match(rel):
                    pkg = "/".join(rel.split("/")[:2])
                    if pkg not in have and pkg in libs:
                        needed.add(pkg)
                    elif pkg not in have and pkg in pkgs:
                        # a package that cannot be built: adding it would not help, and
                        # leaving it out means this file does not compile
                        blocked.setdefault(pkg, set()).add(os.path.relpath(root, R))
                    target = os.path.join(R, rel)
                else:
                    # a sibling, relative to the including file
                    target = os.path.normpath(os.path.join(os.path.dirname(f), rel))
                if os.path.exists(target):
                    stack.append((target, root))
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
    print(
        f"\n{len(layer)} packages, {tu} TU ({len(added)} added over the BuildFile graph)"
    )
    if blocked:
        print(
            f"\n{len(blocked)} included packages cannot be built; these files will fail:"
        )
        for pkg in sorted(blocked):
            print(f"  {pkg}:")
            for f in sorted(blocked[pkg]):
                print(f"      {f}")

    if args.write:
        header = [ln for ln in open(listing) if ln.startswith("#")]
        with open(listing, "w") as fh:
            fh.writelines(header)
            fh.write("\n".join(sorted(layer)) + "\n")
        print("wrote", listing)


if __name__ == "__main__":
    main()
