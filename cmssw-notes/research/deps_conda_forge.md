# CMSSW_20_1_0_pre2 externals vs conda-forge

_Generated 2026-09-16 from: `tools.txt` (782 SCRAM tools), the SCRAM toolbox XMLs (`path=` → `/cvmfs/.../external/<pkg>/<ver>`), `pkgs.json` (CMSSW BuildFile `<use>` graph), `cmsdist` (branch `IB/CMSSW_20_1_X/master` @ edd157d, **newer than pre2**: versions marked "IB" come from there), conda-forge `repodata.json` for linux-64 / linux-aarch64 / osx-64 / osx-arm64 / noarch (downloaded 2026-09-16), `conda-forge-pinning` `conda_build_config.yaml` (main), and open conda-forge/staged-recipes PRs._

## Summary

**Scope.** The 782 tools are 402 `py3-*` tools plus 380 others. The 380 collapse to about 200 underlying externals, grouped here into **169 rows**: 74 core, 26 generator, 38 optional, 8 GPU, 17 devtool, 3 toolchain and 3 data.

**Coverage.**
- **121 of 169 rows already have a conda-forge package.** Most can be used as-is (95 rows need no action).
- A few need a variant or patch (hepmc2, dd4hep, geant4, evtgen, thepeg, sherpa), a version bump (pythia8, vecgeom, millepede, cms-md5) or extra platforms (cpu_features, cms-md5, thepeg).
- **48 rows are missing**: 10 core, 13 generator, 14 optional, 3 GPU, 6 devtool and 2 data.
- **py3:** 392 of 402 exist on conda-forge. See the [Python section](#python-py3--tools-402) for the 10 missing ones.

**Missing core dependencies (new recipes needed):**
1. `coral` (CORAL_2_3_21, CMS fork, SCRAM-built): needed by CondCore/CondDB.
2. `frontier_client` 2.10.2: needed by CORAL FrontierAccess, i.e. conditions access.
3. `heppdt` **3.04.01** with the CMS TBB thread-safety patch. conda-forge only has HepPDT 2.06.01, which is a different series.
4. `alpaka` 2.1.1: header-only, used by 43 packages.
5. `hls` (Xilinx arbitrary-precision types, CMS fork): header-only, used by DataFormats/L1T*.
6. `utm` (CMS L1 menu library): the name clashes with the unrelated Python `utm` on conda-forge.
7. `xtd` (patatrack, header-only).
8. `g4hepem`.
9. `classlib`: needed by DQMServices/Core.
10. `ktjet`.
11. `fftjet`.

Also needed for common workflows:
- Generators: `pythia6` (incl. `pydata`, also used by FastSimulation) and `tauolapp`.
- ML: the TensorFlow XLA AOT runtime (`tensorflow-xla-runtime`).
- Data: `cmsswdata` (~115 `data-*` packages).
- L1Trigger: `hls4mlEmulatorExtras`, `conifer` and the L1 ML model libraries.

**Hardest items**
1. **CORAL + frontier_client (+ oracle).** CORAL is built with SCRAM and carries CMS-only patches (thread safety, py3). OracleAccess needs the proprietary instant client (x86_64 only), so it must be dropped.
2. **TensorFlow C++.**
   - CMS uses its own `cms-externals/tensorflow` fork (~23 commits for system grpc/protobuf/eigen, gcc15) and also needs the XLA AOT runtime.
   - conda-forge `libtensorflow_cc` 2.21 is only on linux-64 and osx-arm64 (linux-aarch64 has 2.19.1, osx-64 has 2.18).
   - It is built against protobuf 6.33.5 / abseil 20260107 / grpc 1.78, but **libtorch 2.13 on conda-forge is built against protobuf 7.35.1 / abseil 20260526**, so the two cannot be installed together. Either TF gets rebuilt against current pins, or torch is held at 2.12.0 (which has protobuf 6.33 builds).
3. **The Geant4 / DD4hep / VecGeom simulation stack.**
   - geant4: CMS enables VecGeom solids, C++20, static libs and a voxelisation patch; conda-forge builds C++17 without VecGeom.
   - dd4hep: CMS uses `DD4HEP_USE_GEANT4_UNITS=ON`; conda-forge uses the default unit system.
   - vecgeom: 2.1.1 is needed, conda-forge has 2.0.0.
   - g4hepem is missing.
4. **The HepMC2 ABI.** The CMS fork changes `WeightContainer::size_type` to `unsigned long long`. Any HepMC2 consumer (pythia8, evtgen, photos, tauola, thepeg, sherpa, CMSSW dictionaries) must use the same patched build.
5. **ROOT.**
   - CMS uses the `cms-sw/root` fork (+1 commit), its own builtin LLVM, `vdt=OFF` and `dcache=ON`.
   - conda-forge has 6.36.10 with a C++20 build on all 4 platforms (latest is 6.40.04), using external clangdev.
   - Usable, but CMSSW should either follow conda-forge's ROOT (6.38/6.40) or get a 6.36.13+ build.
6. **Toolchain / macOS.** conda-forge builds with gcc 15 on linux and clang 21 + libc++ on osx. CMS uses gcc 13.4 (IB 14.3), and CMSSW has not supported macOS/libc++ for years. Compiler porting and `-Werror` fallout will dominate the osx work.
7. **Generator chain for Herwig7** (thepeg is linux-only on conda-forge; gosam, gosamcontrib, qgraf, form, openloops and madgraph 2.7 are missing). Also pythia6, hydjet, hydjet2, pyquen and cepgen (Fortran, gcc15 patches). Low priority unless generator workflows are in scope.

**Version / pinning mismatches that matter** (CMSSW pre2 → conda-forge global pin → conda-forge latest):

| dep | CMSSW pre2 (IB) | cf pin | cf latest | impact |
|---|---|---|---|---|
| ROOT | 6.36.13 (6.36.15) | root_base 6.36.10 / 6.38.4 / 6.40.2, cxx 20/23 | 6.40.04 | 6.36.10 cxx20 available everywhere; newer 6.36.x needs a feedstock branch, or CMSSW follows cf |
| tbb | 2022.3 | 2023 | 2023.1.0 | same oneTBB ABI (libtbb.so.12); root_base needs tbb>=2023 → move to 2023 |
| boost | 1.91 (1.92) | 1.88 (HEP stack on cf built vs 1.88/1.90) | 1.92.0 | run_exports pin x.x → must match dd4hep/thepeg/acts builds; CMS header patches |
| fmt | 10.2.1 | 12.1 | 12.2.0 | **CMSSW port to fmt 12 needed** (libtorch requires 12.1) |
| protobuf | 3.21.9 (6.31.1) | 7.35.1 | 7.36.1 | fine for CMSSW; **TF (6.33.5) vs torch (7.35.1) conflict** on cf |
| abseil | 20230802 (20250814) | 20260526 | 20260817 | same TF/torch conflict |
| grpc | 1.35.0 (1.82.0) | 1.82 | 1.83.1 | triton client only |
| tensorflow | 2.17.0 (2.21.0) | 2.16 | 2.21.0 (la64 2.19.1, o64 2.18.0) | see above |
| pytorch | 2.13.0 | 2.12 | 2.13.0 | ok |
| onnxruntime | 1.26.0 | — | 1.30.0 (o64 1.22.2) | 1.26.0 exists on l64/la64/oa64 |
| python | 3.12.13 | 3.11–3.14 | 3.14.7 | ok |
| numpy | 1.26.4 | 2 | 2.5.3 | CMSSW should move to numpy 2 (cf builds allow numpy <3, most ≥1.23) |
| xerces-c | 3.1.3 | 3.3 | 3.3.0 | geant4/dd4hep on cf built vs 3.3 |
| tinyxml2 | 6.2.0 | 11.0 | 11.0.0 | API mostly compatible; verify |
| gsl | 2.6 | 2.7 | 2.8 | minor |
| hdf5 | 1.14.6 | 1.14.6 | 2.2.0 | matches pin |
| highfive | 2.10.1 | — | 3.3.0 | 3.x API break; 2.10.1 available |
| xgboost | 1.7.5 | — | 3.4.2 | CMSSW uses C API; 1.7.6 builds exist |
| lhapdf | 6.4.0 | 6.5 | 6.5.6 | minor |
| pythia8 | 8.317 | 8.312 | 8.312 | needs bump |
| vecgeom | 2.1.1 | — | 2.0.0 | needs bump |
| clhep / geant4 / hepmc3 | 2.4.7.2 / 11.4.2 / 3.3.1 | 2.4.7.2 / 11.4.2 / 3.3 | same | match |
| compilers | gcc 13.4 (IB 14.3), C++20 | gcc 15 (linux), clang 21 (osx); CUDA builds gcc 14/15 | — | CMSSW must build cleanly with gcc 15 and clang/libc++ |
| CUDA | 13.3.1 | 12.9 / 13.4 (linux only) | 13.4 | GPU is linux-only on cf; ROCm mostly absent |
| glibc | EL9 (2.34) | sysroot 2.17 (2.28 for CUDA) | — | may need `c_stdlib_version` 2.28 for some deps |

**CMS patches that are significant for compatibility** (details in the tables):
- **Change ABI or behaviour:**
  - hepmc2 (`size_type`).
  - heppdt (TBB concurrent map).
  - dd4hep (Geant4 units).
  - geant4 (VecGeom, voxelisation patch, C++20).
  - evtgen (HepMC2 build + boost fix).
  - coral (FrontierAccess thread-safety lock).
  - md5 (IB renames symbols to `edm_md5`).
- **Build or warning fixes, likely upstreamable or harmless:**
  - boost (~40 headers).
  - root (1 TBasket commit).
  - vdt, lwtnn, eigen, fastjet, onnxruntime.
  - thepeg / herwig7 / sherpa / rivet generator patches.
  - hls, classlib, clhep.
  - tensorflow (system-lib integration).
  - pytorch (system fmt).
- **Already upstreamed:** conda-forge `fastjet-contrib` already carries both CMS patches.

**Already in progress on staged-recipes:**
- `herwig` (#33684, open, updated 2026-08-31).
- `professor2` (#34853, open, 2026-09-16).
- `roctracer` for ROCm (#25913).
- No open PRs for coral, frontier_client, alpaka, heppdt 3, pythia6, tauolapp or the other missing packages.

**Legend.**
- Platforms: `l64` linux-64, `la64` linux-aarch64, `o64` osx-64, `oa64` osx-arm64. `all 4` means the same latest version on every platform. A version in parentheses is the latest on that platform when it lags.
- "# CMSSW pkgs using": number of CMSSW packages whose BuildFiles `<use>` any of the tools for that external. It counts direct uses only; transitive deps such as vecgeom and geant4data show 0.
- Categories: **core** = needed to build and run standard reco/sim/DQM/conditions. **generator** = GeneratorInterface. **optional** = niche subsystem (L1 emulator models, online DB, alignment, Fireworks, not-yet-used ACTS). **gpu**, **devtool**, **toolchain** and **data** are self-explanatory.

## C++ / Fortran / system externals

### Core HEP / CMS-specific C++ libraries

| package | CMSSW version | conda-forge name | cf latest | platforms (l64 la64 o64 oa64) | # CMSSW pkgs using | CMS patches / build notes | category | action needed |
|---|---|---|---|---|---|---|---|---|
| root (46 tools: root*, roofit*, roostats, histfactory, rootcling, …) | 6.36.13 (IB 6.36.15) | `root_base`, `root` | 6.40.04 | all 4 | 695 | Built from `cms-sw/root` branch `cms/v6-36-00-patches/122aa7ce3fa` = upstream patches branch + 1 CMS commit (TBasket: distinct return codes per failure). Build: **builtin (CMS-forked) LLVM/cling**, `vdt=OFF`, `dcache=ON` (linux), davix/xrootd/tmva/roofit/mathmore/fftw3/imt/root7/pyroot ON, C++20. cf: external clangdev, `vdt=ON`, `dcache=OFF`, `root_cxx_standard` 20/23 variants. cf still ships 6.36.10 cxx20 on all 4 platforms. | core | version bump (6.36.1x cxx20 build) or move CMSSW to 6.38/6.40; upstream TBasket patch; dcache optional |
| boost (12 tools incl. boost_python, boost_mpi) | 1.91.0 (IB 1.92.0) | `libboost-devel`, `libboost-python-devel`, `libboost-mpi` | 1.92.0 | all 4 | 347 | `patches/boost-cms-fixes`: ~40 header tweaks (deprecation/warning silencing for -Werror, interprocess, serialization, math). cf global pin `libboost_devel 1.88` (HEP stack on cf currently built vs 1.88/1.90). 1.91.0 builds exist. | core | none (follow cf pin; check whether CMS header fixes are needed with CMSSW -Werror flags) |
| clhep | 2.4.7.2 | `clhep` | 2.4.7.2 | all 4 | 291 | `cms-externals/clhep` fork: only builds monolithic `libCLHEP` + `<cstdlib>` fix. cf builds split libs + libCLHEP; pinned 2.4.7.2. | core | none |
| hepmc (HepMC2) | 2.06.10 | `hepmc2` | 2.06.11 | all 4 | 83 | `cms-externals/hepmc` fork: **`WeightContainer::size_type` changed to `unsigned long long`** (ABI + ROOT dictionary/persistency relevant), SimpleVector reflex fix, PythiaWrapper pyint, modulemap, `std::iterator` removal. cf `hepmc2` is stock 2.06.11. | core | patch (CMS-flavoured hepmc2 variant/output; must be used consistently by pythia8/evtgen/photos/tauola/thepeg/sherpa) |
| hepmc3 | 3.3.1 | `hepmc3` | 3.3.1 | all 4 | 10 | none | core | none |
| heppdt | 3.04.01 | `heppdt` | 2.06.01 | all 4 | 31 | `cms-externals/heppdt` fork: ParticleTable uses `tbb::concurrent_unordered_map` (thread safety), silenced banners, `std::hash`. **cf only has HepPDT 2.06.01 (different series)**. | core | new recipe (HepPDT 3.x with CMS patches; name clash with existing `heppdt` 2.x) |
| tbb (+tbbbind) | v2022.3.0 | `tbb-devel`, `tbb` | 2023.1.0 | l64 la64 o64(2023.0.0) oa64 | 45 | none; cf pin `tbb 2023` (root_base requires tbb>=2023). | core | none (use 2023) |
| xerces-c | 3.1.3 | `xerces-c` | 3.3.0 | all 4 | 37 | none; cf pin 3.3 (geant4/dd4hep built vs 3.3). | core | none (CMSSW must accept 3.3) |
| eigen | git c1d6374 (IB 5.0.1) | `eigen` | 5.0.1 | all 4 | 28 | `eigen-const-scalar-operand` patch; CMS IB already on 5.0.1. cf has 3.4.0 and 5.0.1. | core | none (verify patch still needed) |
| fmt | 10.2.1 | `fmt` | 12.2.0 | all 4 | 17 | none. cf pin `fmt 12.1`; libtorch 2.13 on cf requires fmt 12.1. 10.2.1 builds exist. | core | CMSSW port to fmt 12 (or fmt 10 islands – not viable with libtorch) |
| vdt (+vdt_headers) | 0.4.3 | `vdt` | 0.4.4 | all 4 | 22 | `vdt-integer-overflow` patch | core | none (check patch vs 0.4.4) |
| fastjet | 3.4.1 | `fastjet-cxx` | 3.5.1 | all 4 | 23 | fork = stock tarball; `fastjet-deprecated-warn` patch. (`fastjet` on cf is the scikit-hep Python package.) | core | none (3.5 bump) |
| fastjet-contrib | 1.101 | `fastjet-contrib` | 1.104 | all 4 | 6 | `cms-externals` fork: CMS additions to JetCleanser/RecursiveTools + no `--as-needed`. **cf feedstock already carries both CMS patches.** | core | none |
| dd4hep (dd4hep, -core, -geant4) | v01-37x (master ed75e7e) | `dd4hep` | 1.37 | l64 la64 o64(1.34) oa64 | 30 | CMS builds with **`DD4HEP_USE_GEANT4_UNITS=ON`** (cf uses the default TGeo cm-based unit system; CMSSW DD4hep geometry code assumes Geant4 mm units), xerces-c on, C++20, post-1.37 master commit. | core | patch/variant in cf recipe (Geant4 units); osx-64 rebuild |
| geant4 (geant4core, geant4vis, geant4static, …) | 11.4.2 | `geant4` | 11.4.2 | all 4 | 42 | `cms-externals/geant4` = 11.4.2 + 1 commit (disable parallel voxelisation). CMS build: **VecGeom solids (`GEANT4_USE_USOLIDS=all`)**, C++20, shared **and static** libs (`geant4static` for BigProducts), MT, TLS global-dynamic. cf: C++17, no VecGeom, shared only, +HDF5/Qt. | core | variant/patch (VecGeom + C++20 + voxelisation patch); static libs only for BigProducts (skip) |
| geant4data (G4EMLOW, G4NDL, …) | 11.0 | `geant4-data-emlow` | 8.8.0 | noarch | 0 | stock data sets | data | none (cf `geant4-data-*` noarch outputs) |
| vecgeom | 2.1.1 | `vecgeom` | 2.0.0 | all 4 | 0 | `vecgeom-fix-vector` patch; scalar backend, LTO flags | core | version bump (2.0.0 → 2.1.1) |
| g4hepem | 20251114 | **missing** | — | — | 2 | static-only build (G4HepEm), used by SimG4Core/PhysicsLists | core | new recipe |
| alpaka (+ -serial/-tbb/-cuda/-rocm) | 2.1.1 | **missing** | — | — | 43 | header-only, stock | core | new recipe (easy, header-only) |
| xtd (cms-patatrack) | git fdcc020 | **missing** | — | — | 2 | header-only portable math lib | core | new recipe (easy) |
| hls (Xilinx HLS_arbitrary_Precision_Types) | 2025.05 | **missing** | — | — | 16 | `cms-externals` fork: memory-init + `<cmath>`/`<cstdlib>` fixes; header-only; used by DataFormats/L1T* | core | new recipe (easy) |
| utm (CMS L1 trigger menu lib) | utm_0.14.1 | **missing** | — | — | 3 | gitlab.cern.ch/cms-l1t-utm; `utm-boost190` patch. **cf `utm` is an unrelated Python package.** Used by CondFormats/L1TObjects. | core | new recipe (different name, e.g. `cms-l1t-utm`) |
| md5 | 1.0.0 (IB 2.0.0) | `cms-md5` | 1.0.0 | l64 o64 (no la64,oa64) | 3 | `cms-externals/md5`; IB renames to `edm_md5` to avoid symbol collisions. cf `cms-md5` 1.0.0 exists (old, 2021). | core | version bump + add aarch64/osx-arm64 |
| cpu_features | 0.9.0 | `cpu_features` | 0.9.0 | l64 la64 o64(0.4.1) (no oa64) | 1 | stock | core | add osx builds (osx-64 stuck at 0.4.1, no osx-arm64) |
| coral (CoralBase, RelationalAccess, …) | CORAL_2_3_21 | **missing** | — | — | 19 | `cms-externals/coral` py3 branch (FrontierAccess thread-safety global lock, auto_ptr→unique_ptr, boost fs fixes, py312 patch, macOS/gcc8 patches); **built with SCRAM**; OracleAccess dropped on non-x86_64. Used by CondCore/CondDB (conditions). | core | new recipe (hard: needs CMake build from upstream lcgcoral + CMS patches; frontier_client dep) |
| frontier_client | 2.10.2 | **missing** | — | — | 0 | `frontier_client_py312` patch; plain Makefile build; needs expat, pacparser, zlib | core | new recipe (moderate; macOS untested upstream) |
| pacparser | 1.5.0 | `pacparser` | 1.5.2 | all 4 | 0 | `pacparser-pymod-install` patch | core | none |
| classlib | 3.1.3 | **missing** | — | — | 1 | `cms-externals` fork (glibc sysctl removal, gcc11, CLK_TCK, unwind fixes); built without zlib/bz2/lzma/lzo; used by DQMServices/Core | core | new recipe (moderate; macOS support doubtful) |
| ktjet | 1.06 | **missing** | — | — | 2 | stock (ancient, CLHEP based); RecoJets/JetAlgorithms | core | new recipe (easy) |
| fftjet | 1.5.0 | **missing** | — | — | 1 | stock autotools; needs fftw | core | new recipe (easy) |
| lwtnn | 2.14.1 | `lwtnn` | 2.14.2 | all 4 | 2 | `lwtnn-assert-fix` patch | core | none |
| correctionlib (C++ part) | 2.9.0 | `correctionlib` | 2.9.0 | all 4 | 1 | none | core | none |
| xgboost (C API) | 1.7.5 | `libxgboost` | 3.4.2 | all 4 | 3 | stock. cf latest 3.4.2; 1.7.6 builds exist. CMSSW uses the C API (PhysicsTools/XGBoost). | core | none if 1.7.6 acceptable; else port CMSSW to 3.x API |
| onnxruntime | 1.26.0 | `onnxruntime-cpp` | 1.30.0 | l64 la64 o64(1.22.2) oa64 | 3 | `onnxruntime/cms-changes` (MLAS platform.cpp, scatter.cc), 2 backports, ciso646; full protobuf; CUDA provider when available | core | none/verify patches (osx-64 stuck at 1.22.2) |
| tensorflow C++ (tensorflow-cc, -framework, -includes) | 2.17.0 (IB 2.21.0) | `libtensorflow_cc` | 2.21.0 | l64 la64(2.19.1) o64(2.18.0) oa64 | 2 | `cms-externals/tensorflow` fork (~23 commits on 2.21: build against system grpc/protobuf/eigen/pybind11, gcc15, EIGEN_USE_THREADS) + tf2xla return-type patch; bazel build w/ clang for XLA codegen. **cf 2.21 builds pin protobuf 6.33.5 / abseil 20260107 / grpc 1.78 — incompatible with cf libtorch 2.13 (protobuf 7.35.1 / abseil 20260526)**; libtorch 2.12.0 has a matching protobuf-6.33 build. | core | version bump/rebuild of TF vs current pins (or pin torch 2.12); linux-aarch64 (2.19.1) and osx-64 (2.18) lagging |
| tensorflow-xla-runtime + tfaot-model-test-* | 2.17.0 | **missing** | — | — | 1 | XLA AOT runtime library + AOT-compiled test models (PhysicsTools/TensorFlowAOT) | optional | new recipe (likely not shipped by cf libtensorflow_cc; verify) |
| pytorch C++ (pytorch, pytorch-interface) | 2.13.0 | `libtorch` | 2.13.0 | all 4 | 4 | `pytorch-system-fmt`, `pytorch-hipblaslt-include` patches; built vs system fmt/eigen/protobuf/OpenBLAS | core | none (but see TF/protobuf pin conflict) |
| triton-inference-client (C++ gRPC client) | 2.25.0 | `tritonclient` | 2.71.0 | noarch | 1 | r22.08 client+common; needs grpc/protobuf/rapidjson. cf only has the noarch Python `tritonclient`. | optional | new recipe (C++ client lib) |
| cmsswdata (+~115 `data-*` packages) | 43.0 | **missing** | — | — | 1 | tarballs from github.com/cms-data/*; several GB total | data | new recipe(s) (noarch data; maybe split/fetch-on-demand) |
| hls4mlEmulatorExtras | 1.1.7 | **missing** | — | — | 4 | stock | optional | new recipe (L1Trigger) |
| conifer | 1.7 | **missing** | — | — | 3 | stock (C++ BDT emulator headers) | optional | new recipe (L1Trigger) |
| L1 ML models: AXOL1TL, CICADA, TOPO, TOoLLiP, L1METML, NNPuppiTauModel, L1TSC4NGJetModel, L1TSC82ProngJetModel, EMTF_NN | various | **missing** | — | — | 3 | CMS hls4ml-emulator model libraries (cms-hls4ml GitHub) | optional | new recipes (L1Trigger only; could bundle) |
| CSCTrackFinderEmulation | 1.2 | **missing** | — | — | 1 | `cms-externals` repo | optional | new recipe (L1Trigger/CSCTrackFinder) |
| clue | 1.1.1 (IB 1.1.3) | **missing** | — | — | 1 | header-only (gitlab.cern.ch/kalos/clue); RecoLocalCalo/HGCalRecProducers | optional | new recipe (easy) |
| CLUEstering | 2.11.0 | **missing** | — | — | 0 | header-only; no direct BuildFile users | optional | new recipe (easy) / skip |
| hector | 1.3.4_patch1 | **missing** | — | — | 5 | `cms-externals/hector` fork (graphics libs removed, CMSSW mods); PPS/forward proton transport | optional | new recipe |
| mille | V01-00-00 | **missing** | — | — | 2 | stock (DESY Mille) | optional | new recipe (Alignment) |
| millepede (Millepede-II) | V05-00-00 | `millepede` | 04.16.03 | all 4 | 1 | stock | optional | version bump (cf 04.16.03) |
| gbl (General Broken Lines) | V04-00-00 | **missing** | — | — | 1 | stock (DESY gitlab), eigen+mille | optional | new recipe (Alignment) |
| acts (acts-*, actsvg, traccc*, detray, covfie, vecmem) | v44.0.1 (IB 46.8.1) | `acts-core` | 45.5.1 | all 4 | 0 | One CMS build of ACTS with bundled traccc/detray/covfie/vecmem/actsvg + DD4hep/Geant4/ROOT/FastJet/JSON plugins, CUDA/ROCm backends. cf `acts-core` has core only. **No CMSSW BuildFile uses it yet.** | optional | skip for now (later: extend acts recipe + new traccc/detray/covfie/vecmem) |
| actsdata | v10 | **missing** | — | — | 0 | data | data | skip for now |
| celeritas + g4vg | 0.7.0-devX / 1.0.6 | **missing** | — | — | 1 | celeritas `develop` snapshot, static; g4vg release | optional | new recipes (skip initially) |
| dip (CERN DIP) | git 8693f00 | **missing** | — | — | 1 | gitlab.cern.ch (authenticated URL); DQM/BeamMonitor online only | optional | skip |
| log4cplus | 2.0.7 | `log4cplus` | 2.0.7 | l64 o64 (no la64,oa64) | 1 | stock; only needed by dip | optional | skip (or add aarch64/arm64) |
| oracle (instant client, oracleocci) | 19.11.0.0.0dbru | `oracle-instant-client` | 23.7.0.25.01 | l64 o64(19.8.0.0.0) (no la64,oa64) | 2 | proprietary binaries; x86_64 only (aarch64 19.10) | optional | skip (online DB only); cf pkg linux-64/osx-64 only |
| tkonlinesw (+tkonlineswdb) | 4.2.0-1_gcc7 | **missing** | — | — | 3 | 4 patches; needs oracle; tracker online DB | optional | skip |
| sigcpp | 3.2.0 | `sigcpp-3.0` | 3.6.0 | all 4 | 1 | stock; Fireworks only | optional | none |
| xrdcl-record | 5.4.2 | **missing** | — | — | 0 | XRootD client record plugin | optional | new recipe (easy) |
| mpi (CMS wrapper) / openmpi | 1.0 / 5.0.10 | `openmpi` | 5.0.10 | all 4 | 3 | `openmpi-opt`: built with UCX/libfabric/xpmem/gdrcopy (HPC) | optional | none (HeterogeneousCore/MPI*) |

### General system / third-party libraries

| package | CMSSW version | conda-forge name | cf latest | platforms (l64 la64 o64 oa64) | # CMSSW pkgs using | CMS patches / build notes | category | action needed |
|---|---|---|---|---|---|---|---|---|
| python3 | 3.12.13 | `python` | 3.14.7 | all 4 | 5 | stock | core | none (cf builds 3.11–3.14) |
| numpy-c-api (py3-numpy) | 1.26.4 | `numpy` | 2.5.3 | all 4 | 0 | CMSSW pins numpy 1.x; cf pin `numpy 2` (built packages allow numpy <3, many ≥1.23) | core | CMSSW move to numpy 2 (recommended) |
| protobuf | 3.21.9 (IB 6.31.1) | `libprotobuf` | 7.36.1 | all 4 | 3 | stock; cf pin 7.35.1 | core | none (CMSSW regenerates .pb; see TF conflict) |
| abseil-cpp | 20230802.2 (IB 20250814.1) | `libabseil` | 20260817.0 | all 4 | 0 | stock; cf pin 20260526 | core | none |
| grpc | 1.35.0 (IB 1.82.0) | `libgrpc` | 1.83.1 | all 4 | 0 | IB adds grpc PR 28212 patch; cf pin 1.82 | optional | none |
| flatbuffers | 24.3.25 | `flatbuffers` | 25.12.19 | all 4 | 0 | stock; cf pin 25.9.23 | core | none |
| re2 | 2021-06-01 | `re2` | 2025.11.05 | all 4 | 0 | stock | core | none |
| c-ares | 1.15.0 | `c-ares` | 1.34.8 | all 4 | 0 | stock | core | none |
| xrootd | 6.0.2 | `xrootd`, `libxrootd` | 6.1.1 | all 4 | 2 | stock (with isal, davix, libxml2) | core | none |
| davix | 0.8.9 | `davix` | 0.8.10 | all 4 | 1 | stock | core | none |
| dcap | 2.47.14 | `dcap` | 2.47.14 | all 4 | 1 | stock (linux only in CMS) | optional | none |
| isal | 2.30.0 | `isa-l` | 2.32.1 | l64 la64 o64 oa64(2.31.1) | 0 | stock | core | none |
| curl | 8.13.0 | `libcurl` | 8.22.0 | all 4 | 3 | stock | core | none |
| openssl | system | `openssl` | 4.0.2 | all 4 | 3 | system lib on EL9 | core | none |
| zlib | 1.3.2 | `libzlib` | 1.3.2 | all 4 | 10 | stock | core | none |
| bz2lib | 1.0.8 | `bzip2` | 1.0.8 | all 4 | 1 | stock | core | none |
| xz | 5.8.3 | `xz` | 5.8.3 | all 4 | 3 | stock | core | none |
| zstd | 1.5.7 | `zstd` | 1.5.7 | all 4 | 2 | stock | core | none |
| lz4 | 1.9.2 | `lz4-c` | 1.10.0 | all 4 | 0 | stock | core | none |
| c-blosc2 | 3.2.1 | `c-blosc2` | 3.3.4 | all 4 | 0 | stock | optional | none |
| expat | 2.7.1 | `expat` | 2.8.1 | all 4 | 6 | stock | core | none |
| libxml2 | 2.9.10 | `libxml2` | 2.15.4 | all 4 | 0 | stock; cf pin 2.15 | core | none |
| libxslt | 1.1.42 | `libxslt` | 1.1.45 | all 4 | 0 | stock | optional | none |
| json (nlohmann) | 3.12.0 | `nlohmann_json` | 3.12.0 | all 4 | 10 | stock | core | none |
| tinyxml2 | 6.2.0 | `tinyxml2` | 11.0.0 | all 4 | 7 | stock; cf pin 11.0 (6.2.0 linux-64/osx-64 only) | core | none (CMSSW must accept tinyxml2 11) |
| yaml-cpp | 0.8.0 | `yaml-cpp` | 0.8.0 | all 4 | 0 | stock | core | none |
| gsl | 2.6 | `gsl` | 2.8 | all 4 | 10 | stock; cf pin 2.7 | core | none |
| fftw3 | 3.3.8 | `fftw` | 3.3.11 | all 4 | 1 | stock | core | none |
| OpenBLAS | 0.3.27 | `libopenblas`, `openblas` | 0.3.34 | all 4 | 0 | stock (+x86-64-v2 microarch build) | core | none |
| hdf5 | 1.14.6 | `hdf5` | 2.2.0 | all 4 | 3 | stock; matches cf pin 1.14.6 | core | none |
| highfive | 2.10.1 | `highfive` | 3.3.0 | all 4 | 1 | stock; cf latest 3.3.0 (API break), 2.10.1 builds exist | generator | none (pin 2.10) / port to 3.x |
| sqlite | 3.48.0 | `libsqlite`, `sqlite` | 3.53.4 | all 4 | 0 | stock | core | none |
| libuuid | 2.40 | `libuuid` | 2.42.3 | all 4 | 1 | stock | core | none |
| pcre2 | 10.36 | `pcre2` | 10.47 | all 4 | 0 | stock; cf pin 10.47 | core | none |
| pcre (v1) | 8.43 | `pcre` | 8.45 | all 4 | 0 | stock; needed by classlib/igprof/grpc | optional | none (cf 8.45, unmaintained upstream) |
| libffi | 3.4.6 | `libffi` | 3.7.0 | all 4 | 0 | stock | core | none |
| db6 | 6.2.32 | `libdb` | 6.2.32 | all 4 | 0 | stock (python dbm) | optional | none |
| gdbm | 1.24 | `gdbm` | 1.18 | all 4 | 0 | stock (python dbm) | optional | none (cf 1.18 old but OK) |
| libpng | 1.6.44 | `libpng` | 1.6.58 | all 4 | 0 | stock | core | none |
| libjpeg-turbo | 3.0.4 | `libjpeg-turbo` | 3.2.0 | all 4 | 0 | stock | core | none |
| libtiff | 4.6.0 | `libtiff` | 4.7.2 | all 4 | 0 | stock | core | none |
| giflib / libungif | 5.2.1 / 4.1.4 | `giflib` | 6.1.3 | all 4 | 0 | stock | core | none |
| freetype | 2.14.3 | `freetype` | 2.14.3 | all 4 | 0 | stock | core | none |
| x11 / opengl | system | `xorg-libx11`, `libgl` | 1.8.13 | all 4 | 2 | system libs (Fireworks, ROOT graphics) | optional | none (cf xorg-*/libglvnd) |
| hwloc | 2.12.2 | `libhwloc` | 2.13.0 | all 4 | 0 | stock | core | none |
| jemalloc (+jemalloc-debug, -prof) | 5.3.1 | `jemalloc` | 5.3.1 | all 4 | 5 | `cms-externals/jemalloc` (gcc16 bad_alloc fix); CMS: `--enable-stats`, prof/debug variants, aarch64 lg-page=16. cf: `--disable-tls --disable-initial-exec-tls` on linux, no prof variant. | core | none for base; new output/variant for -prof/-debug (optional) |
| gperftools (tcmalloc, profiler) | 2.11 | `gperftools` | 2.18.90 | all 4 | 2 | stock | optional | none |
| libzmq | 4.3.5 | `zeromq` | 4.3.5 | all 4 | 0 | stock (pyzmq) | optional | none |
| openldap | 2.5.19 | `openldap` | 2.6.13 | all 4 | 0 | stock (python-ldap) | optional | none |
| opencv | 4.9.0 | `libopencv` | 5.0.0 | all 4 | 0 | stock; no direct CMSSW users | optional | none |
| xtensor / xtl | 0.24.1 / 0.7.4 | `xtensor`, `xtl` | 0.27.1 | all 4 | 0 | stock; no direct CMSSW users | optional | none |
| libunwind | 1.8.1 | `libunwind` | 1.8.3 | l64 la64 (no o64,oa64) | 0 | IB adds libunwind PR 831 patch; linux only | devtool | none |
| numactl / libpciaccess | 2.0.19 / 0.16 | `numactl` | 2.0.18 | l64 la64 (no o64,oa64) | 0 | stock; linux only | optional | none |
| ucx / libfabric / xpmem / rdma-core | 1.21.0 / 2.1.0 / 2.6.3 / 57.0 | `ucx` | 1.22.0 | l64 la64 (no o64,oa64) | 0 | HPC transport stack for openmpi; linux only (libfabric also osx on cf) | optional | none |
| catch2 | 3.13.0 | `catch2` | 3.16.0 | all 4 | 89 | stock (tests) | core | none |
| cppunit | 1.15.x (git) | `cppunit` | 1.15.1 | all 4 | 55 | freedesktop git snapshot (tests) | core | none |
| google-test | 1.17.0 | `gtest` | 1.18.0 | all 4 | 0 | stock (tests) | optional | none |
| google-benchmark | 1.9.4 | `benchmark` | 1.9.5 | all 4 | 1 | stock | optional | none |

### Generators and generator tools

| package | CMSSW version | conda-forge name | cf latest | platforms (l64 la64 o64 oa64) | # CMSSW pkgs using | CMS patches / build notes | category | action needed |
|---|---|---|---|---|---|---|---|---|
| pythia8 | 317 (8.317) | `pythia8` | 8.312 | all 4 | 7 | no patches; `--with-hepmc2 --with-hepmc3 --with-lhapdf6 --with-mg5mes` | generator | version bump (cf pin 8.312) |
| pythia6 (+pydata, pythia6_headers, pdfdummy) | 426 | **missing** | — | — | 9 | Fortran, static only, `--with-hepevt=4000`, `pythia6-gcc14` patch; `pydata` also used by FastSimulation | generator | new recipe |
| evtgen | 2.0.0 | `evtgen` | 2.2.3 | all 4 | 2 | `cms-externals/evtgen` fork (boost fix in CLEO model); CMS builds **HepMC2** (`EVTGEN_HEPMC3=OFF`) + Pythia8/Photos/Tauola. cf builds HepMC3 (2.0.0 builds only linux-64/osx-64). | generator | patch/variant (HepMC2 + CMS fix) |
| tauolapp (TAUOLA++) | 1.1.8 | **missing** | — | — | 3 | stock LHC tarball, `--with-hepmc` (HepMC2), pythia8, lhapdf | generator | new recipe |
| photospp (PHOTOS++) | 3.64 | `photos` | 3.64 | all 4 | 2 | stock, HepMC2+HepMC3 (cf same) | generator | none |
| lhapdf | 6.4.0 | `lhapdf` | 6.5.6 | all 4 | 4 | stock + bundled MSTW2008nlo68cl set and pdfsets index; python enabled | generator | none (cf pin 6.5; PDF sets handled separately) |
| herwig7 | 7.2.2 | **missing** | — | — | 1 | 4 patches (Matchbox MG py3, FxFx fix, LHEEventNumFxFx, MB); deps thepeg, gosam, madgraph, openloops | generator | new recipe — **open staged-recipes PR #33684 “Add herwig”** (herwig 7.3?) |
| thepeg | 2.2.2 | `thepeg` | 2.2.3 | l64 la64 (no o64,oa64) | 1 | 4 patches (LHEEventNum, deprecated-warn, Particle-parents, C++23) | generator | patch + add osx builds (cf linux only, 2.2.3) |
| sherpa | 2.2.16 | `sherpa` | 3.0.0 | all 4 | 1 | 3 patches (hepmcshort, setenv, disable-manual); deps blackhat, openloops, openmpi, mcfm (build) | generator | patch (cf latest 3.0.0; 2.2.16 builds exist) |
| rivet | 4.1.2 | `rivet` | 4.1.4 | all 4 | 1 | 2 patches (duplicate-libs, postrelease); CMS links onnxruntime+highfive | generator | none |
| yoda | 2.1.2 | `yoda` | 2.1.4 | all 4 | 1 | stock; built with ROOT | generator | none |
| hydjet | 1.9.3 | **missing** | — | — | 1 | `hydjet-gcc15` patch; needs pyquen, pythia6, lhapdf | generator | new recipe |
| hydjet2 | 2.4.4 | **missing** | — | — | 1 | `hydjet2-gcc15` patch; + root | generator | new recipe |
| pyquen | 1.5.4 | **missing** | — | — | 2 | `pyquen-gcc15` patch; Fortran + pythia6 | generator | new recipe |
| cepgen | 1.2.5 | **missing** | — | — | 1 | `cepgen-gcc15` patch; many deps (root, pythia6, hepmc2/3, lhapdf, gsl) | generator | new recipe |
| starlight | r193 | **missing** | — | — | 0 | `cms-externals` fork + CMAKE_CXX_FLAGS patch; no direct BuildFile users | generator | new recipe (low priority) |
| alpgen | 214 | **missing** | — | — | 0 | Fortran; no direct BuildFile users | generator | skip / new recipe |
| madgraph5amcatnlo | 2.7.3 | `mg5amcnlo` | 3.5.7 | all 4 | 0 | py3 tarball; used only by herwig7 Matchbox | generator | version mismatch (cf 3.5.7) – skip or new version |
| openloops | 2.1.2 | **missing** | — | — | 0 | scons build + process libraries download | generator | new recipe (low priority) |
| gosam / gosamcontrib (+qgraf, form) | 2.1.0 / 2.0-20180708 | **missing** | — | — | 0 | herwig7 Matchbox deps; qgraf & form also missing on cf | generator | new recipes (low priority) |
| blackhat | 0.9.9 | **missing** | — | — | 0 | `cms-externals` fork (gcc4.8/6/10 fixes, armv7); sherpa dep | generator | new recipe (low priority) |
| collier | 1.2.8 | `collier` | 1.2.10 | all 4 | 0 | stock (cmsrep mirror) | generator | none |
| qd | 2.3.13 | `qd` | 2.3.22 | all 4 | 0 | stock | generator | none |
| professor2 | 2.4.2 | `professor` | 2.5.9 | l64 o64(2.4.0) (no la64,oa64) | 0 | stock (root, yoda, iminuit) | generator | none — **open staged-recipes PR #34853 “Add Professor 2”**; cf `professor` 2.5.9 linux-64 / 2.4.0 osx-64 |
| mctester | 1.25.1 | **missing** | — | — | 0 | stock; no direct BuildFile users | generator | skip / new recipe |

### GPU stacks (linux only on conda-forge)

| package | CMSSW version | conda-forge name | cf latest | platforms (l64 la64 o64 oa64) | # CMSSW pkgs using | CMS patches / build notes | category | action needed |
|---|---|---|---|---|---|---|---|---|
| cuda (cuda, cublas, cufft, curand, cusolver, cusparse, npp, nvjpeg, nvrtc, nvml, cupti, nvperf, stubs, nvidia-drivers) | 13.3.1 | `cuda-nvcc` | 13.4.59 | l64 la64 (no o64,oa64) | 22 | repackaged NVIDIA runfile | gpu | none on linux (cf CUDA 13.4 pin); n/a on osx |
| cudnn | 9.23.0.39 | `cudnn` | 9.26.0.51 | l64 la64 (no o64,oa64) | 0 | binary | gpu | none on linux |
| cuda-compatible-runtime | 2.0 | **missing** | — | — | 0 | cms-patatrack test binary | gpu | new recipe (tiny) / skip |
| gdrcopy | 2.6 | **missing** | — | — | 0 | GPUDirect RDMA | gpu | skip |
| rocm (rocm, rocm-core, rocm-llvm, comgr, rocr-runtime, rocm-smi-lib, rocprofiler*, roctracer, rocgdb) | 7.14 | `rocm-core` | 7.2.4 | l64 la64 (no o64,oa64) | 11 | CMS builds ROCm from source (`rocm/*.spec`) | gpu | skip initially (cf has only parts of ROCm 7.2.4, linux-64) |
| hip*/roc* math libs (hipblas, hipblaslt, hipfft, hiprand, hipsolver, hipsparse(lt), rocblas, rocfft, rocrand, rocsolver, rocsparse, rocthrust, rocprim, miopen, rccl) | 7.14 | `hipfft` | 1.0.13 | l64 (no la64,o64,oa64) | 0 | source builds | gpu | skip (mostly missing on cf; roctracer staged-recipes PR #25913) |
| aotriton | 0.13b | **missing** | — | — | 0 | ROCm pytorch attention kernels | gpu | skip |
| pytorch-cuda / pytorch-rocm, torch-scatter/sparse/cluster(-cuda), pyg-lib(-cuda) | 2.13.0 / 2.1.2 / 0.6.18 / 1.6.3 / 0.7.0 | `pytorch_scatter` | 2.1.2 | all 4 | 4 | pip builds vs CMS torch | gpu | none (cf CUDA builds on linux; pyg-lib 0.6.0 → bump) |

### Toolchain and developer tools

| package | CMSSW version | conda-forge name | cf latest | platforms (l64 la64 o64 oa64) | # CMSSW pkgs using | CMS patches / build notes | category | action needed |
|---|---|---|---|---|---|---|---|---|
| gcc (gcc-ccompiler/cxx/f77, gcc-atomic, gcc-plugin, flags tools) | 13.4.0 (IB 14.3.1) | `gxx` | 16.2.0 | all 4 | 34 | CMS-built GCC; f77compiler used by 13 GeneratorInterface pkgs; gcc-plugin for static analysis | toolchain | none (cf gcc 15 on linux / clang 21 on osx — **macOS/libc++ is a new port for CMSSW**) |
| llvm (llvm-*compiler, pyclang, iwyu-cxxcompiler) | 21.1.4 | `clangdev`, `libclang`, `python-clang` | 23.1.1 | all 4 | 3 | `cms-externals/llvm-project` fork (`cms/llvmorg-21.1.4`); `pyclang` is **needed at build time by CondFormats/Serialization** code generator | toolchain | none (use clangdev/libclang/python-clang 21.1.8) |
| gmake | 4.3 | `make` | 4.4.1 | all 4 | 0 |  | devtool | none |
| gdb | 16.2 | `gdb` | 17.2 | all 4 | 1 |  | devtool | none |
| valgrind | 3.24.0 | `valgrind` | 3.27.1 | l64 la64 o64(3.14.0) (no oa64) | 2 |  | devtool | none (linux only in practice) |
| heaptrack | 1.4.0 | `heaptrack` | 1.5.0 | l64 la64 (no o64,oa64) | 0 |  | devtool | none (linux only) |
| igprof | 5.9.16 | **missing** | — | — | 0 | linux-only profiler | devtool | skip |
| perfetto | 56.1 | **missing** | — | — | 0 | tracing SDK | devtool | skip / new recipe |
| ittnotify | 16.06.18 | `ittapi` | 3.28.4 | l64 o64(3.25.3) (no la64,oa64) | 0 | Intel SEAPI (VTune) | devtool | skip (cf `ittapi` linux-64/osx-64) |
| dablooms | 0.9.1 | **missing** | — | — | 1 | used by Utilities/StaticAnalyzers | devtool | skip |
| git / git-lfs | 2.54.0 / 3.7.1 | `git` | 2.55.0 | all 4 | 0 |  | devtool | none |
| lcov | 1.9 | `lcov` | 2.5 | all 4 | 0 |  | devtool | none |
| sloccount | 2.26 | **missing** | — | — | 0 |  | devtool | skip |
| glimpse | 4.18.7-6 | `glimpse` | 4.18.7 | l64 la64 o64 (no oa64) | 0 | `cms-externals` repo | devtool | skip (cf no osx-arm64) |
| gnuplot | 5.2.8 | `gnuplot` | 6.0.5 | all 4 | 0 |  | devtool | none |
| clang-uml | 0.6.2x | **missing** | — | — | 0 |  | devtool | skip |
| mozsearch | 20251022 | **missing** | — | — | 0 | code browser | devtool | skip |
| ruff | 0.5.6 | `ruff` | 0.16.7 | all 4 | 0 |  | devtool | none |
| cmssw-config / python-paths / python_tools / das_client / SCRAM | V09-09-09 / 1.0 / 3.1 / v03.01.00 | `dasgoclient` | 02.04.54 | all 4 | 1 | CMS build/infra glue | toolchain | replace with conda activation + CMake/SCRAM strategy (not packages) |

## Python (`py3-*`) tools (402)

**392 of 402 are on conda-forge.** The py3.12-compatible latest version was checked per platform; almost all are noarch or built for all 4 platforms.

**Missing (10):**

| tool | version | notes |
|---|---|---|
| `py3-cmsml` | 0.2.7 | CMS ML helpers (pure Python on PyPI). Easy noarch recipe. |
| `py3-cms-tfaot` | 1.0.1 | CMS TF AOT tooling. Needed by `tfaot-*`/PhysicsTools/TensorFlowAOT. |
| `py3-scinum` | 2.2.2 | Pure Python. Easy noarch recipe. |
| `py3-dxr` | 1.0.x | CMS-built code indexer (devtool). Skip. |
| `py3-flawfinder` | 2.0.20 | Devtool. Skip or easy noarch. |
| `py3-prwlock` | 0.4.1 | Pure Python. Easy noarch recipe. |
| `py3-textual-fspicker` | 1.0.1 | Pure Python. Easy noarch recipe. |
| `py3-virtualenvwrapper` | 6.1.1 | Devtool. Skip. |
| `py3-dash-svg` | 0.0.12 | Pure Python. Easy noarch recipe. |
| `py3-tensorflow-io-gcs-filesystem` | 0.37.1 | TF GCS plugin. Skip (not needed). |

**Present, but with platform gaps for py3.12:**
- **Linux-only:** `pycuda` (GPU), `triton` (GPU), `secretstorage` (o64 exists, no osx-arm64).
- **Only on linux-64 and osx-64:** `histogrammar` and `argparse`. `argparse` is stdlib, so this is irrelevant.

**conda-forge is older than CMSSW:**

| package | CMSSW | conda-forge |
|---|---|---|
| `histogrammar` | 1.1.2 | 1.0.32 |
| `plotille` | 6.0.5 | 5.0.0 |
| `pycuda` | 2026.1 | 2025.1.2 |
| `pyg-lib` | 0.7.0 | 0.6.0 |
| `singledispatch` | 4.1.2 | 3.6.1 |
| `tensorboard` | 2.21.0 | 2.20.0 |
| `python-xxhash` | 3.8.1 | 3.7.0 |

Everything else on conda-forge is at the CMSSW version or newer.

**Naming differences:**

| CMSSW tool | conda-forge name |
|---|---|
| `py3-torch` | `pytorch` |
| `py3-tables` | `pytables` |
| `py3-matplotlib` | `matplotlib-base` |
| `py3-xgboost` | `py-xgboost` |
| `py3-msgpack` | `msgpack-python` |
| `py3-flatbuffers` | `python-flatbuffers` |
| `py3-blosc2` | `python-blosc2` |
| `py3-kaleido` | `python-kaleido` |
| `py3-xxhash` | `python-xxhash` |
| `py3-cx-oracle` | `cx_oracle` |
| `py3-torch-scatter`, `py3-torch-sparse`, `py3-torch-cluster` | `pytorch_scatter`, `pytorch_sparse`, `pytorch_cluster` |
| `py3-backports-*`, `py3-jaraco-*`, `py3-repoze-lru` | dotted names (e.g. `backports.zstd`, `jaraco.classes`, `repoze.lru`) |

**Pinning notes:**
- `numpy` is 1.26.4 in CMSSW but pinned to 2 on conda-forge (see above).
- `py3-tensorflow` is 2.17.0 in CMSSW. conda-forge has 2.21.0 on l64/oa64, 2.19.1 on la64 and 2.18.0 on o64.
- `sqlalchemy` is 1.3.24 in CMSSW. It is still installable, but conda-forge's current ecosystem is 2.x.
- `protobuf` (Python) is 5.29.6 in CMSSW vs 7.x on conda-forge. Keep it consistent with libprotobuf.

<details><summary>Full py3 table (402 rows)</summary>

| tool | CMSSW version | conda-forge name | cf latest (py3.12-compatible) | platforms |
|---|---|---|---|---|
| py3-absl-py | 2.5.0 | `absl-py` | 2.5.0 | noarch |
| py3-annotated-types | 0.7.0 | `annotated-types` | 0.8.0 | noarch |
| py3-anyio | 4.14.1 | `anyio` | 4.15.1 | noarch |
| py3-appdirs | 1.4.4 | `appdirs` | 1.4.4 | noarch |
| py3-argon2-cffi-bindings | 25.1.0 | `argon2-cffi-bindings` | 26.1.0 | all 4 |
| py3-argon2-cffi | 25.1.0 | `argon2-cffi` | 25.1.0 | noarch |
| py3-argparse | 1.4.0 | `argparse` | 1.4.0 | l64 o64 |
| py3-asn1crypto | 1.5.1 | `asn1crypto` | 1.5.1 | noarch |
| py3-astor | 0.8.1 | `astor` | 0.8.1 | noarch |
| py3-astroid | 4.1.2 | `astroid` | 4.3.1 | all 4 |
| py3-asttokens | 3.0.1 | `asttokens` | 3.0.2 | noarch |
| py3-astunparse | 1.6.3 | `astunparse` | 1.6.3 | noarch |
| py3-async-lru | 2.3.0 | `async-lru` | 2.3.0 | noarch |
| py3-atomicwrites | 1.4.1 | `atomicwrites` | 1.4.1 | noarch |
| py3-attrs | 26.1.0 | `attrs` | 26.1.0 | noarch |
| py3-autopep8 | 2.3.2 | `autopep8` | 2.3.2 | noarch |
| py3-avro | 1.12.1 | `avro` | 1.12.2 | noarch |
| py3-awkward-cpp | 54 | `awkward-cpp` | 56 | all 4 |
| py3-awkward-pandas | 2023.8.0 | `awkward-pandas` | 2023.8.0 | noarch |
| py3-awkward | 2.10.0 | `awkward` | 2.13.0 | noarch |
| py3-babel | 2.18.0 | `babel` | 2.18.0 | noarch |
| py3-backcall | 0.2.0 | `backcall` | 0.2.0 | noarch |
| py3-backports-entry-points-selectable | 1.3.0 | `backports.entry-points-selectable` | 1.3.0 | noarch |
| py3-backports-tarfile | 1.2.0 | `backports.tarfile` | 1.2.0 | noarch |
| py3-backports-zstd | 1.6.0 | `backports.zstd` | 1.7.0 | noarch |
| py3-beautifulsoup4 | 4.15.0 | `beautifulsoup4` | 4.15.0 | noarch |
| py3-beniget | 0.5.0 | `beniget` | 0.5.0 | noarch |
| py3-bleach | 6.4.0 | `bleach` | 6.4.0 | noarch |
| py3-blinker | 1.9.0 | `blinker` | 1.9.0 | noarch |
| py3-blosc2 | 4.7.0 | `python-blosc2` | 4.12.0 | all 4 |
| py3-bokeh | 3.9.1 | `bokeh` | 3.10.0 | noarch |
| py3-boost-histogram | 1.7.2 | `boost-histogram` | 1.8.1 | all 4 |
| py3-bottleneck | 1.6.0 | `bottleneck` | 1.6.0 | all 4 |
| py3-cachecontrol | 0.14.4 | `cachecontrol` | 0.14.4 | noarch |
| py3-cachetools | 7.1.4 | `cachetools` | 7.1.8 | noarch |
| py3-cachy | 0.3.0 | `cachy` | 0.3.0 | noarch |
| py3-calver | 2025.10.20 | `calver` | 2025.10.20 | noarch |
| py3-certifi | 2026.6.17 | `certifi` | 2026.7.22 | noarch |
| py3-cffi | 2.1.0 | `cffi` | 2.1.1 | noarch |
| py3-chardet | 7.4.3 | `chardet` | 7.6.0 | noarch |
| py3-charset-normalizer | 3.4.9 | `charset-normalizer` | 3.5.1 | noarch |
| py3-choreographer | 1.3.0 | `choreographer` | 1.3.0 | noarch |
| py3-cleo | 2.1.0 | `cleo` | 2.1.0 | noarch |
| py3-click | 8.4.2 | `click` | 8.5.0 | noarch |
| py3-clikit | 0.6.2 | `clikit` | 0.6.2 | noarch |
| py3-cloudpickle | 3.1.2 | `cloudpickle` | 3.1.2 | noarch |
| py3-cms-tfaot | 1.0.1 | **missing** | — | — |
| py3-cmsml | 0.2.7 | **missing** | — | — |
| py3-colorama | 0.4.6 | `colorama` | 0.4.6 | noarch |
| py3-colorlover | 0.3.0 | `colorlover` | 0.3.0 | noarch |
| py3-comm | 0.2.3 | `comm` | 0.2.3 | noarch |
| py3-commonmark | 0.9.2 | `commonmark` | 0.9.2 | noarch |
| py3-contextlib2 | 21.6.0 | `contextlib2` | 21.6.0 | noarch |
| py3-contourpy | 1.3.0 | `contourpy` | 1.4.0 | all 4 |
| py3-correctionlib | 2.9.0 | `correctionlib` | 2.9.0 | all 4 |
| py3-coverage | 7.15.0 | `coverage` | 7.16.0 | noarch |
| py3-cppy | 1.3.1 | `cppy` | 1.3.1 | noarch |
| py3-cramjam | 2.11.0 | `cramjam` | 2.11.0 | all 4 |
| py3-crashtest | 0.4.1 | `crashtest` | 0.4.1 | noarch |
| py3-cryptography | 49.0.0 | `cryptography` | 50.0.1 | all 4 |
| py3-cx-oracle | 8.3.0 | `cx_oracle` | 8.3.0 | all 4 |
| py3-cycler | 0.12.1 | `cycler` | 0.12.1 | noarch |
| py3-cython | 3.2.8 | `cython` | 3.3.0 | noarch |
| py3-dash-bootstrap-components | 2.0.4 | `dash-bootstrap-components` | 2.0.4 | noarch |
| py3-dash-svg | 0.0.12 | **missing** | — | — |
| py3-dash | 4.4.0 | `dash` | 4.4.1 | noarch |
| py3-dask-awkward | 2026.2.1 | `dask-awkward` | 2026.2.1 | noarch |
| py3-dask | 2026.7.0 | `dask` | 2026.8.0 | noarch |
| py3-debugpy | 1.8.21 | `debugpy` | 1.8.21 | all 4 |
| py3-decorator | 5.3.1 | `decorator` | 5.3.1 | noarch |
| py3-defusedxml | 0.7.1 | `defusedxml` | 0.7.1 | noarch |
| py3-deprecated | 1.3.1 | `deprecated` | 1.3.1 | noarch |
| py3-deprecation | 2.1.0 | `deprecation` | 2.1.0 | noarch |
| py3-dill | 0.4.1 | `dill` | 0.4.1 | noarch |
| py3-distlib | 0.4.3 | `distlib` | 0.4.3 | noarch |
| py3-distro | 1.9.0 | `distro` | 1.9.0 | noarch |
| py3-dnspython | 2.8.0 | `dnspython` | 2.8.0 | noarch |
| py3-docopt | 0.6.2 | `docopt` | 0.6.2 | noarch |
| py3-docutils | 0.23 | `docutils` | 0.23 | noarch |
| py3-dulwich | 1.2.10 | `dulwich` | 1.2.10 | all 4 |
| py3-dxr | 1.0.x | **missing** | — | — |
| py3-editables | 0.6 | `editables` | 0.6 | noarch |
| py3-entrypoints | 0.4 | `entrypoints` | 0.4 | noarch |
| py3-exceptiongroup | 1.3.1 | `exceptiongroup` | 1.3.1 | noarch |
| py3-execnet | 2.1.2 | `execnet` | 2.1.2 | noarch |
| py3-executing | 2.2.1 | `executing` | 2.2.1 | noarch |
| py3-fastjsonschema | 2.21.2 | `python-fastjsonschema` | 2.22.2 | noarch |
| py3-filelock | 3.29.7 | `filelock` | 3.32.6 | noarch |
| py3-findpython | 0.8.0 | `findpython` | 0.8.0 | noarch |
| py3-fire | 0.7.1 | `fire` | 0.7.1 | noarch |
| py3-flake8 | 7.3.0 | `flake8` | 7.3.0 | noarch |
| py3-flask | 3.1.3 | `flask` | 3.1.3 | noarch |
| py3-flatbuffers | 25.12.19 | `python-flatbuffers` | 25.12.19 | noarch |
| py3-flawfinder | 2.0.20 | **missing** | — | — |
| py3-flit-core | 3.12.0 | `flit-core` | 4.0.2 | noarch |
| py3-flit | 3.12.0 | `flit` | 4.0.2 | noarch |
| py3-fonttools | 4.63.0 | `fonttools` | 4.65.0 | noarch |
| py3-fsspec | 2026.6.0 | `fsspec` | 2026.7.0 | noarch |
| py3-funcsigs | 1.0.2 | `funcsigs` | 1.0.2 | noarch |
| py3-future | 1.0.0 | `future` | 1.0.0 | noarch |
| py3-gast | 0.7.0 | `gast` | 0.7.0 | noarch |
| py3-gitdb | 4.0.12 | `gitdb` | 4.0.12 | noarch |
| py3-gitpython | 3.1.50 | `gitpython` | 3.1.62 | noarch |
| py3-google-auth-oauthlib | 1.4.0 | `google-auth-oauthlib` | 1.4.1 | noarch |
| py3-google-auth | 2.55.2 | `google-auth` | 2.58.0 | noarch |
| py3-google-pasta | 0.2.0 | `google-pasta` | 0.2.0 | noarch |
| py3-grpcio-tools | 1.60.1 | `grpcio-tools` | 1.83.1 | all 4 |
| py3-grpcio | 1.60.1 | `grpcio` | 1.83.1 | all 4 |
| py3-h11 | 0.16.0 | `h11` | 0.16.0 | noarch |
| py3-h5py | 3.13.0 | `h5py` | 3.16.0 | all 4 |
| py3-hatch-fancy-pypi-readme | 25.1.0 | `hatch-fancy-pypi-readme` | 25.1.0 | noarch |
| py3-hatch-jupyter-builder | 0.9.1 | `hatch-jupyter-builder` | 0.9.1 | noarch |
| py3-hatch-vcs | 0.5.0 | `hatch-vcs` | 0.5.0 | noarch |
| py3-hatchling | 1.31.0 | `hatchling` | 1.32.0 | noarch |
| py3-hepdata-lib | 0.21.0 | `hepdata-lib` | 0.21.0 | noarch |
| py3-hepdata-validator | 0.3.6 | `hepdata-validator` | 0.3.6 | noarch |
| py3-hist | 2.10.1 | `hist` | 2.11.0 | noarch |
| py3-histogrammar | 1.1.2 | `histogrammar` | 1.0.32 | l64 o64 |
| py3-histoprint | 2.6.0 | `histoprint` | 2.7.1 | noarch |
| py3-httpcore | 1.0.9 | `httpcore` | 1.0.9 | noarch |
| py3-httpx | 0.28.1 | `httpx` | 0.28.1 | noarch |
| py3-idna | 3.18 | `idna` | 3.19 | noarch |
| py3-iminuit | 2.32.0 | `iminuit` | 2.32.0 | all 4 |
| py3-importlib-metadata | 9.0.0 | `importlib-metadata` | 9.0.1 | noarch |
| py3-importlib-resources | 7.1.0 | `importlib-resources` | 7.1.0 | noarch |
| py3-iniconfig | 2.3.0 | `iniconfig` | 2.3.0 | noarch |
| py3-ipaddress | 1.0.23 | `ipaddress` | 1.0.23 | noarch |
| py3-ipykernel | 7.3.0 | `ipykernel` | 7.3.0 | noarch |
| py3-ipython-pygments-lexers | 1.1.1 | `ipython_pygments_lexers` | 1.1.1 | noarch |
| py3-ipython | 9.15.0 | `ipython` | 9.17.1 | noarch |
| py3-ipython_genutils | 0.2.0 | `ipython_genutils` | 0.2.0 | noarch |
| py3-ipywidgets | 8.1.8 | `ipywidgets` | 8.1.9 | noarch |
| py3-isort | 8.0.1 | `isort` | 9.0.1 | noarch |
| py3-itsdangerous | 2.2.0 | `itsdangerous` | 2.2.0 | noarch |
| py3-janus | 2.0.0 | `janus` | 2.0.0 | noarch |
| py3-jaraco-classes | 3.4.0 | `jaraco.classes` | 3.4.0 | noarch |
| py3-jaraco-context | 6.1.2 | `jaraco.context` | 6.1.2 | noarch |
| py3-jaraco-functools | 4.5.0 | `jaraco.functools` | 4.6.0 | noarch |
| py3-jax | 0.9.0.1 | `jax` | 0.10.2 | noarch |
| py3-jaxlib | 0.9.0.1 | `jaxlib` | 0.10.2 | all 4 |
| py3-jedi | 0.20.0 | `jedi` | 0.20.0 | noarch |
| py3-jeepney | 0.9.0 | `jeepney` | 0.9.0 | noarch |
| py3-jinja2 | 3.1.6 | `jinja2` | 3.1.6 | noarch |
| py3-joblib | 1.5.3 | `joblib` | 1.6.0 | noarch |
| py3-json5 | 0.15.0 | `json5` | 0.15.0 | noarch |
| py3-jsonpickle | 4.1.2 | `jsonpickle` | 4.1.2 | noarch |
| py3-jsonschema-specifications | 2025.9.1 | `jsonschema-specifications` | 2025.9.1 | noarch |
| py3-jsonschema | 4.26.0 | `jsonschema` | 4.26.0 | noarch |
| py3-jupyter-builder | 1.0.2 | `jupyter-builder` | 1.2.3 | noarch |
| py3-jupyter-client | 8.9.1 | `jupyter_client` | 8.10.0 | noarch |
| py3-jupyter-console | 6.6.3 | `jupyter_console` | 6.6.3 | noarch |
| py3-jupyter-core | 5.9.1 | `jupyter_core` | 5.9.1 | noarch |
| py3-jupyter-events | 0.12.1 | `jupyter_events` | 0.12.1 | noarch |
| py3-jupyter-lsp | 2.3.1 | `jupyter-lsp` | 2.3.1 | noarch |
| py3-jupyter-packaging | 0.12.3 | `jupyter-packaging` | 0.12.3 | noarch |
| py3-jupyter-server-terminals | 0.5.4 | `jupyter_server_terminals` | 0.5.4 | noarch |
| py3-jupyter-server | 2.20.0 | `jupyter_server` | 2.21.1 | noarch |
| py3-jupyterlab-pygments | 0.2.2 | `jupyterlab_pygments` | 0.3.0 | noarch |
| py3-jupyterlab-server | 2.28.0 | `jupyterlab_server` | 2.28.1 | noarch |
| py3-jupyterlab-widgets | 3.0.16 | `jupyterlab_widgets` | 3.0.17 | noarch |
| py3-jupyterlab | 4.6.1 | `jupyterlab` | 4.6.3 | noarch |
| py3-kaleido | 1.3.0 | `python-kaleido` | 1.3.0 | noarch |
| py3-keras-applications | 1.0.8 | `keras-applications` | 1.0.8 | noarch |
| py3-keras-preprocessing | 1.1.2 | `keras-preprocessing` | 1.1.2 | noarch |
| py3-keras | 3.15.0 | `keras` | 3.15.1 | noarch |
| py3-keras2onnx | 1.7.0 | `keras2onnx` | 1.7.0 | noarch |
| py3-keyring | 25.7.0 | `keyring` | 25.7.0 | noarch |
| py3-kiwisolver | 1.5.0 | `kiwisolver` | 1.5.1 | all 4 |
| py3-law | 0.1.20 | `law` | 0.1.20 | noarch |
| py3-lazy-object-proxy | 1.12.0 | `lazy-object-proxy` | 1.12.0 | all 4 |
| py3-lit | 18.1.8 | `lit` | 23.1.1 | noarch |
| py3-lizard | 1.23.0 | `lizard` | 1.24.0 | noarch |
| py3-locket | 1.0.0 | `locket` | 1.0.0 | noarch |
| py3-lockfile | 0.12.2 | `lockfile` | 0.12.2 | noarch |
| py3-logistro | 2.0.1 | `logistro` | 2.0.1 | noarch |
| py3-luigi | 3.8.1 | `luigi` | 3.8.1 | noarch |
| py3-lxml | 6.1.1 | `lxml` | 6.1.3 | all 4 |
| py3-lz4 | 4.4.5 | `lz4` | 4.4.5 | all 4 |
| py3-mako | 1.3.12 | `mako` | 1.4.1 | noarch |
| py3-markdown-it-py | 4.2.0 | `markdown-it-py` | 4.2.0 | noarch |
| py3-markdown | 3.10.2 | `markdown` | 3.10.3 | noarch |
| py3-markupsafe | 3.0.3 | `markupsafe` | 3.0.3 | noarch |
| py3-matplotlib-inline | 0.2.2 | `matplotlib-inline` | 0.2.2 | noarch |
| py3-matplotlib | 3.11.0 | `matplotlib-base` | 3.11.1 | all 4 |
| py3-mccabe | 0.7.0 | `mccabe` | 0.7.0 | noarch |
| py3-mdit-py-plugins | 0.6.1 | `mdit-py-plugins` | 0.6.1 | noarch |
| py3-mdurl | 0.1.2 | `mdurl` | 0.1.2 | noarch |
| py3-meson-python | 0.20.0 | `meson-python` | 0.21.1 | noarch |
| py3-meson | 1.11.1 | `meson` | 1.12.0 | noarch |
| py3-mistune | 3.3.3 | `mistune` | 3.3.4 | noarch |
| py3-ml_dtypes | 0.5.4 | `ml_dtypes` | 0.5.4 | all 4 |
| py3-mock | 5.2.0 | `mock` | 5.2.0 | noarch |
| py3-more-itertools | 11.1.0 | `more-itertools` | 11.1.0 | noarch |
| py3-mplhep-data | 0.1.0 | `mplhep_data` | 0.1.0 | noarch |
| py3-mplhep | 1.3.1 | `mplhep` | 1.3.3 | noarch |
| py3-mpmath | 1.4.1 | `mpmath` | 1.4.1 | noarch |
| py3-msgpack | 1.2.1 | `msgpack-python` | 1.2.2 | all 4 |
| py3-multidict | 6.7.1 | `multidict` | 6.7.1 | noarch |
| py3-namex | 0.1.0 | `namex` | 0.1.0 | noarch |
| py3-narwhals | 2.23.0 | `narwhals` | 2.26.0 | noarch |
| py3-nbclient | 0.11.0 | `nbclient` | 0.11.0 | noarch |
| py3-nbconvert | 7.17.1 | `nbconvert` | 7.17.1 | noarch |
| py3-nbformat | 5.10.4 | `nbformat` | 5.11.1 | noarch |
| py3-ndindex | 1.10.1 | `ndindex` | 1.10.1 | noarch |
| py3-nest-asyncio | 1.6.0 | `nest-asyncio` | 1.6.0 | noarch |
| py3-nest-asyncio2 | 1.7.2 | `nest-asyncio2` | 1.7.2 | noarch |
| py3-networkx | 3.6.1 | `networkx` | 3.6.1 | noarch |
| py3-notebook-shim | 0.2.4 | `notebook-shim` | 0.2.4 | noarch |
| py3-notebook | 7.6.0 | `notebook` | 7.6.2 | noarch |
| py3-numexpr | 2.14.1 | `numexpr` | 2.14.2 | all 4 |
| py3-numpy | 1.26.4 | `numpy` | 2.5.3 | all 4 |
| py3-nvidia-ml-py | 13.610.43 | `nvidia-ml-py` | 13.610.43 | noarch |
| py3-oauthlib | 3.3.1 | `oauthlib` | 3.3.1 | noarch |
| py3-onnx | 1.22.0 | `onnx` | 1.22.0 | all 4 |
| py3-onnxconverter-common | 1.16.0 | `onnxconverter-common` | 1.16.0 | noarch |
| py3-onnxmltools | 1.16.0 | `onnxmltools` | 1.16.0 | noarch |
| py3-opt-einsum | 3.4.0 | `opt-einsum` | 3.4.0 | noarch |
| py3-optree | 0.19.1 | `optree` | 0.20.0 | all 4 |
| py3-orjson | 3.11.5 | `orjson` | 3.12.0 | all 4 |
| py3-overrides | 7.7.0 | `overrides` | 7.7.0 | noarch |
| py3-packaging | 26.2 | `packaging` | 26.3 | noarch |
| py3-pandas | 3.0.3 | `pandas` | 3.0.5 | all 4 |
| py3-pandocfilters | 1.5.1 | `pandocfilters` | 1.5.0 | noarch |
| py3-parsimonious | 0.11.0 | `parsimonious` | 0.11.0 | noarch |
| py3-parso | 0.8.7 | `parso` | 0.8.7 | noarch |
| py3-partd | 1.4.2 | `partd` | 1.4.2 | noarch |
| py3-pastel | 0.2.1 | `pastel` | 0.2.1 | noarch |
| py3-pathlib2 | 2.3.7.post1 | `pathlib2` | 2.3.7.post1 | all 4 |
| py3-pathspec | 1.1.1 | `pathspec` | 1.1.1 | noarch |
| py3-pbr | 7.0.3 | `pbr` | 7.1.1 | noarch |
| py3-pbs-installer | 2026.6.10 | `pbs-installer` | 2026.9.1 | noarch |
| py3-pdm-backend | 2.4.9 | `pdm-backend` | 2.4.9 | noarch |
| py3-pexpect | 4.9.0 | `pexpect` | 4.9.0 | noarch |
| py3-pickleshare | 0.7.5 | `pickleshare` | 0.7.5 | noarch |
| py3-pillow | 12.3.0 | `pillow` | 12.3.0 | all 4 |
| py3-pip | 26.1.2 | `pip` | 26.2.1 | noarch |
| py3-pkgconfig | 1.6.0 | `pkgconfig` | 1.6.0 | noarch |
| py3-pkginfo | 1.12.1.2 | `pkginfo` | 1.12.1.2 | noarch |
| py3-plac | 1.4.5 | `plac` | 1.4.7 | noarch |
| py3-platformdirs | 4.10.0 | `platformdirs` | 4.11.8 | noarch |
| py3-plotext | 5.3.2 | `plotext` | 5.3.2 | noarch |
| py3-plotille | 6.0.5 | `plotille` | 5.0.0 | noarch |
| py3-plotly | 6.8.0 | `plotly` | 7.0.0 | noarch |
| py3-pluggy | 1.6.0 | `pluggy` | 1.6.0 | noarch |
| py3-ply | 3.11 | `ply` | 3.11 | noarch |
| py3-poetry-core | 2.4.1 | `poetry-core` | 2.4.1 | noarch |
| py3-poetry-plugin-export | 1.10.0 | `poetry-plugin-export` | 1.10.0 | noarch |
| py3-poetry | 2.4.1 | `poetry` | 2.4.3 | noarch |
| py3-portpicker | 1.6.0 | `portpicker` | 1.6.0 | noarch |
| py3-prettytable | 3.18.0 | `prettytable` | 3.18.0 | noarch |
| py3-prometheus-client | 0.25.0 | `prometheus_client` | 0.26.0 | noarch |
| py3-prompt_toolkit | 3.0.52 | `prompt-toolkit` | 3.0.53 | noarch |
| py3-protobuf | 5.29.6 | `protobuf` | 7.35.1 | all 4 |
| py3-prwlock | 0.4.1 | **missing** | — | — |
| py3-psutil | 7.2.2 | `psutil` | 7.2.2 | all 4 |
| py3-ptyprocess | 0.7.0 | `ptyprocess` | 0.7.0 | noarch |
| py3-pure-eval | 0.2.3 | `pure_eval` | 0.2.4 | noarch |
| py3-py-cpuinfo | 9.0.0 | `py-cpuinfo` | 9.0.0 | noarch |
| py3-pyasn1-modules | 0.4.2 | `pyasn1-modules` | 0.4.2 | noarch |
| py3-pyasn1 | 0.6.4 | `pyasn1` | 0.6.4 | noarch |
| py3-pybind11 | 3.0.4 | `pybind11` | 3.1.0 | noarch |
| py3-pycodestyle | 2.14.0 | `pycodestyle` | 2.14.0 | noarch |
| py3-pycparser | 3.0 | `pycparser` | 3.0 | noarch |
| py3-pycuda | 2026.1 | `pycuda` | 2025.1.2 | l64 la64 |
| py3-pycurl | 7.47.0 | `pycurl` | 7.47.0 | all 4 |
| py3-pydantic-core | 2.46.4 | `pydantic-core` | 2.49.0 | all 4 |
| py3-pydantic | 2.13.4 | `pydantic` | 2.13.5 | noarch |
| py3-pydot | 4.0.1 | `pydot` | 4.0.1 | noarch |
| py3-pyflakes | 3.4.0 | `pyflakes` | 3.4.0 | noarch |
| py3-pyg-lib-cuda | 0.7.0 | `pyg-lib` | 0.6.0 | all 4 |
| py3-pyg-lib | 0.7.0 | `pyg-lib` | 0.6.0 | all 4 |
| py3-pygithub | 2.9.1 | `pygithub` | 2.10.0 | noarch |
| py3-pygments | 2.20.0 | `pygments` | 2.21.0 | noarch |
| py3-pyjwt | 2.13.0 | `pyjwt` | 2.13.0 | noarch |
| py3-pylev | 1.4.0 | `pylev` | 1.4.0 | noarch |
| py3-pylint | 4.0.6 | `pylint` | 4.0.8 | noarch |
| py3-pymongo | 4.17.0 | `pymongo` | 4.18.1 | all 4 |
| py3-pynacl | 1.6.2 | `pynacl` | 1.6.2 | all 4 |
| py3-pyparsing | 3.3.2 | `pyparsing` | 3.3.2 | noarch |
| py3-pyproject-metadata | 0.12.1 | `pyproject-metadata` | 0.12.1 | noarch |
| py3-pysocks | 1.7.1 | `pysocks` | 1.7.1 | noarch |
| py3-pysqlite3 | 0.6.0 | `pysqlite3` | 0.6.0 | noarch |
| py3-pytest-cov | 7.1.0 | `pytest-cov` | 7.1.0 | noarch |
| py3-pytest-runner | 6.0.1 | `pytest-runner` | 6.0.0 | noarch |
| py3-pytest-xdist | 3.8.0 | `pytest-xdist` | 3.8.0 | noarch |
| py3-pytest | 9.1.1 | `pytest` | 9.1.1 | noarch |
| py3-python-daemon | 3.1.2 | `python-daemon` | 3.1.2 | noarch |
| py3-python-dateutil | 2.9.0.post0 | `python-dateutil` | 2.9.0.post0 | noarch |
| py3-python-discovery | 1.4.4 | `python-discovery` | 1.6.0 | noarch |
| py3-python-json-logger | 4.1.0 | `python-json-logger` | 4.2.0 | noarch |
| py3-python-ldap | 3.4.7 | `python-ldap` | 3.4.7 | all 4 |
| py3-python-rapidjson | 1.23 | `python-rapidjson` | 1.25 | all 4 |
| py3-pythran | 0.18.1 | `pythran` | 0.19.0 | noarch |
| py3-pytoml | 0.1.21 | `pytoml` | 0.1.21 | noarch |
| py3-pytools | 2026.1.1 | `pytools` | 2026.1.1 | noarch |
| py3-pytz | 2026.2 | `pytz` | 2026.3.post1 | noarch |
| py3-pyyaml | 6.0.3 | `pyyaml` | 6.0.3 | noarch |
| py3-pyzmq | 27.1.0 | `pyzmq` | 27.2.0 | all 4 |
| py3-rapidfuzz | 3.14.5 | `rapidfuzz` | 3.14.6 | all 4 |
| py3-referencing | 0.37.0 | `referencing` | 0.37.0 | noarch |
| py3-regex | 2026.6.28 | `regex` | 2026.9.10 | all 4 |
| py3-repoze-lru | 0.8 | `repoze.lru` | 0.8 | noarch |
| py3-requests-oauthlib | 2.0.0 | `requests-oauthlib` | 2.0.0 | noarch |
| py3-requests-toolbelt | 1.0.0 | `requests-toolbelt` | 1.0.0 | noarch |
| py3-requests | 2.34.2 | `requests` | 2.34.2 | noarch |
| py3-retrying | 1.4.2 | `retrying` | 1.4.2 | noarch |
| py3-rfc3339-validator | 0.1.4 | `rfc3339-validator` | 0.1.4 | noarch |
| py3-rfc3986-validator | 0.1.1 | `rfc3986-validator` | 0.1.1 | noarch |
| py3-rich | 15.0.0 | `rich` | 15.0.0 | noarch |
| py3-rpds-py | 2026.6.3 | `rpds-py` | 2026.6.3 | all 4 |
| py3-rsa | 4.9.1 | `rsa` | 4.9.1 | noarch |
| py3-scandir | 1.10.0 | `scandir` | 1.10.0 | all 4 |
| py3-schema | 0.7.8 | `schema` | 0.7.8 | noarch |
| py3-scikit-build-core | 1.0.1 | `scikit-build-core` | 1.0.3 | noarch |
| py3-scikit-build | 0.19.1 | `scikit-build` | 0.19.0 | noarch |
| py3-scikit-learn | 1.9.0 | `scikit-learn` | 1.9.1 | all 4 |
| py3-scinum | 2.2.2 | **missing** | — | — |
| py3-scipy | 1.17.1 | `scipy` | 1.18.1 | all 4 |
| py3-seaborn | 0.13.2 | `seaborn` | 0.13.2 | noarch |
| py3-secretstorage | 3.5.0 | `secretstorage` | 3.5.0 | l64 la64 |
| py3-semantic-version | 2.10.0 | `semantic_version` | 2.10.0 | noarch |
| py3-send2trash | 2.1.0 | `send2trash` | 2.1.0 | noarch |
| py3-setuptools-rust | 1.13.0 | `setuptools-rust` | 1.13.0 | noarch |
| py3-setuptools-scm | 10.2.0 | `setuptools-scm` | 10.2.3 | noarch |
| py3-setuptools | 83.0.0 | `setuptools` | 84.0.0 | noarch |
| py3-shellingham | 1.5.4 | `shellingham` | 1.5.4 | noarch |
| py3-simplegeneric | 0.8.1 | `simplegeneric` | 0.8.1 | noarch |
| py3-simplejson | 4.1.1 | `simplejson` | 4.1.2 | all 4 |
| py3-singledispatch | 4.1.2 | `singledispatch` | 3.6.1 | noarch |
| py3-siphash24 | 1.8 | `siphash24` | 1.9 | all 4 |
| py3-six | 1.17.0 | `six` | 1.17.0 | noarch |
| py3-skl2onnx | 1.20.0 | `skl2onnx` | 1.20.0 | noarch |
| py3-smmap | 5.0.3 | `smmap` | 5.0.3 | noarch |
| py3-sniffio | 1.3.1 | `sniffio` | 1.3.1 | noarch |
| py3-soupsieve | 2.8.4 | `soupsieve` | 2.9.2 | noarch |
| py3-sqlalchemy | 1.3.24 | `sqlalchemy` | 2.0.52 | all 4 |
| py3-stack-data | 0.6.3 | `stack_data` | 0.6.3 | noarch |
| py3-stevedore | 5.9.0 | `stevedore` | 5.9.1 | noarch |
| py3-subprocess32 | 3.5.4 | `subprocess32` | 3.5.4 | noarch |
| py3-sympy | 1.14.0 | `sympy` | 1.14.0 | noarch |
| py3-tables | 3.11.1 | `pytables` | 3.11.1 | all 4 |
| py3-tabulate | 0.10.0 | `tabulate` | 0.10.0 | noarch |
| py3-tblib | 3.2.2 | `tblib` | 3.2.2 | noarch |
| py3-tenacity | 9.1.4 | `tenacity` | 9.1.4 | noarch |
| py3-tensorboard-data-server | 0.7.2 | `tensorboard-data-server` | 0.7.0 | all 4 |
| py3-tensorboard-plugin-wit | 1.8.1 | `tensorboard-plugin-wit` | 1.8.1 | noarch |
| py3-tensorboard | 2.21.0 | `tensorboard` | 2.20.0 | noarch |
| py3-tensorflow-estimator | 2.15.0 | `tensorflow-estimator` | 2.19.1 | noarch |
| py3-tensorflow-io-gcs-filesystem | 0.37.1 | **missing** | — | — |
| py3-tensorflow | 2.17.0 | `tensorflow` | 2.21.0 | all 4 |
| py3-termcolor | 3.3.0 | `termcolor` | 3.3.0 | noarch |
| py3-terminado | 0.18.1 | `terminado` | 0.18.1 | noarch |
| py3-testpath | 0.6.0 | `testpath` | 0.6.0 | noarch |
| py3-textual-fspicker | 1.0.1 | **missing** | — | — |
| py3-textual-plotext | 1.0.1 | `textual-plotext` | 1.0.1 | noarch |
| py3-textual | 8.2.8 | `textual` | 8.2.8 | noarch |
| py3-threadpoolctl | 3.6.0 | `threadpoolctl` | 3.7.0 | noarch |
| py3-tinycss2 | 1.5.1 | `tinycss2` | 1.5.1 | noarch |
| py3-toml | 0.10.2 | `toml` | 0.10.2 | noarch |
| py3-tomli-w | 1.2.0 | `tomli-w` | 1.2.0 | noarch |
| py3-tomli | 2.4.1 | `tomli` | 2.4.1 | noarch |
| py3-tomlkit | 0.15.0 | `tomlkit` | 0.15.1 | noarch |
| py3-toolz | 1.1.0 | `toolz` | 1.1.0 | noarch |
| py3-torch-cluster-cuda | 1.6.3 | `pytorch_cluster` | 1.6.3 | all 4 |
| py3-torch-cluster | 1.6.3 | `pytorch_cluster` | 1.6.3 | all 4 |
| py3-torch-cuda | 2.13.0 | `pytorch` | 2.13.0 | all 4 |
| py3-torch-rocm | 2.13.0 | `pytorch` | 2.13.0 | all 4 |
| py3-torch-scatter-cuda | 2.1.2 | `pytorch_scatter` | 2.1.2 | all 4 |
| py3-torch-scatter | 2.1.2 | `pytorch_scatter` | 2.1.2 | all 4 |
| py3-torch-sparse-cuda | 0.6.18 | `pytorch_sparse` | 0.6.18 | all 4 |
| py3-torch-sparse | 0.6.18 | `pytorch_sparse` | 0.6.18 | all 4 |
| py3-torch | 2.13.0 | `pytorch` | 2.13.0 | all 4 |
| py3-tornado | 6.5.7 | `tornado` | 6.5.8 | all 4 |
| py3-tqdm | 4.68.4 | `tqdm` | 4.70.1 | noarch |
| py3-traitlets | 5.15.1 | `traitlets` | 5.16.1 | noarch |
| py3-triton | 3.7.1 | `triton` | 3.7.1 | l64 la64 |
| py3-trove-classifiers | 2026.6.1.19 | `trove-classifiers` | 2026.6.1.19 | noarch |
| py3-typed-ast | 1.5.5 | `typed-ast` | 1.5.5 | all 4 |
| py3-typing-extensions | 4.16.0 | `typing-extensions` | 4.16.0 | noarch |
| py3-typing-inspection | 0.4.2 | `typing-inspection` | 0.4.4 | noarch |
| py3-tzdata | 2026.2 | `tzdata` | 2026c | noarch |
| py3-uhi | 1.1.1 | `uhi` | 1.1.1 | noarch |
| py3-uncertainties | 3.2.3 | `uncertainties` | 3.2.3 | noarch |
| py3-uproot | 5.7.5 | `uproot` | 5.7.6 | noarch |
| py3-urllib3 | 2.7.0 | `urllib3` | 2.8.0 | noarch |
| py3-vcs-versioning | 2.2.2 | `vcs_versioning` | 2.3.4 | noarch |
| py3-vector | 1.8.1 | `vector` | 1.8.1 | noarch |
| py3-versioneer | 0.29 | `versioneer` | 0.29 | noarch |
| py3-virtualenv-clone | 0.5.7 | `virtualenv-clone` | 0.5.7 | noarch |
| py3-virtualenv | 21.6.0 | `virtualenv` | 21.7.9 | noarch |
| py3-virtualenvwrapper | 6.1.1 | **missing** | — | — |
| py3-wcwidth | 0.8.2 | `wcwidth` | 0.8.3 | noarch |
| py3-webencodings | 0.5.1 | `webencodings` | 0.5.1 | noarch |
| py3-websocket-client | 1.9.0 | `websocket-client` | 1.9.2 | noarch |
| py3-werkzeug | 3.1.8 | `werkzeug` | 3.1.8 | noarch |
| py3-wheel | 0.47.0 | `wheel` | 0.48.0 | noarch |
| py3-widgetsnbextension | 4.0.15 | `widgetsnbextension` | 4.0.16 | noarch |
| py3-wrapt | 1.14.1 | `wrapt` | 2.4.0 | all 4 |
| py3-xgboost | 1.7.5 | `py-xgboost` | 3.4.2 | noarch |
| py3-xxhash | 3.8.1 | `python-xxhash` | 3.7.0 | all 4 |
| py3-xyzservices | 2026.3.0 | `xyzservices` | 2026.9.1 | noarch |
| py3-zipp | 4.1.0 | `zipp` | 4.1.0 | noarch |

</details>

## Method and caveats

- **Platforms and versions.** "cf latest" and platforms come from the full `repodata.json` of each subdir, not `current_repodata`. Pre-release versions are ignored when a release exists. A package being listed on a platform does not guarantee a build for every Python version or every current pin. For py3 packages, py3.12 compatibility was checked explicitly.
- **Usage counts.** They come from `pkgs.json` (direct BuildFile `<use>` entries). Tools used only transitively through other tools (vecgeom, geant4data, pcre, …) show low or zero counts.
- **Patches and build notes.** They come from `cmsdist` `IB/CMSSW_20_1_X/master`, which is slightly newer than pre2. For forks hosted in `cms-externals`/`cms-sw`, the extra commits on the CMS branch were inspected via the GitHub API. The cmsdist master branch already moves protobuf→6.31, abseil→20250814, grpc→1.82, tensorflow→2.21, boost→1.92, eigen→5.0.1 and root→6.36.15, which brings CMS closer to conda-forge.
- **Not verified.** Whether the conda-forge `libtensorflow_cc` package ships the XLA AOT runtime (`tf_xla_runtime` sources/lib) used by `tensorflow-xla-runtime`/`tfaot` has not been checked. Treat it as missing until confirmed.
- **Staged-recipes check.** Open staged-recipes PRs were listed in full (1133 open PRs) and matched by title and recipe directory. Feedstock existence was checked via `conda-forge/<name>-feedstock`.
