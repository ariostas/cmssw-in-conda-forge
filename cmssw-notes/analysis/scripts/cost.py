"""Estimate per-package build cost: translation units + source bytes from compile_commands.json."""

import json
import os
import collections
import re

R = "/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2"
cc = json.load(open(R + "/compile_commands.json"))
tu = collections.Counter()
byts = collections.Counter()
kinds = collections.Counter()
for e in cc:
    f = e["file"]
    m = re.search(r"src/([^/]+/[^/]+)/(.*)", f)
    if not m:
        kinds["nonsrc:" + f[:60]] += 1
        continue
    p = m.group(1)
    rest = m.group(2)
    tu[p] += 1
    kinds[rest.split("/")[0]] += 1
    path = f if f.startswith("/") else os.path.join(R, f)
    try:
        byts[p] += os.path.getsize(path)
    except OSError:
        pass
print(kinds.most_common(12))
json.dump(
    {p: {"tu": tu[p], "bytes": byts[p]} for p in tu},
    open("_work/cost.json", "w"),
    indent=1,
)
print(sum(tu.values()), len(tu))
