#!/usr/bin/env bash
set -euo pipefail

# ZAP installer for the public Quit4859/zap-terminal repository.
REPO_URL="${ZAP_REPO_URL:-https://github.com/Quit4859/zap-terminal.git}"
BRANCH="${ZAP_BRANCH:-main}"
INSTALL_DIR="${ZAP_INSTALL_DIR:-$HOME/.local/share/zap}"
BIN_DIR="${ZAP_BIN_DIR:-$HOME/.local/bin}"

say() { printf '\033[1;38;5;208m[ZAP]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[ZAP ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

case "$REPO_URL" in
  *"OWNER/REPO"*) fail "Installer is not configured yet. Set REPO_URL in install.sh to your GitHub repository." ;;
esac

command -v git >/dev/null 2>&1 || fail "Git is required. Install Git and rerun this command."
PYTHON="$(command -v python3 || command -v python || true)"
[ -n "$PYTHON" ] || fail "Python 3.10+ is required."

"$PYTHON" - <<'PY' || fail "ZAP requires Python 3.10 or newer."
import sys
if sys.version_info < (3, 10):
    raise SystemExit(1)
PY

if [ -d "$INSTALL_DIR/.git" ]; then
  say "ZAP is already installed at $INSTALL_DIR"
  say "Checking for updates..."
  git -C "$INSTALL_DIR" fetch --quiet origin "$BRANCH"
  LOCAL="$(git -C "$INSTALL_DIR" rev-parse @)"
  REMOTE="$(git -C "$INSTALL_DIR" rev-parse "@{u}")"
  if [ "$LOCAL" = "$REMOTE" ]; then
    say "ZAP is already up to date."
  else
    say "Update available. Updating ZAP..."
    git -C "$INSTALL_DIR" checkout --quiet "$BRANCH"
    git -C "$INSTALL_DIR" reset --hard --quiet "origin/$BRANCH"
  fi
else
  say "Installing ZAP into $INSTALL_DIR"
  mkdir -p "$(dirname "$INSTALL_DIR")" "$BIN_DIR"
  if [ -e "$INSTALL_DIR" ]; then
    fail "$INSTALL_DIR exists but is not a Git repository. Move it and rerun."
  fi
  git clone --quiet --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
"$PYTHON" -m venv .venv
"$INSTALL_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/python" -m pip install --quiet -e .
"$INSTALL_DIR/.venv/bin/python" -m playwright install chromium

cat > "$BIN_DIR/zap" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/.venv/bin/zap" "\$@"
EOF
chmod +x "$BIN_DIR/zap"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "Add $BIN_DIR to PATH. For Bash/Zsh, run:"
     printf '  echo '\''export PATH="%s:$PATH"'\'' >> ~/.bashrc\n' "$BIN_DIR"
     printf '  source ~/.bashrc\n'
     ;;
esac

say "Installation complete."
say "Start ZAP by running: zap"
