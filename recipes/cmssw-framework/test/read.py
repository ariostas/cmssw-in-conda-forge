# Read the file back through PoolSource and run a module over its products.
import FWCore.ParameterSet.Config as cms

process = cms.Process("READ")
process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring("file:test.root"),
    # cacheSize=0 disables ROOT's TTreeCache. With the default size, PoolSource sets a cache
    # size on the Events tree and then detaches the cache it created; ROOT's one-shot
    # automatic cache setup then finds a size but no cache and reports an error, which
    # CMSSW turns into a fatal exception ("TTree::SetCacheSizeAux: Not setting up an
    # automatically sized TTreeCache because of missing cache previously set").
    # See PLAN.md; this needs to be understood with CMS before the package is released.
    cacheSize=cms.untracked.uint32(0),
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))
process.options = cms.untracked.PSet(numberOfThreads=cms.untracked.uint32(1))
process.dump = cms.EDAnalyzer("EventContentAnalyzer")
process.p = cms.Path(process.dump)
