# CMSSW runtime environment (replaces `cmsenv` for the conda installation)
export CMSSW_CONDA_BACKUP_SCRAM_ARCH="${SCRAM_ARCH:-}"
export CMSSW_CONDA_BACKUP_ROOT_INCLUDE_PATH="${ROOT_INCLUDE_PATH:-}"
export CMSSW_CONDA_BACKUP_ROOT_LIBRARY_PATH="${ROOT_LIBRARY_PATH:-}"
export CMSSW_CONDA_BACKUP_ROOT_TTREECACHE_SIZE="${ROOT_TTREECACHE_SIZE:-}"
export CMSSW_CONDA_BACKUP_ROOT_TTREECACHE_PREFILL="${ROOT_TTREECACHE_PREFILL:-}"

export SCRAM_ARCH=@SCRAM_ARCH@
export CMSSW_VERSION=@CMSSW_VERSION@
export CMSSW_BASE="${CONDA_PREFIX}/share/cmssw/@SCRAM_ARCH@/cms/cmssw/@CMSSW_VERSION@"
export CMSSW_RELEASE_BASE=""
export LOCALRT="${CMSSW_BASE}"
export CMSSW_SEARCH_PATH="${CMSSW_BASE}/src"
export CMSSW_PLUGIN_PATH="${CMSSW_BASE}/lib/@SCRAM_ARCH@"
export ROOT_INCLUDE_PATH="${CMSSW_BASE}/src:${CONDA_PREFIX}/include/eigen3${ROOT_INCLUDE_PATH:+:${ROOT_INCLUDE_PATH}}"
export ROOT_LIBRARY_PATH="${CMSSW_BASE}/lib/@SCRAM_ARCH@${ROOT_LIBRARY_PATH:+:${ROOT_LIBRARY_PATH}}"
# As `cmsenv` does (the root_interface tool file): CMSSW's PoolSource sets up the TTreeCache
# itself, and ROOT's own automatic setup, which these turn off, then fails with "Not setting
# up an automatically sized TTreeCache because of missing cache previously set".
export ROOT_TTREECACHE_SIZE=0
export ROOT_TTREECACHE_PREFILL=0
