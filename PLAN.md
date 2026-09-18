# Plan: packaging CMSSW for conda-forge

Goal: install CMSSW (the CMS offline software) with `conda install`/`pixi add` on
**linux-64, linux-aarch64, osx-arm64** (osx-64 is not a target). It must be split
into packages that each build within conda-forge CI limits.

This document is the result of an initial exploration. Details and evidence:

- `cmssw-notes/research/scram_notes.md`: how SCRAM and cmssw-config work, runtime
  environment, build products, chaining, macOS issues.
- `cmssw-notes/research/deps_conda_forge.md`: every external dependency checked
  against conda-forge repodata (name, version, platforms, CMS patches, action).
- `cmssw-notes/research/prior_art.md`: earlier attempts (fwlite-feedstock, Stitched,
  cmssw-spack, scram2cmake) and conda-forge CI and splitting practices.
- `cmssw-notes/analysis/`: scripts that parse all `BuildFile.xml` files of a release
  and compute the package graph, build cost and a proposed partition.
  `partition2.json` maps every package's lib and plugins to a build group.

Reference release used for the analysis: `CMSSW_20_1_0_pre2` on CVMFS
(`/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2`).
The packaging repos (cmsdist, cmssw-config, SCRAM, pkgtools) are cloned in the
git-ignored `_work/`.

---

## 1. What we are dealing with

### 1.1 CMSSW itself

| Quantity | Value |
|---|---|
| Packages (`Subsystem/Package`) | 1,358 (1,230 with compiled code) across 104 subsystems |
| Translation units (from `compile_commands.json`) | 17,172: 9,756 `src/`, 5,352 `plugins/`, 1,893 `test/`, 171 `bin/` |
| Not counted above | ROOT dictionaries (282 `classes_def.xml`), alpaka GPU backends, LTO |
| Build products | 954 libraries (430 MB), 1,873 edm plugins (1.18 GB), tests (448 MB); CVMFS `lib/` is 3 GB because everything is built for two micro-archs |
| Generated Python configs | about 10.8k `cfipython` files, produced by running `edmWriteConfigs` on each built plugin |
| Upstream release build time | 3.2–5.5 h wall time per release on CMS build machines (with LTO, externals prebuilt) |
| Estimated CPU cost | 10–30 CPU-s per TU gives roughly **50–150 CPU-hours** for one arch without LTO or GPU. This must be measured (M1). |

**Dependency structure (key finding).**
- The **library** graph between packages is a DAG.
- Package-level cycles only appear through `plugins/` (9 small cycles) and `test/` (21).
- At the **subsystem** level, almost all subsystems form one strongly connected
  component. For example, DataFormats packages depend on RecoTracker libs and CondFormats
  depends on CondCore. **A naive "one package per subsystem" split is therefore impossible.**
- The split must be done per package, and each package's `src/` library can go
  in a different group from its `plugins/`.

### 1.2 Externals

The SCRAM toolbox selects 782 tools, which collapse to about 200 real externals plus about 400 Python
packages. Summary from `deps_conda_forge.md`:

- **Python:** 392 of 402 are already on conda-forge. The missing ones are trivial or skippable
  (cmsml, cms-tfaot, scinum, ...).
- **Already available and fine:** python 3.12, ROOT (6.36.x branch and 6.40,
  C++20, all 4 platforms), boost, tbb, clhep, hepmc3, xrootd, hdf5, eigen, fastjet(-contrib),
  xerces-c, protobuf/grpc, lhapdf, pythia8 (needs bump), onnxruntime, gsl, fftw, zstd/lz4/xz, ...
- **Missing core dependencies, needing new recipes:**
  - `coral`, `frontier_client`, `classlib` (conditions DB access; coral builds with SCRAM)
  - `heppdt` 3.x (conda-forge has 2.06, a different series)
  - `alpaka`, `hls` (Xilinx ap_types headers), `xtd` (all header-only)
  - `utm` (L1 menu lib; the name clashes with an unrelated Python package), `g4hepem`, `ktjet`, `fftjet`
  - `cms-md5`: platforms missing
  - `cpu_features`: no osx-arm64
- **Generator and simulation stack:**
  - Missing: pythia6 (+pydata), tauolapp, herwig7 (staged-recipes PR open),
    thepeg (linux-only), sherpa 2.2 (cf has 3.x), openloops, evtgen built against HepMC2.
  - geant4 on cf is C++17 without VecGeom; CMS uses C++20 + VecGeom + a patch.
  - dd4hep needs `DD4HEP_USE_GEANT4_UNITS=ON`.
- **ABI-sensitive CMS patches:**
  - CMS's HepMC2 changes `WeightContainer::size_type`.
  - ROOT is a CMS fork (1 commit), which is probably fine.
  - TensorFlow is a CMS fork plus the XLA AOT runtime.
- **Version skews that need porting CMSSW or new builds:** fmt 10→12, tinyxml2 6.2→11,
  numpy 1.26→2, xerces-c 3.1→3.3, highfive 2→3, xgboost 1.7→3.
- **Co-installability problem:** conda-forge's `libtensorflow_cc` and `libtorch` currently
  require different protobuf and abseil versions.
- **Data:** `cmsswdata` = 112 `cms-data/*` repositories, **8.6 GB total**. SimG4CMS-Calo alone is
  2.9 GB. These must be separate noarch packages, and some are too large to ship as-is.
- **Out of scope, at least initially:** CUDA/ROCm backends (no GPU CI on conda-forge),
  Oracle/tkonlinesw/DIP (proprietary or online only), dev tools (igprof, valgrind, gdb, ...),
  ACTS/traccc (not used by CMSSW packages yet).

### 1.3 The build system (SCRAM + cmssw-config)

- SCRAM V3 is about 4k lines of stdlib-only Python 3. It parses tool XMLs and `BuildFile.xml`
  into `.SCRAM/<arch>/` caches.
- cmssw-config's `BuildRules.py` generates make fragments, and GNU make builds using
  `cmssw-config/SCRAM/GMake/Makefile.rules`.
- **Needs:** python3, bash ≥4, GNU make, GNU coreutils/sed/find, and a `SCRAM_ARCH` string. All of these
  are available in conda.
- **The build runs built code:** `rootcling` in dependency order with `.pcm` files,
  `edmPluginRefresh` loads each plugin, `edmWriteConfigs` generates `cfipython`,
  `edmCheckClassVersion`, and the CondFormats serialization generator (libclang Python). **Consequence:**
  cross-compilation, e.g. osx-arm64 on osx-64 CI, needs these steps disabled or deferred, or a
  native runner.
- **Chaining:**
  - A developer area or patch release can be built on top of an installed release
    (`RELEASETOP` / `cmssw` tool), which is one chaining level.
  - Since conda installs all packages into **one prefix**, one level is enough. Layer N is built as a
    "patch-release-like" area on top of the merged installation of layers 0..N-1.
- **Files shared between layers:** `lib/<arch>/.edmplugincache`, `python/<Sub>/__init__.py`
  and `.SCRAM` metadata. They must be regenerated or merged at install time, via
  per-plugin cache fragments, a post-link/activation step, or a trigger-style rebuild.
- **Runtime environment:**
  - The PluginManager scans `LD_LIBRARY_PATH` (`DYLD_FALLBACK_LIBRARY_PATH` on macOS, which SIP strips)
    for `.edmplugincache`, so a patch adding a dedicated plugin-path variable is needed.
  - `FileInPath` needs `CMSSW_SEARCH_PATH` and `CMSSW_BASE`/`CMSSW_RELEASE_BASE`/`CMSSW_DATA_PATH`.
  - Python paths should go through a `.pth` file.
  - All of this maps onto a conda activation script.

### 1.4 macOS

- CMS dropped macOS around 2015. Leftovers still exist (`osx` branches in cmssw-config, `__APPLE__` in FWCore).
- **C++ code:** only 30 source files use Linux-specific APIs (mallinfo, /proc, dl_iterate_phdr,
  pthread_setname_np, sched_getaffinity, ...), and 11 already have `__APPLE__` guards.
  CMS runs clang builds continuously (`CMSSW_20_1_CLANG_X`), but **only with libstdc++**.
  libc++ has not been tested. Known issues from earlier attempts include missing transitive includes,
  `M_PIl`, `constexpr std::pow`, `.so` vs `.dylib` in plugin/rootmap names, and case-insensitive
  file name clashes.
