# CMSSW in conda-forge

This repository is an effort to package [CMSSW](https://github.com/cms-sw/cmssw), the software
framework of the CMS experiment at CERN, for [conda-forge](https://conda-forge.org). The goal is
to install it with

```sh
conda install -c conda-forge cmssw-fwlite   # or pixi add / mamba install
```

on **linux-64, linux-aarch64 and osx-arm64**, without CVMFS or a CMS-specific environment.

It is a fork of [conda-forge/staged-recipes](https://github.com/conda-forge/staged-recipes), the
entry point for new conda-forge packages. The original staged-recipes README is in
[README-staged-recipes.md](README-staged-recipes.md).

> **Status: proof of concept.** Nothing has been submitted to conda-forge yet.

## Why this is hard

- **Size:** CMSSW is a monorepo of about 1,360 packages and 15k C++ translation units (not
  counting tests). A full build is far too large for a single conda-forge CI job, so it has to be
  split into several packages that are built on top of each other.
- **Build system:** CMS uses its own build system,
  [SCRAM](https://github.com/cms-sw/SCRAM) with [cmssw-config](https://github.com/cms-sw/cmssw-config),
  and builds its ~200 externals itself with [cmsdist](https://github.com/cms-sw/cmsdist). Some of
  those externals carry CMS-specific patches, and a few are not on conda-forge at all.
- **Build-time code execution:** the build runs freshly built code (ROOT dictionaries, plugin
  registration, generated python configuration).
- **Platforms:** CMSSW targets Linux with GCC, and macOS support was dropped around 2015.

The full analysis, the decisions and a progress log are in [PLAN.md](PLAN.md).

## Approach

- **Build with SCRAM inside rattler-build.** Official releases use the same build rules
  (dictionaries, plugins, generated configs), so this stays as close to them as possible. It only
  needs a few small patches to SCRAM and cmssw-config, and the SCRAM tool files are generated to
  point at the conda environment.
- **Use conda-forge externals** (ROOT, boost, TBB, CLHEP, HepMC, ...) instead of CMS's builds.
  Missing dependencies get their own recipes, and CMSSW is patched where needed. The patches are
  meant to be upstreamed.
- **Split CMSSW into layers.** Each layer is a SCRAM developer area built on top of the layers that
  are already installed. Every package ships its own plugin cache and build metadata, so packages
  never overwrite each other's files.
- **Replace `cmsenv` with a conda activation script:** no SCRAM is needed at runtime.
- **Pin one ROOT and one CLHEP version per CMSSW version.**
- **Grow layer by layer:** FWLite first, then the framework, conditions, geometry, tracking,
  the rest of reconstruction, and finally DQM, validation and simulation, all from
  `CMSSW_20_1_0_pre2`. Each layer is chosen by the subsystems it should deliver plus exactly
  their dependencies (including headers CMSSW includes without declaring them), not by an even
  split of the code.

## Status

| Package | Recipe | linux-aarch64 | linux-64 | osx-arm64 |
|---|---|---|---|---|
| `cms-scram` | [recipes/cms-scram](recipes/cms-scram) | ✅ | ✅ | ✅ |
| `cmssw-toolbox` | [recipes/cmssw-toolbox](recipes/cmssw-toolbox) | ✅ | ✅ | ✅ |
| `alpaka` | [recipes/alpaka](recipes/alpaka) | ✅ | ✅ | ✅ |
| `hls-arbitrary-precision-types` | [recipes/hls-arbitrary-precision-types](recipes/hls-arbitrary-precision-types) | ✅ | ✅ | ✅ |
| `cms-md5` (existing feedstock needs new platforms) | [cmssw-notes/feedstock-changes/cms-md5](cmssw-notes/feedstock-changes/cms-md5) | ✅ | ✅ | ✅ |
| `cpu_features` (existing feedstock skips macOS) | [cmssw-notes/feedstock-changes/cpu_features](cmssw-notes/feedstock-changes/cpu_features) | — | — | ✅ |
| `frontier-client` | [recipes/frontier-client](recipes/frontier-client) | ✅ | ✅ | ✅ |
| `coral` | [recipes/coral](recipes/coral) | ✅ | ✅ | ✅ |
| `mille` (Millepede-II I/O) | [recipes/mille](recipes/mille) | ✅ | ✅ | ✅ |
| `gbl` (General Broken Lines) | [recipes/gbl](recipes/gbl) | ✅ | ✅ | ✅ |
| `classlib` (CMS socket/IO library, for DQM) | [recipes/classlib](recipes/classlib) | ✅ | ✅ | ✅ |
| `cmssw-fwlite` | [recipes/cmssw-fwlite](recipes/cmssw-fwlite) | ✅ | ✅ | ✅ |
| `cmssw-framework` (`cmsRun`) | [recipes/cmssw-framework](recipes/cmssw-framework) | ✅ | ✅ | ✅ |
| `cmssw-conditions` | [recipes/cmssw-conditions](recipes/cmssw-conditions) | ✅ | ✅ | ✅ |
| `cmssw-geometry` (DD4hep detector description) | [recipes/cmssw-geometry](recipes/cmssw-geometry) | ✅ | ✅ | ✅ |
| `cmssw-reco` (tracking, vertexing, muons) | [recipes/cmssw-reco](recipes/cmssw-reco) | ✅ | ✅ | ✅ |
| `cmssw-reco-objects` (RAW unpacking, calorimetry, e/gamma, particle flow, jets) | [recipes/cmssw-reco-objects](recipes/cmssw-reco-objects) | ✅ | ✅ | ✅ |
| `cmssw-sim-dqm` (DQM, validation, digitisation, fast simulation) | [recipes/cmssw-sim-dqm](recipes/cmssw-sim-dqm) | ✅ | ✅ | ✅ |
| `cmssw-devel` (build your own packages) | [recipes/cmssw-devel](recipes/cmssw-devel) | ✅ | ✅ | ✅ |

✅ = builds locally with rattler-build (in Docker for Linux, natively for macOS) and passes the
recipe tests. — = not needed: the existing feedstock already covers that platform.

Every package now builds on all three platforms from the same sources. macOS builds against a
**newer ROOT than the release uses** (6.40 instead of 6.36) because conda-forge's 6.36 is
unusable there; see [PLAN.md](PLAN.md).

**What works**

- `cmssw-fwlite` (138 CMSSW packages, 1.3k translation units, a 60 MB package) builds against
  conda-forge's ROOT 6.36, gcc 15 and python 3.12. It takes about 1 CPU-hour natively on aarch64
  (10 min wall time on 10 cores), so it fits the default conda-forge CI runners.
- From a plain conda environment (no SCRAM, no CVMFS, no `cmsenv`), FWLite reads CMS MiniAOD files,
  e.g. CMS Open Data over XRootD:

  ```python
  from DataFormats.FWLite import Events, Handle

  events = Events("root://eospublic.cern.ch//eos/opendata/cms/mc/RunIIFall15MiniAODv2/...")
  muons = Handle("std::vector<pat::io_v1::Muon>")
  for event in events:
      event.getByLabel("slimmedMuons", muons)
      print([m.pt() for m in muons.product()])
  ```

- `cmsRun` runs from that same environment. `cmssw-framework` adds the event processing
  framework, the EDM input and output modules and the storage layer, and its tests write an EDM
  file and read it back:

  ```sh
  cmsRun write.py && cmsRun read.py      # 5 events, products intact
  ```

  It also opens a CMS Open Data MiniAOD over XRootD. A conda environment is not a CMS site, so
  the package ships a site configuration that uses the global CMS services: files through the
  global XRootD redirector, conditions from the central Frontier servers.
- `coral` and `frontier-client`, which CMSSW needs to read detector conditions, both build in
  well under five minutes. CORAL turns out to be a SCRAM project like CMSSW, so it reuses the
  same toolbox.
- **Detector conditions come from the real CMS database.** With `cmssw-conditions` installed,
  `cmsRun` reads a payload from `frontier://FrontierProd/CMS_CONDITIONS` over the network, which
  exercises CORAL, the Frontier client and the payload deserialization:

  ```
  %MSG-s DataGetter: EventSetupRecordDataGetter:get@beginRun Run: 325175
  got data of type "BeamSpotObjects" with name "" in record BeamSpotObjectsRcd
  ```
- **The geometry agrees with CMS's own build.** conda-forge's DD4hep stores lengths in
  centimetres where CMS's stores millimetres, but the unit constants move with it, so every
  quantity CMSSW reads is identical and the node tree matches exactly. Checked against the
  CVMFS release rather than argued: see [cmssw-notes/geometry-comparison](cmssw-notes/geometry-comparison).
- **All of the above also works on macOS (osx-arm64), natively**, reconstruction included:
  `cmsRun`, the conditions layer, the DD4hep geometry, the reco layer and the developer loop. It
  needs a newer ROOT than the release uses, and small portability patches, all of which are meant
  to go upstream. Most of them are code that only compiled because libstdc++ is more permissive
  than libc++.
- **The normal CMSSW development loop works.** `cmssw-devel` adds the compilers and headers, and
  then a conda environment behaves like a `cmsrel` area on top of a CVMFS release:

  ```sh
  cmsrel CMSSW_20_1_0_pre2
  cd CMSSW_20_1_0_pre2/src
  cmsenv
  git cms-init && git cms-addpkg FWCore/Modules   # or copy it out of $CMSSW_RELEASE_BASE/src
  # ... edit ...
  scram b
  ```

  The rebuilt package shadows the one in the release, for linking and for `cmsRun`'s plugins.
  `git cms-init` works unchanged; without CVMFS its first run clones `cms-sw/cmssw` (1.6 GB,
  about 4 minutes), after which it takes 13 s and `git cms-addpkg` is instant.
- **The CMS detector geometry builds with conda-forge's DD4hep.** `cmssw-geometry` adds the
  detector description, the tracker and calorimeter geometry records, the magnetic field engine
  and the track propagators, and its test builds a detector from the CMS XML:

  ```
  Iterate over the detectors:
  ..done!
  ```

  This needed taking conda-forge's in-flight boost 1.90 migration, which the whole stack is now
  built against.
- **Reconstruction builds.** `cmssw-reco` (238 CMSSW packages, a 42 MB package) adds local
  reconstruction in the tracker, the Kalman-filter track finding and fitting chain, primary and
  secondary vertexing, muon reconstruction and identification, and the rest of the detector
  geometry. Its test loads every library of the release and constructs the core tracking,
  vertexing and muon modules from their generated configuration:

  ```
  5 producers, 42 ES producers
  reconstruction configuration built
  ```

  It needed two new externals, `gbl` and `mille`, the track-refitting libraries used by
  alignment. The plugins that run a TensorFlow or PyTorch inference are left out (see below).
- **The rest of reconstruction and the DQM/validation stack build.** `cmssw-reco-objects` (283
  packages) adds unpacking of the detector's raw data, calorimeter and muon local
  reconstruction, electrons and photons, particle flow, jets and b-tagging; its test constructs
  all of them, particle flow included:

  ```
  155 producers, 68 ES producers
  local reconstruction configuration built
  ```

  `cmssw-sim-dqm` (418 packages, 1538 libraries) adds data quality monitoring, validation,
  digitisation, fast simulation, alignment and calibration workflows and analysis tools. They
  needed one new external, `classlib`, and tool files for protobuf, onnxruntime, xgboost, hdf5,
  lhapdf and others that conda-forge already has.
- **The L1 trigger, RPC and conddb, on an assumed licence.** The L1 trigger menu library `utm`
  has no licence. It is packaged as `cms-l1t-utm` **on the assumption, not granted by its
  authors, that it will be released under Apache-2.0**, and with it the two layers above gain
  52 packages: the RPC chambers' formats, unpacking, rechits and digitisation, the legacy and
  Stage-2 L1 emulator and unpackers, and the conddb tools. None of this can be submitted until
  utm has a real licence.
- 22 CMSSW source patches in total, plus one to cmssw-config. About half are needed only for
  macOS, and most of those fix code that only compiled because libstdc++ is more permissive
  than libc++. All are meant for upstream.

## Where this stands

**Seven CMSSW layers build and pass their tests on all three platforms**, but nothing has been
submitted to conda-forge yet. They hold 1179 of
the release's 1358 packages: about 11.0k of its 15.3k translation units (excluding tests), or
**72% of the build**. 8 of those points depend on `utm`, which is used on an **assumed**
licence (above); without it the figure is 64%. That is everything reachable: what is left
needs externals that are broken on conda-forge or not packaged yet (below).
"Reachable" counts the headers CMSSW includes without declaring them as dependencies; on the
BuildFile graph alone the figure reads 63%, and two small patches (a dependency on `ktjet` that
nothing uses, and TensorFlow for a single e/gamma component) add three points.

**Proven so far**

- SCRAM runs inside rattler-build with small patches, so CMS's own dictionary, plugin and
  configuration generation is reused instead of being reimplemented.
- Layering works: each layer is a SCRAM developer area built against the installed release and
  then installed into it, and a user's own `scram b` area works on top in the same way.
- `cmsRun` runs, reads conditions from the central CMS database, and builds the CMS detector.
  The geometry was checked against CMS's own build of the release.
- CMSSW compiles against conda-forge's toolchain and externals (it has built with three
  different ROOT versions), including clang and libc++ on macOS.
- Build cost: about 7.6 CPU-s per translation unit measured end to end (including dictionaries,
  install and tests), so about 23 CPU-hours per architecture for the whole 72%. CPU is not the
  constraint.

**Not proven yet** (roughly by risk)

1. **Memory on CI.** The heaviest translation units (alpaka kernels in `RecoTracker/PixelSeeding`)
   peak at 4.3 GB each, and a default conda-forge runner has 7 GB. The reco layer therefore
   builds with one job there: about 2.2 hours of its 6-hour limit, which works but leaves little
   room for heavier layers. The layer builds size their job count from available memory.
2. **Externals beyond today's 72%**, cumulative in order: the ML runtimes (73%), the L1 ML
   models (86%; through `L1Trigger/L1TGlobal` and `HLTrigger/HLTcore` they also cost many
   plugins in every layer), a few small unpackaged externals (90%), CMS's Geant4 extensions
   (90%) and the event generators (94%).
3. **Data packages.** 8.6 GB of CMS data files (one repository is 2.9 GB) versus what
   conda-forge accepts. They are now the next thing in the way: the digitisers cannot even be
   configured without them, so nothing that simulates or reconstructs from RAW can run yet.
4. Maintenance: every ROOT/boost/python migration forces a coordinated rebuild of all layers, and
   upstream packages change under the stack. For example, fastjet split its headers into a new
   package mid-build, and that package cannot be installed next to lwtnn. This is what ended the
   previous FWLite feedstock in 2022, so automation and upstreaming matter more than the initial
   build.

The licences of two dependencies, utm and coral, are social rather than technical problems, and
they gate conditions tooling and L1 reconstruction from RAW.

**Known issues / open questions**

- **macOS uses ROOT 6.40, not the 6.36 the release was validated against.** conda-forge's 6.36
  ships prebuilt Darwin modules that only work with the macOS SDK they were built with, so cling
  fails on system headers for any user. ROOT 6.38 generates them from the active SDK. macOS can
  move back once conda-forge's 6.36.x carries that fix, or CMSSW moves to a newer ROOT.
- Two dependencies have **no licence** and cannot go to conda-forge until that is resolved:
  - [utm](https://gitlab.cern.ch/cms-l1t-utm/utm), the CMS L1 trigger menu library, needed by
    `CondFormats/L1TObjects` and through it the `conddb` tools, `DataFormats/RPCDigi`, the L1
    unpackers and the L1 emulator. It is packaged here (`cms-l1t-utm`) and those packages are
    built, on the **assumption that its authors will release it under Apache-2.0. They have
    not.** The request has not been made yet.
  - `coral`, the LCG relational abstraction layer used for conditions access. It is built here
    and works, but neither the CMS fork nor the upstream repository has a licence file or
    licence headers.
- **TensorFlow and PyTorch plugins are left out.** conda-forge has a `libtensorflow_cc`, but its
  C++ headers are incomplete (`xla/tsl/framework/allocator.h` is missing) and do not compile.
  This also costs the DeepSC superclustering, whose TensorFlow files are patched out of
  `RecoEcal/EgammaCoreTools` so that e/gamma and particle flow build; the PF superclusters
  themselves also need the Triton client.
- conda-forge's xrootd 6 headers use `statx` on Linux, which needs glibc 2.28, but the package
  does not say so, and `root_base` 6.36 keeps the build at 2.17. The one plugin package that
  includes them (`IORawData/DTCommissioning`) is built without its plugins.
- **macOS gets the scalar geometry vectors.** CMSSW enables its SIMD `Basic3DVector` only when
  `__BIGGEST_ALIGNMENT__ >= 16`, and Apple arm64 reports 8. Code that relied on the SIMD
  internals is patched to compute the same values either way, but macOS numerics may differ from
  Linux in the last bits, and the geometry comparison has only been run on Linux. A few
  Linux-only packages (the malloc-interposing memory monitors, the valgrind profiler and the
  beam halo generator) are left out on macOS.
- `cmssw-reco` pins `fastjet-cxx` to build 5, the last one that ships its headers. Build 6
  moved them into `fastjet-cxx-devel`, which needs a CGAL that needs eigen 5, while lwtnn needs
  eigen 3.4.
- `cmssw-devel` covers the layers up to `cmssw-conditions`. It does not yet pull in the
  development packages of the geometry and reco externals (dd4hep, geant4, fastjet, ...), so
  rebuilding a package from those layers needs them installed by hand.
- CMS's HepMC2 fork changes an ABI-relevant type. conda-forge's stock `hepmc2` is used instead,
  with a new dictionary class version. Reading GEN-level `HepMCProduct` data still needs validation.
- Fireworks (event display) is not included.
- The CMSSW source patches, in each layer's `patches/` directory, should be proposed upstream.

## Roadmap

1. Submit the dependency recipes (`alpaka`, `hls-arbitrary-precision-types`, `mille`, `gbl`,
   `classlib`, `frontier-client`, and PRs to the `cms-md5` and `cpu_features` feedstocks for the missing
   platforms) and upstream the CMSSW patches; they gate everything else.
2. Ask the utm and CORAL authors for a licence (pure lead time). utm is already used on an
   assumed Apache-2.0 licence; if its authors choose otherwise, the 8 points it brings come out.
3. The data packages, starting with those the digitisers and a RECO step read, so that a
   standard workflow can run end to end.
4. Fix conda-forge's TensorFlow headers; then the ML runtimes, simulation and generators, and
   automation for new CMSSW releases and conda-forge migrations.

See [PLAN.md](PLAN.md) for details.

## Repository layout

- [PLAN.md](PLAN.md): analysis, decisions, milestones and progress log.
- [recipes/](recipes): the recipes. The upstream staged-recipes `example-*` recipes are also here.
- [cmssw-notes/research](cmssw-notes/research): background research:
  - SCRAM internals;
  - availability of every external on conda-forge;
  - prior packaging attempts.
- [cmssw-notes/analysis](cmssw-notes/analysis): scripts that analyse the CMSSW package dependency
  graph and build cost, and propose how to split it. `reach.py` says what is reachable with the
  working externals and proposes layers, `includes.py` closes a layer over headers that CMSSW
  includes without declaring them, and `preflight.py` checks a layer before a build.
- [cmssw-notes/geometry-comparison](cmssw-notes/geometry-comparison): compares the geometry with
  CMS's own build of the release.
- [cmssw-notes/build-local.sh](cmssw-notes/build-local.sh): builds the recipes inside conda-forge
  CI containers.
- [CLAUDE.md](CLAUDE.md): notes for AI coding agents working on this repository.

## Building locally

The recipes use the [rattler-build](https://rattler.build) v1 format. To build them in the
conda-forge CI image (the repository is mounted at `/repo`):

```sh
docker run -it --platform linux/amd64 -v "$PWD":/repo -v cmssw-work:/work \
  quay.io/condaforge/linux-anvil-x86_64:alma9 bash
# inside the container
mamba create -y -p /work/tools -c conda-forge rattler-build conda-forge-pinning
cp /work/tools/conda_build_config.yaml /work/
PATH=/work/tools/bin:$PATH bash /repo/cmssw-notes/build-local.sh linux64
```

Built packages end up in `/work/output`, which can be used as a local channel. Under x86-64
emulation on an Apple-silicon Mac this is about 2.6x slower than a native linux-aarch64 build
(`condaforge/miniforge3`, config `linux_aarch64`).

The CMSSW layers limit their parallel jobs to what the available memory allows, at about 4.5 GB
per job, because a few translation units need that much. On macOS the recipes build natively; see
[CLAUDE.md](CLAUDE.md) for the setup (a macOS 15 SDK is needed, and long builds should run under
`caffeinate -i` so the machine does not sleep).
