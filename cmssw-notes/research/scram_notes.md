# SCRAM + cmssw-config: technical notes for packaging CMSSW in conda-forge

Scope: research only. Sources are the local clones under `_work/` (SCRAM `21a9cd1`, the
cmssw-config master clone, cmsdist, pkgtools) and the CVMFS release
`/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2` (built with config tag
`V09-09-09`; the clone is newer, so a few details differ, for example the edm cache fragment
naming). Paths below are relative to `_work/` unless they start with `/cvmfs`.

---

## 0. TL;DR

* **SCRAM V3 is about 4k lines of stdlib-only Python 3.** It parses XML (the `config/`,
  tool files and `BuildFile.xml`s), caches the results as JSON and generates GNU Make
  fragments. The build itself is **gmake running `config/SCRAM/GMake/Makefile.rules`**
  (2.3k lines of make macros) plus a Python "BuildRules" plugin (2k lines) from
  **cmssw-config**. Runtime needs are python3, bash (4+), GNU make (called as `gmake`),
  GNU coreutils/sed/grep/find, and `which`. Perl is only used by cmsdist tooling
  (`fix_tool_variables`), not by SCRAM.
* **SCRAM_ARCH is just a string `<os>_<cpu>_<compiler>`.** Almost nothing in cmssw-config
  parses it beyond `osx%` (Darwin), `_aarch64_`, `_amd64_` and `_mic_`, so
  `osx14_arm64_clang19` or `linux_amd64_gcc14` are acceptable. There *is* Darwin logic
  (`dylib`, `install_name_tool -id @rpath`, `-add_rpath`, `DYLD_FALLBACK_LIBRARY_PATH`),
  but it dates from the osx10* era and is unmaintained. Known breakages on macOS: SCRAM
  imports `os.sched_getaffinity` (Linux-only), there are GNU-only `cp -urpT`/`sed -i`/
  `declare -A`/`date +%N` calls, `CXXSHAREDFLAGS` gets a default only on Linux,
  `--push-state/--no-as-needed` is applied unconditionally for FORCE_LINK tools, and the
  cmsdist gcc tool has `-fuse-ld=bfd` and a stale Darwin branch (`-arch x86_64`). All of
  these are patchable. The larger macOS risk is CMSSW's C++ itself, which hasn't been
  built on macOS in about 10 years.
* **Every edm plugin's build *executes* built code.** `edmWriteConfigs -p plugin.so`
  runs `fillDescriptions` and writes about 10.8k `cfipython/*_cfi.py` files.
  `edmPluginRefresh plugin.so` dlopens the plugin to produce the plugin cache.
  `edmCheckClassVersion`/`edmCheckClassTransients` load the ROOT dictionaries. `rootcling`
  runs for every `classes_def.xml`, and CondFormats serialization runs a libclang Python
  script. **This holds for any build system (SCRAM or CMake), and it makes cross-compiling
  (e.g. osx-arm64 from osx-64) essentially impossible without deferring these steps.**
* **Release chaining.** `RELEASETOP` supports one level (dev area → release). Patch
  releases add a second level through a "scram-type tool" named after the project
  (`cmssw` → `CMSSW_BASE_FULL_RELEASE`, `IS_PATCH`). Arbitrary depth exists through
  scram-type tools with distinct names (`updateToolMK.py:getScramProjectOrder` recurses;
  CORAL is consumed this way). **With conda, every layer is installed into the *same
  prefix tree*, so a single level (RELEASETOP = merged installed tree, or one `cmssw`
  scram tool) is enough.** The catch is that global metadata files must be merged per
  install: `.SCRAM/<arch>/MakeData/DirCache.mk`, `BuildFiles/`, `MakeData/edmplugins`,
  `lib/<arch>/.edmplugincache`, and `python/<Subsystem>/__init__.py`.
* **Runtime.** PluginManager scans *each directory in `LD_LIBRARY_PATH`*
  (`DYLD_FALLBACK_LIBRARY_PATH` on macOS) for exactly one `.edmplugincache` (plus
  `.poisonededmplugincache`). FileInPath needs `CMSSW_SEARCH_PATH`, and a hit is accepted
  only if it lies under `CMSSW_BASE`, `CMSSW_RELEASE_BASE` or `CMSSW_DATA_PATH`. The
  python package `__init__.py` files need `SCRAM_ARCH` (pyinit.py) or `LOCALRT`.
* **Metadata for a generated build already exists in machine-readable form**:
  - `.SCRAM/<arch>/BuildFiles/**` holds each parsed BuildFile as JSON.
  - `.SCRAM/<arch>/tools/<tool>` holds each tool as JSON.
  - `DirCache.json` holds the class map.
  - `MakeData/DirCache/*.mk` holds per-directory product definitions.
  - `etc/dependencies/*.out.gz` holds uses/usedby/prod2src at header level.
  - `compile_commands.json` has 17,172 TUs.
  - `scram b echo_<var>` prints any computed make variable.

  There is prior art for BuildFile→CMake: **gartung/scram2cmake** (`buildfile2cmake`,
  about 1000 lines, last commit 2021) plus **gartung/cmaketools** and **cmssw-spack**,
  which handle genreflex, `.edmplugincache` and `edmWriteConfigs` in CMake.
* **Size and cost.** 1,230 packages / 2,430 BuildFiles; 17,172 C++ TUs (145 MB source);
  954 shared libs + 1,873 edm plugins + 282 `classes_def.xml` dictionaries; 224 alpaka
  `.cc` files built per backend (serial/cuda/rocm). The CVMFS `lib/` is 3.2 GB because
  **everything is built twice (x86-64-v3 default + `scram_x86-64-v2` multi-target)**;
  one microarch is about 1.6 GB. No build logs or timings are on CVMFS; cmssdt build logs
  sit behind CERN SSO.

---

## 1. SCRAM end to end

### 1.1 Components and runtime requirements

| piece | where | language |
|---|---|---|
| `scram` CLI | `SCRAM/cli/scram` (bash wrapper) → `SCRAM/cli/scram.py` | python3, stdlib only (`xml.etree`, `json`, `argparse`) |
| core (areas, tools, runtime env, DirCache) | `SCRAM/SCRAM/{Configuration,Core,BuildSystem}` | python3 |
| build rules generator plugin | `cmssw-config/SCRAM/Plugins/BuildRules.py` (+ `Plugins/CMSSW/ExtraBuildRule.py`) | python3, imported from `$LOCALTOP/config/SCRAM/Plugins` (see `SCRAM/SCRAM/Plugins/CMSSW/__init__.py` path hack) |
| make rules | `cmssw-config/SCRAM/GMake/Makefile.rules` + `Makefile.{edmplugin,lcgdict,cxxmodule,bigedm.rules,cuda,rocm,alpaka,serialization,pch,dnn,...}` | GNU make 4 macros |
| helpers | `cmssw-config/SCRAM/*.py, *.sh` (`updateToolMK.py`, `linkexternal.py`, `projectAreaRename.py`, `findDependencies.py`, `createSymLinks.sh` …) | python3 / bash |
| hooks | `cmssw-config/SCRAM/hooks/{project,runtime}/*` | bash |

* The wrapper `cli/scram` clears `LD_LIBRARY_PATH` and uses the *system* python3
  (`env -i PATH=/usr/bin:/bin bash -c 'command -v python3'`) unless `SCRAMRT_SET` is set.
  For conda this must be patched to use `$PREFIX/bin/python3`, or you must accept
  /usr/bin/python3.
* `SCRAM/__init__.py` has `BASEPATH='@CMS_PATH@'`, which is substituted at install
  (`cmsdist/SCRAMV1.spec`). It is used for the project lookup DB (`etc/scramrc/*.map`),
  site hooks, `share/overrides`, and version spawning (`$BASEPATH/common/scram`,
  `Core/Utils.py:spawnversion`). Set it to `$PREFIX/...` or use `SCRAM_LOOKUPDB`.