- **SCRAM on macOS:**
  - `os.sched_getaffinity` crashes on import (one-line fix).
  - SCRAM calls a missing `cmsos` command.
  - Rules use GNU-only commands like `cp -urpT` and `sed -i` (put conda's GNU tools on PATH).
  - Linux-only link flags: `--as-needed`, `--push-state`, `-z defs`.
- **Dependencies:** a few deps lack osx builds (thepeg, cpu_features osx-arm64, tensorflow on osx-64).
- Plan: treat macOS as a **separate porting track** that starts once linux-64 works. Target
  osx-arm64 first. osx-64 is being wound down across conda-forge (tbb, tensorflow, onnxruntime).

### 1.5 Prior art worth reusing

- `conda-forge/fwlite-feedstock` (2019–2022, archived): FWLite 11.3 via a CMake conversion,
  linux-64 + osx-64. It died from maintenance burden (migrations, OpenGL on macOS, TBB).
  **Lesson:** automate re-generation and keep the number of hand-maintained pieces low.
- `cmsdist/fwlite.spec` + `fwlite_build_set.file`: CMS's own 152-package FWLite subset, about
  2.3k TUs including plugins and tests. It is a ready-made first target.
- `code4hep/stitched-alpha2` (active, CMS core-software people): FWCore + core
  DataFormats extracted into a CMake project with exported targets and a Spack recipe.
  It is a possible base for a CMake route, and we should coordinate with them.
- `gartung/scram2cmake`, `cms-sw/cmssw2cmake`, `gartung/cmssw-spack`: BuildFile→CMake
  generators (frozen in 2018–2023).

---

## 2. Key decisions

### D1. Build system: SCRAM inside conda-build (recommended to start) vs generated CMake

| | (A) Patched SCRAM | (B) Generated CMake (scram2cmake / Stitched-style) |
|---|---|---|
| Parity with official releases | exact (same rules for dicts, plugins, cfipython, class versions, serialization, alpaka) | must re-implement all of those |
| Code to write and maintain | small patches to SCRAM + cmssw-config, tool XML generation | a generator plus CMake modules, re-validated each release |
| Layered builds | "patch release on top of prefix" (verified in the code; needs a spike) | natural (`find_package` of earlier layers) |
| Users' `cmsrel`/`scram b` developer workflow | works almost unchanged | lost, unless SCRAM is packaged anyway |
| macOS | needs GNU tools + cmssw-config osx fixes | more control over flags |
| conda-forge friendliness | unusual but acceptable (it is just a build tool) | idiomatic |

**Recommendation:** go with (A) for the linux-64 prototype, since it gets to a working release fastest
and keeps the developer workflow. Keep (B) as a fallback if layering or macOS with SCRAM
proves unworkable. For (B), reuse SCRAM's parsed `.SCRAM/*.json` data and align with Stitched
instead of starting from scratch. We decide at the end of M2.

### D2. How to split

**Layered separate recipes/feedstocks** (not one multi-output recipe). All outputs of a recipe
build in one CI job, so a multi-output recipe does not reduce build time. Each layer is a
feedstock that builds a set of packages against the previous layers installed from the channel.
It may also split its own result into outputs (e.g. `-devel` headers, python).

First-pass partition (`cmssw-notes/analysis/scripts/partition2.py`, output `partition2.json`):
- Each package's `src/` lib and `plugins/`+`bin/` are separate nodes.
  **(Superseded 2026-09-18: with layers built as developer areas they cannot be separated;
  see the progress log. Use `analysis/scripts/reach.py`, not `partition2.py`.)**
- A node goes in its preferred group, or a later group if one of its dependencies requires it.
- Tests are excluded (1,893 TUs).

| # | Group | Nodes | TUs | New externals first needed here |
|---|---|---|---|---|
| 0 | core (FWCore, Utilities, IOPool, HeterogeneousCore, ...) | 25 | 123 | root, boost, tbb, clhep, hepmc, fmt, alpaka, xerces-c, md5, libuuid |
| 1 | dataformats (DataFormats, SimDataFormats, CondFormats, ...) | 236 | 2,160 | classlib, eigen, hepmc3, vdt, protobuf, xrootd, davix, tinyxml2, utm, hls, cpu_features |
| 2 | conditions + geometry | 243 | 2,703 | coral, frontier_client, dd4hep, geant4, heppdt, gsl, hdf5 |
| 3 | common reco (tracking, local reco, unpackers) | 243 | 1,740 | fastjet, fastjet-contrib, clue |
| 4 | L1 + HLT | 96 | 963 | L1 ML models (axol1tl, cicada, ...) |
| 5 | reco / PAT / NanoAOD tooling | 261 | 2,324 | onnxruntime, tensorflow-cc, pytorch, xgboost, lwtnn, correctionlib, fftjet, lhapdf, pythia8 |
| 6 | sim + generators | 266 | 2,433 | pythia6, herwig7, sherpa, evtgen, tauolapp, photospp, rivet, g4hepem, ... |
| 7 | DQM, validation, alignment, calibration | 346 | 2,833 | millepede, gbl, dip, log4cplus |

Notes:
- Group 0 is tiny because FWCore/Framework and friends depend on DataFormats libraries.
  In practice groups 0+1 merge into one "framework + dataformats" layer.
- The expected cost per group is about 1–3k TUs, i.e. roughly 5–25 CPU-hours each. A default
  conda-forge runner (6 h × 2–4 cores) holds about 12–20 CPU-hours, so groups must be split
  further (to about 12–20 layers) **or** we request the large runners conda-forge now offers
  (up to 16+ CPUs on linux, 6–12 on osx-arm64) through `admin-requests`. The latter keeps the
  number of feedstocks around 6–8, which matters a lot for maintenance.
- Group names are only a starting point. Partitioning should become an automated
  step that reruns for every CMSSW release. The group of each package may shift
  between releases, and plugins that move to later groups are fine.
- **Aligned user-facing tiers:**
  - `cmssw-fwlite`: the cmsdist FWLite set, for reading AOD/MiniAOD/NanoAOD in python and ROOT.
    This is the MVP.
  - `cmssw-reco`: can run RECO/HLT from RAW with conditions from Frontier.
  - `cmssw-sim`: GEN-SIM.
  - `cmssw`: a metapackage with everything.

### D3. Versions, pinning and release cadence

- CMSSW publishes pre-releases every few weeks. Proposal: package **one production release cycle**
  (e.g. the first `CMSSW_20_1_0` final and its patch releases). Version the packages as
  `20.1.0` and keep all layers pinned `==` to each other (same version + build number),
  enforced with `run_exports`/`pin_subpackage` or exact pins between feedstocks.
- CMS pins externals exactly. We use conda-forge's global pinnings wherever CMSSW compiles
  (tbb, boost, fmt, numpy 2, ...) and upstream the needed CMSSW patches (fmt 12, tinyxml2 11,
  xerces 3.3, highfive 3, libc++/macOS fixes) to cms-sw/cmssw, so we don't carry them forever.
- The compiler is conda-forge's GCC (currently 15) on linux; CMS has gcc14 and gcc15 IB
  branches (`el10_amd64_gcc14`, `IB/CMSSW_20_1_X/g15`), so this should be manageable.
- **Open question:** how to handle conda-forge migrations (ROOT, boost, tbb, python). Every migration
  forces a rebuild of all layers in order, so we need a bot or script to drive that.

### D4. Data

- Ship each `cms-data/<Sub>-<Pkg>` repository as its own noarch package `cmssw-data-<sub>-<pkg>`.
  The source is the GitHub tag listed in `cmsswdata.spec`.
- Layer packages depend only on the data they need; `FileInPath` resolves data through
  `CMSSW_DATA_PATH`/`CMSSW_SEARCH_PATH`.
- Very large data (SimG4CMS-Calo 2.9 GB, CalibTracker-SiPixelESProducers 0.8 GB, ...) needs
  checking against anaconda.org size limits and conda-forge norms. Possible alternatives: optional packages,
  or on-demand download.

---

## 3. Milestones

### M0: tooling and a local build loop (small)
- [ ] Local build env: `pixi`/`rattler-build` in this repo, recipes under `recipes/`.
      Linux builds via Docker (`build-locally.py`) on this Mac, or a remote linux box.
- [ ] Script to regenerate the analysis (`cmssw-notes/analysis/scripts`) for any release
      tag, using a sparse git checkout of cms-sw/cmssw instead of CVMFS.
- [ ] Choose the target release (see D3). Proposal: follow `CMSSW_20_1_X` until 20_1_0 is out.

### M1: build system packages + cost measurement (linux-64)
- [ ] Recipe `cms-scram` (noarch python). Patches: python from PREFIX, no `cmsos`,
      `sched_getaffinity` fallback, no `/cvmfs` assumptions.
- [ ] Recipe `cmssw-config` (noarch). Patches: disable biglib, multi-microarch, LTO,
      CUDA/ROCm alpaka backends, and tests by default; conda compiler and flags from env.
- [ ] Recipe or script `cmssw-tool-conf`: generate SCRAM tool XMLs pointing at `$PREFIX`
      (port `cmsdist/scram-tools.file/tools/*`, dropping CVMFS paths). This also
      documents exactly which conda packages map to which tool.
- [ ] **Spike:** build FWCore + DataFormats/Common locally with SCRAM against conda-forge
      ROOT/boost/tbb/clhep. **Record CPU time per TU** and extrapolate the full release cost
      to pick the number of layers (D2).
- [ ] **Spike:** verify layered building. Build group 1 as a patch-release-style area
      on top of an installed group 0 in the same prefix, including dictionaries (`.pcm` from
      the earlier layer), plugin cache and `cfipython`.

### M2: missing dependencies for the FWLite tier
Submit to staged-recipes (each is its own small PR):
- [ ] header-only: `alpaka`, `xtd`, `hls` (ap_types)
- [ ] `classlib`, `cms-md5` platforms, `cpu_features` osx-arm64 (feedstock PR)
- [ ] `utm` (name it e.g. `cms-utm`), `heppdt` 3.x (new name or major-version output)
- [ ] `tinyxml2` 6.2.0 (e.g. `tinyxml2-6`), **or** a CMSSW patch for tinyxml2 11
- [ ] decide HepMC2: a CMS-ABI `hepmc2` build vs patching CMSSW
- [ ] **Decision point D1:** confirm SCRAM route or switch to CMake.

### M3: `cmssw-fwlite` on linux-64
- [ ] Recipe(s) for the FWLite set (about 2.3k TUs), using the cmsdist `fwlite_build_set.file`.
- [ ] Activation scripts: `CMSSW_*` variables, plugin path, `CMSSW_SEARCH_PATH`,
      `ROOT_INCLUDE_PATH`, python `.pth`.
- [ ] PluginManager patch: dedicated plugin search path; per-layer cache fragments merged
      at activation or post-link.
- [ ] Tests: `import DataFormats.FWLite`, read a MiniAOD/NanoAOD test file,
      `edmDumpEventContent`, `edmPluginDump`.
- [ ] Upstream CMSSW patches that are generally useful.

### M4: full framework (`cmsRun` works)
- [ ] Missing deps for conditions: `coral` (without Oracle), `frontier_client`.
- [ ] Layers for groups 0–3; `cmsRun` a simple config with conditions from Frontier.
- [ ] Merge mechanism for shared files across layers (`.edmplugincache`,
      `python/<Sub>/__init__.py`, `.SCRAM` metadata for developer areas).
- [ ] Developer workflow: `scram project` / `cmsrel` on top of the conda prefix, check out a
      package, `scram b`, and run it. This is critical for real users (e.g. LST development:
      the `RecoTracker/LST` closure is 337 packages, about 6.1k TUs).

### M5: reco, L1/HLT, ML (groups 4–5)
- [ ] ML stack: resolve TF/libtorch protobuf/abseil co-installability, TF XLA AOT runtime,
      onnxruntime, xgboost version, cms-tfaot, cmsml.
- [ ] L1 externals (hls4mlEmulatorExtras, conifer, model packages).
- [ ] Data packages needed by reco (`cmssw-data-*`).
- [ ] Target: run a standard RECO step from RAW (e.g. a relval workflow `runTheMatrix.py -l ...`).

### M6: simulation and generators (group 6)
- [ ] geant4 with VecGeom + C++20 (a feedstock variant, or a CMS-flavored output), vecgeom 2.1,
      dd4hep with Geant4 units, g4hepem.
- [ ] Generators: pythia6, tauolapp, photospp, evtgen (HepMC2), herwig7/thepeg, sherpa 2.2,
      openloops... Many are optional and can be marked as such.

### M7: DQM, validation, alignment (group 7), full `cmssw` metapackage

### M8: macOS (osx-arm64, then maybe osx-64), in parallel from M3 onward
- [x] SCRAM/cmssw-config osx fixes (dylib handling, GNU tools, link flags).
- [x] libc++ + clang fixes in CMSSW for the layers built so far. **Not** yet upstreamed as PRs to
      cms-sw/cmssw. Could add a CMS clang+libc++ syntax-check IB to prevent regressions.
- [x] Linux-specific API fallbacks, for the packages built so far (`pipe2`, `execv`, `environ`,
      `HOST_NAME_MAX`, `/proc`). More will appear as later layers are added.
- [ ] Build-time code execution on osx-arm64 runners (native, not cross). Works locally; not yet
      tried on conda-forge's runners.

### M9: automation and hand-off
- [ ] Script to bump all layers to a new CMSSW release: rerun partition, regenerate recipes,
      check that versions of changed externals match conda-forge pins.
- [ ] Feedstock maintainers; coordinate with CMS core software (cms-sw) and the
      Stitched/Code4hep effort; announce on CMS talk and the conda-forge Zulip.
- [ ] Clean up this repository (remove `cmssw-notes/`, `PLAN.md`).

---

## 4. Risks

| Risk | Mitigation |
|---|---|
| Build cost far above estimate, too many layers | measure in M1; request large runners early; disable LTO/multi-arch/tests |
| Migration churn (ROOT/boost/tbb/python) across 6–20 feedstocks, which killed fwlite-feedstock | fewer, larger layers on large runners; automation (M9); upstream patches instead of carrying them |
| ABI-sensitive CMS patches to externals (HepMC2, geant4, TF fork) conflict with stock conda-forge packages | prefer upstream versions + CMSSW patches; use distinct package names only where unavoidable |
| Layering through SCRAM chaining doesn't handle dictionaries/pcm or plugin caches cleanly | spike in M1; fall back to CMake (D1) |
| Package size limits (plugins 1.2 GB, data 8.6 GB) | split outputs; strip debug info; one data package per repo; optional big data |
| Python-version matrix (PyROOT makes ROOT python-dependent, so every layer builds once per python) | restrict to one python version per CMSSW release if conda-forge policy allows, or `noarch` python parts where possible |
| libc++/macOS porting effort larger than expected | macOS is a separate track, linux ships first |
| Conditions access requires Frontier or network at runtime | document; test with local SQLite conditions |

## 5. Decisions taken (2026-09-16)

1. **Target release:** `CMSSW_20_1_0_pre2`, as a proof of concept.
2. **CI runners:** assume the default conda-forge runners. Request large runners only if the
   measurements (M1) show it is absolutely necessary.
3. **First deliverable:** `cmssw-fwlite`.
4. **osx-64:** not supported. Platforms are linux-64, linux-aarch64 and osx-arm64.
5. **Contacting CMS core software and Code4hep:** later, once the project is further along.
6. **Local development:** this machine is an arm64 Mac whose Docker VM is native aarch64.
   Linux spikes are built as **linux-aarch64** in Docker. linux-64 is covered by
   CI with the same recipes.

7. **ROOT/CLHEP pinning:** each CMSSW version pins one `root_base` and one `clhep` version
   (the conda-forge builds closest to the ones the release uses) in the recipe's
   `variants.yaml`. It doesn't follow the global pinning's multiple versions.
8. **linux-64 local builds:** use the conda-forge CI image `quay.io/condaforge/linux-anvil-x86_64:alma9`
   through Docker's Rosetta emulation on the arm64 Mac (`cmssw-notes/build-local.sh linux64`).
9. **macOS runtime (2026-09-17, reversed 2026-09-18):** the original decision was to stay on ROOT
   6.36.10 on macOS for consistency with the CMS releases, leaving osx-arm64 a *compile-only*
   target. That traded a working platform for a version number: conda-forge's 6.36 cannot run on
   macOS at all. macOS now pins ROOT 6.40 instead, is a full runtime target, and the mismatch with
   the release's 6.36.13 is documented in each `variants.yaml`. Revisit if conda-forge's 6.36.x
   gains the SDK fix.

## 6. Progress log

### 2026-09-16: SCRAM spike on linux-aarch64 (Docker on the arm64 Mac)

Setup: `condaforge/miniforge3` container, a conda env with conda-forge externals
(gcc 15.3, ROOT 6.40.04 C++20, boost 1.92, tbb 2023.1, python 3.12, ...). Scripts are in
`cmssw-notes/spike/`.

**Results**

- **SCRAM works inside a conda env.** It needed only 2 small SCRAM patches
  (`recipes/cms-scram`) and 3 cmssw-config patches (`recipes/cmssw-config`):
  - fall back to `make` when there is no `gmake`;
  - force `SHELL=bash`, since the rules use `$'\n'`;
  - read the per-directory `DirCache/*.mk` fragments of the release instead of one
    merged `DirCache.mk`, so layers can be installed by separate packages.
- **Toolbox:** tool XMLs are generated from templates by
  `recipes/cmssw-tool-conf/cmssw-generate-toolbox`. The templates were converted from the
  CVMFS release with `cmssw-notes/analysis/scripts/cvmfs_tools_to_templates.py` and edited
  by hand.
- **SCRAM_ARCH strings:** `linux_amd64_gcc`, `linux_aarch64_gcc`, `osx_arm64_clang`. They have
  no compiler version, so install paths survive compiler migrations. SCRAM only
  recognises an arch if `share/cmssw/<arch>/cms/cms-common` exists.
- **Layering works with the normal developer-area mechanism:**
  - layer 1 is bootstrapped as a release directly at
    `$PREFIX/share/cmssw/<arch>/cms/cmssw/CMSSW_X`;
  - layer 2 is a `scram project` dev area on top of it (`RELEASETOP`), including
    dictionaries that depend on layer-1 `.pcm` files.
- **FWLite builds with no errors** (138 packages, i.e. cmsdist's FWLite set minus Fireworks and
  minus the 3 packages that need `utm`). It needed 4 CMSSW patches
  (`recipes/cmssw-fwlite/patches`), all candidates for upstreaming:
  1. The serialization generator filtered out conda's libstdc++ include dir (`lib/gcc/.../include/c++`).
  2. `CondFormats` portable archive used boost's private `base_type` typedefs (CMS patches boost).
  3. `HepMC::WeightContainer` dictionary: CMS's HepMC2 fork changes `size_type`, so a
     ClassVersion 4 was added for upstream HepMC2 (see open issues).
  4. PluginManager reads `<dir>/.edmplugincache.d/*` (one cache per installed package)
     and honours `CMSSW_PLUGIN_PATH`.
- **Runtime:** `edmPluginDump`, `edmFileInPath`, `import FWCore.ParameterSet.Config` and
  `DataFormats.FWLite` work. **A remote 2015 MiniAOD file (CMS Open Data, xrootd) was read
  successfully with FWLite** (muons and jets).
- **Build cost** (10 Apple-silicon cores in Docker, no LTO, `-O3`):

  | step | packages | wall | CPU (user+sys) |
  |---|---|---|---|
  | layer 1 (FWCore/DataFormats core, 230 objects) | 10 | 39 s | 5 min |
  | layer 2 (rest of FWLite incl. dictionaries, plugins) | 138 | 7.8 min | 61 min |

  So FWLite needs about 1 CPU-hour here, probably 2–3 on CI x86 cores. **FWLite fits in a single
  recipe on the default runners.** Extrapolating to the full release (about 15k non-test
  TUs) gives very roughly 15–25 CPU-hours here, i.e. perhaps 4–8 layers on default
  runners. This must be re-measured on heavier packages (Reco, Sim, L1).

**Open issues found**

- **`utm` has no license**, so it can't go to conda-forge until the CMS L1T maintainers add one.
  - It is published only as source at https://gitlab.cern.ch/cms-l1t-utm/utm (public; tags up
    to `utm_0.14.1`, Jan 2026). There are no PyPI or binary releases, and the conda-forge `utm`
    package is an unrelated project.
  - The repo has no license file or license metadata. The docs
    (globaltrigger.web.cern.ch/globaltrigger/release/utm) only say
    "© 2014-2025, Takashi Matsushita, Bernhard Arnold, Herbert Bergauer".
  - Action: ask the CMS L1 Global Trigger group to add an OSS license. It blocks `CondFormats/L1TObjects`,
  `CondFormats/RPCObjects` and `DataFormats/RPCDigi`.
