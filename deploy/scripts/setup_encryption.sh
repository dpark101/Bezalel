#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — LUKS Disk Encryption Setup
#
# Creates an encrypted LUKS volume for storing sensitive application data.
# The volume is mounted at /data and configured for automatic unlock on boot
# using a keyfile.
#
# Usage: sudo bash setup_encryption.sh /dev/sdX
#   where /dev/sdX is the block device to encrypt.
#
# WARNING: This will DESTROY all data on the specified device!
# =============================================================================
set -euo pipefail

# ── Must run as root ────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)."
    exit 1
fi

# ── Validate arguments ─────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <device>"
    echo "Example: $0 /dev/sdb"
    exit 1
fi

DEVICE="$1"
CRYPT_NAME="bezalel_data"
MOUNT_POINT="/data"
KEYFILE="/root/.bezalel_keyfile"

# ── Safety check ────────────────────────────────────────────────────────────
if [[ ! -b "${DEVICE}" ]]; then
    echo "ERROR: '${DEVICE}' is not a valid block device."
    exit 1
fi

echo "============================================="
echo "  Bezalel.AI — LUKS Encryption Setup"
echo "============================================="
echo ""
echo "  Device:      ${DEVICE}"
echo "  Mapper:      /dev/mapper/${CRYPT_NAME}"
echo "  Mount point: ${MOUNT_POINT}"
echo ""
echo "  WARNING: ALL DATA ON ${DEVICE} WILL BE DESTROYED!"
echo ""
read -rp "  Type 'YES' to continue: " CONFIRM
if [[ "${CONFIRM}" != "YES" ]]; then
    echo "Aborted."
    exit 1
fi

# ── Install cryptsetup if needed ────────────────────────────────────────────
apt-get install -y -qq cryptsetup

# ── 1. Format device with LUKS ─────────────────────────────────────────────
echo "[1/6] Formatting ${DEVICE} with LUKS encryption..."
cryptsetup luksFormat --type luks2 --cipher aes-xts-plain64 --key-size 512 \
    --hash sha256 --iter-time 5000 "${DEVICE}"
echo "  -> LUKS volume created."

# ── 2. Open the encrypted volume ───────────────────────────────────────────
echo "[2/6] Opening encrypted volume..."
cryptsetup open "${DEVICE}" "${CRYPT_NAME}"
echo "  -> Volume opened as /dev/mapper/${CRYPT_NAME}."

# ── 3. Create ext4 filesystem ──────────────────────────────────────────────
echo "[3/6] Creating ext4 filesystem..."
mkfs.ext4 -L bezalel_data "/dev/mapper/${CRYPT_NAME}"
echo "  -> ext4 filesystem created."

# ── 4. Generate keyfile for automatic unlock ────────────────────────────────
echo "[4/6] Generating keyfile at ${KEYFILE}..."
dd if=/dev/urandom of="${KEYFILE}" bs=4096 count=1 status=none
chmod 0400 "${KEYFILE}"
chown root:root "${KEYFILE}"

# Add keyfile as an additional LUKS key slot
cryptsetup luksAddKey "${DEVICE}" "${KEYFILE}"
echo "  -> Keyfile created and added to LUKS."

# ── 5. Configure /etc/crypttab for auto-unlock ─────────────────────────────
echo "[5/6] Configuring /etc/crypttab and /etc/fstab..."

# Get the UUID of the LUKS device
DEVICE_UUID=$(blkid -s UUID -o value "${DEVICE}")

# Add to crypttab (auto-unlock with keyfile on boot)
if ! grep -q "${CRYPT_NAME}" /etc/crypttab 2>/dev/null; then
    echo "${CRYPT_NAME} UUID=${DEVICE_UUID} ${KEYFILE} luks" >> /etc/crypttab
fi

# Add to fstab (auto-mount on boot)
mkdir -p "${MOUNT_POINT}"
if ! grep -q "${CRYPT_NAME}" /etc/fstab 2>/dev/null; then
    echo "/dev/mapper/${CRYPT_NAME} ${MOUNT_POINT} ext4 defaults,noatime 0 2" >> /etc/fstab
fi

echo "  -> crypttab and fstab configured."

# ── 6. Mount the volume ────────────────────────────────────────────────────
echo "[6/6] Mounting encrypted volume at ${MOUNT_POINT}..."
mount "${MOUNT_POINT}"
echo "  -> Volume mounted."

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  LUKS Encryption Setup Complete!"
echo "============================================="
echo ""
echo "  Encrypted device: ${DEVICE}"
echo "  Mapped to:        /dev/mapper/${CRYPT_NAME}"
echo "  Mounted at:       ${MOUNT_POINT}"
echo "  Keyfile:          ${KEYFILE}"
echo ""
echo "  CRITICAL — Backup Instructions:"
echo "  ─────────────────────────────────"
echo "  1. Back up the LUKS header:"
echo "     cryptsetup luksHeaderBackup ${DEVICE} \\"
echo "         --header-backup-file /root/bezalel_luks_header.bak"
echo ""
echo "  2. Copy the keyfile to a secure offline location:"
echo "     cp ${KEYFILE} /path/to/secure/usb/bezalel_keyfile"
echo ""
echo "  3. Record your LUKS passphrase in a password manager."
echo ""
echo "  Without these backups, data loss is PERMANENT if the"
echo "  header is corrupted or the keyfile is lost."
echo "============================================="
