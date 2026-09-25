"""How much of CMSSW can be built, given which externals are available.

A package's library can be built when every package library it links against can be built and
every external it uses is available; its plugins additionally need the libraries their own
`uses` list names. Walking that to a fixed point gives the buildable set for a given set of
blocked externals, which is what decides how far the packaging can go -- far more than build
time does.

    python3 cmssw-notes/analysis/scripts/reach.py            # the ladder of scenarios
    python3 cmssw-notes/analysis/scripts/reach.py --layers 1500 \
        --scenario "geometry (dd4hep),L1 menu (unlicensed utm)"

Reads `_work/pkgs.json` (from depgraph.py) and the release's compile_commands.json.
"""

import argparse
import collections
import json
import sys
import os
import re

RELEASE = "/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2"
SHIPPED = [
    "cmssw-fwlite",
    "cmssw-framework",
    "cmssw-conditions",
    "cmssw-geometry",
    "cmssw-reco",
    "cmssw-reco-objects",
]

# Externals that are blocked, and why. The reason doubles as the group name in the ladder:
# unblocking is nearly always an all-or-nothing decision about one upstream problem.
BLOCKED = {
    # dd4hep and dd4hep-core are NOT blocked any more: cmssw-geometry builds against
    # conda-forge's dd4hep, runs, and matches CMS's own build (see cmssw-notes/geometry-
    # comparison).
    #
    # geant4 is not blocked either, as of 2026-09-21. conda-forge ships 11.4.2 and
    # cmssw-geometry already builds and runs against it: Geometry/HGCalCommonData needs it,
    # and the whole Geometry/CaloTopology chain hangs off that package. Keeping it in this
    # list understated reachability by 8 points (54% -> 62%) and, worse, made the reco layer
    # look as though its central packages needed a missing external. What is still unproven
    # is *full simulation* (SimG4Core and friends actually producing hits), which is M6's
    # job; that is a build question like any other, not a missing-external question.
    #
    # dd4hep-geant4 (DDG4) stays blocked until conda-forge's dd4hep is confirmed to ship it.
    "dd4hep-geant4": "simulation (geant4)",
    "utm": "L1 menu (unlicensed utm)",
    # g4hepem and adept are genuinely absent from conda-forge.
    "g4hepemcore": "simulation (geant4)",
    "g4hepemstatic": "simulation (geant4)",
    "adept": "simulation (geant4)",
    # conda-forge has libtensorflow_cc, but its C++ headers are incomplete and cannot be
    # compiled against: tensorflow/core/framework/allocator.h includes
    # "xla/tsl/framework/allocator.h", which the package does not ship in 2.18.0 or 2.19.1
    # (include/xla/tsl holds only protobuf/). So anything that includes tensor.h, which is
    # everything PhysicsTools/TensorFlow does, fails. Checking that session.h existed was
    # not enough; the headers have to be compiled, not listed.
    #
    # This is worth fixing at the feedstock rather than working around: it would unblock
    # RecoTracker's TensorFlow plugins, whose generated cfi the _cff fragments import
    # unconditionally, and with them the full RecoTracker_cff.
    "tensorflow": "ML runtimes",
    "tensorflow-cc": "ML runtimes",
    "tensorflow-runtime": "ML runtimes",
    "tensorflow-xla-runtime": "ML runtimes",
    "tensorflow-xla_compiled_cpu_function": "ML runtimes",
    "tfaot-model-test-multi": "ML runtimes",
    "tfaot-model-test-simple": "ML runtimes",
    "pytorch": "ML runtimes",
    "triton-inference-client": "ML runtimes",
    "AXOL1TL": "L1 ML models",
    "CICADA": "L1 ML models",
    "L1METML": "L1 ML models",
    "NNPuppiTauModel": "L1 ML models",
    "TOoLLiP": "L1 ML models",
    "conifer": "L1 ML models",
    "hls4mLEmulatorExtras": "L1 ML models",
    "hls4mlEmulatorExtras": "L1 ML models",
    "CSCTrackFinderEmulation": "L1 ML models",
    "herwig7": "generators",
    "thepeg": "generators",
    "sherpa": "generators",
    "evtgen": "generators",
    "photospp": "generators",
    "tauolapp": "generators",
    "rivet": "generators",
    "yoda": "generators",
    "pythia6": "generators",
    "pythia6_pdfdummy": "generators",
    "hydjet": "generators",
    "hydjet2": "generators",
    "pyquen": "generators",
    "CepGen": "generators",
    # see PATCHED_USES for RecoJets/JetAlgorithms, which declares ktjet without using it
    "ktjet": "generators",
    "hector": "generators",
    "millepede": "small unpackaged",
    # gbl and mille are packaged (recipes/gbl, recipes/mille) and build on linux-aarch64.
    # They matter out of proportion to their size: RecoTracker/TrackProducer's plugins --
    # the track producer and refitter themselves -- use them through
    # Alignment/ReferenceTrajectories, so without them a reconstruction layer has no way to
    # produce a track.
    "log4cplus": "small unpackaged",
    "clue": "small unpackaged",
    "fftjet": "small unpackaged",
    "sigcpp": "small unpackaged",
    "dablooms": "small unpackaged",
    "xtd": "small unpackaged",
    "TkOnlineSwDB": "small unpackaged",
    "tkonlineswdb": "small unpackaged",
    "pyclang": "small unpackaged",
    "mpi": "small unpackaged",
    "opengl": "small unpackaged",
    "cuda": "GPU and proprietary",
    "cuda-nvml": "GPU and proprietary",
    "cupti": "GPU and proprietary",
    "rocm": "GPU and proprietary",
    "pytorch-cuda": "GPU and proprietary",
    "oracle": "GPU and proprietary",
    "oracleocci": "GPU and proprietary",
    "dcap": "GPU and proprietary",
    "dip": "GPU and proprietary",
}