- **HepMC2 ABI:** CMS's fork uses `unsigned long long` for `WeightContainer::size_type`.
  With stock conda-forge `hepmc2`, the symbols differ and the class checksum changes. We still
  need to validate that CMS files with `HepMCProduct` (GEN level) are readable via
  schema evolution, or else ship a CMS-flavoured hepmc2.
- `pat::Muon` etc. are now `using` aliases for `pat::io_v1::*`, so FWLite `Handle`s need the
  `io_v1` name until the library is loaded. This is upstream behaviour, not packaging.
- `cms-md5`: the existing feedstock is linux-64/osx-64 only and needs aarch64/arm64 builds.
  It installs `include/md5.h`, a generic name.
- `hls` headers and `alpaka` need new recipes (drafts in `recipes/`).
- conda-forge's aarch64 sysroot is glibc 2.17. It was fine so far.
- The Docker image's `/bin/sh` is dash. Fixed by forcing bash in the make rules.

### 2026-09-16: first recipes built with rattler-build (linux-aarch64)

**Recipes**

| recipe | status | notes |
|---|---|---|
| `recipes/cms-scram` | builds, tests pass | noarch. Symlinks are dereferenced (not allowed in noarch) and `bin/scram` is a wrapper script |
| `recipes/alpaka` | builds | noarch, header-only (CMake install) |
| `recipes/hls-arbitrary-precision-types` | builds | noarch, header-only, from the CMS fork |
| `cmssw-notes/feedstock-changes/cms-md5` | builds | goes to the existing feedstock as a PR (add aarch64/arm64 builds and `run_exports`), not to staged-recipes |
| `recipes/cmssw-fwlite` | **builds, tests pass** (incl. header-parsing tests) | about 9.3 min wall / 61 CPU-min on 10 cores; package is 60 MB; ROOT 6.36.10 |

