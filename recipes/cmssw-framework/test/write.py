# Write an EDM file with the full framework (cmsRun): EmptySource -> PoolOutputModule.
import FWCore.ParameterSet.Config as cms

process = cms.Process("WRITE")
process.source = cms.Source("EmptySource", firstRun=cms.untracked.uint32(1))
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(5))
process.options = cms.untracked.PSet(numberOfThreads=cms.untracked.uint32(1))
process.out = cms.OutputModule("PoolOutputModule", fileName=cms.untracked.string("test.root"))
process.e = cms.EndPath(process.out)
