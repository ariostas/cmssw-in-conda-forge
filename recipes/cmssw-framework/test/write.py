# Write an EDM file with the full framework: EmptySource -> a producer -> PoolOutputModule.
import FWCore.ParameterSet.Config as cms

process = cms.Process("WRITE")
process.source = cms.Source("EmptySource", firstRun=cms.untracked.uint32(1))
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(5))
process.options = cms.untracked.PSet(numberOfThreads=cms.untracked.uint32(1))
process.flag = cms.EDProducer("BooleanProducer", value=cms.bool(True))
process.p = cms.Path(process.flag)
process.out = cms.OutputModule("PoolOutputModule", fileName=cms.untracked.string("test.root"))
process.e = cms.EndPath(process.out)
