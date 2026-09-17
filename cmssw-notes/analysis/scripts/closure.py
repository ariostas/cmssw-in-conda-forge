"""Packages a new CMSSW layer needs, given the layers that are already packaged.

usage: closure.py <target> [<target> ...]
  reads _work/pkgs.json (see depgraph.py) and recipes/*/packages.txt

A target package is built completely (src, plugins, bin), or only its library if it is written
as "Subsystem/Package:lib"; everything a target needs is pulled in with its library only.
Packages that an existing layer already provides are dropped.
"""

import json
import os
import sys
from collections import deque

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")


def load_installed():
    installed = {}
    for recipe in sorted(os.listdir(os.path.join(REPO, "recipes"))):
        listing = os.path.join(REPO, "recipes", recipe, "packages.txt")
        if os.path.exists(listing):
            for pkg in open(listing).read().split():
                installed[pkg] = recipe
    return installed


def closure(pkgs, targets):
    """{package: "full"|"lib"} for the targets and everything they build against.

    targets maps a package to "full" or "lib".
    """
    need = dict(targets)
    queue = deque(need.items())
    while queue:
        name, mode = queue.popleft()
        kinds = {"lib", "plugins", "bin"} if mode == "full" else {"lib"}
        for kind, uses in pkgs.get(name, {}).get("uses", {}).items():
            if kind not in kinds:
                continue
            for use in uses:
                if use in pkgs and use not in need:
                    need[use] = "lib"
                    queue.append((use, "lib"))
    return need


def main():
    pkgs = json.load(open(os.path.join(REPO, "_work", "pkgs.json")))
    installed = load_installed()
    targets = {}
    for arg in sys.argv[1:]:
        name, _, mode = arg.partition(":")
        targets[name] = mode or "full"
    unknown = [t for t in targets if t not in pkgs]
    if unknown:
        sys.exit("unknown packages: %s" % ", ".join(unknown))

    need = closure(pkgs, targets)
    new = sorted(p for p in need if p not in installed)
    print(
        "%d targets, %d in the closure, %d already packaged, %d new"
        % (len(targets), len(need), len(need) - len(new), len(new))
    )
    print("%d source files in the new packages" % sum(pkgs[p]["nsrc"] for p in new))
    for p in new:
        print("  %-50s %5d %s" % (p, pkgs[p]["nsrc"], need[p]))


if __name__ == "__main__":
    main()
