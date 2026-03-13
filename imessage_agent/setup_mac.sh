#!/usr/bin/env bash
#
# Bezalel.AI iMessage Sync Agent - macOS Setup
#
# This script sets up the sync agent on the user's Mac:
#   1. Verifies Python 3 is available
#   2. Creates a virtual environment
#   3. Installs dependencies
#   4. Creates an env-file template
#   5. Installs and loads the launchd agent
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$HOME/.bezalel_venv"
AGENT_DIR="$HOME/.bezalel_agent"
ENV_FILE="$HOME/.bezalel_env"
PLIST_NAME="com.bezalel.imessagesync.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_FILE="$HOME/Library/Logs/bezalel_sync.log"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 1. Check Python 3 ───────────────────────────────────────────────────────
info "Checking for Python 3..."
if command -v python3 &>/dev/null; then
    PYTHON3="$(command -v python3)"
    PY_VERSION="$("$PYTHON3" --version 2>&1)"
    info "Found $PY_VERSION at $PYTHON3"
else
    error "Python 3 is not installed or not in PATH."
    echo "  Install it from https://www.python.org/downloads/ or via Homebrew:"
    echo "    brew install python@3"
    exit 1
fi

# Ensure Python version >= 3.10
PY_MINOR="$("$PYTHON3" -c 'import sys; print(sys.version_info.minor)')"
PY_MAJOR="$("$PYTHON3" -c 'import sys; print(sys.version_info.major)')"
if [[ "$PY_MAJOR" -lt 3 ]] || { [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 10 ]]; }; then
    error "Python 3.10 or newer is required (found $PY_VERSION)."
    exit 1
fi

# ── 2. Create virtual environment ───────────────────────────────────────────
info "Creating virtual environment at $VENV_DIR ..."
"$PYTHON3" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

info "Upgrading pip..."
pip install --upgrade pip --quiet

# ── 3. Install dependencies ─────────────────────────────────────────────────
info "Installing Python dependencies..."
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

# ── 4. Copy agent files to ~/.bezalel_agent ──────────────────────────────────
info "Copying agent files to $AGENT_DIR ..."
mkdir -p "$AGENT_DIR"
cp "$SCRIPT_DIR/bezalel_imessage_sync.py" "$AGENT_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$AGENT_DIR/"

# ── 5. Create env-file template ─────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    info "Creating environment file template at $ENV_FILE ..."
    cat > "$ENV_FILE" <<'ENVEOF'
# Bezalel.AI iMessage Sync - Environment Variables
# Fill in the values below and save this file.

# Long-lived master API key (obtain from Bezalel admin dashboard)
BEZALEL_MASTER_KEY=

# AES-256 encryption key (64 hex characters). Generate one with:
#   python3 -c "import os; print(os.urandom(32).hex())"
BEZALEL_ENCRYPTION_KEY=

# Server URL (default shown below)
BEZALEL_SERVER_URL=https://www.danieltaehyunpark.com
ENVEOF
    chmod 600 "$ENV_FILE"
    warn "You MUST edit $ENV_FILE and fill in your keys before the agent will work."
else
    info "Environment file already exists at $ENV_FILE -- skipping."
fi

# ── 6. Prepare and install launchd plist ─────────────────────────────────────
info "Installing launchd agent..."

PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

mkdir -p "$LAUNCH_AGENTS_DIR"

# Patch the template plist with actual user paths
sed \
    -e "s|/Users/USER/.bezalel_venv|$VENV_DIR|g" \
    -e "s|/Users/USER/.bezalel_agent|$AGENT_DIR|g" \
    -e "s|/Users/USER/Library/Logs|$HOME/Library/Logs|g" \
    -e "s|/Users/USER/.bezalel_env|$ENV_FILE|g" \
    "$PLIST_SRC" > "$PLIST_DST"

# Ensure the log file exists so launchd doesn't complain
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

# ── 7. Load the agent ───────────────────────────────────────────────────────
# Unload first (ignore errors if not loaded)
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
info "launchd agent loaded."

# ── 8. Summary ───────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Bezalel iMessage Sync Agent - Setup Complete"
echo "============================================================"
echo ""
echo "  Virtual environment : $VENV_DIR"
echo "  Agent scripts       : $AGENT_DIR"
echo "  Environment file    : $ENV_FILE"
echo "  launchd plist       : $PLIST_DST"
echo "  Log file            : $LOG_FILE"
echo ""
echo "  IMPORTANT next steps:"
echo ""
echo "  1. Edit $ENV_FILE and add your keys."
echo ""
echo "  2. Grant Full Disk Access to Python so it can read chat.db:"
echo "     System Settings > Privacy & Security > Full Disk Access"
echo "     Click '+' and add:  $VENV_DIR/bin/python3"
echo "     (You may also need to add /usr/bin/python3 or the"
echo "      Homebrew python binary if it delegates to one.)"
echo ""
echo "  3. Verify the agent is running:"
echo "     launchctl list | grep bezalel"
echo "     tail -f $LOG_FILE"
echo ""
echo "  4. To trigger a manual full sync:"
echo "     $VENV_DIR/bin/python3 $AGENT_DIR/bezalel_imessage_sync.py --full-sync"
echo ""
echo "============================================================"
