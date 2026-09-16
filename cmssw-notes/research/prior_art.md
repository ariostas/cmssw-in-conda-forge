# CMSSW in conda-forge: prior art and known pitfalls

Research date: 2026-09-16. Sources: GitHub API (`gh`), conda-forge docs and feedstocks, the anaconda.org API, CMS talks. Every claim links to its source. "Verified" means I looked at the repo or data myself, not only a search-engine summary.

---

## TL;DR (decision-relevant)

1. **CMSSW code has been on conda-forge before.** `conda-forge/fwlite-feedstock` (Patrick Gartung and Chris Burr, 2019-2022) shipped FWLite plus Fireworks for linux-64 **and osx-64**, built with CMake from a trimmed CMSSW copy. It was **archived in Jan 2022**. The stated reasons: Fireworks uses OpenGL functions that are deprecated on macOS, CMS had other ways to ship on Linux, and the autotick bot kept sending migration PRs. Pinning conflicts (tbb 2021 vs the TBB that CMSSW supported) also stalled updates.
2. **Active effort in 2026: Code4hep / "Stitched" (makortel, Dr15Jones, kpedro88).** They extracted the CMSSW framework (FWCore + core DataFormats) into a **CMake project with exported targets and a Spack package**, and they build on it with Key4hep pieces (podio, edm4hep, k4geo, geant4). This is the closest match to "split CMSSW into subpackages with CMake", and it is maintained by CMS core-software people. Reuse or align with it.
3. **Other CMake conversions exist but are all frozen snapshots**, not maintained builds: `cms-sw/cmssw2cmake` (2018), `gartung/buildfile2cmake`, `gartung/fwlite` and `gartung/fwdata` (to 2023), `cms-sw/Stitched` (CMake added 2023), and `hep-cce2/cms_miniaod_dict` (2024, for reading MiniAOD). A SCRAM-inside-Spack build of all of CMSSW plus its externals was tried in `iarspider/cms-spack-repo` (2021-2023, 513 packages) and dropped. Nothing exists for Homebrew or Nix, and neither Spack upstream nor Key4hep has CMSSW.
4. **macOS:** CMS built on osx106/107/108 (gcc 4.2 to 4.8) around 2010-2015. The last osx commits in cmsdist and cmssw-config are from 2014-2015. Only three prerelease builds (CMSSW_4_3_0_pre1 to pre3, osx106_amd64_gcc421) are still listed in `releases.map`. A few remnants are still in the code (`__APPLE__` in FWCore, `IS_DARWIN` and `.dylib` logic in cmssw-config, `DYLD_FALLBACK_LIBRARY_PATH` handling in SCRAM). **Clang is exercised continuously, but only with libstdc++:** there is a `CMSSW_20_1_CLANG_X` IB (no LTO) and a clang `-fsyntax-only` PR test. **libc++ is not tested at all.** Gartung's conda builds hit libc++/Apple-specific failures, listed in §2.
5. **conda-forge deps:** ROOT is built with **C++20 by default** (a `cxx23` variant also exists; the `root_cxx_standard` marker package run-exports the standard). It covers linux-64, linux-aarch64, osx-64 and osx-arm64, and has 6.36.x/6.38.x ABI branches. CMS currently uses ROOT 6.36.15. Most HEP externals are present. **Missing:** alpaka, HLS arbitrary-precision types, frontier_client, coral, openloops, herwig7, celeritas, and `cpu_features` for osx-arm64. **osx-64 is quietly going away** in several feedstocks (tbb, onnxruntime, tensorflow, dd4hep all have old osx-64 builds only). **geant4 on conda-forge is C++17 and built without VecGeom.**
6. **CI limits:** the default Azure and GHA runners have a **6 h** limit on 2-4 CPUs. Since June 2026 conda-forge has **sponsored large runners** (Namespace, Blacksmith and Depot, up to 16-64 vCPU on Linux and 6-12 vCPU on osx-arm64). You request them per feedstock through `admin-requests`. pytorch, tensorflow and onnxruntime use them, with job timeouts of 12-24 h. `open-gpu-server` (Cirun) was **decommissioned in March 2026**.
7. **Build-time reference:** CMS release builds take **about 3.2-5.5 h wall time per architecture** on CMS build nodes (examples in §5). CMSSW is **5.5M lines of code → about 3k binary products**, plus **550+ externals** (ACAT 2024). LTO has been on by default since 13_0_X (2-3 % faster) and roughly doubles build cost. On a 4-core runner a full release is far beyond 6 h, so **either large runners plus several feedstocks, or a subset.**
8. **Multi-output vs. multi-feedstock:** all outputs of one recipe build **in the same CI job for each variant**, so the time limit applies to the sum. conda-forge precedent for splitting something that takes hours:
   * **separate feedstocks** for LLVM: `llvmdev` (about 3 h on linux-64) and `clangdev` (about 1.3 h). Qt6 split into `qt6-*` feedstocks.
   * **one build with many outputs** when the whole thing fits in one job: `arrow-cpp` → libarrow, libparquet and others; `vtk` → vtk-base; `root` → root_base.
   * rattler-build `staging:` outputs let you build once and split into many packages, but only inside one job.

---

## 1. Prior packaging of CMSSW or its parts

