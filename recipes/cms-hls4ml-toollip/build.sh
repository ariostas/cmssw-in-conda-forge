#!/bin/bash
set -euo pipefail

# TOoLLiP_tmp_v bundles Xilinx's HLS headers, two of them proprietary (see ASSUMED-LICENSE.txt).
# The model code never includes that copy -- it finds the headers on the include path -- so it
# is removed rather than left in the build tree.
rm -rf TOoLLiP_tmp_v/NN/ap_types
# The top-level Makefile builds every model version with a sub-make each, passing these down;
# its defaults point at sibling checkouts of hls4mlEmulatorExtras and the HLS types, and its
# install target at lib64/.
make all -j "${CPU_COUNT}" \
  CXXFLAGS="${CXXFLAGS} -O3 -fPIC -std=c++17" \
  INCLUDES="-I${PREFIX}/include/hls4ml -I${PREFIX}/include/ap_types -I${PREFIX}/include" \
  LD_FLAGS="${LDFLAGS} -L${PREFIX}/lib -lemulator_interface"
mkdir -p "${PREFIX}/lib"
for model in TOoLLiP_v1 TOoLLiP_v2 TOoLLiP_v3 TOoLLiP_tmp_v; do
  cp "${model}.so" "${PREFIX}/lib/"
done
