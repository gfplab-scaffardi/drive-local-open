#!/bin/zsh
# Build signed (or ad-hoc) Drive Local Open.app and wrap it in a DMG.
# Usage:
#   ./packaging/macos/build_dmg.sh
# Env:
#   SIGN_IDENTITY   Developer ID Application: Name (Company) — optional
#   NOTARY_PROFILE  notarytool keychain profile (default: drive-local-open-notary)
#   SKIP_NOTARIZE=1 skip Apple notarization even if SIGN_IDENTITY is set
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export PYINSTALLER_CONFIG_DIR="${ROOT}/build/pyinstaller-cache"
mkdir -p "${PYINSTALLER_CONFIG_DIR}"

VERSION="$(python3 -c "import pathlib,re; t=pathlib.Path('pyproject.toml').read_text(); print(re.search(r'version\\s*=\\s*\\\"([^\\\"]+)\\\"', t).group(1))")"
VENV="${ROOT}/.venv"
PYI="${VENV}/bin/pyinstaller"
DIST="${ROOT}/dist"
BUILD="${ROOT}/build"
APP_NAME="Drive Local Open.app"
APP="${DIST}/${APP_NAME}"
DMG_NAME="DriveLocalOpen-${VERSION}.dmg"
DMG="${DIST}/${DMG_NAME}"
STAGE="${DIST}/dmg-stage"
VOL="Drive Local Open"
NOTARY_PROFILE="${NOTARY_PROFILE:-drive-local-open-notary}"

if [[ ! -x "$PYI" ]]; then
  echo "Missing PyInstaller. Run: python3 -m venv .venv && .venv/bin/pip install pyinstaller" >&2
  exit 1
fi

# Auto-detect Developer ID if not provided
if [[ -z "${SIGN_IDENTITY:-}" ]]; then
  SIGN_IDENTITY="$(security find-identity -v -p codesigning 2>/dev/null \
    | sed -n 's/.*"\(Developer ID Application: .*\)"/\1/p' \
    | head -1 || true)"
fi

echo "==> PyInstaller (${VERSION})"
rm -rf "${DIST}/Drive Local Open" "${DIST}/${APP_NAME}" "${BUILD}/drive_local_open"
"$PYI" --noconfirm --clean \
  --distpath "$DIST" \
  --workpath "$BUILD" \
  packaging/macos/drive_local_open.spec

if [[ ! -d "$APP" ]]; then
  echo "Expected app missing: $APP" >&2
  exit 1
fi

echo "==> Codesign"
xattr -cr "$APP"
if [[ -n "${SIGN_IDENTITY}" ]]; then
  echo "    identity: ${SIGN_IDENTITY}"
  codesign --force --deep --options runtime --timestamp \
    --sign "${SIGN_IDENTITY}" "$APP"
  codesign --verify --deep --strict --verbose=2 "$APP"
else
  echo "    WARNING: no Developer ID — using ad-hoc signature (Gatekeeper will warn)"
  codesign --force --deep -s - "$APP"
fi

if [[ -n "${SIGN_IDENTITY}" && "${SKIP_NOTARIZE:-0}" != "1" ]]; then
  echo "==> Notarize (profile=${NOTARY_PROFILE})"
  ZIP_FOR_NOTARY="${DIST}/DriveLocalOpen-app-for-notary.zip"
  rm -f "$ZIP_FOR_NOTARY"
  ditto -c -k --keepParent "$APP" "$ZIP_FOR_NOTARY"
  xcrun notarytool submit "$ZIP_FOR_NOTARY" \
    --keychain-profile "$NOTARY_PROFILE" \
    --wait
  xcrun stapler staple "$APP"
  spctl --assess --type execute --verbose "$APP" || true
  rm -f "$ZIP_FOR_NOTARY"
else
  echo "==> Skip notarize (no Developer ID or SKIP_NOTARIZE=1)"
fi

echo "==> DMG"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
# Optional readme for Gatekeeper when unsigned
if [[ -z "${SIGN_IDENTITY}" ]]; then
  cat > "$STAGE/README.txt" <<'EOF'
Drive Local Open

1. 「Drive Local Open.app」を Applications へドラッグ
2. 初回は右クリック → 「開く」で許可（未署名ビルドの場合）
3. https://www.i-s3.com/tools/drive-local-open.html のブックマークレットを追加
EOF
fi

hdiutil create -volname "$VOL" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

(
  cd "$DIST"
  shasum -a 256 "$DMG_NAME" | tee "${DMG_NAME}.sha256"
)

echo "Wrote $DMG"
if [[ -z "${SIGN_IDENTITY}" ]]; then
  echo "NOTE: Enroll in Apple Developer Program, install Developer ID Application,"
  echo "      then re-run with SIGN_IDENTITY and notary profile for Gatekeeper-clean DMG."
fi
