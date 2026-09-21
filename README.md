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

- **Size:** CMSSW is a monorepo of about 1,350 packages and 17k C++ translation units. A full
  build is far too large for a single conda-forge CI job, so it has to be split into several
  packages that are built on top of each other.
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
- **Start small:** the first target is FWLite from `CMSSW_20_1_0_pre2`.

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
| `cmssw-fwlite` | [recipes/cmssw-fwlite](recipes/cmssw-fwlite) | ✅ | ✅ | ✅ |
| `cmssw-framework` (`cmsRun`) | [recipes/cmssw-framework](recipes/cmssw-framework) | ✅ | ✅ | ✅ |
| `cmssw-conditions` | [recipes/cmssw-conditions](recipes/cmssw-conditions) | ✅ | ✅ | ✅ |
| `cmssw-geometry` (DD4hep detector description) | [recipes/cmssw-geometry](recipes/cmssw-geometry) | ✅ | ✅ | ✅ |
| `cmssw-devel` (build your own packages) | [recipes/cmssw-devel](recipes/cmssw-devel) | ✅ | ✅ | ✅ |

✅ = builds locally with rattler-build (in Docker for Linux, natively for macOS) and passes the
recipe tests. — = not tried yet.

Every package now builds on all three platforms from the same sources. macOS builds against a
**newer ROOT than the release uses** (6.40 instead of 6.36) because conda-forge's 6.36 is
unusable there; see [PLAN.md](PLAN.md).

**What works**

- `cmssw-fwlite` (138 CMSSW packages, 1.7k translation units, a 60 MB package) builds against
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
- **All of the above also works on macOS (osx-arm64), natively.** The same seven packages build
  and pass their tests on an M1 Max in about 40 minutes: `cmsRun`, the conditions layer, the
  DD4hep geometry and the developer loop. It needs a newer ROOT than the release uses, and about
  a dozen small portability patches, all of which are meant to go upstream.
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
- Only 6 small CMSSW patches are needed (4 of them only for macOS), all meant for upstream.

## Where this stands

**There is an MVP on Linux**, but nothing has been submitted to conda-forge yet. What remains for a
released MVP is process rather than research: submit the dependency recipes (`alpaka`,
`hls-arbitrary-precision-types`, a `cms-md5` feedstock PR) and then `cmssw-fwlite`, and upstream the
CMSSW patches.

**Proven so far**

- Build cost is about 1-3 CPU-s per translation unit, roughly 10x cheaper than the first estimate.
  The full release extrapolates to about 15-25 CPU-hours, i.e. a handful of layered feedstocks
  rather than dozens.
- SCRAM runs inside rattler-build with small patches, so CMS's own dictionary, plugin and
  configuration generation is reused instead of being reimplemented.
- Layering works: a SCRAM developer area builds against an installed release.
- CMSSW compiles against conda-forge's toolchain and externals (it built with 3 different ROOT
  versions), so the ecosystem fits.

**Not proven yet** (roughly by risk)

1. Only about 10% of the code is built, and it is the cheapest 10%. Reco, Sim and L1 are heavier and
   more likely to need missing externals.
2. Layering exists only as a spike, not as recipes. The per-package plugin caches and build metadata
   need an end-to-end test with two installed conda packages.
3. `cmsRun` has not been run. It needs conditions access, i.e. new `coral` and `frontier_client`
   recipes (coral itself builds with SCRAM).
4. Heavy externals: geant4 with VecGeom and C++20, TensorFlow and libtorch which currently cannot be
   installed together, and a long tail of generators.
5. 8.6 GB of external data packages (one is 2.9 GB) versus what conda-forge accepts.
6. Maintenance: every ROOT/boost/python migration forces a coordinated rebuild of all layers. This
   is what ended the previous FWLite feedstock in 2022, so automation and upstreaming matter more
   than the initial build.

Rough estimate: `cmsRun` with reconstruction is a few weeks of work, a complete release with
simulation and generators is months plus an ongoing commitment. Nothing found so far looks like a
blocker; the two hard external blockers are small and social rather than technical (utm's missing
license, and the ROOT 6.36 macOS backport).

**Known issues / open questions**

- **macOS runtime:** `cmssw-fwlite` builds on osx-arm64, but conda-forge's ROOT 6.36.10 interpreter only
  handles system headers with the macOS 11.0 SDK it was built with (fixed upstream in ROOT 6.38, and
  conda-forge's ROOT 6.40 is fine). FWLite therefore only works on macOS with `SDKROOT` pointing at a
  MacOSX11.0.sdk. CMSSW stays on ROOT 6.36 for consistency with CMS releases, so the plan assumes the
  fix gets backported to conda-forge's `root-feedstock` 6.36.x branch; until then macOS is build-only.
- [utm](https://gitlab.cern.ch/cms-l1t-utm/utm), the CMS L1 trigger menu library, has **no
  license**, so it cannot be packaged yet. The 3 FWLite packages that need it are excluded for now.
- CMS's HepMC2 fork changes an ABI-relevant type. conda-forge's stock `hepmc2` is used instead,
  with a new dictionary class version. Reading GEN-level `HepMCProduct` data still needs validation.
- Fireworks (event display) is not included.
- The CMSSW source patches in [recipes/cmssw-fwlite/patches](recipes/cmssw-fwlite/patches) should
  be proposed upstream.

## Roadmap

1. Submit the dependency recipes and upstream the CMSSW patches; they gate everything else.
2. Build the next layer as a recipe: the framework with `cmsRun` and conditions access (CORAL,
   frontier_client). This tests layering and conditions, the two biggest unknowns, and is where
   CMSSW becomes useful beyond reading files.
3. Ask the CMS L1 utm authors for a license (pure lead time).
4. Then reconstruction, simulation, DQM, and automation for new CMSSW releases and conda-forge
   migrations.

See [PLAN.md](PLAN.md) for details.

## Repository layout

- [PLAN.md](PLAN.md): analysis, decisions, milestones and progress log.
- [recipes/](recipes): the recipes. The upstream staged-recipes `example-*` recipes are also here.
- [cmssw-notes/research](cmssw-notes/research): background research:
  - SCRAM internals;
  - availability of every external on conda-forge;
  - prior packaging attempts.
- [cmssw-notes/analysis](cmssw-notes/analysis): scripts that analyse the CMSSW package dependency
  graph and build cost, and propose how to split it.
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

Built packages end up in `/work/output`, which can be used as a local channel.
