# The emulator reads its lookup tables from $CSC_TRACK_FINDER_DATA_DIR/L1Trigger/CSCTrackFinder/data;
# the trailing slash is needed, the path is appended as is
if [ -n "${CSC_TRACK_FINDER_DATA_DIR+x}" ]; then
  export CONDA_BACKUP_CSC_TRACK_FINDER_DATA_DIR="${CSC_TRACK_FINDER_DATA_DIR}"
fi
export CSC_TRACK_FINDER_DATA_DIR="${CONDA_PREFIX}/share/cms-csctrackfinderemulation/"
