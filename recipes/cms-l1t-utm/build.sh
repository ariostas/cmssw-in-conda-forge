#!/bin/bash
set -euo pipefail

# The Makefiles take the locations of their dependencies from these (see Makefile.default)
export XERCES_C_BASE=${PREFIX}
export BOOST_BASE=${PREFIX}

./configure
# The Makefiles set CXX=c++ and CXXFLAGS=-std=c++11 -O2 for themselves; use conda's compiler
# and flags instead. C++17 rather than 11: the bundled XSD code is written for C++11 (it uses
# unique_ptr, not auto_ptr), and current boost headers no longer promise C++11 support.
# The build is not parallel-safe across libraries (.NOTPARALLEL), only within one.
make all -j "${CPU_COUNT}" \
  CXX="${CXX}" \
  CXXFLAGS="${CXXFLAGS} -std=c++17 -fPIC -O2" \
  CPPFLAGS="${CPPFLAGS} -DNDEBUG" \
  AR="${CXX} -shared -fPIC ${LDFLAGS}"
make install PREFIX="${PREFIX}"

# The install target puts the XML schemas at the top of the prefix; tmTable reads them at run
# time from $UTM_XSD_DIR, which the activation script sets. menu.xsd is the entry point.
mkdir -p "${PREFIX}/share/cms-l1t-utm"
mv "${PREFIX}"/*.xsd "${PREFIX}/xsd-type" "${PREFIX}/share/cms-l1t-utm/"

for action in activate deactivate; do
  mkdir -p "${PREFIX}/etc/conda/${action}.d"
  cp "${RECIPE_DIR}/${action}.sh" "${PREFIX}/etc/conda/${action}.d/${PKG_NAME}_${action}.sh"
done
