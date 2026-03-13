#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — Server Provisioning Script (Ubuntu 24.04)
#
# Provisions a fresh Ubuntu 24.04 server with all dependencies and
# configuration needed to run the Bezalel.AI platform.
#
# Usage: sudo bash server_setup.sh
# =============================================================================
set -euo pipefail

# ── Must run as root ────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
fi

echo "============================================="
echo "  Bezalel.AI — Server Setup (Ubuntu 24.04)"
echo "============================================="
echo ""

# ── Configuration ───────────────────────────────────────────────────────────
DEPLOY_USER="bezalel"
PROJECT_DIR="/data/bezalel"
DB_NAME="bezalel"
DB_USER="bezalel"
DB_PASS=$(openssl rand -base64 24)  # Random password for PostgreSQL user

# ── 1. System updates ──────────────────────────────────────────────────────
echo "[1/12] Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget gnupg2 software-properties-common apt-transport-https \
    ca-certificates lsb-release build-essential unzip jq

# ── 2. Create non-root sudo user ───────────────────────────────────────────
echo "[2/12] Creating deploy user '${DEPLOY_USER}'..."
if ! id "${DEPLOY_USER}" &>/dev/null; then
    adduser --disabled-password --gecos "Bezalel Deploy" "${DEPLOY_USER}"
    usermod -aG sudo "${DEPLOY_USER}"
    # Allow passwordless sudo for deploy user
    echo "${DEPLOY_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${DEPLOY_USER}"
    chmod 0440 "/etc/sudoers.d/${DEPLOY_USER}"

    # Copy SSH authorized keys from root if they exist
    if [[ -f /root/.ssh/authorized_keys ]]; then
        mkdir -p "/home/${DEPLOY_USER}/.ssh"
        cp /root/.ssh/authorized_keys "/home/${DEPLOY_USER}/.ssh/"
        chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
        chmod 700 "/home/${DEPLOY_USER}/.ssh"
        chmod 600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"
    fi
    echo "  -> User '${DEPLOY_USER}' created."
else
    echo "  -> User '${DEPLOY_USER}' already exists, skipping."
fi

# ── 3. Harden SSH ──────────────────────────────────────────────────────────
echo "[3/12] Hardening SSH configuration..."
SSHD_CONFIG="/etc/ssh/sshd_config"
cp "${SSHD_CONFIG}" "${SSHD_CONFIG}.bak"

# Disable root login and password authentication
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' "${SSHD_CONFIG}"
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "${SSHD_CONFIG}"
sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' "${SSHD_CONFIG}"
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "${SSHD_CONFIG}"

systemctl restart sshd
echo "  -> Root SSH login disabled, key-only auth enforced."

# ── 4. Configure UFW firewall ──────────────────────────────────────────────
echo "[4/12] Configuring UFW firewall..."
apt-get install -y -qq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
ufw --force enable
echo "  -> UFW enabled (ports 22, 80, 443 open)."

# ── 5. Enable unattended upgrades ──────────────────────────────────────────
echo "[5/12] Enabling unattended security upgrades..."
apt-get install -y -qq unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades
echo "  -> Unattended upgrades enabled."

# ── 6. Set timezone ────────────────────────────────────────────────────────
echo "[6/12] Setting timezone to US/Eastern..."
timedatectl set-timezone US/Eastern
echo "  -> Timezone set to $(timedatectl show --property=Timezone --value)."

# ── 7. Install Node.js 20 LTS ──────────────────────────────────────────────
echo "[7/12] Installing Node.js 20 LTS..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y -qq nodejs
npm install -g pm2
echo "  -> Node.js $(node -v) and PM2 installed."

# ── 8. Install Python 3.11+ ────────────────────────────────────────────────
echo "[8/12] Installing Python 3.11+..."
add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
apt-get update -qq
apt-get install -y -qq python3.11 python3.11-venv python3.11-dev python3-pip
# Set python3.11 as default python3 if not already
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 2>/dev/null || true
echo "  -> Python $(python3.11 --version) installed."

# ── 9. Install PostgreSQL 16 ───────────────────────────────────────────────
echo "[9/12] Installing PostgreSQL 16..."
echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg
apt-get update -qq
apt-get install -y -qq postgresql-16 postgresql-client-16

# Create database and user
sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" 2>/dev/null || true
echo "  -> PostgreSQL 16 installed. Database '${DB_NAME}' created."

# ── 10. Install Nginx and Certbot ──────────────────────────────────────────
echo "[10/12] Installing Nginx and Certbot..."
apt-get install -y -qq nginx certbot python3-certbot-nginx
systemctl enable nginx
echo "  -> Nginx and Certbot installed."

# ── 11. Install Git ────────────────────────────────────────────────────────
echo "[11/12] Verifying Git installation..."
apt-get install -y -qq git
echo "  -> Git $(git --version) installed."

# ── 12. Set up project directories ─────────────────────────────────────────
echo "[12/12] Setting up project directories..."
mkdir -p "${PROJECT_DIR}"/{frontend,backend,backups,logs}

# Create Python virtual environment
python3.11 -m venv "${PROJECT_DIR}/backend/venv"

# Set ownership
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${PROJECT_DIR}"

# Set up PM2 startup script for the deploy user
env PATH=$PATH:/usr/bin pm2 startup systemd -u "${DEPLOY_USER}" --hp "/home/${DEPLOY_USER}"

echo "  -> Project directories created at ${PROJECT_DIR}."

# ── Completion summary ─────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  Server Setup Complete!"
echo "============================================="
echo ""
echo "  User:       ${DEPLOY_USER}"
echo "  Project:    ${PROJECT_DIR}"
echo "  Database:   ${DB_NAME}"
echo "  DB User:    ${DB_USER}"
echo "  DB Pass:    ${DB_PASS}"
echo ""
echo "  IMPORTANT: Save the database password above!"
echo "  Add it to your .env file as part of DATABASE_URL:"
echo "    postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
echo ""
echo "  Next steps:"
echo "    1. Log in as '${DEPLOY_USER}' and set up SSH keys"
echo "    2. Run setup_encryption.sh  (disk encryption)"
echo "    3. Run setup_ssl.sh         (SSL certificates)"
echo "    4. Run setup_tailscale.sh   (remote access)"
echo "    5. Run setup_cloudflare.sh  (DNS and proxy)"
echo "    6. Deploy the application with deploy.sh"
echo "============================================="