* `SCRAM_ARCH` **must be in the environment** (`ConfigArea.__init__`,
  `ProjectDB.__init__` read `environ['SCRAM_ARCH']` directly; KeyError otherwise).
* The make driver is `config/SCRAM/run_gmake.sh`: it runs
  `${SCRAM_GMAKE_PATH}gmake -r -f tmp/<arch>/Makefile`. `SCRAM_GMAKE_PATH` comes from
  the `gmake` tool's PATH (`RuntimeEnv._toolenv`). Conda's `make` package provides
  `make`, so a `gmake` symlink/tool is needed.
* `Makefile.rules` resolves `CMD_<x>` via `which` for:
  `sh awk basename cat cd chmod cp dirname diff echo false find g++ gcc grep ln ls mkdir mv
  printf python3 md5sum rm sed sort touch tr true uname uniq xargs ld wc cut git gunzip
  tail head objcopy ar rsync` (line 134).

### 1.2 `scram project`

* **Release bootstrap** (what cmsdist does, `cmsdist/scram-project-build.file`):
  1. `config/updateConfig.py -p CMSSW -v <ver> -s <scramver> -t <tool-conf> --keys ...`
     copies `Projects/CMSSW/*` (`BuildFile.xml`, `Self.xml`, `boot.xml`, `bootsrc.xml`)
     into `config/` and substitutes `@...@`.
  2. `scram project -d <dir> -b config/bootsrc.xml`
     (`SCRAM/Core/Commands/project.py:project_bootnewproject`,
     `Configuration/BootStrapProject.py`) creates `<dir>/CMSSW_X/`, copies `config`
     (and `src` for `bootsrc`), copies `toolbox/tools/{selected,available}` from the
     tool-conf into `config/toolbox/<arch>/tools/`, writes `.SCRAM/Environment` and
     `config/scram_version`, then runs `ToolManager.setupself()` + `setupalltools()`.
     That parses every tool XML into `.SCRAM/<arch>/tools/<name>` JSON.
* **Developer area**: `scram project CMSSW_X` or `scram project /abs/path`
  (`project_bootfromrelease`). It looks the release up via `ProjectDB`
  (`$BASEPATH/etc/scramrc/*.map`), then calls
  `ConfigArea.satellite()` (`Configuration/ConfigArea.py`), which:
  - copies the release `config/` and the `.SCRAM/<arch>/tools` JSON cache into the new
    area;
  - writes `.SCRAM/<arch>/Environment` with `RELEASETOP=<release>`;
  - creates `chkarch`;
  - runs the project hooks (`config/SCRAM/hooks/project-hook`).

### 1.3 Toolbox (`scram setup`)

* Tool XML files (`<tool name version [type=scram|compiler] [path=]>` with `<client>
  <environment name=INCLUDE|LIBDIR|…>`, `<lib>`, `<use>`, `<flags …>`,
  `<runtime name type=path>`) are parsed by `SCRAM/BuildSystem/ToolFile.py` into JSON:
  `LIB, INCLUDE, LIBDIR, USE, FLAGS{}, RUNTIME{PATH:VAR:[...]}, <TOOL>_BASE`.
  Example `/cvmfs/.../.SCRAM/el9_amd64_gcc13/tools/boost`.
* `scram setup <tool>` → `Commands/setup.py` → `ToolManager.coresetup`. If anything
  changed it then runs `scram build ExternalLinks`, which calls `linkexternal.py`. That
  creates `external/<arch>/{lib,bin,data}` symlink farms, so LD_LIBRARY_PATH/PATH/
  CMSSW_SEARCH_PATH need only one entry per release (`Self.xml` flags
  `EXTERNAL_SYMLINK`, `NO_EXTERNAL_RUNTIME`). In a conda prefix everything is already in
  `$PREFIX/lib`, so this farm is redundant but harmless.
* How cmsdist generates the tool files:
  - `cmsdist/scram-tools.file/tools/<pkg>/*.xml` are templates with `@VAR@`
    placeholders.
  - Optional `env.sh` scripts per tool compute those variables (e.g.
    `tools/gcc/env.sh` computes all compiler/linker flags, with a Darwin branch).
  - `bin/get_tools` copies the templates and runs `bin/fix_tool_variables` (perl),
    which expands `@VAR@` from the env and injects `name/version/path` into `<tool>`.
  - Assembly happens in `cmsdist/scram/tool-conf-src.file` (e.g. `cmssw-tools.spec`):
    it loops over `%requiredtools`, adds `systemtools` and a generated
    `python-paths.xml`, and generates simple tool files for every `py3-*` package.
  - There are 248 tool directories.
* **Project-type tools**: `tools/cmssw/cmssw.xml` and `tools/coral/coral.xml` are
  `<tool type="scram">`. They mark a SCRAM project consumed as an external
  (`SCRAM_PROJECT` in JSON). See §3.
* **For conda, the tool files are the main thing to write**. It is actually simpler than
  cmsdist: every tool has `path=$PREFIX`, `INCLUDE=$PREFIX/include` (or a subdir),
  `LIBDIR=$PREFIX/lib`, and runtime entries only where non-standard.
  `/Users/.../_work/tools.txt` lists the tool/version set.

### 1.4 `scram build`

`SCRAM/Core/Commands/build.py:process`:

1. It locates the area (`Core.initialize`: walks up for `.SCRAM`, reads
   `.SCRAM/Environment` and `.SCRAM/<arch>/Environment`, sets `LOCALTOP`,
   `RELEASETOP`). If RELEASETOP is set, it errors unless
   `$RELEASETOP/.SCRAM/<arch>/MakeData` exists.
2. It computes the **build-time runtime environment** (`RuntimeEnv.runtimebuildenv`) and
   *replaces* `os.environ` with it. Builds therefore run with the full tool runtime env,
   which is needed because built plugins are executed.
3. `DirCache.checkfiles()` walks `config/` and `src/`, matching dirs against the
   `<classpath>` rules in `config/BuildFile.xml`:
   `+Project/+SubSystem/+Package/src+library`, `.../plugins+plugins`,
   `bin+binary`, `test+test`, `python+python`, `scripts+scripts`,
   `BigProducts+SubSystem/+BigProduct/+donothing`. Directory mtimes and BuildFile mtimes
   are cached in `.SCRAM/<arch>/DirCache.json`.
4. On changes, `write_gmake()` calls the `BuildRules` plugin
   (`cmssw-config/SCRAM/Plugins/BuildRules.py`) for each added dir and BuildFile:
   - Templates `Project_template`, `SubSystem_template`, `Package_template`,
     `library_template`, `plugins_template`, `binary_template`, `test_template`,
     `python_template`, `BigProduct_template` write make fragments to
     `.SCRAM/<arch>/MakeData/DirCache/src_<Sub>_<Pkg>_<dir>.mk`.
   - These fragments are concatenated into `.SCRAM/<arch>/MakeData/DirCache.mk`
     (`BuildRules.endRules`), which is 4.1 MB for the full release.
   - Each parsed BuildFile is saved as JSON under `.SCRAM/<arch>/BuildFiles/<path>`,
     plus one tiny `<product>` file per product (`X_PACKAGE := self/...`).
   - `Project_template` writes `MakeData/src.mk` and `variables.mk`: flags from
     `config/BuildFile.xml`, plugin types, GENREFLEX/ROOTCLING paths.
