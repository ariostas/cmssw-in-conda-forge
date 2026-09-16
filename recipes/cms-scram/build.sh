#!/bin/bash
set -euxo pipefail

SCRAM_HOME="${PREFIX}/share/scram"
mkdir -p "${SCRAM_HOME}/bin" "${PREFIX}/bin" "${PREFIX}/share/cmssw/etc/scramrc"

sed -i.bak -e "s|@CMS_PATH@|${PREFIX}/share/cmssw|g;s|@SCRAM_VERSION@|${PKG_VERSION_SCRAM}|g" SCRAM/__init__.py
rm SCRAM/__init__.py.bak
# dereference symlinks (not supported in noarch packages)
cp -RL SCRAM "${SCRAM_HOME}/"
cp cli/scram.py "${SCRAM_HOME}/bin/"
install -m 755 "${RECIPE_DIR}/scram-wrapper.sh" "${SCRAM_HOME}/bin/scram"
cat > "${PREFIX}/bin/scram" <<'WRAPPER'
#!/bin/bash
exec "$(dirname "$(realpath "$0")")/../share/scram/bin/scram" "$@"
WRAPPER
chmod 755 "${PREFIX}/bin/scram"

# Project lookup database: CMSSW releases are installed under share/cmssw/<arch>/cms/cmssw
echo 'CMSSW=$SCRAM_ARCH/cms/cmssw/CMSSW_*' > "${PREFIX}/share/cmssw/etc/scramrc/cmssw.map"
touch "${PREFIX}/share/cmssw/etc/scramrc/site.cfg"
