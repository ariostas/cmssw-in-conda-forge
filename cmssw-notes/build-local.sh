#!/bin/bash
# Build the CMSSW recipes locally, inside a conda-forge style container or natively (osx).
#
# usage: [WORK=<dir>] build-local.sh <ci-config> [recipe ...]
#   e.g. build-local.sh linux64                       (container, repo mounted at /repo)
#        WORK=_work/osx-work build-local.sh osx_arm64  (natively on macOS)
# ci-config is one of the files in .ci_support (without .yaml). WORK (default /work) must contain
# conda_build_config.yaml (the conda-forge global pinning). Packages are written to $WORK/output,
# which is also used as a channel, so recipes must be given in dependency order.
set -euo pipefail

CONFIG=$1
shift
RECIPES=("$@")
if [ ${#RECIPES[@]} -eq 0 ]; then
  RECIPES=(recipes/cms-scram recipes/cmssw-toolbox recipes/alpaka
           recipes/hls-arbitrary-precision-types cmssw-notes/feedstock-changes/cms-md5
           recipes/frontier-client recipes/coral
           recipes/cmssw-fwlite recipes/cmssw-framework recipes/cmssw-conditions)
fi

WORK=$(mkdir -p "${WORK:-/work}" && cd "${WORK:-/work}" && pwd)
cd "$(dirname "$0")/.."
OUT=${WORK}/output
mkdir -p "${OUT}" "${WORK}/logs"
# use the local output directory as an additional channel
sed "s|^- conda-forge$|- ${OUT},conda-forge|" ".ci_support/${CONFIG}.yaml" > "${WORK}/${CONFIG}_local.yaml"
# only one python version for local testing
printf 'python:\n  - 3.12.* *_cpython\nis_python_min:\n  - false\n' > ${WORK}/local_variants.yaml

# Rebuilding a recipe without bumping its build number reuses the already extracted package
# from rattler's cache, so drop the cached copies of what we are about to rebuild.
PKG_CACHE=${RATTLER_CACHE_DIR:-${HOME}/.cache/rattler/cache}/pkgs

for recipe in "${RECIPES[@]}"; do
  name=$(basename "${recipe}")
  rm -rf "${PKG_CACHE}/${name}-"*
  echo ">> building ${recipe} (log: ${WORK}/logs/${name}-${CONFIG}.log)"
  start=$(date +%s)
  # explicit -m disables the auto-discovery of the recipe's variants.yaml, add it last so it wins
  # $WORK/extra_variants.yaml: machine-specific settings, e.g. CONDA_BUILD_SYSROOT on macOS
  recipe_variants=()
  [ -f "${WORK}/extra_variants.yaml" ] && recipe_variants+=(-m "${WORK}/extra_variants.yaml")
  [ -f "${recipe}/variants.yaml" ] && recipe_variants+=(-m "${recipe}/variants.yaml")
  if rattler-build build --recipe "${recipe}" --output-dir "${OUT}" \
      -m "${WORK}/${CONFIG}_local.yaml" -m ${WORK}/conda_build_config.yaml -m ${WORK}/local_variants.yaml \
      ${recipe_variants[@]+"${recipe_variants[@]}"} \
      > "${WORK}/logs/${name}-${CONFIG}.log" 2>&1; then
    echo "   ok ($(( $(date +%s) - start )) s)"
  else
    echo "   FAILED ($(( $(date +%s) - start )) s)"
    tail -20 "${WORK}/logs/${name}-${CONFIG}.log"
    exit 1
  fi
done
