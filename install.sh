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

say "Installing Chromium browser dependencies..."
"$INSTALL_DIR/.venv/bin/python" -m playwright install chromium

# Install system shared libraries Chromium needs to launch headlessly.
install_sys_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    say "Installing system libraries via apt (may require sudo)..."
    sudo apt-get update -qq 2>/dev/null || true
    sudo apt-get install -y -qq \
      libatk1.0-0 libatk-bridge2.0-0 libasound2t64 libgbm-dev libgtk-3-0 \
      libnss3 libxss1 libxtst6 libxrandr2 libatspi2.0-0 libxcomposite1 \
      libxdamage1 libxfixes3 libxkbcommon0 libx11-xcb1 libxcb-dri3-0 \
      libxcb-xfixes0 libxcb-randr0 libxcb-shm0 libcups2 libdrm2 \
      libpango-1.0-0 libpangocairo-1.0-0
  elif command -v apk >/dev/null 2>&1; then
    say "Installing system libraries via apk (may require sudo)..."
    sudo apk add --no-cache \
      atk atk-bridge cairo gdk-pixbuf gtk+3.0 libxcomposite libxcursor \
      libxdamage libxi libxtst nss pango udev xorg-server
  elif command -v dnf >/dev/null 2>&1; then
    say "Installing system libraries via dnf (may require sudo)..."
    sudo dnf install -y \
      atk atk-bridge cairo gdk-pixbuf2 gtk3 libXcomposite libXcursor \
      libXdamage libXi libXtst nss pango xorg-x11-server-Xorg
  elif command -v yum >/dev/null 2>&1; then
    say "Installing system libraries via yum (may require sudo)..."
    sudo yum install -y \
      atk atk-bridge cairo gdk-pixbuf2 gtk3 libXcomposite libXcursor \
      libXdamage libXi libXtst nss pango xorg-x11-server-Xorg
  elif command -v pacman >/dev/null 2>&1; then
    say "Installing system libraries via pacman (may require sudo)..."
    sudo pacman -S --needed --noconfirm \
      atk at-spi2-core cairo gdk-pixbuf2 gtk3 libxcomposite libxcursor \
      libxdamage libxi libxtst nss pango xorg-server
  elif command -v brew >/dev/null 2>&1; then
    say "Installing Chromium via brew (may require sudo)..."
    brew install chromium
  else
    say "No supported package manager found. Chromium system libraries must be installed manually."
  fi
}

install_sys_deps || say "WARNING: system library install may have failed; Zap may not launch without them."

# Verify Chromium can launch.
say "Verifying Chromium launches..."
if ! "$INSTALL_DIR/.venv/bin/python" -c "
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
    pw = await async_playwright().start()
    try:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(Path('/tmp/zap-verify-profile')),
            headless=True, viewport={'width': 800, 'height': 600},
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        await ctx.close()
    except Exception as e:
        print('CHROMIUM_CHECK_FAILED:', e)
        sys.exit(1)
    finally:
        await pw.stop()
asyncio.run(main())
" 2>/dev/null; then
  say "WARNING: Chromium could not launch. Zap may show 'ENGINE ERROR'."
  say "Install the missing system libraries manually (see install.sh for the package list)."
else
  say "Chromium launches successfully."
fi

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
