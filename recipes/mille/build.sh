#!/bin/bash
set -euo pipefail

# Mille installs its cmake package files into <prefix>/cmake and its fortran .mod into
# <prefix>/modules rather than the usual lib/cmake and include. That is the layout CMS's
# own build produces and the one GBL's find_package(Mille) and CMSSW's mille tool file
# expect, so it is kept rather than relocated.

mkdir -p build
cd build

cmake "${SRC_DIR}" \
  -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="${PREFIX}" \
  -DCMAKE_CXX_STANDARD=20 \
  -DSUPPORT_ROOT=ON \
  -DSUPPORT_ZLIB=ON \
  -DBUILD_TESTS=OFF \
  -DCMAKE_VERBOSE_MAKEFILE=ON

cmake --build . -j "${CPU_COUNT}"
cmake --install .
