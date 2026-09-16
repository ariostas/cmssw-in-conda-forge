#!/bin/bash
# Build the CMSSW recipes locally inside a conda-forge style container.
#
# usage (inside the container, repo mounted at /repo):
#   build-local.sh <ci-config> [recipe ...]
#   e.g. build-local.sh linux64
# ci-config is one of the files in .ci_support (without .yaml). Packages are written to
# /work/output, which is also used as a channel, so recipes must be given in dependency order.
set -euo pipefail

CONFIG=$1
shift
RECIPES=("$@")
if [ ${#RECIPES[@]} -eq 0 ]; then
  RECIPES=(recipes/cms-scram recipes/alpaka recipes/hls-arbitrary-precision-types
           cmssw-notes/feedstock-changes/cms-md5 recipes/cmssw-fwlite)
fi

cd /repo
OUT=/work/output
mkdir -p "${OUT}" /work/logs
# use the local output directory as an additional channel
sed "s|^- conda-forge$|- ${OUT},conda-forge|" ".ci_support/${CONFIG}.yaml" > "/work/${CONFIG}_local.yaml"
# only one python version for local testing
printf 'python:\n  - 3.12.* *_cpython\nis_python_min:\n  - false\n' > /work/local_variants.yaml

for recipe in "${RECIPES[@]}"; do
  name=$(basename "${recipe}")
  echo ">> building ${recipe} (log: /work/logs/${name}-${CONFIG}.log)"
  start=$(date +%s)
  # explicit -m disables the auto-discovery of the recipe's variants.yaml, add it last so it wins
  recipe_variants=()
  [ -f "${recipe}/variants.yaml" ] && recipe_variants=(-m "${recipe}/variants.yaml")
  if rattler-build build --recipe "${recipe}" --output-dir "${OUT}" \
      -m "/work/${CONFIG}_local.yaml" -m /work/conda_build_config.yaml -m /work/local_variants.yaml \
      "${recipe_variants[@]}" \
      > "/work/logs/${name}-${CONFIG}.log" 2>&1; then
    echo "   ok ($(( $(date +%s) - start )) s)"
  else
    echo "   FAILED ($(( $(date +%s) - start )) s)"
    tail -20 "/work/logs/${name}-${CONFIG}.log"
    exit 1
  fi
done
