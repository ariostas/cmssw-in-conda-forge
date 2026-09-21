# Import the standard tracking configuration and build the reconstruction sequences.
#
# This is the test that matters for this layer. Loading RecoTracker_cff imports the
# generated cfi of every tracking plugin, so a plugin that failed to build, or whose
# parameter definitions were not generated, shows up here rather than the first time someone
# tries to reconstruct something. It is also what forced TensorFlow into the layer: the
# iterative tracking fragments import mkFitOutputConverter_cfi and the TensorFlow track
# classifiers unconditionally, whether or not mkFit is the one a process modifier selects,
# so without them this import fails outright.
#
# It needs no input data and no conditions: nothing is run, the process is only built.

import FWCore.ParameterSet.Config as cms

process = cms.Process("RECO")

process.load("RecoTracker.Configuration.RecoTracker_cff")
process.load("RecoVertex.Configuration.RecoVertex_cff")
process.load("RecoMuon.Configuration.RecoMuon_cff")

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(0))

producers = process.producers_()
es_producers = process.es_producers_()
print("tracking configuration built:", len(producers), "producers,", len(es_producers), "ES producers")

# the modules the iterative tracking sequence is actually made of
for name in ("initialStepTrackCandidates", "generalTracks", "offlinePrimaryVertices"):
    assert name in producers, "%s missing from the configuration" % name
