"""Like partition.py, but splits each package into a 'lib' node (src/) and a 'plugins' node (plugins/, bin/).
Nothing links against plugins, so plugins only need their deps' libs to be in same-or-earlier groups."""

import json
import collections
import re

exec(
    open("cmssw-notes/analysis/scripts/partition.py")
    .read()
    .split("pref = {}")[0]
    .split("deps = json.load")[0]
)
deps = json.load(open("_work/deps.json"))
cost = json.load(open("_work/cost.json"))
pkgs = json.load(open("_work/pkgs.json"))
GROUPS = eval(
    re.search(
        r"GROUPS = (\[.*?\n\])",
        open("cmssw-notes/analysis/scripts/partition.py").read(),
        re.S,
    ).group(1)
)
# per-kind TU counts
R = "/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2"
cc = json.load(open(R + "/compile_commands.json"))
kt = collections.Counter()
for e in cc:
    m = re.search(r"src/([^/]+/[^/]+)/([^/]+)/", e["file"])
    if m:
        kt[
            (
                m.group(1),
                "lib"
                if m.group(2) == "src"
                else ("test" if m.group(2) == "test" else "plugins"),
            )
        ] += 1
pref = {s: i for i, (_, subs) in enumerate(GROUPS) for s in subs}
g = {}
for p in deps:
    g[(p, "lib")] = g[(p, "plugins")] = pref[p.split("/")[0]]


def ndeps(p, kind):
    kinds = ("lib",) if kind == "lib" else ("plugins", "bin", "lib")
    s = set()
    for k in kinds:
        for u in pkgs[p]["uses"].get(k, []):
            for q in deps:
                pass
    return s


# rebuild uses with resolution
lower = {n.lower(): n for n in deps}
res = {}
for p in deps:
    for kind, kinds in (("lib", ("lib",)), ("plugins", ("plugins", "bin"))):
        s = set()
        for k in kinds:
            for u in pkgs[p]["uses"].get(k, []):
                q = lower.get(u.lower())
                if q and q != p:
                    s.add((q, "lib"))
        if kind == "plugins":
            s.add((p, "lib"))
        res[(p, kind)] = s
changed = True
while changed:
    changed = False
    for n, s in res.items():
        m = max([g[x] for x in s] + [g[n]])
        if m != g[n]:
            g[n] = m
            changed = True
tot = collections.Counter()
cnt = collections.Counter()
for (p, kind), gi in g.items():
    tot[gi] += kt[(p, kind)]
    cnt[gi] += 1 if kt[(p, kind)] else 0
for i, (name, _) in enumerate(GROUPS):
    print(f"{i} {name:26s} nodes={cnt[i]:4d} TUs={tot[i]:5d}")
print("tests (not assigned):", sum(v for (p, k), v in kt.items() if k == "test"))
lp = [p for p in deps if g[(p, "lib")] != g[(p, "plugins")] and kt[(p, "plugins")]]
print("packages whose plugins land in a later group than their lib:", len(lp))
json.dump(
    {f"{p}:{k}": GROUPS[v][0] for (p, k), v in g.items() if kt[(p, k)] or k == "lib"},
    open("_work/partition2.json", "w"),
    indent=1,
    sort_keys=True,
)