# <use>s that a layer's patches remove, as (package, product kind) -> uses. The BuildFile
# graph would otherwise count these packages as blocked, and with them everything above them.
PATCHED_USES = {
    # cmssw-reco-objects 0001: declared, but no file in the package includes KtJet; jet
    # clustering is FastJet. Unpatched, this blocks RecoJets/JetProducers and all of jets.
    ("RecoJets/JetAlgorithms", "lib"): {"ktjet"},
    # cmssw-reco-objects 0003: only the DeepSC supercluster evaluator (DeepSCGraphEvaluation,
    # EcalClustersGraph) uses TensorFlow, and the patch leaves those two files out. Unpatched,
    # this one library blocks e/gamma and particle flow, and RecoLocalCalo includes its
    # EcalClusterTools.h.
    ("RecoEcal/EgammaCoreTools", "lib"): {"PhysicsTools/TensorFlow"},
}

# The order the ladder unblocks them in: cheapest and most valuable first.
LADDER = [
    "L1 menu (unlicensed utm)",
    "ML runtimes",
    "L1 ML models",
    "small unpackaged",
    "simulation (geant4)",
    "generators",
    "GPU and proprietary",
]


def load():
    pkgs = json.load(open("_work/pkgs.json"))
    # what the compiled files #include without declaring it (include_graph.py)
    if os.path.exists("_work/include-uses.json"):
        for pkg, kinds in json.load(open("_work/include-uses.json")).items():
            if pkg not in pkgs:
                continue
            for kind, used in kinds.items():
                have = pkgs[pkg]["uses"].setdefault(kind, [])
                have += [u for u in used if u in pkgs and u not in have]
    else:
        print(
            "warning: no _work/include-uses.json, undeclared includes are not counted "
            "(run include_graph.py)",
            file=sys.stderr,
        )
    for (pkg, kind), removed in PATCHED_USES.items():
        uses = pkgs[pkg]["uses"].get(kind, [])
        pkgs[pkg]["uses"][kind] = [u for u in uses if u not in removed]
    names = {n.lower(): n for n in pkgs}
    tus = collections.Counter()
    for entry in json.load(open(RELEASE + "/compile_commands.json")):
        m = re.search(r"src/([^/]+/[^/]+)/([^/]+)/", entry["file"])
        if m:
            kind = {"src": "lib", "test": "test"}.get(m.group(2), "plugins")
            tus[(m.group(1), kind)] += 1
    return pkgs, names, tus


def read_list(path):
    out = []
    for line in open(path):
        line = line.split("#")[0].strip()
        if line:
            out.append(line.split(":")[0])
    return out


def solve(pkgs, names, blocked):
    """The package libraries and plugin sets that can be built without the blocked externals."""

    def resolve(use):
        return use if use in pkgs else names.get(use.lower())

    # Start from everything and take away what cannot be built, until nothing changes. The
    # other direction (add what has all its dependencies) is the same on the BuildFile graph,
    # which is acyclic for libraries, but not once undeclared includes are counted: headers
    # include each other across packages in cycles, which are harmless when the packages
    # are built together and would keep every member of a cycle out forever.
    libs, changed = set(pkgs), True
    while changed:
        changed = False
        for p in sorted(libs):
            for use in pkgs[p]["uses"].get("lib", []):
                q = resolve(use)
                if (use in blocked) if q is None else (q != p and q not in libs):
                    libs.discard(p)
                    changed = True
                    break
    plugins = set()
    for p in libs:
        uses = pkgs[p]["uses"].get("plugins", []) + pkgs[p]["uses"].get("bin", [])
        if all(
            (resolve(u) in libs) if resolve(u) else (u not in blocked) for u in uses
        ):
            plugins.add(p)
    return libs, plugins


