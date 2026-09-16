"""Externals (SCRAM tools) needed by a set of CMSSW packages, following tool->tool <use> edges."""

import json
import re
import sys
import os

TOOLDIR = "/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2/config/toolbox/el9_amd64_gcc13/tools/selected"
pkgs = json.load(open("_work/pkgs.json"))
names = {n.lower(): n for n in pkgs}
pset = [
    line.strip()
    for line in open(sys.argv[1])
    if line.strip() and not line.startswith("#")
]
kinds = sys.argv[2].split(",") if len(sys.argv) > 2 else ["lib", "plugins", "bin"]
tooluse = {}
for f in os.listdir(TOOLDIR):
    t = open(os.path.join(TOOLDIR, f)).read()
    m = re.search(r'<tool name="([^"]+)" version="([^"]+)"(?: path="([^"]*)")?', t)
    if m:
        tooluse[m.group(1).lower()] = (
            m.group(2),
            m.group(3),
            [u.lower() for u in re.findall(r'<use name="([^"]+)"', t)],
        )
need, direct = set(), set()
for p in pset:
    if p not in pkgs:
        continue
    for k in kinds:
        for u in pkgs[p]["uses"].get(k, []):
            if u.lower() not in names:
                direct.add(u.lower())
stack = list(direct)
while stack:
    t = stack.pop()
    if t in need:
        continue
    need.add(t)
    stack += tooluse.get(t, (None, None, []))[2]
for t in sorted(need):
    v, path, _ = tooluse.get(t, ("?", "", []))
    print(
        f"{t:28s} {v:14s} {'direct' if t in direct else 'indirect':9s} {(path or '').replace('/cvmfs/cms.cern.ch/el9_amd64_gcc13/', '')}"
    )
