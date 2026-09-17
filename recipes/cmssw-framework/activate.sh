# CMSSW expects a CMS site configuration; this points at the one for conda installations
# (see share/cmssw/SITECONF/conda/JobConfig/site-local-config.xml).
export CMSSW_CONDA_BACKUP_SITECONFIG_PATH="${SITECONFIG_PATH:-}"
export SITECONFIG_PATH="${CONDA_PREFIX}/share/cmssw/SITECONF/conda"
