#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — Deployment Script
#
# Pulls latest code, installs dependencies, builds the frontend, runs
# database migrations, and restarts services.
#
# Usage: bash deploy.sh [--skip-build] [--skip-migrate]
# =============================================================================
set -euo pipefail

PROJECT_DIR="/data/bezalel"
FRONTEND_DIR="${PROJECT_DIR}/frontend"
BACKEND_DIR="${PROJECT_DIR}/backend"
VENV="${BACKEND_DIR}/venv"

# ── Parse flags ─────────────────────────────────────────────────────────────
SKIP_BUILD=false
SKIP_MIGRATE=false
for arg in "$@"; do
    case "${arg}" in
        --skip-build)   SKIP_BUILD=true ;;
        --skip-migrate) SKIP_MIGRATE=true ;;
    esac
done

echo "============================================="
echo "  Bezalel.AI — Deployment"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================="
echo ""

# ── 1. Pull latest code ────────────────────────────────────────────────────
echo "[1/6] Pulling latest code..."
cd "${PROJECT_DIR}"
if [[ -d .git ]]; then
    git pull --ff-only
    echo "  -> Code updated."
else
    echo "  -> Not a git repo, skipping pull."
fi

# ── 2. Install/update Python dependencies ──────────────────────────────────
echo "[2/6] Installing Python dependencies..."
source "${VENV}/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "${BACKEND_DIR}/requirements.txt"
deactivate
echo "  -> Python dependencies updated."

# ── 3. Install/update Node.js dependencies ─────────────────────────────────
echo "[3/6] Installing Node.js dependencies..."
cd "${FRONTEND_DIR}"
npm ci --silent
echo "  -> Node.js dependencies updated."

# ── 4. Build Next.js frontend ──────────────────────────────────────────────
if [[ "${SKIP_BUILD}" == "false" ]]; then
    echo "[4/6] Building Next.js frontend..."
    npm run build
    echo "  -> Frontend built."
else
    echo "[4/6] Skipping frontend build (--skip-build)."
fi

# ── 5. Run database migrations ─────────────────────────────────────────────
if [[ "${SKIP_MIGRATE}" == "false" ]]; then
    echo "[5/6] Running database migrations..."
    cd "${BACKEND_DIR}"
    source "${VENV}/bin/activate"
    alembic upgrade head
    deactivate
    echo "  -> Migrations complete."
else
    echo "[5/6] Skipping migrations (--skip-migrate)."
fi

# ── 6. Restart PM2 processes ───────────────────────────────────────────────
echo "[6/6] Restarting services..."
pm2 reload ecosystem.config.js --update-env 2>/dev/null \
    || pm2 start "${PROJECT_DIR}/deploy/pm2/ecosystem.config.js"
pm2 save
echo "  -> Services restarted."

# ── Verify services ────────────────────────────────────────────────────────
echo ""
echo "Verifying services..."
sleep 3

FRONTEND_OK=false
BACKEND_OK=false

# Check frontend
if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    FRONTEND_OK=true
    echo "  [OK] Frontend (localhost:3000)"
else
    echo "  [FAIL] Frontend (localhost:3000)"
fi

# Check backend
if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
    BACKEND_OK=true
    echo "  [OK] Backend (localhost:8000)"
else
    echo "  [FAIL] Backend (localhost:8000)"
fi

echo ""
if [[ "${FRONTEND_OK}" == "true" && "${BACKEND_OK}" == "true" ]]; then
    echo "Deployment successful!"
else
    echo "WARNING: One or more services may not be running correctly."
    echo "Check logs with: pm2 logs"
fi

echo ""
pm2 status
echo ""
echo "============================================="
echo "  Deployment complete at $(date '+%H:%M:%S')"
echo "============================================="
