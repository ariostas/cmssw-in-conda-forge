# CMSSW in conda-forge

This repo is a fork of conda-forge/staged-recipes used only for packaging CMSSW (CMS experiment
software) for conda-forge. `PLAN.md` holds the plan, the decisions and the progress log. Read it
first, and add to its progress log (section 6) when something significant is learned.

## Layout

- `recipes/`: rattler-build (v1 `recipe.yaml`) recipes. `example-v1/` and `example-v0-deprecated/`
  are upstream staged-recipes examples; leave them alone.
  - `cms-scram`: the SCRAM build tool (noarch).
  - `alpaka`, `hls-arbitrary-precision-types`: header-only dependencies (noarch).
  - `cmssw-fwlite`: FWLite built from `CMSSW_20_1_0_pre2`. It contains:
    - `packages.txt`: CMSSW packages to build;
    - `patches/`: CMSSW source patches;
    - `cmssw-config-patches/`: patches to cms-sw/cmssw-config;
    - `toolbox/`: SCRAM tool file templates plus the `cmssw-generate-toolbox` generator;
    - `variants.yaml`: ROOT/CLHEP pins for this CMSSW version;
    - activation scripts.
- `cmssw-notes/`
  - `research/`: background reports (SCRAM internals, conda-forge dependency survey, prior art).
  - `analysis/scripts/`: BuildFile.xml dependency graph, build cost and partitioning scripts.
    They read `_work/` and the CVMFS release.
  - `spike/`: scripts for hand-building SCRAM areas outside rattler-build.
  - `feedstock-changes/`: recipes whose real fix goes to an existing feedstock (e.g. `cms-md5`),
    not to staged-recipes.
  - `build-local.sh`: builds recipes in order into `/work/output` inside a container.
- `_work/` (git-ignored): clones of cmsdist, cmssw-config, SCRAM and pkgtools, plus analysis outputs.

## Reference material

- CVMFS is mounted on this machine, e.g. `/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2`
  (full `src/`, `config/toolbox/.../tools/selected/*.xml` for resolved tool files,
  `compile_commands.json`). Reads are slow; keep scans targeted.
- The versions used by the release are SCRAM `V3_00_95` (commit `21a9cd1`; there is no git tag),
  cmssw-config `V09-09-09`, ROOT 6.36.13 and CLHEP 2.4.7.2.
- `_work/cmsdist/*.spec` show how CMS builds each external and which patches it applies.

## Building locally

The host is an arm64 Mac, so builds happen in Docker:

- `cmssw-dev`: `condaforge/miniforge3`, native **linux-aarch64**, volume `cmssw-work` at `/work`.
  It also has a hand-made env `/work/env` used for spikes.
- `cmssw-dev-amd64`: `quay.io/condaforge/linux-anvil-x86_64:alma9` (the CI image), **linux-64**
  through Rosetta (about 2.6x slower), volume `cmssw-work-amd64`. Run commands as `-u root`. The image
  has no `ps`/`pkill`.
- Both mount the repo at `/repo`. rattler-build lives in `/work/tools/bin`, and
  `/work/conda_build_config.yaml` is the conda-forge global pinning.

```sh
docker exec -u root -d cmssw-dev-amd64 bash -c 'export PATH=/work/tools/bin:$PATH; \
  bash /repo/cmssw-notes/build-local.sh linux64 recipes/cmssw-fwlite > /work/build.log 2>&1'
# per-recipe logs: /work/logs/<recipe>-<config>.log, packages: /work/output
```

- Start long builds with `docker exec -d` and poll rarely. Host-side watcher loops get killed when
  the Mac is low on memory, but the build keeps running in the container.
- `cmssw-fwlite` takes about 9 min natively (aarch64) and about 24 min under emulation (x86-64), on 10 cores.
- Explicit `-m` variant files disable rattler-build's auto-discovery of `variants.yaml`, so
  `build-local.sh` passes the recipe's `variants.yaml` last. Without it, the global pinning's
  multiple `root_base`/`clhep` versions give 9 variants.

### macOS (native)

