#!/bin/bash
set -euxo pipefail

case "${target_platform}" in
  linux-64)      export SCRAM_ARCH=linux_amd64_gcc ;;
  linux-aarch64) export SCRAM_ARCH=linux_aarch64_gcc ;;
  osx-arm64)     export SCRAM_ARCH=osx_arm64_clang ;;
  *) echo "Unsupported platform ${target_platform}"; exit 1 ;;
esac

CMSSW_VERSION=${CMSSW_TAG}
CMSSW_ROOT=${PREFIX}/share/cmssw
RELEASE_PARENT=${CMSSW_ROOT}/${SCRAM_ARCH}/cms/cmssw
RELEASE=${RELEASE_PARENT}/${CMSSW_VERSION}
STAGE=${SRC_DIR}/stage

# Built plugins and dictionaries are loaded by python scripts during the build, so the
# host python (with ROOT) has to come first in PATH.
export PATH=${PREFIX}/bin:${PATH}

# SCRAM only considers architectures that have a cms-common directory. It needs to contain a
# file, because conda packages do not carry empty directories.
mkdir -p "${CMSSW_ROOT}/${SCRAM_ARCH}/cms/cms-common"
echo "This directory marks ${SCRAM_ARCH} as an available SCRAM architecture (see SCRAM's ProjectDB)." \
  > "${CMSSW_ROOT}/${SCRAM_ARCH}/cms/cms-common/README"

# 1. SCRAM toolbox pointing to the host prefix (templates come from cmssw-toolbox). It holds
#    every tool of this CMSSW release, including ones only used by later layers: the tool files
#    only refer to $PREFIX, so they do not depend on what is installed while building this layer.
cmssw-generate-toolbox "${STAGE}/toolbox" --prefix "${PREFIX}"

# 2. project configuration
cp -R "${SRC_DIR}/config" "${STAGE}/config"
echo "${CMSSW_CONFIG_TAG}" > "${STAGE}/config/config_tag"
python "${STAGE}/config/updateConfig.py" -p CMSSW -v "${CMSSW_VERSION}" -s "${SCRAM_VERSION}" \
  -t "${STAGE}/toolbox" --keys SCRAM_COMPILER=gcc --keys ENABLE_LTO=0 --keys ENABLE_PGO=0 \
  --keys PROJECT_GIT_HASH="${CMSSW_VERSION}"
sed -i.bak -e 's| SCRAM_TARGETS=.*"| SCRAM_TARGETS=""|' \
           -e 's| ALPAKA_BACKENDS=.*"| ALPAKA_BACKENDS="serial"|' "${STAGE}/config/Self.xml"
rm "${STAGE}/config/Self.xml.bak"

# 3. sources of the FWLite packages (same removals as cmsdist's fwlite.spec)
mkdir -p "${STAGE}/src"
while read -r pkg; do
  [ -z "${pkg}" ] && continue
  mkdir -p "${STAGE}/src/$(dirname "${pkg}")"
  cp -R "${SRC_DIR}/cmssw/${pkg}" "${STAGE}/src/${pkg}"
done < "${RECIPE_DIR}/packages.txt"
pushd "${STAGE}/src"
rm -rf ./*/*/test DataFormats/*/plugins Heterogeneous*/*/plugins CommonTools/Utils/plugins \
  CommonTools/Utils/src/TMVAEvaluator.cc FWCore/MessageLogger/python/MessageLogger_cfi.py
# cmsRun. It only becomes useful with the later layers (it needs input, output and services),
# but it has to be built here: a layer that had a src/FWCore/Framework directory would shadow
# this package and its library would drop out of every link line.
# Of the seven executables in FWCore/Framework/bin only the plain one is built; the others
# differ just in the allocator they link (jemalloc, tcmalloc, gperftools).
cat > FWCore/Framework/bin/BuildFile.xml <<'BUILDFILE'
<bin name="cmsRun" file="cmsRun.cpp">
  <use name="tbb"/>
  <use name="boost"/>
  <use name="boost_program_options"/>
  <use name="FWCore/AbstractServices"/>
  <use name="FWCore/Framework"/>
  <use name="FWCore/MessageLogger"/>
  <use name="FWCore/PluginManager"/>
  <use name="FWCore/ServiceRegistry"/>
  <use name="FWCore/Utilities"/>
  <use name="FWCore/ParameterSet"/>
  <use name="FWCore/ParameterSetReader"/>
