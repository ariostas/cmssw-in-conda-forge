#!/bin/bash
set -euo pipefail

case "${target_platform}" in
  linux-64)      export SCRAM_ARCH=linux_amd64_gcc ;;
  linux-aarch64) export SCRAM_ARCH=linux_aarch64_gcc ;;
  osx-arm64)     export SCRAM_ARCH=osx_arm64_clang ;;
  *) echo "Unsupported platform ${target_platform}"; exit 1 ;;
esac

cmssw-build-layer \
  --release "${PREFIX}/share/cmssw/${SCRAM_ARCH}/cms/cmssw/${CMSSW_TAG}" \
  --source "${SRC_DIR}/cmssw" \
  --packages "${RECIPE_DIR}/packages.txt" \
  --src-only "${RECIPE_DIR}/src-only.txt"
