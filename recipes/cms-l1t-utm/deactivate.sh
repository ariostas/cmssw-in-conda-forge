if [ -n "${CONDA_BACKUP_UTM_XSD_DIR+x}" ]; then
  export UTM_XSD_DIR="${CONDA_BACKUP_UTM_XSD_DIR}"
  unset CONDA_BACKUP_UTM_XSD_DIR
else
  unset UTM_XSD_DIR
fi
