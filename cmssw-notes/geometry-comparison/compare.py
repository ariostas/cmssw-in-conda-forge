"""Dump the numeric content of a TGeoManager written by DDTestDumpFile."""

import sys
import ROOT

ROOT.gROOT.SetBatch(True)
path = sys.argv[1]
f = ROOT.TFile.Open(path)
keys = [k.GetName() for k in f.GetListOfKeys()]
tags = {k: f.Get(k).GetTitle() for k in keys if k in ("CMSSW_VERSION", "tag")}
f.Close()
print("# file:", path)
print("# keys:", keys, tags)
# Import, not Get: reading the object alone leaves the volume tree unresolved.
geom = ROOT.TGeoManager.Import(path)
assert geom is not None, "no TGeoManager in file"

top = geom.GetTopVolume()
print("top volume:", top.GetName())


def shape_params(sh):
    # the parameters a TGeoBBox-derived shape exposes, plus the class so a shape swap shows up
    out = [sh.ClassName()]
    for attr in ("GetDX", "GetDY", "GetDZ", "GetRmin", "GetRmax", "GetPhi1", "GetDphi"):
        if hasattr(sh, attr):
            try:
                out.append("%s=%.9g" % (attr[3:], getattr(sh, attr)()))
            except Exception:
                pass
    return " ".join(out)


vols = sorted({v.GetName(): v for v in geom.GetListOfVolumes()}.items())
print("n_volumes:", len(vols))
for name, v in vols:
    print("VOL %-28s %s" % (name, shape_params(v.GetShape())))

it = ROOT.TGeoIterator(top)
node = it.Next()
n = 0
paths = []
while node:
    p = ROOT.TString()
    it.GetPath(p)
    m = node.GetMatrix()
    t = m.GetTranslation()
    paths.append(
        "NODE %-52s vol=%-22s t=(%.9g, %.9g, %.9g)"
        % (str(p), node.GetVolume().GetName(), t[0], t[1], t[2])
    )
    n += 1
    node = it.Next()
print("n_nodes:", n)
for line in paths:
    print(line)