5. `MakeInterface.exec` → `config/SCRAM/run_gmake.sh` → gmake with
   `tmp/<arch>/Makefile`, which is generated by `config/SCRAM/GMake/Makefile` and
   includes:
   - `MakeData/variables.mk` and `Makefile.rules`;
   - `MakeData/Tools.mk`, generated by `config/SCRAM/updateToolMK.py` from the tool JSON:
     `<tool>_EX_INCLUDE/LIB/LIBDIR/USE/FLAGS_*`;
   - `MakeData/Tools/SCRAMBased/all.mk` (from RELEASETOP / scram-type tools);
   - `DirCache.mk`.
6. `Makefile.rules` evaluates the per-product `*_INIT_FUNC` macros
   (`Library`, `Binary`, `edmPlugin`, `LCGDict`, `CondSerialization`, `BigProductRule`,
   ...) into concrete rules. It computes transitive `_LOC_USE_ALL`/`_EX_*_ALL` via cached
   recursive make functions and orders link libs via tool `_ORDER`. Flag precedence is in
   `AdjustFlagsImp` (line 375):
   compiler tool → `REM_<type>_<flag>` / `<type>_<flag>` (EDM, LCGDICT, BIGOBJ,
   TEST_LIBRARY …) → product `LOC_FLAGS` → per-file `FILE<name>_LOC_FLAGS` → `USER_*`
   env.
7. Target `release-build` (cmsdist) = `project_all`, then `PostBuild`
   (`CompilePython`, `ProjectPluginRefresh`, `poisoned_edmplugins`).

Typical cmsdist sequence (`cmsdist/scram-project-build.file`, `%build`):
- `scram b clean`
- `scram b -r echo_CXX` (forces cache regeneration)
- `scram b -f -k -j N llvm-ccdb` (produces `compile_commands.json`)
- `scram b --verbose -f USER_CXXFLAGS=... -jN release-build`
- `findDependencies.py`
- `run_edmPluginRefresh lib/<arch>`
- `scram install`
- `linkexternal.py`
- `gindices`
- debug-info split with `dwz`/`objcopy`

Environment knobs used there include `BUILD_LOG=yes`, `SCRAM_NOPLUGINREFRESH=yes`,
`SCRAM_NOLOADCHECK`, `SCRAM_NOSYMCHECK`.

Useful control env vars (`SCRAM/README.md` “CONTROL FLAGS”): `USER_CXXFLAGS` etc.,
`SCRAM_IGNORE_PACKAGES`, `SCRAM_IGNORE_SUBDIRS=test` (skip test dirs),
`SCRAM_NOEDMWRITECONFIG=1`, `SCRAM_NOEDM_CHECKS`, `SCRAM_NOSYMCHECK=1`,
`SCRAM_APPLY_BIGLIB_RULES=no`, `BUILD_LOG=yes`.

### 1.5 OS/arch assumptions and Linux-isms (for `osx*_arm64_clang*`)

What is already Darwin-aware:
* `Makefile.rules:124-129`: `IS_DARWIN` if SCRAM_ARCH matches `osx%`. It sets
  `SHAREDSUFFIX=dylib` and `OS_RUNTIME_LIBRARY_PATH=DYLD_FALLBACK_LIBRARY_PATH`
  (lines 221-230), and `install_name_tool -id @rpath/<lib>` +
  `-add_rpath $LOCALTOP/lib/<arch>` on every lib/plugin/bin copy (lines 553-633,
  `Makefile.edmplugin:77`).
* `config/BuildFile.xml` (`Projects/CMSSW/BuildFile.xml`): `<ifos name="darwin">`
  → `MISSING_SYMBOL_FLAGS=-Wl,-undefined,error`, else
  `-Wl,-z,defs` / `BIGOBJ_CXXFLAGS=-Wl,--exclude-libs,ALL`.
* `SCRAM/Core/RuntimeEnv.py:_fixlibenv`: on `osx*` it maps LD_LIBRARY_PATH to
  DYLD_FALLBACK_LIBRARY_PATH.
* `FWCore/PluginManager/src/standard.cc` reads `DYLD_FALLBACK_LIBRARY_PATH` under
  `__APPLE__`.
* `cmsdist/scram-tools.file/bin/os_libdir.sh`: `OS_RUNTIME_LDPATH_NAME`.

What is Linux-only or will break:
* `SCRAM/BuildSystem/MakeInterface.py:3` `from os import sched_getaffinity`. This is an
  **ImportError on macOS, so `scram build` cannot start**. It's a one-line patch
  (`os.cpu_count()`).
* `SCRAM/Core/Utils.py:cmsos()` runs a `cmsos` command (from cms-common). In dev areas
  `build.py:420` does `SCRAM_ARCH.startswith(None)`, a TypeError, and calls the
  non-existent `SCRAM.printwarning`. This only triggers when `.SCRAM/<arch>/chkarch`
  exists (dev areas) and can be avoided with `--ignore-arch` or a patch.
* `Makefile.rules:1867-1871`: `CXXSHAREDFLAGS := -shared` is defaulted only on Linux.
  On macOS it must come from the compiler tool (`-dynamiclib`/`-shared`).
* `Makefile.rules:1863` `get_link_lib_arg` adds `-Wl,--push-state -Wl,--no-as-needed
  -l<x> -Wl,--pop-state` for tools flagged `FORCE_LINK` (systemtools `resolv.xml` has
  `FORCE_LINK=1`) and for CUDA dlink libs. That's GNU ld only; don't set FORCE_LINK
  on macOS.
* Command-line GNUisms: `cp -urpT` (`src2store_copy`, line 837), `sed -i -e`
  (Makefile.rules, Makefile.edmplugin:78 area, hooks, utils), `declare -A`
  (`createSymLinks.sh`, bash ≥4), `date +%s.%N`, `/proc/$PPID/fd/1` (line 24, harmless),
  `ld -r -z muldefs` (`LD_UNIT` for BigProducts), `objcopy` (CUDA),
  `ld.so --help` (`support-psabi-micro-archs.sh`, multi-target hook, guarded by
  `uname -m = x86_64`). On macOS the build env needs conda `bash`, `make`, `sed`,
  `coreutils`, `findutils`, `grep` first in PATH.
* cmsdist gcc tool (`scram-tools.file/tools/gcc/env.sh`):
  - Linux: `OS_SHAREDFLAGS="-shared -Wl,-E"`, `OS_LDFLAGS="-Wl,-E -Wl,--hash-style=gnu
    -Wl,--as-needed -Wl,-z,noexecstack"`, `LD_UNIT="-r -z muldefs"`, `-fuse-ld=bfd`
    always (also visible in `compile_commands.json`).
  - Darwin branch is stale (`-arch x86_64 -single_module -Wl,-commons -Wl,use_dylibs`).
  - These flags live in *tool files*, which we would author anyway.
* A few CMSSW BuildFiles carry Linux linker flags, e.g. `REM_LDFLAGS="-Wl,--as-needed"`
  in `GeneratorInterface/{Hydjet,Pyquen,Hydjet2}Interface/plugins`. BuildFile flags are
  otherwise very tame: across 2,430 BuildFiles there are 71 `CXXFLAGS`, 18
  `REM_CXXFLAGS`, 6 `LDFLAGS` (mostly `-lXMLIO`), and 6 files with
  `ifos/architecture` conditionals.
* Multi-microarch (`SCRAM_TARGETS`, `lib/<arch>/scram_x86-64-v2/`,
  `hooks/runtime/90-cmssw-vectorize`) is x86-only and should be disabled for conda:
  empty `SCRAM_TARGETS` in `Self.xml`, no `.SCRAM/<arch>/multi-targets`.
* The SCRAM git history has no macOS-related commits. The Python rewrite (V3) has never
  been used on macOS; the Darwin bits in cmssw-config are inherited from the perl/V2 era
  (`osx10*` archs, around 2014-2016). The C++ side (e.g. `FWCore/Services/plugins/
  ProcInfoFetcher.cc`, `SimpleMemoryCheck.cc`, `/proc`, `malloc.h`) has Linux
  dependencies too. **Porting CMSSW sources to macOS is the bigger task, independent of
  SCRAM vs CMake.**

