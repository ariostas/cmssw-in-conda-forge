#!/bin/bash
# cmssw-devel pulls in the compilers and headers that `scram b` needs; the only files it
# installs are the cmsrel and cmsenv shell functions.
set -euo pipefail

for action in activate deactivate; do
  mkdir -p "${PREFIX}/etc/conda/${action}.d"
  cp "${RECIPE_DIR}/${action}.sh" "${PREFIX}/etc/conda/${action}.d/${PKG_NAME}_${action}.sh"
done