def count_tus(tus, libs, plugins):
    n = sum(tus[(p, "lib")] for p in libs)
    return n + sum(tus[(p, "plugins")] for p in plugins)


def ladder(pkgs, names, tus, total):
    groups = collections.defaultdict(set)
    for ext, reason in BLOCKED.items():
        groups[reason].add(ext)
    print(f"{'scenario':46s} {'libs':>5s} {'plugins':>8s} {'TU':>7s} {'share':>7s}")
    unblocked = set()
    for label in ["today"] + LADDER:
        unblocked |= groups.get(label, set())
        libs, plugins = solve(pkgs, names, set(BLOCKED) - unblocked)
        n = count_tus(tus, libs, plugins)
        prefix = "today" if label == "today" else "+ " + label
        print(
            f"{prefix:46s} {len(libs):5d} {len(plugins):8d} {n:7d} {100 * n / total:6.0f}%"
        )


def components(graph):
    """The strongly connected components of `graph`, in an order where each follows its
    dependencies (Tarjan, iterative: the recursive form overflows on this graph).

    Neighbours are visited in sorted order. Python randomises string hashing per process, so
    iterating the adjacency sets directly made the component order -- and through it the whole
    layer partition -- differ from run to run, by as much as 50 packages in the first layer.
    """
    index, stack, on_stack, order, out = {}, [], set(), {}, []
    counter = 0
    for root in graph:
        if root in index:
            continue
        work = [(root, iter(sorted(graph[root])))]
        index[root] = order[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, it = work[-1]
            for nxt in it:
                if nxt not in index:
                    index[nxt] = order[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(graph[nxt]))))
                    break
                if nxt in on_stack:
                    order[node] = min(order[node], index[nxt])
            else:
                work.pop()
                if order[node] == index[node]:
                    group = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        group.append(w)
                        if w == node:
                            break
                    out.append(frozenset(group))
                if work:
                    parent = work[-1][0]
                    order[parent] = min(order[parent], order[node])
    return out


def target_layer(pkgs, names, tus, blocked, subsystems):
    """The dependency closure of whole subsystems, minus what the shipped layers already own.

    `--layers` packs the buildable frontier greedily, which fills its budget with whatever
    happens to be ready: asking it for 1500 TU gives a slice of 79 subsystems, from Fireworks
    to TopQuarkAnalysis, that is not about anything. A layer is easier to justify, to test and
    to name when it is chosen by what it is *for*, so this takes the subsystems a layer is
    meant to deliver and adds exactly what they need.

    Prints the package list, then the packages that have nothing to compile (they only carry
    XML, python or headers) for src-only.txt, then the ones whose plugins need something
    blocked -- those are the layer's real decisions, because `--src-only` drops a package's
    whole plugins/ directory and cannot keep some of its plugin libraries and not others.
    """
    libs, plugins = solve(pkgs, names, blocked)
    shipped = set()
    for recipe in SHIPPED:
        shipped |= set(read_list(f"recipes/{recipe}/packages.txt"))

    def deps_of(p):
        uses = pkgs[p]["uses"].get("lib", [])
        if p in plugins:
            uses += pkgs[p]["uses"].get("plugins", []) + pkgs[p]["uses"].get("bin", [])
        out = set()
        for use in uses:
            q = use if use in pkgs else names.get(use.lower())
            if q and q in libs:
                out.add(q)
        return out

    seen = {p for p in libs if p.split("/")[0] in subsystems}
    stack = list(seen)
    while stack:
        for q in deps_of(stack.pop()):
            if q not in seen:
                seen.add(q)
                stack.append(q)

    new = sorted(seen - shipped)
    src_only, blocked_plugins = [], []
    for p in new:
        if tus[(p, "lib")] == 0 and tus[(p, "plugins")] == 0:
            src_only.append(p)
        elif tus[(p, "plugins")] and p not in plugins:
            blocked_plugins.append(p)
    tu = sum(
        tus[(p, "lib")] + (tus[(p, "plugins")] if p in plugins else 0) for p in new
    )
    print(f"# {len(new)} packages, {tu} TU, closure of {' '.join(sorted(subsystems))}")
    print("\n".join(new))
    print(f"\n# nothing to compile ({len(src_only)}), for src-only.txt:")
    print("\n".join("  " + p for p in src_only))
    print(f"\n# plugins need a blocked external ({len(blocked_plugins)}):")
    for p in blocked_plugins:
        print(f"  {p} ({tus[(p, 'plugins')]} plugin TU)")


