# CMSSW in conda-forge

This repo is a fork of conda-forge/staged-recipes used only for packaging CMSSW (CMS experiment
software) for conda-forge. `PLAN.md` holds the plan, the decisions and the progress log. Read it
first, and add to its progress log (section 6) when something significant is learned.

## Layout

- `recipes/`: rattler-build (v1 `recipe.yaml`) recipes. `example-v1/` and `example-v0-deprecated/`
  are upstream staged-recipes examples; leave them alone.
  - `cms-scram`: the SCRAM build tool (noarch).
  - `cmssw-toolbox` (noarch): everything the CMSSW and CORAL recipes share:
    - `tools/`, `tools-osx/`: SCRAM tool file templates;
    - `cmssw-generate-toolbox`: instantiates them for a conda prefix;
    - `cmssw-build-layer`: builds a set of CMSSW packages against an installed release;
    - `cmssw-install-layer`: adds the result to that release;
    - `cmssw-link-python-modules`: macOS `.so` aliases for python extension modules.
  - `alpaka`, `hls-arbitrary-precision-types`: header-only dependencies (noarch).
  - `frontier-client`, `coral`: conditions database access. CORAL is a SCRAM project like
    CMSSW and builds with the same toolbox.
  - The CMSSW layers, each built on the previous one and all installed into **one** release
    directory: `cmssw-fwlite` (the base release) → `cmssw-framework` (`cmsRun`, IOPool,
    services, storage) → `cmssw-conditions` (CondCore/CondFormats) → `cmssw-geometry`
    (DD4hep detector description, geometry records, magnetic field). A layer contains:
    - `packages.txt`: CMSSW packages to build; `src-only.txt`: those of which only `src/` is;
    - `patches/`, `cmssw-config-patches/`: source patches;
    - `variants.yaml`: ROOT/CLHEP pins for this CMSSW version;
    - `build.sh`: a few lines around `cmssw-build-layer`;
    - activation scripts (`cmssw-fwlite` only; there is one release directory).
  - `cmssw-devel`: a metapackage that turns a CMSSW environment into one where `scram b` works
    (compilers, `make`, and the `-devel` splits of the externals the layers were built against).
    Its test runs the whole developer loop, so it is the regression test for that workflow.
- `cmssw-notes/`
  - `research/`: background reports (SCRAM internals, conda-forge dependency survey, prior art).
  - `analysis/scripts/`: BuildFile.xml dependency graph, build cost and partitioning scripts.
    They read `_work/` and the CVMFS release.
  - `spike/`: scripts for hand-building SCRAM areas outside rattler-build.
  - `feedstock-changes/`: recipes whose real fix goes to an existing feedstock, not to
    staged-recipes: `cms-md5` (needs more platforms) and `cpu_features` (the feedstock skips osx,
    but it builds there unchanged and `cmssw-framework` cannot be built without it).
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
- Rebuilding a recipe without bumping its build number would otherwise reuse the previously
  extracted package from rattler's package cache; `build-local.sh` deletes those first. A stale
  `cmssw-toolbox` there is silent and very confusing. The cache is in a different place on macOS
  (see below).
- `build-local.sh` takes a lock: two runs share the output directory and the per-recipe logs,
  and the interleaved logs look like impossible build errors.
- Do not edit any bash script while it is running — `build-local.sh`, a recipe's `build.sh`, a
  test script. bash reads a script as it goes, so an edit makes the running copy fail with a
  syntax error somewhere unrelated to the change. Copy it elsewhere first, or wait.

### macOS (native)

- Everything under `_work/` (git-ignored):
  - dev env: `_work/osx-env`, activated with `source _work/osx-activate.sh`;
  - rattler-build and the pinning: `_work/osx-tools`;
  - `WORK` dir for `build-local.sh`: `_work/osx-work`;
  - CMSSW source with the patch series applied: `_work/osx-src/cmssw-CMSSW_20_1_0_pre2` (a git repo).
