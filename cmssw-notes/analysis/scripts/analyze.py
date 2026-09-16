import json
import sys
import collections

pkgs = json.load(open(sys.argv[1]))
tools = {line.split()[0].lower(): line.split()[1] for line in open(sys.argv[2])}
names = set(pkgs)
lower = {n.lower(): n for n in names}
deps = {}
ext = {}
unknown = collections.Counter()
for p, i in pkgs.items():
    lib_d, all_d, e = set(), set(), set()
    for kind, uses in i["uses"].items():
        for u in uses:
            if u in names or u.lower() in lower:
                t = lower[u.lower()]
                if t != p:
                    all_d.add(t)
                    if kind == "lib":
                        lib_d.add(t)
            elif u.lower() in tools:
                e.add(u.lower())
            else:
                unknown[u] += 1
    deps[p] = {"lib": lib_d, "all": all_d, "nontest": set()}
    ext[p] = e
# non-test deps: lib + plugins + bin
for p, i in pkgs.items():
    s = set()
    for kind, uses in i["uses"].items():
        if kind in ("test",):
            continue
        s |= {
            lower[u.lower()]
            for u in uses
            if u.lower() in lower and lower[u.lower()] != p
        }
    deps[p]["nontest"] = s
print("unknown uses (top):", unknown.most_common(15))
# cycles check via SCC on nontest graph
sys.setrecursionlimit(10000)


def scc(graph):
    idx, low, st, on, res, c = {}, {}, [], set(), [], [0]

    def v(n):
        idx[n] = low[n] = c[0]
        c[0] += 1
        st.append(n)
        on.add(n)
        for m in graph[n]:
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

    for n in graph:
        if n not in idx:
            v(n)
    return res


for key in ("lib", "nontest", "all"):
    g = {p: deps[p][key] for p in pkgs}
    big = [c for c in scc(g) if len(c) > 1]
    print(key, "cycles:", len(big), [sorted(c)[:6] for c in big][:5])
json.dump(
    {
        p: {k: sorted(v) for k, v in d.items()} | {"ext": sorted(ext[p])}
        for p, d in deps.items()
    },
    open(sys.argv[3], "w"),
    indent=1,
)