def partition(pkgs, names, tus, blocked, budget, dump=None):
    """Greedily pack the buildable packages into layers of at most `budget` TUs.

    A layer may only contain packages whose dependencies are in the same or an earlier layer,
    which is what `cmssw-install-layer` needs: each layer builds against the ones below it.

    A package is one node, not two. Its `src/` library and its `plugins/` cannot be split
    across layers, because a layer is a developer area and `src/<Sub>/<Pkg>` in one of those
    is the local definition of the whole package: the release's library for it would drop out
    of every link line. That makes the graph cyclic -- CMSSW has a handful of package cycles
    that run through plugins, which are harmless when everything builds in one area -- so
    cycles are condensed into single nodes, which simply means those packages share a layer.
    """
    libs, plugins = solve(pkgs, names, blocked)
    shipped = set()
    for recipe in SHIPPED:
        shipped |= set(read_list(f"recipes/{recipe}/packages.txt"))

    graph = {}
    for p in sorted(libs):
        uses = pkgs[p]["uses"].get("lib", [])
        if p in plugins:
            uses = (
                uses
                + pkgs[p]["uses"].get("plugins", [])
                + pkgs[p]["uses"].get("bin", [])
            )
        out = set()
        for use in uses:
            q = use if use in pkgs else names.get(use.lower())
            if q and q != p and q in libs:
                out.add(q)
        graph[p] = out

    groups = components(graph)
    cycles = sum(1 for g in groups if len(g) > 1)
    if cycles:
        biggest = max(len(g) for g in groups)
        print(f"  ({cycles} package cycles condensed, largest {biggest} packages)")
    cost = {
        g: sum(
            tus[(p, "lib")] + (tus[(p, "plugins")] if p in plugins else 0) for p in g
        )
        for g in groups
    }
    deps = {
        g: {h for h in groups if h is not g and any(graph[p] & h for p in g)}
        for g in groups
    }

    placed = {g: 0 for g in groups if g <= shipped}
    todo = [g for g in groups if g not in placed]
    layer = 1
    while todo:
        batch, total, growing = [], 0, True
        while growing:
            growing = False
            for g in todo:
                if g in placed or g in batch:
                    continue
                if all(d in placed or d in batch for d in deps[g]):
                    if total + cost[g] > budget and batch:
                        continue
                    batch.append(g)
                    total += cost[g]
                    growing = True
        if not batch:
            print(f"  cannot place {len(todo)} groups; a partly shipped cycle?")
            break
        for g in batch:
            placed[g] = layer
        todo = [g for g in todo if g not in placed]
        members = sorted(p for g in batch for p in g)
        subs = collections.Counter(p.split("/")[0] for p in members)
        print(
            f"  layer {layer:2d}: {len(members):4d} packages {total:5d} TU   "
            f"{' '.join(s for s, _ in subs.most_common(5))}"
        )
        if layer == dump:
            print("\n".join(sorted(members)))
        layer += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--layers", type=int, metavar="TU_BUDGET", help="also propose a layer partition"
    )
    ap.add_argument(
        "--scenario", default="today", help="'today', 'full', or a reason from BLOCKED"
    )
    ap.add_argument(
        "--dump",
        type=int,
        metavar="N",
        help="print the package list of layer N, one per line, for packages.txt",
    )
    ap.add_argument(
        "--target",
        metavar="SUB,SUB",
        help="print the layer that delivers these subsystems and their dependencies",
    )
    args = ap.parse_args()

    pkgs, names, tus = load()
    total = count_tus(tus, set(pkgs), set(pkgs))
    print(f"{len(pkgs)} packages, {total} translation units excluding test/\n")
    ladder(pkgs, names, tus, total)

    blocked = set(BLOCKED)
    if args.scenario == "full":
        blocked = set()
    elif args.scenario != "today":
        keep = {
            e for e, reason in BLOCKED.items() if reason in args.scenario.split(",")
        }
        blocked -= keep

    if args.layers:
        print(f"\nlayers of at most {args.layers} TU, scenario '{args.scenario}':")
        partition(pkgs, names, tus, blocked, args.layers, args.dump)

    if args.target:
        print(f"\nscenario '{args.scenario}':")
        target_layer(pkgs, names, tus, blocked, set(args.target.split(",")))


if __name__ == "__main__":
    main()
