"""Parse CMSSW BuildFile.xml files and build a package dependency graph."""

import json
import os
import re
import sys
from collections import defaultdict

SRC = sys.argv[1]
tools = {line.split()[0].lower() for line in open(sys.argv[2])}
use_re = re.compile(r'<\s*use\s+name\s*=\s*"([^"]+)"', re.I)
pkgs = {}
for sub in sorted(os.listdir(SRC)):
    d = os.path.join(SRC, sub)
    if not os.path.isdir(d):
        continue
    for p in sorted(os.listdir(d)):
        pd = os.path.join(d, p)
        if not os.path.isdir(pd):
            continue
        name = f"{sub}/{p}"
        info = {"lib": defaultdict(set), "counts": {}}
        nfiles = 0
        for root, dirs, files in os.walk(pd):
            rel = os.path.relpath(root, pd).split(os.sep)[0]
            for f in files:
                if f.endswith((".cc", ".cpp", ".cxx", ".h", ".C", ".dev.cc", ".cu")):
                    nfiles += 1
                if f == "BuildFile.xml":
                    kind = (
                        rel
                        if rel in ("plugins", "test", "bin")
                        else ("lib" if rel == "." else "other:" + rel)
                    )
                    for u in use_re.findall(
                        open(os.path.join(root, f), errors="replace").read()
                    ):
                        info["lib"][kind].add(u)
        pkgs[name] = {
            "uses": {k: sorted(v) for k, v in info["lib"].items()},
            "nsrc": nfiles,
            "haslib": os.path.isdir(os.path.join(pd, "src")),
            "hasplugins": os.path.isdir(os.path.join(pd, "plugins")),
            "haspython": os.path.isdir(os.path.join(pd, "python")),
        }
json.dump(pkgs, open(sys.argv[3], "w"), indent=1)
print(len(pkgs), "packages")
