# Build the unpackers, the calorimeter and muon local reconstruction, particle flow and jet
# clustering from their configuration fragments.
#
# As in cmssw-reco's test, nothing is run: the modules are only constructed, which needs no
# input data and no conditions, but does need every plugin to be registered and every cfi
# they import (some generated from the plugins' parameter descriptions during the build) to
# be there. The fragments were chosen with a walk of their python imports that stays inside
# this layer and the ones below it. The full RawToDigi_cff does not: it reaches the Stage-2
# L1 unpackers, whose plugins need the L1 ML models.

import FWCore.ParameterSet.Config as cms

process = cms.Process("RECO")

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(0))

# RAW to digis
process.load("EventFilter.EcalRawToDigi.ecalDigis_cff")
process.load("EventFilter.HcalRawToDigi.HcalRawToDigi_cfi")
process.load("EventFilter.CSCRawToDigi.cscUnpacker_cfi")
process.load("EventFilter.DTRawToDigi.dtunpacker_cfi")
# the RPC and legacy L1 unpackers, which need the L1 menu library (cms-l1t-utm, used on the
# assumption that it will be released under Apache-2.0). Their cfis import ones generated
# from the plugins' parameter descriptions.
process.load("EventFilter.RPCRawToDigi.rpcUnpacker_cfi")
process.load("EventFilter.L1GlobalTriggerRawToDigi.l1GtUnpack_cfi")
process.load("EventFilter.GctRawToDigi.l1GctHwDigis_cfi")
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

for name in ("ecalDigis", "hcalDigis", "muonCSCDigis", "muonDTDigis", "rpcunpacker",
             "l1GtUnpack", "l1GctHwDigis", "ecalMultiFitUncalibRecHit", "hbhereco", "towerMaker",
             "csc2DRecHits", "dt1DRecHits", "rpcRecHits", "particleFlowTmp", "ak4CaloJets"):
    assert name in producers, "%s missing from the configuration" % name

print("local reconstruction configuration built")
