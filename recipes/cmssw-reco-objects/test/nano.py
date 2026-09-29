# Build the NanoAOD configuration `cmsDriver.py --step NANO` makes from MiniAOD, for data and
# for simulation, and check that every module and ES module it would run is a registered
# plugin.
#
# Unlike the other tests this one does not go through cmsRun: turning the configuration into
# the framework's parameter sets resolves every FileInPath, and NanoAOD's name files from
# CMS's separate data repositories (e.g. the b-jet energy regression's model, from
# cms-data/PhysicsTools-NanoAOD), which are not packaged yet. Building it in python still
# needs every cff and cfi it imports, including the ones generated from the plugins'
# parameter descriptions during the build.

import subprocess

import FWCore.ParameterSet.Config as cms
from Configuration.Eras.Era_Run3_2025_cff import Run3_2025

plugins = set(subprocess.run(["edmPluginDump"], capture_output=True, text=True, check=True).stdout.split())


def types(process, labels):
    for label in labels:
        module = getattr(process, label)
        if not isinstance(module, cms.EDAlias):
            yield module.type_()


for sequence in ("nanoSequence", "nanoSequenceMC"):
    process = cms.Process("NANO", Run3_2025)
    process.load("PhysicsTools.NanoAOD.nano_cff")
    process.nanoAOD_step = cms.Path(getattr(process, sequence))
    from PhysicsTools.NanoAOD.nano_cff import nanoAOD_customizeCommon

    process = nanoAOD_customizeCommon(process)
    used = set(types(process, process.nanoAOD_step.moduleNames()))
    used |= {module.type_() for module in process.es_producers_().values()}
    used |= {module.type_() for module in process.es_sources_().values()}
    missing = sorted(used - plugins)
    print(sequence, len(process.nanoAOD_step.moduleNames()), "modules of", len(used), "types")
    assert not missing, "not registered: " + ", ".join(missing)
    # the muon and (PUPPI) jet tables, and the cross-linking of PAT objects they read
    for label in ("muonTable", "jetPuppiTable", "finalJetsPuppi", "linkedObjects"):
        assert label in process.nanoAOD_step.moduleNames(), "%s missing from %s" % (label, sequence)

print("NanoAOD configuration built")
