#!/bin/bash
set -euo pipefail

cp "${BUILD_PREFIX}"/share/gnuconfig/config.* cfg/

# Every optional compression and hashing library is enabled rather than stripped out of the
# Makefile the way cmsdist does: conda-forge has all of them, and a library that links what
# it uses does not leave undefined symbols for CMSSW's link lines to resolve.
opts=()
for ext in zlib bz2lib lzma lzo openssl pcre; do
  opts+=("--with-${ext}-includes=${PREFIX}/include" "--with-${ext}-libraries=${PREFIX}/lib")
done
./configure --prefix="${PREFIX}" --disable-static "${opts[@]}"

# The Makefile's own CXXFLAGS add -Werror, which newer compilers trip over in code that
# predates them (-Wcast-function-type on signal handlers). -ansi is kept: it is how CMS
# builds the library.
make -j "${CPU_COUNT}" CXXFLAGS="${CXXFLAGS} -ansi"
make install
rm -f "${PREFIX}/lib/libclasslib.la"