Verdict: SCRAM could plausibly work with `SCRAM_ARCH=osx14_arm64_clang19` after a
handful of small patches to SCRAM and cmssw-config plus a correct clang tool file. The
remaining risk is untested Darwin branches (rpath handling at copy time, `.dylib` vs
`.so` expectations in scripts such as `edm/*.cache` naming). This is feasible but
unproven.

---

## 2. Build products per package and what they mean for split conda packages

The release tree layout (product stores in `config/BuildFile.xml`) is:
`lib/<arch> bin/<arch> test/<arch> biglib/<arch> objs/<arch> static/<arch>
cfipython/<arch> logs/<arch> include python doc`, plus `src/`, `external/<arch>`,
`config/`, `.SCRAM/`, `etc/`.

Measured on `CMSSW_20_1_0_pre2` (sizes in MB, default microarch only; the `scram_x86-64-v2`
copy roughly doubles lib/bin/test):

| store | contents |
|---|---|
| `lib/el9_amd64_gcc13` | 954 `lib*.so` (430 MB), 1,873 `plugin*.so` (1,178 MB), 315 `*_rdict.pcm` + 315 `*.rootmap`, 1,873 per-plugin cache fragments (`<name>.edmplugin` in V09-09-09; `lib/edm/<name>.cache` in the newer config), `.edmplugincache` (16,502 lines), `lib*.components` (DD4hep plugin caches), `scram_x86-64-v2/` duplicate |
| `biglib/…` | `pluginSimulation.so` (31 MB) + its own `.edmplugincache` (210 lines) |
| `bin/…` | 408 executables (59 MB) + 227 python scripts |
| `test/…` | 799 test executables and test plugins (448 MB) |
| `objs/…` | 51 `*.obj` partially-linked objects (122 MB), used to relink BigProducts in dev areas |
| `static/…` | 81 `lib*_rocm.a` (198 MB), ROCm/CUDA device-code archives for alpaka dlink |
| `cfipython/…` | 10,764 generated `*_cfi.py` (+pyc) |
| `python/` | 1,457 `__init__.py` (+pyc) only; real modules live in `src/*/*/python` |
| `external/…` | 4,022 symlinks (externals symlink farm + `data/` links to cmsswdata) |
| `src/` | full sources (headers are needed by dev areas and ROOT_INCLUDE_PATH), `python/`, `data/`, `scripts/` (74k files) |

Product types and generation steps:

1. **Libraries** (`<pkg>/src` → `lib<SubPkg>.so`) and **edm plugins** (`<pkg>/plugins`
   or `EDM_PLUGIN=1` → `plugin<Name>.so`). Compile rules are `CXXCompileRule`; links are
   `link_lib_common`, with `-Wl,-z,defs` missing-symbol checks.
2. **edm plugin registration** (`Makefile.edmplugin:edm_register_plugin`). After linking:
   - `edmWriteConfigs -p <tmp plugin>` runs in `tmp/.../edm_write_config/`; the
     generated `*_cfi.py` files are copied to `cfipython/<arch>/<Sub>/<Pkg>/`, then
     checked for duplicates per package (`check_duplicate_cfi_config`).
   - `edmPluginRefresh <tmp plugin>` writes the per-plugin cache fragment.
   - At `PostBuild`/`ProjectPluginRefresh`, `config/SCRAM/run_edmPluginRefresh` does
     `cat lib/edm/*.cache > lib/.edmplugincache`. cmsdist sets `SCRAM_NOPLUGINREFRESH`
     and runs the concatenation once at the end.
   - **This needs the freshly built plugin plus all its dependencies to be loadable
     (runtime env) at build time.**
   - **Split impact:** `.edmplugincache` is one file per lib directory. Either give each
     conda package its own lib dir (and put all of them in the plugin search path), or
     ship per-plugin fragments and regenerate the merged cache in a post-link/activation
     step, or patch `PluginManager` to read a directory of fragments. The fragments
     already exist, so the patch is small.
3. **ROOT dictionaries** (`Makefile.lcgdict`, `BuildRules.searchForSpecialFiles`). For
   each `classes.h` + `classes_def.xml` (282 in src, plus alpaka
   `classes_<backend>_def.xml` variants), it runs
   `rootcling -reflex -f <x>r.cc -inlineInputHeader -rmf <x>r.rootmap -rml lib<X>.so
   -m <dep>_rdict.pcm … classes.h classes_def.xml`. The `.cc` is compiled into the same
   library; `*_rdict.pcm` and `.rootmap` go to `lib/<arch>`. Dependency pcm files are
   passed with `-m` (`Tool_DependencyPCMS`), so **dictionaries of dependent packages must
   exist first**. The ordering is expressed through `$(WORKINGDIR)/rootpcms/<pkg>` stamps.
   After linking, `edmCheckClassVersion -l lib -x classes_def.xml` and
   `edmCheckClassTransients` load the library (Python + ROOT).
   - C++ modules (`Makefile.cxxmodule`) are optional and off
     (`root_EX_FLAGS_CXXMODULES`; `ENABLE_TOOL_PCM=0`).
   - **Split impact:** `.rootmap` files are per library (no clash). ROOT finds rootmaps
     by scanning dynamic library paths, and pcm files must sit next to the library.
4. **CondFormats serialization** (`Makefile.serialization`): for `src/headers.h` (36
   packages) it runs `CondFormats/Serialization/python/condformats_serialization_
   generate.py`, which needs libclang Python bindings (`llvm` tool), and generates
   `Serialization.cc`.
