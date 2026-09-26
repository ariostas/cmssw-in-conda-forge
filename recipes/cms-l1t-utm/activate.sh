# tmTable validates L1 menu XML against the schemas here
if [ -n "${UTM_XSD_DIR+x}" ]; then
  export CONDA_BACKUP_UTM_XSD_DIR="${UTM_XSD_DIR}"
fi
export UTM_XSD_DIR="${CONDA_PREFIX}/share/cms-l1t-utm"
