#!/bin/bash
set -euxo pipefail

# The Makefile has no configure step: point it at the conda prefix and let it pick up the
# compilers and flags from the environment.
MAKE_ARGS=(
  CC="${CC}" CXX="${CXX}"
  EXPAT_DIR="${PREFIX}" ZLIB_DIR="${PREFIX}" OPENSSL_DIR="${PREFIX}" PACPARSER_DIR="${PREFIX}"
  CFLAGS="${CFLAGS} -O2" CXXFLAGS="${CXXFLAGS} -O2"
  # the rules that link the executables use only CXXOPT_APP/COPT, so the search paths for the
  # dependencies of libfrontier_client have to go in there
  "COPT=-Wall \$(CFLAGS) -DFRONTIER_DEBUG -fPIC -DPIC ${LDFLAGS}"
  "CXXOPT_APP=-Wall \$(CXXFLAGS) -DFRONTIER_DEBUG -DFNTR_USE_NAMESPACE -DFNTR_USE_EXCEPTIONS -fPIC -DPIC ${LDFLAGS}"
  # the link rules hardcode the compiler name
  'LINK_SO=$(CXX) $(CXXFLAGS) -shared -o libfrontier_client.so.$(FN_VER_MAJOR).$(FN_VER_MINOR) -Wl,-soname,libfrontier_client.so.$(FN_VER_MAJOR)'
  'LINK_DYLIB=$(CXX) $(CXXFLAGS) -dynamiclib -install_name @rpath/libfrontier_client.$(FN_VER_MAJOR).$(FN_VER_MINOR).dylib -compatibility_version $(FN_VER_MAJOR) -current_version $(FN_VER_MAJOR).$(FN_VER_MINOR) -o libfrontier_client.$(FN_VER_MAJOR).$(FN_VER_MINOR).dylib $(LIBS)'
)
# The default LIBS of the Makefile is Linux specific (librt does not exist on macOS).

LIBS="-L${PREFIX}/lib -lexpat -lssl -lcrypto -lz ${LDFLAGS}"
if [[ "${target_platform}" == linux-* ]]; then
  LIBS="${LIBS} -ldl -lrt"
else
  # The Makefile decides between .so and .dylib with `[ -f /usr/lib/libc.dylib ]`. Since Big Sur
  # the system dylibs only exist inside the dyld shared cache, so that test is false on every
  # supported macOS and the build takes the Linux path: it links with -shared and -soname and
  # fails with "ld: unknown option: -soname".
  MAKE_ARGS+=(DYLIBTYPE=dylib)
fi

# the Makefile is not parallel safe: libfrontier_client.so depends on http/.libs,
# which is produced by the separate "htclient" target
make "${MAKE_ARGS[@]}" LIBS="${LIBS}"
make "${MAKE_ARGS[@]}" LIBS="${LIBS}" install distdir="${PREFIX}"

# The Makefile also installs a pure python DB-API client (python/lib/frontier.py). It is not
# used by CORAL or CMSSW, and shipping it would make this package python-version specific.
rm -rf "${PREFIX}/python"
