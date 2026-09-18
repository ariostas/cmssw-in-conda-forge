# DD4hep loads its plugins by itself, not through CMSSW's PluginManager: the CMS detector
# description is a DD4hep plugin library (DD4HEP_PLUGIN=1 in DetectorDescription/DDCMS's
# BuildFile) whose factories DD4hep looks up through its own component registry. It scans the
# directories on one environment variable for `*.components` files and looks nowhere else --
# LD_LIBRARY_PATH on Linux, DYLD_LIBRARY_PATH on macOS, chosen at compile time in
# GaudiPluginService/src/PluginServiceV2.cpp; DD4HEP_LIBRARY_PATH does not exist. CMSSW's copies
# live in the release, which nothing else puts on that path. Without this, the geometry fails at
# runtime with "no factory with name Create(DDDefinition_XML_reader)".
#
# On macOS this only reaches processes the shell starts directly. SIP drops DYLD_* when it
# execs a protected binary, so `cmsRun` works but `some-wrapper.sh` that runs cmsRun does not.
export CMSSW_CONDA_BACKUP_@LIBPATH_VAR@="${@LIBPATH_VAR@:-}"
export @LIBPATH_VAR@="${CONDA_PREFIX}/share/cmssw/@SCRAM_ARCH@/cms/cmssw/@CMSSW_VERSION@/lib/@SCRAM_ARCH@${@LIBPATH_VAR@:+:${@LIBPATH_VAR@}}"
