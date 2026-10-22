#!/bin/bash
# The CMSSW developer loop, against a release installed as conda packages.
#
# This is the conda equivalent of
#     cmsrel CMSSW_x_y_z && cd CMSSW_x_y_z/src && cmsenv && git cms-addpkg <Pkg> && scram b
# and it checks the part that is easy to get wrong: a package rebuilt in the work area has to
# win over the copy that came with the release, both when linking and when cmsRun loads plugins.
set -euxo pipefail

# -P: on macOS mktemp hands back a path under a symlink, and scram reports the real one
WORK=$(cd "$(mktemp -d)" && pwd -P)
trap 'rm -rf "${WORK}"' EXIT

# cmsrel and cmsenv are shell functions, so they do not survive into this script the way an
# environment variable does; source the file that defines them.
. "${CONDA_PREFIX:-${PREFIX}}/etc/conda/activate.d/cmssw-devel_activate.sh"

# `cmsrel`. scram finds the release through share/cmssw/etc/scramrc/cmssw.map in the prefix.
cd "${WORK}"
scram list -c CMSSW | grep -q "${CMSSW_VERSION}"
cmsrel "${CMSSW_VERSION}"
cd "${CMSSW_VERSION}/src"

# `cmsenv`. This resets CMSSW_BASE to the work area and puts the release below it; everything
# after this point has to come out of the work area first.
cmsenv
test "${CMSSW_BASE}" = "${WORK}/${CMSSW_VERSION}"
test -n "${CMSSW_RELEASE_BASE}"

# `git cms-addpkg FWCore/Modules`, without needing the network or a clone of cmssw: the
# release ships the full source of every package it built.
mkdir -p FWCore
cp -R "${CMSSW_RELEASE_BASE}/src/FWCore/Modules" FWCore/
chmod -R u+w FWCore/Modules

# a change a test can see from the outside (python, because sed -i differs between GNU and BSD)
MARKER="this BooleanProducer was built in the work area"
MARKER="${MARKER}" python3 - <<'PYEOF'
import os

path = "FWCore/Modules/plugins/BooleanProducer.cc"
source = open(path).read()
edited = "#include <iostream>\n" + source.replace(
    "token_(produces<bool>()) {}",
    'token_(produces<bool>()) { std::cout << "%s" << std::endl; }' % os.environ["MARKER"],
)
assert edited.count(os.environ["MARKER"]) == 1, "BooleanProducer.cc is not what this test expects"
open(path, "w").write(edited)
PYEOF
grep -q "${MARKER}" FWCore/Modules/plugins/BooleanProducer.cc

scram b -j "${CPU_COUNT:-2}"

# the plugin was rebuilt into the work area and not into the release
case "${SCRAM_ARCH}" in osx_*) SO=dylib ;; *) SO=so ;; esac
PLUGIN="${CMSSW_BASE}/lib/${SCRAM_ARCH}/pluginFWCoreModulesPlugins.${SO}"
test -f "${PLUGIN}"
grep -qa "${MARKER}" "${PLUGIN}"

# ... and cmsRun loads it in preference to the one in the release
cat > run.py <<'PYEOF'
import FWCore.ParameterSet.Config as cms

process = cms.Process("DEV")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))
process.flag = cms.EDProducer("BooleanProducer", value=cms.bool(True))
process.p = cms.Path(process.flag)
PYEOF
cmsRun run.py 2>&1 | tee run.log
grep -q "${MARKER}" run.log

# Two kinds of package that need more of the toolchain than C++. A CondFormats package, whose
# serialization code SCRAM generates with libclang and the release's clang...
mkdir -p CondFormats
cp -R "${CMSSW_RELEASE_BASE}/src/CondFormats/HIObjects" CondFormats/
chmod -R u+w CondFormats/HIObjects
# ... and one with a Fortran source, compiled with the release's Fortran compiler.
mkdir -p DevloopTest/Fortran/src
cat > DevloopTest/Fortran/BuildFile.xml <<'XMLEOF'
<use name="f77compiler"/>
<export>
  <lib name="1"/>
</export>
XMLEOF
cat > DevloopTest/Fortran/src/answer.f <<'FEOF'
      INTEGER FUNCTION ANSWER()
      ANSWER = 42
      END
FEOF

scram b -j "${CPU_COUNT:-2}"

test -f "${CMSSW_BASE}/lib/${SCRAM_ARCH}/libCondFormatsHIObjects.${SO}"
find "${CMSSW_BASE}/tmp" -path '*CondFormats/HIObjects*' -name '*Serialization*.cc' | grep -q .
python3 -c "import ctypes, sys; sys.exit(ctypes.CDLL(sys.argv[1]).answer_() != 42)" \
  "${CMSSW_BASE}/lib/${SCRAM_ARCH}/libDevloopTestFortran.${SO}"

echo "OK: the work area shadows the installed release, and builds CondFormats and Fortran"
