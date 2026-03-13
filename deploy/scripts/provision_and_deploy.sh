#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — One-Shot Server Provisioning & Deployment
#
# Provisions a fresh Hetzner Ubuntu VPS from scratch and deploys the full
# Bezalel.AI platform (PostgreSQL, FastAPI backend, Next.js frontend, Nginx).
#
# Usage:  sudo bash provision_and_deploy.sh
#
# IMPORTANT: Run this as root on your fresh Hetzner VPS.
# =============================================================================
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
DOMAIN="www.danieltaehyunpark.com"
REPO_URL="https://github.com/dpark101/Bezalel.git"
BRANCH="claude/build-bezalel-ai-V4OYg"
PROJECT_DIR="/data/bezalel"
DEPLOY_USER="bezalel"
DB_NAME="bezalel"
DB_USER="bezalel"
DB_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
SECRET_KEY=$(openssl rand -hex 64)
FERNET_KEY=""  # generated below with python

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

# ── Must run as root ─────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root."
    exit 1
fi

echo ""
echo "============================================="
echo "  Bezalel.AI — Full Server Provisioning"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================="
echo ""

# =============================================================================
# PHASE 1: System packages
# =============================================================================
echo "── Phase 1: System Packages ──────────────────"

echo "Updating system..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget gnupg2 software-properties-common apt-transport-https \
    ca-certificates lsb-release build-essential unzip jq git
log "System updated and base packages installed."

# ── Firewall ─────────────────────────────────────────────────────────────────
apt-get install -y -qq ufw
ufw default deny incoming 2>/dev/null || true
ufw default allow outgoing 2>/dev/null || true
ufw allow 22/tcp comment "SSH" 2>/dev/null || true
ufw allow 80/tcp comment "HTTP" 2>/dev/null || true
ufw allow 443/tcp comment "HTTPS" 2>/dev/null || true
ufw --force enable 2>/dev/null || true
log "UFW firewall configured (22, 80, 443)."

# ── Timezone ─────────────────────────────────────────────────────────────────
timedatectl set-timezone US/Eastern 2>/dev/null || true
log "Timezone set to US/Eastern."

# =============================================================================
# PHASE 2: Install Node.js 20 LTS
# =============================================================================
echo ""
echo "── Phase 2: Node.js ──────────────────────────"

if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi
npm install -g pm2 2>/dev/null
log "Node.js $(node -v) and PM2 installed."

# =============================================================================
# PHASE 3: Install Python 3.11+
# =============================================================================
echo ""
echo "── Phase 3: Python ───────────────────────────"

if ! command -v python3.11 &>/dev/null; then
    add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev python3-pip
fi
log "Python $(python3.11 --version 2>&1) installed."

# =============================================================================
# PHASE 4: Install PostgreSQL 16
# =============================================================================
echo ""
echo "── Phase 4: PostgreSQL ───────────────────────"

if ! command -v psql &>/dev/null || ! psql --version 2>/dev/null | grep -q "16"; then
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg 2>/dev/null
    apt-get update -qq
    apt-get install -y -qq postgresql-16 postgresql-client-16
fi

# Ensure PostgreSQL is running.
systemctl enable postgresql
systemctl start postgresql

# Create database and user (idempotent).
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" \
    | grep -q 1 || sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" \
    | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" 2>/dev/null || true
log "PostgreSQL 16 running. Database '${DB_NAME}' ready."

# =============================================================================
# PHASE 5: Install Nginx
# =============================================================================
echo ""
echo "── Phase 5: Nginx ────────────────────────────"

apt-get install -y -qq nginx certbot python3-certbot-nginx
systemctl enable nginx
log "Nginx and Certbot installed."

# =============================================================================
# PHASE 6: Create project structure & clone repo
# =============================================================================
echo ""
echo "── Phase 6: Clone Repository ─────────────────"

mkdir -p "${PROJECT_DIR}" /data/backups

if [[ -d "${PROJECT_DIR}/.git" ]]; then
    cd "${PROJECT_DIR}"
    git fetch origin "${BRANCH}"
    git checkout "${BRANCH}"
    git pull origin "${BRANCH}"
    log "Repository updated on branch ${BRANCH}."
