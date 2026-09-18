# Build a detector from the CMS XML with DD4hep and walk it.
#
# The geometry is DetectorDescription/DDCMS's own tree-navigation test, which pulls in the
# 2021 material definitions from Geometry/CMSCommonData: both packages are in this layer, so
# the test needs nothing from outside it. That also makes it the place where the units question
# shows up -- the XML declares its world volume as 5*m, and DD4hep's evaluator turns that into
# 500 with the TGeo units conda-forge builds with, or 5000 with the Geant4 units CMS uses. The
# number only has to be consistent between the library and CMSSW, which it is when neither
# defines DD4HEP_USE_GEANT4_UNITS; see PLAN.md.

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
