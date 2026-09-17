# Read the file back through PoolSource and run a module on it.
import FWCore.ParameterSet.Config as cms

process = cms.Process("READ")
process.source = cms.Source("PoolSource", fileNames=cms.untracked.vstring("file:test.root"))
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))
process.dump = cms.EDAnalyzer("EventContentAnalyzer")
process.p = cms.Path(process.dump)
