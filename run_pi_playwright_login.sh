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
FULLSCREEN_MODE="${FULLSCREEN_MODE:-kiosk}"   # kiosk|maximized
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

install_pkgs() {
  # shellcheck disable=SC2068
  sudo apt-get update -y
  sudo apt-get install -y $@
}

log "WORKDIR: $WORKDIR"
log "LOG: $LOG_FILE"

log "Step: ensure base packages"
if ! need_cmd python3; then install_pkgs python3; fi
install_pkgs python3-venv python3-pip ca-certificates curl

log "Step: ensure Chromium installed"
if [[ -z "$CHROMIUM_PATH" ]]; then
  if need_cmd chromium-browser; then
    CHROMIUM_PATH="$(command -v chromium-browser)"
  elif need_cmd chromium; then
    CHROMIUM_PATH="$(command -v chromium)"
  else
    log "Chromium not found, installing..."
    if sudo apt-get install -y chromium-browser; then
      CHROMIUM_PATH="$(command -v chromium-browser)"
    else
      sudo apt-get install -y chromium
      CHROMIUM_PATH="$(command -v chromium)"
    fi
  fi
fi
log "Chromium path: $CHROMIUM_PATH"

# If no display, default to headless unless user explicitly set HEADLESS
if [[ "${DISPLAY:-}" == "" && "$HEADLESS" == "0" ]]; then
  log "No DISPLAY detected -> switching to HEADLESS=1"
  HEADLESS=1
fi

log "Step: create venv + install Python Playwright"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install --upgrade playwright

# Install system deps Playwright likes (safe even if already installed)
# This may install extra libs; comment out if you want minimal.
log "Step: install Playwright deps (may take a bit)"
python -m playwright install-deps chromium || true

log "Step: run automation"
python "$PWD/main.py" \
  --url "$URL" \
  --redirect-url "$REDIRECT_URL" \
  --username-placeholder "$USERNAME_PLACEHOLDER" \
  --password-selector "$PASSWORD_SELECTOR" \
  --login-button-text "$LOGIN_BUTTON_TEXT" \
  --wait-seconds "$WAIT_AFTER_LOGIN_SECONDS" \
  --fullscreen-mode "$FULLSCREEN_MODE" \
  --headless "$HEADLESS" \
  --chromium-path "$CHROMIUM_PATH" \
  --out-dir "$OUT_DIR" \
  --tab-switch-interval "$TAB_SWITCH_INTERVAL" \
  ${EXTRA_TAB_URLS:+--extra-tab-urls $EXTRA_TAB_URLS} | tee -a "$LOG_FILE"

log "DONE. Screenshot should be at: $OUT_DIR/after_redirect.png"