5. **cfipython**: also `CFIPYTHON_PACKAGE_FILES` (`FWCore/ParameterSet/templates/modules.py`
   copied into each package's cfipython dir; `ExtraBuildRule.Project`).
6. **Python**:
   - Each `python/<Sub>/<Pkg>/__init__.py` is a copy of `config/SCRAM/pyinit.py`. It finds
     `cmssw_base_dir` from `__file__` and appends `src/<Sub>/<Pkg>/python` and
     `cfipython/$SCRAM_ARCH/<Sub>/<Pkg>` to `__path__`, so **`SCRAM_ARCH` is needed at
     runtime**.
   - Each `python/<Sub>/__init__.py` is generated by `create_subsystem_init`: in a
     release it inserts `$LOCALRT/python/<Sub>`; in a dev area it appends
     `$RELEASETOP/python/<Sub>`.
   - `.pyc` files are compiled with `python -m compileall` (`COMPILE_PYTHON_SCRIPTS=yes`).
   - `PYTHON3PATH` is read by cmsdist's python `sitecustomize.py`
     (`cmsdist/python3.spec:65`); for conda, use `PYTHONPATH` or a `.pth` file.
   - **Split impact:** the subsystem-level `__init__.py` (and `python/__init__.py`) would
     be installed by several packages if a subsystem is split. Either keep the file
     content identical and put it in a common "skeleton" package, or split by
     subsystem. Also, the layout under `$PREFIX` is non-standard
     (`$PREFIX/<root>/python`, `src/...`); it needs a `.pth`.
7. **Scripts** (`<pkg>/scripts/*` → `bin/<arch>`) and `bin/` executables.
   **Tests** (`<pkg>/test/BuildFile.xml`): 1,569 test `.cc` files. They can be skipped
   with `SCRAM_IGNORE_SUBDIRS=test`, but some *test plugins* are needed by unit tests of
   other packages.
8. **Data**: `src/<Sub>/<Pkg>/data` is used in place via
   `CMSSW_SEARCH_PATH=$LOCALTOP/src`. External data packages (`cmsswdata`, 43.0) are
   symlinked by `linkexternal.py` into `external/<arch>/data/<Sub>/<Pkg>`
   (`SYMLINK_DEPTH_CMSSW_SEARCH_PATH=2`), and `CMSSW_DATA_PATH` is set by the cmsswdata
   tool. **Data must be installed (it's in `src/`), and 4,440 data files are in the
   tree.**
9. **BigProducts / biglib** (`src/BigProducts/Simulation/BuildFile.xml`,
   `Makefile.bigedm.rules`): plugin objects are also compiled into `objs/<arch>/*.obj`
   (`ld -r`) and merged into `biglib/<arch>/pluginSimulation.so`. `biglib` comes before
   `lib` in LD_LIBRARY_PATH. **Cross-package by construction: disable it**
   (`scram b disable-biglib` or `SCRAM_APPLY_BIGLIB_RULES=no`; it's also automatically
   off for `SCRAM_DEFAULT_COMPILER=llvm`, line 1873). That saves 51 extra "big object"
   compiles.
10. **Alpaka backends** (`BuildRules.alpaka_template_generic`, `dumpBuildFileData`):
    - For each `<pkg>/*/alpaka/` dir and each selected backend in
      `ALPAKA_BACKENDS="cuda rocm serial"` (filtered by tool availability:
      `cuda-gcc-support`, `rocm`), a separate product
      `<Name>Portable{SerialSync,CudaAsync,ROCmAsync}` is generated from the same sources
      with `alpaka-<backend>` tool.
    - `.dev.cc` files go through nvcc/hipcc. CUDA device link (`nvcc -dlink`) uses
      `static/<arch>/lib*_cuda.a`.
    - **For conda: serial only, unless GPU variants are built. Set Self.xml
      `ALPAKA_BACKENDS="serial"` or don't provide cuda/rocm tools.**
    - Legacy CUDA (`*.cu`, 31 files) behaves similarly.
11. **Multi-targets** (`SCRAM_TARGETS`, `Makefile.rules:MultiTargets`): a second
    compile/link of every lib/plugin/bin for `x86-64-v2`. Disable it.
12. **LLVM analyzer/ccdb/iwyu/code-checks**: `checker`, `llvm-ccdb`, `code-checks*`,
    `emit-llvm`, `dxr`, `mozsearch` are all developer-only targets and irrelevant for
    packaging. `llvm-ccdb` re-runs the whole compile graph with `COMPILER=llvm
    SCRAM_GENERATE_LLVM_CCDB=YES` to write JSON instead of compiling (cheap).
13. **PCH / DNN / OpenCL / Rivet / DD4hep plugins**: `Makefile.pch` (`precompile.h`),
    `Makefile.dnn` (TF AOT `tfcompile`, `DNN_NAME`, 1 package), `Makefile.aocx`,
    Rivet plugins (`.rivetcache`, `RIVET_ANALYSIS_PATH`), and DD4hep plugins
    (`lib*.components` generated per lib by DD4hep's listcomponents, no merge needed).
14. **`.SCRAM/` metadata** is needed if users are to create dev areas on top of the
    conda install. Minimum set:
    - `.SCRAM/Environment`, `.SCRAM/<arch>/{tools/, DirCache.json, RuntimeCache.json}`;
    - `MakeData/{DirCache.mk, DirCache/*.mk, Tools.mk, Tools/, src.mk, variables.mk,
      edmplugins}`;
    - `BuildFiles/`, `config/`, `external/<arch>/links.DB`.

    `DirCache.mk` and `edmplugins` are concatenations of per-directory information, so
    they can be regenerated from per-package fragments at install/activation time.
15. **`etc/dependencies/*.out.gz`** (`findDependencies.py`): header-level
    `uses/usedby`, BuildFile `bfuses/bfusedby`, python `pyuses/pyusedby`, and
    `prod2src`. Useful for partitioning.
16. **Poisoned plugin caches** (`Makefile.edmplugin` bottom): in dev/patch areas, a
    `.poisonededmplugincache` masks release plugins that are rebuilt locally or deleted.
    Not needed if layers are disjoint.

Summary of items needing special handling when split into conda packages in one prefix:
`.edmplugincache` (merge), `python/<Sub>/__init__.py` (shared file),
`.SCRAM/<arch>/MakeData/{DirCache.mk,edmplugins}` + `BuildFiles/` (merge, only if dev
areas are supported), BigProducts (disable), `external/<arch>` symlink farm
(drop or regenerate), dictionary pcm dependency ordering (satisfied if dependencies
are installed first), build-time execution of plugins (native builds only), and
multi-target/alpaka GPU variants (disable).

---

## 3. Release chaining (RELEASETOP, patch releases, scram-type tools)

### 3.1 Dev area → release (one level)
* `.SCRAM/<arch>/Environment` contains `RELEASETOP=...` (`ConfigArea.satellite`).
* The `self` tool gets release paths appended for `INCLUDE`, `LIBDIR` and all `PATH:`
  runtime vars by replacing LOCALTOP with RELEASETOP (`ToolManager.addrelease`).
  So `-I$LOCALTOP/src -I$RELEASETOP/src`, `-L.../lib/<arch>` for both, and
  CMSSW_SEARCH_PATH / LD_LIBRARY_PATH / PYTHON3PATH include both.
* `updateToolMK.py` (tool `self` with reltop) processes
  `$RELEASETOP/.SCRAM/<arch>/MakeData/DirCache.mk` through `mkprocessfile`: it keeps
  only `_LOC_USE → _EX_USE`, `ALL_PRODS → ALL_EXTERNAL_PRODS`, and `self → tool`, then
  writes `MakeData/Tools/SCRAMBased/self.mk`. It also concatenates the release's
  `BuildFiles/src/**/<product>` files into `self_libs_def.mk`. The dev area therefore
  knows every release product's exported deps without rebuild rules.
* Local definitions win because every generated product block is guarded by
  `ifeq ($(strip $(<name>)),)` and the local `DirCache.mk` is included before
  `SCRAMBased/all.mk` (Makefile.rules:1843-1850).
* Differences in dev-area mode: `IS_DEV_AREA=1` (DEV_ vs RELEASE_ flag adjustments,
  line 1900; private-header check errors fatal), poisoned plugin caches, and subsystem
  python `__init__` appending `$RELEASETOP/python/<Sub>`.

### 3.2 Patch release (second level)
* A patch release (`cmsdist/cmssw-patch.spec` + `cmssw-patch-build.file`) is built as a
  *release area* (no RELEASETOP) whose toolbox contains the `cmssw` scram-type tool
  (`scram-tools.file/tools/cmssw/cmssw.xml`: LIBDIR/INCLUDE/runtime pointing at
  `$TOOL_BASE` = full release, and `CMSSW_FULL_RELEASE_BASE`).
* `updateToolMK.py`: if a tool name equals the project name, the base var is
  `CMSSW_BASE_FULL_RELEASE`, and `IS_PATCH:=yes` is written into `self.mk`.
  `Makefile.rules:18` sets `FULL_RELEASE_FOR_A_PATCH`, which is searched by
  `find_release_file` and used for unit-test dirs, CUDA dlink, and BigProducts
  `objs-full`. `ExtraBuildRule.Project` appends the full release `src` to
  CMSSW_SEARCH_PATH at build time.
* cmsdist then **symlinks all non-patched `src/`, `python/`, `cfipython/` packages from
  the full release** into the patch release (`PatchReleaseLink` macros). That's needed
  because FileInPath and pyinit resolve relative to CMSSW_BASE, and dev areas on top of
  a patch only know one RELEASETOP.
* A dev area on a patch release is RELEASETOP=patch + the `cmssw` tool inherited
  through the copied toolbox, giving 3 levels in practice.

### 3.3 Arbitrary depth via scram-type tools
* Any `<tool type="scram" name="X">` with `X_BASE` is treated like CORAL is by CMSSW:
  `ToolManager._toolsdata_scram` and `updateToolMK.getScramProjectOrder` recurse into
  `X_BASE/.SCRAM/<arch>/tools` to order projects, and `X_BASE/.SCRAM/<arch>/MakeData/
  DirCache.mk` is imported as external products. Multi-level chains of *differently
  named* SCRAM projects are supported by design.
* Caveats:
  - The name must be unique. `mkprocessfile` uses `%s_BASE % tool.upper()` without
    `-`→`_` conversion, while ToolFile converts, so avoid `-` in names.
  - Only the tool named like the project gets patch semantics.
  - Runtime/python/FileInPath don't handle N separate trees well; the patch release
    solves this with symlinks.
  - `.edmplugincache` works naturally with N trees because each tree's `lib/<arch>` is
    a separate LD_LIBRARY_PATH dir.

### 3.4 Could this build CMSSW in layers for conda?
Yes, and the conda single-prefix layout makes it easier than on CVMFS. All layers
install into the same tree `R=$PREFIX/<cmssw-root>` (`src/`, `lib/<arch>`,
`python/`, `cfipython/<arch>`, `.SCRAM/`). When building layer N, the host env already
contains layers 0..N-1 merged under `R`, so one chaining level is enough:

* **(a1) dev-area style:** `scram project` from `R` (RELEASETOP=R), put layer-N
  packages into `src/`, `scram b`, then install the products into `R`. This is the
  most exercised code path (every CMS developer does partial checkouts). Downsides:
  - dev-area semantics (poison caches, `DEV_` flags, python subsystem `__init__`
    appending RELEASETOP) must be post-processed into release form;
  - `R/.SCRAM/<arch>/MakeData/DirCache.mk` and `BuildFiles/` of the installed layers
    must be complete (merged).
* **(a2) patch-release style:** bootstrap a *release* area for layer N (`-b bootsrc.xml`
  with only the layer's `src`), with a `cmssw` scram-type tool pointing at `R`. The
  output is already release-shaped. `IS_PATCH` enables poison caches for the full
  release but nothing is overridden (disjoint packages). This matches exactly how patch
  releases are built.
* In both cases the per-layer products are disjoint files, except these merged/global
  ones:
  - `lib/<arch>/.edmplugincache` and `.poisonededmplugincache`;
  - `.SCRAM/<arch>/MakeData/{DirCache.mk,edmplugins,Tools.mk}`, `BuildFiles/`,
    `DirCache.json`, `RuntimeCache.json`;
  - `python/__init__.py` and `python/<Sub>/__init__.py`;
  - `external/<arch>/*` links.

  Handle them in a conda activation/post-link "regenerate" script from per-package
  fragments, or put each layer in its own subtree (`R/layers/<N>/...` with
  RELEASETOP/scram tools per layer, so N levels, not recommended).
* Build-time cost of SCRAM itself for a layer: parsing the release DirCache.mk (4 MB)
  and the tool makefiles takes on the order of a minute (not measured here).
  `scram b -r echo_CXX` for a full release regenerates everything.

---

## 4. Runtime environment (`cmsenv` = `eval $(scram runtime -sh)`)

`RuntimeEnv._runtime()` collects all tools' `<runtime>` entries (compilers last),
caches them in `.SCRAM/<arch>/RuntimeCache.json`, applies `SCRAM_PREFIX_<VAR>`
overrides and `share/overrides`, runs project runtime hooks
(`config/SCRAM/hooks/runtime/*`: `00-modulemap`, `00-nvidia-drivers`,
`01-gpu-selection`, `50-remove-release-external-lib`, `90-cmssw-vectorize`) and site
hooks, and prints export statements (saving old values as `SRT_<VAR>_SCRAMRT` for
`scram unsetenv`).

From `Self.xml` (project) + `RuntimeCache.json` of CMSSW_20_1_0_pre2:

| var | release value (R = release top) | purpose |
|---|---|---|
| `CMSSW_BASE`, `LOCALRT` | R (dev area: dev top) | FileInPath, python init, Config.py stack checks |
| `CMSSW_RELEASE_BASE` | `''` in release; RELEASETOP in dev area | FileInPath |
| `CMSSW_FULL_RELEASE_BASE` | from `cmssw` tool (patch) | Config.py |
| `CMSSW_VERSION`, `CMSSW_GIT_HASH` | version | various |
| `SCRAM_ARCH` | arch (set by cmsenv / login env) | pyinit.py (`cfipython/$SCRAM_ARCH`) |
| `LD_LIBRARY_PATH` | `R/biglib/<arch>:R/lib/<arch>:R/external/<arch>/lib` (+ cuda lib64 …) | dynamic loading, **edm PluginManager search path**, ROOT rootmap/pcm lookup |
| `PATH` | `R/bin/<arch>:R/external/<arch>/bin` + tools | executables |
| `PYTHON3PATH` | `R/python:R/lib/<arch>` (+ coral python/lib, `cmssw-tools/.../site-packages` for py3-* deps) | python modules; `lib/<arch>` holds pybind11 modules |
| `CMSSW_SEARCH_PATH` | `R/poison:R/src:R/external/<arch>/data` | FileInPath |
| `CMSSW_DATA_PATH` | cmsswdata install | FileInPath "Data" location |
| `ROOT_INCLUDE_PATH` | `R/src` + 85 external include dirs | cling header lookup for dictionaries at runtime |
| `RIVET_ANALYSIS_PATH` | `R/lib/<arch>`, `R/external/<arch>/lib/Rivet` | Rivet plugins |
| `TEST_SRTOPT_PATH` (optional) | `R/test/<arch>` | unit tests (`scram b runtests`) |
| `LANG=C`, `SCRAM_DEFAULT_MICROARCH`, `SCRAM_TARGET`, … | | |
| external vars | `G4*DATA`, `ROOTSYS`, `PYTHIA8DATA`, `LHAPDF_DATA_PATH`, `CLHEP_PARAM_PATH`, `HEPPDT_PARAM_PATH`, `EVTGENDATA`, `HERWIGPATH`, `THEPEGPATH`, `CEPGEN_PATH`, `FRONTIER_CLIENT`, `TNS_ADMIN`, `XRDCL_RECORDER_PLUGIN`, `OPENBLAS_NUM_THREADS`, `CUBLAS_WORKSPACE_CONFIG`, `ROCM_PATH`, … | these come from tool files; most conda packages set their own via activation |

**PluginManager** (`src/FWCore/PluginManager/src/standard.cc`, `PluginManager.cc`):
* The search path is the split `LD_LIBRARY_PATH` (`DYLD_FALLBACK_LIBRARY_PATH` if
  `__APPLE__`). There is no `CMSSW_PLUGIN_PATH`.
* For each existing directory it reads `<dir>/.edmplugincache` and
  `<dir>/.poisonededmplugincache` (poisoned entries map to `<dir>/poisoned`). Earlier
  dirs take precedence. The same plugin name twice *in the same dir* throws
  `MultiplePlugins`.
* Cache line format: `pluginFoo.so FooName CMS%EDM%Framework%Module`, with the file
  relative to the dir.
* If no cache is found and `mustHaveCache` is set, it throws.
* For conda:
  - (i) Set `LD_LIBRARY_PATH=$PREFIX/<root>/lib/<arch>` in activation. conda-forge
    frowns on setting LD_LIBRARY_PATH, and on macOS DYLD_* vars are stripped by SIP
    when going through `/bin/sh`, `/usr/bin/env` etc.
  - (ii) Patch `standard.cc` to also honour e.g. `CMSSW_PLUGIN_PATH` or a
    compiled-in `$PREFIX` path. **Recommended**: tiny patch that avoids LD_LIBRARY_PATH.
  - Library dependencies of plugins are found via RPATH (conda sets RPATH to
    `$PREFIX/lib`; CMSSW libs in `R/lib/<arch>` need an extra rpath entry, e.g.
    `$ORIGIN`).

**FileInPath** (`src/FWCore/Utilities/src/FileInPath.cc` — not ParameterSet):
* `CMSSW_SEARCH_PATH` must be set (it throws otherwise). It is tokenized on `:`, and
  `<element>/<relative path>` is checked.
* A hit is accepted only if some parent directory of the element equals
  `CMSSW_BASE` (Local), `CMSSW_RELEASE_BASE` (Release), or `CMSSW_DATA_PATH` (Data).
  If `CMSSW_RELEASE_BASE` is empty, `CMSSW_BASE` is treated as the release. Otherwise
  it continues with the next element and finally throws.
* For conda: `CMSSW_BASE=R`, `CMSSW_RELEASE_BASE` empty, `CMSSW_SEARCH_PATH=R/src:R/external/<arch>/data`
  (or data dirs directly under `CMSSW_DATA_PATH`), `CMSSW_DATA_PATH=<cmsswdata root>`.
  **Every search-path entry must live under one of those three roots.**

**Python**: `FWCore/ParameterSet/python/Config.py:54` uses
`CMSSW_BASE/CMSSW_RELEASE_BASE/CMSSW_FULL_RELEASE_BASE` for import-stack checks.
`python/<Sub>/__init__.py` in the release uses `LOCALRT`; `pyinit.py` needs
`SCRAM_ARCH` (or patch it to a fixed arch string at install).

A conda activation script would roughly be:
```sh
export SCRAM_ARCH=<fixed string>   CMSSW_VERSION=...  CMSSW_BASE=$R  LOCALRT=$R  CMSSW_RELEASE_BASE=
export CMSSW_SEARCH_PATH=$R/src:$R/external/$SCRAM_ARCH/data   CMSSW_DATA_PATH=$PREFIX/share/cmsswdata
export ROOT_INCLUDE_PATH=$R/src:$PREFIX/include${ROOT_INCLUDE_PATH:+:$ROOT_INCLUDE_PATH}
export CMSSW_PLUGIN_PATH=$R/lib/$SCRAM_ARCH     # requires PluginManager patch, else LD_LIBRARY_PATH
# PATH: symlink/copy bin/<arch>/* into $PREFIX/bin instead of exporting PATH
# PYTHONPATH: $R/python and $R/lib/<arch> via a .pth file in site-packages instead of env
# LANG=C, G4/Pythia/LHAPDF data vars: prefer the corresponding conda packages' own activation
```
(`PYTHON3PATH` is only honoured through cmsdist's `sitecustomize.py`; for conda use
`.pth` or `PYTHONPATH`.)

---

## 5. Non-SCRAM builds, metadata dumps, `compile_commands.json`

### 5.1 Machine-readable build metadata available from a SCRAM area
* `.SCRAM/<arch>/BuildFiles/src/<Sub>/<Pkg>/[<dir>/]BuildFile.xml`: parsed BuildFile as
  JSON (`USE`, `EXPORT`, `FLAGS`, `BUILDPRODUCTS` with `FILES`, conditionals already
  resolved for the arch/tools). Plus one file per product naming its package.
* `.SCRAM/<arch>/DirCache.json`: `CLASSMAP` (dir → template: 1,119 library, 740 plugins,
  1,170 test, 913 python, 68 binary, 116 scripts, 1 BigProduct), `BFCACHE`, `PACKMAP`.
* `.SCRAM/<arch>/tools/<tool>`: tool JSON (INCLUDE, LIB, LIBDIR, USE, FLAGS, RUNTIME).
* `.SCRAM/<arch>/MakeData/DirCache/*.mk`: per-dir product definitions, including the
  alpaka backend expansion and plugin flags (see
  `src_HeterogeneousCore_AlpakaTest_plugins.mk`).
* `scram b echo_<anyvar>` prints any make variable (`Makefile.rules:2022`), e.g.
  `echo_CXXFLAGS`, `echo_<Product>_LOC_USE_ALL`, `echo_<Product>_EX_LIB_ALL`;
  `echo_<pkg>_USES|_USED_BY|_ORIGIN` go through `projectInfo.py`.
  `scram b deps-tree A B`.
* `etc/dependencies/{uses,usedby,bfuses,bfusedby,pyuses,pyusedby,prod2src}.out.gz`.
* `compile_commands.json` (below).
* The SCRAM Python API itself (`SCRAM.BuildSystem.BuildFile`, `ToolFile`) can be imported
  offline to parse BuildFiles/tool files without gmake.

### 5.2 Existing CMake generators (prior art)
* **gartung/scram2cmake** `buildfile2cmake` (about 1,000 lines Python, last commit
  2021-06). It generates `CMakeLists.txt` per package/subsystem, including:
  - genreflex dictionary commands (`ROOT_genreflex_CMD`);
  - an `edmPluginRefresh` custom command producing `lib/.edmplugincache`;
  - `edmWriteConfigs -p $<TARGET_FILE>` producing cfipython;
  - python `__init__.py` generation;
  - test env (`CMSSW_BASE`, `CMSSW_SEARCH_PATH`, `LD_LIBRARY_PATH` …);
  - install rules for cfipython, pcm/rootmap, `.edmplugincache`.

  It is used with **gartung/cmaketools** (Find modules) by **gartung/cmssw-spack**
  (`packages/cmssw/package.py`: "CMSSW built with Cmakefile generated by scram2cmake",
  CMSSW_10_2_0_pre1, Ninja) and for "Stitched" (FWCore-only subset). It originated from
  Teemperor/scram2cmake (C++ modules work). It is stale (C++17 era, no alpaka, no
  CondFormats serialization, old genreflex), but shows the required custom steps.
* No CMake port exists inside the SCRAM or cmssw-config repos.
* `USER_CXXFLAGS`/`USER_LDFLAGS` etc. are environment overrides used by cmsdist (e.g.
  `-fdebug-prefix-map`, `-g`), not an alternative build.

### 5.3 `compile_commands.json` at the release top (79 MB)
* It is generated by `scram b llvm-ccdb`: the compile rules run with `COMPILER=llvm
  SCRAM_GENERATE_LLVM_CCDB=YES`, writing one JSON per object, merged by
  `config/SCRAM/llvm-ccdb.py`.
* **The commands are clang-flavoured**: `clang++ … --gcc-toolchain=<gcc>`, with clang-only
  warnings appended (`-Wno-c++11-narrowing -D__STRICT_ANSI__ -ftemplate-depth=512
  -fsized-deallocation …`). Not verbatim gcc commands.
* It contains 17,172 entries (16,564 `.cc`, 603 `.cpp`, 4 `.C`, 1 `.c`), all under `src/`,
  including `test/` dirs. It excludes rootcling-generated dictionary sources,
  serialization-generated sources, CUDA/ROCm and non-serial alpaka backends
  (`CODE_CHECK_ALPAKA_BACKEND=serial`; 220 alpaka entries are serial only), and
  multi-target duplicates.
* The average command is 4.4 kB (max 7.9 kB), with 21.6 include dirs on average (max 53).
* Flags are **almost uniform**:
  - `-O3 -std=c++20 -march=x86-64-v3 -flto=auto -fPIC -pthread -ftree-vectorize
    -fvisibility-inlines-hidden -fno-math-errno -fuse-ld=bfd -Xassembler
    --compress-debug-sections`, a long list of `-Werror=`/`-W` flags,
    `-DBOOST_DISABLE_ASSERTS -DGNU_GCC -D_GNU_SOURCE -DCMSSW_GIT_HASH/PROJECT_NAME/
    PROJECT_VERSION -DCMS_MICRO_ARCH=x86-64-v3`.
  - Variation comes mostly from tool defines: TBB (16.9k), Boost (16.9k), Eigen
    (12.6k), alpaka host (9.2k), Geant4 `-DG4V9` (7.4k), DD4hep (6.7k),
    `__STDC_*_MACROS` (1.8k), fastjet `KTDOUBLEPRECISION` (443). A handful of
    package-local defines exist.
  - Only 71 BuildFiles add CXXFLAGS.

  So a generated CMake build needs just a global flag set, per-target include
  dirs/defines from tool `USE`, and a few per-target extras. **Note that release builds
  use `-flto=auto`**; linking is then the heavy step. Drop LTO for conda.

---

## 6. Build-time data and size breakdown

* `/cvmfs/.../CMSSW_20_1_0_pre2/logs/el9_amd64_gcc13/` is **empty**. cmsdist moves
  per-package build logs out of the install (`tmp/<arch>/cache/log/src` →
  `$cmsroot/WEB/build-logs/<arch>/<ver>/logs/src/src-logs.tgz`). The public copy is
  under `https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/...`, which now redirects to CERN
  SSO. The logs contain no timestamps anyway; `HOOK_PACKAGE`/`HOOK_PRODUCT`/
  `USER_HOOK_*` in `Makefile.rules` could be used to record per-package start/end times
  in our own builds.
* **Size breakdown** (MB, default microarch; CVMFS doubles it with `scram_x86-64-v2`):
  - plugins 1,178;
  - shared libs 430;
  - tests 448;
  - static device archives 198;
  - `objs` for biglib 122;
  - bin 59;
  - biglib 31;
  - pcm+rootmap 4;
  - cfipython 4.5 (+10 pyc).

  The debug info is split into a separate RPM, so stripped sizes are likely similar.
* **Work units** (from `compile_commands.json`, DirCache.json and the CVMFS src listing):
  - 17,172 C++ TUs, 145 MB source;
  - 1,230 packages, 2,430 BuildFiles;
  - 954 libs + 1,873 plugins + 408 bins + 799 test products, i.e. ~4k links, plus as
    many `edmWriteConfigs` + `edmPluginRefresh` runs as there are plugins;
  - 282 `classes_def.xml` → rootcling + a large dictionary TU each;
  - 36 CondFormats serialization generations;
  - 224 alpaka `.cc` × backends; 74 `.dev.cc`; 31 `.cu`;
  - 1,569 test `.cc`.
* TU counts by subsystem (top): CondFormats 1,514, L1Trigger 1,248, DataFormats 1,105,
  FWCore 802, Geometry 757, DQM 740, PhysicsTools 637, CondTools 591, RecoTracker 466,
  EventFilter 463, Validation 425, Alignment 387, Fireworks 380, CommonTools 306.
  Largest packages: CondFormats/DataRecord 431, FWCore/Framework 281,
  OnlineDB/EcalCondDB 225, Fireworks/Core 177. Per-package TU and bytes are in
  `_work/cost.json`.
* **CPU estimate (assumption, not measured):** CMSSW TUs are heavy (-O3, Boost/ROOT/TBB/
  FWCore templates). Assuming 10-30 CPU-s per TU gives about 50-150 CPU-h of compilation
  for one microarch without LTO and without GPU backends. Add dictionaries (282 ×
  roughly 1-2 min rootcling + compile), ~4k links (cheap without LTO, heavy with it),
  and ~1.9k plugin load runs (a few seconds each). Excluding `test/` saves about 10% of
  TUs. A conda-forge job (2 cores × ~5.5 usable hours ≈ 11 CPU-h) therefore holds about
  7-20% of CMSSW, i.e. **roughly 10-20 layers/jobs minimum**, more with 7 GB RAM limits
  on heavy TUs. **Validate this by timing one mid-size subsystem** (e.g. FWCore:
  802 TUs) with `BUILD_LOG=yes` and `USER_HOOK_PRODUCT` timestamps, then scale by the TU
  and bytes numbers in `cost.json`.

---

## 7. Options and recommendation

### (a) SCRAM inside conda-build
Pros:
* Exact parity with official builds: the same BuildFile semantics, dictionaries, cfi
  generation, EDM checks, alpaka product expansion, python layout and tests.
* Near-zero maintenance as CMSSW evolves: cmssw-config tags are pinned per release.
* Layering fits: patch-release style (a2) or dev-area style (a1), with one chaining level
  because all layers share one prefix.
* **Users get the normal `cmsrel`/`scram project` + `git cms-addpkg` + `scram b`
  workflow on top of the conda install**, which is likely the most valuable feature for
  CMS users.
* Only small patches to SCRAM (python path, BASEPATH, sched_getaffinity, cmsos).

Cons:
* ~250 tool XMLs to author. They're trivial in a single prefix, but must track conda
  package names and versions.
* gmake + SCRAM metadata overhead.
* Global metadata files (DirCache.mk, BuildFiles, edmplugins, .edmplugincache,
  subsystem `__init__.py`) must be merged per installed package.
* Non-standard install tree and env vars.
* macOS Darwin branches are untested (patches needed).
* Cross-compilation is impossible: any build system has this problem.

### (b) Generated CMake (or Ninja) build
Pros:
* Idiomatic for conda-forge: ccache/sccache, Ninja, `install(COMPONENT)` per split
  output, `CMAKE_CROSSCOMPILING_EMULATOR` hooks, easier macOS work (Apple ld, rpath).
* No gmake-parse overhead.
* Arbitrary partitioning via target sets.
* Standard `$PREFIX/lib` layout, with a patched PluginManager and FileInPath roots.

Cons:
* You must reimplement and keep in sync: dictionary generation with pcm ordering,
  edm plugin cache, cfipython, class-version checks, CondFormats serialization
  (libclang), alpaka backend multiplication, per-file flags, private-header checks,
  scripts/python/data install, and unit test wiring.
* Divergence from what CMS validates.
* No `scram b` dev-area workflow for users unless SCRAM metadata is also produced.
* Prior art (scram2cmake) is ~5 years stale.

### (c) Hybrid: SCRAM front-end, CMake/Ninja back-end
Run `scram project -b` + `scram b -r echo_CXX` (or import SCRAM's `BuildFile`/`ToolFile`
parsers directly) on the source to obtain resolved products/uses/flags
(`.SCRAM/<arch>/BuildFiles` JSON + `DirCache/*.mk` + tool JSON), and generate one CMake
project per layer. The generator can be revived from scram2cmake. This keeps parsing
exact and gives CMake ergonomics, but the custom steps of (b) still have to be
maintained.

### Recommendation
Start with **(a), patch-release-style layering (a2) on linux-64**. It has the least new
code, gives exact parity plus the user dev-area workflow, and the layering mechanism
(release area + `cmssw` scram-type tool, or RELEASETOP) already exists and is exercised
daily. Concretely:
- SCRAM: patch `cli/scram` python selection, `BASEPATH`, `MakeInterface.sched_getaffinity`
  and `cmsos`.
- Tool files: generate from `tools.txt` pointing at `$PREFIX`.
- Self.xml: `ALPAKA_BACKENDS="serial"`, `SCRAM_TARGETS=""`, no LTO/PGO.
- Build: `disable-biglib`, `SCRAM_IGNORE_SUBDIRS=test` (initially).
- Install: per-plugin cache fragments + a regenerate step for `.edmplugincache`,
  `DirCache.mk` and `edmplugins`.
- Patch PluginManager to take a plugin path env var.
- Fix `SCRAM_ARCH` in pyinit via activation.

Treat macOS as a separate project whose main cost is porting CMSSW C++; revisit (c) only
if SCRAM's Darwin path or native-build constraints (build-time execution of plugins,
rootcling, libclang) prove unworkable there. Before committing to the partition, time
one subsystem build to calibrate the CPU-hours estimate.
