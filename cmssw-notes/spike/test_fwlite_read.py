"""Read a few events of a remote CMS Open Data MiniAOD file with FWLite."""

import sys

from DataFormats.FWLite import Events, Handle

url = sys.argv[1]
events = Events(url)
muons = Handle("std::vector<pat::io_v1::Muon>")
jets = Handle("std::vector<pat::io_v1::Jet>")
for i, event in enumerate(events):
    event.getByLabel("slimmedMuons", muons)
    event.getByLabel("slimmedJets", jets)
    mu = muons.product()
    print(
        "run %d event %d: %d muons %s, %d jets, leading jet pt %.1f"
        % (
            event.eventAuxiliary().run(),
            event.eventAuxiliary().event(),
            mu.size(),
            ["%.1f" % m.pt() for m in mu],
            jets.product().size(),
            jets.product()[0].pt() if jets.product().size() else -1,
        )
    )
    if i >= 4:
        break
print("FWLite read OK")
