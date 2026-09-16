"""Assign CMSSW packages to ordered build groups (future conda packages).

g(p) = max(preferred(p), max g(dep) for non-test deps). Packages in an SCC share a group.
"""

import json
import collections
import sys

deps = json.load(open("_work/deps.json"))
cost = json.load(open("_work/cost.json"))
GROUPS = [
    (
        "core",
        [
            "FWCore",
            "Utilities",
            "FWStorage",
            "FWIO",
            "IOPool",
            "PerfTools",
            "IgTools",
            "HeterogeneousCore",
            "DQMServices",
            "IORawData",
            "Documentation",
        ],
    ),
    (
        "dataformats",
        [
            "DataFormats",
            "SimDataFormats",
            "AnalysisDataFormats",
            "FastSimDataFormats",
            "TBDataFormats",
            "CondFormats",
            "CalibFormats",
        ],
    ),
    (
        "conditions-geometry",
        [
            "CondCore",
            "Geometry",
            "GeometryReaders",
            "DetectorDescription",
            "MagneticField",
            "CalibCalorimetry",
            "CalibTracker",
            "CalibMuon",
            "CalibPPS",
            "RecoLuminosity",
            "CondTools",
            "OnlineDB",
        ],
    ),
    (
        "common-reco",
        [
            "CommonTools",
            "TrackingTools",
            "TrackPropagation",
            "RecoCaloTools",
            "RecoVertex",
            "RecoLocalTracker",
            "RecoLocalCalo",
            "RecoLocalMuon",
            "RecoLocalFastTime",
            "EventFilter",
            "RecoTracker",
            "RecoMTD",
            "RecoPPS",
            "RecoHGCal",
            "RecoTICL",
            "RecoRomanPot",
        ],
    ),
    ("l1-hlt", ["L1Trigger", "L1TriggerConfig", "L1TriggerScouting", "HLTrigger"]),
    (
        "reco",
        [
            "RecoEcal",
            "RecoEgamma",
            "RecoMuon",
            "RecoJets",
            "RecoMET",
            "RecoParticleFlow",
            "RecoTauTag",
            "RecoBTag",
            "RecoBTau",
            "RecoHI",
            "RecoML",
            "JetMETCorrections",
            "EgammaAnalysis",
            "PhysicsTools",
            "TopQuarkAnalysis",
            "HeavyFlavorAnalysis",
            "MuonAnalysis",
            "TauAnalysis",
            "AnalysisAlgos",
            "JetMETAnalysis",
            "HeavyIonsAnalysis",
        ],
    ),
    (
        "sim-gen",
        [
            "SimGeneral",
            "SimG4Core",
            "SimG4CMS",
            "SimCalorimetry",
            "SimTracker",
            "SimMuon",
            "SimFastTiming",
            "SimPPS",
            "SimTransport",
            "SimRomanPot",
            "Mixing",
            "IOMC",
            "GeneratorInterface",
            "FastSimulation",
            "SLHCUpgradeSimulations",
        ],
    ),
    (
        "dqm-validation-alignment",
        [
            "DQM",
            "DQMOffline",
            "Validation",
            "HLTriggerOffline",
            "L1TriggerOffline",
            "DPGAnalysis",
            "Alignment",
            "Calibration",
            "CaloOnlineTools",
            "RecoTBCalo",
            "HeterogeneousTest",
            "Fireworks",
            "Configuration",
            "BigProducts",
        ],
    ),
]
pref = {}
for i, (_, subs) in enumerate(GROUPS):
    for s in subs:
        pref[s] = i
missing = {p.split("/")[0] for p in deps} - set(pref)
assert not missing, missing
g = {p: pref[p.split("/")[0]] for p in deps}
changed = True
while changed:
    changed = False
    for p, d in deps.items():
        m = max([g[q] for q in d["nontest"]] + [g[p]])
        if m != g[p]:
            g[p] = m
            changed = True
tot = collections.Counter()
n = collections.Counter()
moved = collections.defaultdict(list)
for p in deps:
    tu = cost.get(p, {}).get("tu", 0)
    tot[g[p]] += tu
    n[g[p]] += 1
    if g[p] != pref[p.split("/")[0]]:
        moved[(pref[p.split("/")[0]], g[p])].append((p, tu))
for i, (name, _) in enumerate(GROUPS):
    print(f"{i} {name:26s} pkgs={n[i]:4d} TUs={tot[i]:5d}")
for (a, b), ps in sorted(moved.items()):
    print(
        f"moved {GROUPS[a][0]} -> {GROUPS[b][0]}: {len(ps)} pkgs, {sum(t for _, t in ps)} TUs:",
        ", ".join(p for p, _ in sorted(ps, key=lambda x: -x[1])[:12]),
    )
if len(sys.argv) > 1:
    json.dump(
        {p: GROUPS[g[p]][0] for p in deps},
        open(sys.argv[1], "w"),
        indent=1,
        sort_keys=True,
    )
