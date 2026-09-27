// The library finds its lookup tables through CSC_TRACK_FINDER_DATA_DIR, which the activation
// script sets, and fails with an exception rather than a crash when it is not set.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>

std::string FileInPath_wrapper(const char* r);

int main() {
  std::string path = FileInPath_wrapper("L1Trigger/CSCTrackFinder/data/core_2014_05_15/comp_dphi_5.dat");
  std::printf("%s\n", path.c_str());
  if (!std::ifstream(path).good())
    return 1;
  unsetenv("CSC_TRACK_FINDER_DATA_DIR");
  try {
    FileInPath_wrapper("x");
  } catch (std::runtime_error const& e) {
    std::printf("unset: %s\n", e.what());
    return 0;
  }
  return 1;
}
