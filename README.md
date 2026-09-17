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
| `alpaka` | [recipes/alpaka](recipes/alpaka) | ✅ | ✅ | ✅ |
| `hls-arbitrary-precision-types` | [recipes/hls-arbitrary-precision-types](recipes/hls-arbitrary-precision-types) | ✅ | ✅ | ✅ |
| `cms-md5` (existing feedstock needs new platforms) | [cmssw-notes/feedstock-changes/cms-md5](cmssw-notes/feedstock-changes/cms-md5) | ✅ | ✅ | ✅ |
| `cmssw-fwlite` | [recipes/cmssw-fwlite](recipes/cmssw-fwlite) | ✅ | ✅ | ⚠️ builds, runtime blocked |

✅ = builds locally with rattler-build (in Docker) and passes the recipe tests.

**What works**

- `cmssw-fwlite` (138 CMSSW packages, a 60 MB package) builds against conda-forge's ROOT 6.36,
  gcc 15 and python 3.12. It takes about 1 CPU-hour natively on aarch64, so it fits the default
  conda-forge CI runners.
- From a plain conda environment (no SCRAM, no CVMFS), FWLite reads CMS MiniAOD files, e.g.
  CMS Open Data over XRootD:

  ```python
  from DataFormats.FWLite import Events, Handle

  events = Events("root://eospublic.cern.ch//eos/opendata/cms/mc/RunIIFall15MiniAODv2/...")
  muons = Handle("std::vector<pat::io_v1::Muon>")
  for event in events:
      event.getByLabel("slimmedMuons", muons)
      print([m.pt() for m in muons.product()])
  ```

- The layering mechanism (a second set of packages built on top of an installed first one) was
  tested by hand with SCRAM. It is not yet a recipe.

**Known issues / open questions**

- **macOS runtime:** `cmssw-fwlite` builds on osx-arm64, but conda-forge's ROOT 6.36.10 interpreter only
  handles system headers with the macOS 11.0 SDK it was built with (fixed upstream in ROOT 6.38). FWLite
  therefore only works on macOS with `SDKROOT` pointing at a MacOSX11.0.sdk. CMSSW stays on ROOT 6.36 for
  consistency with CMS releases, so macOS runtime support is postponed.
- [utm](https://gitlab.cern.ch/cms-l1t-utm/utm), the CMS L1 trigger menu library, has **no
  license**, so it cannot be packaged yet. The 3 FWLite packages that need it are excluded for now.
- CMS's HepMC2 fork changes an ABI-relevant type. conda-forge's stock `hepmc2` is used instead,
  with a new dictionary class version. Reading GEN-level `HepMCProduct` data still needs validation.
- Fireworks (event display) is not included.
- The CMSSW source patches in [recipes/cmssw-fwlite/patches](recipes/cmssw-fwlite/patches) should
  be proposed upstream.

## Roadmap

1. Run the recipes in real conda-forge CI (linux-64) and submit the dependency recipes.
2. osx-arm64: the build works; runtime needs a fix for ROOT 6.36's interpreter on newer macOS SDKs.
3. Turn layering into recipes: the framework with `cmsRun` and conditions access (CORAL,
   frontier_client), then reconstruction, simulation and DQM.
4. Automate updates to new CMSSW releases and conda-forge migrations.

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
