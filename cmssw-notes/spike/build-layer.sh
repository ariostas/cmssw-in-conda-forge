#!/bin/bash
# Build a layer of CMSSW packages in a developer area on top of an installed release.
#
# usage: build-layer.sh <cmssw-src> <package-list> <workdir> [remove-glob ...]
#   remove-glob: paths (relative to src/) removed after copying, e.g. 'DataFormats/*/plugins'
# env:   PREFIX, SCRAM_ARCH, CMSSW_VERSION, CPU_COUNT (optional)
set -euo pipefail

CMSSW_SRC=$(realpath "$1")
PKG_LIST=$(realpath "$2")
WORKDIR=$3
shift 3

: "${PREFIX:?}" "${SCRAM_ARCH:?}" "${CMSSW_VERSION:?}"
export PATH=${PREFIX}/bin:${PATH}

mkdir -p "${WORKDIR}"
cd "${WORKDIR}"
rm -rf "${CMSSW_VERSION}"
scram project "${CMSSW_VERSION}"
cd "${CMSSW_VERSION}/src"

while read -r pkg; do
  [ -z "${pkg}" ] && continue
  mkdir -p "$(dirname "${pkg}")"
  cp -R "${CMSSW_SRC}/${pkg}" "${pkg}"
done < "${PKG_LIST}"
rm -rf ./*/*/test
for glob in "$@"; do
  # shellcheck disable=SC2086
  rm -rf ${glob}
done

LDFLAGS_RPATH="-Wl,-rpath,${PREFIX}/lib -Wl,-rpath-link,${PREFIX}/lib -L${PREFIX}/lib"
time scram b -k -j "${CPU_COUNT:-$(nproc)}" USER_LDFLAGS="${LDFLAGS_RPATH}"
