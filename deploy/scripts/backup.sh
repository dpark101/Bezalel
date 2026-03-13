#!/usr/bin/env bash
# =============================================================================
# Bezalel.AI — Daily Backup Script
#
# Creates an encrypted PostgreSQL backup:
#   1. Dumps the database with pg_dump
#   2. Compresses with gzip
#   3. Encrypts with GPG (symmetric passphrase)
#   4. Stores in /data/backups/ with date-stamped filename
#   5. Cleans up backups older than 30 days
#
# Usage: bash backup.sh
#   Requires BACKUP_GPG_PASSPHRASE environment variable or
#   /data/bezalel/.backup_passphrase file.
#
# Intended to run via cron (see backup_cron).
# =============================================================================
set -euo pipefail

# ── Configuration ───────────────────────────────────────────────────────────
DB_NAME="bezalel"
DB_USER="bezalel"
BACKUP_DIR="/data/backups"
LOG_FILE="/data/bezalel/logs/backup.log"
DATE_STAMP=$(date +"%Y-%m-%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/bezalel_${DATE_STAMP}.sql.gz.gpg"
RETENTION_DAYS=30

# ── Passphrase for GPG encryption ──────────────────────────────────────────
PASSPHRASE_FILE="/data/bezalel/.backup_passphrase"
if [[ -n "${BACKUP_GPG_PASSPHRASE:-}" ]]; then
    GPG_PASSPHRASE="${BACKUP_GPG_PASSPHRASE}"
elif [[ -f "${PASSPHRASE_FILE}" ]]; then
    GPG_PASSPHRASE=$(cat "${PASSPHRASE_FILE}")
else
    echo "ERROR: No GPG passphrase found." | tee -a "${LOG_FILE}"
    echo "  Set BACKUP_GPG_PASSPHRASE env var or create ${PASSPHRASE_FILE}" | tee -a "${LOG_FILE}"
    exit 1
fi

# ── Logging helper ──────────────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

# ── Ensure directories exist ───────────────────────────────────────────────
mkdir -p "${BACKUP_DIR}"
mkdir -p "$(dirname "${LOG_FILE}")"

log "Starting backup..."

# ── 1. Dump, compress, and encrypt ─────────────────────────────────────────
log "Dumping database '${DB_NAME}'..."
pg_dump -U "${DB_USER}" -h localhost "${DB_NAME}" \
    | gzip \
    | gpg --batch --yes --symmetric --cipher-algo AES256 \
          --passphrase "${GPG_PASSPHRASE}" \
          --output "${BACKUP_FILE}"

if [[ $? -eq 0 && -f "${BACKUP_FILE}" ]]; then
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    log "Backup created: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    log "ERROR: Backup failed!"
    exit 1
fi

# ── 2. Clean up old backups ────────────────────────────────────────────────
log "Removing backups older than ${RETENTION_DAYS} days..."
DELETED=$(find "${BACKUP_DIR}" -name "bezalel_*.sql.gz.gpg" -mtime +${RETENTION_DAYS} -print -delete | wc -l)
log "Deleted ${DELETED} old backup(s)."

# ── 3. Summary ─────────────────────────────────────────────────────────────
TOTAL_BACKUPS=$(find "${BACKUP_DIR}" -name "bezalel_*.sql.gz.gpg" | wc -l)
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
log "Backup complete. ${TOTAL_BACKUPS} backup(s) stored, total size: ${TOTAL_SIZE}."
log "---"
