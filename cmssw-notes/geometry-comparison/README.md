# Comparing the conda geometry against CMS's own build

This answers the question the `cmssw-geometry` layer left open: conda-forge's DD4hep is built
without `DD4HEP_USE_GEANT4_UNITS`, CMS's is built with it, and the recipe assumed that this is
harmless because CMSSW never relies on DD4hep's base unit. It does not have to be assumed any
more — both builds of `CMSSW_20_1_0_pre2` can be run side by side and compared.

## What is compared

1. **The stored geometry.** `dump.py` builds `DetectorDescription/DDCMS`'s tree-navigation test
   geometry and writes the `TGeoManager` to a ROOT file with the release's own `DDTestDumpFile`.
   `compare.py` prints every volume's shape parameters and every node's translation from such a
   file, and `scale.py` checks whether the two dumps are related by a single constant factor.
2. **What CMSSW actually reads.** `UnitProbe/` is a one-file EDAnalyzer that prints the same
   quantity raw, the `dd4hep::cm` constant its translation unit was compiled with, and the ratio
   of the two — which is how CMSSW converts a DD4hep length to its own centimetres. `probe.py`
   runs it. It is built in a developer area on each side, so it compiles with each side's flags.

## Running it

CVMFS has a native `el9_aarch64_gcc13` build of the same release, so this needs no emulation on
an arm64 host. `/cvmfs` can be bind-mounted into a container even though it is a FUSE mount:

```sh
docker run -d --name cmssw-cvmfs --platform linux/arm64 \
    -v /cvmfs:/cvmfs:ro -v cmssw-work:/work almalinux:9 sleep infinity
docker exec cmssw-cvmfs dnf install -y glibc-devel which procps-ng   # CMS's gcc needs these
```

Then in that container `scram project CMSSW_20_1_0_pre2` after
`source /cvmfs/cms.cern.ch/cmsset_default.sh`, and in a conda environment with `cmssw-geometry`
and `cmssw-devel`, `scram project $CMSSW_VERSION`. Copy `UnitProbe` into each `src/`, `scram b`,
and run `probe.py` and `dump.py` in both.

## The result (2026-09-21)

The stored geometry differs by exactly ten everywhere: 1250 non-zero numeric fields, every single
ratio 10.0, and no difference at all in structure (736 compared lines, identical volume and node
names, 725 nodes and 12 volumes on both sides). CMS stores millimetres, conda stores centimetres.

The unit constants differ by the same factor in the same direction, so everything CMSSW reads
agrees exactly:

| | CMS (CVMFS) | conda |
|---|---|---|
| `dd4hep::mm` | 1 | 0.1 |
| `dd4hep::cm` | 10 | 1 |
| world half-length, as stored | 450000 | 45000 |
| world half-length, `/ dd4hep::cm` | **45000** | **45000** |
| a node's x, as stored | 50000 | 5000 |
| a node's x, `/ dd4hep::cm` | **5000** | **5000** |

**A trap worth knowing.** Reading `dd4hep::mm` from a bare `cling` session gives 0.1 on *both*
sides, because `DD4hepUnits.h` switches on a macro that CMS sets as a compile flag in its
`dd4hep-core.xml` tool file. The constant has to be read from something compiled the way CMSSW is
compiled, which is why `UnitProbe` is an EDAnalyzer and not a script.
