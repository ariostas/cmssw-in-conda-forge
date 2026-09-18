"""Packages a layer's sources #include but that no layer installs.

The BuildFile graph understates what a layer needs. CMSSW is built as one area where every
package's interface/ is on the include path whether or not a BuildFile names it in a <use>,
so a package can include another's headers without declaring it and nobody notices upstream.
A layer that installs only what the dependency graph names then fails to compile, several
minutes in. Geometry/CaloEventSetup includes the Castor and Zdc headers from
Geometry/ForwardGeometry exactly like this.

Run before building a new layer, against the layer's packages.txt:

    python3 cmssw-notes/analysis/scripts/undeclared.py recipes/cmssw-geometry

This is a list of candidates, not a gate. A hit only breaks the build if a translation unit
that is actually compiled reaches the include; cmssw-conditions has three that do not, and it
builds. Check each one rather than adding packages blindly.
"""

import os
import re
import sys

RELEASE = "/cvmfs/cms.cern.ch/el9_amd64_gcc13/cms/cmssw/CMSSW_20_1_0_pre2"
LOWER = ["cmssw-fwlite", "cmssw-framework", "cmssw-conditions"]
SOURCE_SUFFIXES = (".cc", ".h", ".cpp", ".icc", ".hpp")


def read_list(path):
    out = []
    for line in open(path):
        line = line.split("#")[0].strip()
        if line:
            out.append(line.split(":")[0])
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    layer_dir = sys.argv[1].rstrip("/")

    installed = set()
    for recipe in LOWER:
        listing = os.path.join("recipes", recipe, "packages.txt")
        if os.path.exists(listing) and os.path.basename(layer_dir) != recipe:
            installed |= set(read_list(listing))
    layer = set(read_list(os.path.join(layer_dir, "packages.txt")))
    have = installed | layer
    src_only_file = os.path.join(layer_dir, "src-only.txt")
    src_only = set(read_list(src_only_file)) if os.path.exists(src_only_file) else set()

    missing = {}
    for pkg in sorted(layer):
        for root, _, files in os.walk(os.path.join(RELEASE, "src", pkg)):
            # test/ is deleted by cmssw-build-layer, and plugins/ and bin/ go too for the
            # src-only packages, so what any of them include does not matter
            if os.sep + "test" in root:
                continue
            if pkg in src_only and (
                os.sep + "plugins" in root or os.sep + "bin" in root
            ):
                continue
            for name in files:
                if not name.endswith(SOURCE_SUFFIXES):
                    continue
                try:
                    text = open(os.path.join(root, name), errors="ignore").read()
                except OSError:
                    continue
                for inc in re.findall(
                    r'#\s*include\s+"([A-Z][A-Za-z0-9]+/[A-Za-z0-9]+)/interface/', text
                ):
                    if inc not in have and os.path.isdir(
                        os.path.join(RELEASE, "src", inc)
                    ):
                        missing.setdefault(inc, set()).add(pkg)

    for pkg in sorted(missing):
        print(f"  {pkg:45s} included by {', '.join(sorted(missing[pkg]))}")
    print(
        f"{len(missing)} packages included by {os.path.basename(layer_dir)} but not installed"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
