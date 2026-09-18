# DD4hep loads its plugins by itself, not through CMSSW's PluginManager: the CMS detector
# description is a DD4hep plugin library (DD4HEP_PLUGIN=1 in DetectorDescription/DDCMS's
# BuildFile) whose factories DD4hep looks up through its own component registry. It finds the
# libraries holding that registry on LD_LIBRARY_PATH and nowhere else -- DD4HEP_LIBRARY_PATH
# does not work with conda-forge's build -- and CMSSW's copies live in the release, which
# nothing else puts on that path. Without this, the geometry fails at runtime with
# "no factory with name Create(DDDefinition_XML_reader)".
export CMSSW_CONDA_BACKUP_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/share/cmssw/@SCRAM_ARCH@/cms/cmssw/@CMSSW_VERSION@/lib/@SCRAM_ARCH@${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
