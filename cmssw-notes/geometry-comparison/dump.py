# Build the DDCMS tree-navigation test geometry and write the TGeoManager to a ROOT file,
# so that the same XML can be compared between CMS's own build and the conda one.
import os
import FWCore.ParameterSet.Config as cms

process = cms.Process("GeometryDump")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

process.MessageLogger = cms.Service(
    "MessageLogger",
    cerr=cms.untracked.PSet(enable=cms.untracked.bool(False)),
    cout=cms.untracked.PSet(
        enable=cms.untracked.bool(True),
        threshold=cms.untracked.string("INFO"),
        noLineBreaks=cms.untracked.bool(True),
        Geometry=cms.untracked.PSet(limit=cms.untracked.int32(-1)),
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
process.dump = cms.EDAnalyzer(
    "DDTestDumpFile",
    DDDetector=cms.ESInputTag("", ""),
    outputFileName=cms.untracked.string(os.environ["DUMP_OUT"]),
    tag=cms.untracked.string(os.environ.get("DUMP_TAG", "unknown")),
)
process.p = cms.Path(process.dump)
