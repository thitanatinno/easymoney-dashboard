#!/usr/bin/env bash
set -euo pipefail

# Load credentials and overrides from .env in the same directory as this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source <(grep -v '^\s*#' "$SCRIPT_DIR/.env" | grep -v '^\s*$')
  set +o allexport
fi

WORKDIR="${WORKDIR:-$PWD/pw_py_login}"
VENV_DIR="$WORKDIR/venv"
OUT_DIR="$WORKDIR/out"
LOG_DIR="$WORKDIR/logs"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/run_$TS.log"

URL="${URL:-https://www.hyxicloud.com}"
REDIRECT_URL="${REDIRECT_URL:-https://www.hyxicloud.com/#/dataWall}"
USERNAME_PLACEHOLDER="${USERNAME_PLACEHOLDER:-Login Account}"
PASSWORD_SELECTOR="${PASSWORD_SELECTOR:-input[name='password']}"
LOGIN_BUTTON_TEXT="${LOGIN_BUTTON_TEXT:-Login}"
WAIT_AFTER_LOGIN_SECONDS="${WAIT_AFTER_LOGIN_SECONDS:-30}"
HEADLESS="${HEADLESS:-0}"                     # 1=headless, 0=headful
CHROMIUM_PATH="${CHROMIUM_PATH:-}"            # optional override

# Tab-switching options:
TAB_SWITCH="${TAB_SWITCH:-true}"              # true=enable tab cycling, false=skip
EXTRA_TAB_URLS="${EXTRA_TAB_URLS:-}"          # space-separated extra tab URLs
TAB_SWITCH_INTERVAL="${TAB_SWITCH_INTERVAL:-300}"  # seconds between tab switches
export TAB_SWITCH

# Optional credentials via env (recommended) or prompted by Python:
#   export LOGIN_USER="..."
#   export LOGIN_PASS="..."

mkdir -p "$WORKDIR" "$OUT_DIR" "$LOG_DIR"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG_FILE" ; }

need_cmd() { command -v "$1" >/dev/null 2>&1; }
need_pkg()  { dpkg -s "$1" &>/dev/null 2>&1; }

install_pkgs() {
  sudo apt-get update -y
  sudo apt-get install -y "$@"
}

log "WORKDIR: $WORKDIR"
log "LOG: $LOG_FILE"

log "Step: ensure base packages"
if ! need_cmd python3; then install_pkgs python3; fi
MISSING_PKGS=()
need_pkg python3-venv    || MISSING_PKGS+=(python3-venv)
need_pkg python3-pip     || MISSING_PKGS+=(python3-pip)
need_pkg ca-certificates || MISSING_PKGS+=(ca-certificates)
need_cmd curl            || MISSING_PKGS+=(curl)
if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
  log "Installing missing base packages: ${MISSING_PKGS[*]}"
  install_pkgs "${MISSING_PKGS[@]}"
else
  log "Base packages already installed, skipping"
fi

log "Step: ensure system Chromium installed (fallback option)"
if ! need_cmd chromium-browser && ! need_cmd chromium; then
  log "System Chromium not found, installing..."
  if sudo apt-get install -y chromium-browser; then
    SYSTEM_CHROMIUM_PATH="$(command -v chromium-browser)"
  else
    sudo apt-get install -y chromium
    SYSTEM_CHROMIUM_PATH="$(command -v chromium)"
  fi
else
  if need_cmd chromium-browser; then
    SYSTEM_CHROMIUM_PATH="$(command -v chromium-browser)"
  else
    SYSTEM_CHROMIUM_PATH="$(command -v chromium)"
  fi
fi
log "System Chromium path: $SYSTEM_CHROMIUM_PATH"

log "Step: ensure Playwright bundled Chromium installed"
PLAYWRIGHT_CHROMIUM_FLAG="$WORKDIR/.playwright_chromium_installed"
if [[ ! -f "$PLAYWRIGHT_CHROMIUM_FLAG" ]]; then
  log "Installing Playwright bundled Chromium..."
  python -m playwright install chromium
  touch "$PLAYWRIGHT_CHROMIUM_FLAG"
else
  log "Playwright bundled Chromium already installed, skipping"
fi

# Load browser mode from .env
BROWSER_MODE="${BROWSER_MODE:-playwright-bundle}"
log "Browser mode: $BROWSER_MODE"

# Set chromium path based on mode
if [[ "$BROWSER_MODE" == "system-chromium" ]]; then
  CHROMIUM_PATH="$SYSTEM_CHROMIUM_PATH"
  log "Using system Chromium: $CHROMIUM_PATH"
else
  CHROMIUM_PATH=""  # Empty = use Playwright bundle
  log "Using Playwright bundled Chromium (no explicit path)"
fi

# If no display, default to headless unless user explicitly set HEADLESS
if [[ "${DISPLAY:-}" == "" && "$HEADLESS" == "0" ]]; then
  log "No DISPLAY detected -> switching to HEADLESS=1"
  HEADLESS=1
fi

log "Step: create venv + install Python Playwright"
if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# Only install pip build tools if any are missing
if ! python -c "import pip, setuptools, wheel" &>/dev/null 2>&1; then
  log "Installing pip build tools (pip/setuptools/wheel)..."
  python -m pip install --upgrade pip setuptools wheel
else
  log "pip build tools already present, skipping"
fi

# Only install Playwright if not already installed
if ! python -c "import playwright" &>/dev/null 2>&1; then
  log "Installing Playwright..."
  python -m pip install playwright
else
  log "Playwright already installed, skipping"
fi

# Install Playwright system deps only once (tracked via sentinel file)
PLAYWRIGHT_DEPS_FLAG="$WORKDIR/.playwright_deps_installed"
if [[ ! -f "$PLAYWRIGHT_DEPS_FLAG" ]]; then
  log "Step: install Playwright system deps (may take a bit)"
  python -m playwright install-deps chromium || true
  touch "$PLAYWRIGHT_DEPS_FLAG"
else
  log "Playwright system deps already installed, skipping"
fi

log "Step: run automation"
python "$PWD/main.py" \
  --url "$URL" \
  --redirect-url "$REDIRECT_URL" \
  --username-placeholder "$USERNAME_PLACEHOLDER" \
  --password-selector "$PASSWORD_SELECTOR" \
  --login-button-text "$LOGIN_BUTTON_TEXT" \
  --wait-seconds "$WAIT_AFTER_LOGIN_SECONDS" \
  --headless "$HEADLESS" \
  --chromium-path "$CHROMIUM_PATH" \
  --out-dir "$OUT_DIR" \
  --tab-switch-interval "$TAB_SWITCH_INTERVAL" \
  ${EXTRA_TAB_URLS:+--extra-tab-urls $EXTRA_TAB_URLS} | tee -a "$LOG_FILE"

log "DONE. Screenshot should be at: $OUT_DIR/after_redirect.png"
