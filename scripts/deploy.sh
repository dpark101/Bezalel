#!/usr/bin/env bash
# deploy.sh — Push latest site files to the server
# Usage: bash scripts/deploy.sh <server-ip-or-hostname>
# Example: bash scripts/deploy.sh root@123.456.789.0

set -euo pipefail

DOMAIN="danieltaehyunpark.com"
WEBROOT="/var/www/${DOMAIN}"
SERVER="${1:-}"

if [[ -z "${SERVER}" ]]; then
  echo "Usage: $0 <user@server>"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Syncing site files to ${SERVER}:${WEBROOT} ..."
rsync -avz --delete \
  --exclude '.git' \
  --exclude 'scripts/' \
  --exclude 'nginx/' \
  "${REPO_ROOT}/" \
  "${SERVER}:${WEBROOT}/"

echo "==> Setting permissions..."
ssh "${SERVER}" "chown -R www-data:www-data ${WEBROOT} && chmod -R 755 ${WEBROOT}"

echo "==> Reloading Nginx..."
ssh "${SERVER}" "nginx -t && systemctl reload nginx"

echo ""
echo "Deployed to https://${DOMAIN}"
