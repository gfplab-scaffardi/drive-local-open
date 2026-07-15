#!/bin/zsh
# Build a source distribution zip for site / GitHub Releases.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c "import pathlib,re; t=pathlib.Path('$ROOT/pyproject.toml').read_text(); print(re.search(r'version\s*=\s*\"([^\"]+)\"', t).group(1))")"
NAME="drive-local-open-${VERSION}"
OUT="$ROOT/dist"
STAGE="$OUT/$NAME"
rm -rf "$STAGE"
mkdir -p "$STAGE"

rsync -a \
  --exclude '.git' \
  --exclude 'dist' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'tests' \
  "$ROOT/" "$STAGE/"

# Keep a short install note at zip root
cat > "$STAGE/INSTALL.txt" <<EOF
Drive Local Open ${VERSION}
https://www.i-s3.com/tools/drive-local-open.html

macOS:
  ./apps/macos/install_local.sh

Windows:
  apps\\windows\\register_protocol.bat

Requires: Python 3.10+ and Google Drive for Desktop.
EOF

mkdir -p "$OUT"
ZIP="$OUT/${NAME}.zip"
rm -f "$ZIP"
(cd "$OUT" && zip -rq "$ZIP" "$NAME")
rm -rf "$STAGE"
echo "Wrote $ZIP"
shasum -a 256 "$ZIP" | tee "$ZIP.sha256"
