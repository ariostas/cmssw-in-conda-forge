"""One-time conversion of CMS's resolved SCRAM tool files into conda templates.

Reads the tool files of a CVMFS release, keeps the requested tools (plus the
tools they <use>), and rewrites them so that every external lives in @PREFIX@.
The output is a starting point that gets edited by hand afterwards.

usage: python3 cvmfs_tools_to_templates.py <outdir> <tool> [<tool> ...]
"""

import os
import re
import sys

TOOLDIR = (
    "/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2/"
    "config/toolbox/el9_amd64_gcc13/tools/selected"
)

outdir = sys.argv[1]
wanted = [t.lower() for t in sys.argv[2:]]

tools = {}
for f in os.listdir(TOOLDIR):
    text = open(os.path.join(TOOLDIR, f)).read()
    m = re.search(r'<tool name="([^"]+)"', text)
    if m:
        tools[m.group(1).lower()] = (f, text)

selected, stack = set(), list(wanted)
while stack:
    t = stack.pop()
    if t in selected or t not in tools:
        if t not in tools:
            print("WARNING: unknown tool", t)
        continue
    selected.add(t)
    stack += [u.lower() for u in re.findall(r'<use name="([^"]+)"', tools[t][1])]

os.makedirs(outdir, exist_ok=True)
for t in sorted(selected):
    f, text = tools[t]
    # every external is installed in the conda prefix
    text = re.sub(r'path="/cvmfs/[^"]*"', 'path="@PREFIX@"', text)
    text = re.sub(
        r"/cvmfs/cms.cern.ch/[^\"'\s]*?/(external|lcg|cms)/[^/\"'\s]+/[^/\"'\s]+",
        "@PREFIX@",
        text,
    )
    # conda uses lib, not lib64
    text = text.replace("$TOOL_BASE/lib64", "$TOOL_BASE/lib")
    text = text.replace("python3.12", "python@PYTHON_VERSION@")
    open(os.path.join(outdir, f + ".in"), "w").write(text)
print(len(selected), "tools written:", " ".join(sorted(selected)))
