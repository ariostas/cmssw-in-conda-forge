#!/bin/bash
set -euxo pipefail

mkdir build
cd build
cmake -DCMAKE_INSTALL_PREFIX="${PREFIX}" -DCMAKE_INSTALL_LIBDIR="lib" \
      -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON ..
make -j"${CPU_COUNT}"
make test
make install
