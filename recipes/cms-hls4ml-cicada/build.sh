#!/bin/bash
set -euo pipefail

# The top-level Makefile builds every model version with a sub-make each, passing these down;
# its defaults point at sibling checkouts of hls4mlEmulatorExtras and the HLS types, and its
# install target at lib64/.
make all -j "${CPU_COUNT}" \
  CXXFLAGS="${CXXFLAGS} -O3 -fPIC -std=c++17" \
  INCLUDES="-I${PREFIX}/include/hls4ml -I${PREFIX}/include/ap_types -I${PREFIX}/include" \
  LD_FLAGS="${LDFLAGS} -L${PREFIX}/lib -lemulator_interface"
mkdir -p "${PREFIX}/lib"
cp ${MODEL_PREFIX}_*.so "${PREFIX}/lib/"