</bin>
BUILDFILE
popd

# 4. create the release area in its final location and build it
mkdir -p "${RELEASE_PARENT}"
(cd "${STAGE}" && scram project -d "${RELEASE_PARENT}" -b config/bootsrc.xml)
cd "${RELEASE}"
USER_LDFLAGS="-Wl,-rpath,${PREFIX}/lib -L${PREFIX}/lib"
if [[ "${target_platform}" == linux-* ]]; then
  # (on macOS the build rules add the release library directory to the rpaths themselves)
  USER_LDFLAGS="${USER_LDFLAGS} -Wl,-rpath,${RELEASE}/lib/${SCRAM_ARCH} -Wl,-rpath-link,${PREFIX}/lib"
fi
if [[ "${target_platform}" == osx-* ]]; then
  # The EDM class version checks compare ROOT checksums computed on Linux, which differ on macOS
  # for classes with (u)int64_t members ((unsigned) long long instead of (unsigned) long).
  export SCRAM_NOEDM_CHECKS=1
  # The SDK is passed to the compiler explicitly by the toolbox (-isysroot). ROOT's interpreter,
  # which runs during the build, must not see it: conda-forge's ROOT ships system modules built
  # against an older SDK and they conflict with the ones built from a newer SDK.
  env -u SDKROOT -u CONDA_BUILD_SYSROOT scram b -k -j "${CPU_COUNT}" USER_LDFLAGS="${USER_LDFLAGS}" </dev/null
else
  scram b -k -j "${CPU_COUNT}" USER_LDFLAGS="${USER_LDFLAGS}" </dev/null
fi

# 5. clean up build products that are not needed at runtime
# external/ is SCRAM's symlink farm into the prefix, not needed in conda
rm -rf tmp logs objs external test/${SCRAM_ARCH}
find . -name "__pycache__" -type d -prune -exec rm -rf {} +

# macOS: python cannot import a .dylib, and FWCore/PythonParameterSet is an extension module
# (cmsRun reads its configuration through it). The release is built in place here, so the
# libraries this layer built and the release's are the same directory.
if [ "${target_platform}" = "osx-arm64" ]; then
  cmssw-link-python-modules --from "lib/${SCRAM_ARCH}" --to "lib/${SCRAM_ARCH}"
fi

# one plugin cache file per package (see patch 0004)
LIBDIR=lib/${SCRAM_ARCH}
if [ -f "${LIBDIR}/.edmplugincache" ]; then
  mkdir -p "${LIBDIR}/.edmplugincache.d"
  mv "${LIBDIR}/.edmplugincache" "${LIBDIR}/.edmplugincache.d/${PKG_NAME}"
fi

# 6. make the release usable without scram runtime
for exe in bin/${SCRAM_ARCH}/*; do
  ln -s "../share/cmssw/${SCRAM_ARCH}/cms/cmssw/${CMSSW_VERSION}/${exe}" "${PREFIX}/bin/$(basename "${exe}")"
done
echo "${RELEASE}/python" > "${SP_DIR}/cmssw.pth"
echo "${RELEASE}/lib/${SCRAM_ARCH}" >> "${SP_DIR}/cmssw.pth"

for action in activate deactivate; do
  mkdir -p "${PREFIX}/etc/conda/${action}.d"
  sed -e "s|@SCRAM_ARCH@|${SCRAM_ARCH}|g" -e "s|@CMSSW_VERSION@|${CMSSW_VERSION}|g" \
    "${RECIPE_DIR}/${action}.sh" > "${PREFIX}/etc/conda/${action}.d/${PKG_NAME}_${action}.sh"
done
