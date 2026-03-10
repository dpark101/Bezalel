#!/usr/bin/env bash
# setup.sh — One-time server setup for danieltaehyunpark.com on Ubuntu 24.04
# Run as root or with sudo: sudo bash setup.sh

set -euo pipefail

DOMAIN="danieltaehyunpark.com"
WEBROOT="/var/www/${DOMAIN}"
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"
EMAIL="danieltaehyunpark@gmail.com"

echo "==> Updating packages..."
apt-get update -qq
apt-get upgrade -y -qq

echo "==> Installing Nginx and Certbot..."
apt-get install -y nginx certbot python3-certbot-nginx

echo "==> Creating web root..."
mkdir -p "${WEBROOT}"

echo "==> Copying site files..."
cp "$(dirname "$0")/../index.html" "${WEBROOT}/index.html"
chown -R www-data:www-data "${WEBROOT}"
chmod -R 755 "${WEBROOT}"

echo "==> Installing Nginx config..."
cp "$(dirname "$0")/../nginx/${DOMAIN}" "${NGINX_CONF}"

# Temporarily use HTTP-only config for cert issuance
cat > "${NGINX_CONF}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};
    root ${WEBROOT};
    index index.html;
    location / { try_files \$uri \$uri/ =404; }
}
EOF

ln -sf "${NGINX_CONF}" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

echo "==> Testing Nginx config..."
nginx -t

echo "==> Starting / reloading Nginx..."
systemctl enable nginx
systemctl restart nginx

echo "==> Obtaining SSL certificate..."
certbot --nginx \
    -d "${DOMAIN}" \
    -d "www.${DOMAIN}" \
    --non-interactive \
    --agree-tos \
    --email "${EMAIL}" \
    --redirect

echo "==> Installing final Nginx config with security headers..."
cp "$(dirname "$0")/../nginx/${DOMAIN}" "${NGINX_CONF}"
nginx -t && systemctl reload nginx

echo "==> Enabling Certbot auto-renewal..."
systemctl enable certbot.timer
systemctl start certbot.timer

echo ""
echo "Done! Site is live at https://${DOMAIN}"
