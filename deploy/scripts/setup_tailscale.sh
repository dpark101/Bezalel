#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — Tailscale VPN Setup
#
# Installs Tailscale for secure remote access to the server without exposing
# SSH to the public internet (beyond Cloudflare).
#
# Usage: sudo bash setup_tailscale.sh
# =============================================================================
set -euo pipefail

# ── Must run as root ────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
fi

echo "============================================="
echo "  Bezalel.AI — Tailscale Setup"
echo "============================================="
echo ""

# ── 1. Install Tailscale ───────────────────────────────────────────────────
echo "[1/3] Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh
echo "  -> Tailscale installed."

# ── 2. Start Tailscale and authenticate ────────────────────────────────────
echo "[2/3] Starting Tailscale..."
echo ""
echo "  A browser URL will appear below. Open it to authenticate this device"
echo "  with your Tailscale account."
echo ""
tailscale up
echo ""
echo "  -> Tailscale authenticated."
echo "  -> Tailscale IP: $(tailscale ip -4)"

# ── 3. Configure UFW to allow Tailscale traffic ───────────────────────────
echo "[3/3] Configuring UFW for Tailscale..."

# Allow all traffic on the Tailscale interface
ufw allow in on tailscale0
ufw allow out on tailscale0

# Allow Tailscale's UDP port for direct connections
ufw allow 41641/udp comment "Tailscale direct"

ufw reload
echo "  -> UFW updated to allow Tailscale traffic."

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  Tailscale Setup Complete!"
echo "============================================="
echo ""
echo "  Tailscale IP: $(tailscale ip -4)"
echo "  Status:       $(tailscale status --self --peers=false)"
echo ""
echo "  To access this server from another device:"
echo "  ──────────────────────────────────────────"
echo "  1. Install Tailscale on your local machine:"
echo "     - macOS:   brew install tailscale"
echo "     - Linux:   curl -fsSL https://tailscale.com/install.sh | sh"
echo "     - Windows: https://tailscale.com/download/windows"
echo "     - iOS/Android: Install from App Store / Play Store"
echo ""
echo "  2. Run 'tailscale up' and log in with the same account."
echo ""
echo "  3. SSH using the Tailscale IP:"
echo "     ssh bezalel@$(tailscale ip -4)"
echo ""
echo "  4. (Optional) Enable MagicDNS in the Tailscale admin console"
echo "     to SSH by hostname instead of IP."
echo "============================================="
