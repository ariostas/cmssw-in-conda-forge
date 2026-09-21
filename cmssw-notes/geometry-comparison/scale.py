"""Is one geometry dump the other scaled by a constant, or do they mix units?

    python3 scale.py conda.txt cvmfs.txt

Reads two outputs of compare.py and reports, for every numeric field, the set of distinct
second/first ratios. A single ratio means the two differ by one unit conversion and nothing
else; several means something is inconsistent.
"""

import re
import sys

NUM = re.compile(r"-?\d+\.?\d*(?:e[-+]?\d+)?")


def numbers(line):
    # only the numeric fields; names and paths must match exactly on their own
    return [
        float(x)
        for x in NUM.findall(
            line.split("TGeoBBox")[-1]
            if "TGeoBBox" in line
            else line[line.find("t=(") :]
        )
    ]


def key(line):
    return line.split("t=(")[0] if "t=(" in line else line.split("TGeoBBox")[0]


def load(path):
    return [line.rstrip() for line in open(path) if line.startswith(("VOL ", "NODE "))]


a, b = load(sys.argv[1]), load(sys.argv[2])
assert len(a) == len(b), (len(a), len(b))

bad_names = 0
ratios = {}
zeros = 0
for la, lb in zip(a, b):
    if key(la) != key(lb):
        bad_names += 1
        if bad_names < 4:
            print("NAME MISMATCH:\n  ", key(la), "\n  ", key(lb))
        continue
    na, nb = numbers(la), numbers(lb)
    assert len(na) == len(nb), (la, lb)
    for x, y in zip(na, nb):
        if x == 0 and y == 0:
            zeros += 1
            continue
        if x == 0 or y == 0:
            print("ZERO MISMATCH:", la, "|", lb)
            continue
        r = round(y / x, 9)
        ratios[r] = ratios.get(r, 0) + 1

print("lines compared:", len(a))
print("name mismatches:", bad_names)
print("numeric fields both zero:", zeros)
print("distinct cvmfs/conda ratios:", ratios)
