#!/bin/bash
# Build a toy model library the way the CMS model packages build theirs, load it through the
# emulator interface, and exercise the replacement hls::stream and ap_shift_reg.
set -euxo pipefail
cd test
INC="-I${PREFIX}/include/hls4ml -I${PREFIX}/include/ap_types -I${PREFIX}/include"
${CXX} ${CXXFLAGS} -std=c++17 -fPIC ${INC} -shared toy_model.cpp -o ToyModel_v1.so \
  ${LDFLAGS} -L${PREFIX}/lib -lemulator_interface
${CXX} ${CXXFLAGS} -std=c++17 ${INC} main.cpp -o toy-test \
  ${LDFLAGS} -L${PREFIX}/lib -Wl,-rpath,${PREFIX}/lib -lemulator_interface
./toy-test
