# The two commands a CMSSW developer expects. On a CVMFS installation they come from
# cmsset_default.sh; here they belong to cmssw-devel, because both only make sense once you
# can actually build something. They have to be shell functions: cmsenv changes the caller's
# environment.

# cmsrel: make a work area on top of the installed release. `cmsrel` with no argument uses the
# release this environment provides, which is the only one it has.
cmsrel() {
  scram project "${@:-${CMSSW_VERSION}}"
}

# cmsenv: switch to the work area you are standing in. scram works this out from $PWD, so this
# has to run in the caller's shell and from inside the area.
cmsenv() {
  local runtime
  if ! runtime=$(scram runtime -sh); then
    echo "cmsenv: not inside a CMSSW work area (try 'cmsrel ${CMSSW_VERSION}' first)" >&2
    return 1
  fi
  eval "${runtime}"
}
