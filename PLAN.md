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
- [ ] SCRAM/cmssw-config osx fixes (dylib handling, GNU tools, link flags).
- [ ] libc++ + clang fixes in CMSSW, upstreamed as PRs to cms-sw/cmssw. Could add a
      CMS clang+libc++ syntax-check IB to prevent regressions.
- [ ] Linux-specific API fallbacks in the 30 affected files.
- [ ] Build-time code execution on osx-arm64 runners (native, not cross).

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
9. **macOS runtime (2026-09-17):** stay on ROOT 6.36.10 on macOS too, for consistency with the CMS
   releases. osx-arm64 remains a *compile-only* target until the ROOT 6.36 interpreter/SDK issue
   (see progress log) is resolved; runtime use on macOS is postponed.

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