- Everything under `_work/` (git-ignored):
  - dev env: `_work/osx-env`, activated with `source _work/osx-activate.sh`;
  - rattler-build and the pinning: `_work/osx-tools`;
  - `WORK` dir for `build-local.sh`: `_work/osx-work`;
  - CMSSW source with the patch series applied: `_work/osx-src/cmssw-CMSSW_20_1_0_pre2` (a git repo).
- `PATH=$PWD/_work/osx-tools/bin:$PATH WORK=_work/osx-work bash cmssw-notes/build-local.sh osx_arm64 recipes/cmssw-fwlite`
- conda-forge's ld64 can't read the macOS 26 SDK, so `_work/osx-work/extra_variants.yaml` sets
  `CONDA_BUILD_SYSROOT` to `/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk`.
- `_work/sdks/MacOSX11.0.sdk` matches conda-forge ROOT 6.36.10's prebuilt modules. It's needed as
  `SDKROOT` for ROOT's interpreter at runtime (see PLAN.md, osx-arm64 port).
- The old mamba 1.5 on the host can't solve with the local channel; install local `.conda` files directly with `conda install --offline`.
- SIP strips `DYLD_*` variables when running `/bin/bash`, `/usr/bin/env` and similar protected
  binaries. Rely on rpaths and `ROOT_LIBRARY_PATH`, never on `DYLD_*`.

## CMSSW/SCRAM gotchas learned so far

- `SCRAM_ARCH` is `linux_amd64_gcc`, `linux_aarch64_gcc` or `osx_arm64_clang` (no compiler version).
  SCRAM only lists a release if `share/cmssw/<arch>/cms/cms-common` exists. Releases are installed at
  `$PREFIX/share/cmssw/<arch>/cms/cmssw/<CMSSW_VERSION>`.
- Tool files need explicit `INCLUDE`/`LIBDIR` pointing at `$PREFIX`, because in rattler-build the
  compiler lives in `BUILD_PREFIX` and does not search `$PREFIX/include`.
- The build loads freshly built plugins and dictionaries from python, so `$PREFIX/bin` (host python
  with ROOT) must come first in `PATH`, and the tool files must use `PY_VER`.
- conda-forge ROOT 6.36 has Vc enabled, so dictionaries need `libVc.a`. The generator adds it when
  `R__HAS_VC` is defined.
- At runtime ROOT parses CMSSW headers, so external header packages are **run** dependencies.
- Packages installed by separate conda packages must not share files. Use per-package plugin caches
  (`lib/<arch>/.edmplugincache.d/<pkg>`, which needs the PluginManager patch) and per-directory
  `.SCRAM/<arch>/MakeData/DirCache/*.mk` fragments (which need the cmssw-config `updateToolMK.py` patch).
- Layering works: a `scram project` dev area on top of the installed release (`RELEASETOP`).
- The CMSSW 20_1 data formats use `io_v1` namespaces with `using` aliases (e.g. `pat::Muon`). FWLite
  `Handle`s and TClass lookups need the `io_v1` name.
- The `utm` package has no license, so the 3 packages that depend on it are excluded.
- macOS: libc++ is stricter than libstdc++, and `uint64_t` is `unsigned long long` there. EDM class
  checksums differ for 64-bit integer members, so the checks are skipped (`SCRAM_NOEDM_CHECKS`).
  ROOT 6.36's interpreter only works with the SDK its modules were built with.

## Patches

To change CMSSW patches, apply the existing series to a git-initialised copy of the release source
(the aarch64 container has one at `/work/cmssw-git/cmssw`), edit it, and regenerate one patch per
logical change with `git diff -- <paths>`. Keep the original line endings: some CMSSW files are CRLF.
Patches should be upstreamable where possible, and each carries a comment explaining why it is needed.

## Conventions

- Run `prek -a --quiet` before committing. Revert its changes to pre-existing upstream files (e.g. `.github/`).
- Commit and push significant changes directly to `main`, using conventional commits and an
  `Assisted-by: <harness>:<model>` trailer.
- Recipe maintainer is `ariostas`. Follow staged-recipes requirements: license files, sha256,
  no symlinks in noarch packages, tests.
