import json
import collections

deps = json.load(open("_work/deps.json"))
cost = json.load(open("_work/cost.json"))
print("total bytes", sum(c["bytes"] for c in cost.values()) / 1e6, "MB")


def sub(p):
    return p.split("/")[0]


# subsystem aggregation
S = collections.defaultdict(lambda: {"tu": 0, "n": 0})
SG = collections.defaultdict(set)
for p, d in deps.items():
    s = sub(p)
    S[s]["tu"] += cost.get(p, {}).get("tu", 0)
    S[s]["n"] += 1
    for q in d["nontest"]:
        if sub(q) != s:
            SG[s].add(sub(q))
for s in S:
    SG[s]


def sccs(g):
    idx, low, st, on, res, c = {}, {}, [], set(), [], [0]
    import sys

    sys.setrecursionlimit(100000)

    def v(n):
        idx[n] = low[n] = c[0]
        c[0] += 1
        st.append(n)
        on.add(n)
        for m in g[n]:
            if m not in idx:
                v(m)
                low[n] = min(low[n], low[m])
            elif m in on:
                low[n] = min(low[n], idx[m])
        if low[n] == idx[n]:
            comp = []
            while True:
                m = st.pop()
                on.discard(m)
                comp.append(m)
                if m == n:
                    break
            res.append(comp)

    for n in list(g):
        if n not in idx:
            v(n)
    return res


comps = sccs(SG)
print("subsystem SCCs >1:", [sorted(c) for c in comps if len(c) > 1])
for s, v in sorted(S.items(), key=lambda x: -x[1]["tu"]):
    print(f"{s:28s} pkgs={v['n']:4d} TUs={v['tu']:5d}")
# package-level topological depth on lib graph
depth = {}


def dep(p):
    if p in depth:
        return depth[p]
    depth[p] = 0
    depth[p] = 1 + max([dep(q) for q in deps[p]["lib"]] + [-1])
    return depth[p]


for p in deps:
    dep(p)
L = collections.Counter(depth.values())
print("lib depth histogram", sorted(L.items()))


# transitive closure size of lib deps for some key packages
def closure(p, key="lib"):
    seen = set()
    st = [p]
    while st:
        x = st.pop()
        for q in deps[x][key]:
            if q not in seen:
                seen.add(q)
                st.append(q)
    return seen


for p in [
    "FWCore/Framework",
    "DataFormats/PatCandidates",
    "Configuration/StandardSequences",
    "RecoTracker/LST",
    "DataFormats/Common",
]:
    if p in deps:
        c = closure(p, "nontest")
        print(
            p,
            "nontest closure",
            len(c),
            "TUs",
            sum(cost.get(q, {}).get("tu", 0) for q in c),
        )
ext = collections.Counter(e for d in deps.values() for e in d["ext"])
print("ext usage:", ext.most_common(80))