else
    cd /tmp
    rm -rf bezalel-clone
    git clone --branch "${BRANCH}" "${REPO_URL}" bezalel-clone
    # Move contents into project dir (preserving .git).
    cp -a bezalel-clone/. "${PROJECT_DIR}/"
    rm -rf bezalel-clone
    log "Repository cloned to ${PROJECT_DIR}."
fi

mkdir -p "${PROJECT_DIR}/logs"

# =============================================================================
# PHASE 7: Python virtual environment & backend dependencies
# =============================================================================
echo ""
echo "── Phase 7: Backend Setup ────────────────────"

VENV="${PROJECT_DIR}/backend/venv"
if [[ ! -d "${VENV}" ]]; then
    python3.11 -m venv "${VENV}"
fi

source "${VENV}/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "${PROJECT_DIR}/backend/requirements.txt"
deactivate
log "Python venv created and dependencies installed."

# =============================================================================
# PHASE 8: Generate .env file
# =============================================================================
echo ""
echo "── Phase 8: Environment Configuration ────────"

# Generate Fernet key using the venv's python.
FERNET_KEY=$("${VENV}/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

ENV_FILE="${PROJECT_DIR}/backend/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    cat > "${ENV_FILE}" << ENVEOF
# =============================================================================
# Bezalel.AI — Production Environment Variables
# Generated on $(date '+%Y-%m-%d %H:%M:%S')
# =============================================================================

# ── Database ─────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}

# ── Authentication / JWT ─────────────────────────────────────────────────
SECRET_KEY=${SECRET_KEY}
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24
MAX_FAILED_LOGINS=5
LOCKOUT_MINUTES=30

# ── SMTP (disabled — fill in later) ─────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@bezalel.ai
SMTP_USE_TLS=true

# ── Google OAuth (fill in later) ─────────────────────────────────────────
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://${DOMAIN}/api/auth/google/callback

# ── Microsoft OAuth (fill in later) ──────────────────────────────────────
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_REDIRECT_URI=https://${DOMAIN}/api/auth/microsoft/callback
MICROSOFT_TENANT_ID=common

# ── Anthropic AI (fill in later) ─────────────────────────────────────────
ANTHROPIC_API_KEY=

# ── iMessage Bridge ──────────────────────────────────────────────────────
IMESSAGE_MASTER_KEY=

# ── Encryption ───────────────────────────────────────────────────────────
ENCRYPTION_KEY=${FERNET_KEY}

# ── Frontend Origin (CORS) ───────────────────────────────────────────────
FRONTEND_ORIGIN=https://${DOMAIN}
ENVEOF
    log ".env file generated with auto-generated secrets."
else
    warn ".env file already exists — skipping generation."
fi

# =============================================================================
# PHASE 9: Set up Alembic & run database migrations
# =============================================================================
echo ""
echo "── Phase 9: Database Migrations ──────────────"

BACKEND_DIR="${PROJECT_DIR}/backend"

# Copy alembic config into backend directory (where deploy.sh expects it).
cp "${PROJECT_DIR}/deploy/alembic.ini" "${BACKEND_DIR}/alembic.ini"
cp -r "${PROJECT_DIR}/deploy/alembic" "${BACKEND_DIR}/alembic"
mkdir -p "${BACKEND_DIR}/alembic/versions"

# Generate initial migration and apply.
cd "${BACKEND_DIR}"
source "${VENV}/bin/activate"
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
deactivate
log "Database schema created via Alembic."

# =============================================================================
# PHASE 10: Build Next.js frontend
# =============================================================================
echo ""
echo "── Phase 10: Frontend Build ──────────────────"

cd "${PROJECT_DIR}/frontend"
npm ci --silent 2>&1 | tail -1
npm run build
log "Next.js frontend built."

# =============================================================================
# PHASE 11: Configure Nginx (direct access, no Cloudflare initially)
# =============================================================================
echo ""
echo "── Phase 11: Nginx Configuration ─────────────"

# Write a direct-access nginx config (no Cloudflare IP filtering) for initial
# setup. Once Cloudflare is configured, swap in the full bezalel.conf.
cat > /etc/nginx/sites-available/bezalel << 'NGINXEOF'
# Bezalel.AI — Nginx (direct access mode, pre-Cloudflare)

# Rate-limiting zones
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=1r/s;
limit_req_zone $binary_remote_addr zone=general:10m rate=2r/s;

upstream nextjs_frontend {
    server 127.0.0.1:3000;
    keepalive 32;
}

upstream fastapi_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

# HTTP server (will be updated by Certbot for HTTPS)
server {
    listen 80;
    listen [::]:80;
    server_name www.danieltaehyunpark.com danieltaehyunpark.com;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 256;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml
               application/rss+xml image/svg+xml;

    client_max_body_size 10M;

    # FastAPI backend
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # Rate-limited login
    location /api/auth/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://fastapi_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
    }

    # Next.js frontend
    location / {
        limit_req zone=general burst=40 nodelay;
        proxy_pass http://nextjs_frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
    }

    # Next.js static assets
    location /_next/static/ {
        proxy_pass http://nextjs_frontend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        expires 365d;
        add_header Cache-Control "public, immutable";
    }

    # Deny hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
NGINXEOF

# Enable the site.
ln -sf /etc/nginx/sites-available/bezalel /etc/nginx/sites-enabled/bezalel
rm -f /etc/nginx/sites-enabled/default

# Test and reload.
nginx -t && systemctl reload nginx
log "Nginx configured for ${DOMAIN}."

# =============================================================================
# PHASE 12: SSL Certificate (Let's Encrypt)
# =============================================================================
echo ""
echo "── Phase 12: SSL Certificate ─────────────────"

# Only attempt SSL if DNS is pointing to this server.
SERVER_IP=$(curl -s4 ifconfig.me || echo "unknown")
DNS_IP=$(dig +short "${DOMAIN}" 2>/dev/null | head -1 || echo "none")

if [[ "${DNS_IP}" == "${SERVER_IP}" ]]; then
    certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos \
        --email "admin@danieltaehyunpark.com" --redirect
    log "SSL certificate obtained and installed."
else
    warn "DNS for ${DOMAIN} (${DNS_IP}) does not point to this server (${SERVER_IP})."
    warn "Skipping SSL. After pointing DNS, run:"
    warn "  certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos --email admin@danieltaehyunpark.com --redirect"
fi

# =============================================================================
# PHASE 13: Start services with PM2
# =============================================================================
echo ""
echo "── Phase 13: Start Services ──────────────────"

# Start PM2 processes.
cd "${PROJECT_DIR}"
pm2 start deploy/pm2/ecosystem.config.js
pm2 save

# Set up PM2 startup (so it survives reboots).
pm2 startup systemd -u root --hp /root 2>/dev/null || true
pm2 save

log "PM2 processes started."

# Wait for services to come up.
sleep 5

# ── Verify ───────────────────────────────────────────────────────────────────
echo ""
echo "── Verification ──────────────────────────────"

FRONTEND_OK=false
BACKEND_OK=false

if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    FRONTEND_OK=true
    log "Frontend (localhost:3000) — UP"
else
    err "Frontend (localhost:3000) — DOWN"
fi

if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    BACKEND_OK=true
    log "Backend  (localhost:8000) — UP"
else
    err "Backend  (localhost:8000) — DOWN"
fi

echo ""
pm2 status

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "============================================="
echo "  Bezalel.AI — Provisioning Complete!"
echo "============================================="
echo ""
echo "  Server IP:    ${SERVER_IP}"
echo "  Domain:       ${DOMAIN}"
echo "  Branch:       ${BRANCH}"
echo ""
echo "  Database:     ${DB_NAME}"
echo "  DB User:      ${DB_USER}"
echo "  DB Password:  ${DB_PASS}"
echo ""
echo "  Project dir:  ${PROJECT_DIR}"
echo "  Backend .env: ${ENV_FILE}"
echo ""

if [[ "${FRONTEND_OK}" == "true" && "${BACKEND_OK}" == "true" ]]; then
    log "All services running!"
else
    warn "Some services may not be running. Check: pm2 logs"
fi

echo ""
echo "  SAVE THE DATABASE PASSWORD ABOVE!"
echo ""
echo "  Next steps:"
echo "    1. Point DNS for ${DOMAIN} → ${SERVER_IP}"
echo "    2. Run:  certbot --nginx -d ${DOMAIN} (if SSL was skipped)"
echo "    3. Fill in SMTP/OAuth/Anthropic keys in ${ENV_FILE}"
echo "    4. Change your root password:  passwd"
echo ""
echo "============================================="
