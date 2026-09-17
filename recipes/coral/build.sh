#!/bin/bash
set -euxo pipefail

case "${target_platform}" in
  linux-64)      export SCRAM_ARCH=linux_amd64_gcc ;;
  linux-aarch64) export SCRAM_ARCH=linux_aarch64_gcc ;;
  osx-arm64)     export SCRAM_ARCH=osx_arm64_clang ;;
  *) echo "Unsupported platform ${target_platform}"; exit 1 ;;
esac

STAGE=${SRC_DIR}/stage
AREA=${SRC_DIR}/area/${CORAL_VERSION}

export PATH=${PREFIX}/bin:${PATH}

# 1. SCRAM toolbox and project configuration. CORAL is a SCRAM project like CMSSW, and
#    cmssw-config carries its project definition (Projects/CORAL).
cmssw-generate-toolbox "${STAGE}/toolbox" --prefix "${PREFIX}"
cp -R "${SRC_DIR}/config" "${STAGE}/config"
echo "${CMSSW_CONFIG_TAG}" > "${STAGE}/config/config_tag"
python "${STAGE}/config/updateConfig.py" -p CORAL -v "${CORAL_VERSION}" -s "${SCRAM_VERSION}" \
  -t "${STAGE}/toolbox" --keys SCRAM_COMPILER=gcc --keys ENABLE_LTO=0 --keys ENABLE_PGO=0
sed -i.bak -e 's| SCRAM_TARGETS=.*"| SCRAM_TARGETS=""|' "${STAGE}/config/Self.xml"
rm "${STAGE}/config/Self.xml.bak"

# 2. sources. Oracle and MySQL are proprietary/unneeded, the CORAL server and the LFC replica
#    service are not used by CMSSW, and the tests need cppunit.
mkdir -p "${STAGE}/src"
cp -R "${SRC_DIR}/coral/." "${STAGE}/src/"
pushd "${STAGE}/src"
rm -rf OracleAccess MySQLAccess CORAL_SERVER LFCReplicaService Tests ./*/tests logs cmt ./*/cmt
popd

# 3. build
mkdir -p "$(dirname "${AREA}")"
(cd "${STAGE}" && scram project -d "$(dirname "${AREA}")" -b config/bootsrc.xml)
cd "${AREA}"
USER_LDFLAGS="-Wl,-rpath,${PREFIX}/lib -L${PREFIX}/lib"
if [[ "${target_platform}" == linux-* ]]; then
  USER_LDFLAGS="${USER_LDFLAGS} -Wl,-rpath-link,${PREFIX}/lib"
fi
scram b -k -j "${CPU_COUNT}" USER_LDFLAGS="${USER_LDFLAGS}" </dev/null

# 4. install into the normal conda layout, so that CORAL does not need a SCRAM area at runtime.
#    CMSSW refers to the libraries through plain SCRAM tool files (see cmssw-toolbox).
#    The CORAL project puts its products in <arch>/lib and <arch>/python.
mkdir -p "${PREFIX}/lib" "${PREFIX}/include"
cp -a "${SCRAM_ARCH}"/lib/liblcg_* "${PREFIX}/lib/"
# the include product store is a farm of symlinks into src/
cp -RL include/LCG "${PREFIX}/include/"
# PyCoral: the python module is the library itself, imported as "coral"
if [ -f "${PREFIX}/lib/liblcg_PyCoral${SHLIB_EXT}" ]; then
  mkdir -p "${SP_DIR}"
  ln -s "../../../lib/liblcg_PyCoral${SHLIB_EXT}" "${SP_DIR}/coral${SHLIB_EXT}"
fi
