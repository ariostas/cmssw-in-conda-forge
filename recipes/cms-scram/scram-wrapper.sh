#!/bin/bash
# conda wrapper for SCRAM: always use the python3 from the same environment.
# Installed as <prefix>/share/scram/bin/scram, called from <prefix>/bin/scram.
scram_bin=$(dirname "$(realpath "$0")")
cmd_python3="${scram_bin}/../../../bin/python3"
[ -x "${cmd_python3}" ] || cmd_python3=$(command -v python3)
if [ "${SCRAMRT_SET}" = "" ] ; then
  export SCRAMV3_BACKUP_LD_LIBRARY_PATH=${LD_LIBRARY_PATH}
  export LD_LIBRARY_PATH=""
fi
unset SCRAM_RUNTIME_TYPE
unset SCRAM_RTBOURNE_SET
PYTHONPATH="" exec "${cmd_python3}" "${scram_bin}/scram.py" "$@"
