#!/bin/bash
set -euo pipefail

case "${target_platform}" in
  linux-64)      export SCRAM_ARCH=linux_amd64_gcc ;;
  linux-aarch64) export SCRAM_ARCH=linux_aarch64_gcc ;;
  osx-arm64)     export SCRAM_ARCH=osx_arm64_clang ;;
  *) echo "Unsupported platform ${target_platform}"; exit 1 ;;
esac

PACKAGES=${RECIPE_DIR}/packages.txt
if [[ "${target_platform}" == osx-* ]]; then
  grep -vxF -f <(grep -v '^#' "${RECIPE_DIR}/skip-osx.txt") "${PACKAGES}" > "${SRC_DIR}/packages.txt"
  PACKAGES=${SRC_DIR}/packages.txt
fi

cmssw-build-layer \
  --release "${PREFIX}/share/cmssw/${SCRAM_ARCH}/cms/cmssw/${CMSSW_TAG}" \
  --source "${SRC_DIR}/cmssw" \
  --packages "${PACKAGES}" \
  --src-only "${RECIPE_DIR}/src-only.txt"
