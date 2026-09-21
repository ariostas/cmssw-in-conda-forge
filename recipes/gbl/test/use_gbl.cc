// GBL's headers are included directly by CMSSW (Alignment/ReferenceTrajectories), without
// going through its cmake package, so they have to compile standalone against the installed
// eigen. GblPoint pulls in the Eigen matrix types, which is where a bad include path shows up.
#include "GblPoint.h"
#include "GblTrajectory.h"

int main() {
  Eigen::Matrix<double, 5, 5> jac = Eigen::Matrix<double, 5, 5>::Identity();
  gbl::GblPoint point(jac);
  return 0;
}
