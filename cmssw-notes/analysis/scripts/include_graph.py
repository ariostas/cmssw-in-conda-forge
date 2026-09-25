"""Record, for every package, which other packages its compiled files reach by #include.

BuildFiles do not declare everything a package includes: in one SCRAM area every package's
interface/ is on the include path, so a header can be used without a <use>. `reach.py`
walks the BuildFile graph, and so counted packages as buildable whose sources include a
header from a package that is not -- RecoMET/METAlgorithms includes L1Trigger/CSCTrackFinder,
which needs the unlicensed utm, and the build is the first to notice. This walks the include
graph of the whole release once, the way includes.py does for a single layer, and writes the
result where reach.load() merges it into the BuildFile uses.

    python3 cmssw-notes/analysis/scripts/include_graph.py   # writes _work/include-uses.json

Rerun it when PATCHED_OUT in includes.py changes. Takes a few minutes on CVMFS.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from includes import COMMENTS, PATCHED_OUT, PKG_INCLUDE, R, active_includes  # noqa: E402

OUT = "_work/include-uses.json"


def main():
    cache = {}

    def includes(path):
        if path not in cache:
            try:
                text = COMMENTS.sub("", open(path, errors="ignore").read())
                cache[path] = active_includes(text)
            except OSError:
                cache[path] = []
        return cache[path]

    # packages reached from one file, memoised: headers are shared across the release
    reached = {}

    def reach_from(f, stack=()):
        if f in reached:
            return reached[f]
        if f in stack:
            return set()
        out = set()
        for rel in includes(f):
            if PKG_INCLUDE.match(rel):
                out.add("/".join(rel.split("/")[:2]))
                target = os.path.join(R, rel)
            else:
                target = os.path.normpath(os.path.join(os.path.dirname(f), rel))
            if os.path.exists(target):
                out |= reach_from(target, stack + (f,))
        reached[f] = out
        return out

    result = {}
    subs = sorted(d for d in os.listdir(R) if os.path.isdir(os.path.join(R, d)))
    for sub in subs:
        for pkg in sorted(os.listdir(os.path.join(R, sub))):
            name = f"{sub}/{pkg}"
            entry = {}
            for kind in ("src", "plugins", "bin"):
                found = set()
                for root, _, files in os.walk(os.path.join(R, sub, pkg, kind)):
                    for n in files:
                        if n.endswith((".cc", ".cpp", ".c", ".cu")):
                            f = os.path.join(root, n)
                            if not any(m in f for m in PATCHED_OUT):
                                found |= reach_from(f)
                found.discard(name)
                if found:
                    entry["lib" if kind == "src" else kind] = sorted(found)
            if entry:
                result[name] = entry
    json.dump(result, open(OUT, "w"), indent=1, sort_keys=True)
    print(f"{len(result)} packages, {len(cache)} files read, wrote {OUT}")


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
