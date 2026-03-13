#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — SSL Certificate Setup (Let's Encrypt via Certbot)
#
# Obtains an SSL certificate for www.danieltaehyunpark.com and configures
# automatic renewal.
#
# Usage: sudo bash setup_ssl.sh
# =============================================================================
set -euo pipefail

# ── Must run as root ────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
fi

DOMAIN="www.danieltaehyunpark.com"
EMAIL="${1:-admin@danieltaehyunpark.com}"

echo "============================================="
echo "  Bezalel.AI — SSL Certificate Setup"
echo "============================================="
echo ""

# ── 1. Install Certbot with Nginx plugin ───────────────────────────────────
echo "[1/4] Installing Certbot and Nginx plugin..."
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx
echo "  -> Certbot installed."

# ── 2. Obtain SSL certificate ──────────────────────────────────────────────
echo "[2/4] Obtaining SSL certificate for ${DOMAIN}..."
certbot certonly \
    --nginx \
    --non-interactive \
    --agree-tos \
    --email "${EMAIL}" \
    --domain "${DOMAIN}" \
    --redirect
echo "  -> Certificate obtained."

# ── 3. Set up auto-renewal cron job ────────────────────────────────────────
echo "[3/4] Configuring automatic renewal..."

# Certbot installs a systemd timer by default on Ubuntu 24.04;
# add a cron job as a fallback.
CRON_LINE="0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'"
(crontab -l 2>/dev/null | grep -v certbot; echo "${CRON_LINE}") | crontab -
echo "  -> Auto-renewal cron job added (daily at 3 AM)."

# ── 4. Test renewal ────────────────────────────────────────────────────────
echo "[4/4] Testing certificate renewal (dry run)..."
certbot renew --dry-run
echo "  -> Renewal dry run succeeded."

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  SSL Setup Complete!"
echo "============================================="
echo ""
echo "  Domain:      ${DOMAIN}"
echo "  Certificate: /etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
echo "  Private key: /etc/letsencrypt/live/${DOMAIN}/privkey.pem"
echo "  Renewal:     Automatic (cron + systemd timer)"
echo ""
echo "  Reload Nginx to apply the certificate:"
echo "    sudo systemctl reload nginx"
echo "============================================="
