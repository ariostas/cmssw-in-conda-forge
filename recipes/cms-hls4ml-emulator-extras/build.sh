#!/bin/bash
set -euo pipefail

# Upstream's hls_stream.h and ap_shift_reg.h are Xilinx's, under a proprietary licence; use
# conda-forge's own implementations instead (see ap_types/ in the recipe).
cp "${RECIPE_DIR}"/ap_types/hls_stream.h "${RECIPE_DIR}"/ap_types/ap_shift_reg.h include/ap_types/

# The Makefile builds libemulator_interface.so with no soname or install name and installs it
# to lib64/, so build it here instead.
if [[ "${target_platform}" == osx-* ]]; then
  soflags="-Wl,-install_name,@rpath/libemulator_interface${SHLIB_EXT}"
else
  # dlopen() is in libdl on glibc 2.17
  soflags="-Wl,-soname,libemulator_interface${SHLIB_EXT} -ldl"
fi
mkdir -p "${PREFIX}/lib"
${CXX} ${CXXFLAGS} -std=c++17 -O3 -fPIC -Iinclude/hls4ml -shared src/hls4ml/emulator.cc \
  -o "${PREFIX}/lib/libemulator_interface${SHLIB_EXT}" ${LDFLAGS} ${soflags}

mkdir -p "${PREFIX}/include"
cp -R include/. "${PREFIX}/include/"
