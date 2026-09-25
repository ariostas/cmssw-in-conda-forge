# Build the unpackers, the calorimeter and muon local reconstruction, particle flow and jet
# clustering from their configuration fragments.
#
# As in cmssw-reco's test, nothing is run: the modules are only constructed, which needs no
# input data and no conditions, but does need every plugin to be registered and every cfi
# they import (some generated from the plugins' parameter descriptions during the build) to
# be there. The fragments were chosen with a walk of their python imports that stays inside
# this layer and the ones below it. The full RawToDigi_cff does not: it reaches the L1
# unpackers, which need the unlicensed utm.

import FWCore.ParameterSet.Config as cms

process = cms.Process("RECO")

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(0))

# RAW to digis
process.load("EventFilter.EcalRawToDigi.ecalDigis_cff")
process.load("EventFilter.HcalRawToDigi.HcalRawToDigi_cfi")
process.load("EventFilter.CSCRawToDigi.cscUnpacker_cfi")
process.load("EventFilter.DTRawToDigi.dtunpacker_cfi")
# local reconstruction
process.load("RecoLocalCalo.Configuration.ecalLocalRecoSequence_cff")
process.load("RecoLocalCalo.Configuration.hcalLocalReco_cff")
process.load("RecoLocalCalo.Configuration.hcalGlobalReco_cff")
process.load("RecoJets.JetProducers.CaloTowerSchemeB_cfi")
process.load("RecoLocalMuon.Configuration.RecoLocalMuon_cff")
# the particle-flow algorithm itself
process.load("RecoParticleFlow.PFProducer.particleFlow_cff")
# jets, and the corrections applied to them
process.load("RecoJets.JetProducers.ak4CaloJets_cfi")
process.load("RecoJets.JetProducers.ak4PFJets_cfi")
process.load("RecoJets.JetProducers.fixedGridRhoProducerFastjet_cfi")
process.load("JetMETCorrections.Configuration.JetCorrectors_cff")

producers = process.producers_()
print(len(producers), "producers,", len(process.es_producers_()), "ES producers")

for name in ("ecalDigis", "hcalDigis", "muonCSCDigis", "muonDTDigis", "ecalMultiFitUncalibRecHit",
             "hbhereco", "towerMaker", "csc2DRecHits", "dt1DRecHits", "particleFlowTmp",
             "ak4CaloJets"):
    assert name in producers, "%s missing from the configuration" % name

print("local reconstruction configuration built")
