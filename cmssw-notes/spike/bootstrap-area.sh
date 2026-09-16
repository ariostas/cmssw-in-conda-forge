#!/bin/bash
# Bootstrap a SCRAM release area for a subset of CMSSW packages (spike version of what
# the cmssw-* recipes will do). Mirrors cmsdist's scram-project-build.file.
#
# usage: bootstrap-area.sh <cmssw-src> <cmssw-config-src> <package-list> <area-parent>
# env:   PREFIX (conda env with externals + cms-scram), SCRAM_ARCH, CMSSW_VERSION
set -euo pipefail

CMSSW_SRC=$(realpath "$1")
CONFIG_SRC=$(realpath "$2")
PKG_LIST=$(realpath "$3")
AREA_PARENT=$4
REPO=$(cd "$(dirname "$0")/../.." && pwd)

: "${PREFIX:?}" "${SCRAM_ARCH:?}" "${CMSSW_VERSION:?}"
export PATH=${PREFIX}/bin:${PATH}

STAGE=$(mktemp -d)
trap 'rm -rf "${STAGE}"' EXIT

# 1. SCRAM toolbox for this environment
"${REPO}/recipes/cmssw-fwlite/toolbox/cmssw-generate-toolbox" "${STAGE}/toolbox" --prefix "${PREFIX}" \
  --templates "${REPO}/recipes/cmssw-fwlite/toolbox/tools"

# 2. project configuration
cp -R "${CONFIG_SRC}" "${STAGE}/config"
rm -rf "${STAGE}/config/.git"
(cd "${STAGE}/config" && patch -p1 < "${REPO}/recipes/cmssw-fwlite/cmssw-config-patches/0001-conda-build-environment-fixes.patch")
echo "V09-09-09" > "${STAGE}/config/config_tag"
"${STAGE}/config/updateConfig.py" -p CMSSW -v "${CMSSW_VERSION}" -s V3_00_95 -t "${STAGE}/toolbox" \
  --keys SCRAM_COMPILER=gcc --keys ENABLE_LTO=0 --keys ENABLE_PGO=0 --keys PROJECT_GIT_HASH="${CMSSW_VERSION}"
# no multi-microarch builds, no GPU backends
sed -i -e 's| SCRAM_TARGETS=.*"| SCRAM_TARGETS=""|' \
       -e 's| ALPAKA_BACKENDS=.*"| ALPAKA_BACKENDS="serial"|' "${STAGE}/config/Self.xml"

# 3. sources: only the selected packages, without tests
mkdir -p "${STAGE}/src"
while read -r pkg; do
  [ -z "${pkg}" ] && continue
  mkdir -p "${STAGE}/src/$(dirname "${pkg}")"
  cp -R "${CMSSW_SRC}/${pkg}" "${STAGE}/src/${pkg}"
  rm -rf "${STAGE}/src/${pkg}/test"
done < "${PKG_LIST}"

# 4. create the release area
mkdir -p "${AREA_PARENT}"
rm -rf "${AREA_PARENT:?}/${CMSSW_VERSION}"
(cd "${STAGE}" && scram project -d "$(realpath "${AREA_PARENT}")" -b config/bootsrc.xml)
echo "Created ${AREA_PARENT}/${CMSSW_VERSION}"