### 1.1 conda-forge `fwlite` (2019-2022, archived)
- Feedstock: https://github.com/conda-forge/fwlite-feedstock (archived). Original staged-recipes PR "Fireworks: CMS experiment's event display…": https://github.com/conda-forge/staged-recipes/pull/8199 (merged 2019-05-06).
- Last package was `fwlite 11.3.1.2` for linux-64 and osx-64 ([anaconda.org](https://anaconda.org/conda-forge/fwlite)).
- **Source:** the tarball of `gartung/fwlite` (a trimmed CMSSW tree with generated CMakeLists), the `cms-data` repos, sample ROOT files, and `gartung/cmaketools` (HSF find modules).
- **Dependencies:** `root ==6.22.08`, `boost-cpp`, `clhep`, `cms-md5`, `eigen`, `fmt`, `hepmc2`, `gsl`, `libuuid`, `pybind11`, `sigcpp-2.0`, `tbb-devel >=2021`, `tinyxml2`.
- **Build:** C++17, RelWithDebInfo, then `edmPluginRefresh plugin*${SHLIB_EXT}` at build time.
  - On macOS the build rewrote `.so` to `.dylib` in the `*.rootmap` files and set `MACOSX_DEPLOYMENT_TARGET=10.15`.
  - `ignore_prefix_files: lib/*.pcm`, because ROOT pcm files must not be prefix-relocated.
- **Why it was archived** ([PR #57 comments](https://github.com/conda-forge/fwlite-feedstock/pull/57), [issue #58](https://github.com/conda-forge/fwlite-feedstock/issues/58)): gartung wrote *"It makes use of outdated OpenGL functions that are deprecated on macOS. The build will always fail on the latest macOS and we have other ways of distributing the build for linux."* He also asked how to turn off regro-cf-autotick-bot.
  - Earlier friction: *"CMSSW 11.2.0 is only compatible with old tbb"* stalled the tbb 2021 migration ([#43](https://github.com/conda-forge/fwlite-feedstock/pull/43)).
  - An osx deployment-target and gfortran detection problem showed up in [#42](https://github.com/conda-forge/fwlite-feedstock/pull/42).
- **Lessons:**
  - Keep Fireworks and other OpenGL/GUI code out of the macOS build, or make it optional.
  - Budget for migration churn from ROOT, TBB, Boost and Python rebuilds.
  - Keep CMSSW's external versions compatible with conda-forge's global pins.
- Related: `cms-md5` is still on conda-forge (1.0.0, linux-64 and osx-64 only). `cms-combine` is also there, for linux, aarch64, ppc64le, osx-64 and osx-arm64. It has an open issue about **numerical differences between CMSSW-built and conda-forge-built binaries and between Linux and macOS**: https://github.com/conda-forge/cms-combine-feedstock/issues/39. Expect the same validation question for CMSSW.

### 1.2 Gartung's CMake conversions of FWLite, FWData and Stitched (Spack)
- https://github.com/gartung/cmssw-spack (2017-2023): a Spack repo with branches `master`, `fwlite`, `stitched` and `fwdata`. `master` has about 200 packages: CMS-patched externals, `*-toolfile` packages, `cmssw`, `cmssw-scram`, `fwlite`, `fwdata`, `stitched`.
- https://github.com/gartung/fwlite (to 2022, CMSSW 12.4.0), a CMake FWLite tree. Its commit history is a useful **list of macOS fixes**: "Changes needed for macOS" and "More changes for macOS", about 2020-2022. Details in §2.3.
- https://github.com/gartung/fwdata (to 2023): *"all CMSSW data product dictionary and supporting sources"*, enough to read RECO and AOD files with `root.exe`. Built with Spack.
- https://github.com/gartung/buildfile2cmake, forked from `Teemperor/scram2cmake`: generates CMakeLists.txt from SCRAM `BuildFile.xml` and relies on `HSF/cmaketools` find modules. https://github.com/gartung/cmaketools is a fork of `HSF/cmaketools`.
- https://github.com/cms-sw/cmssw2cmake (2018, CMSSW_10_2_0_pre1 era): converts SCRAM build rules and toolfiles to CMake inside an installed release area. It needs a cms environment and has been dead since 2018.
- https://github.com/cms-sw/Stitched: *"an export of the CMSSW Framework packages and a minimal set of data packages needed for testing the Framework"*.
  - It is generated through the cms-bot filter [`cmssw-subprojcts/Stitched.filter`](https://github.com/cms-sw/cms-bot/tree/master/cmssw-subprojcts). The filter covers DataFormats Common, Provenance, StdDictionaries and friends, plus about 25 FWCore packages.
  - A top-level CMakeLists.txt was added 2023-03-01, with `cms_rootdict` and `genreflex` macros and an `edmPluginRefresh` post-build step. The repo has not been pushed since.
- https://github.com/hep-cce2/cms_miniaod_dict (2024-2025, Chris Jones for HEP-CCE):
  - A CMake-buildable subset of CMSSW_14_1_0_pre6, *"enough of CMSSW to be able to read CMS' MiniAOD"*.
  - GPU data structures were removed, HLS and one other header-only package are vendored, and CMakeLists were generated from BuildFile.xml.
  - **Pitfall it notes:** *"The CMS version [of CLHEP] appears to have changed some global `const` variables to `constexpr` and the CMSSW code requires the `constexpr` version."* Check this against conda-forge's clhep 2.4.7.2. Stitched's Spack recipe uses upstream `clhep@2.4.7.2:`, so it is probably fine now.
  - It uses the external `hepmc` 2.06.10 from `cms-externals` and ships its own `FindHepMC.cmake`.

### 1.3 Code4hep / Stitched alpha (2025-2026, active) — most relevant
- Org: https://github.com/code4hep (repos: `Code4hep`, `build`, `c4h-dist`, `c4h-spack-packages`, `stitched-alpha2`, `stitched-example`, `extract-cmssw`, `code4hep-doc`, and a `cmssw` fork).
- **Stitched alpha 2:** https://github.com/code4hep/stitched-alpha2, created May 2026, last push Aug 2026. makortel says the framework is *"extracted from CMSSW"* *"with minimal amount of changes to make the framework usable outside of CMS"*.
  - The history is re-extracted with `git-filter-repo` ([extract-cmssw](https://github.com/code4hep/extract-cmssw)): a `cmssw_master` branch plus tags like `CMSSW_<date>_<hash>`, with Stitched-specific patches on `main_<date>` branches.
  - Hand-written, modern CMake: `CMAKE_CXX_STANDARD 20`, `find_package` for Boost (program_options only), TBB, Python3, tinyxml2, c4h_md5, CLHEP, pybind11, CpuFeatures, uuid (pkg-config) and ROOT (Core, RIO, Net, Hist, Tree).
  - It installs exported `Stitched::` targets, `StitchedConfig.cmake` and env scripts. Plugin cache generation is automatic (`stitched_generate_plugincache()`).
  - Libraries are **renamed** `stitched_FWCore_*` and `stitched_DataFormats_*`. Converted `BuildFile.xml` files were removed.
  - `add_link_options(LINKER:-z,defs)`, a GNU-ld flag, means macOS is not wired up yet.
- **Spack package** https://github.com/code4hep/c4h-spack-packages (`stitched`, `c4h-md5`, `stitched-example`; a PR adds `code4hep`, `k4geo` and `geant4`):
  - Dependencies: `boost@1.80:+program_options`, `intel-tbb@2022.3.0:`, `python@3.12.4:`, **`tinyxml2@6.2.0` (exact pin: "later versions would require changes in the namespacing")**, `clhep@2.4.7.2:`, `py-pybind11@3.0.2:`, `cpu-features@0.9.0:+shared`, `root@6.36.0:`, `util-linux-uuid` (Linux only).
  - `gdb` is a runtime dependency on Linux only; the recipe notes it *"Does not build trivially on MacOS"*.
  - It has a `cxxstd` variant of 20 or 23. The platform conditionals show that macOS is intended.
- **Code4hep** https://github.com/code4hep/Code4hep is a "dedicated Code4hep subsystem for Stitched framework". It uses `find_package(Stitched REQUIRED)`, has `c4h_*` CMake helper functions, and holds packages for PodioUtilities, G4Application, Generators, Geometry and IO.
  - The [build](https://github.com/code4hep/build) repo is *"an interim solution to bootstrap a CMake-based installation, still using CMSSW dependencies"*. It installs cmake, podio, edm4hep, geant4, lcio, k4geo, c4h_md5, stitched and code4hep on top of a CMSSW release area.
- Why it matters: this is the upstream-sanctioned direction for CMake-ifying the CMSSW framework. A conda-forge `stitched` or `cmssw-framework` feedstock could be built from it almost directly. Coordinate with makortel before inventing a parallel CMake layer.

### 1.4 CMS's official Spack evaluation (2021-2023, dropped)
- https://github.com/iarspider/cms-spack-repo (Ivan Razumov and Andrea Valenzuela, CMS core software). Branches `CMSSW_12_1_X` to `CMSSW_13_0_X`, 513 `package.py` files.
  - `Cmssw(ScramPackage)` **wraps SCRAM inside Spack** and emulates the IB flavors (COVERAGE, DBG, UBSAN, CLANG, CXXMODULE…).
  - It also contains a `cmssw-cmake` package that uses `scram2cmake` for CMSSW_10_2_0_pre1.
- Related cms-bot PRs ("Add scripts to handle Spack installation", "Spack: move installation under week number", "Add config.map entry for Spack build", 2022): https://github.com/cms-sw/cms-bot/pull/1773, /1775, /1776, /1880. cmsdist PRs such as "[Spack] Update py-packages" (#7767) and "Update some python packages to align with Spack" (#8116).
- `cms-sw/cms-spack` is an empty repo created 2022-11-09. `cms-sw/cmsdist.bits` is an empty repo created 2026-06-03; it may be an evaluation of ALICE's `bits` build tool.
- Outcome: no Spack-built CMSSW was ever adopted. SCRAM plus cmsBuild (pkgtools) is still the production path.

### 1.5 CMS's own FWLite partial build (in production)
- cmsdist `fwlite.spec` with `fwlite_build_set.file` (153 packages) and `fwlite-tools.spec`. These show the dependency closure CMS itself considers "FWLite":
  - alpaka, eigen, fmt, tbb, boost, clhep, hepmc, hepmc3, hls, python3, root, sigcpp, libuuid, xerces-c, zlib, vdt, tinyxml2, md5, pybind11, utm, llvm, cuda and rocm (optional).
- The build patches out `FWCore/Framework/bin`, `*/test`, `DataFormats/*/plugins` and `CommonTools/Utils/plugins`, and removes `MessageLogger_cfi.py`.
- It is built as an additional IB test: [cms-bot `build-fwlite`](https://github.com/cms-sw/cms-bot/blob/master/build-fwlite), `ADDITIONAL_TESTS=...fwlite...` in `config.map`. This is a good template for a "cmssw-fwlite" output.

### 1.6 Other ecosystems
- **Spack upstream** (`spack/spack-packages`): no `cmssw` package; only `evtgen` mentions CMSSW.
- **Key4hep-spack**: no CMSSW. Its relevance is Code4hep's use of podio, edm4hep and k4geo, and the talk [Key4HEP & Spack (CHEP 2021)](https://indico.cern.ch/event/1036588/contributions/4353224/attachments/2242569/3802587/2021-05-11-CHEP-Spack.pdf).
- **LCG stacks:** no CMSSW.
- **Homebrew and Nix:** nothing found in GitHub search, nixpkgs issues or the web.
- The cms-sw org also has a "cmssw-framework" snapshot (2016), `cmssw-modulemap` (C++ modules, 2019) and `circles` (library-size visualization).

---

## 2. macOS history and clang/libc++ status

### 2.1 History
- **SCRAM_ARCHs:** osx106_amd64_gcc421 and gcc462, osx107_amd64_gcc462, osx108_amd64_gcc481, and later osx10*_amd64 builds (search results; the [SCRAM ReleaseNotes](https://github.com/cms-sw/SCRAM/blob/master/ReleaseNotes.txt) mention osx archs).
  - Today's `https://cmssdt.cern.ch/SDT/releases.map` lists only CMSSW_4_3_0_pre1 to pre3 on `osx106_amd64_gcc421`. osx never became a production architecture after that.
- **Timeline from commit history (verified with `gh search commits`):**
  - cmsdist: many Darwin fixes by David Abdurachmanov in 2013-2014 (gcc 4.8 on Darwin, ROOT with Cocoa disabled, llvm, xerces, nss, thepeg…). The last osx-specific commits are 2015 ("lapack: remove osx*_*_gcc421" on 2015-12-10, and an Oracle Darwin tweak).
  - cmssw-config: `install_name_tool` for `.dylib` (2010), DYLD handling (2012), "various osx fixes: big plugin extension…" (2014-10-08). Nothing after 2014.
  - cms-bot: osx `df` and `md5` tweaks in 2014-2015. pkgtools: "Fix typo for OSX building" in 2015.
  - So **macOS support effectively died around 2015** (CMSSW 7_x), with no formal announcement found.
- **2017 revival attempt with Spack** by gartung: cmssw PRs for "macOS clang and libc++":
  - merged: [#17344](https://github.com/cms-sw/cmssw/pull/17344) FWCore/Utilities, [#17358](https://github.com/cms-sw/cmssw/pull/17358) PileupSummaryInfo, [#17380](https://github.com/cms-sw/cmssw/pull/17380) CaloTowers, [#17155](https://github.com/cms-sw/cmssw/pull/17155) (missing `<functional>`)
  - closed: [#17343](https://github.com/cms-sw/cmssw/pull/17343), [#17357](https://github.com/cms-sw/cmssw/pull/17357), and [#17345](https://github.com/cms-sw/cmssw/pull/17345) ("run scripts on macOS with **SIP** enabled", closed as no longer needed)
- **2020 conda FWLite on macOS:** tracked in [cmssw#28894](https://github.com/cms-sw/cmssw/issues/28894), "Building FWLITE 11.0.0 on macOS with Conda". Details in §2.3.
- Historical: [cmssw#14113](https://github.com/cms-sw/cmssw/issues/14113). **Mixed-case duplicate file names broke `git clone` on case-insensitive APFS/HFS+.** Worth re-checking the current tree for case collisions.

### 2.2 Remnants in current code (verified)
- **`FWCore/PluginManager/src/standard.cc`:** on `__APPLE__` it reads `DYLD_FALLBACK_LIBRARY_PATH` instead of `LD_LIBRARY_PATH` to find plugin directories.
  - ⚠ SIP strips `DYLD_*` variables when processes are launched through `/bin/sh` or other system binaries.
  - In a conda env, libraries sit in `$CONDA_PREFIX/lib`, so a patch should add a dedicated search path, for example an env var like `CMSSW_PLUGIN_PATH` set by an activation script, or a compiled-in prefix.
- **`FWCore/PluginManager/bin/refresh.cc`:** `PER_PROCESS_DSO 20` on `__APPLE__`.
- **`FWCore/Framework/bin/cmsRun.cpp`:** raises `RLIMIT_NOFILE` to `OPEN_MAX` on Apple.
- **`FWCore/Framework/src/EventProcessor.cc`:** `#ifndef __APPLE__ #include <sched.h>` (CPU affinity).
- **`FWCore/Framework/src/make_shared_noexcept_false.h`:** a libc++ workaround for `noexcept(false)` destructors.
- **`FWStorage/StorageFactory/src/RemoteFile.cc`:** `_NSGetEnviron`. `FWStorage/XrdAdaptor` has `__MACH__` branches.
- Also: `DQMServices/Core/src/DQMNet.cc`, `EventFilter/Utilities/src/EvFDaqDirector.cc`, `CalibCalorimetry/EcalLaserSorting`, `SimCalorimetry/EcalElectronicsEmulation/bin/GenABIO.cc`.
- **cmssw-config** `SCRAM/GMake/Makefile.rules`: `IS_DARWIN` when `SCRAM_ARCH` matches `osx%`, `SHAREDSUFFIX := dylib`. Also `Projects/CMSSW/BuildFile.xml` `<ifos name="darwin">`.
- **SCRAM** `SCRAM/Core/RuntimeEnv.py`: rewrites `LD_LIBRARY_PATH` to `DYLD_FALLBACK_LIBRARY_PATH` for osx archs.
- **cmsdist:** about 40 specs still carry `osx` or `darwin` conditionals (root, boost, geant4, xrootd, llvm, gcc, …).

### 2.3 Concrete libc++ / Apple-clang breakages seen (gartung, 2020-2022)
From [cmssw#28894](https://github.com/cms-sw/cmssw/issues/28894) and the `gartung/fwlite` commits ["Fixes for macOS"](https://github.com/gartung/fwlite/commit/03000a79059ad17f0c20d1a101a6e0470820c4af), ["Changes needed for MacOS"](https://github.com/gartung/fwlite/commit/9c41b51a1836bd793cd2b18e8508876e3641f9ed), ["More changes for macOS"](https://github.com/gartung/fwlite/commit/7de0dbdf29ea9956e2b7fc01422103afa96f4075) and ["Changes needed for macOS"](https://github.com/gartung/fwlite/commit/8493331ff8a53f5f28882fb2dea619931a0a87ae):

| Symptom | Cause | Status in CMSSW today |
|---|---|---|
| `M_PIl` unknown | glibc extension, missing in macOS libm | `angle_units.h` now uses `M_PI` (fixed). `M_PIl` is still used in DPGAnalysis/SiStripTools, JetMETCorrections/FFTJetObjects and Validation/RecoTrack. |
| `std::array` incomplete type | missing `#include <array>` (libstdc++ includes it transitively) | Fixed at the time. **This class of bug keeps coming back**; libc++ removes transitive includes aggressively. |
| `std::auto_ptr` in `classes_def.xml` I/O rules | removed from libc++ in C++17 | now 0 occurrences in SimDataFormats/GeneratorProducts (fixed) |
| `optional::value()` unavailable | Apple availability markup requires macOS ≥ 10.14 | conda-forge's minimum is now 11.0 (non-issue) |
| `constexpr ESProxyIndex() noexcept = default;` rejected | clang default-member-initializer rule | Check the current code |
| `constexpr` using `std::pow` (`TTBV.h`) | GCC treats cmath as constexpr builtins; clang does not | Still present in `DataFormats/L1TrackTrigger/interface/TTBV.h` and others. gartung "fixed" it by replacing the expression with `i*i`, which is **wrong**; don't copy that. |
| `crypt dl nsl rt` link libraries | Linux-only libraries | Drop them on macOS. Use `stdc++fs` on Linux and `c++experimental` on old macOS; not needed with a modern libc++. |
| `plugin*.so` glob and `.so` in rootmaps | macOS suffix is `.dylib` | CMake generator must use `CMAKE_SHARED_*_SUFFIX` |
| Fireworks OpenGL | deprecated on macOS | reason for archiving the fwlite feedstock |

### 2.4 Does CMSSW compile with clang today?
- **Yes, against libstdc++ on Linux.**
  - `cms-bot/config.map` has `RELEASE_QUEUE=CMSSW_20_1_CLANG_X` using `CMSDIST_TAG=IB/CMSSW_20_1_X/clang` with `BUILD_OPTS=no-lto`. The clang cmsdist branch differs from master only in `llvm.spec` (537 commits ahead, 1 file changed; LLVM 21.1.4 in cmsdist).
  - Production queues have `PRS_TEST_CLANG=1`, so every PR runs `scram build COMPILER='llvm compile'` with `-fsyntax-only` ([pr_testing/test_multiple_prs.sh](https://github.com/cms-sw/cms-bot/blob/master/pr_testing/test_multiple_prs.sh)). Clang front-end compatibility is therefore maintained continuously.
  - LTO is off for CLANG IBs because *"we cannot link against external libraries, e.g., dd4hep, built with gcc"* ([cmsdist#8335](https://github.com/cms-sw/cmsdist/issues/8335)).
- **No libc++ or macOS testing exists**, and the clang-analyzer / static-checks runs also use libstdc++. Expect a steady trickle of missing-include and GCC-extension issues, plus availability-macro problems.
- New option on conda-forge: **GCC 15 with libc++ on macOS** is available since Nov 2025 ([blog](https://conda-forge.org/blog/2025/11/21/gcc-macos/)). It keeps GCC semantics (constexpr builtins, `M_PIl`?) while staying ABI-compatible with clang-built packages such as ROOT. Missing-include issues from libc++ would remain, and ROOT/cling on macOS is clang-based anyway.

---

## 3. conda-forge state of key dependencies (verified via the anaconda.org API, 2026-09-16)

| package (conda-forge) | latest | platforms at latest | cmsdist (IB/CMSSW_20_1_X) | notes |
|---|---|---|---|---|
| `root` / `root_base` | 6.40.04 | linux-64/aarch64/ppc64le, osx-64/arm64 | 6.36.15 | **`root_cxx_std` variants 20 (preferred) and 23**; `root_cxx_standard` marker run_export; ABI branches 6.36.x and 6.38.x; C++20 is fine |
| `geant4` | 11.4.2 | linux-64/aarch64, osx-64/arm64 | 11.4.2 | `CMAKE_CXX_STANDARD=17`, MT on, GDML on, **no VecGeom**; CMS builds with vecgeom and LTO |
| `clhep` | 2.4.7.2 | all unix | 2.4.7.2 | constexpr caveat (§1.2) |
| `hepmc3` / `hepmc2` | 3.3.1 / 2.06.11 | all unix | 3.3.1 / 2.06.10 | |
| `pythia8` | 8.312 | all unix | 8.317 | behind |
| `fastjet-cxx`, `fastjet-contrib` | 3.5.1 / 1.104 | all | 3.4.1 / 1.101 | ahead |
| `xrootd` (`libxrootd-devel`) | 6.1.1 | all unix | 6.0.2 | split outputs |
| `tbb-devel` | 2023.1.0 | **no osx-64 at latest** (osx-64 stops at 2023.0.0) | 2022.3.0 | |
| `dd4hep` | 1.37 | linux-64/aarch64, osx-arm64 (osx-64 stuck at 1.34) | v01-37x | depends on `root_cxx_standard` |
| `vecgeom` | 2.0.0 | linux-64/aarch64, osx-64/arm64 | 2.1.1 | built `-DBACKEND=Vc -DVECGEOM_GDML=OFF` |
| `alpaka` | **missing** | | 2.1.1 | header-only; would need a staged-recipe |
| `libtorch` (pytorch-cpu feedstock) | 2.13.0 | linux-64/aarch64, osx-64/arm64, win | (py3-torch) | built on Namespace 16 CPU / 12 CPU osx runners |
| `libtensorflow_cc` (tensorflow feedstock) | 2.21.0 | **linux-64 and osx-arm64 only** (aarch64 at 2.19.1, osx-64 at 2.18.0) | 2.21.0 | CMS uses TF AOT/XLA (`tensorflow-xla-runtime`) as well |
| `onnxruntime-cpp` | 1.30.0 | linux-64/aarch64, osx-arm64, win (osx-64 at 1.22.2) | | |
| `libboost-devel` | 1.92.0 | all | 1.92.0 | |
| `tinyxml2` | 11.0.0 | all | **6.2.0** | CMSSW and Stitched pin 6.2.0 ("namespacing") → **patch needed** |
| `fmt` | 12.2.0 | all | 10.2.1 | fmt major-version API churn |
| `xerces-c` | 3.3.0 | all | 3.1.3 | |
| `eigen` | 5.0.1 | all | 5.0.1 | |
| `vdt`, `libsigcpp` (3.6), `sigcpp-2.0`, `heppdt` (2.06.01 vs CMS 3.04.01!), `evtgen` (2.2.3 vs 2.0.0), `photos`, `lhapdf`, `rivet`, `yoda`, `sherpa` (3.0 vs 2.2.16), `thepeg` (linux only), `davix`, `cppunit`, `gsl`, `hdf5`, `libuuid`, `nlohmann_json`, `pybind11` | present | mostly all unix | | version skews to check |
| `cpu_features` | 0.9.0 | **no osx-arm64** | | Stitched requires it |
| `cms-md5` | 1.0.0 | linux-64, osx-64 only | md5 2.0.0 (`c4h-md5` in Code4hep) | needs refresh |
| `alpaka`, `hls` (HLS arbitrary precision), `frontier_client`, `coral`, `openloops`, `herwig7`, `celeritas`, CMS `acts` build | **not found** | | | |

### 3.1 ROOT feedstock specifics
Sources: [recipe.yaml](https://github.com/conda-forge/root-feedstock/blob/main/recipe/recipe.yaml), [build_root.sh](https://github.com/conda-forge/root-feedstock/blob/main/recipe/build_root.sh) and [conda_build_config.yaml](https://github.com/conda-forge/root-feedstock/blob/main/recipe/conda_build_config.yaml).
- `ROOT_CXX_STANDARD` comes from the variant: `root_cxx_std: [20, 23]` with `preferred_root_cxx_std: "20"` (down-prioritized variants). The build string is `cxx20_h…`.
  - Downstream packages get `root_cxx_standard ==20` through run_exports, so CMSSW packages will be pinned to the C++20 ROOT automatically.
- It uses conda-forge's external `llvmdev`/`clangdev` 20.1.8 with ROOT-specific clang patches (`clangdev … root_64004*`), `builtin_clang=OFF` and `builtin_cling=ON`.
  - On macOS it pins `c_compiler_version`/`cxx_compiler_version: 20`, because *"libc++ shipped by the conda-forge compilers on MacOS may not be compatible with the version of clang used by … cling"*.
  - At runtime it requires `libcxx-devel 20.*` (osx) or `libstdcxx-devel`/`sysroot` (linux) plus the `*_impl` compiler, **because cling needs the headers**. Since August 2026 the conda-forge default is clang 21 ([news](https://github.com/conda-forge/conda-forge.github.io/blob/main/news/2026-08-06-moving-to-gcc-15-clang-21.md)). Watch for header or PCH mismatches when CMSSW dictionaries are built with clang 21 against a ROOT whose cling is LLVM 20.
- Several macOS patches disable libc++ availability checks in rootcling, makepch and the cling runtime, and add a libc.modulemap.
- `runtime_cxxmodules=OFF` only when cross-compiling; native builds use the default (modules on).
  - CMSSW production uses rootmap plus rdict.pcm dictionaries; C++-modules builds are the separate `CMSSW_*_CXXMODULE_X` IB. Gartung's fwlite loaded rootmap dictionaries into conda ROOT fine.
  - `*.pcm` files **must be excluded from prefix replacement** (`ignore_prefix_files`).
- PyROOT puts `python` in `root_base` host requirements. Any CMSSW package with `python` in host (pybind11, PythonParameterSet) gets a **python × root_cxx_std build matrix**. ROOT itself runs 24 linux jobs.
- CI: Linux on GHA (`ubuntu-latest`, 4 CPU): **about 1.0-1.2 h linux-64, 0.6 h aarch64 (native arm runners), 1.9-2.5 h ppc64le (emulated)**. osx-64 and osx-arm64 on Azure.

### 3.2 CI time limits and large runners
- **Default runners** ([reference](https://github.com/conda-forge/conda-forge.github.io/blob/main/docs/reference/runners.md)): Azure `ubuntu-latest` has 2 CPU, 7 GB RAM and 6 h; Azure `macOS-15` / `macos-15-arm64` have 3 CPU, 7-14 GB and 6 h; GHA `ubuntu-latest` / `ubuntu-24.04-arm` have 4 CPU, 16 GB, 14 GB disk and 6 h.
  - Linux feedstocks moved to GHA in Mar 2026 ([news](https://github.com/conda-forge/conda-forge.github.io/blob/main/news/2026-03-08-move-to-github-actions.md)). Max **50 concurrent GHA jobs per feedstock**; jobs may be cancelled if org limits are near. Windows and macOS still default to Azure.
- **Large runners** ([blog, 2026-06-17](https://github.com/conda-forge/conda-forge.github.io/blob/main/blog/2026-06-17-large-runners-gha.mdx), [how-to](https://conda-forge.org/docs/how-to/advanced/self-hosted-runners/)):
  - Sponsored by Namespace.so, Blacksmith.sh and Depot.dev, requested through a PR to [conda-forge/admin-requests](https://github.com/conda-forge/admin-requests) (`action: namespace|blacksmith|depot`).
  - Labels are set via `github_actions_labels` in `recipe/conda_build_config.yaml`, with `provider: github_actions` and a larger `github_actions: timeout_minutes`.
  - Sizes: Namespace 8/16 CPU Linux (32/64 GB) and 6/12 CPU osx-arm64 (14/28 GB); Blacksmith up to 16 vCPU Linux and 12 vCPU macOS (48 GB); **Depot up to 64 vCPU / 256 GB Linux** and 8 CPU osx-arm64.
  - The blog says these are for feedstocks that *"cannot be built … within the allocated six hours, or run out of RAM or disk despite all possible workarounds"*.
- **Cirun / open-gpu-server:** *"decommissioned on March 13th"* 2026. The Cirrus Runners replacement was abandoned after Cirrus Labs was acquired. **No GPU CI currently.** `conda-forge/.cirun` still exists and "other providers may be available via cirun.io".
- **Observed heavy builds:**
  - pytorch-cpu: `timeout_minutes: 1440`, Namespace 16 CPU Linux, 12 CPU osx-arm64 (osx-64 cross-built from osx-arm64). Jobs take 1.3-7.5 h (CUDA aarch64 about 7.5 h).
  - tensorflow: `timeout_minutes: 1080`, Namespace, 1.6-2.8 h.
  - onnxruntime: `timeout_minutes: 720`, Namespace, 0.3-2.7 h.
  - llvmdev: default GHA, **3.1 h linux-64**. clangdev: 1.3 h. vtk: 2.4-4.5 h on default runners (Azure for Windows).
- **Policy:** no off-label CI use. Only the smithy-generated workflows are allowed ([infrastructure docs](https://conda-forge.org/docs/maintainer/infrastructure/)).
- **macOS minimum is now 11.0** ([news 2026-02-06](https://github.com/conda-forge/conda-forge.github.io/blob/main/news/2026-02-06-macOS-11.md)). osx-64 builds are increasingly done by cross-compiling from osx-arm64 (`build_platform: osx_64: osx_arm64`) or dropped.

---

## 4. Multi-output vs. multi-feedstock for huge C++ codebases

- **conda-forge knowledge base** ([Multi-output recipes](https://conda-forge.org/docs/maintainer/knowledge_base/#multi-output-recipes)) lists the use cases: library plus bindings, runtime plus headers, base vs. full dependency sets (`matplotlib-base`), CPU vs. GPU. Pitfalls: use a top-level name different from the outputs (`*-split`) and give each output its own script names.
- **Key mechanical fact:** a feedstock job builds *all* outputs of the recipe for one variant in one CI job. Splitting into outputs does **not** parallelize the build or reset the 6 h clock. Only **separate feedstocks** (or separate variants) run in separate jobs.
- **Build once, split into outputs** (fits in one job):
  - `arrow-cpp` ([meta.yaml](https://github.com/conda-forge/arrow-cpp-feedstock/blob/main/recipe/meta.yaml)): the top-level `apache-arrow` build, then `install-libarrow.sh` per output (libarrow, libarrow-acero, -compute, -dataset, -flight, -flight-sql, -gandiva, -substrait, libparquet, arrow-utils, parquet-utils, plus the `libarrow-all` metapackage). 0.5-1.1 h per job.
  - `vtk` (rattler-build): `vtk-split` → `vtk-base`, `vtk-io-ffmpeg`, `vtk`.
  - `llvmdev`: `llvm-package` → llvmdev, libllvmNN, llvm-tools, libllvm-cNN, lit.
  - `xrootd`: libxrootd, libxrootd-devel, xrootd-cli, python-xrootd, xrootd.
  - `root`: root_base, root, root_cxx_standard.
  - `geant4`: geant4-toolkit… geant4, geant4-examples.
- **rattler-build `staging:` outputs** ([docs](https://rattler-build.prefix.dev/latest/multiple_output_cache/)): *"A staging output runs its build plan once, then copies its files directly into each inheriting package's prefix"*. The work directory is kept too, so outputs can run `cmake --install --component`.
  - Staging caches are reused across Python versions if python is not in the staging variant keys. This helps keep the heavy C++ build out of the python matrix.
  - `--error-overlapping-files` and `--error-unused-staging-files` enforce clean splits.
- **Separate feedstocks from one source tree** (each piece takes hours or has its own cadence):
  - LLVM: `llvmdev`, `clangdev`, `compiler-rt`, `lld`, `libcxx`, `openmp` each have a feedstock. clangdev builds against the llvmdev package: 3.1 h plus 1.3 h on linux-64.
  - Qt6 (2025-2026): `qt6-main` was deliberately slimmed and modules *"broken out into separate feedstocks, each producing its own `qt6-*` package version-locked to `qt6-main`"*, for size and license reasons ([blog](https://github.com/conda-forge/conda-forge.github.io/blob/main/blog/2026-07-01-qt6-status-in-conda-forge.md)).
  - pytorch keeps one feedstock (`pytorch-cpu`) with libtorch and pytorch outputs, but on large runners with 24 h timeouts.
- **Implications for CMSSW:**
  - A layered set of feedstocks mirroring the dependency DAG is the only way to stay within per-job limits without one giant large-runner job. For example: framework/Stitched → DataFormats/FWLite → Reco/Sim subsystems → BigProducts-equivalents.
  - Each feedstock can still use staging outputs for per-package or per-subsystem splits.
  - Cost: exact version pinning between feedstocks (`pin_subpackage` or `max_pin='x.x.x'` equivalents), coordinated rebuilds on every ROOT/TBB/Boost/Python migration (the fwlite lesson), and a longer release chain. Bot automerge helps.
  - Consider a **single "cmssw-split" feedstock on Depot 64-vCPU runners** as a first step, then split once cost and timing data exist.

---

## 5. CMSSW-specific build facts and published numbers

- **Size** ([ACAT 2024, "Optimizing the CMSSW Infrastructure for Run 3", Valenzuela, Muzaffar, Razumov](https://indico.cern.ch/event/1330797/contributions/5796567/attachments/2819181/4922564/ACAT2024-CMSSWOptimization-Valenzuela.pdf)):
  - *"5.5M lines of code leading to 3k binary products"* and *"550+ external packages built from source"*.
  - *"Around 40 IBs are build and deployed every day"*; all IBs are deployed every 12 h to CVMFS.
- **LTO:**
  - Flags: `-flto -fipa-icf -flto-odr-type-merging -fno-fat-lto-objects`.
  - Default since CMSSW_13_0_X (Feb 2023), for a 2-3 % speedup. geant4, vecgeom, g4hepem, dd4hep and celeritas are also built with LTO.
  - Incompatible with the CUDA IB (NVCC), the ASAN IB, the CLANG IB (GCC-built externals) and older ppc64le GCC. The `NONLTO_X` IB and the `no-lto` build option exist.
  - No build-time numbers were published. Generic GCC LTO roughly doubles build time or more and needs a lot of link memory; the GCC 15 pre-processing RSS problem is tracked in cmsdist#10848 (`-ftrack-macro-expansion=0`).
- **PGO:** 7-8 % speedup, not yet approved by physics validation as of 2024. `cmssw#42721`: "CMSSW_13_2_2 fails to build with PGO and LTO". It needs an instrumented build, a profiling run and a rebuild.
- **Release build wall times** (computed from cms-bot comment timestamps, "build has started" to "build has finished", on CERN OpenStack `cmsbuild9xx` VMs and `arm-cmsbuild00x`; core counts not published):
  - `CMSSW_20_1_0_pre3` ([#51806](https://github.com/cms-sw/cmssw/issues/51806)): el9_aarch64_gcc14 **4.66 h**, el8_amd64_gcc14 **4.73 h**, el9_amd64_gcc14 **5.49 h**
  - `CMSSW_20_0_0` ([#51663](https://github.com/cms-sw/cmssw/issues/51663)): el8_amd64_gcc13 **3.8 h**, el9_amd64_gcc13 **4.0 h**, el8_aarch64_gcc13 **3.4 h**
  - `CMSSW_17_0_0_pre5` ([#51759](https://github.com/cms-sw/cmssw/issues/51759)): el8_aarch64 **3.25 h**, el9/el8 amd64 **4.05 h**
  - These builds include LTO and are CMSSW-only; externals (`cmssw-tool-conf`) are prebuilt and cached. A 2015 paper cites a builder cluster of *"284 virtual cores and 540 GB"* and `cmsBuild --builders 4 -j 16` usage ([arXiv:1507.07429](https://ar5iv.arxiv.org/html/1507.07429)).
- **BigProducts** (`BigProducts/*`): cmssw-config has `BIGOBJ` rules (`Makefile.bigedm.rules`, `AddBigObjRule`) that link many plugins into one big shared object. The `no-bigproduct` switch filters out the `BigProducts` subsystem, and cmsdist has a `no-biglib` build option (used by the G4ADEPT IB). Skip these in a conda build, since they duplicate code already in the individual plugins.
- **Other build-infrastructure specifics a CMake/conda port must replicate:**
  - `genreflex` dictionaries (`classes.h`/`classes_def.xml`) producing `.rootmap` and `_rdict.pcm`, and class-version checks.
  - edm plugin registration: `edmPluginRefresh` producing `.edmplugincache`, with plugin libraries named `plugin*.so`.
  - Python config packages installed as `python/<Subsystem>/<Package>`, plus generated cfipython (`cms-sw/cmssw-cfipython`).
  - Alpaka backends built as `…PortableSerialSync`/`CudaAsync`/`ROCmAsync` variant libraries (`Makefile.alpaka`).
  - Data files come from `cms-data/*` repos (`cmsswdata.spec`), which are large; they fit naturally as separate `noarch` outputs or feedstocks.
  - `-z defs` style strict linking on Linux; macOS needs `-undefined error` (cmssw-config used it in 2011).

---

## Link index
- conda-forge fwlite (archived): https://github.com/conda-forge/fwlite-feedstock · issue #58 · PR #57
- Code4hep: https://github.com/code4hep · stitched-alpha2 · c4h-spack-packages · build
- cms-sw/Stitched: https://github.com/cms-sw/Stitched · cms-bot Stitched.filter
- gartung: https://github.com/gartung/cmssw-spack · https://github.com/gartung/fwlite · https://github.com/gartung/fwdata · https://github.com/gartung/buildfile2cmake
- cms-sw/cmssw2cmake: https://github.com/cms-sw/cmssw2cmake
- hep-cce2/cms_miniaod_dict: https://github.com/hep-cce2/cms_miniaod_dict
- CMS Spack evaluation: https://github.com/iarspider/cms-spack-repo
- CMSSW macOS conda issue: https://github.com/cms-sw/cmssw/issues/28894 · case-sensitivity: https://github.com/cms-sw/cmssw/issues/14113
- Clang LTO issue: https://github.com/cms-sw/cmsdist/issues/8335 · PGO+LTO: https://github.com/cms-sw/cmssw/issues/42721
- ACAT 2024 slides: https://indico.cern.ch/event/1330797/contributions/5796567/
- conda-forge runners: https://conda-forge.org/docs/reference/runners/ · self-hosted how-to: https://conda-forge.org/docs/how-to/advanced/self-hosted-runners/ · infrastructure: https://conda-forge.org/docs/maintainer/infrastructure/
- conda-forge GCC on macOS: https://conda-forge.org/blog/2025/11/21/gcc-macos/
- ROOT feedstock: https://github.com/conda-forge/root-feedstock · cms-combine issue: https://github.com/conda-forge/cms-combine-feedstock/issues/39
- rattler-build staging outputs: https://rattler-build.prefix.dev/latest/multiple_output_cache/
