"""Check a layer before building it, since finding these by compiling costs an hour each.

Three things go wrong silently when a layer's lists are edited by hand:

  * a package whose plugins need a blocked external is neither in src-only.txt nor covered
    by one of the layer's patches, so the build dies somewhere in the middle;
  * an external nobody wrote a tool file for, which SCRAM reports only as
    "****WARNING: Invalid tool <name>" at configure time and then as undefined references
    minutes later;
  * packages.txt not closed over the headers its sources include (see includes.py).

    python3 cmssw-notes/analysis/scripts/preflight.py recipes/cmssw-reco
"""

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reach  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    layer_dir = sys.argv[1].rstrip("/")

    pkgs, names, tus = reach.load()
    libs, plugins = reach.solve(pkgs, names, set(reach.BLOCKED))
    layer = set(reach.read_list(os.path.join(layer_dir, "packages.txt")))
    so_file = os.path.join(layer_dir, "src-only.txt")
    src_only = set(reach.read_list(so_file)) if os.path.exists(so_file) else set()

    # what the layer's patches take out of the build, read from the patches themselves
    patched = set()
    for p in glob.glob(os.path.join(layer_dir, "patches", "*.patch")):
        for m in re.finditer(r"^--- a/([A-Za-z0-9]+/[A-Za-z0-9]+)/", open(p).read(), re.M):
            patched.add(m.group(1))

    bad = []
    for p in sorted(layer):
        if p in src_only or p in patched:
            continue
        if tus[(p, "plugins")] and p not in plugins:
            bad.append((p, tus[(p, "plugins")]))

    have = {
        os.path.basename(f)[: -len(".xml.in")].lower()
        for f in glob.glob("recipes/cmssw-toolbox/tools*/*.xml.in")
    }
    missing_tools = {}
    for p in layer:
        kinds = ("lib",) if p in src_only else ("lib", "plugins", "bin")
        for kind in kinds:
            for u in pkgs[p]["uses"].get(kind, []):
                if u in pkgs or u.lower() in names:
                    continue
                if u.lower() not in have:
                    missing_tools.setdefault(u.lower(), set()).add(p)
    # an external only the patched-out products need is not actually missing
    missing_tools = {
        e: v for e, v in missing_tools.items() if not v <= (patched | src_only)
    }

    print(f"{len(layer)} packages, {len(src_only)} src-only, {len(patched)} patched")
    if bad:
        print(f"\n{len(bad)} packages whose plugins cannot build and are not src-only or patched:")
        for p, n in bad:
            print(f"  {p}  ({n} plugin TU)")
    if missing_tools:
        print(f"\n{len(missing_tools)} externals with no tool file:")
        for e in sorted(missing_tools):
            print(f"  {e:22s} {sorted(missing_tools[e])[:3]}")
    if not bad and not missing_tools:
        print("\nok")
    return 1 if (bad or missing_tools) else 0


if __name__ == "__main__":
    sys.exit(main())
