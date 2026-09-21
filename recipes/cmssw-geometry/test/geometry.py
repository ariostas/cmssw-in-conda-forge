# Build a detector from the CMS XML with DD4hep and walk it.
#
# The geometry is DetectorDescription/DDCMS's own tree-navigation test, which pulls in the
# 2021 material definitions from Geometry/CMSCommonData: both packages are in this layer, so
# the test needs nothing from outside it. It is also where the units question showed up: DD4hep
# stores this geometry in centimetres here and in millimetres in CMS's build, because CMS sets
# DD4HEP_USE_GEANT4_UNITS and conda-forge's DD4hep does not. That is a difference in storage
# only; the dd4hep unit constants move with it, so everything CMSSW reads is identical. Checked
# against CMS's own build of this release -- see cmssw-notes/geometry-comparison/.

import FWCore.ParameterSet.Config as cms

process = cms.Process("GeometryTest")

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
    confGeomXMLFiles=cms.FileInPath("DetectorDescription/DDCMS/data/cms-test-tree-navigation.xml"),
    appendToDataLabel=cms.string(""),
)

process.DDVectorRegistryESProducer = cms.ESProducer(
    "DDVectorRegistryESProducer", appendToDataLabel=cms.string("")
)

process.test = cms.EDAnalyzer("DDCMSDetector", DDDetector=cms.ESInputTag("", ""))

process.p = cms.Path(process.test)
