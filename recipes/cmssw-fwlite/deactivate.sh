unset CMSSW_VERSION CMSSW_BASE CMSSW_RELEASE_BASE LOCALRT CMSSW_SEARCH_PATH CMSSW_PLUGIN_PATH
for var in SCRAM_ARCH ROOT_INCLUDE_PATH ROOT_LIBRARY_PATH; do
  backup="CMSSW_CONDA_BACKUP_${var}"
  if [ -n "${!backup:-}" ]; then
    export "${var}=${!backup}"
  else
    unset "${var}"
  fi
  unset "${backup}"
done
