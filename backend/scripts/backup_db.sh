#!/usr/bin/env bash
# backend/scripts/backup_db.sh
#
# Workstream 10 — daily backup of the CogniTrace Postgres database.
#
# Usage:
#     ./scripts/backup_db.sh
#
# Environment:
#     DATABASE_URL  — full Postgres URL, e.g. postgres://user:pass@host:5432/db
#     BACKUP_DIR    — output directory (default: ./backups)
#     RETENTION_DAYS — how long to keep local backups (default: 14)
#
# Cron entry (every day at 02:30):
#     30 2 * * * cd /app && ./scripts/backup_db.sh >> /var/log/cognitrace/backup.log 2>&1
#
# This script is intentionally simple. Pair it with an S3 / rclone sync
# for off-host durability — the local file is just the first hop.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/cognitrace_${TIMESTAMP}.sql.gz"

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL is not set" >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting backup → ${BACKUP_FILE}"

# pg_dump with --format=custom is preferred for partial restores, but
# plain-text gzip is the simplest portable format and what most small
# teams use. Adjust if you need parallel restore speed.
pg_dump \
    --no-owner \
    --no-privileges \
    --format=plain \
    --quote-all-identifiers \
    "${DATABASE_URL}" \
    | gzip -9 > "${BACKUP_FILE}"

BYTES=$(stat -c %s "${BACKUP_FILE}" 2>/dev/null || stat -f %z "${BACKUP_FILE}")
echo "[$(date -Iseconds)] Backup complete (${BYTES} bytes)"

# Retention sweep — delete anything older than ${RETENTION_DAYS}.
find "${BACKUP_DIR}" -type f -name "cognitrace_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete || true

echo "[$(date -Iseconds)] Retention sweep done (kept last ${RETENTION_DAYS} days)"
