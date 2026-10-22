# Read the file back through PoolSource and run a module over its products.
import FWCore.ParameterSet.Config as cms

process = cms.Process("READ")
process.source = cms.Source(
    "PoolSource",
    # With PoolSource's default cache size. That only works because cmssw-fwlite's activation
    # turns ROOT's automatic TTreeCache setup off (ROOT_TTREECACHE_SIZE=0), as `cmsenv` does;
    # without it ROOT fails with "TTree::SetCacheSizeAux: Not setting up an automatically sized
    # TTreeCache because of missing cache previously set", which CMSSW makes fatal.
    fileNames=cms.untracked.vstring("file:test.root"),
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))
process.options = cms.untracked.PSet(numberOfThreads=cms.untracked.uint32(1))
process.dump = cms.EDAnalyzer("EventContentAnalyzer")
process.p = cms.Path(process.dump)
