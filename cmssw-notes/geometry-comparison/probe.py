import FWCore.ParameterSet.Config as cms

process = cms.Process("UnitProbe")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))
process.MessageLogger = cms.Service(
    "MessageLogger",
    cerr=cms.untracked.PSet(enable=cms.untracked.bool(False)),
    cout=cms.untracked.PSet(
        enable=cms.untracked.bool(True), threshold=cms.untracked.string("WARNING")
    ),
)
process.DDDetectorESProducer = cms.ESSource(
    "DDDetectorESProducer",
    confGeomXMLFiles=cms.FileInPath(
        "DetectorDescription/DDCMS/data/cms-test-tree-navigation.xml"
    ),
    appendToDataLabel=cms.string(""),
)
process.DDVectorRegistryESProducer = cms.ESProducer(
    "DDVectorRegistryESProducer", appendToDataLabel=cms.string("")
)
process.probe = cms.EDAnalyzer("UnitProbe", DDDetector=cms.ESInputTag("", ""))
process.p = cms.Path(process.probe)
