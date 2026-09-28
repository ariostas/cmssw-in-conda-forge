# Build the validation and DQM output modules from their configuration fragments. As in the
# reconstruction layers' tests nothing is run: constructing the configuration needs every
# cfi it imports and every plugin it names to be registered, but no input data and no
# conditions. The exceptions are CICADA and TOoLLiP, whose models are loaded as their modules
# are built.
#
# The mixing module and its digitisers are not loaded: their parameters name files from CMS's
# separate data repositories (SimTracker/SiStripDigitizer/data/APVProbaList.txt, from
# cms-data/SimTracker-SiStripDigitizer), which are not packaged yet. The recipe checks the
# digitiser plugins are registered instead.

import FWCore.ParameterSet.Config as cms

process = cms.Process("VALIDATION")

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(0))

# the tracking validation that compares reconstructed tracks with simulated ones
process.load("Validation.RecoTrack.MultiTrackValidator_cfi")
# DQM's own output format, on an end path so that the module is actually constructed and
# writes its (empty) file
process.dqmOut = cms.OutputModule("DQMRootOutputModule", fileName=cms.untracked.string("dqm.root"))
process.out = cms.EndPath(process.dqmOut)

# The L1 calorimeter trigger's anomaly score, which loads its hls4ml model (CICADAModel_*.so,
# from cms-hls4ml-cicada) by name when it is constructed. On a path, so that it is.
process.load("L1Trigger.L1TCaloLayer1.simCaloStage2Layer1Summary_cfi")
process.cicada = cms.Path(process.simCaloStage2Layer1Summary)
# The same for the Phase-2 L1 long-lived particle jet tagger (TOoLLiP_v1.so, from
# cms-hls4ml-toollip), from the cfi generated from the plugin's parameter description.
process.load("L1Trigger.Phase2L1ParticleFlow.TOoLLiPProducer_cfi")
process.toollip = cms.Path(process.TOoLLiPProducer)

producers = process.producers_()
analyzers = process.analyzers_()
print(len(producers), "producers,", len(analyzers), "analyzers")
# DQMEDAnalyzer() makes an EDProducer: DQM modules produce their histograms as products
assert "multiTrackValidator" in producers, "multiTrackValidator missing from the configuration"
assert "simCaloStage2Layer1Summary" in producers, "CICADA missing from the configuration"
assert "TOoLLiPProducer" in producers, "TOoLLiP missing from the configuration"
print("validation configuration built")