**Things learned from building in rattler-build** (none showed up in the spike env):

- The compiler lives in `BUILD_PREFIX`, so `$PREFIX/include` is not searched
  implicitly. Every tool file needs explicit `INCLUDE`/`LIBDIR` (this was an issue for `openssl`).
- The build env gets a newer python, pulled in by noarch `cms-scram`. The host python must come first
  in `PATH`, because built dictionaries and plugins are loaded by python scripts during the build.
  The python version for the tool files comes from `PY_VER`.
- conda-forge's ROOT 6.36 is built with Vc, so its headers require `libVc.a` at link time. The toolbox
  generator adds it to the `rootcling` tool automatically.
- **Variant explosion:** the global pinning currently lists 3 `root_base` versions (6.36, 6.38,
  6.40) and 3 `clhep` versions, which gives 9 builds. FWLite built and passed tests with all of
  those that were tried. The feedstock needs a recipe-level `conda_build_config.yaml` to restrict
  them (probably one ROOT).
- `external/<arch>` (SCRAM's symlink farm into the prefix) must not be packaged.
- **Runtime headers:** ROOT's interpreter parses CMSSW headers on first use, so the header packages
  (`libboost-headers`, `tbb-devel`, `eigen`, `alpaka`, `hls-arbitrary-precision-types`) are **run**
  dependencies, and `include/eigen3` must be in `ROOT_INCLUDE_PATH`. The recipe tests
  now include CMSSW headers through the interpreter so this is caught.
- **End-to-end check:** `mamba create -c <local> cmssw-fwlite xrootd`, activate, then read a
  CMS Open Data MiniAOD over xrootd with FWLite. This works. No SCRAM is involved at runtime;
  everything is set by the activation script (`CMSSW_BASE`, `CMSSW_SEARCH_PATH`,
  `CMSSW_PLUGIN_PATH`, `ROOT_LIBRARY_PATH`, `ROOT_INCLUDE_PATH`) plus a `.pth` file and
  `bin/` symlinks.

**linux-64** (conda-forge CI image `linux-anvil-x86_64:alma9`, Rosetta emulation on 10 cores):
all recipes build and `cmssw-fwlite` passes its tests. It took 22 min wall / 147 CPU-min
(about 2.4x the native aarch64 CPU time) with the single pinned variant (ROOT 6.36.10, CLHEP 2.4.7.2).

**Next steps**

1. linux-64 in real conda-forge CI (a PR against this staged-recipes fork) to get CI build times.
2. Recipe cleanup for staged-recipes: split the cmssw-config/toolbox pieces into a base
   package that later layers reuse; `conda_build_config.yaml` for ROOT; lint.
3. osx-arm64: native build of the same recipes (SCRAM osx fixes, clang/libc++ port).
4. Layering beyond FWLite: turn the dev-area-on-release mechanism from the spike into a
   recipe for the next layer (e.g. `cmssw-core` framework + `cmsRun`), and install
   `DirCache/*.mk`, `BuildFiles/` and `.edmplugincache.d/<pkg>` per package.
5. Upstream the 4 CMSSW patches to cms-sw/cmssw and ask the utm maintainers about a license.

### 2026-09-17: osx-arm64 port

FWLite now builds natively on osx-arm64 (M1 Max, conda-forge clang 21 + libc++), both as a
hand-built spike (two layers) and through the `cmssw-fwlite` recipe with rattler-build (about 10 min).
The spike reads the CMS Open Data MiniAOD file with the same results as on Linux, **but only when ROOT's
interpreter uses the macOS 11.0 SDK** (see blocker below).

**Build environment**
- The conda-forge linker (ld64) can't parse the macOS 26 SDK (`arm64e.x1` in `libSystem.tbd`), so local
  builds use `CONDA_BUILD_SYSROOT=.../MacOSX15.4.sdk` (via `$WORK/extra_variants.yaml`). CI uses its own SDKs.
- Deployment target 13.3 (`variants.yaml`), needed for floating point `std::to_chars` (std::format).
  conda-forge's ROOT uses `-D_LIBCPP_DISABLE_AVAILABILITY` instead.
- The toolbox gets a `tools-osx/` overlay: clang flags (from CMS's llvm tool), `-isysroot`,
  `-dynamiclib`, `-headerpad_max_install_names`, no GNU ld options, and alpaka without
  `ALPAKA_HAS_STD_ATOMIC_REF`. Do not use `-dead_strip_dylibs`: it produced a dylib with no load
  commands, which dyld refuses to load.

**SIP (System Integrity Protection) and DYLD_* variables**
- SIP strips `DYLD_*` whenever a protected binary (`/bin/bash`, `/usr/bin/env`, ...) is executed.
- SCRAM exec'd `run_gmake.sh` via its `#!/bin/bash` shebang, so the make rules lost
  `DYLD_FALLBACK_LIBRARY_PATH` and all `-L` flags. Fixed in the cms-scram patch (exec `bash` from PATH);
  make's `SHELL` also prefers the PATH bash.
- Build-time python checks start via `#!/usr/bin/env python3`, so they lose `DYLD_*` too:
  - libraries from the release weren't found → explicit rpaths;
  - ROOT didn't find the release's rootmaps, so base-class dictionaries were missing and **class checksums
    changed** → `ROOT_LIBRARY_PATH` is now exported next to the library path in the project
    `Self.xml` (cmssw-config patch).

**CMSSW source fixes for clang/libc++** (patches 0005, 0006), all small and upstreamable:
- floating-point `std::from_chars` doesn't exist in libc++;
- `std::formatter::format` must be const;
- no constexpr `std::abs`/`std::pow`;
- `uint64_t` is `unsigned long long` on macOS, which gives duplicate overloads;
- missing `<sstream>` includes;
- `pthread_setname_np` can only name the calling thread.
- `hls-arbitrary-precision-types` forward-declared `std::complex`, which breaks with libc++'s inline namespace.

**EDM class version checks** are skipped on macOS (`SCRAM_NOEDM_CHECKS=1`). Checksums of classes with
`(u)int64_t` members differ from the Linux ones (`unsigned long long` vs `unsigned long`), even though
the on-disk layout is identical.

**Blocker for macOS runtime: conda-forge ROOT 6.36.10 and the macOS SDK**
- ROOT 6.36.10 on conda-forge ships prebuilt system modules (`Darwin.pcm`, `_DarwinFoundation*.pcm`,
  `std.pcm`, ...) built against `/opt/conda-sdks/MacOSX11.0.sdk`. With any other SDK (Xcode's 26.5, the
  Command Line Tools' 15.x), cling fails on plain `#include <unistd.h>`: "`_OSSwapInt16` has different
  definitions in different modules", "could not build module `_DarwinFoundation3`".
- FWLite parses CMSSW headers at runtime, so it breaks for users. It works when `SDKROOT` points to a
  MacOSX11.0.sdk (tested).
- ROOT 6.38+ generates the Darwin modulemap from the active SDK (root-project/root commit
  `dfc83fa305`), and conda-forge's ROOT 6.40.04 works with the default SDK.
- Possible fix: backport that change to conda-forge/root-feedstock's `6.36.x` branch and rebuild. This was
  **postponed** (decision 9).
- The recipe tests don't catch this, because the test env has `CONDA_BUILD_SYSROOT` set and
  `Declare()` still returns true.

(**Resolved 2026-09-18** by pinning ROOT 6.40 on macOS instead of backporting, and by adding a test
that does catch it. The diagnosis above was right in every detail; only the conclusion — wait for
6.36.x — was wrong. See the 2026-09-18 entry and decision 9.)

### 2026-09-17: layering as conda packages, CORAL and Frontier

**Shared build tooling.** The SCRAM tool file templates, the toolbox generator and the new
layer installer moved out of `cmssw-fwlite` into a `cmssw-toolbox` package (noarch), which
every layer and CORAL uses as a build dependency. Each layer feedstock would otherwise need
its own copy.

**How a layer is packaged.** `cmssw-framework` is the first layer built on top of an installed
`cmssw-fwlite`:
- `scram project <version>` creates a developer area against the installed release;
- the packages of the layer are copied into it and built with `scram b`;
- `cmssw-install-layer` copies the products into the **installed release tree**, refusing to
  overwrite anything: libraries, binaries, `src/`, `python/`, `cfipython/`, and the build
  metadata (`MakeData/DirCache/*.mk`, `BuildFiles/`, `tools/`, `InstalledTools/`) that later
  layers and users' developer areas need. All of those are per-package or per-tool paths, so
  conda packages never share a file. Files that already exist with identical content (the
  per-subsystem `python/<Sub>/__init__.py`) are skipped.
  There is one CMSSW release directory, so the activation scripts of `cmssw-fwlite` keep working
  unchanged and a user's developer area still chains only one level.

**Things that had to change for this to work**
- A layer must not contain a directory for a package that a lower layer owns: SCRAM takes
  `src/<Sub>/<Pkg>` in a developer area as the local definition of that package, and the release's
  library then drops out of every link line. `cmsRun` is therefore built in `cmssw-fwlite`, since
  its source sits in `FWCore/Framework/bin` and that library belongs to the base layer.
- SCRAM only offers a release if `share/cmssw/<arch>/cms/cms-common` exists, and conda does not
  carry empty directories: the directory now holds a README.
- `cms-scram` is a *build* dependency, so its baked-in project database points at `BUILD_PREFIX`.
  A layer build sets `SCRAM_LOOKUPDB` to the host prefix.
- **SCRAM checks that a tool's `INCLUDE`/`LIBDIR`/`BINDIR` exist** when it sets the tool up. So
  the toolbox cannot simply contain every tool of the release: `cmssw-generate-toolbox` now
  leaves out the tools whose directories are missing, and every layer generates the tool files
  for its own externals and adds them to the release with `scram setup`.
- Rebuilding a recipe locally without bumping the build number serves the previous package from
  rattler's cache; `build-local.sh` now drops the cached copies first.

**New external recipes**
- `frontier-client` 2.10.2 (`recipes/frontier-client`): plain Makefile, BSD. Its rules hardcode
  `c++` and only pass `CXXOPT_APP`/`COPT` to the link steps, so the compiler and the link flags
  are overridden on the make command line. The pure python DB-API client it also ships is left
  out, so the package stays python-independent.
- `coral` 2.3.21 (`recipes/coral`): CORAL is a SCRAM project like CMSSW, and cmssw-config carries
  its project definition (`Projects/CORAL`), so it builds with the same toolbox and about 30 s of
  CPU. Oracle, MySQL, the CORAL server and the LFC replica service are dropped. Its products are
  installed into the normal conda layout (`lib/liblcg_*`, `include/LCG`) instead of a SCRAM area;
  CMSSW refers to them through four plain tool files (`coralbase`, `coralkernel`, `coralcommon`,
  `relationalaccess`), which is all CMSSW actually uses.
- **CORAL has no license.** Neither the CMS fork nor the upstream LCG repository has a license
  file or license headers. This is a second licensing blocker next to `utm` and has to be raised
  with CERN/CMS. The recipe is marked `LicenseRef-Unresolved` and cannot be submitted.

**`cmsRun` works, with one open bug.** The layer's tests write an EDM file and read it back,
and `cmsRun` opens a real CMS Open Data MiniAOD over XRootD through the site configuration
below. Reading through `PoolSource` needs `cacheSize=0` though: `RootTreeCacheManager` sets a
cache size on the Events tree and then detaches the `TTreeCache` it created, so ROOT's one-shot
automatic cache setup finds a size but no cache and calls `Error("SetCacheSizeAux", "Not
setting up an automatically sized TTreeCache because of missing cache previously set")`, which
CMSSW's `InitRootHandlers` turns into a fatal exception. Checked and ruled out: the ROOT
version (the CMS fork is upstream `v6-36-00-patches` plus one commit in `TBasket.cxx`, and
nothing touched `TTree.cxx` between that and 6.36.10), the ROOT build options (IMT is on in
both), `system.rootrc`, the `cache-hint` of the site configuration, and the thread count.
`edmProvDump`, `edmFileUtil` and FWLite are not affected. This has to be understood with CMS;
it is currently unclear why their own tests do not hit it.

**A conda environment is not a CMS site.** `PoolSource` needs a site-local configuration
(`$SITECONFIG_PATH/JobConfig/site-local-config.xml` plus a `storage.json` next to it), which at
CMS comes from `/cvmfs/cms.cern.ch/SITECONF`. `cmssw-framework` ships one that describes a
"conda site" using the global CMS services: files are read through the global XRootD redirector
and conditions come from the central Frontier servers, with no Squid proxy. An activation script
points `SITECONFIG_PATH` at it, and a user at a real site can override it.

**Conditions work against the real CMS database.** `cmssw-conditions` (58 packages, about 6 min
on 10 aarch64 cores) builds CondCore and CondFormats against CORAL, and `cmsRun` reads a real
payload from `frontier://FrontierProd/CMS_CONDITIONS`:

```python
CondDB.connect = cms.string("frontier://FrontierProd/CMS_CONDITIONS")
process.beamspot = cms.ESSource("PoolDBESSource", CondDB, toGet=cms.VPSet(cms.PSet(
    record=cms.string("BeamSpotObjectsRcd"), tag=cms.string("BeamSpotObjects_PCL_byLumi_v0_prompt"))))
process.get = cms.EDAnalyzer("EventSetupRecordDataGetter", toGet=cms.VPSet(cms.PSet(
    record=cms.string("BeamSpotObjectsRcd"), data=cms.vstring("BeamSpotObjects"))))
```

```
%MSG-s DataGetter: EventSetupRecordDataGetter:get@beginRun Run: 325175
got data of type "BeamSpotObjects" with name "" in record BeamSpotObjectsRcd
```

That is CORAL, frontier_client, the Frontier servers listed in the conda site configuration and
the payload deserialization all working together. The recipe's own tests stay offline (they check
that the libraries load and that `PoolDBESSource` is registered), because conda-forge CI has no
network; this check is run by hand.

**DD4hep blocks geometry twice over.** The alignment, HCAL and Phase-2 tracker payload
registrations pull in the geometry builders and through them DD4hep, and conda-forge's DD4hep
cannot be used with this stack:
- **Units.** CMS builds DD4hep with `DD4HEP_USE_GEANT4_UNITS=ON` and compiles CMSSW with the
  matching define. conda-forge's does not set it, so it uses TGeo units; setting the define
  anyway would make CMSSW and the library disagree about lengths by a factor of ten wherever a
  value crosses the boundary. The tool file therefore leaves it out, which is self consistent
  but is not what CMS validates.
  **(Revised 2026-09-18: every CMSSW use of a DD4hep unit is a conversion factor, so TGeo units
  are probably fine, not merely self consistent. See the progress log.)**
- **boost.** The DD4hep build for ROOT 6.36.10 (which is the one that matches our pin) was built
  against boost 1.90, while conda-forge's global pinning is still 1.88, so it cannot be installed
  next to anything built against the pinning. Moving the whole CMSSW stack to boost 1.90 would
  work but is exactly the migration churn that killed the previous FWLite feedstock.
  **(Revised 2026-09-18: this is an in-flight conda-forge migration, `libboost190.yaml`, that
  every feedstock has to join anyway, and the target state solves. See the progress log.)**

The conditions layer therefore leaves out the five payload registrations that need geometry
(`CondCore/{Alignment,Hcal,SiPhase2Tracker,L1T,RPC}Plugins`); they belong to a later geometry
layer, together with a DD4hep that CMS's configuration can actually use.

**The serialization generator needs an `llvm-cxxcompiler` tool.** The CondFormats serialization
code is generated by parsing the headers with libclang, and the make rule asks for the *llvm*
compiler's flags. Without a `llvm-cxxcompiler` tool file those are empty, so clang got no
`-std=c++20` and failed on every header that uses `std::format` (`FWCore/MessageLogger`, reached
from `CondFormats/HLTObjects`). The toolbox now has `llvm-cxxcompiler` and `llvm-ccompiler`,
which inherit the gcc flags and drop the ones clang does not understand, as CMS's own tool files do.

**How far `utm` reaches.** Earlier this looked like 3 FWLite packages. `CondFormats/L1TObjects`
blocks, among others, `CondCore/Utilities` (the `conddb` tools), `CondCore/L1TPlugins`,
`DataFormats/RPCDigi`, `EventFilter/L1GlobalTriggerRawToDigi` and the `L1Trigger/*` emulator, so
**it is on the critical path for reconstruction from RAW and for RPC muon reconstruction**. It
does not block conditions access itself (`CondCore/CondDB` and `CondCore/ESSources` do not need it).

### 2026-09-18: how far this can go, and the developer setup

Two questions: how much of CMSSW is realistically buildable, and whether the normal
`cmsrel` / `cmsenv` / `scram b` development loop works against a release installed from conda.

**Build cost is not the wall.** `cmssw-notes/analysis/scripts/reach.py` counts 15,279
translation units outside `test/`. Measured against the three layers that exist
(2,510 TUs, 589 s + 181 s + 351 s wall on 10 native aarch64 cores), and against a single
timed package build (`FWCore/Modules`, 33 TUs, 345 CPU-s), the cost is roughly 3–10 CPU-s per
translation unit depending on how header-heavy the package is. The whole release is therefore
of the order of **25 CPU-hours per architecture**, which at ~1,500 TUs per feedstock is about
2 CPU-hours each: comfortably inside a default conda-forge runner. Size is not a wall either:
the three layers install 217 MB for 2,510 TUs, so a complete release lands near 1.3 GB
installed and a few hundred MB of `.conda` files spread over all the layers.

**Externals are the wall.** `reach.py` walks the dependency graph with a set of externals
marked unavailable and reports what remains buildable:

| scenario | package libs | TUs | share |
|---|---|---|---|
| today | 895 | 6,072 | 40% |
| + dd4hep (geometry) | 1,040 | 8,177 | 54% |
| + utm (L1 menu) | 1,081 | 9,096 | 60% |
| + ML runtimes and L1 ML models | 1,142 | 10,523 | 69% |
| + small unpackaged (clue, fftjet, log4cplus, millepede, ...) | 1,161 | 11,000 | 72% |
| + geant4 | 1,291 | 13,738 | 90% |
| + generators | 1,330 | 14,477 | 95% |
| + GPU and proprietary (cuda, oracle, dip, dCache) | 1,358 | 15,279 | 100% |

So **40% of CMSSW is reachable with what is packaged today**, and the two decisions already
identified — a DD4hep that CMS's configuration can use, and the `utm` license — are worth
20 percentage points between them and are what stands between here and reconstruction.
Everything past that is a long tail of individually small externals. Note the ordering matters:
geant4 on its own only unlocks 58 TUs, because simulation needs the geometry too.

The table assumes every external not listed as blocked really does work; a few in the "today"
row have not been compiled against yet (`onnxruntime`, whose conda-forge header layout differs
from CMS's, plus `classlib` and `davix`). Blocking all three moves the first row from 6,072 to
5,750 TUs, so the 40% is good to about two points either way.

**The data is smaller than it looked.** Mapping the 109 `cms-data` repositories onto the packages
that need them (they are named `data-<Sub>-<Pkg>`) gives 1.65 GB for what is buildable today and
**2.94 GB for reconstruction**, against 8.4 GB for the whole release. The 2.9 GB `SimG4CMS-Calo`
repository that dominates the total is simulation-only. The largest one reconstruction actually
needs is `CalibTracker-SiPixelESProducers` at 0.78 GB, which is within what conda-forge hosts.
So the data is a nuisance rather than a wall, as long as each repository stays its own package and
layers depend only on what they need.

**Splitting is straightforward, with one constraint.** `reach.py --layers 1500` greedily packs
the buildable packages into dependency-respecting layers: **5 more layers** reach reconstruction
and **9 more** cover the entire release, each a feedstock built against the ones below it,
exactly like the three that exist.

The constraint corrects the first-pass partition in D2, which put a package's `src/` library and
its `plugins/` in different groups. That is not possible here: a layer is a developer area, and
`src/<Sub>/<Pkg>` in one is the local definition of the *whole* package, so the release's library
for it drops out of every link line. A package is therefore one indivisible node. Doing it that
way makes the graph cyclic — CMSSW has 9 package cycles that run through plugins, harmless when
everything builds in one area — so the cycles have to be condensed, which just means those
packages share a layer. The largest is 13 packages (PatAlgos, NanoAOD, SiStripClusterizer, DeDx
and friends). None of them straddles the three layers already shipped, and the layer count is
unchanged, so the constraint costs nothing in practice — but a partitioner that ignores it
produces a partition that cannot be built.

**The cost that grows with the layer count is maintenance, not CPU.** Twelve feedstocks all
pinned `==` to each other have to be rebuilt in order for every ROOT, boost, python or numpy
migration, and conda-forge's migration bot cannot drive an ordered chain like that by itself.
That is the same churn that killed the previous FWLite feedstock (see 1.5), and it argues for
keeping the number of layers at the low end of what the runners allow. At 3,000 TUs per layer
(about 4–5 CPU-hours, so roughly 2 h wall on a 2-core runner) only **5 more layers** cover the
whole release, for 8 feedstocks in total; that is the size to aim at, not 12. It also argues for
writing the script that rebuilds the chain in order before there are many layers rather than after.

**The developer loop works.** In an environment with `cmssw-devel` installed:

```
cmsrel CMSSW_20_1_0_pre2
cd CMSSW_20_1_0_pre2/src
cmsenv
git cms-init && git cms-addpkg FWCore/Modules    # or copy it out of $CMSSW_RELEASE_BASE/src
scram b
```

`scram runtime` chains correctly by itself: `CMSSW_BASE` becomes the work area,
`CMSSW_RELEASE_BASE` the conda release, and `PATH` and `LD_LIBRARY_PATH` get the work area
first and the release after it. The compiler is found with no configuration, because
`gcc-cxxcompiler.xml` records `$PREFIX/bin/<triplet>-c++` — the path conda's own compiler
packages install to — and conda rewrites the prefix at install time. The release ships the full
`src/` of every package it built, so a package can be copied out of it without any network access.

Four things had to be fixed to make that true:

- **A rebuilt plugin was ignored.** `CMSSW_PLUGIN_PATH` (set by the activation script, pointing
  at the installed release) was *prepended* to the plugin search path, so it beat the work area
  and `cmsRun` kept loading the release's copy of a plugin the developer had just rebuilt. It is
  now appended: in a work area SCRAM already orders the path correctly, and in a plain
  environment `LD_LIBRARY_PATH` is empty so nothing changes.
- **`cmsrel` and `cmsenv` did not exist.** They are shell functions on a CVMFS installation too
  (from `cmsset_default.sh`), and they now come from `cmssw-devel`'s activation script, which is
  the right home: both only make sense once you can build something. `cmsrel` with no argument
  uses the release the environment provides, since that is the only one it has.
- **Linking failed on `-llzma`.** A run dependency only has to be enough to *load* a library;
  compiling against one also needs its headers and its unversioned link-time symlink, which
  conda-forge often splits into a `-devel` package. The new `cmssw-devel` metapackage pulls in
  the compilers, `make` and everything the layers were built against, and its test runs the whole
  loop above: check out a package, change it, `scram b`, and confirm `cmsRun` sees the change.
  Note that conda's compiler activation exports `CFLAGS`, `CXXFLAGS` and `LDFLAGS` into the
  shell. SCRAM assigns its own in the makefiles, which take precedence over the environment, and
  the builds come out correct — but this is the first place to look if one ever behaves oddly.
- **Two tool files described externals that are not installed.** `dd4hep-core.xml` and `utm.xml`
  were written into the release because `cmssw-generate-toolbox` only checked that a tool's
  `INCLUDE`/`LIBDIR` directories exist — and they default to `$TOOL_BASE/lib` and
  `$TOOL_BASE/include`, i.e. the conda prefix itself, which always exists. The generator now also
  checks that the libraries a tool lists are present, so a package that uses one of those tools
  fails with `Unknown tool` instead of `cannot find -lDDCore` at the end of a long build.

**What a developer cannot do.** Two limits, both of which announce themselves clearly rather
than failing obscurely:
- Only packages whose dependencies are in the installed layers can be built. Checking out
  `RecoTracker/TkTrackingRegions` today gives
  `****WARNING: Invalid tool TrackingTools/DetLayers` and one line per missing package, which
  at least names exactly what is absent.
- A checked-out package's `test/` directory generally does not build: layer builds delete
  `test/` (`rm -rf ./*/*/test`), so test-only dependencies such as `FWCore/TestProcessor` are
  not in the release. Unit tests would need either a `cmssw-tests` layer or test-only
  dependencies added to the existing ones.

**`git cms-init` works too, at a one-off price.** It needs only `CMSSW_BASE` and `CMSSW_VERSION`,
both set by `scram runtime`, plus `git`, `curl` and — unless `--https` is passed — `ssh`. Without
CVMFS there is no local mirror, so the first run makes a full bare clone of `cms-sw/cmssw` into
`~/.cmsgit-cache`: 1.6 GB and about 4 minutes. After that `git cms-init` takes 13 s and
`git cms-addpkg FWCore/Modules` 0.4 s, i.e. the sparse checkout behaves exactly as on lxplus.
A `cms-git-tools` conda package would be a thin noarch recipe (its only real dependencies are
git, curl and openssh). The open question is whether to point it at a patched branch: the release
carries six patches touching nine packages, and a developer who checks one of those out gets the
unpatched upstream version. Upstreaming the patches removes the problem entirely.

### 2026-09-18: the DD4hep blocker is mostly a migration, not a wall

Looked at what it would actually take to unblock geometry, since it is worth 14 percentage
points of the release on its own and gates everything downstream. The picture is better than
the 2026-09-17 entry assumed; the three obstacles are not equally hard.

**boost: an in-flight migration, not a conflict.** Every one of the 12 `dd4hep` 1.37 builds on
conda-forge requires `libboost >=1.90`, while the global pinning (checked against
`conda-forge-pinning-2026.09.18`) still says 1.88 — so `mamba create cmssw-fwlite dd4hep` fails
outright. But the pinning ships `migrations/libboost190.yaml`, an active version migration
(`migrator_ts` = 2026-04-24), and dd4hep has simply been migrated already. Nothing except our
own build holds us at 1.88: ROOT does not depend on boost at all. And the target state solves
today:

```sh
mamba create --dry-run -c conda-forge dd4hep=1.37 root_base=6.36.10 root_cxx_standard=20 \
    libboost-devel=1.90 clhep=2.4.7.2      # resolves
```

So this is not "moving the whole stack to boost 1.90 and taking on migration churn". It is
joining a migration every feedstock has to join anyway, which a feedstock does by taking the
migration's pin into its variant config. Worth doing before there are many layers, not after.

**The C++ standard is a non-issue.** dd4hep publishes both `root_cxx_standard ==20` and `==23`
variants, and the `==20` one exists for exactly our `root_base 6.36.10`. The earlier `cxx23`
conflict in a failed solve was just the solver reporting the other variant.

**Units look much less dangerous than assumed.** The feedstock's cmake line sets
`DD4HEP_USE_GEANT4=ON` but not `DD4HEP_USE_GEANT4_UNITS`, so conda-forge's DD4hep uses TGeo
units where CMS uses Geant4 units. But CMSSW never assumes what DD4hep's base unit is. It does
not reference `DD4HEP_USE_GEANT4_UNITS` anywhere, and every one of the 511 uses of
`dd4hep::mm`, `dd4hep::cm` and `dd4hep::deg` in the release is a conversion: 335 divide by one
(`dpar[1] / dd4hep::cm`), 167 multiply by one, and the handful left over define named scale
constants (`k_ScaleToDD4hep = dd4hep::cm`, `k_ScaleToDD4hepFromG4 = dd4hep::mm`) that are used
the same way. No file mixes them with CLHEP units. The constant comes from DD4hep's own
headers, so the ratio is right whichever base the library was compiled with, as long as the two
sides agree — and with the define left out on both, they do.

That makes TGeo units *probably* fine rather than *merely self consistent*. It is still a
reading of the code, not a measurement: the geometry layer has to be built against this DD4hep
and its numbers compared against the CVMFS release before this is settled. A conda-forge
*variant* for Geant4 units would be a poor fallback anyway — the two builds would differ in the
meaning of their numbers rather than in any ABI signature, so nothing would stop a solver
mixing them.

Net effect: of the three things blocking geometry, one is an ordinary migration, one was never
real, and the third is an experiment rather than a decision.

### 2026-09-18: what a geometry layer would contain

Sketched the next layer now that DD4hep looks reachable, so the work is ready when the boost
migration is taken.

`closure.py Geometry/TrackerGeometryBuilder Geometry/CaloTopology Geometry/Records
DetectorDescription/DDCMS Geometry/CaloEventSetup Geometry/MuonNumbering` gives **23 new
packages, about 1,005 source files** — the same size as `cmssw-conditions` (58 packages, 1,072
TUs), so one ordinary layer. It is `DetectorDescription/{Core,DDCMS,Parser}`,
`Geometry/{CaloEventSetup,CaloTopology,EcalAlgo,EcalCommonData,HGCal*,Hcal*,MuonNumbering,
Tracker*}`, `CondFormats/GeometryObjects`, `MagneticField/{Engine,Records}` and four
`TrackingTools/*` packages.

Two things the dependency graph does not show, both of which have bitten this project before:

- **XML-only packages are invisible.** `Geometry/CMSCommonData` is 8 MB of detector XML in
  CMSSW's own `src/` with no `src/` or `plugins/` directory, so nothing links against it and
  `closure.py` never mentions it — but nothing loads a detector without it. There are 16 such
  packages under `Geometry/` (about 17 MB); reconstruction needs at least `CMSCommonData` and
  `TrackerRecoData`. They belong in the layer's `src-only.txt`. This is the same failure mode as
  the runtime-only `TFileAdaptor` plugin in `cmssw-framework`.
- **`cms-data` is nearly irrelevant here.** Only `MagneticField/Engine` (70 MB) plus three small
  `Geometry/*` repos, about 90 MB in total. The geometry itself ships with CMSSW's source.

**It needs exactly two new externals.** Everything else the 23 packages use is already in the
toolbox. The new ones are `dd4hep` (12 uses, across `DetectorDescription/DDCMS` and the
`Geometry/*CommonData` packages) and `geant4core` — the latter from a single package,
`Geometry/HGCalCommonData`. `cuda` shows up once and only in `Geometry/TrackerGeometryBuilder`'s
`test/`, which layer builds delete, so it is not a dependency at all.

Both new externals are on conda-forge and both have now been checked for configuration
compatibility rather than assumed broken (see the two entries above). If `geant4` turns out to be
a problem after all, dropping `Geometry/HGCalCommonData` and the three HGCal packages that follow
it would isolate it, at the cost of the Phase-2 calorimeter geometry.

So the layer is small, its data is small, and the blocker in front of it is a migration plus a
numerical check. The check itself is easy once the layer builds: compare the numbers a
`DDCompactView`/`TrackerGeometry` produces against the same query on the CVMFS release.

### 2026-09-18: the data packages are probably not out of reach after all

The working assumption has been that `cms-data` has to stay outside conda-forge. Checking the
precedent, that looks too pessimistic. The largest noarch packages conda-forge hosts today are
`presto-server` at 1.32 GB and **`geant4-data-ndl` at 1.12 GB** — a physics data package of
exactly the kind in question — followed by `proj-data` at 0.84 GB and a row of 0.5 GB spaCy
models.

Against that, the reconstruction data set is 2.94 GB spread over 55 repositories whose largest
member is `CalibTracker-SiPixelESProducers` at 0.78 GB: every one of them is smaller than
packages conda-forge already carries. Only `SimG4CMS-Calo` (2.9 GB uncompressed, simulation
only) clearly exceeds the precedent, and it would want checking compressed before being called
impossible.

The same solve also shows **geant4 11.4.2 is on conda-forge** and pairs with the DD4hep build we
want, pulling its own data packages with it. `reach.py` currently blocks geant4 as "needs a
CMS-configured build", which was an assumption rather than a finding; it is worth re-testing,
because geant4 is the single largest remaining step in the ladder (+18 points). That is a
question for after geometry, not before.

### 2026-09-18: conda-forge's geant4 may already be good enough

`reach.py` blocks geant4 as "needs a CMS-configured build", which was an assumption carried over
from the first survey. Comparing `_work/cmsdist/geant4.spec` against the conda-forge feedstock's
`build_geant4.sh` line by line, the configurations agree on everything that matters:

| option | CMS | conda-forge |
|---|---|---|
| `GEANT4_BUILD_MULTITHREADED` | ON | ON |
| `GEANT4_BUILD_TLS_MODEL` | `global-dynamic` | `global-dynamic` |
| `GEANT4_USE_GDML` | ON | ON |
| `GEANT4_USE_SYSTEM_CLHEP` / `EXPAT` / `ZLIB` | ON | ON |
| `GEANT4_USE_USOLIDS` | `"all"` (VecGeom) | not set |

The two that usually break a plugin-loading, multithreaded framework — the TLS model and the
multithreaded build — match exactly, which is the part that would have been expensive to
discover the hard way. The single difference is VecGeom solids, and that is a performance choice
internal to Geant4: **CMSSW never links against VecGeom.** The only mentions of it anywhere in
the release are four ROOT plotting macros (`PlotVecGeom.C` and friends); no `BuildFile.xml`
names the tool.

So the ladder's largest remaining rung (+18 points, 72% to 90%) may not need a custom Geant4 at
all. This is a reading of two build scripts, not a test, so the classification in `reach.py`
stays as it is until something is actually built against it — but it means simulation should be
attempted with conda-forge's geant4 before anyone considers packaging a CMS-configured one.

**linux-64 parity (2026-09-18).** The whole chain was rebuilt on linux-64 after the plugin path
fix: `cmssw-toolbox` 8 s, `cmssw-fwlite` 2,188 s, `cmssw-framework` 569 s, `cmssw-conditions`
1,292 s (its first build on this platform) and `cmssw-devel` 105 s, all passing their tests under
Rosetta emulation — including the developer loop, which rebuilds a package in a work area and
checks that `cmsRun` loads it in preference to the release's copy.

### 2026-09-18: the geometry layer builds, and DD4hep works

Took the boost migration and built the layer. The whole stack rebuilt against **boost 1.90**
with no source changes at all — coral 62 s, fwlite 914 s, framework 226 s, conditions 598 s,
devel 83 s, all passing their tests — which settles the first of the three DD4hep obstacles: it
really was just a migration. Then `cmssw-geometry` built in 611 s and its test produced

```
Iterate over the detectors:
..done!
```

i.e. a CMS detector built from the CMS XML by conda-forge's DD4hep, from a conda environment.

Three things had to be found first, and none of them was the thing everyone expected.

**DD4hep finds its plugins only on `LD_LIBRARY_PATH`.** The CMS detector description is not an
EDM plugin: `DetectorDescription/DDCMS/plugins/BuildFile.xml` builds `dd4hep/*.cc` into a
separate library with `DD4HEP_PLUGIN="1"`, and DD4hep looks those up through its own component
registry (`lib*.components`, generated by `listcomponents_dd4hep`). It searches for them on
`LD_LIBRARY_PATH` and nowhere else — `DD4HEP_LIBRARY_PATH` does *not* work with conda-forge's
build, which carries a patch that changed the plugin search. Nothing in a conda environment puts
the release's `lib/` on that path, so the geometry failed at runtime with

```
dd4hep: Failed to locate plugin to interpret files of type "DDDefinition"
        - no factory:DDDefinition_XML_reader
```

after having already created the TGeoManager, which makes it look like a DD4hep version problem
rather than a path problem. `cmssw-geometry` therefore ships its own activation script that
prepends the release's library directory to `LD_LIBRARY_PATH`. This will need another answer on
macOS, where SIP strips `DYLD_*`.

**The BuildFile graph understates what a layer needs.** `Geometry/CaloEventSetup`'s plugins
include `Geometry/ForwardGeometry`'s Castor and Zdc headers without a `<use>` for it. That is
invisible upstream, where every package's `interface/` is on the include path regardless, and it
cost a ten-minute build to discover. `analysis/scripts/undeclared.py` now scans a layer's sources
for includes of packages no layer installs; it found exactly this one, and the layer is clean
after adding `Geometry/ForwardGeometry` and `Geometry/VeryForwardGeometryBuilder`.

**A missing tool file fails late and quietly.** `rootgeom` and `ofast-flag` had no templates in
the toolbox, so SCRAM printed `****WARNING: Invalid tool rootgeom` and carried on, and the build
died several minutes later on `undefined reference to gGeoManager` — `libGeom` had simply been
dropped from the link line. Both are now in the toolbox. Worth remembering that
`cmssw-conditions` builds with three such warnings of its own today; they are harmless only
because the code that needs those tools is excluded.

**What is still open.** The units question is *not* settled. The geometry builds and iterates,
which it would do in either unit system, so nothing here distinguishes them. Settling it needs a
numeric comparison against the CVMFS release, which cannot be run on this machine: CVMFS is
mounted on the arm64 Mac while the release there is `el9_amd64_gcc13`. The cheapest honest test
is probably to compare against published CMS geometry numbers instead, or to run the same
configuration inside the amd64 container with CVMFS mounted into it.

### 2026-09-18: osx-arm64 catches up with Linux, on a newer ROOT

The whole stack now builds and passes its tests natively on osx-arm64: `frontier-client` 29 s,
`coral` 86 s, `cmssw-fwlite` 646 s, `cmssw-framework` 347 s, `cmssw-conditions` 575 s,
`cmssw-geometry` 592 s, `cmssw-devel` 92 s (M1 Max, 10 cores). `cmsRun` writes and reads an EDM
file, DD4hep builds the CMS detector from the CMS XML, and the developer loop ends with

```
OK: the work area shadows the installed release
```

Before today macOS had only `cmssw-fwlite`, and that was marked *builds, runtime blocked*.

**ROOT 6.40 on macOS, and it does not match the release.** The 2026-09-17 blocker was real and is
unchanged: conda-forge's ROOT 6.36 ships prebuilt Darwin system modules built against
`/opt/conda-sdks/MacOSX11.0.sdk`, and with any other SDK cling dies on `#include <unistd.h>`
("could not build module `_DarwinFoundation3`"). Verified again before changing anything, and
verified that 6.40.04 does the same include with the Command Line Tools SDK and no `SDKROOT` at
all. So `variants.yaml` now selects `root_base` 6.40 on osx and keeps 6.36.10 on Linux. This is a
deliberate deviation from the release's validated ROOT 6.36.13 and is written down in the file
that does it. It should go away once conda-forge's 6.36.x branch backports root-project/root
`dfc83fa305`, or once CMSSW moves to a ROOT whose macOS builds work.

The old test did not catch this, as suspected, for two reasons rather than one: the build and test
environments set `SDKROOT`/`CONDA_BUILD_SYSROOT` and users do not, *and* the CMSSW headers it
declared never reach the Darwin modules that fail. `cmssw-fwlite` now has a test that drops both
variables and declares `#include <unistd.h>`, which does return false on 6.36 with the system SDK.

`root_cxx_standard` had to become an explicit host dependency: 6.36.10 only exists as a cxx20
build, but 6.40 comes in cxx20 and cxx23, and nothing else would have chosen between them.

**Nine portability problems, all small, none of them conceptual.**

- *frontier-client* decided between `.so` and `.dylib` with `[ -f /usr/lib/libc.dylib ]`. Since Big
  Sur the system dylibs only exist inside the dyld shared cache, so that test is false on every
  supported macOS: the build took the Linux path and died on `ld: unknown option: -soname`.
- *cmssw-config* `createSymLinks.sh` uses associative arrays, which need bash 4, and its shebang is
  `#!/bin/bash` — bash 3.2 on macOS. There the array assignments parse as arithmetic subscripts and
  CORAL failed with `division by 0 (error token is "/CoralCommon")`. Now `#!/usr/bin/env bash`.
  While there, the terminal probe `[ -t 1 ] >> /proc/$PPID/fd/1` prints an error on every macOS
  build before correctly concluding "pipe"; silenced.
- *CORAL* `MessageStream.h` declares `operator<<` for `std::_Setfill`, `std::_Setiosflags` and
  friends. Those are libstdc++ implementation details, but the guard is `#elif defined(__GNUC__)`
  — and clang defines `__GNUC__` too. Changed to `__GLIBCXX__`, which is what it actually meant.
- *libc++ availability annotations.* conda-forge's libc++ marks everything introduced in LLVM 19
  and 20 as `introduced = 99.0` with a deliberately invalid attribute pointing at its knowledge
  base, so anything including `<charconv>` (through `<chrono>`, so: a lot) fails with
  `error: expected ')'`. The annotations do not apply here, because the libc++ used at run time is
  the conda one, not the system's; the macOS compiler tool file now defines
  `_LIBCPP_DISABLE_AVAILABILITY`, which is what conda-forge's own ROOT does.
  **This made patch 0005 obsolete**: it replaced floating point `std::from_chars` with `strtod`
  "because libc++ does not implement it". libc++ does implement it now — that is why there is an
  availability annotation at all — so the patch was removing a parser difference that no longer
  existed and introducing one of its own (`strtod` accepts hex floats and leading whitespace,
  `from_chars` does not). Dropped, and checked by compiling and running the call.
- *FWCore/Services and FWStorage/Services*: `pipe2` is Linux-only (replaced with `pipe` +
  `FD_CLOEXEC`, which cannot be atomic on macOS), `execv` takes `char* const*` so the existing
  non-Linux branch never compiled, and `environ` needs `_NSGetEnviron()`.
- *CondCore/CondDB* `Utils.h` uses `HOST_NAME_MAX`, which macOS does not define, and `std::map`
  without including `<map>`.
- *DetectorDescription and Geometry*: four includes of libstdc++ internals
  (`<ext/alloc_traits.h>`, `<ext/pool_allocator.h>`) that nothing uses, and two missing standard
  includes (`<utility>`, `<sstream>`).
- *python extension modules.* `cmsRun` reads its configuration through
  `import libFWCorePythonParameterSet`, and CPython only recognises `.so` as an extension suffix,
  on macOS as well as on Linux — but SCRAM builds `.dylib` there. dyld does not care about the
  extension, so `cmssw-link-python-modules` (new, in the toolbox) adds a `.so` symlink for every
  library that exports `PyInit_<its own name>`. Only the libraries a layer built get an alias, so
  no two conda packages claim the same file. Exactly one library matches today.
- *cpu_features* has no osx-arm64 build: the conda-forge feedstock has `skip: true  # [osx]`, which
  looks like it predates upstream's macOS/aarch64 support (0.8.0, through `sysctlbyname`). It
  builds there unchanged, and `cmssw-framework` cannot be built without it, because
  `FWCore/Services/plugins/CPU.cc` includes `cpu_features_macros.h` unconditionally. Local recipe
  in `cmssw-notes/feedstock-changes/`; the real fix is dropping the skip in the feedstock.

**DD4hep on macOS reads `DYLD_LIBRARY_PATH`.** Same mechanism as on Linux, different variable, and
it is chosen at compile time in `GaudiPluginService/src/PluginServiceV2.cpp`; there is no
`DD4HEP_LIBRARY_PATH` in DD4hep at all. (conda-forge's patch 0004 additionally prepends the
directory of `libGaudiPluginMgr` itself, which is why `$PREFIX/lib` works without help and the
release's `lib/` still does not.) The `cmssw-geometry` activation script now picks the variable at
build time. SIP limits this: a variable exported by an already-running shell does reach a
non-protected child, so `cmsRun` gets it, but a wrapper shell script in between would not.

**The developer area needed a link path that the layer builds had been hiding.** `scram b` in a
work area on macOS failed with `ld: library not found for -lTree`. The link line SCRAM generates
has no `-L` for the conda prefix at all — not for ROOT, boost, TBB or anything else. On Linux that
is harmless because conda-forge's gcc is configured with the prefix in its default search path
("the compiler adds `${PREFIX}/lib` to rpath, so it's better to add `-L` ... as well", says its own
activation script); conda-forge's macOS clang is not, and only gets there through `LDFLAGS`. Every
layer build passes `-L$PREFIX/lib` as `USER_LDFLAGS`, so nothing had noticed. The macOS compiler
tool files now carry `-L$PREFIX/lib -Wl,-rpath,$PREFIX/lib`, which is where it belongs.

**One thing that cannot be fixed yet.** `cmssw-devel` pulls `c-compiler`/`cxx-compiler`, which
resolve to conda-forge's current defaults — clang 18 on osx-arm64, against layers built with
clang 21. Asking for the exact version does not solve: `clangxx_osx-arm64 21` needs
`libcxx-devel 21`, and conda-forge's `root_base` 6.40 needs `libcxx-devel 20`. The two cannot
share an environment. It does not affect the layers, whose build and host environments are
separate, and the developer loop passes as it is, so this is recorded rather than worked around.

**Two of my own mistakes worth recording.** `build-local.sh` deletes rattler's extracted copy of
each package it is about to rebuild, and looked only in `~/.cache/rattler`; on macOS the cache is
in `~/Library/Caches/rattler`. The deletion silently did nothing, so a rebuilt `cmssw-toolbox`
with the same build string was ignored and the fix looked ineffective — twice, before I checked
the file that was actually used. And an XML comment in a tool file contained `--`, which SCRAM's
parser rejects; it prints `ERROR: Failed to parse` and then continues with `root = None`, so the
real message was a `TypeError` twenty lines further down. All ~86 tool templates are now checked
with an XML parser after editing.
