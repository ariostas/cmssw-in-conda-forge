# Build the core reconstruction modules from their configuration fragments.
#
# Each cfi here is generated from a plugin's parameter definitions during the build, so a
# plugin that did not build, or whose cfi was not generated, fails at this import rather
# than the first time someone tries to reconstruct something. That makes this the test that
# matters for the layer, and it needs no input data and no conditions: nothing is run, the
# modules are only constructed.
#
# The full RecoTracker_cff is deliberately not loaded. It reaches well outside
# reconstruction -- FastSimulation, jets, tau and heavy ion -- through the jet-core seeding
# step and the era customisations, so it cannot be imported until those layers exist. The
# fragments below were checked to stay inside this layer and the ones under it.

import FWCore.ParameterSet.Config as cms

process = cms.Process("RECO")

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(0))

# transient tracking rechit builders: the tracker geometry and the CPEs behind it
process.load("RecoTracker.TransientTrackingRecHit.TTRHBuilders_cff")
# the measurement tracker, which is what pattern recognition navigates
process.load("RecoTracker.MeasurementDet.MeasurementTrackerEventProducer_cfi")
# Kalman filter track finding
process.load("RecoTracker.CkfPattern.CkfTrackCandidates_cfi")
# primary vertices
process.load("RecoVertex.PrimaryVertexProducer.OfflinePrimaryVertices_cfi")
# the muon reconstruction service, which ties the muon geometry to the propagators
process.load("RecoMuon.TrackingTools.MuonServiceProxy_cff")

producers = process.producers_()
es_producers = process.es_producers_()
print(len(producers), "producers,", len(es_producers), "ES producers")

for name in ("MeasurementTrackerEvent", "ckfTrackCandidates", "offlinePrimaryVertices"):
    assert name in producers, "%s missing from the configuration" % name

# the ES producers these need have to be there too, or the modules could never be run
assert any("TransientTrackingRecHitBuilder" in str(type(p)) or "TTRHBuilder" in n
           for n, p in es_producers.items()), "no transient rechit builder configured"

print("reconstruction configuration built")
