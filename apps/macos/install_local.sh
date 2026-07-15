#!/bin/zsh
# Install Drive Local Open CLI into ~/.local/bin and refresh the macOS helper app.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$HOME/.local/bin"
chmod +x "$ROOT/bin/drive-local-open" "$ROOT/apps/macos/build_app.sh"
ln -sfn "$ROOT/bin/drive-local-open" "$HOME/.local/bin/drive-local-open"

# Backward-compatible helper (opens Terminal instead of Finder)
cat > "$HOME/.local/bin/google-drive-iterm" <<'EOF'
#!/bin/zsh
exec "$HOME/.local/bin/drive-local-open" --open terminal "$@"
EOF
chmod +x "$HOME/.local/bin/google-drive-iterm"

"$ROOT/apps/macos/build_app.sh"
echo "Installed: $HOME/.local/bin/drive-local-open"
echo "Compat:    $HOME/.local/bin/google-drive-iterm  (-> --open terminal)"
