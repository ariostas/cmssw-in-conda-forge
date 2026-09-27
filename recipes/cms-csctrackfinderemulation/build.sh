#!/bin/bash
set -euo pipefail

# The makefile sets its own compiler, GCC-only flags (-fipa-pta) and -msse3; use conda's
# compiler and flags instead, keeping upstream's -O1: the generated sources are tens of
# thousands of lines each.
if [[ "${target_platform}" == osx-* ]]; then
  soflags="-Wl,-install_name,@rpath/libCSCTrackFinderEmulation.dylib"
else
  soflags="-Wl,-soname,libCSCTrackFinderEmulation.so"
fi
make all -j "${CPU_COUNT}" \
  CXX="${CXX}" \
  CXXFLAGS="${CXXFLAGS} -fPIC -O1 -pthread -std=c++14" \
  LDFLAGS="-shared ${LDFLAGS} ${soflags}"

mkdir -p "${PREFIX}/lib"
cp lib64/libCSCTrackFinderEmulation${SHLIB_EXT} "${PREFIX}/lib/"

# CMSSW includes <L1Trigger/CSCTrackFinder/src/core_*/vpp_generated.h>. Upstream installs
# them to include/ of its own prefix; here they get a directory of their own, so that a
# L1Trigger/ tree does not appear in the shared include/.
dest="${PREFIX}/include/cms-csctrackfinderemulation/L1Trigger/CSCTrackFinder"
mkdir -p "${dest}"
(cd L1Trigger/CSCTrackFinder && find src -name '*.h' | while read -r h; do
  mkdir -p "${dest}/$(dirname "${h}")"
  cp "${h}" "${dest}/${h}"
done)

mkdir -p "${PREFIX}/share/cms-csctrackfinderemulation/L1Trigger/CSCTrackFinder"
cp -R L1Trigger/CSCTrackFinder/data "${PREFIX}/share/cms-csctrackfinderemulation/L1Trigger/CSCTrackFinder/"

for action in activate deactivate; do
  mkdir -p "${PREFIX}/etc/conda/${action}.d"
  cp "${RECIPE_DIR}/${action}.sh" "${PREFIX}/etc/conda/${action}.d/${PKG_NAME}_${action}.sh"
done
