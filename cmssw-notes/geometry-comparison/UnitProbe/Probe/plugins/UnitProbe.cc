// Print the same geometry quantity three ways: as DD4hep stores it, as the dd4hep unit
// constant this translation unit was compiled with, and as the ratio CMSSW code actually uses
// (value / dd4hep::cm). CMS compiles with DD4HEP_USE_GEANT4_UNITS=1 and conda-forge does not,
// so the first two must differ by ten between the two builds and the third must not.
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/ESTransientHandle.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "Geometry/Records/interface/IdealGeometryRecord.h"
#include "DetectorDescription/DDCMS/interface/DDDetector.h"
#include "DD4hep/Detector.h"
#include "DD4hep/DD4hepUnits.h"

#include "TGeoManager.h"
#include "TGeoNode.h"
#include "TGeoBBox.h"

#include <cstdio>

class UnitProbe : public edm::one::EDAnalyzer<> {
public:
  explicit UnitProbe(const edm::ParameterSet& p)
      : m_tag(p.getParameter<edm::ESInputTag>("DDDetector")), m_token(esConsumes(m_tag)) {}
  void analyze(edm::Event const&, edm::EventSetup const&) override;

private:
  const edm::ESInputTag m_tag;
  const edm::ESGetToken<cms::DDDetector, IdealGeometryRecord> m_token;
};

void UnitProbe::analyze(edm::Event const&, edm::EventSetup const& es) {
  edm::ESTransientHandle<cms::DDDetector> det = es.getTransientHandle(m_token);
  TGeoManager const& geom = det->manager();

  printf("PROBE dd4hep_mm %.9g\n", dd4hep::mm);
  printf("PROBE dd4hep_cm %.9g\n", dd4hep::cm);

  TGeoVolume* top = geom.GetTopVolume();
  TGeoBBox* box = dynamic_cast<TGeoBBox*>(top->GetShape());
  printf("PROBE world_raw_dz %.9g\n", box->GetDZ());
  printf("PROBE world_cmssw_cm_dz %.9g\n", box->GetDZ() / dd4hep::cm);

  // a node a few levels down, so the check is not only about the world volume
  TGeoNode* n = top->GetNode(0);
  for (int i = 0; i < 2 && n && n->GetVolume()->GetNdaughters() > 0; ++i) {
    printf("PROBE node%d_raw_x %.9g\n", i, n->GetMatrix()->GetTranslation()[0]);
    printf("PROBE node%d_cmssw_cm_x %.9g\n", i, n->GetMatrix()->GetTranslation()[0] / dd4hep::cm);
    n = n->GetVolume()->GetNode(0);
  }
}

DEFINE_FWK_MODULE(UnitProbe);