- `PATH=$PWD/_work/osx-tools/bin:$PATH WORK=_work/osx-work bash cmssw-notes/build-local.sh osx_arm64 recipes/cmssw-fwlite`
- conda-forge's ld64 can't read the macOS 26 SDK, so `_work/osx-work/extra_variants.yaml` sets
  `CONDA_BUILD_SYSROOT` to `/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk`.
- macOS builds against **ROOT 6.40, not the 6.36 the release uses**: conda-forge's 6.36 ships
  prebuilt Darwin modules that only work with the SDK they were built against, so cling fails on
  `#include <unistd.h>` for any user. `variants.yaml` has the details, and `cmssw-fwlite` has a
  test for it that drops `SDKROOT`/`CONDA_BUILD_SYSROOT` first, because both build and test
  environments set them and users do not.
- The old mamba 1.5 on the host can't solve with the local channel; install local `.conda` files directly with `conda install --offline`.
- SIP strips `DYLD_*` variables when running `/bin/bash`, `/usr/bin/env` and similar protected
  binaries. Rely on rpaths and `ROOT_LIBRARY_PATH`, never on `DYLD_*`. A variable exported by an
  already-running shell does survive into a non-protected child, which is why the `cmssw-geometry`
  activation script can hand `DYLD_LIBRARY_PATH` to `cmsRun` but not to a wrapper shell script.
- rattler's package cache is at `~/Library/Caches/rattler/cache/pkgs` on macOS, not
  `~/.cache/rattler`. `build-local.sh` deletes the extracted copies of what it is about to
  rebuild; when it looked in the wrong place the build silently reused the *previous* contents of
  a package with the same build string, which reads as "my fix had no effect".
- conda-forge's Linux gcc is configured with the conda prefix in its default library search path;
  its macOS clang is not, and only gets there through `LDFLAGS`. SCRAM builds its own link line,
  so the macOS compiler tool files add `-L$PREFIX/lib -Wl,-rpath,$PREFIX/lib`. Without it only
  the layer builds work (they pass the same thing as `USER_LDFLAGS`) and a user's developer area
  dies with `ld: library not found for -lTree`.
- python only recognises `.so` as an extension suffix, on macOS too, but SCRAM builds `.dylib`.
  `cmssw-link-python-modules` adds a `.so` symlink for every library exporting
  `PyInit_<its own name>`; `libFWCorePythonParameterSet` is the one `cmsRun` needs to read a
  configuration. Each layer only aliases the libraries it built, so no two packages claim a file.
- `c-compiler`/`cxx-compiler` resolve to conda-forge's current default, which on osx-arm64 lags
  the version the variants pin. `cmssw-devel` therefore uses `${{ compiler('c') }}` and friends
  in its **run** requirements, so a developer gets the toolchain the release was built with.

## CMSSW/SCRAM gotchas learned so far

- `SCRAM_ARCH` is `linux_amd64_gcc`, `linux_aarch64_gcc` or `osx_arm64_clang` (no compiler version).
  SCRAM only lists a release if `share/cmssw/<arch>/cms/cms-common` exists, and that directory has
  to contain a file because conda does not carry empty directories. Releases are installed at
  `$PREFIX/share/cmssw/<arch>/cms/cmssw/<CMSSW_VERSION>`. The list of releases comes from
  `share/cmssw/etc/scramrc/cmssw.map`, which cms-scram installs, so **cms-scram has to be a host
  dependency** of anything that builds a layer: the copy in the build prefix knows no releases.
- Tool files need explicit `INCLUDE`/`LIBDIR` pointing at `$PREFIX`, because in rattler-build the
  compiler lives in `BUILD_PREFIX` and does not search `$PREFIX/include`.
- SCRAM checks that a tool's `INCLUDE`/`LIBDIR`/`BINDIR` exist when it sets the tool up, so a
  toolbox cannot describe packages that are not installed. `cmssw-generate-toolbox` leaves those
  tool files out, and each layer adds the ones for its own externals with `scram setup`. That
  check is not enough on its own: most tools default to `$TOOL_BASE/{lib,include}`, i.e. the conda
  prefix, which always exists. The generator therefore also checks that the `<lib>` entries are
  present, or a missing external is only noticed as `cannot find -l<lib>` at the end of a build.
