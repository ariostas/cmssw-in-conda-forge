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
  --packages "${RECIPE_DIR}/packages.txt"

# CMS site configuration. CMSSW expects to run at a CMS site, which provides a
# site-local-config.xml and a storage description through $SITECONFIG_PATH; a conda
# environment is not one, so ship a "site" that uses the global CMS services.
SITECONF=${PREFIX}/share/cmssw/SITECONF/conda
mkdir -p "${SITECONF}/JobConfig"
cp "${RECIPE_DIR}/siteconf/site-local-config.xml" "${SITECONF}/JobConfig/"
cp "${RECIPE_DIR}/siteconf/storage.json" "${SITECONF}/"

for action in activate deactivate; do
  mkdir -p "${PREFIX}/etc/conda/${action}.d"
  cp "${RECIPE_DIR}/${action}.sh" "${PREFIX}/etc/conda/${action}.d/${PKG_NAME}_${action}.sh"
done
