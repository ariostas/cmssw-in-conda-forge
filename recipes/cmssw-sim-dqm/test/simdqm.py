# Build the validation and DQM output modules from their configuration fragments. As in the
# reconstruction layers' tests nothing is run: constructing the configuration needs every
# cfi it imports and every plugin it names to be registered, but no input data and no
# conditions.
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

producers = process.producers_()
analyzers = process.analyzers_()
print(len(producers), "producers,", len(analyzers), "analyzers")
# DQMEDAnalyzer() makes an EDProducer: DQM modules produce their histograms as products
assert "multiTrackValidator" in producers, "multiTrackValidator missing from the configuration"
print("validation configuration built")