- The build loads freshly built plugins and dictionaries from python, so `$PREFIX/bin` (host python
  with ROOT) must come first in `PATH`, and the tool files must use `PY_VER`.
- conda-forge ROOT 6.36 has Vc enabled, so dictionaries need `libVc.a`. The generator adds it when
  `R__HAS_VC` is defined.
- At runtime ROOT parses CMSSW headers, so external header packages are **run** dependencies.
- Packages installed by separate conda packages must not share files. Use per-package plugin caches
  (`lib/<arch>/.edmplugincache.d/<pkg>`, which needs the PluginManager patch) and per-directory
  `.SCRAM/<arch>/MakeData/DirCache/*.mk` fragments (which need the cmssw-config `updateToolMK.py` patch).
- Before building a new layer, run `analysis/scripts/undeclared.py recipes/<layer>`. CMSSW is
  built as one area where every package's `interface/` is on the include path whether or not a
  BuildFile declares a `<use>`, so packages include headers they never declare and a layer that
  installs only what the graph names fails to compile minutes in.
- A missing tool file is only a `****WARNING: Invalid tool <name>` at configure time; the build
  then dies much later with undefined references, because the tool's libraries were silently
  dropped from the link line. Grep a layer's log for `Invalid tool` even when it succeeds.
- DD4hep loads the CMS detector description through its **own** plugin registry, not CMSSW's:
  `DetectorDescription/DDCMS` builds `dd4hep/*.cc` with `DD4HEP_PLUGIN="1"`. It finds those
  libraries only on `LD_LIBRARY_PATH` (`DD4HEP_LIBRARY_PATH` does not work with conda-forge's
  build), so `cmssw-geometry` ships an activation script that adds the release's `lib/`.
- **A layer must not contain a directory for a package that a lower layer owns.** SCRAM treats
  `src/<Sub>/<Pkg>` in a developer area as the local definition of that package, so the release's
  library drops out of every link line (`****WARNING: Invalid tool <Sub>/<Pkg>`). This is why
  `cmsRun` is built in `cmssw-fwlite`, even though it is only useful once `cmssw-framework` adds
  input, output and services: its source lives in `FWCore/Framework/bin`, and that package's
  library belongs to the base layer.
- A user's developer area is the same construction as a layer, so it works out of the box, but
  only if nothing overrides SCRAM's search order. `CMSSW_PLUGIN_PATH` (set by the activation
  script for the case where there is no developer area) is therefore **appended** to the plugin
  search path, not prepended: `scram runtime` already puts the work area first and the release
  after it, and a locally rebuilt plugin has to win.
- Layering: a layer is a `scram project` developer area on top of the installed release
  (`RELEASETOP`), whose products are then copied **into that release** by `cmssw-install-layer`.
  There is one release directory, so the activation scripts and a user's own developer area (which
  can only chain one level) keep working. Everything a layer installs is at a per-package or
  per-tool path: `lib/<arch>/*`, `src/<Sub>/<Pkg>`, `python/`, `cfipython/`,
  `.SCRAM/<arch>/MakeData/DirCache/*.mk`, `.SCRAM/<arch>/{BuildFiles,tools,InstalledTools}`,
  `config/toolbox/<arch>/tools/selected`. `.SCRAM/<arch>/DirCache.json` is not needed by a
  developer area, and `MakeData/Tools.mk` and `edmplugins` are regenerated in each area.
- The CMSSW 20_1 data formats use `io_v1` namespaces with `using` aliases (e.g. `pat::Muon`). FWLite
  `Handle`s and TClass lookups need the `io_v1` name.
- Two dependencies have **no license** and cannot go to conda-forge until that is resolved:
  - `utm` (CMS L1 trigger menu). It blocks `CondFormats/L1TObjects`, and through it
    `CondCore/Utilities` (the `conddb` tools), `DataFormats/RPCDigi`, the L1 unpackers and the
    `L1Trigger/*` emulator, so it is on the critical path for reconstruction from RAW.
  - `coral` (the LCG relational abstraction layer, needed for conditions). Neither the CMS fork
    nor the upstream LCG repository has a license file or license headers.
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
