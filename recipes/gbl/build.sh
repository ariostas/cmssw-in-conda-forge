#!/bin/bash
set -euo pipefail

# The C++ library lives in cpp/. Mille is already installed in the host prefix, so
# find_package(Mille) succeeds and cmake/getMille.cmake never runs -- that fallback clones
# Mille from the network mid-build, which a conda build must not do.

mkdir -p build
cd build

cmake "${SRC_DIR}/cpp" \
  -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="${PREFIX}" \
  -DCMAKE_CXX_STANDARD=20 \
  -DSUPPORT_ROOT=False \
  -DEIGEN3_INCLUDE_DIR="${PREFIX}/include/eigen3" \
  -DCMAKE_VERBOSE_MAKEFILE=ON

cmake --build . -j "${CPU_COUNT}"
cmake --install .
