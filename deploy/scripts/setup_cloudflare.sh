#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — Cloudflare DNS and Security Setup
#
# Configures Cloudflare DNS, proxy mode, SSL settings, and firewall rules
# using the Cloudflare API.
#
# Usage: bash setup_cloudflare.sh <API_TOKEN> <DOMAIN> <SERVER_IP>
#   API_TOKEN  — Cloudflare API token with DNS:Edit and Firewall:Edit perms
#   DOMAIN     — Root domain (e.g., danieltaehyunpark.com)
#   SERVER_IP  — Public IPv4 address of the server
# =============================================================================
set -euo pipefail

# ── Validate arguments ─────────────────────────────────────────────────────
if [[ $# -lt 3 ]]; then
    echo "Usage: $0 <API_TOKEN> <DOMAIN> <SERVER_IP>"
    echo "Example: $0 cf_token_abc123 danieltaehyunpark.com 203.0.113.50"
    exit 1
fi

CF_API_TOKEN="$1"
DOMAIN="$2"
SERVER_IP="$3"
CF_API="https://api.cloudflare.com/client/v4"

echo "============================================="
echo "  Bezalel.AI — Cloudflare Setup"
echo "============================================="
echo ""

# ── Helper: Cloudflare API request ──────────────────────────────────────────
cf_api() {
    local method="$1"
    local endpoint="$2"
    shift 2
    curl -s -X "${method}" \
        "${CF_API}${endpoint}" \
        -H "Authorization: Bearer ${CF_API_TOKEN}" \
        -H "Content-Type: application/json" \
        "$@"
}

# ── 1. Get Zone ID ─────────────────────────────────────────────────────────
echo "[1/4] Looking up zone ID for ${DOMAIN}..."
ZONE_RESPONSE=$(cf_api GET "/zones?name=${DOMAIN}")
ZONE_ID=$(echo "${ZONE_RESPONSE}" | jq -r '.result[0].id')

if [[ "${ZONE_ID}" == "null" || -z "${ZONE_ID}" ]]; then
    echo "ERROR: Could not find zone for domain '${DOMAIN}'."
    echo "       Make sure the domain is added to your Cloudflare account."
    exit 1
fi
echo "  -> Zone ID: ${ZONE_ID}"

# ── 2. Set A record for www subdomain ──────────────────────────────────────
echo "[2/4] Creating/updating DNS A record for www.${DOMAIN}..."

# Check if the record already exists
EXISTING=$(cf_api GET "/zones/${ZONE_ID}/dns_records?type=A&name=www.${DOMAIN}")
RECORD_ID=$(echo "${EXISTING}" | jq -r '.result[0].id // empty')

DNS_DATA=$(cat <<ENDJSON
{
    "type": "A",
    "name": "www",
    "content": "${SERVER_IP}",
    "ttl": 1,
    "proxied": true
}
ENDJSON
)

if [[ -n "${RECORD_ID}" ]]; then
    # Update existing record
    cf_api PUT "/zones/${ZONE_ID}/dns_records/${RECORD_ID}" -d "${DNS_DATA}" | jq -r '.success'
    echo "  -> A record updated (proxied)."
else
    # Create new record
    cf_api POST "/zones/${ZONE_ID}/dns_records" -d "${DNS_DATA}" | jq -r '.success'
    echo "  -> A record created (proxied)."
fi

# ── 3. Set SSL mode to Full (Strict) ──────────────────────────────────────
echo "[3/4] Setting SSL mode to Full (Strict)..."
cf_api PATCH "/zones/${ZONE_ID}/settings/ssl" \
    -d '{"value":"strict"}' | jq -r '.success'
echo "  -> SSL mode set to Full (Strict)."

# ── 4. Create firewall rule to block non-Cloudflare traffic ────────────────
echo "[4/4] Creating firewall rule (WAF custom rule)..."

# Create a WAF custom rule that blocks requests not going through CF proxy.
# Cloudflare automatically identifies these; this adds an extra layer via
# the "managed challenge" action for suspicious traffic.
RULE_DATA=$(cat <<'ENDJSON'
{
    "description": "Bezalel - Challenge non-standard requests",
    "expression": "(not cf.client.bot and cf.threat_score gt 14)",
    "action": "managed_challenge"
}
ENDJSON
)

# Use the Rulesets API (WAF Custom Rules)
RULESET_RESPONSE=$(cf_api GET "/zones/${ZONE_ID}/rulesets?kind=zone&phase=http_request_firewall_custom")
RULESET_ID=$(echo "${RULESET_RESPONSE}" | jq -r '.result[0].id // empty')

if [[ -n "${RULESET_ID}" ]]; then
    # Add rule to existing ruleset
    cf_api PATCH "/zones/${ZONE_ID}/rulesets/${RULESET_ID}" \
        -d "{\"rules\":[${RULE_DATA}]}" | jq -r '.success'
else
    # Create new ruleset with the rule
    cf_api POST "/zones/${ZONE_ID}/rulesets" \
        -d "{\"name\":\"Bezalel WAF\",\"kind\":\"zone\",\"phase\":\"http_request_firewall_custom\",\"rules\":[${RULE_DATA}]}" | jq -r '.success'
fi
echo "  -> Firewall rule created."

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  Cloudflare Setup Complete!"
echo "============================================="
echo ""
echo "  Domain:     www.${DOMAIN}"
echo "  A Record:   ${SERVER_IP} (proxied through Cloudflare)"
echo "  SSL Mode:   Full (Strict)"
echo "  Firewall:   Threat score challenge enabled"
echo ""
echo "  Additional recommended Cloudflare settings (manual):"
echo "  - Enable 'Always Use HTTPS'"
echo "  - Set Minimum TLS Version to 1.2"
echo "  - Enable HSTS in Cloudflare dashboard"
echo "  - Configure Page Rules as needed"
echo "============================================="
